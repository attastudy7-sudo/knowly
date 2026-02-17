import os
import requests
from flask import render_template, redirect, url_for, flash, request, current_app, abort, make_response
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.posts import bp
from app.forms import CreatePostForm, CommentForm
from app.models import Post, Document, Comment, Like, Subject
from app.cloudinary_helper import upload_document, delete_document


def allowed_file(filename, allowed_extensions):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """
    Create a new post with optional document upload.
    """
    form = CreatePostForm()
    
    # Populate subject choices
    subjects = Subject.query.filter_by(is_active=True).order_by(Subject.order, Subject.name).all()
    form.subject.choices = [(0, 'Select a subject (optional)')] + [(s.id, s.name) for s in subjects]
    
    if form.validate_on_submit():
        # Create the post
        post = Post(
            title=form.title.data,
            description=form.description.data,
            author=current_user
        )
        
        # Set subject if selected
        if form.subject.data and form.subject.data != 0:
            post.subject_id = form.subject.data
            subject = Subject.query.get(form.subject.data)
            if subject:
                subject.update_post_count()
        
        # Handle document upload if provided
        if form.document.data:
            file = form.document.data
            
            if allowed_file(file.filename, current_app.config['ALLOWED_DOCUMENT_EXTENSIONS']):
                # Upload to Cloudinary
                result = upload_document(file)
                
                if result:
                    # Create document record with Cloudinary URL
                    document = Document(
                        filename=secure_filename(file.filename),
                        original_filename=secure_filename(file.filename),
                        file_path=result['url'],          # Cloudinary URL
                        file_type=file.filename.rsplit('.', 1)[1].lower(),
                        file_size=result['file_size'],
                        is_paid=form.is_paid.data if form.is_paid.data else False,
                        price=float(form.price.data) if form.price.data else 0.0
                    )
                    
                    db.session.add(document)
                    db.session.flush()
                    
                    post.has_document = True
                    post.document_id = document.id
                else:
                    flash('Document upload failed. Please try again.', 'danger')
                    return render_template('posts/create.html', title='Create Post', form=form)
        
        db.session.add(post)
        db.session.commit()
        
        flash('Your post has been created!', 'success')
        return redirect(url_for('main.index'))
    
    return render_template('posts/create.html', title='Create Post', form=form)


@bp.route('/<int:post_id>')
def view(post_id):
    """
    View a single post with comments.
    """
    post = Post.query.get_or_404(post_id)
    comment_form = CommentForm()
    
    page = request.args.get('page', 1, type=int)
    comments = post.comments.order_by(Comment.created_at.desc()).paginate(
        page=page,
        per_page=current_app.config['COMMENTS_PER_PAGE'],
        error_out=False
    )
    
    return render_template('posts/view.html', 
                         title=post.title, 
                         post=post, 
                         comment_form=comment_form,
                         comments=comments)


