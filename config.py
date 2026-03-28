import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-youtube-clone'
    
    # Railway Persistent Volume Support
    # If the user mounts a volume in Railway (e.g. /data), all uploads & SQLite DB will be stored there.
    DATA_DIR = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', os.path.abspath(os.path.dirname(__file__)))
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f"sqlite:///{os.path.join(DATA_DIR, 'youtube.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(DATA_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 1000 * 1024 * 1024 # 1GB max upload size
