import hashlib
import hmac
import json
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
    if current_app.config.get('ALLOW_ALL_PRICING'):
        return True
    return current_user.is_authenticated and current_user.is_admin


def _apply_pricing(document, form):
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
    if _is_local():
        return _upload_local(file, form, json_file)
    return _upload_cloudinary(file, form, json_file)


def _upload_local(file, form, json_file=None):
    try:
        file_ext          = file.filename.rsplit('.', 1)[1].lower()
        original_filename = secure_filename(file.filename)
        unique_name       = f"{uuid.uuid4().hex}.{file_ext}"
        upload_folder     = _local_upload_folder()
        save_path         = os.path.join(upload_folder, unique_name)

        file.save(save_path)
        file_size = os.path.getsize(save_path)
        file_url  = f"/static/uploads/documents/{unique_name}"

        document = Document(
            filename=unique_name,
            original_filename=original_filename,
            file_path=file_url,
            file_type=file_ext,
            file_size=file_size,
            is_paid=False,
            price=0.0,
        )

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
    if _is_local():
        _delete_local(document)
    else:
        _delete_cloudinary(document)


def _delete_local(document):
    try:
        upload_folder = _local_upload_folder()
        file_path     = os.path.join(upload_folder, document.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        if document.json_sidecar_path:
            json_filename = os.path.basename(document.json_sidecar_path)
            json_path = os.path.join(upload_folder, json_filename)
            if os.path.exists(json_path):
                os.remove(json_path)
    except Exception as e:
        current_app.logger.warning(f"Failed to delete local file '{document.filename}': {e}")


def _delete_cloudinary(document):
    try:
        import cloudinary.uploader
        resource_type = (
            'image' if document.file_type in {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            else 'raw'
        )
        cloudinary.uploader.destroy(document.filename, resource_type=resource_type)
        if document.json_sidecar_path:
            parsed_url = urllib.parse.urlparse(document.json_sidecar_path)
            path_parts = parsed_url.path.split('/')
            if len(path_parts) > 3:
                public_id = '/'.join(path_parts[5:])
                if public_id.endswith('.json'):
                    public_id = public_id[:-5]
                cloudinary.uploader.destroy(public_id, resource_type='raw')
    except Exception as e:
        current_app.logger.warning(f"Failed to delete Cloudinary file '{document.filename}': {e}")


# ── Storage: stream / serve ───────────────────────────────────────────────────

def _signed_proxy_token(document_id: int, expires: int, secret: bytes) -> str:
    return hmac.new(secret, f'{document_id}:{expires}'.encode(), hashlib.sha256).hexdigest()


def _stream_document(document, as_attachment: bool = False):
    if _is_local():
        return _stream_local(document, as_attachment)
    return _stream_cloudinary(document, as_attachment)


def _stream_local(document, as_attachment: bool = False):
    try:
        upload_folder = _local_upload_folder()
        file_path     = os.path.join(upload_folder, document.filename)
        if not os.path.exists(file_path):
            current_app.logger.error(f"Local file not found: {file_path}")
            return None, None
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
    try:
        upstream = req.get(document.file_path, stream=True, timeout=20)
        upstream.raise_for_status()
    except Exception as e:
        current_app.logger.error(
            f"Cloudinary fetch failed for document {document.id} ({document.file_path}): {e}"
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


# ── Quiz helpers ──────────────────────────────────────────────────────────────

def on_post_approved(post) -> None:
    """
    Call this from admin/routes.py after setting post.status = 'approved'.
    Re-reads the stored JSON sidecar, re-validates, and updates QuizData.
    Failure is logged but never blocks the approval.
    """
    if not post.document or not post.document.json_sidecar_path:
        return
    try:
        from app.services.quiz_service import quiz_from_sidecar
        quiz = quiz_from_sidecar(post)
        if quiz:
            current_app.logger.info(
                "Quiz (re-)attached to approved post %s: %d questions, %d marks.",
                post.id, len(json.loads(quiz.questions)), quiz.total_marks
            )
        else:
            current_app.logger.info(
                "Post %s approved — no valid quiz sidecar found.", post.id
            )
    except Exception as exc:
        current_app.logger.warning(
            "Quiz attachment failed for post %s during approval: %s", post.id, exc
        )


def _try_attach_quiz(post, json_bytes: bytes) -> None:
    """
    Validate json_bytes and attach a quiz to post.
    Flashes a user-facing message for both success and failure.
    Never raises.
    """
    try:
        from app.services.quiz_service import validate_and_attach_quiz
        quiz_data, error = validate_and_attach_quiz(post, json_bytes)
        if quiz_data:
            flash(
                f'Quiz attached successfully! '
                f'({quiz_data.total_marks} marks, '
                f'{len(json.loads(quiz_data.questions))} questions)',
                'success'
            )
        else:
            flash(
                f'Your post was submitted but the quiz JSON was rejected: {error} '
                f'The post will be published without a quiz.',
                'warning'
            )
    except Exception as exc:
        current_app.logger.exception(
            "Unexpected error attaching quiz to post %s.", post.id
        )
        flash(
            'Your post was submitted, but the quiz could not be processed '
            'due to an unexpected error.',
            'warning'
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

        json_bytes = None

        if form.document.data and form.document.data.filename:
            file = form.document.data
            if allowed_file(file.filename, current_app.config['ALLOWED_DOCUMENT_EXTENSIONS']):
                json_file = (
                    form.json_sidecar.data
                    if hasattr(form, 'json_sidecar')
                    and form.json_sidecar.data
                    and form.json_sidecar.data.filename
                    else None
                )
                if json_file:
                    json_bytes = json_file.read()
                    json_file.seek(0)   # rewind so upload_document can save it
                document = upload_document(file, form, json_file)
                if document:
                    db.session.add(document)
                    db.session.flush()
                    post.has_document = True
                    post.document_id  = document.id

        db.session.add(post)
        db.session.commit()

        if json_bytes and post.document:
            _try_attach_quiz(post, json_bytes)

        current_user.update_streak()
        current_user.add_xp(10)

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

        json_bytes = None
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

            json_file = (
                form.json_sidecar.data
                if hasattr(form, 'json_sidecar')
                and form.json_sidecar.data
                and form.json_sidecar.data.filename
                else None
            )
            if json_file:
                json_bytes = json_file.read()
                json_file.seek(0)

            document = upload_document(new_file, form, json_file)
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

        if json_bytes and post.document:
            _try_attach_quiz(post, json_bytes)

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
        current_user.update_streak()
        current_user.add_xp(2)
        liked = False
    else:
        db.session.add(Like(user_id=current_user.id, post_id=post.id))
        db.session.commit()
        current_user.update_streak()
        current_user.add_xp(2)
        liked = True

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
        current_user.update_streak()
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

    if ext in {'png', 'jpg', 'jpeg', 'gif', 'webp'}:
        return jsonify({'type': 'image', 'url': document.file_path}), 200

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