@bp.route('/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(post_id):
    """
    Edit an existing post (only by the author).
    """
    post = Post.query.get_or_404(post_id)
    
    if post.author != current_user:
        flash('You cannot edit this post.', 'danger')
        return redirect(url_for('posts.view', post_id=post.id))
    
    form = CreatePostForm()
    
    subjects = Subject.query.filter_by(is_active=True).order_by(Subject.order, Subject.name).all()
    form.subject.choices = [(0, 'Select a subject (optional)')] + [(s.id, s.name) for s in subjects]
    
    if form.validate_on_submit():
        post.title = form.title.data
        post.description = form.description.data
        
        old_subject_id = post.subject_id
        if form.subject.data and form.subject.data != 0:
            post.subject_id = form.subject.data
        else:
            post.subject_id = None
        
        if old_subject_id != post.subject_id:
            if old_subject_id:
                old_subject = Subject.query.get(old_subject_id)
                if old_subject:
                    old_subject.update_post_count()
            if post.subject_id:
                new_subject = Subject.query.get(post.subject_id)
                if new_subject:
                    new_subject.update_post_count()
        
        # Handle new document upload
        if form.document.data:
            # Delete old document from Cloudinary if exists
            if post.document:
                # Extract public_id from Cloudinary URL and delete
                old_url = post.document.file_path
                if 'cloudinary.com' in old_url:
                    # Extract public_id from URL
                    public_id = '/'.join(old_url.split('/')[7:]).rsplit('.', 1)[0]
                    delete_document(public_id)
                db.session.delete(post.document)
            
            file = form.document.data
            if allowed_file(file.filename, current_app.config['ALLOWED_DOCUMENT_EXTENSIONS']):
                result = upload_document(file)
                
                if result:
                    document = Document(
                        filename=secure_filename(file.filename),
                        original_filename=secure_filename(file.filename),
                        file_path=result['url'],
                        file_type=file.filename.rsplit('.', 1)[1].lower(),
                        file_size=result['file_size'],
                        is_paid=form.is_paid.data if form.is_paid.data else False,
                        price=float(form.price.data) if form.price.data else 0.0
                    )
                    
                    db.session.add(document)
                    db.session.flush()
                    
                    post.has_document = True
                    post.document_id = document.id
                else:
                    flash('Document upload failed. Please try again.', 'danger')
        
        db.session.commit()
        flash('Your post has been updated!', 'success')
        return redirect(url_for('posts.view', post_id=post.id))
    
    elif request.method == 'GET':
        form.title.data = post.title
        form.description.data = post.description
        if post.subject_id:
            form.subject.data = post.subject_id
    
    return render_template('posts/edit.html', title='Edit Post', form=form, post=post)


@bp.route('/<int:post_id>/delete', methods=['POST'])
@login_required
def delete(post_id):
    """
    Delete a post (only by the author).
    """
    post = Post.query.get_or_404(post_id)
    
    if post.author != current_user:
        flash('You cannot delete this post.', 'danger')
        return redirect(url_for('posts.view', post_id=post.id))
    
    # Delete document from Cloudinary if exists
    if post.document:
        old_url = post.document.file_path
        if 'cloudinary.com' in old_url:
            public_id = '/'.join(old_url.split('/')[7:]).rsplit('.', 1)[0]
            delete_document(public_id)
    
    db.session.delete(post)
    db.session.commit()
    
    flash('Your post has been deleted.', 'success')
    return redirect(url_for('main.index'))


@bp.route('/<int:post_id>/like', methods=['POST'])
@login_required
def like(post_id):
    """Like or unlike a post."""
    post = Post.query.get_or_404(post_id)
    
    existing_like = Like.query.filter_by(user_id=current_user.id, post_id=post.id).first()
    
    if existing_like:
        db.session.delete(existing_like)
        db.session.commit()
        flash('Post unliked.', 'info')
    else:
        new_like = Like(user_id=current_user.id, post_id=post.id)
        db.session.add(new_like)
        db.session.commit()
        flash('Post liked!', 'success')
    
    return redirect(request.referrer or url_for('main.index'))


@bp.route('/<int:post_id>/comment', methods=['POST'])
@login_required
def comment(post_id):
    """Add a comment to a post."""
    post = Post.query.get_or_404(post_id)
    form = CommentForm()
    
    if form.validate_on_submit():
        comment = Comment(
            content=form.content.data,
            author=current_user,
            post=post
        )
        db.session.add(comment)
        db.session.commit()
        flash('Your comment has been posted!', 'success')
    
    return redirect(url_for('posts.view', post_id=post.id))


@bp.route('/document/<int:document_id>/download')
@login_required
def download_document(document_id):
    """
    Download a document from Cloudinary.
    """
    document = Document.query.get_or_404(document_id)
    
    if not document.has_access(current_user):
        flash('You need to purchase this document to download it.', 'warning')
        return redirect(url_for('payments.checkout', document_id=document.id))
    
    # Increment download count
    document.download_count += 1
    db.session.commit()
    
    # Redirect to Cloudinary URL for download
    cloudinary_url = document.file_path
    return redirect(cloudinary_url)


@bp.route('/document/<int:document_id>/preview')
@login_required
def preview_document(document_id):
    """
    Preview a document from Cloudinary in the browser.
    """
    document = Document.query.get_or_404(document_id)
    
    if not document.has_access(current_user):
        flash('You need to purchase this document to view it.', 'warning')
        return redirect(url_for('payments.checkout', document_id=document.id))
    
    # For PDFs and images, redirect directly to Cloudinary URL
    previewable_types = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp'}
    file_type = document.file_type.lower()
    
    if file_type not in previewable_types:
        flash('Preview is only available for PDF and image files.', 'info')
        return redirect(url_for('posts.download_document', document_id=document.id))
    
    # Redirect to Cloudinary URL for preview
    return redirect(document.file_path)


@bp.route('/terms')
def terms():
    """Terms of Service page."""
    return render_template('terms.html', title='Terms of Service')