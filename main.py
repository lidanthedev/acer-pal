# app.py
from flask import Flask, request, jsonify, render_template, redirect, url_for, abort, send_from_directory, flash
from Endpoint import Endpoint
import logging
import threading
import time
import uuid
import os
import requests
from urllib.parse import unquote
import re
from datetime import datetime

# --- Basic Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_change_me'


# --- Constants & Configuration ---
API_BASE_URL = 'https://acermovies.val.run/api'
DEFAULT_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}
# FIX 1: Use an absolute path for the default download directory.
# This makes the path relative to the script's location, which is much more reliable.
DEFAULT_DOWNLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'downloads'))

# FEATURE 3: Read the download directory from an environment variable.
# If 'DOWNLOAD_DIRECTORY' is not set, it falls back to the default.
DOWNLOAD_DIR = os.getenv('DOWNLOAD_DIRECTORY', DEFAULT_DOWNLOAD_DIR)

# --- In-memory storage for downloads ---
download_progress = {}

# --- Helper Functions ---

# Create the directory if it doesn't exist
if not os.path.exists(DOWNLOAD_DIR):
    try:
        os.makedirs(DOWNLOAD_DIR)
        logger.info(f"Created download directory at: {DOWNLOAD_DIR}")
    except OSError as e:
        logger.error(f"FATAL: Could not create download directory at '{DOWNLOAD_DIR}'. Please check permissions. Error: {e}")
        # In a real app, you might want to exit here if the directory is critical
        
def sanitize_filename(filename):
    """Removes illegal characters from a filename."""
    sanitized = re.sub(r'[\\/*?:"<>|]', "", filename)
    sanitized = sanitized.replace(' ', '_')
    # Limit filename length to avoid issues with file systems
    return sanitized[:200]

# --- Page Rendering Routes ---

@app.route('/')
def index():
    """Render the main search page."""
    return render_template('index.html')

# NEW ROUTE for the Settings Page
@app.route('/settings')
def settings():
    """Render the settings information page."""
    # Pass the currently configured download directory to the template
    return render_template('settings.html', download_dir=DOWNLOAD_DIR)
    
# ... (all other routes like /search, /qualities, /episodes remain the same) ...
@app.route('/search')
def search_results():
    search_query = request.args.get('query')
    if not search_query:
        return redirect(url_for('index'))
    endpoint = Endpoint(url=f'{API_BASE_URL}/search', headers=DEFAULT_HEADERS, method='POST', payload={"searchQuery": search_query})
    try:
        response_data, status_code, _ = endpoint.fetch()
        if status_code == 200 and response_data.get('searchResult'):
            return render_template('results.html', results=response_data['searchResult'], query=search_query)
        else:
            return render_template('results.html', results=[], query=search_query, error="No results found or API error.")
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return render_template('results.html', results=[], query=search_query, error=f"An error occurred: {e}")

@app.route('/qualities', methods=['POST'])
def select_quality():
    movie_url = request.form.get('url')
    movie_title = request.form.get('title')
    movie_image = request.form.get('image')
    if not movie_url:
        return redirect(url_for('index'))
    endpoint = Endpoint(url=f'{API_BASE_URL}/sourceQuality', headers=DEFAULT_HEADERS, method='POST', payload={"url": movie_url})
    try:
        response_data, status_code, _ = endpoint.fetch()
        if status_code == 200 and response_data.get('sourceQualityList'):
            movie_info = {'title': movie_title, 'image': movie_image}
            return render_template('qualities.html', qualities=response_data['sourceQualityList'], movie=movie_info)
        else:
            return "Could not fetch qualities for this source.", 404
    except Exception as e:
        logger.error(f"Quality fetch error: {str(e)}")
        return f"An error occurred while fetching qualities: {e}", 500

