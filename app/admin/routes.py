from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import current_user
from app import db
from app.admin import bp
from app.forms import SubjectForm, BulkEmailForm
from app.models import Subject, User, Post, Comment, Document
from app.utils import admin_required
import re
import os


def slugify(text):
    """Convert text to URL-friendly slug."""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')


@bp.route('/')
@admin_required
def dashboard():
    """Admin dashboard with overview statistics."""
    total_users    = User.query.count()
    total_posts    = Post.query.count()
    total_subjects = Subject.query.count()
    total_comments = Comment.query.count()

    pending_count  = Post.query.filter_by(status='pending').count()
    approved_count = Post.query.filter_by(status='approved').count()
    rejected_count = Post.query.filter_by(status='rejected').count()

    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_posts = Post.query.order_by(Post.created_at.desc()).limit(5).all()

    return render_template(
        'admin/dashboard.html',
        title='Admin Dashboard',
        total_users=total_users,
        total_posts=total_posts,
        total_subjects=total_subjects,
        total_comments=total_comments,
        pending_count=pending_count,
        approved_count=approved_count,
        rejected_count=rejected_count,
        recent_users=recent_users,
        recent_posts=recent_posts,
    )


# ============ SUBJECT MANAGEMENT ============

@bp.route('/subjects')
@admin_required
def subjects():
    subjects = Subject.query.order_by(Subject.order, Subject.name).all()
    return render_template('admin/subjects.html', title='Manage Subjects', subjects=subjects)


@bp.route('/subjects/create', methods=['GET', 'POST'])
@admin_required
def create_subject():
    form = SubjectForm()

    if form.validate_on_submit():
        slug = slugify(form.name.data)
        existing = Subject.query.filter_by(slug=slug).first()
        if existing:
            flash('A subject with this name already exists.', 'danger')
            return redirect(url_for('admin.create_subject'))

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
@admin_required
def edit_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    form = SubjectForm()

    if form.validate_on_submit():
        new_slug = slugify(form.name.data)
        if new_slug != subject.slug:
            existing = Subject.query.filter_by(slug=new_slug).first()
            if existing and existing.id != subject.id:
                flash('A subject with this name already exists.', 'danger')
                return redirect(url_for('admin.edit_subject', subject_id=subject.id))
            subject.slug = new_slug

        subject.name        = form.name.data
        subject.description = form.description.data
        subject.icon        = form.icon.data or 'book'
        subject.color       = form.color.data or '#6366f1'
        subject.order       = int(form.order.data) if form.order.data else 0
        subject.is_active   = form.is_active.data
        db.session.commit()
        flash(f'Subject "{subject.name}" updated successfully!', 'success')
        return redirect(url_for('admin.subjects'))

    elif request.method == 'GET':
        form.name.data        = subject.name
        form.description.data = subject.description
        form.icon.data        = subject.icon
        form.color.data       = subject.color
        form.order.data       = str(subject.order)
        form.is_active.data   = subject.is_active

    return render_template('admin/subject_form.html', title='Edit Subject', form=form, subject=subject)


@bp.route('/subjects/<int:subject_id>/delete', methods=['POST'])
@admin_required
def delete_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    posts = Post.query.filter_by(subject_id=subject.id).all()
    for post in posts:
        post.subject_id = None
    name = subject.name
    db.session.delete(subject)
    db.session.commit()
    flash(f'Subject "{name}" deleted successfully.', 'success')
    return redirect(url_for('admin.subjects'))


@bp.route('/subjects/<int:subject_id>/toggle', methods=['POST'])
@admin_required
def toggle_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    subject.is_active = not subject.is_active
    db.session.commit()
    status = 'activated' if subject.is_active else 'deactivated'
    flash(f'Subject "{subject.name}" {status}.', 'success')
    return redirect(url_for('admin.subjects'))


# ============ USER MANAGEMENT ============

@bp.route('/users')
@admin_required
def users():
    page   = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    query  = User.query

    if search:
        query = query.filter(
            db.or_(
                User.username.contains(search),
                User.email.contains(search),
                User.full_name.contains(search)
            )
        )

    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    return render_template('admin/users.html', title='Manage Users', users=users, search=search)


@bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@admin_required
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'warning')
        return redirect(url_for('admin.users'))
    user.is_active = not user.is_active
    db.session.commit()
    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User "{user.username}" has been {status}.', 'success')
    return redirect(url_for('admin.users'))


@bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'warning')
        return redirect(url_for('admin.users'))

    username = user.username

    if user.profile_picture != 'default.jpg':
        profile_pic_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'], 'profiles', user.profile_picture
        )
        if os.path.exists(profile_pic_path):
            os.remove(profile_pic_path)

    for post in user.posts:
        if post.document:
            doc_path = post.document.file_path
            if os.path.exists(doc_path):
                os.remove(doc_path)

    db.session.delete(user)
    db.session.commit()
    flash(f'User "{username}" and all their content has been deleted.', 'success')
    return redirect(url_for('admin.users'))


# ============ POST MANAGEMENT ============

