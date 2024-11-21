from flask import Flask, render_template, request, redirect, url_for, send_file, send_from_directory, flash, session, \
    after_this_request
import os
import face_recognition
import shutil
import zipfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = 'your_secret_key'

# סיומות קבצים מותרות
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def clear_uploads():
    folder = app.config['UPLOAD_FOLDER']
    if os.path.exists(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # ניקוי העלאות קודמות
        clear_uploads()
        session.clear()

        # קבלת תמונת הסלפי
        selfie = request.files.get('selfie')

        if 'selfie' not in request.files or selfie.filename == '':
            flash('אנא העלה תמונת סלפי.')
            return redirect(request.url)

        if selfie and allowed_file(selfie.filename):
            selfie_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(selfie.filename))
            selfie.save(selfie_path)
        else:
            flash('סוגי קבצים מותרים: png, jpg, jpeg, gif')
            return redirect(request.url)

        # קבלת קבצי התקייה הנבחרת
        files = request.files.getlist('folder')
        if not files:
            flash('אנא בחר תקייה.')
            return redirect(request.url)

        # שמירת הקבצים המועלים לתקייה זמנית
        folder_files = []
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                # יצירת תיקיות משנה אם קיימות
                sub_dir = os.path.dirname(file.filename)
                if sub_dir:
                    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], sub_dir), exist_ok=True)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
                file.save(file_path)
                folder_files.append(file_path)

        # עיבוד התמונות
        matched_images = process_uploaded_images(folder_files, selfie_path)

        # שמירת רשימת התמונות עם התאמה בסשן
        session['matched_images'] = matched_images

        return render_template('index.html', images=matched_images)
    else:
        return render_template('index.html')


def process_uploaded_images(folder_files, selfie_path):
    matched_images = []
    selfie_image = face_recognition.load_image_file(selfie_path)
    try:
        selfie_encoding = face_recognition.face_encodings(selfie_image)[0]
    except IndexError:
        flash('לא זוהה פנים בתמונת הסלפי.')
        return []

    for file_path in folder_files:
        try:
            unknown_image = face_recognition.load_image_file(file_path)
            unknown_encodings = face_recognition.face_encodings(unknown_image)
            for unknown_encoding in unknown_encodings:
                results = face_recognition.compare_faces([selfie_encoding], unknown_encoding)
                if results[0]:
                    relative_path = os.path.relpath(file_path, app.config['UPLOAD_FOLDER'])
                    matched_images.append(relative_path)
                    break  # מעבר לתמונה הבאה אם נמצא התאמה
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            continue
    return matched_images


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/download')
def download_all():
    matched_images = session.get('matched_images', [])
    if not matched_images:
        flash('אין תמונות להורדה.')
        return redirect(url_for('index'))

    zip_filename = 'matched_images.zip'
    zipf = zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED)
    try:
        for image in matched_images:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], image)
            zipf.write(file_path, arcname=image)
    finally:
        zipf.close()

    @after_this_request
    def cleanup(response):
        try:
            os.remove(zip_filename)
            # מחיקת תקיית uploads
            clear_uploads()
        except Exception as e:
            print(f"Error deleting files: {e}")
        return response

    return send_file(zip_filename, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True)
