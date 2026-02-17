import os
import platform
from datetime import timedelta

# Base directory of the application
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    """
    Configuration class for the Flask application.
    Contains all settings needed for security, database, uploads, etc.
    """
    
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
            print("⚠️  WARNING: Using default SECRET_KEY. Set SECRET_KEY env var for production!")
        else:
            raise ValueError("SECRET_KEY environment variable must be set in production")
    
    # CSRF Protection
    WTF_CSRF_SECRET_KEY = SECRET_KEY
    WTF_CSRF_ENABLED = True
    
    # ============================================================================
    # Database Configuration
    # ============================================================================

    DATABASE_URL = os.environ.get("DATABASE_URL")

    if IS_RENDER and DATABASE_URL:
        # Production (Render)
        SQLALCHEMY_DATABASE_URI = DATABASE_URL

        print("\n" + "="*70)
        print("🚀 PRODUCTION MODE (Render)")
        print("="*70)
        print("☁️  Using Turso database")
        print("="*70 + "\n")

    elif IS_WINDOWS and IS_DEVELOPMENT:
        # Windows development
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'edushare_dev.db')

        print("\n" + "="*70)
        print("🪟 WINDOWS DEVELOPMENT MODE")
        print("="*70)
        print("📁 Using local SQLite: edushare_dev.db")
        print("="*70 + "\n")

    else:
        # Default fallback (Linux/mac local dev)
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'edushare_dev.db')
        print("\n⚠️  Using local SQLite: edushare_dev.db\n")

    # ============================================================================
    # File Upload Settings
    # ============================================================================
    
    UPLOAD_FOLDER = os.path.join(basedir, 'app/static/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max file size
    
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
    # Payment Settings (Future Integration)
    # ============================================================================
    
    STRIPE_PUBLIC_KEY = os.environ.get('STRIPE_PUBLIC_KEY')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    PAYSTACK_PUBLIC_KEY = os.environ.get('PAYSTACK_PUBLIC_KEY')
    PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY')
    
    # ============================================================================
    # Email Settings (Future Integration)
    # ============================================================================
    
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')