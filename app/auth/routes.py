import os

from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user
from flask_dance.contrib.google import make_google_blueprint

from app import db
from app.auth import bp
from app.forms import LoginForm, SignupForm
from app.models import User


# ─────────────────────────────────────────────────────────────────────────────
# GOOGLE OAUTH BLUEPRINT FACTORY
# ─────────────────────────────────────────────────────────────────────────────

def create_google_blueprint():
    """
    Called in the app factory (app/__init__.py):

        google_bp = create_google_blueprint()
        app.register_blueprint(google_bp, url_prefix='/login')

    The OAuth callback lands at /login/google/authorized (handled by
    Flask-Dance). The oauth_authorized signal in __init__.py then
    logs the user in — there is NO separate /google/callback route.

    Add these URIs in Google Cloud Console:
        Local:      http://localhost:5000/login/google/authorized
        Production: https://your-domain.onrender.com/login/google/authorized

    Required env vars:
        GOOGLE_OAUTH_CLIENT_ID
        GOOGLE_OAUTH_CLIENT_SECRET
    """
    return make_google_blueprint(
        client_id=os.environ.get('GOOGLE_OAUTH_CLIENT_ID'),
        client_secret=os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET'),
        scope=[
            'openid',
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile',
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — find user by username OR email
# ─────────────────────────────────────────────────────────────────────────────

def _find_user_by_login(identifier: str):
    """
    Accept either a username or email in the login field.
    If the identifier contains '@' we try email first, then username.
    """
    identifier = identifier.strip()
    if '@' in identifier:
        user = User.query.filter_by(email=identifier).first()
        if user:
            return user
    return User.query.filter_by(username=identifier).first()


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — create or fetch a Google OAuth user
# ─────────────────────────────────────────────────────────────────────────────

def _get_or_create_google_user(google_email: str, google_name: str):
    """
    Find an existing account by Google email, or create a new one.

    Username is derived from the email prefix; a numeric suffix is appended
    if the base username is already taken.

    Google-created accounts have password_hash=None and can only log in
    via Google unless a password is set separately.
    """
    user = User.query.filter_by(email=google_email).first()
    if user:
        return user, False

    base_username = google_email.split('@')[0].replace('.', '_').lower()
    username = base_username
    counter  = 1
    while User.query.filter_by(username=username).first():
        username = f"{base_username}{counter}"
        counter += 1

    user = User(
        username  = username,
        email     = google_email,
        full_name = google_name or username,
    )
    user.password_hash = None   # Google-only account — no password
    db.session.add(user)
    db.session.commit()
    return user, True


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN — accepts username OR email
# ─────────────────────────────────────────────────────────────────────────────

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm()

    if form.validate_on_submit():
        user = _find_user_by_login(form.username.data)

        if user is None:
            flash('No account found with that username or email.', 'danger')
            return redirect(url_for('auth.login'))

        if user.password_hash is None:
            flash(
                'This account uses Google sign-in. '
                'Please use "Continue with Google" below.',
                'warning',
            )
            return redirect(url_for('auth.login'))

        if not user.check_password(form.password.data):
            flash('Incorrect password.', 'danger')
            return redirect(url_for('auth.login'))

        login_user(user, remember=form.remember_me.data)
        flash(f'Welcome back, {user.username}!', 'success')

        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('main.index')
        return redirect(next_page)

    return render_template('auth/login.html', title='Log In', form=form)


# ─────────────────────────────────────────────────────────────────────────────
# SIGNUP
# ─────────────────────────────────────────────────────────────────────────────

@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = SignupForm()

    if form.validate_on_submit():
        user = User(
            username  = form.username.data,
            email     = form.email.data,
            full_name = form.full_name.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        flash('Account created! Please sign in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/signup.html', title='Sign Up', form=form)


# ─────────────────────────────────────────────────────────────────────────────
# GOOGLE — initiate OAuth flow
# Saves the 'next' param in session so it survives the OAuth redirect.
# ─────────────────────────────────────────────────────────────────────────────

@bp.route('/google/login')
def google_login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    next_page = request.args.get('next')
    if next_page and next_page.startswith('/'):
        session['next_after_google'] = next_page

    return redirect(url_for('google.login'))


# ─────────────────────────────────────────────────────────────────────────────
# LOGOUT
# ─────────────────────────────────────────────────────────────────────────────

@bp.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))