from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import dropbox
import requests
import random
import string
from datetime import datetime
import time  # নতুন ইম্পোর্ট যোগ করা হয়েছে
import threading  # নতুন ইম্পোর্ট যোগ করা হয়েছে

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'txt', 'pdf', 'mp3', 'wav'}

# ড্রপবক্স কনফিগারেশন
DROPBOX_TOKEN = "sl.u.AFk3iqFqBXp7iXCxltbwQOQvpGel6tXwLpwR95gGCsnx4YnCqdIZOvqNt5v8P1JWUzCiXfQlGodZgLYeA2qRbc2A52OV0jDcEzFgbWu00QxD6rHKdzZ6A6RkwI711uqkqEj3OZBUd0fExKVY8cUxbS5tupXnHS9y0lVG5h9k0mNUn0n4MBA5MckkxAsG4fpiUC6bxJQKNyd7SMeQ8O6-RIn30xvM7zOgh6xv9sd-2CHujpSQ1ITcPzj7AIs-QW-CzSDFDG9QXLquNJh2n9EsQJPDxlYJEH-2GYUzZ_KogshwOE6Z9fVXn_WiyqvSGNjM9pdTkeNNsXtAMjQ8ICwTLBmtFuXW6gJCx0mrEE-C4xDWWsZ2cx7wV19LfRJR0F3QFZm2JnK0ULcHDyApRQUf_wlpReMv841z7ywtXbEVMM89dDYAOtnL7FB3j95Ojx_jfcFp6qDpYOeJmTnRe-hmcemPFdQlBUesjVQy-2dDaa0iiDnGFUa9srwfufIZgIyp-_KIcYzq9ClkCWd86BvQdSpSt5j2DgHG3d5Wrwoo6izm0RgnOIiB46pAcwDJ469vtdIMdIVK6J5rJCeoWG7QxlvavclF3STfui3Sa7COfDtscVeBxqeUMjm6IzmgffNxoqqt3MdZiUae7UusbzciE4WosVaQJfCBxBySdvo1NZMUojqyBies9oCnEfeJZzCXI3jN_jr5uoF0k23AjZR9FNTNhl9RyQTMDYscYuYlvFtRcvG57udCTEd_KVVk-RIzmzkeIq2mhj-SEKL_4mtNJNw0aEXpqivEMFMA1aJ7hXmOQ-7Hn7BpQbuS8aIKskUERTJ71ThBJRWro3uHo1WxfCpq89v-rKeiSM_bSTE35n7YqEf8Dq1xJMCJxwWFOz0BIDnXJlAvJBshmvdfOdPDAsPpyF_vfqDKL63H3YKvd9jwQhlileDHIYw7PSAg61LLzpD9Q2CtB-XcJmHXpqe9yA8UojwF1MTRsX9ZLTMwi48tXKHe_rkRdCHQ3S3_jCm1hLzdR5swMe7n6bFT7ohEtzgAfLASF3vYEYTYovfMt0r9mANm6mSJLBtg0P1fKfdbqcoN1b0MbrHPCS0ogfBlsCUOHvb4nVDLq5Bjx_1dG1rBW9KoQbs4y12G6WDirF8kQhdNfTJVpObXKLlhI2bZJ2yVP-3rqD8FLmn1urlbLcEqS3HR3UDdMHV7gTXXcUeegMeLyIl3mC5sR6dzMU1mH2sl5wFHnb_IY1dh-zp3S7ALrKy2kDFtyNzglEk89iUKHVhoDRBH74gKWFlbQc4XftA8eWGiW-XFj_JrS54tDgONhd24Ce9wG2ijx21NOs1pg8CO54rgI-po5_4HUNbvvRzZB_1m-A-Tgqh0GsstE9ETC9kffy86ebbBS-xH1QwiyGEO-OckrINBX1SwVeAm_SXV"
dbx = dropbox.Dropbox(DROPBOX_TOKEN)

# ইউআইডি স্টোরেজ
generated_uuids = set()
uploaded_files = []

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

def upload_to_dropbox(url, quality):
    try:
        response = requests.get(url)
        response.raise_for_status()

        custom_uuid = generate_custom_uuid()
        ext = 'mp4'
        new_filename = f"{custom_uuid}_{quality}.{ext}"
        
        dbx_path = f"/{new_filename}"
        dbx.files_upload(response.content, dbx_path, mode=dropbox.files.WriteMode.overwrite)
        
        shared_link = dbx.sharing_create_shared_link_with_settings(dbx_path)
        download_link = shared_link.url.replace("dl=0", "raw=1")
        
        file_type = f"Video ({quality})"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        uploaded_files.append({
            'filename': new_filename,
            'link': download_link,
            'type': file_type,
            'timestamp': timestamp
        })
        
        return download_link
    except Exception as e:
        raise e

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
            dbx.files_upload(file.read(), dbx_path, mode=dropbox.files.WriteMode.overwrite)
            
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
                'x-rapidapi-key': '1be027dfcemshff3b8bc39162975p19fa5fjsnab9d1232788d'
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

            hd_link = upload_to_dropbox(hd_url, 'HD')
            sd_link = upload_to_dropbox(sd_url, 'SD')

            session['facebook_links'] = {'hd': hd_link, 'sd': sd_link}
            return redirect(url_for('index'))
        else:
            filename = video_url.split('/')[-1].split('?')[0]
            if not allowed_file(filename):
                return "Invalid file format!"
            
            ext = filename.rsplit('.', 1)[1].lower()
            custom_uuid = generate_custom_uuid()
            new_filename = f"{custom_uuid}.{ext}"
            
            response = requests.get(video_url)
            response.raise_for_status()
            
            dbx_path = f"/{new_filename}"
            dbx.files_upload(response.content, dbx_path, mode=dropbox.files.WriteMode.overwrite)
            
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
                'x-rapidapi-key': '1be027dfcemshff3b8bc39162975p19fa5fjsnab9d1232788d'
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

            hd_link = upload_to_dropbox(hd_url, 'HD')
            sd_link = upload_to_dropbox(sd_url, 'SD')

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
            
            response = requests.get(video_url)
            response.raise_for_status()
            
            dbx_path = f"/{new_filename}"
            dbx.files_upload(response.content, dbx_path, mode=dropbox.files.WriteMode.overwrite)
            
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
    url = "https://hello-if-qn39.onrender.com"  # আপনার এপ্লিকেশনের URL দিয়ে পরিবর্তন করুন
    while True:
        time.sleep(300)  # 5 মিনিট পরপর পিং
        try:
            requests.get(url)
        except Exception as e:
            print(f"Error: {e}")

if __name__ == '__main__':
    threading.Thread(target=keep_alive, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