@bp.route('/posts')
@admin_required
def posts():
    page           = request.args.get('page', 1, type=int)
    search         = request.args.get('search', '')
    subject_filter = request.args.get('subject', type=int)
    status_filter  = request.args.get('status', '')

    query = Post.query

    if search:
        query = query.filter(
            db.or_(
                Post.title.contains(search),
                Post.description.contains(search)
            )
        )

    if subject_filter:
        query = query.filter_by(subject_id=subject_filter)

    if status_filter in ('pending', 'approved', 'rejected'):
        query = query.filter_by(status=status_filter)

    posts = query.order_by(Post.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    subjects = Subject.query.filter_by(is_active=True).order_by(Subject.name).all()

    return render_template(
        'admin/posts.html',
        title='Manage Posts',
        posts=posts,
        subjects=subjects,
        search=search,
        subject_filter=subject_filter,
        status_filter=status_filter,
    )


@bp.route('/posts/<int:post_id>/delete', methods=['POST'])
@admin_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    title = post.title

    if post.document:
        file_path = post.document.file_path
        if os.path.exists(file_path):
            os.remove(file_path)

    db.session.delete(post)
    db.session.commit()
    flash(f'Post "{title}" has been deleted.', 'success')
    return redirect(url_for('admin.posts'))


# ============ POST MODERATION ============

@bp.route('/moderation')
@admin_required
def moderation():
    tab  = request.args.get('tab', 'pending')
    page = request.args.get('page', 1, type=int)

    valid_tabs = ('pending', 'approved', 'rejected')
    if tab not in valid_tabs:
        tab = 'pending'

    query = Post.query.filter_by(status=tab)
    posts = query.order_by(Post.created_at.desc()).paginate(
        page=page, per_page=15, error_out=False
    )

    counts = {
        'pending':  Post.query.filter_by(status='pending').count(),
        'approved': Post.query.filter_by(status='approved').count(),
        'rejected': Post.query.filter_by(status='rejected').count(),
    }

    return render_template(
        'admin/moderation.html',
        title='Post Moderation',
        posts=posts,
        tab=tab,
        counts=counts,
    )


@bp.route('/moderation/<int:post_id>/approve', methods=['POST'])
@admin_required
def approve_post(post_id):
    post = Post.query.get_or_404(post_id)
    post.status           = 'approved'
    post.rejection_reason = None
    db.session.commit()
    flash(f'Post "{post.title}" approved and is now live.', 'success')
    next_url = request.form.get('next') or url_for('admin.moderation')
    return redirect(next_url)


@bp.route('/moderation/<int:post_id>/reject', methods=['POST'])
@admin_required
def reject_post(post_id):
    post = Post.query.get_or_404(post_id)
    reason = request.form.get('reason', '').strip()
    post.status           = 'rejected'
    post.rejection_reason = reason or None
    db.session.commit()
    flash(f'Post "{post.title}" has been rejected.', 'warning')
    next_url = request.form.get('next') or url_for('admin.moderation')
    return redirect(next_url)


# ============ STATISTICS & REPORTS ============

@bp.route('/statistics')
@admin_required
def statistics():
    total_users     = User.query.count()
    active_users    = User.query.filter_by(is_active=True).count()
    inactive_users  = total_users - active_users

    total_posts             = Post.query.count()
    posts_with_documents    = Post.query.filter_by(has_document=True).count()
    posts_without_documents = total_posts - posts_with_documents

    subjects_stats = []
    subjects = Subject.query.all()
    for subject in subjects:
        subject.update_post_count()
        subjects_stats.append({
            'name':       subject.name,
            'post_count': subject.post_count,
            'color':      subject.color,
        })
    db.session.commit()

    from app.models import Like
    total_likes    = Like.query.count()
    total_comments = Comment.query.count()

    from sqlalchemy import func
    top_posters = db.session.query(
        User.username,
        User.full_name,
        func.count(Post.id).label('post_count')
    ).join(Post).group_by(User.id).order_by(func.count(Post.id).desc()).limit(10).all()

    return render_template(
        'admin/statistics.html',
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
        top_posters=top_posters,
    )


# ============ BULK EMAIL ============

@bp.route('/send-email', methods=['GET', 'POST'])
@admin_required
def send_email():
    import requests

    users       = User.query.filter(User.email.isnot(None)).all()
    total_users = len(users)

    form = BulkEmailForm()
    
    if form.validate_on_submit():
        subject  = form.subject.data.strip()
        body     = form.body.data.strip()
        send_to  = form.send_to.data
        selected = request.form.getlist('selected_emails')

        recipients = [u.email for u in users] if send_to == 'all' else selected

        if not recipients:
            flash('No recipients selected.', 'danger')
            return render_template('admin/send_email.html', users=users, total_users=total_users, form=form)

        sender = (
            current_app.config.get('MAIL_DEFAULT_SENDER') or
            current_app.config.get('MAIL_USERNAME')
        )

        api_key = current_app.config.get('BREVO_API_KEY')
        sent    = 0
        failed  = 0

        for email in recipients:
            try:
                response = requests.post(
                    "https://api.brevo.com/v3/smtp/email",
                    headers={
                        "api-key": api_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "sender": {"email": sender},
                        "to": [{"email": email}],
                        "subject": subject,
                        "htmlContent": body
                    }
                )
                if response.status_code == 201:
                    sent += 1
                else:
                    current_app.logger.error(f"Brevo error for {email}: {response.text}")
                    failed += 1
            except Exception as e:
                current_app.logger.error(f"Failed to send to {email}: {e}")
                failed += 1

        if sent:
            result = f'Email sent successfully to {sent} user(s).'
            if failed:
                result += f' {failed} failed — check the server logs.'
            flash(result, 'success')
        else:
            flash(f'All {failed} sends failed. Check your Brevo API key and sender address.', 'danger')

        return redirect(url_for('admin.send_email'))

    return render_template('admin/send_email.html', users=users, total_users=total_users, form=form)