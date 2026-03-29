"""
Configuration file for Movie Ticket Booking System
Contains all the configuration settings for the Flask application
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Flask Configuration
SECRET_KEY = os.environ.get('SECRET_KEY') or 'movie-ticket-booking-secret-key-2024'
DEBUG = True

# MongoDB Configuration
MONGO_URI = os.environ.get('MONGO_URI') or 'mongodb://localhost:27017/moviesdb'
DB_NAME = 'nandiDB'

# Upload Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

# Session Configuration
SESSION_TYPE = 'filesystem'
PERMANENT_SESSION_LIFETIME = 3600  # 1 hour

# Admin credentials (can be stored in database in production)
ADMIN_EMAIL = 'admin@movie.com'
ADMIN_PASSWORD = 'admin123'
