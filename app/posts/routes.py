import hashlib
import hmac
import time
import urllib.parse
import os
import uuid

import requests as req

from flask import (
    Response, render_template, redirect, stream_with_context,
    url_for, flash, request, current_app, jsonify, send_from_directory,
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app import db
from app.posts import bp
from app.forms import CreatePostForm, CommentForm
from app.models import Post, Document, Comment, Like, Subject


# ── Environment detection ─────────────────────────────────────────────────────

def _is_local() -> bool:
    """True when running in local development mode (no Cloudinary keys set)."""
    return not bool(current_app.config.get('CLOUDINARY_CLOUD_NAME'))


def _local_upload_folder() -> str:
    """Absolute path to the local uploads folder. Created if it doesn't exist."""
    folder = os.path.join(current_app.root_path, 'static', 'uploads', 'documents')
    os.makedirs(folder, exist_ok=True)
    return folder


# ── Helpers ───────────────────────────────────────────────────────────────────

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def _pricing_allowed() -> bool:
    """
    BACKDOOR: Returns True if the current user is allowed to set a price.

    By default only admins can set prices. To temporarily open pricing to
    ALL users (e.g. during a promotion or while testing), set this env var:

        ALLOW_ALL_PRICING=1

    in your .env or hosting environment, then restart the app. Remove it to
    revert to admin-only pricing.
    """
    if current_app.config.get('ALLOW_ALL_PRICING'):
        return True
    return current_user.is_authenticated and current_user.is_admin


def _apply_pricing(document, form):
    """
    Set is_paid/price on a Document from form data, but only if the current
    user is allowed to set pricing. Regular users always get free documents.
    """
    if _pricing_allowed() and form.is_paid.data:
        try:
            price = float(form.price.data) if form.price.data else 0.0
        except (ValueError, TypeError):
            price = 0.0
        document.is_paid = True
        document.price   = round(price, 2)
    else:
        document.is_paid = False
        document.price   = 0.0


# ── Storage: upload ───────────────────────────────────────────────────────────

def upload_document(file, form, json_file=None):
    """
    Upload a file to Cloudinary (production) or local disk (development).
    Returns a Document model instance or None on failure.
    """
    if _is_local():
        return _upload_local(file, form, json_file)
    return _upload_cloudinary(file, form, json_file)


def _upload_local(file, form, json_file=None):
    """Save file to app/static/uploads/documents/ for local dev."""
    try:
        file_ext          = file.filename.rsplit('.', 1)[1].lower()
        original_filename = secure_filename(file.filename)
        unique_name       = f"{uuid.uuid4().hex}.{file_ext}"
        upload_folder     = _local_upload_folder()
        save_path         = os.path.join(upload_folder, unique_name)

        file.save(save_path)
        file_size = os.path.getsize(save_path)

        # file_path stored as the relative URL path served by Flask
        file_url = f"/static/uploads/documents/{unique_name}"

        document = Document(
            filename=unique_name,
            original_filename=original_filename,
            file_path=file_url,
            file_type=file_ext,
            file_size=file_size,
            is_paid=False,
            price=0.0,
        )
        
        # Handle JSON sidecar if provided
        if json_file and json_file.filename:
            json_ext = 'json'
            json_unique_name = f"{uuid.uuid4().hex}.{json_ext}"
            json_save_path = os.path.join(upload_folder, json_unique_name)
            json_file.save(json_save_path)
            document.json_sidecar_path = f"/static/uploads/documents/{json_unique_name}"
        
        _apply_pricing(document, form)
        return document

    except Exception as e:
        current_app.logger.error(f"Local upload failed: {e}")
        flash('File upload failed. Please try again.', 'danger')
        return None


def _upload_cloudinary(file, form, json_file=None):
    """Upload to Cloudinary for production."""
    try:
        import cloudinary.uploader
        file_ext          = file.filename.rsplit('.', 1)[1].lower()
        original_filename = secure_filename(file.filename)

        result = cloudinary.uploader.upload(
            file,
            folder='edushare/documents',
            resource_type='auto',
            type='upload',
            use_filename=True,
            unique_filename=True,
            format=file_ext,
        )

        document = Document(
            filename=result['public_id'],
            original_filename=original_filename,
            file_path=result['secure_url'],
            file_type=file_ext,
            file_size=result.get('bytes', 0),
            is_paid=False,
            price=0.0,
        )
        
        # Handle JSON sidecar if provided
        if json_file and json_file.filename:
            json_result = cloudinary.uploader.upload(
                json_file,
                folder='edushare/documents',
                resource_type='raw',
                type='upload',
                use_filename=True,
                unique_filename=True,
                format='json',
            )
            document.json_sidecar_path = json_result['secure_url']
        
        _apply_pricing(document, form)
        return document

    except Exception as e:
        current_app.logger.error(f"Cloudinary upload failed: {e}")
        flash('File upload failed. Please try again.', 'danger')
        return None


# ── Storage: delete ───────────────────────────────────────────────────────────

def delete_document(document):
    """Delete a document from Cloudinary (prod) or local disk (dev)."""
    if _is_local():
        _delete_local(document)
    else:
        _delete_cloudinary(document)


def _delete_local(document):
    """Remove file from local disk."""
    try:
        upload_folder = _local_upload_folder()
        file_path     = os.path.join(upload_folder, document.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            
        # Delete JSON sidecar if it exists
        if document.json_sidecar_path:
            import os
            json_filename = os.path.basename(document.json_sidecar_path)
            json_path = os.path.join(upload_folder, json_filename)
            if os.path.exists(json_path):
                os.remove(json_path)
    except Exception as e:
        current_app.logger.warning(f"Failed to delete local file '{document.filename}': {e}")


def _delete_cloudinary(document):
    """Remove file from Cloudinary."""
    try:
        import cloudinary.uploader
        resource_type = (
            'image' if document.file_type in {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            else 'raw'
        )
        cloudinary.uploader.destroy(document.filename, resource_type=resource_type)
        
        # Delete JSON sidecar if it exists
        if document.json_sidecar_path:
            # Extract public_id from JSON sidecar path
            # Cloudinary URL format: https://res.cloudinary.com/<cloud_name>/image/upload/<public_id>.<format>
            import urllib.parse
            parsed_url = urllib.parse.urlparse(document.json_sidecar_path)
            path_parts = parsed_url.path.split('/')
            if len(path_parts) > 3:  # Skip /res.cloudinary.com/<cloud_name>/<resource_type>/<upload_type>/
                public_id = '/'.join(path_parts[5:])  # Get everything after /<resource_type>/<upload_type>/
                if public_id.endswith('.json'):
                    public_id = public_id[:-5]  # Remove .json extension
                cloudinary.uploader.destroy(public_id, resource_type='raw')
    except Exception as e:
        current_app.logger.warning(f"Failed to delete Cloudinary file '{document.filename}': {e}")


# ── Storage: stream / serve ───────────────────────────────────────────────────

def _signed_proxy_token(document_id: int, expires: int, secret: bytes) -> str:
    return hmac.new(secret, f'{document_id}:{expires}'.encode(), hashlib.sha256).hexdigest()


def _stream_document(document, as_attachment: bool = False):
    """
    Return (body_iterator, response_kwargs) for serving a document.
    Uses local file serving in dev, Cloudinary streaming in prod.
    """
    if _is_local():
        return _stream_local(document, as_attachment)
    return _stream_cloudinary(document, as_attachment)


def _stream_local(document, as_attachment: bool = False):
    """Serve file directly from local disk."""
    try:
        upload_folder = _local_upload_folder()
        file_path     = os.path.join(upload_folder, document.filename)

        if not os.path.exists(file_path):
            current_app.logger.error(f"Local file not found: {file_path}")
            return None, None

        # Determine MIME type
        ext_mime = {
            'pdf':  'application/pdf',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'doc':  'application/msword',
            'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'ppt':  'application/vnd.ms-powerpoint',
            'txt':  'text/plain',
            'png':  'image/png',
            'jpg':  'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif':  'image/gif',
        }
        content_type = ext_mime.get(document.file_type.lower(), 'application/octet-stream')

        def generate():
            with open(file_path, 'rb') as f:
                while chunk := f.read(8192):
                    yield chunk

        headers = {}
        if as_attachment:
            safe_name = urllib.parse.quote(document.original_filename or 'download')
            headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{safe_name}"
        headers['Content-Length'] = str(os.path.getsize(file_path))

        return (
            stream_with_context(generate()),
            dict(status=200, content_type=content_type, headers=headers),
        )

    except Exception as e:
        current_app.logger.error(f"Local file serve failed: {e}")
        return None, None


def _stream_cloudinary(document, as_attachment: bool = False):
    """Stream file from Cloudinary."""
    try:
        upstream = req.get(document.file_path, stream=True, timeout=20)
        upstream.raise_for_status()
    except Exception as e:
        current_app.logger.error(
            f"Cloudinary fetch failed for document {document.id} "
            f"({document.file_path}): {e}"
        )
        return None, None

    content_type = upstream.headers.get('Content-Type', 'application/octet-stream')
    headers = {}

    if as_attachment:
        safe_name = urllib.parse.quote(document.original_filename or 'download')
        headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{safe_name}"

    if 'Content-Length' in upstream.headers:
        headers['Content-Length'] = upstream.headers['Content-Length']

    return (
        stream_with_context(upstream.iter_content(chunk_size=8192)),
        dict(status=200, content_type=content_type, headers=headers),
    )


# ── Post CRUD ─────────────────────────────────────────────────────────────────

@bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form = CreatePostForm()
    subjects = Subject.query.filter_by(is_active=True).order_by(Subject.order, Subject.name).all()
    form.subject.choices = [(0, 'Select a subject (optional)')] + [(s.id, s.name) for s in subjects]

    if form.validate_on_submit():
        post = Post(
            title=form.title.data,
            description=form.description.data,
            author=current_user,
            status='pending',
        )

        if form.subject.data and form.subject.data != 0:
            post.subject_id = form.subject.data
            subject = db.session.get(Subject, form.subject.data)
            if subject:
                subject.post_count = subject.posts.count() + 1

        if form.document.data and form.document.data.filename:
            file = form.document.data
            if allowed_file(file.filename, current_app.config['ALLOWED_DOCUMENT_EXTENSIONS']):
                # Handle JSON sidecar if provided
                json_file = form.json_sidecar.data if hasattr(form, 'json_sidecar') and form.json_sidecar.data else None
                document = upload_document(file, form, json_file)
                if document:
                    db.session.add(document)
                    db.session.flush()
                    post.has_document = True
                    post.document_id  = document.id

        db.session.add(post)
        db.session.commit()
        
        # Update user's activity streak and add XP
        current_user.update_streak()
        current_user.add_xp(10)  # +10 XP for creating a post
        
        flash(
            'Your post has been submitted and is awaiting admin approval. '
            'It will appear in the feed once reviewed.',
            'info'
        )
        return redirect(url_for('main.index'))

    return render_template('posts/create.html', title='Create Post', form=form,
                           show_pricing=_pricing_allowed())


@bp.route('/<int:post_id>')
def view(post_id):
    post = Post.query.get_or_404(post_id)

    if post.status != 'approved':
        if not current_user.is_authenticated or current_user.id != post.user_id:
            flash('This post is not available.', 'warning')
            return redirect(url_for('main.index'))

    comment_form = CommentForm()
    page = request.args.get('page', 1, type=int)
    comments = post.comments.order_by(Comment.created_at.desc()).paginate(
        page=page,
        per_page=current_app.config['COMMENTS_PER_PAGE'],
        error_out=False
    )

    # ── Quiz / leaderboard context ────────────────────────────────────────
    # has_quiz is passed to the template so it can show/hide the Take Quiz
    # button and the leaderboard section without making a DB call in Jinja2.
    #
    # PDFs uploaded without a JSON sidecar (manually created notes, externally
    # sourced study guides, etc.) will have no QuizData record.  That is
    # normal and valid — the template shows a "Quiz not available" notice
    # instead of the Take Quiz button for those posts.
    from app.models import QuizData, QuizLeaderboard

    quiz_data = None
    has_quiz  = False
    leaderboard_entries = []
    user_entry          = None
    total_participants  = 0

    if post.has_document and post.document and post.document.file_type == 'pdf':
        quiz_data = QuizData.query.filter_by(post_id=post.id).first()
        has_quiz  = quiz_data is not None

        if has_quiz:
            leaderboard_entries = (
                QuizLeaderboard.query
                .filter_by(post_id=post.id)
                .order_by(
                    QuizLeaderboard.score_pct.desc(),
                    QuizLeaderboard.time_taken.asc(),
                    QuizLeaderboard.created_at.asc()
                )
                .limit(10)
                .all()
            )
            total_participants = QuizLeaderboard.query.filter_by(post_id=post.id).count()

            if current_user.is_authenticated:
                user_entry = QuizLeaderboard.query.filter_by(
                    post_id=post.id,
                    user_id=current_user.id
                ).first()

    return render_template(
        'posts/view.html',
        title=post.title,
        post=post,
        comment_form=comment_form,
        comments=comments,
        # quiz context
        has_quiz=has_quiz,
        leaderboard_entries=leaderboard_entries,
        user_entry=user_entry,
        total_participants=total_participants,
    )

@bp.route('/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(post_id):
    post = Post.query.get_or_404(post_id)

    if post.author != current_user:
        flash('You cannot edit this post.', 'danger')
        return redirect(url_for('posts.view', post_id=post.id))

    form = CreatePostForm()
    subjects = Subject.query.filter_by(is_active=True).order_by(Subject.order, Subject.name).all()
    form.subject.choices = [(0, 'Select a subject (optional)')] + [(s.id, s.name) for s in subjects]

    if form.validate_on_submit():
        post.title            = form.title.data
        post.description      = form.description.data
        post.status           = 'pending'
        post.rejection_reason = None

        old_subject_id  = post.subject_id
        post.subject_id = form.subject.data if (form.subject.data and form.subject.data != 0) else None

        if old_subject_id != post.subject_id:
            if old_subject_id:
                old_sub = db.session.get(Subject, old_subject_id)
                if old_sub:
                    old_sub.post_count = old_sub.posts.count()
            if post.subject_id:
                new_sub = db.session.get(Subject, post.subject_id)
                if new_sub:
                    new_sub.post_count = new_sub.posts.count() + 1

        if _pricing_allowed() and form.is_paid.data:
            try:
                submitted_price = float(form.price.data) if form.price.data else 0.0
            except (ValueError, TypeError):
                submitted_price = 0.0

            if submitted_price <= 0:
                flash('Please enter a valid price greater than 0 for paid documents.', 'danger')
                return render_template('posts/edit.html', title='Edit Post', form=form,
                                       post=post, show_pricing=_pricing_allowed())

            final_is_paid = True
            final_price   = round(submitted_price, 2)
        else:
            if post.document:
                final_is_paid = post.document.is_paid
                final_price   = post.document.price
            else:
                final_is_paid = False
                final_price   = 0.0

        new_file = form.document.data
        if new_file and new_file.filename:
            if not allowed_file(new_file.filename, current_app.config['ALLOWED_DOCUMENT_EXTENSIONS']):
                flash('Invalid file type.', 'danger')
                return render_template('posts/edit.html', title='Edit Post', form=form,
                                       post=post, show_pricing=_pricing_allowed())

            if post.document:
                delete_document(post.document)
                db.session.delete(post.document)
                db.session.flush()

            document = upload_document(new_file, form)
            if document:
                document.is_paid = final_is_paid
                document.price   = final_price
                db.session.add(document)
                db.session.flush()
                post.has_document = True
                post.document_id  = document.id

        elif post.document:
            if _pricing_allowed():
                post.document.is_paid = final_is_paid
                post.document.price   = final_price

        db.session.commit()
        
        # Regenerate quiz if document was updated (new file uploaded)
        if new_file and new_file.filename and post.status == 'approved':
            try:
                from app.services.quiz_generator import regenerate_quiz
                regenerate_quiz(post.id)
            except Exception as e:
                current_app.logger.warning(f"Failed to regenerate quiz for post {post.id}: {e}")
        
        flash('Your post has been updated and is awaiting re-approval.', 'info')
        return redirect(url_for('posts.view', post_id=post.id))

    elif request.method == 'GET':
        form.title.data       = post.title
        form.description.data = post.description
        if post.subject_id:
            form.subject.data = post.subject_id
        if post.document:
            form.is_paid.data = post.document.is_paid
            form.price.data   = post.document.price if post.document.is_paid else None

    return render_template('posts/edit.html', title='Edit Post', form=form,
                           post=post, show_pricing=_pricing_allowed())


@bp.route('/<int:post_id>/delete', methods=['POST'])
@login_required
def delete(post_id):
    post = Post.query.get_or_404(post_id)

    if post.author != current_user:
        flash('You cannot delete this post.', 'danger')
        return redirect(url_for('posts.view', post_id=post.id))

    if post.document:
        delete_document(post.document)

    db.session.delete(post)
    db.session.commit()
    flash('Your post has been deleted.', 'success')
    return redirect(url_for('main.index'))


# ── Social actions ────────────────────────────────────────────────────────────

@bp.route('/<int:post_id>/like', methods=['POST'])
@login_required
def like(post_id):
    post = Post.query.get_or_404(post_id)
    existing_like = Like.query.filter_by(user_id=current_user.id, post_id=post.id).first()

    if existing_like:
        db.session.delete(existing_like)
        db.session.commit()
        # Update streak and XP only when liking (not unliking)
        current_user.update_streak()
        current_user.add_xp(2)
        liked = False
    else:
        db.session.add(Like(user_id=current_user.id, post_id=post.id))
        db.session.commit()
        # Update user's activity streak when they like a post
        current_user.update_streak()
        # Add XP for liking a post (+2 XP)
        current_user.add_xp(2)
        liked = True

    # Return JSON for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'liked': liked,
            'like_count': post.like_count()
        })
    
    flash('Post liked!' if liked else 'Post unliked.', 'success' if liked else 'info')
    return redirect(request.referrer or url_for('main.index'))


@bp.route('/<int:post_id>/comment', methods=['POST'])
@login_required
def comment(post_id):
    post = Post.query.get_or_404(post_id)
    form = CommentForm()

    if form.validate_on_submit():
        db.session.add(Comment(
            content=form.content.data,
            author=current_user,
            post=post,
        ))
        db.session.commit()
        # Update user's activity streak when they comment
        current_user.update_streak()
        # Add XP for commenting (+5 XP)
        current_user.add_xp(5)
        flash('Your comment has been posted!', 'success')

    return redirect(url_for('posts.view', post_id=post.id))


# ── Document routes ───────────────────────────────────────────────────────────

@bp.route('/document/<int:document_id>/download')
@login_required
def download_document(document_id):
    document = Document.query.get_or_404(document_id)

    if not document.has_access(current_user):
        flash('You need to purchase this document to download it.', 'warning')
        return redirect(url_for('payments.checkout', document_id=document.id))

    document.download_count += 1
    db.session.commit()

    body, kwargs = _stream_document(document, as_attachment=True)
    if body is None:
        flash('Could not fetch file from storage. Please try again.', 'danger')
        return redirect(url_for('posts.view', post_id=document.post.id))

    return Response(body, **kwargs)


@bp.route('/document/<int:document_id>/preview')
@login_required
def preview_document(document_id):
    document = Document.query.get_or_404(document_id)

    if not document.has_access(current_user):
        return jsonify({'error': 'access_denied'}), 403

    previewable = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'webp',
                   'docx', 'pptx', 'doc', 'ppt', 'xlsx', 'xls'}
    ext = document.file_type.lower()

    if ext not in previewable:
        return jsonify({'error': 'not_previewable'}), 400

    # Images — serve directly
    if ext in {'png', 'jpg', 'jpeg', 'gif', 'webp'}:
        if _is_local():
            # Serve local static URL directly
            return jsonify({'type': 'image', 'url': document.file_path}), 200
        return jsonify({'type': 'image', 'url': document.file_path}), 200

    # In local dev: use a signed proxy URL for Google Docs viewer
    # In prod: same approach via Cloudinary URL
    expires = int(time.time()) + 300
    secret  = current_app.config['SECRET_KEY'].encode()
    token   = _signed_proxy_token(document_id, expires, secret)

    proxy_url = url_for(
        'posts.proxy_document',
        document_id=document.id,
        token=token,
        expires=expires,
        _external=True,
    )

    if _is_local():
        # Google Docs viewer can't reach localhost — open directly in browser instead
        return jsonify({'type': 'local', 'url': document.file_path}), 200

    viewer_url = (
        'https://docs.google.com/viewer?embedded=true&url='
        + urllib.parse.quote(proxy_url, safe='')
    )
    return jsonify({'type': 'gdocs', 'viewer_url': viewer_url}), 200


@bp.route('/document/<int:document_id>/proxy')
def proxy_document(document_id):
    token   = request.args.get('token', '')
    expires = request.args.get('expires', '')

    try:
        exp_ts = int(expires)
    except (ValueError, TypeError):
        return 'Bad request', 400

    if int(time.time()) > exp_ts:
        return 'Preview link expired — please click Preview again', 410

    secret   = current_app.config['SECRET_KEY'].encode()
    expected = _signed_proxy_token(document_id, exp_ts, secret)
    if not hmac.compare_digest(expected, token):
        return 'Forbidden', 403

    document = Document.query.get_or_404(document_id)

    body, kwargs = _stream_document(document, as_attachment=False)
    if body is None:
        return 'Could not fetch file from storage', 502

    return Response(body, **kwargs)


# ── Quiz Routes ────────────────────────────────────────────────────────────────

@bp.route('/<int:post_id>/quiz/leaderboard')
@login_required
def quiz_leaderboard(post_id):
    """Display quiz leaderboard for a post."""
    from app.models import QuizLeaderboard
    
    post = Post.query.get_or_404(post_id)
    
    # Get top 10 leaderboard entries for this post
    leaderboard_entries = (
        QuizLeaderboard.query
        .filter_by(post_id=post.id)
        .order_by(QuizLeaderboard.score_pct.desc(), QuizLeaderboard.time_taken.asc(), QuizLeaderboard.created_at.asc())
        .limit(10)
        .all()
    )
    
    # Get user's own position if they've taken the quiz
    user_entry = QuizLeaderboard.query.filter_by(
        post_id=post.id,
        user_id=current_user.id
    ).first()
    
    # Get total participants
    total_participants = QuizLeaderboard.query.filter_by(post_id=post.id).count()
    
    return render_template(
        'posts/quiz_leaderboard.html',
        title=f'Leaderboard: {post.title}',
        post=post,
        leaderboard_entries=leaderboard_entries,
        user_entry=user_entry,
        total_participants=total_participants
    )


@bp.route('/<int:post_id>/quiz')
@login_required
def quiz(post_id):
    """Display and take a quiz for a post."""
    import json
    from app.models import QuizData
    
    post = Post.query.get_or_404(post_id)
    
    # Check if quiz exists
    quiz_data = QuizData.query.filter_by(post_id=post.id).first()
    if not quiz_data:
        flash('No quiz available for this post yet.', 'info')
        return redirect(url_for('posts.view', post_id=post.id))
    
    # Check access (subscription, purchase, premium access, or free trial)
    has_access = False
    
    # Admins and users with premium access can access everything
    if current_user.is_admin or getattr(current_user, 'can_access_all_content', False):
        has_access = True
    elif post.document and post.document.is_paid:
        # Check if user purchased
        from app.models import Purchase
        purchase = Purchase.query.filter_by(user_id=current_user.id, document_id=post.document.id).first()
        has_access = purchase is not None
        
        # Check subscription
        if not has_access and hasattr(current_user, 'subscription_tier'):
            if current_user.subscription_tier in ['pro', 'enterprise']:
                has_access = True
        
        # Check free quiz attempts
        if not has_access and current_user.has_free_quiz_attempts():
            has_access = True
    else:
        # Free document - everyone has access
        has_access = True
    
    if not has_access:
        flash('You need to purchase, subscribe, or use a free trial to access this quiz.', 'warning')
        return redirect(url_for('posts.view', post_id=post.id))
    
    # Load quiz data
    questions = json.loads(quiz_data.questions)
    meta = json.loads(quiz_data.meta) if quiz_data.meta else {}
    
    return render_template(
        'posts/quiz.html',
        title=f'Quiz: {post.title}',
        post=post,
        quiz_data=quiz_data,
        questions=questions,
        meta=meta,
        quiz_json=json.dumps({
            'questions': questions,
            'total_marks': quiz_data.total_marks,
            'xp_reward': quiz_data.xp_reward,
            'meta': meta
        })
    )


@bp.route('/<int:post_id>/quiz/submit', methods=['POST'])
@login_required
def quiz_submit(post_id):
    """Submit quiz answers and award XP."""
    # Simple rate limiting: track submissions per user in memory
    # This prevents spam/abuse of quiz submission
    import time
    from flask import session
    
    # Get or initialize rate limit tracking
    if not hasattr(quiz_submit, '_rate_limit_store'):
        quiz_submit._rate_limit_store = {}  # {user_id: [(timestamp, post_id), ...]}
    
    current_time = time.time()
    user_id = current_user.id
    
    # Clean old entries (older than 60 seconds)
    if user_id in quiz_submit._rate_limit_store:
        quiz_submit._rate_limit_store[user_id] = [
            (t, p) for t, p in quiz_submit._rate_limit_store[user_id]
            if current_time - t < 60
        ]
        # Check if too many submissions (more than 10 in 60 seconds)
        if len(quiz_submit._rate_limit_store[user_id]) >= 10:
            flash('Too many quiz submissions. Please wait a moment.', 'warning')
            return redirect(url_for('posts.view_post', post_id=post_id))
    else:
        quiz_submit._rate_limit_store[user_id] = []
    
    # Record this submission
    quiz_submit._rate_limit_store[user_id].append((current_time, post_id))
    
    post = Post.query.get_or_404(post_id)
    
    from app.models import QuizData, QuizAttempt, QuizLeaderboard, Purchase
    import json
    
    # Check if user is using a free quiz attempt
    is_free_attempt = False
    if post.document and post.document.is_paid:
        # Check if user purchased
        purchase = Purchase.query.filter_by(user_id=current_user.id, document_id=post.document.id).first()
        # Check subscription
        has_subscription = False
        if hasattr(current_user, 'subscription_tier'):
            has_subscription = current_user.subscription_tier in ['pro', 'enterprise']
        # Check if it's a free attempt
        if not purchase and not has_subscription and current_user.has_free_quiz_attempts():
            is_free_attempt = True
            current_user.use_free_quiz_attempt()
    
    quiz_data = QuizData.query.filter_by(post_id=post.id).first()
    if not quiz_data:
        return jsonify({'error': 'No quiz found'}), 404
    
    data = request.get_json()
    answers = data.get('answers', {})
    timed_out = data.get('timed_out', False)
    time_taken = data.get('time_taken', 0)
    
    # Calculate score
    questions = json.loads(quiz_data.questions)
    total_marks = quiz_data.total_marks
    earned_marks = 0
    
    for i, q in enumerate(questions):
        user_answer = answers.get(str(i), '')
        correct_answer = q.get('answer', '')
        marks = q.get('marks', 1)
        
        # Check answer (case-insensitive for MCQ/TF)
        q_type = q.get('type', 'mcq')
        if q_type in ['mcq', 'tf']:
            if user_answer.upper() == correct_answer.upper():
                earned_marks += marks
        else:
            # For open/short_answer questions - require correct answer to get marks
            # No partial credit to prevent gaming (typing random text for 50%)
            if user_answer.strip() and user_answer.strip().lower() == correct_answer.strip().lower():
                earned_marks += marks
    
    score_pct = (earned_marks / total_marks * 100) if total_marks > 0 else 0
    
    # Calculate XP earned (proportional to score)
    xp_earned = int(quiz_data.xp_reward * (score_pct / 100))
    
    # Save attempt
    attempt = QuizAttempt(
        post_id=post.id,
        user_id=current_user.id,
        answers=json.dumps(answers),
        score_pct=score_pct,
        earned_marks=earned_marks,
        xp_earned=xp_earned,
        timed_out=timed_out,
        time_taken=time_taken
    )
    db.session.add(attempt)
    
    # Update leaderboard - upsert entry
    leaderboard_entry = QuizLeaderboard.query.filter_by(
        post_id=post.id,
        user_id=current_user.id
    ).first()
    
    if leaderboard_entry:
        # Update existing entry if this score is better
        if score_pct > leaderboard_entry.score_pct or (
            score_pct == leaderboard_entry.score_pct and 
            time_taken < leaderboard_entry.time_taken
        ):
            leaderboard_entry.score_pct = score_pct
            leaderboard_entry.earned_marks = earned_marks
            leaderboard_entry.xp_earned = xp_earned
            leaderboard_entry.time_taken = time_taken
            leaderboard_entry.created_at = datetime.utcnow()
    else:
        # Create new entry
        leaderboard_entry = QuizLeaderboard(
            post_id=post.id,
            user_id=current_user.id,
            score_pct=score_pct,
            earned_marks=earned_marks,
            xp_earned=xp_earned,
            time_taken=time_taken
        )
        db.session.add(leaderboard_entry)
    
    # Award XP to user
    if xp_earned > 0:
        current_user.add_xp(xp_earned)
    
    db.session.commit()
    
    return jsonify({
        'score_pct': score_pct,
        'earned_marks': earned_marks,
        'total_marks': total_marks,
        'xp_earned': xp_earned
    })


def _generate_quiz_for_post(post):
    """Generate quiz questions from a post's document using AI."""
    import json
    from app.models import QuizData
    
    if not post.has_document or not post.document:
        return None
    
    document = post.document
    
    # Only generate quizzes for PDF files - other formats not supported for AI extraction
    if document.file_type != 'pdf':
        return None
    
    # Check if quiz already exists
    existing = QuizData.query.filter_by(post_id=post.id).first()
    if existing:
        return existing
    
    # For now, create a simple placeholder quiz
    # In production, this would call OpenAI/Gemini API to generate questions from PDF content
    
    questions = [
        {
            'type': 'mcq',
            'question': f'What is the main topic of "{post.title}"?',
            'options': ['Topic A', 'Topic B', 'Topic C', 'Topic D'],
            'answer': 'A',
            'marks': 2,
            'explanation': 'This is a sample question. Configure OPENAI_API_KEY or GEMINI_API_KEY for AI-generated quizzes.'
        },
        {
            'type': 'tf',
            'question': f'This document is related to {post.subject.name if post.subject else "education"}.',
            'answer': 'T',
            'marks': 1,
            'explanation': 'Sample true/false question.'
        }
    ]
    
    total_marks = sum(q.get('marks', 1) for q in questions)
    xp_reward = current_app.config.get('QUIZ_DEFAULT_XP_REWARD', 50)
    
    meta = json.dumps({
        'title': f'{post.title} Quiz',
        'time_minutes': current_app.config.get('QUIZ_DEFAULT_TIME_MINUTES', 30)
    })
    
    quiz = QuizData(
        post_id=post.id,
        questions=json.dumps(questions),
        total_marks=total_marks,
        xp_reward=xp_reward,
        meta=meta
    )
    
    db.session.add(quiz)
    db.session.commit()
    
    return quiz