import os
from flask import render_template, redirect, url_for, flash, request, current_app, send_file, abort, make_response
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.posts import bp
from app.forms import CreatePostForm, CommentForm
from app.models import Post, Document, Comment, Like, Subject
import uuid


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
            # Update subject post count
            subject = Subject.query.get(form.subject.data)
            if subject:
                subject.update_post_count()
        
        # Handle document upload if provided
        if form.document.data:
            file = form.document.data
            
            if allowed_file(file.filename, current_app.config['ALLOWED_DOCUMENT_EXTENSIONS']):
                # Generate unique filename to avoid conflicts
                file_ext = file.filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
                
                # Save file
                file_path = os.path.join(
                    current_app.config['UPLOAD_FOLDER'],
                    'documents',
                    unique_filename
                )
                file.save(file_path)
                
                # Create document record
                document = Document(
                    filename=unique_filename,
                    original_filename=secure_filename(file.filename),
                    file_path=file_path,
                    file_type=file_ext,
                    file_size=os.path.getsize(file_path),
                    is_paid=form.is_paid.data if form.is_paid.data else False,
                    price=float(form.price.data) if form.price.data else 0.0
                )
                
                db.session.add(document)
                db.session.flush()  # Get the document ID
                
                # Link document to post
                post.has_document = True
                post.document_id = document.id
        
        # Save post to database
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
    
    # Get comments for this post
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
    
    # Check if current user is the author
    if post.author != current_user:
        flash('You cannot edit this post.', 'danger')
        return redirect(url_for('posts.view', post_id=post.id))
    
    form = CreatePostForm()
    
    # Populate subject choices
    subjects = Subject.query.filter_by(is_active=True).order_by(Subject.order, Subject.name).all()
    form.subject.choices = [(0, 'Select a subject (optional)')] + [(s.id, s.name) for s in subjects]
    
    if form.validate_on_submit():
        post.title = form.title.data
        post.description = form.description.data
        
        # Update subject
        old_subject_id = post.subject_id
        if form.subject.data and form.subject.data != 0:
            post.subject_id = form.subject.data
        else:
            post.subject_id = None
        
        # Update subject post counts if changed
        if old_subject_id != post.subject_id:
            if old_subject_id:
                old_subject = Subject.query.get(old_subject_id)
                if old_subject:
                    old_subject.update_post_count()
            if post.subject_id:
                new_subject = Subject.query.get(post.subject_id)
                if new_subject:
                    new_subject.update_post_count()
        
        # Handle new document upload if provided
        if form.document.data:
            # Delete old document if exists
            if post.document:
                old_file_path = post.document.file_path
                if os.path.exists(old_file_path):
                    os.remove(old_file_path)
                db.session.delete(post.document)
            
            # Upload new document
            file = form.document.data
            if allowed_file(file.filename, current_app.config['ALLOWED_DOCUMENT_EXTENSIONS']):
                file_ext = file.filename.rsplit('.', 1)[1].lower()
                unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
                
                file_path = os.path.join(
                    current_app.config['UPLOAD_FOLDER'],
                    'documents',
                    unique_filename
                )
                file.save(file_path)
                
                document = Document(
                    filename=unique_filename,
                    original_filename=secure_filename(file.filename),
                    file_path=file_path,
                    file_type=file_ext,
                    file_size=os.path.getsize(file_path),
                    is_paid=form.is_paid.data if form.is_paid.data else False,
                    price=float(form.price.data) if form.price.data else 0.0
                )
                
                db.session.add(document)
                db.session.flush()
                
                post.has_document = True
                post.document_id = document.id
        
        db.session.commit()
        flash('Your post has been updated!', 'success')
        return redirect(url_for('posts.view', post_id=post.id))
    
    elif request.method == 'GET':
        # Pre-fill form with current data
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
    
    # Check if current user is the author
    if post.author != current_user:
        flash('You cannot delete this post.', 'danger')
        return redirect(url_for('posts.view', post_id=post.id))
    
    # Delete associated document file
    if post.document:
        file_path = post.document.file_path
        if os.path.exists(file_path):
            os.remove(file_path)
    
    # Delete post (cascades to document, comments, likes)
    db.session.delete(post)
    db.session.commit()
    
    flash('Your post has been deleted.', 'success')
    return redirect(url_for('main.index'))


@bp.route('/<int:post_id>/like', methods=['POST'])
@login_required
def like(post_id):
    """
    Like or unlike a post.
    """
    post = Post.query.get_or_404(post_id)
    
    # Check if already liked
    existing_like = Like.query.filter_by(user_id=current_user.id, post_id=post.id).first()
    
    if existing_like:
        # Unlike
        db.session.delete(existing_like)
        db.session.commit()
        flash('Post unliked.', 'info')
    else:
        # Like
        new_like = Like(user_id=current_user.id, post_id=post.id)
        db.session.add(new_like)
        db.session.commit()
        flash('Post liked!', 'success')
    
    # Redirect back to the referring page
    return redirect(request.referrer or url_for('main.index'))


@bp.route('/<int:post_id>/comment', methods=['POST'])
@login_required
def comment(post_id):
    """
    Add a comment to a post.
    """
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
    Download a document.
    Checks if user has access (for paid documents in the future).
    """
    document = Document.query.get_or_404(document_id)
    
    # Check access
    if not document.has_access(current_user):
        flash('You need to purchase this document to download it.', 'warning')
        return redirect(url_for('payments.checkout', document_id=document.id))
    
    # Increment download count
    document.download_count += 1
    db.session.commit()
    
    # Send file
    return send_file(
        document.file_path,
        as_attachment=True,
        download_name=document.original_filename
    )


@bp.route('/document/<int:document_id>/preview')
@login_required
def preview_document(document_id):
    """
    Preview a document in the browser without downloading.
    Supports PDFs and images (PNG, JPG, JPEG, GIF, WEBP).
    """
    document = Document.query.get_or_404(document_id)
    
    # Check access
    if not document.has_access(current_user):
        flash('You need to purchase this document to view it.', 'warning')
        return redirect(url_for('payments.checkout', document_id=document.id))
    
    # Determine MIME type based on file extension
    mime_types = {
        'pdf': 'application/pdf',
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'webp': 'image/webp'
    }
    
    file_type = document.file_type.lower()
    
    if file_type not in mime_types:
        flash('Preview is only available for PDF and image files.', 'info')
        return redirect(url_for('posts.download_document', document_id=document.id))
    
    # Check if file exists
    if not os.path.exists(document.file_path):
        flash('Document file not found.', 'error')
        abort(404)
    
    # Read file content
    with open(document.file_path, 'rb') as f:
        file_data = f.read()
    
    # Create response with file data
    response = make_response(file_data)
    response.headers['Content-Type'] = mime_types[file_type]
    response.headers['Content-Disposition'] = 'inline'  # Force inline display, no filename
    response.headers['Content-Length'] = len(file_data)
    
    # Additional headers for better mobile support
    response.headers['Cache-Control'] = 'public, max-age=3600'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    return response