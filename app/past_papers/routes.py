"""
past_papers/routes.py — Student past paper upload feature.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from flask import (Blueprint, current_app, flash,
                   redirect, render_template, request, url_for)
from flask_login import current_user, login_required

from app import db
from app.models import StudentPastPaper, Subject, Programme, XpTransaction

bp = Blueprint('past_papers', __name__, url_prefix='/past-papers')

ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}
MAX_FILE_SIZE      = 20 * 1024 * 1024
XP_REWARD          = 50


def _allowed(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def _award_xp(user, amount: int, reason: str) -> None:
    user.add_xp(amount)
    db.session.add(XpTransaction(user_id=user.id, amount=amount, reason=reason))


@bp.route('/')
@login_required
def index():
    programmes = Programme.query.order_by(Programme.name).all()
    my_papers  = (StudentPastPaper.query
                  .filter_by(user_id=current_user.id)
                  .order_by(StudentPastPaper.uploaded_at.desc())
                  .limit(20).all())
    return render_template('past_papers/index.html',
                           programmes=programmes, my_papers=my_papers, xp_reward=XP_REWARD)


@bp.route('/upload', methods=['POST'])
@login_required
def upload():
    subject_slug = request.form.get('subject_slug', '').strip()
    year         = request.form.get('year', '').strip()
    semester     = request.form.get('semester', '').strip()
    description  = request.form.get('description', '').strip()
    file         = request.files.get('file')
    redirect_to  = request.form.get('redirect_to', 'past_papers.index')

    if not subject_slug:
        flash('Please select a subject.', 'danger')
        return redirect(url_for(redirect_to))

    subject = Subject.query.filter_by(slug=subject_slug).first()
    if not subject:
        flash('Subject not found.', 'danger')
        return redirect(url_for(redirect_to))

    if not file or not file.filename:
        flash('No file selected.', 'danger')
        return redirect(url_for(redirect_to))

    if not _allowed(file.filename):
        flash('Only PDF and image files (JPG, PNG) are allowed.', 'danger')
        return redirect(url_for(redirect_to))

    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_FILE_SIZE:
        flash('File too large — maximum size is 20 MB.', 'danger')
        return redirect(url_for(redirect_to))

    suffix = Path(file.filename).suffix.lower()
    ftype  = 'pdf' if suffix == '.pdf' else 'image'

    # ── Upload to Cloudinary ──────────────────────────────────────────────────
    try:
        import cloudinary.uploader
        result = cloudinary.uploader.upload(
            file,
            folder='edushare/past_papers',
            resource_type='auto',
            use_filename=False,
            unique_filename=True,
        )
        file_path = result['secure_url']
    except Exception as exc:
        current_app.logger.error("Past paper Cloudinary upload failed: %s", exc)
        flash('File upload failed — please try again.', 'danger')
        return redirect(url_for(redirect_to))

    paper = StudentPastPaper(
        user_id      = current_user.id,
        subject_id   = subject.id,
        subject_slug = subject_slug,
        filename     = file.filename,
        file_path    = file_path,
        file_type    = ftype,
        file_size    = size,
        year         = year or None,
        semester     = semester or None,
        description  = description or None,
        status       = 'pending',
    )
    db.session.add(paper)
    _award_xp(current_user, XP_REWARD, f'Uploaded past paper for {subject.name}')
    paper.xp_awarded = True
    db.session.commit()

    flash(f'Past paper uploaded successfully! You earned {XP_REWARD} XP 🎉', 'success')
    return (redirect(url_for(redirect_to, slug=subject_slug))
            if redirect_to != 'past_papers.index'
            else redirect(url_for('past_papers.index')))