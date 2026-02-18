from flask import Blueprint, render_template, request, current_app
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
        return explore()
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
    Personalized feed — only shows APPROVED posts from followed users.
    """
    page = request.args.get('page', 1, type=int)
    subjects_param = request.args.get('subjects', '')

    selected_subjects = []
    if subjects_param:
        try:
            selected_subjects = [int(id) for id in subjects_param.split(',') if id.strip()]
        except ValueError:
            pass

    following_ids = [user.id for user in current_user.following.all()]

    if following_ids:
        query = Post.query.filter(
            Post.status == 'approved',          # ← moderation filter
            or_(
                Post.user_id.in_(following_ids),
                Post.user_id == current_user.id
            )
        )
    else:
        query = Post.query.filter(
            Post.status == 'approved',          # ← moderation filter
            Post.user_id == current_user.id
        )

    if selected_subjects:
        query = query.filter(Post.subject_id.in_(selected_subjects))

    posts = query.order_by(Post.created_at.desc()).paginate(
        page=page,
        per_page=current_app.config['POSTS_PER_PAGE'],
        error_out=False
    )

    subjects = Subject.query.filter_by(is_active=True).order_by(Subject.order, Subject.name).all()

    return render_template('index.html', title='Home', posts=posts, feed_type='personal',
                           subjects=subjects, selected_subjects=selected_subjects)


@bp.route('/explore')
def explore():
    """
    Explore page — only shows APPROVED posts.
    """
    page = request.args.get('page', 1, type=int)
    subjects_param = request.args.get('subjects', '')

    selected_subjects = []
    if subjects_param:
        try:
            selected_subjects = [int(id) for id in subjects_param.split(',') if id.strip()]
        except ValueError:
            pass

    query = Post.query.filter(Post.status == 'approved')    # ← moderation filter

    if selected_subjects:
        query = query.filter(Post.subject_id.in_(selected_subjects))

    posts = query.order_by(Post.created_at.desc()).paginate(
        page=page,
        per_page=current_app.config['POSTS_PER_PAGE'],
        error_out=False
    )

    subjects = Subject.query.filter_by(is_active=True).order_by(Subject.order, Subject.name).all()

    return render_template('index.html', title='Explore', posts=posts, feed_type='explore',
                           subjects=subjects, selected_subjects=selected_subjects)


@bp.route('/about')
def about():
    """About page."""
    return render_template('about.html', title='About')


@bp.route('/terms')
def terms():
    """Terms of Service page."""
    return render_template('terms.html', title='Terms of Service')