@app.route('/episodes', methods=['POST'])
def list_episodes():
    episodes_api_url = request.form.get('episodes_api_url')
    show_title = request.form.get('title')
    show_image = request.form.get('image')
    if not episodes_api_url:
        return "Error: No episodes URL provided.", 400
    endpoint = Endpoint(url=f'{API_BASE_URL}/sourceEpisodes', headers=DEFAULT_HEADERS, method='POST', payload={"url": episodes_api_url})
    try:
        response_data, status_code, _ = endpoint.fetch()
        if status_code == 200 and response_data.get('sourceEpisodes'):
            show_info = {'title': show_title, 'image': show_image}
            return render_template('episodes.html', episodes=response_data['sourceEpisodes'], show=show_info)
        else:
            return "Could not fetch episode list for this source.", 404
    except Exception as e:
        logger.error(f"Episode list fetch error: {str(e)}")
        return f"An error occurred while fetching episodes: {e}", 500

@app.route('/downloads_page')
def downloads_page():
    return render_template('downloads.html')

@app.route('/file_manager')
def file_manager():
    try:
        files = []
        for filename in sorted(os.listdir(DOWNLOAD_DIR)):
            filepath = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.isfile(filepath):
                file_stats = os.stat(filepath)
                files.append({
                    'name': filename,
                    'size': format_size(file_stats.st_size),
                    'modified': datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
        return render_template('file_manager.html', files=files)
    except Exception as e:
        logger.error(f"File manager error: Could not read directory '{DOWNLOAD_DIR}'. Error: {e}")
        # Pass the error to the template to be displayed to the user
        return render_template('file_manager.html', files=None, error=f"Could not read the downloads directory: {DOWNLOAD_DIR}. Please check that it exists and the application has permission to read it.")

# --- API and Action Routes ---
# ... (start_download, list_downloads, download_file, delete_file remain the same) ...
@app.route('/download', methods=['POST'])
def start_download():
    source_api_url = request.form.get('source_api_url')
    filename = request.form.get('filename', 'download.mp4')
    series_type = request.form.get('seriesType', 'episode')
    if not source_api_url:
        return "Error: No source URL provided.", 400
    try:
        url_endpoint = Endpoint(url=f'{API_BASE_URL}/sourceUrl', headers=DEFAULT_HEADERS, method='POST', payload={"url": source_api_url, "seriesType": series_type})
        response_data, status_code, _ = url_endpoint.fetch()
        if status_code != 200 or not response_data.get('sourceUrl'):
            return "Error: Could not retrieve the final download URL from the API.", 500
        direct_download_url = unquote(response_data['sourceUrl'])
        safe_filename = sanitize_filename(filename)
        download_id = str(uuid.uuid4())
        download_progress[download_id] = {'status': 'starting', 'progress': 0, 'speed': '0 KB/s', 'size': '0 MB', 'downloaded': 0, 'total': 0, 'start_time': time.time(), 'filename': safe_filename, 'error': None}
        thread = threading.Thread(target=download_file_thread, args=(download_id, direct_download_url, safe_filename))
        thread.daemon = True
        thread.start()
        logger.info(f"Download started: {download_id} - {safe_filename}")
        return redirect(url_for('downloads_page'))
    except Exception as e:
        logger.error(f"Download start error: {str(e)}")
        return f"A critical error occurred: {e}", 500

@app.route('/download_all_season', methods=['POST'])
def download_all_season():
    """Download all episodes of a season."""
    episodes_data = request.form.get('episodes_data')
    show_title = request.form.get('show_title', 'Unknown_Show')
    
    if not episodes_data:
        return "Error: No episodes data provided.", 400
    
    try:
        import json
        episodes = json.loads(episodes_data)
        
        if not episodes or not isinstance(episodes, list):
            return "Error: Invalid episodes data.", 400
        
        # Start downloads for all episodes
        download_ids = []
        for episode in episodes:
            episode_link = episode.get('link')
            episode_title = episode.get('title', 'Unknown_Episode')
            
            if not episode_link:
                logger.warning(f"Skipping episode with no link: {episode_title}")
                continue
            
            try:
                # Get the download URL for this episode
                url_endpoint = Endpoint(
                    url=f'{API_BASE_URL}/sourceUrl', 
                    headers=DEFAULT_HEADERS, 
                    method='POST', 
                    payload={"url": episode_link, "seriesType": "episode"}
                )
                response_data, status_code, _ = url_endpoint.fetch()
                
                if status_code != 200 or not response_data.get('sourceUrl'):
                    logger.error(f"Could not get download URL for episode: {episode_title}")
                    continue
                
                direct_download_url = unquote(response_data['sourceUrl'])
                safe_filename = sanitize_filename(f"{show_title}_{episode_title}.mp4")
                download_id = str(uuid.uuid4())
                
                download_progress[download_id] = {
                    'status': 'queued', 
                    'progress': 0, 
                    'speed': '0 KB/s', 
                    'size': '0 MB', 
                    'downloaded': 0, 
                    'total': 0, 
                    'start_time': time.time(), 
                    'filename': safe_filename, 
                    'error': None,
                    'is_season_download': True
                }
                
                download_ids.append(download_id)
                
                # Start download thread with a slight delay to avoid overwhelming the server
                thread = threading.Thread(target=download_file_thread, args=(download_id, direct_download_url, safe_filename))
                thread.daemon = True
                thread.start()
                
                # Small delay between starting downloads
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error setting up download for episode {episode_title}: {str(e)}")
                continue
        
        if download_ids:
            logger.info(f"Started season download with {len(download_ids)} episodes for: {show_title}")
            flash(f"Started downloading {len(download_ids)} episodes from the season!", "success")
        else:
            flash("No episodes could be queued for download.", "warning")
            
        return redirect(url_for('downloads_page'))
        
    except json.JSONDecodeError:
        return "Error: Invalid JSON data for episodes.", 400
    except Exception as e:
        logger.error(f"Season download error: {str(e)}")
        return f"A critical error occurred while starting season download: {e}", 500

@app.route('/downloads', methods=['GET'])
def list_downloads():
    downloads = []
    sorted_ids = sorted(download_progress.keys(), key=lambda k: download_progress[k]['start_time'], reverse=True)
    for download_id in sorted_ids:
        progress = download_progress[download_id]
        downloads.append({'id': download_id, 'filename': progress.get('filename', 'Unknown'), 'status': progress.get('status', 'unknown'), 'progress': f"{progress.get('progress', 0):.2f}", 'size': progress.get('size', '0 MB'), 'speed': progress.get('speed', '0 KB/s'), 'error': progress.get('error')})
    return jsonify({"downloads": downloads})

@app.route('/download_file/<path:filename>')
def download_file(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)

@app.route('/delete_file', methods=['POST'])
def delete_file():
    filename = request.form.get('filename')
    if not filename: abort(400)
    if '..' in filename or filename.startswith('/'): abort(400)
    filepath = os.path.join(DOWNLOAD_DIR, filename)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            flash(f"Successfully deleted '{filename}'", "success")
        except Exception as e:
            flash(f"Error deleting '{filename}': {e}", "danger")
    else:
        flash(f"File '{filename}' not found.", "warning")
    return redirect(url_for('file_manager'))

# --- Download Thread Logic & Helpers (no changes needed here) ---
def download_file_thread(download_id, url, filename):
    try:
        download_progress[download_id]['status'] = 'downloading'
        file_path = os.path.join(DOWNLOAD_DIR, filename)
        with requests.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            download_progress[download_id]['total'] = total_size
            downloaded = 0
            start_time = time.time()
            with open(file_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
                        downloaded += len(chunk)
                        current_time = time.time()
                        elapsed = current_time - start_time
                        speed = (downloaded / elapsed) if elapsed > 0 else 0
                        progress = (downloaded / total_size * 100) if total_size > 0 else 0
                        download_progress[download_id].update({'progress': progress, 'downloaded': downloaded, 'speed': format_speed(speed), 'size': format_size(total_size)})
        download_progress[download_id].update({'status': 'completed', 'progress': 100})
        logger.info(f"Download completed: {download_id} - {filename}")
    except requests.exceptions.RequestException as e:
        download_progress[download_id].update({'status': 'error', 'error': f'Network error: {str(e)}'})
    except Exception as e:
        download_progress[download_id].update({'status': 'error', 'error': str(e)})

def format_size(bytes_size):
    if bytes_size == 0: return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0: return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0

def format_speed(bytes_per_second):
    return f"{format_size(bytes_per_second)}/s"

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)