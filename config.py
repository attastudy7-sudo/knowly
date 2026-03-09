import os
import platform
from datetime import timedelta
from dotenv import load_dotenv

# Load .env from the same directory as this config file
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# Base directory of the application
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    """
    Configuration class for the Flask application.
    Contains all settings needed for security, database, uploads, etc.
    """
    PREFERRED_URL_SCHEME = 'https'
    
    # ============================================================================
    # Environment Detection
    # ============================================================================
    
    # Check if we're in development mode
    IS_DEVELOPMENT = os.environ.get('FLASK_ENV', 'development') == 'development'
    
    # Check if running on Windows
    IS_WINDOWS = platform.system() == 'Windows'
    
    # Check if running on Render (production)
    IS_RENDER = os.environ.get('RENDER') is not None
    
    # ============================================================================
    # Secret Key
    # ============================================================================
    
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        if IS_DEVELOPMENT:
            SECRET_KEY = 'dev-key-for-local-only-CHANGE-IN-PRODUCTION'
            print("WARNING: Using default SECRET_KEY. Set SECRET_KEY env var for production!")
        else:
            raise ValueError("SECRET_KEY environment variable must be set in production")
    
    # CSRF Protection
    WTF_CSRF_SECRET_KEY = SECRET_KEY
    WTF_CSRF_ENABLED = True
    
    # ============================================================================
    # Database Configuration
    # ============================================================================

    DATABASE_URL = os.environ.get("DATABASE_URL")

    if DATABASE_URL:
        # Handle different database URL formats
        if DATABASE_URL.startswith('postgresql://'):
            # PostgreSQL (Neon, Supabase, Railway, etc.)
            SQLALCHEMY_DATABASE_URI = DATABASE_URL
        elif DATABASE_URL.startswith('mysql://'):
            # MySQL/PlanetScale - convert to use pymysql driver
            SQLALCHEMY_DATABASE_URI = DATABASE_URL.replace('mysql://', 'mysql+pymysql://')
        elif DATABASE_URL.startswith('https://'):
            # Turso with https - convert to sqlite+libsql://
            SQLALCHEMY_DATABASE_URI = DATABASE_URL.replace('https://', 'sqlite+libsql://')
        elif DATABASE_URL.startswith('libsql://'):
            # Turso with libsql - add sqlite+ prefix
            SQLALCHEMY_DATABASE_URI = DATABASE_URL.replace('libsql://', 'sqlite+libsql://')
        else:
            # Use as-is for other formats
            SQLALCHEMY_DATABASE_URI = DATABASE_URL

        print("\n" + "="*70)
        print("USING REMOTE DATABASE")
        print("="*70)
        print("Connected to Cloud Database")
        print("="*70 + "\n")

    else:
        # Local development fallback
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'knowly.db')
        
        if IS_WINDOWS:
            print("\n" + "="*70)
            print("WINDOWS DEVELOPMENT MODE")
            print("="*70)
            print("Using local SQLite: knowly.db")
            print("="*70 + "\n")
        else:
            print("\nUsing local SQLite: knowly.db\n")

    # SQLAlchemy settings
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # ============================================================================
    # Cloudinary Configuration
    # ============================================================================

    CLOUDINARY_CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME')
    CLOUDINARY_API_KEY = os.environ.get('CLOUDINARY_API_KEY')
    CLOUDINARY_API_SECRET = os.environ.get('CLOUDINARY_API_SECRET')

    # ============================================================================
    # File Upload Settings
    # ============================================================================

    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB max file size

    # Allowed file extensions for security
    ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'docx', 'pptx', 'txt', 'doc', 'ppt'}
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

    # ============================================================================
    # Pagination Settings
    # ============================================================================
    
    POSTS_PER_PAGE = 10
    COMMENTS_PER_PAGE = 5
    USERS_PER_PAGE = 20
    
    # ============================================================================
    # Session Configuration
    # ============================================================================
    
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = not IS_DEVELOPMENT  # HTTPS only in production
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # ============================================================================
    # Payment Settings
    # ============================================================================
    
    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    PAYSTACK_PUBLIC_KEY = os.environ.get('PAYSTACK_PUBLIC_KEY')
    PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY')
    
    # ============================================================================
    # Email Settings
    # ============================================================================
    
    MAIL_SERVER = 'smtp-relay.brevo.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or os.environ.get('MAIL_USERNAME')
    BREVO_API_KEY = os.environ.get('BREVO_API_KEY')
    
    # ============================================================================
    # AI Configuration (for Quiz Generation)
    # ============================================================================
    
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    
    # Quiz generation settings
    QUIZ_DEFAULT_TIME_MINUTES = int(os.environ.get('QUIZ_DEFAULT_TIME_MINUTES', 30))
    QUIZ_DEFAULT_XP_REWARD = int(os.environ.get('QUIZ_DEFAULT_XP_REWARD', 50))
