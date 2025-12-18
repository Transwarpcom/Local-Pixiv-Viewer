import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DB_PATH') or 'sqlite:///pixiv.db'
    if SQLALCHEMY_DATABASE_URI.startswith('sqlite') and not SQLALCHEMY_DATABASE_URI.startswith('sqlite:///'):
         # Handle relative path if passed as filename
         SQLALCHEMY_DATABASE_URI = 'sqlite:///' + SQLALCHEMY_DATABASE_URI
         
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    DATA_DIR = os.environ.get('DATA_DIR')
    THUMBS_DIR = os.environ.get('THUMBS_DIR')
    SCAN_INTERVAL = 15  # seconds
    
    # Pagination
    ITEMS_PER_PAGE = 20
