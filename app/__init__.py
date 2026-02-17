from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()


def create_app(config_class=Config):
    """
    Application Factory Pattern
    Creates and configures the Flask application instance.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)

    # Initialize Cloudinary
    import cloudinary
    cloudinary.config(
        cloud_name=app.config['CLOUDINARY_CLOUD_NAME'],
        api_key=app.config['CLOUDINARY_API_KEY'],
        api_secret=app.config['CLOUDINARY_API_SECRET'],
        secure=True
    )
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # Register blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.posts import bp as posts_bp
    app.register_blueprint(posts_bp, url_prefix='/posts')
    
    from app.users import bp as users_bp
    app.register_blueprint(users_bp, url_prefix='/users')
    
    from app.payments import bp as payments_bp
    app.register_blueprint(payments_bp, url_prefix='/payments')
    
    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    
    from app import routes
    app.register_blueprint(routes.bp)
    
    # Create database tables if they don't exist
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            print(f"Database already initialized: {e}")
    
    return app


# Import models so SQLAlchemy knows about them
from app import models
from app.models import Subject

import logging
logging.basicConfig(level=logging.INFO)