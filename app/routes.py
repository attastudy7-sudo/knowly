from flask_login import current_user, login_required
from sqlalchemy import or_
from flask import Blueprint, render_template, request, current_app, redirect, url_for, session, abort, make_response, send_from_directory
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
    show_suggestions = False
    suggested_users = {'same_school': [], 'same_programme': [], 'random': []}

    if current_user.is_authenticated and not session.get('suggestions_shown'):
        if current_user.school or current_user.programme:
            show_suggestions = True
            session['suggestions_shown'] = True

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
# VALID CONTENT TYPES  (single source of truth — import from here if needed)
# ─────────────────────────────────────────────────────────────────────────────

VALID_CONTENT_TYPES = {'notes', 'cheatsheet', 'quiz', 'mixed'}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@bp.route('/')
@bp.route('/index')
def index():
    if not current_user.is_authenticated:
        # First-time visitors see the landing/marketing page.
        # A 30-day cookie marks them as returning so subsequent visits
        # land directly on the feed.
        if not request.cookies.get('knowly_visited'):
            response = make_response(redirect(url_for('main.landing')))
            response.set_cookie(
                'knowly_visited', '1',
                max_age=60 * 60 * 24 * 30,   # 30 days
                samesite='Lax',
                secure=False,                  # set True in production (HTTPS)
            )
            return response

        # Returning guest — show the home feed without user-specific content
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
            page=page, per_page=current_app.config['POSTS_PER_PAGE'], error_out=False
        )
        subjects       = Subject.query.filter_by(is_active=True).order_by(Subject.order, Subject.name).all()
        total_posts    = Post.query.filter_by(status='approved').count()
        total_subjects = Subject.query.filter_by(is_active=True).count()
        # Show at most 10 courses in the sidebar for guests; "See all" goes to /library
        all_subjects   = subjects[:10]
        from app.past_papers.routes import XP_REWARD
        return render_template(
            'index.html',
            title='Home',
            xp_reward=XP_REWARD,
            posts=posts,
            feed_type='home',
            subjects=subjects,
            selected_subjects=selected_subjects,
            show_suggestions=False,
            suggested_users=[],
            programmes=[],
            user_programme=None,
            user_subjects=[],
            all_subjects=all_subjects,
            total_posts=total_posts,
            total_subjects=total_subjects,
        )

    from app.models import Programme
    from sqlalchemy import func as sqlfunc

    programmes = Programme.query.filter_by(is_active=True).order_by(Programme.order, Programme.name).limit(6).all()

    user_programme = None
    user_subjects  = []
    if current_user.programme:
        user_programme = Programme.query.filter(
            sqlfunc.lower(Programme.name).contains(current_user.programme.lower())
        ).first()
        if user_programme:
            user_subjects = user_programme.subjects.filter_by(is_active=True)\
                                                    .order_by(Subject.order, Subject.name).limit(8).all()

    all_subjects = Subject.query.filter_by(is_active=True).order_by(Subject.order, Subject.name).limit(8).all()

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

    total_posts    = Post.query.filter_by(status='approved').count()
    total_subjects = Subject.query.filter_by(is_active=True).count()

    from app.past_papers.routes import XP_REWARD
    return render_template(
        'index.html',
        title='Home',
        xp_reward=XP_REWARD,
        posts=posts,
        feed_type='home',
        subjects=subjects,
        selected_subjects=selected_subjects,
        show_suggestions=show_suggestions,
        suggested_users=suggested_users,
        programmes=programmes,
        user_programme=user_programme,
        user_subjects=user_subjects,
        all_subjects=all_subjects,
        total_posts=total_posts,
        total_subjects=total_subjects,
    )


