from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.admin import bp
from app.forms import SubjectForm
from app.models import Subject, User, Post, Comment
import re
import os
from flask import current_app


def slugify(text):
    """Convert text to URL-friendly slug."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')


@bp.route('/')
@login_required
def dashboard():
    """
    Admin dashboard with overview statistics.
    Note: In production, add proper admin role checking.
    """
    # Get statistics
    total_users = User.query.count()
    total_posts = Post.query.count()
    total_subjects = Subject.query.count()
    total_comments = Comment.query.count()
    
    # Recent activity
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_posts = Post.query.order_by(Post.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html', 
                         title='Admin Dashboard',
                         total_users=total_users,
                         total_posts=total_posts,
                         total_subjects=total_subjects,
                         total_comments=total_comments,
                         recent_users=recent_users,
                         recent_posts=recent_posts)


# ============ SUBJECT MANAGEMENT ============

@bp.route('/subjects')
@login_required
def subjects():
    """
    View all subjects.
    Note: In production, add proper admin role checking here.
    For now, any logged-in user can view.
    """
    subjects = Subject.query.order_by(Subject.order, Subject.name).all()
    return render_template('admin/subjects.html', title='Manage Subjects', subjects=subjects)


@bp.route('/subjects/create', methods=['GET', 'POST'])
@login_required
def create_subject():
    """
    Create a new subject.
    Note: In production, add proper admin role checking.
    """
    form = SubjectForm()
    
    if form.validate_on_submit():
        # Generate slug from name
        slug = slugify(form.name.data)
        
        # Check if slug already exists
        existing = Subject.query.filter_by(slug=slug).first()
        if existing:
            flash('A subject with this name already exists.', 'danger')
            return redirect(url_for('admin.create_subject'))
        
        # Create subject
        subject = Subject(
            name=form.name.data,
            slug=slug,
            description=form.description.data,
            icon=form.icon.data or 'book',
            color=form.color.data or '#6366f1',
            order=int(form.order.data) if form.order.data else 0,
            is_active=form.is_active.data
        )
        
        db.session.add(subject)
        db.session.commit()
        
        flash(f'Subject "{subject.name}" created successfully!', 'success')
        return redirect(url_for('admin.subjects'))
    
    return render_template('admin/subject_form.html', title='Create Subject', form=form)


@bp.route('/subjects/<int:subject_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_subject(subject_id):
    """
    Edit an existing subject.
    Note: In production, add proper admin role checking.
    """
    subject = Subject.query.get_or_404(subject_id)
    form = SubjectForm()
    
    if form.validate_on_submit():
        # Update slug if name changed
        new_slug = slugify(form.name.data)
        if new_slug != subject.slug:
            # Check if new slug already exists
            existing = Subject.query.filter_by(slug=new_slug).first()
            if existing and existing.id != subject.id:
                flash('A subject with this name already exists.', 'danger')
                return redirect(url_for('admin.edit_subject', subject_id=subject.id))
            subject.slug = new_slug
        
        # Update subject
        subject.name = form.name.data
        subject.description = form.description.data
        subject.icon = form.icon.data or 'book'
        subject.color = form.color.data or '#6366f1'
        subject.order = int(form.order.data) if form.order.data else 0
        subject.is_active = form.is_active.data
        
        db.session.commit()
        
        flash(f'Subject "{subject.name}" updated successfully!', 'success')
        return redirect(url_for('admin.subjects'))
    
    elif request.method == 'GET':
        # Pre-fill form
        form.name.data = subject.name
        form.description.data = subject.description
        form.icon.data = subject.icon
        form.color.data = subject.color
        form.order.data = str(subject.order)
        form.is_active.data = subject.is_active
    
    return render_template('admin/subject_form.html', title='Edit Subject', form=form, subject=subject)


@bp.route('/subjects/<int:subject_id>/delete', methods=['POST'])
@login_required
def delete_subject(subject_id):
    """
    Delete a subject.
    Note: In production, add proper admin role checking.
    Warning: This will unlink all posts from this subject.
    """
    subject = Subject.query.get_or_404(subject_id)
    
    # Unlink all posts from this subject
    posts = Post.query.filter_by(subject_id=subject.id).all()
    for post in posts:
        post.subject_id = None
    
    # Delete subject
    name = subject.name
    db.session.delete(subject)
    db.session.commit()
    
    flash(f'Subject "{name}" deleted successfully.', 'success')
    return redirect(url_for('admin.subjects'))


@bp.route('/subjects/<int:subject_id>/toggle', methods=['POST'])
@login_required
def toggle_subject(subject_id):
    """
    Toggle subject active status.
    Note: In production, add proper admin role checking.
    """
    subject = Subject.query.get_or_404(subject_id)
    subject.is_active = not subject.is_active
    db.session.commit()
    
    status = 'activated' if subject.is_active else 'deactivated'
    flash(f'Subject "{subject.name}" {status}.', 'success')
    return redirect(url_for('admin.subjects'))


# ============ USER MANAGEMENT ============

@bp.route('/users')
@login_required
def users():
    """
    View and manage all users.
    Note: In production, add proper admin role checking.
    """
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    query = User.query
    
    # Search filter
    if search:
        query = query.filter(
            db.or_(
                User.username.contains(search),
                User.email.contains(search),
                User.full_name.contains(search)
            )
        )
    
    users = query.order_by(User.created_at.desc()).paginate(
        page=page,
        per_page=20,
        error_out=False
    )
    
    return render_template('admin/users.html', 
                         title='Manage Users', 
                         users=users,
                         search=search)


@bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
def toggle_user_active(user_id):
    """
    Toggle user active status (ban/unban).
    Note: In production, add proper admin role checking.
    """
    user = User.query.get_or_404(user_id)
    
    # Prevent admin from deactivating themselves
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'warning')
        return redirect(url_for('admin.users'))
    
    user.is_active = not user.is_active
    db.session.commit()
    
    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User "{user.username}" has been {status}.', 'success')
    return redirect(url_for('admin.users'))


@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    """
    Delete a user and all their content.
    Note: In production, add proper admin role checking.
    WARNING: This will delete all posts, comments, likes by this user.
    """
    user = User.query.get_or_404(user_id)
    
    # Prevent admin from deleting themselves
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'warning')
        return redirect(url_for('admin.users'))
    
    username = user.username
    
    # Delete user's profile picture if not default
    if user.profile_picture != 'default.jpg':
        profile_pic_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            'profiles',
            user.profile_picture
        )
        if os.path.exists(profile_pic_path):
            os.remove(profile_pic_path)
    
    # Delete user's documents
    for post in user.posts:
        if post.document:
            doc_path = post.document.file_path
            if os.path.exists(doc_path):
                os.remove(doc_path)
    
    # Delete user (cascade will handle posts, comments, likes)
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User "{username}" and all their content has been deleted.', 'success')
    return redirect(url_for('admin.users'))


# ============ POST MANAGEMENT ============

@bp.route('/posts')
@login_required
def posts():
    """
    View and manage all posts.
    Note: In production, add proper admin role checking.
    """
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    subject_filter = request.args.get('subject', type=int)
    
    query = Post.query
    
    # Search filter
    if search:
        query = query.filter(
            db.or_(
                Post.title.contains(search),
                Post.description.contains(search)
            )
        )
    
    # Subject filter
    if subject_filter:
        query = query.filter_by(subject_id=subject_filter)
    
    posts = query.order_by(Post.created_at.desc()).paginate(
        page=page,
        per_page=20,
        error_out=False
    )
    
    # Get subjects for filter
    subjects = Subject.query.filter_by(is_active=True).order_by(Subject.name).all()
    
    return render_template('admin/posts.html', 
                         title='Manage Posts', 
                         posts=posts,
                         subjects=subjects,
                         search=search,
                         subject_filter=subject_filter)


@bp.route('/posts/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    """
    Delete a post.
    Note: In production, add proper admin role checking.
    """
    post = Post.query.get_or_404(post_id)
    
    title = post.title
    
    # Delete associated document file
    if post.document:
        file_path = post.document.file_path
        if os.path.exists(file_path):
            os.remove(file_path)
    
    # Delete post (cascade will handle document, comments, likes)
    db.session.delete(post)
    db.session.commit()
    
    flash(f'Post "{title}" has been deleted.', 'success')
    return redirect(url_for('admin.posts'))


# ============ STATISTICS & REPORTS ============

@bp.route('/statistics')
@login_required
def statistics():
    """
    View detailed statistics and analytics.
    Note: In production, add proper admin role checking.
    """
    # User statistics
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    inactive_users = total_users - active_users
    
    # Post statistics
    total_posts = Post.query.count()
    posts_with_documents = Post.query.filter_by(has_document=True).count()
    posts_without_documents = total_posts - posts_with_documents
    
    # Subject statistics
    subjects_stats = []
    subjects = Subject.query.all()
    for subject in subjects:
        subject.update_post_count()
        subjects_stats.append({
            'name': subject.name,
            'post_count': subject.post_count,
            'color': subject.color
        })
    
    db.session.commit()
    
    # Engagement statistics
    from app.models import Like, Comment
    total_likes = Like.query.count()
    total_comments = Comment.query.count()
    
    # Top contributors
    from sqlalchemy import func
    top_posters = db.session.query(
        User.username,
        User.full_name,
        func.count(Post.id).label('post_count')
    ).join(Post).group_by(User.id).order_by(func.count(Post.id).desc()).limit(10).all()
    
    return render_template('admin/statistics.html',
                         title='Statistics & Analytics',
                         total_users=total_users,
                         active_users=active_users,
                         inactive_users=inactive_users,
                         total_posts=total_posts,
                         posts_with_documents=posts_with_documents,
                         posts_without_documents=posts_without_documents,
                         subjects_stats=subjects_stats,
                         total_likes=total_likes,
                         total_comments=total_comments,
                         top_posters=top_posters)
