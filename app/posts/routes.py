import cloudinary.uploader
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.posts import bp
from app.forms import CreatePostForm, CommentForm
from app.models import Post, Document, Comment, Like, Subject


def allowed_file(filename, allowed_extensions):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def upload_document_to_cloudinary(file, form):
    """Upload a file to Cloudinary and return a Document model instance."""
    try:
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        original_filename = secure_filename(file.filename)

        # Images use resource_type 'image'; everything else (PDF, DOCX, etc.) uses 'raw'
        resource_type = 'image' if file_ext in {'png', 'jpg', 'jpeg', 'gif', 'webp'} else 'raw'

        result = cloudinary.uploader.upload(
            file,
            folder='edushare/documents',
            resource_type=resource_type,
            use_filename=True,
            unique_filename=True,
        )

        return Document(
            filename=result['public_id'],        # Cloudinary public_id (used for deletion)
            original_filename=original_filename,
            file_path=result['secure_url'],      # Full HTTPS URL (used for download/preview)
            file_type=file_ext,
            file_size=result.get('bytes', 0),
            is_paid=form.is_paid.data or False,
            price=float(form.price.data) if form.price.data else 0.0
        )
    except Exception as e:
        current_app.logger.error(f"Cloudinary upload failed: {e}")
        flash('File upload failed. Please try again.', 'danger')
        return None


def delete_document_from_cloudinary(document):
    """Delete a document from Cloudinary by its public_id."""
    try:
        resource_type = 'image' if document.file_type in {'png', 'jpg', 'jpeg', 'gif', 'webp'} else 'raw'
        cloudinary.uploader.destroy(document.filename, resource_type=resource_type)
    except Exception as e:
        current_app.logger.warning(f"Failed to delete Cloudinary file '{document.filename}': {e}")


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
            subject = db.session.get(Subject, form.subject.data)
            if subject:
                subject.post_count = subject.posts.count() + 1

        # Handle document upload if provided
        # Check filename too — FileStorage is truthy even when empty
        if form.document.data and form.document.data.filename:
            file = form.document.data
            if allowed_file(file.filename, current_app.config['ALLOWED_DOCUMENT_EXTENSIONS']):
                document = upload_document_to_cloudinary(file, form)
                if document:
                    db.session.add(document)
                    db.session.flush()  # Get the document ID before linking
                    post.has_document = True
                    post.document_id = document.id

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

        # Update subject
        old_subject_id = post.subject_id
        if form.subject.data and form.subject.data != 0:
            post.subject_id = form.subject.data
        else:
            post.subject_id = None

        # Update subject post counts if subject changed
        if old_subject_id != post.subject_id:
            if old_subject_id:
                old_subject = db.session.get(Subject, old_subject_id)
                if old_subject:
                    old_subject.post_count = old_subject.posts.count()
            if post.subject_id:
                new_subject = db.session.get(Subject, post.subject_id)
                if new_subject:
                    new_subject.post_count = new_subject.posts.count() + 1

        # Handle new document upload if provided
        # Check filename too — FileStorage is truthy even when empty
        if form.document.data and form.document.data.filename:
            # Delete old document from Cloudinary and DB if it exists
            if post.document:
                delete_document_from_cloudinary(post.document)
                db.session.delete(post.document)

            file = form.document.data
            if allowed_file(file.filename, current_app.config['ALLOWED_DOCUMENT_EXTENSIONS']):
                document = upload_document_to_cloudinary(file, form)
                if document:
                    db.session.add(document)
                    db.session.flush()
                    post.has_document = True
                    post.document_id = document.id

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

    # Delete associated document from Cloudinary
    if post.document:
        delete_document_from_cloudinary(post.document)

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
    """
    Add a comment to a post.
    """
    post = Post.query.get_or_404(post_id)
    form = CommentForm()

    if form.validate_on_submit():
        new_comment = Comment(
            content=form.content.data,
            author=current_user,
            post=post
        )
        db.session.add(new_comment)
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

    document.download_count += 1
    db.session.commit()

    image_types = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    if document.file_type.lower() in image_types:
        # Images support fl_attachment transformation
        download_url = document.file_path.replace('/upload/', '/upload/fl_attachment/')
    else:
        # Raw files (PDF, DOCX, etc.) — serve URL directly, browser handles download
        download_url = document.file_path

    return redirect(download_url)


@bp.route('/document/<int:document_id>/preview')
@login_required
def preview_document(document_id):
    """
    Preview a document inline via its Cloudinary URL.
    Supports PDFs and images.
    """
    document = Document.query.get_or_404(document_id)

    if not document.has_access(current_user):
        flash('You need to purchase this document to view it.', 'warning')
        return redirect(url_for('payments.checkout', document_id=document.id))

    previewable = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp'}
    if document.file_type.lower() not in previewable:
        flash('Preview is only available for PDF and image files.', 'info')
        return redirect(url_for('posts.download_document', document_id=document.id))

    # Cloudinary serves the file inline — just redirect to the secure URL
    return redirect(document.file_path)