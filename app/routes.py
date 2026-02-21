from flask_login import current_user, login_required
from sqlalchemy import or_
from flask import Blueprint, render_template, request, current_app, redirect, url_for, session
from app import db
from flask import jsonify
from app.models import User, Post, Document, Subject, Like, Comment


# Create main blueprint
bp = Blueprint('main', __name__)


# ─────────────────────────────────────────────────────────────────────────────
# SHORTCUT REDIRECTS — so /login and /signup work without the /auth prefix
# ─────────────────────────────────────────────────────────────────────────────

@bp.route('/login')
def login_redirect():
    """Convenience redirect: /login → /auth/login"""
    return redirect(url_for('auth.login'))


@bp.route('/signup')
@bp.route('/register')
def signup_redirect():
    """Convenience redirect: /signup or /register → /auth/signup"""
    return redirect(url_for('auth.signup'))


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _build_suggestions():
    """
    Build the suggested-users payload and decide whether to show the overlay.
    Returns (show_suggestions: bool, suggested_users: dict).

    The overlay is shown at most once per server-side session — once seen,
    `session['suggestions_shown']` is set to True so it won't appear again
    on a refresh or across subsequent requests (unlike sessionStorage which
    is client-only and resets on a new tab/session).
    """
    show_suggestions = False
    suggested_users = {'same_school': [], 'same_programme': [], 'random': []}

    if current_user.is_authenticated and not session.get('suggestions_shown'):
        if current_user.school or current_user.programme:
            show_suggestions = True
            session['suggestions_shown'] = True          # server-side — persists across page loads

            already_following = [u.id for u in current_user.following.all()]
            exclude = already_following + [current_user.id]

            if current_user.school:
                suggested_users['same_school'] = User.query.filter(
                    User.school == current_user.school,
                    ~User.id.in_(exclude)
                ).limit(4).all()

            if current_user.programme:
                suggested_users['same_programme'] = User.query.filter(
                    User.programme == current_user.programme,
                    ~User.id.in_(exclude)
                ).limit(4).all()

            suggested_users['random'] = User.query.filter(
                ~User.id.in_(exclude)
            ).order_by(db.func.random()).limit(4).all()

    return show_suggestions, suggested_users


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@bp.route('/')
@bp.route('/index')
def index():
    """
    Home page — redirects logged-in users to the explore feed.
    Guests see the landing page.
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.explore'))
    return landing()


def landing():
    """Landing page for non-authenticated users."""
    return render_template('landing.html', title='Welcome')

@bp.route('/api/stats')
def api_stats():
    docs        = Document.query.count()
    users       = User.query.count()
    subjects    = Subject.query.filter_by(is_active=True).count()
    likes       = Like.query.count()
    comments    = Comment.query.count()
    engagements = likes + comments

    return jsonify({
        'documents':    docs,
        'users':        users,
        'subjects':     subjects,
        'engagements':  engagements,
    })



@bp.route('/feed')
@login_required
def feed_route():
    """
    Personalized feed — shows APPROVED posts from followed users
    plus the current user's own posts. Also surfaces the
    people-you-might-know overlay on first visit.
    """
    show_suggestions, suggested_users = _build_suggestions()

    page = request.args.get('page', 1, type=int)
    subjects_param = request.args.get('subjects', '')

    selected_subjects = []
    if subjects_param:
        try:
            selected_subjects = [int(sid) for sid in subjects_param.split(',') if sid.strip()]
        except ValueError:
            pass

    following_ids = [user.id for user in current_user.following.all()]

    if following_ids:
        query = Post.query.filter(
            Post.status == 'approved',
            or_(
                Post.user_id.in_(following_ids),
                Post.user_id == current_user.id
            )
        )
    else:
        query = Post.query.filter(
            Post.status == 'approved',
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

    return render_template(
        'index.html',
        title='Home',
        posts=posts,
        feed_type='personal',
        subjects=subjects,
        selected_subjects=selected_subjects,
        show_suggestions=show_suggestions,
        suggested_users=suggested_users,
    )


@bp.route('/explore')
def explore():
    """
    Explore feed — shows ALL approved posts, not limited to followed users.
    Also surfaces the people-you-might-know overlay on first visit.
    """
    show_suggestions, suggested_users = _build_suggestions()

    page = request.args.get('page', 1, type=int)
    subjects_param = request.args.get('subjects', '')

    selected_subjects = []
    if subjects_param:
        try:
            selected_subjects = [int(sid) for sid in subjects_param.split(',') if sid.strip()]
        except ValueError:
            pass

    query = Post.query.filter(Post.status == 'approved')

    if selected_subjects:
        query = query.filter(Post.subject_id.in_(selected_subjects))

    posts = query.order_by(Post.created_at.desc()).paginate(
        page=page,
        per_page=current_app.config['POSTS_PER_PAGE'],
        error_out=False
    )

    subjects = Subject.query.filter_by(is_active=True).order_by(Subject.order, Subject.name).all()

    return render_template(
        'index.html',
        title='Explore',
        posts=posts,
        feed_type='explore',
        subjects=subjects,
        selected_subjects=selected_subjects,
        show_suggestions=show_suggestions,
        suggested_users=suggested_users,
    )


@bp.route('/about')
def about():
    """About page."""
    return render_template('about.html', title='About')


@bp.route('/terms')
def terms():
    """Terms of Service page."""
    return render_template('terms.html', title='Terms of Service')