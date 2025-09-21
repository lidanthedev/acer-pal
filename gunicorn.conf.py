# Gunicorn configuration file
# For production deployment

import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"
backlog = 2048

# Worker processes - Using 1 worker for homelab to maintain shared state
workers = int(os.getenv('GUNICORN_WORKERS', '1'))
worker_class = "sync"
worker_connections = 1000
# Worker timeout - increased for background downloads to prevent worker kills
timeout = int(os.getenv('GUNICORN_TIMEOUT', '120'))
keepalive = int(os.getenv('GUNICORN_KEEPALIVE', '2'))

# Restart workers after this many requests, to help prevent memory leaks
# Increased from 1000 to prevent worker restarts during long downloads
max_requests = 10000
max_requests_jitter = 1000

# Logging
loglevel = "info"
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "acer-pal"

# Server mechanics
daemon = False
pidfile = None
user = None
group = None
tmp_upload_dir = None

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Performance
preload_app = True
enable_stdio_inheritance = True

# SSL (if needed - commented out by default)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# Worker hooks
def worker_exit(server, worker):
    """Called when a worker exits. Save data to prevent loss."""
    try:
        # Import the save function from the main module
        from main import save_data
        save_data()
    except Exception as e:
        # Log error but don't fail worker exit
        import logging
        logging.getLogger(__name__).error(f"Error saving data during worker exit: {e}")