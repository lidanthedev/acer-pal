# app.py
from pathlib import Path
from flask import Flask, request, jsonify, render_template, redirect, url_for, abort, send_from_directory, flash, session, g
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
from dotenv import load_dotenv
from functools import wraps
import shutil
import queue
import json
import fcntl  # For file locking
import atexit

# Load environment variables from .env file
load_dotenv()

# --- Basic Configuration ---
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your_super_secret_key_change_me')

# --- Authentication Configuration ---
AUTH_USERNAME = os.getenv('AUTH_USERNAME', 'admin')
AUTH_PASSWORD = os.getenv('AUTH_PASSWORD', 'password123')

# --- Server Configuration ---
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 5000))
DEBUG = os.getenv('FLASK_DEBUG', '0').lower() in ['true', '1', 'yes']

def require_auth(f):
    """Decorator to require basic authentication for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'authenticated' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# --- Constants & Configuration ---
API_BASE_URL = os.getenv('API_BASE_URL', 'https://acermovies.val.run/api')
DEFAULT_HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}
# FIX 1: Use an absolute path for the default download directory.
# This makes the path relative to the script's location, which is much more reliable.
DEFAULT_DOWNLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'downloads'))
DEFAULT_COMPLETED_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'completed'))

# FEATURE 3: Read the download directory from an environment variable.
# If 'DOWNLOAD_DIRECTORY' is not set, it falls back to the default.
DOWNLOAD_DIR = Path(os.getenv('DOWNLOAD_DIRECTORY', DEFAULT_DOWNLOAD_DIR))
COMPLETED_DIR = Path(os.getenv('COMPLETED_DIRECTORY', DEFAULT_COMPLETED_DIR))

# Sonarr blackhole configuration
ENABLE_AUTO_MOVE = os.getenv('ENABLE_AUTO_MOVE', 'true').lower() in ['true', '1', 'yes']

# --- In-memory storage for downloads ---
download_progress = {}
season_processing = {}  # Track background season processing status
search_history = []  # Track recent searches (last 5)

# --- Download Queue System ---
MAX_CONCURRENT_DOWNLOADS = 4
download_queue = queue.Queue()  # Queue for pending downloads
active_downloads = set()  # Track currently active download IDs
queue_lock = threading.Lock()  # Thread-safe operations on active_downloads

APP_DATA_FOLDER = Path('app_data')
APP_DATA_FILE = APP_DATA_FOLDER / 'app_data.json'

# --- Data Persistence Functions ---
def save_data():
    """Save download progress and queue state when app exits."""
    try:
        logger.info("Saving app data...")
        
        # Create app data folder if it doesn't exist
        APP_DATA_FOLDER.mkdir(parents=True, exist_ok=True)
        
        data_to_save = {
            'download_progress': download_progress,
            'download_queue': list(download_queue.queue),
            'active_downloads': list(active_downloads),
            'search_history': search_history
        }
        
        # Use file locking to prevent race conditions between multiple processes
        lock_file = APP_DATA_FILE.with_suffix('.lock')
        
        # Try to acquire exclusive lock
        try:
            with lock_file.open('w') as lock_fd:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                
                # Check if we should save (only if we have data or file doesn't exist)
                if any(data_to_save.values()) or not APP_DATA_FILE.exists():
                    logger.debug(f"App data to save: {data_to_save}")
                    
                    # Write to a temporary file first, then move to prevent corruption
                    temp_file = APP_DATA_FILE.with_suffix('.tmp')
                    with temp_file.open('w') as f:
                        json.dump(data_to_save, f, indent=2)
                    temp_file.replace(APP_DATA_FILE)
                    
                    logger.info("App data saved successfully.")
                else:
                    logger.debug("No meaningful data to save, skipping")
                
                # Lock is automatically released when file is closed
                
        except (OSError, IOError) as lock_error:
            # Another process is already saving, skip this save
            logger.debug(f"Another process is saving data, skipping: {lock_error}")
            return
        
        # Clean up lock file
        try:
            lock_file.unlink(missing_ok=True)
        except:
            pass  # Ignore cleanup errors
            
    except Exception as e:
        logger.error(f"Failed to save data: {e}")

def load_data():
    """Load download progress and queue state when app starts."""
    global search_history
    try:
        logger.info("Loading app data...")
        if not APP_DATA_FILE.exists():
            logger.info("No existing app data file found. Starting fresh.")
            return
        with APP_DATA_FILE.open('r') as f:
            data_loaded = json.load(f)
            download_progress.update(data_loaded.get('download_progress', {}))
            for item in data_loaded.get('download_queue', []):
                download_queue.put(item)
            active_downloads.update(data_loaded.get('active_downloads', []))
            search_history.extend(data_loaded.get('search_history', []))
        logger.info("App data loaded successfully.")
    except Exception as e:
        logger.error(f"Failed to load data: {e}")

# --- Helper Functions ---
        
def sanitize_filename(filename):
    """Removes illegal characters from a filename."""
    # Remove invalid characters and replace spaces with underscores
    sanitized = re.sub(r'[\\/*?:"<>|]', "", filename)
    sanitized = sanitized.replace(' ', '_')
    # Limit filename length to avoid issues with file systems
    return sanitized[:200]

def add_to_search_history(query):
    """Add a search query to the search history, keeping only the last 5."""
    global search_history
    
    # Remove query if it already exists to avoid duplicates
    if query in search_history:
        search_history.remove(query)
    
    # Add to the beginning of the list
    search_history.insert(0, query)
    
    # Keep only the last 5 searches
    search_history = search_history[:5]
    
    logger.debug(f"Updated search history: {search_history}")

def extract_clean_show_name(full_title):
    """Extract just the show name from a messy torrent title."""
    logger.info(f"Extracting clean show name from: '{full_title}'")
    
    # Common patterns to extract show name from torrent titles
    # Try different patterns in order of specificity
    
    # Pattern 1: Show Name (Season X...) or Show Name (Complete Series)
    pattern1 = re.match(r'^([^(]+?)\s*\([Ss]eason|^([^(]+?)\s*\([Cc]omplete', full_title)
    if pattern1:
        show_name = (pattern1.group(1) or pattern1.group(2)).strip()
        logger.info(f"Pattern 1 matched: '{show_name}'")
        return clean_show_title_string(show_name)
    
    # Pattern 2: Show Name - Season X or Show Name Season X
    pattern2 = re.match(r'^(.*?)\s*[-–]\s*[Ss]eason\s*\d+|^(.*?)\s+[Ss]eason\s*\d+', full_title)
    if pattern2:
        show_name = (pattern2.group(1) or pattern2.group(2)).strip()
        logger.info(f"Pattern 2 matched: '{show_name}'")
        return clean_show_title_string(show_name)
    
    # Pattern 3: Show Name S01-S12 or Show Name S01E01
    pattern3 = re.match(r'^(.*?)\s*S\d+', full_title, re.IGNORECASE)
    if pattern3:
        show_name = pattern3.group(1).strip()
        logger.info(f"Pattern 3 matched: '{show_name}'")
        return clean_show_title_string(show_name)
    
    # Pattern 4: Remove common quality/format indicators from the end and take the first part
    # Remove things like [720p], {English}, (2019), etc.
    cleaned = re.sub(r'\s*[\[\({].*?[\]\)}]\s*', ' ', full_title)
    # Remove quality indicators
    cleaned = re.sub(r'\s*(720p|1080p|4K|HDTV|BluRay|WEB-DL|REMUX).*$', '', cleaned, flags=re.IGNORECASE)
    # Take everything before the first season indicator or year
    cleaned = re.sub(r'\s*(S\d+|Season\s*\d+|\d{4}).*$', '', cleaned, flags=re.IGNORECASE)
    
    show_name = cleaned.strip()
    if show_name:
        logger.info(f"Pattern 4 (cleanup) matched: '{show_name}'")
        return clean_show_title_string(show_name)
    
    # Fallback: just clean the original
    logger.warning(f"No pattern matched, using fallback for: '{full_title}'")
    return clean_show_title_string(full_title)

def clean_show_title_string(title):
    """Clean a show title string for filename use."""
    # Remove invalid filename characters
    cleaned = re.sub(r'[\\/*?:"<>|]', '', title)
    # Replace spaces with dots, but clean up multiple dots
    cleaned = cleaned.replace(' ', '.')
    cleaned = re.sub(r'\.+', '.', cleaned)  # Replace multiple dots with single dot
    # Remove leading/trailing dots
    cleaned = cleaned.strip('.')
    return cleaned

def create_episode_filename_from_context(show_title, episode_title, selected_quality, original_filename):
    """Create a clean, simple episode filename: Show.Title.S##E##.Quality.ext"""
    logger.info(f"Creating episode filename from context: show_title='{show_title}', episode_title='{episode_title}', selected_quality='{selected_quality}', original_filename='{original_filename}'")
    try:
        # Extract file extension from original filename
        _, ext = os.path.splitext(original_filename)
        if not ext or ext in ['.720p', '.1080p', '.4K']:  # Handle cases where quality is mistaken for extension
            ext = '.mp4'
        
        # Extract just the actual show name from the potentially messy title
        clean_show_title = extract_clean_show_name(show_title.strip())
        
        # Extract season and episode from episode_title
        season_num = 1  # default
        episode_num = 1  # default
        
        # Look for SxxExx pattern first
        sxxexx_match = re.search(r'S(\d+)E(\d+)', episode_title, re.IGNORECASE)
        if sxxexx_match:
            season_num = int(sxxexx_match.group(1))
            episode_num = int(sxxexx_match.group(2))
        else:
            # Look for Season X Episode Y pattern
            season_match = re.search(r'Season[_\s](\d+)', episode_title, re.IGNORECASE)
            if season_match:
                season_num = int(season_match.group(1))
            
            episode_match = re.search(r'Episode[_\s](\d+)', episode_title, re.IGNORECASE)
            if episode_match:
                episode_num = int(episode_match.group(1))
        
        # Extract season from selected_quality if not found in episode title
        if 'Season' in selected_quality:
            season_quality_match = re.search(r'Season\s*(\d+)', selected_quality, re.IGNORECASE)
            if season_quality_match:
                season_num = int(season_quality_match.group(1))
        
        # Extract only the resolution from selected_quality (keep it simple)
        quality = '720p'  # default
        resolution_priorities = ['4K', '2160p', '1080p', '720p', '480p']
        for res in resolution_priorities:
            if re.search(res, selected_quality, re.IGNORECASE):
                quality = res
                break
        
        # Format the filename: Show.Title.S##E##.Quality.ext
        season_str = f"S{season_num:02d}"
        episode_str = f"E{episode_num:02d}"
        
        formatted_filename = f"{clean_show_title}.{season_str}{episode_str}.{quality}{ext}"
        
        logger.info(f"Simple filename: '{show_title}' + '{episode_title}' + '{selected_quality}' -> '{formatted_filename}'")
        return formatted_filename
        
    except Exception as e:
        logger.warning(f"Failed to create episode filename from context: {e}")
        # Fall back to original sanitization
        return sanitize_filename(original_filename)

