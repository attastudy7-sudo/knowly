import os
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
    
    # ============================================================================
    # Secret Key
    # ============================================================================
    
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        if IS_DEVELOPMENT:
            # Allow dev mode without env var
            SECRET_KEY = 'dev-key-for-local-only-CHANGE-IN-PRODUCTION'
            print("⚠️  WARNING: Using default SECRET_KEY. Set SECRET_KEY env var for production!")
        else:
            raise ValueError("SECRET_KEY environment variable must be set in production")
    
    # ============================================================================
    # Database Configuration - Turso (LibSQL)
    # ============================================================================
    
    # Get Turso credentials from environment
    TURSO_URL = os.environ.get('TURSO_DATABASE_URL')
    TURSO_TOKEN = os.environ.get('TURSO_AUTH_TOKEN')
    
    # Validate that credentials are provided
    if not TURSO_URL or not TURSO_TOKEN:
        if IS_DEVELOPMENT:
            # In dev mode, show helpful error but allow startup
            print("\n" + "="*70)
            print("⚠️  TURSO DATABASE NOT CONFIGURED")
            print("="*70)
            print("Set these environment variables:")
            print("  TURSO_DATABASE_URL=https://your-database.turso.io")
            print("  TURSO_AUTH_TOKEN=your-token-here")
            print("\nCreate a .env file with these variables, or set them in your terminal:")
            print("  Windows: $env:TURSO_DATABASE_URL='https://...'")
            print("  Mac/Linux: export TURSO_DATABASE_URL='https://...'")
            print("="*70 + "\n")
            # Use local SQLite as fallback for development
            SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'edushare_dev.db')
            print("📁 Using local SQLite database: edushare_dev.db\n")
        else:
            raise ValueError(
                "TURSO_DATABASE_URL and TURSO_AUTH_TOKEN environment variables must be set. "
                "Please set them in Render dashboard."
            )
    else:
        # Build the correct SQLAlchemy URI for Turso
        # Format: sqlite+libsql://[HOST]?authToken=[TOKEN]
        # Remove https:// from the URL as the driver adds it
        TURSO_HOST = TURSO_URL.replace('https://', '').replace('http://', '')
        SQLALCHEMY_DATABASE_URI = f"sqlite+libsql://{TURSO_HOST}?authToken={TURSO_TOKEN}"
        print(f"✅ Connected to Turso database: {TURSO_HOST}\n")
    
    # SQLAlchemy settings
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # Disable tracking to save resources
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,      # Verify connections before using them
        'pool_recycle': 300,         # Recycle connections after 5 minutes
    }
    
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