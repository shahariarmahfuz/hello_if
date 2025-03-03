from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import dropbox
import requests
import random
import string
from datetime import datetime
import time
import threading
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'txt', 'pdf', 'mp3', 'wav'}

# ড্রপবক্স কনফিগারেশন
DROPBOX_TOKEN = os.getenv("DROPBOX_TOKEN")
dbx = dropbox.Dropbox(DROPBOX_TOKEN)

# ইউআইডি স্টোরেজ
generated_uuids = set()
uploaded_files = []

CHUNK_SIZE = 4 * 1024 * 1024  # 4MB চাঙ্ক সাইজ

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def get_file_type(extension):
    if extension in {'png', 'jpg', 'jpeg', 'gif'}:
        return "Image"
    elif extension in {'mp4', 'mov'}:
        return "Video"
    elif extension in {'mp3', 'wav'}:
        return "Audio"
    elif extension in {'txt', 'pdf'}:
        return "Document"
    else:
        return "Other"

def generate_custom_uuid():
    characters = string.ascii_uppercase + string.digits
    while True:
        parts = [''.join(random.choices(characters, k=4)) for _ in range(4)]
        custom_uuid = '-'.join(parts)
        if custom_uuid not in generated_uuids:
            generated_uuids.add(custom_uuid)
            return custom_uuid

def upload_large_file(file_stream, dbx_path):
    # প্রথম চাঙ্ক পড়ুন
    first_chunk = file_stream.read(CHUNK_SIZE)
    if not first_chunk:
        raise ValueError("ফাইলটি খালি")

    # সেশন শুরু করুন
    upload_session = dbx.files_upload_session_start(first_chunk)
    cursor = dropbox.files.UploadSessionCursor(
        session_id=upload_session.session_id,
        offset=len(first_chunk)
    )
    commit = dropbox.files.CommitInfo(path=dbx_path, mode=dropbox.files.WriteMode.overwrite)

    # বাকি চাঙ্কগুলি আপলোড করুন
    while True:
        chunk = file_stream.read(CHUNK_SIZE)
        if not chunk:
            break
        dbx.files_upload_session_append_v2(chunk, cursor)
        cursor.offset += len(chunk)

    # সেশন সমাপ্ত করুন
    dbx.files_upload_session_finish(b'', cursor, commit)

def upload_from_url(url, dbx_path):
    response = requests.get(url, stream=True)
    response.raise_for_status()

    # প্রথম চাঙ্ক পড়ুন
    chunk_generator = response.iter_content(chunk_size=CHUNK_SIZE)
    first_chunk = next(chunk_generator)

    # সেশন শুরু করুন
    upload_session = dbx.files_upload_session_start(first_chunk)
    cursor = dropbox.files.UploadSessionCursor(
        session_id=upload_session.session_id,
        offset=len(first_chunk)
    )
    commit = dropbox.files.CommitInfo(path=dbx_path, mode=dropbox.files.WriteMode.overwrite)

    # বাকি চাঙ্কগুলি আপলোড করুন
    for chunk in chunk_generator:
        if chunk:
            dbx.files_upload_session_append_v2(chunk, cursor)
            cursor.offset += len(chunk)

    # সেশন সমাপ্ত করুন
    dbx.files_upload_session_finish(b'', cursor, commit)

@app.route('/')
def index():
    link = request.args.get('link')
    facebook_links = session.pop('facebook_links', None)
    return render_template('index.html', link=link, facebook_links=facebook_links)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(url_for('index'))

    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('index'))

    if file and allowed_file(file.filename):
        try:
            ext = file.filename.rsplit('.', 1)[1].lower()
            custom_uuid = generate_custom_uuid()
            new_filename = f"{custom_uuid}.{ext}"
            dbx_path = f"/{new_filename}"

            # ফাইল স্ট্রিম রিসেট করুন
            file.stream.seek(0)
            
            # বড় ফাইল আপলোড
            upload_large_file(file.stream, dbx_path)

            # শেয়ার লিংক তৈরি
            shared_link = dbx.sharing_create_shared_link_with_settings(dbx_path)
            download_link = shared_link.url.replace("dl=0", "raw=1")

            file_type = get_file_type(ext)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            uploaded_files.append({
                'filename': new_filename,
                'link': download_link,
                'type': file_type,
                'timestamp': timestamp
            })
            
            return redirect(url_for('index', link=download_link))
        except Exception as e:
            return f"ত্রুটি: {str(e)}"

    return 'Invalid file format!'