def create_movie_filename_from_context(movie_title, selected_quality, original_filename):
    """Create a clean movie filename from UI context by removing file size brackets."""
    logger.info(f"Creating movie filename from context: movie_title='{movie_title}', selected_quality='{selected_quality}'")
    try:
        # Extract file extension from original filename
        _, ext = os.path.splitext(original_filename)
        if not ext or ext in ['.720p', '.1080p', '.4K']:  # Handle cases where quality is mistaken for extension
            ext = '.mp4'
        
        # Use the selected_quality (UI context) which is already clean
        # Just remove file size information in brackets like [1.8GB], [470MB], etc.
        clean_title = selected_quality.strip()
        
        # Remove file size brackets: [1.8GB], [470MB], [2.6GB], etc.
        clean_title = re.sub(r'\s*\[[^\]]*(?:MB|GB|KB)\][^\]]*', '', clean_title, flags=re.IGNORECASE)
        
        # Remove any remaining empty brackets or extra spaces
        clean_title = re.sub(r'\s*\[\s*\]\s*', '', clean_title)
        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
        
        # Sanitize for filesystem
        safe_title = clean_title.replace(':', ' -').replace('/', ' ').replace('\\', ' ')
        safe_title = re.sub(r'[<>"|?*]', '', safe_title)
        safe_title = re.sub(r'\s+', ' ', safe_title).strip()
        
        formatted_filename = f"{safe_title}{ext}"
        
        logger.info(f"Movie filename: '{selected_quality}' -> '{formatted_filename}'")
        return formatted_filename
        
    except Exception as e:
        logger.warning(f"Failed to create movie filename from context: {e}")
        # Fall back to original sanitization
        return sanitize_filename(original_filename)

