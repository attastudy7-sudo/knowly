from flask import Blueprint, render_template, request, current_app, jsonify
from flask_login import current_user, login_required
from app.models import Post, User, Subject
from sqlalchemy import or_

# Create main blueprint
bp = Blueprint('main', __name__)


@bp.route('/')
@bp.route('/index')
def index():
    """
    Home page - shows landing page for guests, personalized feed if logged in.
    """
    if current_user.is_authenticated:
        return feed()  # Shows personalized feed
    else:
        return landing()


def landing():
    """
    Landing page for non-authenticated users.
    """
    return render_template('landing.html', title='Welcome')


@bp.route('/feed')
@login_required
def feed_route():
    """
    Route wrapper for personalized feed.
    """
    return feed()


def feed():
    """
    Personalized feed showing posts from followed users.
    Algorithm: Show posts from people you follow, sorted by recent.
    """
    page = request.args.get('page', 1, type=int)
    subjects_param = request.args.get('subjects', '')
    
    # Parse multiple subject IDs
    selected_subjects = []
    if subjects_param:
        try:
            selected_subjects = [int(id) for id in subjects_param.split(',') if id.strip()]
        except ValueError:
            pass
    
    # Get IDs of users being followed
    following_ids = [user.id for user in current_user.following.all()]
    
    if following_ids:
        # Show posts from followed users + own posts
        query = Post.query.filter(
            or_(
                Post.user_id.in_(following_ids),
                Post.user_id == current_user.id
            )
        )
    else:
        # If not following anyone, show own posts
        query = Post.query.filter_by(user_id=current_user.id)
    
    # Apply subject filters if selected (multiple subjects with OR logic)
    if selected_subjects:
        query = query.filter(Post.subject_id.in_(selected_subjects))
    
    posts = query.order_by(Post.created_at.desc()).paginate(
        page=page,
        per_page=current_app.config['POSTS_PER_PAGE'],
        error_out=False
    )
    
    # Get all subjects for filter
    subjects = Subject.query.filter_by(is_active=True).order_by(Subject.order, Subject.name).all()
    
    return render_template('index.html', title='Home', posts=posts, feed_type='personal', 
                         subjects=subjects, selected_subjects=selected_subjects)


@bp.route('/explore')
def explore():
    """
    Explore page - shows all posts from all users (public feed).
    """
    page = request.args.get('page', 1, type=int)
    subjects_param = request.args.get('subjects', '')
    
    # Parse multiple subject IDs
    selected_subjects = []
    if subjects_param:
        try:
            selected_subjects = [int(id) for id in subjects_param.split(',') if id.strip()]
        except ValueError:
            pass
    
    # Build query
    query = Post.query
    
    # Apply subject filters if selected (multiple subjects with OR logic)
    if selected_subjects:
        query = query.filter(Post.subject_id.in_(selected_subjects))
    
    posts = query.order_by(Post.created_at.desc()).paginate(
        page=page,
        per_page=current_app.config['POSTS_PER_PAGE'],
        error_out=False
    )
    
    # Get all subjects for filter
    subjects = Subject.query.filter_by(is_active=True).order_by(Subject.order, Subject.name).all()
    
    return render_template('index.html', title='Explore', posts=posts, feed_type='explore',
                         subjects=subjects, selected_subjects=selected_subjects)


@bp.route('/about')
def about():
    """About page."""
    return render_template('about.html', title='About')