@bp.route('/landing')
def landing():
    """Landing/marketing page — always accessible directly."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
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
    from app.models import Programme
    from sqlalchemy import func as sqlfunc

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

    programmes = Programme.query.filter_by(is_active=True).order_by(Programme.order, Programme.name).limit(6).all()

    user_programme = None
    user_subjects  = []
    if current_user.programme:
        user_programme = Programme.query.filter(
            sqlfunc.lower(Programme.name).contains(current_user.programme.lower())
        ).first()
        if user_programme:
            user_subjects = user_programme.subjects.filter_by(is_active=True)\
                                                    .order_by(Subject.order, Subject.name).limit(8).all()

    all_subjects   = Subject.query.filter_by(is_active=True).order_by(Subject.order, Subject.name).limit(8).all()
    total_posts    = Post.query.filter_by(status='approved').count()
    total_subjects = Subject.query.filter_by(is_active=True).count()

    return render_template(
        'index.html',
        title='Home',
        posts=posts,
        feed_type='personal',
        subjects=subjects,
        selected_subjects=selected_subjects,
        show_suggestions=show_suggestions,
        suggested_users=suggested_users,
        programmes=programmes,
        user_programme=user_programme,
        user_subjects=user_subjects,
        all_subjects=all_subjects,
        total_posts=total_posts,
        total_subjects=total_subjects,
    )

@bp.route('/explore')
def explore():
    page           = request.args.get('page', 1, type=int)
    subjects_param = request.args.get('subjects', '')
    selected_type  = request.args.get('type', '').strip().lower() or None
    search_query   = request.args.get('q', '').strip() or None

    # ── Subject filter ────────────────────────────────────────────────────────
    selected_subjects = []
    if subjects_param:
        try:
            selected_subjects = [int(sid) for sid in subjects_param.split(',') if sid.strip()]
        except ValueError:
            pass

    # ── Base query ───────────────────────────────────────────────────────────
    query = Post.query.filter(Post.status == 'approved')

    if selected_subjects:
        query = query.filter(Post.subject_id.in_(selected_subjects))

    if selected_type in ('notes', 'quiz', 'cheatsheet', 'mixed'):
        query = query.filter(Post.content_type == selected_type)

    if search_query:
        like = f'%{search_query}%'
        query = query.filter(
            Post.title.ilike(like) | Post.description.ilike(like)
        )

    posts = query.order_by(Post.created_at.desc()).paginate(
        page=page,
        per_page=20,
        error_out=False
    )

    subjects       = Subject.query.filter_by(is_active=True).order_by(Subject.order, Subject.name).all()
    total_posts    = Post.query.filter_by(status='approved').count()
    total_subjects = Subject.query.filter_by(is_active=True).count()

    return render_template(
        'explore.html',
        title='Explore',
        posts=posts,
        subjects=subjects,
        selected_subjects=selected_subjects,
        selected_type=selected_type,
        search_query=search_query,
        total_posts=total_posts,
        total_subjects=total_subjects,
    )


@bp.route('/about')
def about():
    return render_template('about.html', title='About')


@bp.route('/terms')
def terms():
    return render_template('terms.html', title='Terms of Service')

# ─────────────────────────────────────────────────────────────────────────────
# LIBRARY  — Programme → Course → Content
# ─────────────────────────────────────────────────────────────────────────────

from app.models import Programme
from sqlalchemy import func


@bp.route('/library')
def library():
    programmes = Programme.query.filter_by(is_active=True).order_by(Programme.order, Programme.name).all()

    ungrouped = Subject.query.filter_by(is_active=True, programme_id=None)\
                             .order_by(Subject.order, Subject.name).all()

    # Build faculty groups
    faculty_map = {}
    for prog in programmes:
        key = prog.faculty or '__unassigned__'
        if key not in faculty_map:
            faculty_map[key] = []
        faculty_map[key].append(prog)

    user_programme = None
    user_subjects  = []
    user_faculty   = None
    if current_user.is_authenticated and current_user.programme:
        user_programme = Programme.query.filter(
            func.lower(Programme.name).contains(current_user.programme.lower())
        ).first()
        if user_programme:
            user_subjects = user_programme.subjects.filter_by(is_active=True)\
                                                    .order_by(Subject.order, Subject.name).all()
            user_faculty  = user_programme.faculty

    total_posts      = Post.query.filter_by(status='approved').count()
    total_subjects   = Subject.query.filter_by(is_active=True).count()
    total_programmes = Programme.query.filter_by(is_active=True).count()

    return render_template(
        'library/index.html',
        title='Library',
        programmes=programmes,
        faculty_map=faculty_map,
        ungrouped=ungrouped,
        user_programme=user_programme,
        user_subjects=user_subjects,
        user_faculty=user_faculty,
        total_posts=total_posts,
        total_subjects=total_subjects,
        total_programmes=total_programmes,
    )


@bp.route('/library/faculty/<faculty_slug>')
def library_faculty(faculty_slug):
    """Faculty page — shows all programmes within a faculty."""
    import re

    def _slugify(text):
        text = text.lower()
        text = text.replace("'", '').replace('&', 'and').replace('/', '')
        text = re.sub(r'[-\s]+', '-', text)
        text = re.sub(r'[^\w-]', '', text)
        return text.strip('-')

    all_programmes = Programme.query.filter_by(is_active=True).all()

    # Handle unassigned
    if faculty_slug == 'unassigned':
        faculty_name = 'Unassigned'
        programmes   = [p for p in all_programmes if not p.faculty]
    else:
        faculty_name = None
        programmes   = []
        for p in all_programmes:
            if p.faculty and _slugify(p.faculty) == faculty_slug:
                faculty_name = p.faculty
                programmes.append(p)

    if not programmes:
        abort(404)

    programmes.sort(key=lambda p: p.name)

    return render_template(
        'library/faculty.html',
        title=faculty_name,
        faculty_name=faculty_name,
        faculty_slug=faculty_slug,
        programmes=programmes,
    )

@bp.route('/library/programme/<slug>')
def library_programme(slug):
    """Programme page — shows all subjects/courses within a programme."""
    programme = Programme.query.filter_by(slug=slug, is_active=True).first_or_404()
    subjects = programme.subjects.filter_by(is_active=True)\
                                   .order_by(Subject.order, Subject.name).all()

    counts_by_subject = {}
    for s in subjects:
        approved = s.posts.filter_by(status='approved')
        counts_by_subject[s.id] = {
            'notes':      approved.filter_by(content_type='notes').count(),
            'cheatsheets': approved.filter_by(content_type='cheatsheet').count(),
            'quizzes':    approved.filter_by(content_type='quiz').count(),
            'mixed':      approved.filter_by(content_type='mixed').count(),
            'total':      approved.count(),
        }

    return render_template(
        'library/programme.html',
        title=programme.name,
        programme=programme,
        subjects=subjects,
        counts_by_subject=counts_by_subject,
    )

# ─────────────────────────────────────────────────────────────────────────────
# SUBJECT PAGE  — the key fix
# ─────────────────────────────────────────────────────────────────────────────

@bp.route('/library/subject/<slug>')
def library_subject(slug):
    """
    Subject/course page — tabbed view of Notes | Cheatsheets | Quizzes | All.

    FIX: All tab filtering now goes through Post.content_type exclusively.
         The old approach fell back to a QuizData join for the quiz tab, which
         caused double-counting and missed posts whose content_type was already
         'quiz'.  After running migrate_content_types.py every quiz post will
         have content_type='quiz', so a plain equality filter is sufficient and
         correct.

    URL: /library/subject/<slug>?tab=notes|cheatsheet|quiz|all
    """
    subject = Subject.query.filter_by(slug=slug, is_active=True).first_or_404()

    # Sanitise the tab parameter — reject anything unknown
    tab  = request.args.get('tab', 'all')
    if tab not in ('all', 'notes', 'cheatsheet', 'quiz'):
        tab = 'all'

    page = request.args.get('page', 1, type=int)

    base_query = Post.query.filter(
        Post.subject_id == subject.id,
        Post.status     == 'approved',
    )

    # ── Clean, consistent filter — one line per tab ──────────────────────────
    if tab == 'all':
        q = base_query
    else:
        # Works for 'notes', 'cheatsheet', AND 'quiz' — no special cases needed
        q = base_query.filter(Post.content_type == tab)

    posts = q.order_by(Post.created_at.desc()).paginate(
        page=page, per_page=15, error_out=False
    )

    # ── Tab counts ────────────────────────────────────────────────────────────
    counts = {
        'all':        base_query.count(),
        'notes':      base_query.filter(Post.content_type == 'notes').count(),
        'cheatsheet': base_query.filter(Post.content_type == 'cheatsheet').count(),
        'quiz':       base_query.filter(Post.content_type == 'quiz').count(),
    }

    programme = subject.programme  # may be None

    return render_template(
        'library/subject.html',
        title=f'{subject.name} — Library',
        subject=subject,
        programme=programme,
        posts=posts,
        tab=tab,
        counts=counts,
    )


# ─────────────────────────────────────────────────────────────────────────────
# NOTIFICATIONS API
# ─────────────────────────────────────────────────────────────────────────────

@bp.route('/notifications')
@login_required
def notifications():
    """Return the 30 most recent notifications for the current user."""
    from app.models import Notification
    notifs = (
        Notification.query
        .filter_by(user_id=current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(30)
        .all()
    )
    return jsonify([{
        'id':      n.id,
        'message': n.message,
        'type':    n.notification_type,
        'link':    n.link,
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat(),
    } for n in notifs])


@bp.route('/notifications/mark-read', methods=['POST'])
@login_required
def notifications_mark_read():
    """Mark all unread notifications as read."""
    from app.models import Notification
    Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False,
    ).update({'is_read': True})
    db.session.commit()
    return jsonify({'status': 'ok'})


@bp.route('/notifications/unread-count')
@login_required
def notifications_unread_count():
    """Lightweight poll endpoint for the nav badge."""
    from app.models import Notification
    count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False,
    ).count()
    return jsonify({'count': count})


# ─────────────────────────────────────────────────────────────────────────────
# PWA — Offline fallback page
# Served by the service worker when a navigation request fails with no cache.
# Must be a real route so the SW can pre-cache it during install.
# ─────────────────────────────────────────────────────────────────────────────

@bp.route('/offline')
def offline():
    """PWA offline fallback page."""
    return render_template('offline.html'), 200

# ─────────────────────────────────────────────────────────────────────────────
# PWA — serve SW from root so its scope covers the whole app
# ─────────────────────────────────────────────────────────────────────────────
@bp.route('/sw.js')
def service_worker():
    response = make_response(
        send_from_directory(current_app.static_folder, 'sw.js')
    )
    response.headers['Content-Type']  = 'application/javascript'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Service-Worker-Allowed'] = '/'
    return response