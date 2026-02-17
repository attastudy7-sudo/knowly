from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from app import db
from app.auth import bp
from app.forms import LoginForm, SignupForm
from app.models import User


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login route - handles user authentication.
    If already logged in, redirect to home.
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        # Find user by username
        user = User.query.filter_by(username=form.username.data).first()
        
        # Check if user exists and password is correct
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password', 'danger')
            return redirect(url_for('auth.login'))
        
        # Log the user in
        login_user(user, remember=form.remember_me.data)
        flash(f'Welcome back, {user.username}!', 'success')
        
        # Redirect to the page user was trying to access, or home
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('main.index')
        
        return redirect(next_page)
    
    return render_template('auth/login.html', title='Log In', form=form)


@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    Signup route - handles user registration.
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = SignupForm()
    
    if form.validate_on_submit():
        # Create new user
        user = User(
            username=form.username.data,
            email=form.email.data,
            full_name=form.full_name.data
        )
        user.set_password(form.password.data)
        
        # Save to database
        db.session.add(user)
        db.session.commit()
        
        flash('Congratulations! Your account has been created. Please log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/signup.html', title='Sign Up', form=form)


@bp.route('/logout')
def logout():
    """
    Logout route - logs out the current user.
    """
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))