@app.route('/cloud_upload', methods=['POST'])
def cloud_upload():
    video_url = request.form.get('url')
    if not video_url:
        return redirect(url_for('index'))

    try:
        if 'facebook.com' in video_url:
            headers = {
                'x-rapidapi-host': 'facebook-reel-and-video-downloader.p.rapidapi.com',
                'x-rapidapi-key': 'a5037965bamsh20965b59564899bp13fff0jsn336df3e8acb4'
            }
            params = {'url': video_url}
            
            api_response = requests.get(
                'https://facebook-reel-and-video-downloader.p.rapidapi.com/app/main.php',
                headers=headers,
                params=params
            )
            api_response.raise_for_status()
            video_data = api_response.json()

            sd_url = video_data['links']['Download Low Quality']
            hd_url = video_data['links']['Download High Quality']

            # HD ভিডিও আপলোড
            custom_uuid_hd = generate_custom_uuid()
            dbx_path_hd = f"/{custom_uuid_hd}_HD.mp4"
            upload_from_url(hd_url, dbx_path_hd)
            hd_link = dbx.sharing_create_shared_link_with_settings(dbx_path_hd).url.replace("dl=0", "raw=1")

            # SD ভিডিও আপলোড
            custom_uuid_sd = generate_custom_uuid()
            dbx_path_sd = f"/{custom_uuid_sd}_SD.mp4"
            upload_from_url(sd_url, dbx_path_sd)
            sd_link = dbx.sharing_create_shared_link_with_settings(dbx_path_sd).url.replace("dl=0", "raw=1")

            session['facebook_links'] = {'hd': hd_link, 'sd': sd_link}
            return redirect(url_for('index'))
        else:
            filename = video_url.split('/')[-1].split('?')[0]
            if not allowed_file(filename):
                return "Invalid file format!"
            
            ext = filename.rsplit('.', 1)[1].lower()
            custom_uuid = generate_custom_uuid()
            new_filename = f"{custom_uuid}.{ext}"
            dbx_path = f"/{new_filename}"

            upload_from_url(video_url, dbx_path)

            shared_link = dbx.sharing_create_shared_link_with_settings(dbx_path)
            download_link = shared_link.url.replace("dl=0", "raw=1")
            
            file_type = get_file_type(ext)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            uploaded_files.append({
                'filename': new_filename,
                'link': download_link,
                'type': file_type,
                'timestamp': timestamp
            })
            
            return redirect(url_for('index', link=download_link))
    except Exception as e:
        return f"ত্রুটি: {str(e)}"

@app.route('/up')
def direct_upload():
    video_url = request.args.get('up')
    if not video_url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        if 'facebook.com' in video_url:
            headers = {
                'x-rapidapi-host': 'facebook-reel-and-video-downloader.p.rapidapi.com',
                'x-rapidapi-key': 'a5037965bamsh20965b59564899bp13fff0jsn336df3e8acb4'
            }
            params = {'url': video_url}
            
            api_response = requests.get(
                'https://facebook-reel-and-video-downloader.p.rapidapi.com/app/main.php',
                headers=headers,
                params=params
            )
            api_response.raise_for_status()
            video_data = api_response.json()

            sd_url = video_data['links']['Download Low Quality']
            hd_url = video_data['links']['Download High Quality']

            # HD ভিডিও আপলোড
            custom_uuid_hd = generate_custom_uuid()
            dbx_path_hd = f"/{custom_uuid_hd}_HD.mp4"
            upload_from_url(hd_url, dbx_path_hd)
            hd_link = dbx.sharing_create_shared_link_with_settings(dbx_path_hd).url.replace("dl=0", "raw=1")

            # SD ভিডিও আপলোড
            custom_uuid_sd = generate_custom_uuid()
            dbx_path_sd = f"/{custom_uuid_sd}_SD.mp4"
            upload_from_url(sd_url, dbx_path_sd)
            sd_link = dbx.sharing_create_shared_link_with_settings(dbx_path_sd).url.replace("dl=0", "raw=1")

            return jsonify({
                "success": True,
                "links": {
                    "hd": hd_link,
                    "sd": sd_link
                }
            })
        else:
            filename = video_url.split('/')[-1].split('?')[0]
            if not allowed_file(filename):
                return jsonify({"error": "Invalid file format"}), 400
            
            ext = filename.rsplit('.', 1)[1].lower()
            custom_uuid = generate_custom_uuid()
            new_filename = f"{custom_uuid}.{ext}"
            dbx_path = f"/{new_filename}"

            upload_from_url(video_url, dbx_path)

            shared_link = dbx.sharing_create_shared_link_with_settings(dbx_path)
            download_link = shared_link.url.replace("dl=0", "raw=1")
            
            file_type = get_file_type(ext)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            uploaded_files.append({
                'filename': new_filename,
                'link': download_link,
                'type': file_type,
                'timestamp': timestamp
            })
            
            return jsonify({
                "success": True,
                "link": download_link
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/links')
def show_links():
    return render_template('links.html', files=uploaded_files)

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "alive"})

def keep_alive():
    url = "https://your-app-name.onrender.com/ping"  # আপনার এপ্লিকেশনের URL দিয়ে পরিবর্তন করুন
    while True:
        time.sleep(300)
        try:
            requests.get(url)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == '__main__':
    threading.Thread(target=keep_alive, daemon=True).start()
    app.run(host='0.0.0.0', port=8000)