# --- Authentication Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user authentication."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == AUTH_USERNAME and password == AUTH_PASSWORD:
            session['authenticated'] = True
            flash('Successfully logged in!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password!', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Handle user logout."""
    session.pop('authenticated', None)
    flash('Successfully logged out!', 'info')
    return redirect(url_for('login'))

# --- Page Rendering Routes ---

@app.route('/')
@require_auth
def index():
    """Render the main search page."""
    return render_template('index.html', search_history=search_history)

# NEW ROUTE for the Settings Page
@app.route('/settings')
@require_auth
def settings():
    """Render the settings information page."""
    # Pass the currently configured download directory to the template
    return render_template('settings.html', download_dir=DOWNLOAD_DIR)
    
# ... (all other routes like /search, /qualities, /episodes remain the same) ...
@app.route('/search')
@require_auth
def search_results():
    search_query = request.args.get('query')
    if not search_query:
        return redirect(url_for('index'))
    
    # Add to search history
    add_to_search_history(search_query)
    
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
@require_auth
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
@require_auth
def list_episodes():
    episodes_api_url = request.form.get('episodes_api_url')
    show_title = request.form.get('title')
    show_image = request.form.get('image')
    selected_quality = request.form.get('quality')  # Get the selected quality/season info
    if not episodes_api_url:
        return "Error: No episodes URL provided.", 400
    endpoint = Endpoint(url=f'{API_BASE_URL}/sourceEpisodes', headers=DEFAULT_HEADERS, method='POST', payload={"url": episodes_api_url})
    try:
        response_data, status_code, _ = endpoint.fetch()
        if status_code == 200 and response_data.get('sourceEpisodes'):
            show_info = {'title': show_title, 'image': show_image}
            return render_template('episodes.html', episodes=response_data['sourceEpisodes'], show=show_info, selected_quality=selected_quality)
        else:
            return "Could not fetch episode list for this source.", 404
    except Exception as e:
        logger.error(f"Episode list fetch error: {str(e)}")
        return f"An error occurred while fetching episodes: {e}", 500

@app.route('/downloads_page')
@require_auth
def downloads_page():
    return render_template('downloads.html')

@app.route('/file_manager')
@require_auth
def file_manager():
    try:
        # Get files from downloads directory
        downloads_files = []
        if os.path.exists(DOWNLOAD_DIR):
            for filename in sorted(os.listdir(DOWNLOAD_DIR)):
                filepath = os.path.join(DOWNLOAD_DIR, filename)
                if os.path.isfile(filepath):
                    file_stats = os.stat(filepath)
                    downloads_files.append({
                        'name': filename,
                        'size': format_size(file_stats.st_size),
                        'modified': datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                        'location': 'downloads'
                    })
        
        # Get files from completed directory
        completed_files = []
        if os.path.exists(COMPLETED_DIR):
            for filename in sorted(os.listdir(COMPLETED_DIR)):
                filepath = os.path.join(COMPLETED_DIR, filename)
                if os.path.isfile(filepath):
                    file_stats = os.stat(filepath)
                    completed_files.append({
                        'name': filename,
                        'size': format_size(file_stats.st_size),
                        'modified': datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                        'location': 'completed'
                    })
        
        return render_template('file_manager.html', 
                             downloads_files=downloads_files, 
                             completed_files=completed_files,
                             auto_move_enabled=ENABLE_AUTO_MOVE)
    except Exception as e:
        logger.error(f"File manager error: Could not read directories. Error: {e}")
        return render_template('file_manager.html', 
                             downloads_files=None, 
                             completed_files=None,
                             error=f"Could not read the directories. Please check that they exist and the application has permission to read them.",
                             auto_move_enabled=ENABLE_AUTO_MOVE)

# --- API and Action Routes ---
# ... (start_download, list_downloads, download_file, delete_file remain the same) ...
@app.route('/download', methods=['POST'])
@require_auth
def start_download():
    source_api_url = request.form.get('source_api_url')
    filename = request.form.get('filename', 'download.mp4')
    series_type = request.form.get('seriesType', 'episode')
    
    # Get additional context for TV episodes
    show_title = request.form.get('show_title')
    episode_title = request.form.get('episode_title')
    selected_quality = request.form.get('selected_quality')
    
    if not source_api_url:
        return "Error: No source URL provided.", 400
    try:
        url_endpoint = Endpoint(url=f'{API_BASE_URL}/sourceUrl', headers=DEFAULT_HEADERS, method='POST', payload={"url": source_api_url, "seriesType": series_type})
        response_data, status_code, _ = url_endpoint.fetch()
        if status_code != 200 or not response_data.get('sourceUrl'):
            return "Error: Could not retrieve the final download URL from the API.", 500
        direct_download_url = unquote(response_data['sourceUrl'])
        
        # Create smart filename based on context
        if series_type == 'episode' and show_title and episode_title and selected_quality:
            safe_filename = create_episode_filename_from_context(show_title, episode_title, selected_quality, filename)
            logger.info(f"Generated clean episode filename: {safe_filename}")
        elif series_type == 'movie' and show_title and selected_quality:
            safe_filename = create_movie_filename_from_context(show_title, selected_quality, filename)
            logger.info(f"Generated clean movie filename: {safe_filename}")
        else:
            safe_filename = sanitize_filename(filename)
            logger.info(f"Using sanitized filename: {safe_filename}")
        
        download_id = str(uuid.uuid4())
        download_progress[download_id] = {'status': 'starting', 'progress': 0, 'speed': '0 KB/s', 'size': '0 MB', 'downloaded': 0, 'total': 0, 'start_time': time.time(), 'filename': safe_filename, 'error': None}
        queue_download(download_id, direct_download_url, safe_filename)
        logger.info(f"Download queued: {download_id} - {safe_filename}")
        return redirect(url_for('downloads_page'))
        return redirect(url_for('downloads_page'))
    except Exception as e:
        logger.error(f"Download start error: {str(e)}")
        return f"A critical error occurred: {e}", 500

def process_season_downloads_background(episodes_data, show_title, selected_quality):
    """Process all season episodes in background to avoid worker timeout."""
    processing_id = str(uuid.uuid4())
    
    try:
        import json
        episodes = json.loads(episodes_data)
        
        if not episodes or not isinstance(episodes, list):
            logger.error("Invalid episodes data for season download")
            return
        
        # Track season processing status
        season_processing[processing_id] = {
            'show_title': show_title,
            'total_episodes': len(episodes),
            'processed_episodes': 0,
            'successful_downloads': 0,
            'start_time': time.time(),
            'status': 'processing'
        }
        
        logger.info(f"Processing season download in background: {show_title} ({len(episodes)} episodes)")
        
        # Start downloads for all episodes
        download_ids = []
        successful_downloads = 0
        
        for i, episode in enumerate(episodes):
            episode_link = episode.get('link')
            episode_title = episode.get('title', 'Unknown_Episode')
            
            # Update processing status
            season_processing[processing_id]['processed_episodes'] = i + 1
            
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
                # Use context-based filename generation for better formatting
                if selected_quality:
                    safe_filename = create_episode_filename_from_context(show_title, episode_title, selected_quality, f"{episode_title}.mp4")
                else:
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
                    'is_season_download': True,
                    'season_processing_id': processing_id
                }
                
                download_ids.append(download_id)
                
                # Queue download instead of starting immediately to respect concurrency limits
                queue_download(download_id, direct_download_url, safe_filename)
                
                successful_downloads += 1
                season_processing[processing_id]['successful_downloads'] = successful_downloads
                logger.info(f"Queued download {successful_downloads}/{len(episodes)}: {safe_filename}")
                
                # Small delay between queuing downloads
                time.sleep(0.2)
                
            except Exception as e:
                logger.error(f"Error setting up download for episode {episode_title}: {str(e)}")
                continue
        
        # Mark processing as completed
        season_processing[processing_id]['status'] = 'completed'
        season_processing[processing_id]['end_time'] = time.time()
        
        logger.info(f"Completed season download setup: {successful_downloads} episodes queued for {show_title}")
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON data for episodes in background processing")
        if processing_id in season_processing:
            season_processing[processing_id]['status'] = 'error'
            season_processing[processing_id]['error'] = 'Invalid JSON data'
    except Exception as e:
        logger.error(f"Season background processing error: {str(e)}")
        if processing_id in season_processing:
            season_processing[processing_id]['status'] = 'error'
            season_processing[processing_id]['error'] = str(e)

@app.route('/download_all_season', methods=['POST'])
@require_auth
def download_all_season():
    """Download all episodes of a season - starts background processing and redirects immediately."""
    episodes_data = request.form.get('episodes_data')
    show_title = request.form.get('show_title', 'Unknown_Show')
    selected_quality = request.form.get('selected_quality')
    
    if not episodes_data:
        flash("Error: No episodes data provided.", "error")
        return redirect(url_for('index'))
    
    try:
        import json
        episodes = json.loads(episodes_data)
        
        if not episodes or not isinstance(episodes, list):
            flash("Error: Invalid episodes data.", "error")
            return redirect(url_for('index'))
        
        # Start background processing
        thread = threading.Thread(
            target=process_season_downloads_background, 
            args=(episodes_data, show_title, selected_quality)
        )
        thread.daemon = True
        thread.start()
        
        flash(f"Started processing {len(episodes)} episodes from {show_title} in the background. Downloads will appear in the downloads page as they are prepared.", "info")
        logger.info(f"Started background season processing for: {show_title} ({len(episodes)} episodes)")
        
        return redirect(url_for('downloads_page'))
        
    except json.JSONDecodeError:
        flash("Error: Invalid episode data format.", "error")
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Season download error: {str(e)}")
        flash(f"Error starting season download: {str(e)}", "error")
        return redirect(url_for('index'))

@app.route('/download_selected_episodes', methods=['POST'])
@require_auth
def download_selected_episodes():
    """Download user-selected episodes from a season."""
    selected_episodes_data = request.form.get('selected_episodes')
    show_title = request.form.get('show_title', 'Unknown_Show')
    selected_quality = request.form.get('selected_quality')
    
    if not selected_episodes_data:
        flash("Error: No episodes selected.", "error")
        return redirect(url_for('index'))
    
    try:
        import json
        selected_episodes = json.loads(selected_episodes_data)
        
        if not selected_episodes or not isinstance(selected_episodes, list):
            flash("Error: Invalid episode selection data.", "error")
            return redirect(url_for('index'))
        
        # Start background processing for selected episodes
        thread = threading.Thread(
            target=process_season_downloads_background, 
            args=(selected_episodes_data, show_title, selected_quality)
        )
        thread.daemon = True
        thread.start()
        
        episode_count = len(selected_episodes)
        flash(f"Started processing {episode_count} selected episode{'s' if episode_count != 1 else ''} from {show_title} in the background. Downloads will appear in the downloads page as they are prepared.", "info")
        logger.info(f"Started background processing for {episode_count} selected episodes: {show_title}")
        
        return redirect(url_for('downloads_page'))
        
    except json.JSONDecodeError:
        flash("Error: Invalid episode selection format.", "error")
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Selected episodes download error: {str(e)}")
        flash(f"Error starting selected episodes download: {str(e)}", "error")
        return redirect(url_for('index'))

@app.route('/downloads', methods=['GET'])
@require_auth
def list_downloads():
    downloads = []
    sorted_ids = sorted(download_progress.keys(), key=lambda k: download_progress[k]['start_time'], reverse=True)
    for download_id in sorted_ids:
        progress = download_progress[download_id]
        downloads.append({'id': download_id, 'filename': progress.get('filename', 'Unknown'), 'status': progress.get('status', 'unknown'), 'progress': f"{progress.get('progress', 0):.2f}", 'size': progress.get('size', '0 MB'), 'speed': progress.get('speed', '0 KB/s'), 'error': progress.get('error')})
    
    # Add season processing status
    season_processing_list = []
    for processing_id, processing_info in season_processing.items():
        season_processing_list.append({
            'id': processing_id,
            'show_title': processing_info.get('show_title', 'Unknown'),
            'status': processing_info.get('status', 'unknown'),
            'processed_episodes': processing_info.get('processed_episodes', 0),
            'total_episodes': processing_info.get('total_episodes', 0),
            'successful_downloads': processing_info.get('successful_downloads', 0),
            'start_time': processing_info.get('start_time', 0),
            'error': processing_info.get('error')
        })
    
    return jsonify({
        "downloads": downloads,
        "season_processing": season_processing_list,
        "queue_status": {
            "active_downloads": len(active_downloads),
            "max_concurrent": MAX_CONCURRENT_DOWNLOADS,
            "queued_downloads": download_queue.qsize(),
            "available_slots": MAX_CONCURRENT_DOWNLOADS - len(active_downloads)
        }
    })

@app.route('/download_file/<location>/<path:filename>')
@require_auth
def download_file(location, filename):
    if location == 'downloads':
        return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)
    elif location == 'completed':
        return send_from_directory(COMPLETED_DIR, filename, as_attachment=True)
    else:
        abort(404)

@app.route('/delete_file', methods=['POST'])
@require_auth
def delete_file():
    filename = request.form.get('filename')
    location = request.form.get('location', 'downloads')
    
    if not filename: 
        abort(400)
    if '..' in filename or filename.startswith('/'): 
        abort(400)
    
    # Determine the correct directory
    if location == 'downloads':
        directory = DOWNLOAD_DIR
    elif location == 'completed':
        directory = COMPLETED_DIR
    else:
        flash(f"Invalid location: {location}", "danger")
        return redirect(url_for('file_manager'))
    
    filepath = os.path.join(directory, filename)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            flash(f"Successfully deleted '{filename}' from {location}", "success")
        except Exception as e:
            flash(f"Error deleting '{filename}': {e}", "danger")
    else:
        flash(f"File '{filename}' not found in {location}.", "warning")
    
    return redirect(url_for('file_manager'))

@app.route('/move_to_completed', methods=['POST'])
@require_auth
def move_to_completed():
    filename = request.form.get('filename')
    
    if not filename:
        abort(400)
    if '..' in filename or filename.startswith('/'):
        abort(400)
    
    source_path = os.path.join(DOWNLOAD_DIR, filename)
    dest_path = os.path.join(COMPLETED_DIR, filename)
    
    if not os.path.exists(source_path):
        flash(f"File '{filename}' not found in downloads directory.", "warning")
        return redirect(url_for('file_manager'))
    
    if os.path.exists(dest_path):
        flash(f"File '{filename}' already exists in completed directory.", "warning")
        return redirect(url_for('file_manager'))
    
    try:
        shutil.move(source_path, dest_path)
        flash(f"Successfully moved '{filename}' to completed directory.", "success")
        logger.info(f"Manually moved file to completed: {filename}")
    except Exception as e:
        flash(f"Error moving '{filename}' to completed directory: {e}", "danger")
        logger.error(f"Failed to manually move file: {filename}, Error: {e}")
    
    return redirect(url_for('file_manager'))

# --- Download Thread Logic & Helpers (no changes needed here) ---

def queue_download(download_id, url, filename):
    """Add a download to the queue or start it immediately if slots are available."""
    with queue_lock:
        if len(active_downloads) < MAX_CONCURRENT_DOWNLOADS:
            # Start download immediately
            active_downloads.add(download_id)
            download_progress[download_id]['status'] = 'downloading'
            thread = threading.Thread(target=managed_download_thread, args=(download_id, url, filename))
            thread.daemon = True
            thread.start()
            logger.info(f"Started download immediately: {download_id} -> {filename}")
        else:
            # Add to queue
            download_queue.put((download_id, url, filename))
            download_progress[download_id]['status'] = 'queued'
            logger.info(f"Queued download: {download_id} -> {filename} (Queue size: {download_queue.qsize()})")

def process_download_queue():
    """Process the download queue when a slot becomes available."""
    with queue_lock:
        while len(active_downloads) < MAX_CONCURRENT_DOWNLOADS and not download_queue.empty():
            try:
                download_id, url, filename = download_queue.get_nowait()
                active_downloads.add(download_id)
                download_progress[download_id]['status'] = 'downloading'
                thread = threading.Thread(target=managed_download_thread, args=(download_id, url, filename))
                thread.daemon = True
                thread.start()
                logger.info(f"Started queued download: {download_id} -> {filename} (Queue size: {download_queue.qsize()})")
            except queue.Empty:
                break

def managed_download_thread(download_id, url, filename):
    """Wrapper for download_file_thread that manages the active downloads set."""
    try:
        download_file_thread(download_id, url, filename)
    finally:
        # Always remove from active downloads when done, regardless of success/failure
        with queue_lock:
            active_downloads.discard(download_id)
        # Process queue to start next download
        process_download_queue()

def download_file_thread(download_id, url, filename):
    try:
        download_progress[download_id]['status'] = 'downloading'
        # Always use our clean filename, ignore any server-provided filename
        file_path = os.path.join(DOWNLOAD_DIR, filename)
        logger.info(f"Starting download: {download_id} -> {filename}")
        
        # Ensure the filename is exactly what we want by creating the file directly
        with requests.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            download_progress[download_id]['total'] = total_size
            downloaded = 0
            start_time = time.time()
            
            # Create the file with our exact filename, ignoring Content-Disposition
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
        
        # Download completed successfully - file should already have our clean filename
        download_progress[download_id].update({'status': 'moving', 'progress': 100})
        logger.info(f"Download completed with clean filename: {download_id} - {filename}")
        
        # Verify the file exists with our expected name
        if not os.path.exists(file_path):
            logger.error(f"Downloaded file not found at expected path: {file_path}")
            download_progress[download_id].update({'status': 'error', 'error': 'File not found after download'})
            return
        
        # Move file to completed directory if auto-move is enabled (for Sonarr integration)
        if ENABLE_AUTO_MOVE:
            try:
                completed_file_path = os.path.join(COMPLETED_DIR, filename)
                shutil.move(file_path, completed_file_path)
                download_progress[download_id]['status'] = 'completed'
                download_progress[download_id]['completed_path'] = completed_file_path
                logger.info(f"File moved to completed directory: {filename}")
            except Exception as e:
                logger.error(f"Failed to move file to completed directory: {e}")
                download_progress[download_id]['move_error'] = str(e)
                # File stays in downloads directory if move fails
        
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

# Create the Flask application instance for WSGI
application = app

# Load data on startup and register save on exit
_init_called = False  # Prevent multiple initializations

def init():
    global _init_called
    
    # Prevent multiple initializations (important for Gunicorn workers)
    if _init_called:
        logger.debug("init() already called, skipping duplicate initialization")
        return
    
    _init_called = True
    
    # Create the directories if they don't exist
    for directory in [DOWNLOAD_DIR, COMPLETED_DIR, APP_DATA_FOLDER]:
        if not directory.exists():
            try:
                directory.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created directory at: {directory}")
            except OSError as e:
                logger.error(f"FATAL: Could not create directory at '{directory}'. Please check permissions. Error: {e}")
                # In a real app, you might want to exit here if the directory is critical
    
    load_data()
    
    # Register save_data only once
    atexit.register(save_data)
    
    logger.info("Application data directories initialized.")

init()

if __name__ == '__main__':
    # Only run the development server when called directly
    app.run(debug=DEBUG, host=HOST, port=PORT)