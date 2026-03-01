from datetime import datetime
import json

from flask import session, request, jsonify, render_template, abort, redirect, url_for
from flask_login import current_user, login_required

from app import db
from app.models import QuizData, QuizAttempt, QuizLeaderboard, QuizAssessment, Post, format_time_taken
from app.quiz import bp as quiz_bp
# ── Session key helpers ───────────────────────────────────────────────────────

def _quiz_start_key(post_id: int) -> str:
    return f"quiz_start_{post_id}"


def _quiz_submitted_key(post_id: int) -> str:
    return f"quiz_submitted_{post_id}"


# ── Route: record quiz start (call this when the quiz overlay is dismissed) ───

@quiz_bp.route('/quiz/start/<int:post_id>', methods=['GET', 'POST'])
@quiz_bp.route('/<int:post_id>/quiz/start', methods=['GET', 'POST'])
@login_required
def quiz_start(post_id):
    """
    Called by the frontend immediately when the user clicks 'Start Quiz'.
    Stores the server-side start timestamp in the session.
    Clears any previous submission guard so a retake is allowed.
    Handles both URL patterns: /quiz/start/<post_id> and /<post_id>/quiz/start
    """
    # Allow retake: clear the previous submission flag
    session.pop(_quiz_submitted_key(post_id), None)
    session[_quiz_start_key(post_id)] = datetime.utcnow().isoformat()
    session.modified = True
    
    # Get the post first
    post = Post.query.get_or_404(post_id)
    
    # ── Check payment access for paid posts ─────────────────────────────────────
    # If the post has a document that is paid, user must have purchased it
    if post.document and post.document.is_paid:
        if not post.document.has_access(current_user):
            from flask import flash, redirect, url_for
            flash('You need to purchase this content to access the quiz.', 'warning')
            return redirect(url_for('payments.checkout', post_id=post.id))
    
    # If it's a GET request, render the quiz page directly
    if request.method == 'GET':
        quiz_data = QuizData.query.filter_by(post_id=post_id).first_or_404()
        
        # Parse quiz meta data if available
        try:
            if quiz_data.meta:
                meta = json.loads(quiz_data.meta)
            else:
                meta = {}
        except json.JSONDecodeError:
            meta = {}
            
        # Ensure time_minutes is available
        if 'time_minutes' not in meta:
            meta['time_minutes'] = 30
            
        # Prepare quiz JSON for frontend
        try:
            questions = json.loads(quiz_data.questions)
            # Wrap questions in object with required metadata
            quiz_json = {
                'questions': questions,
                'total_marks': quiz_data.total_marks,
                'xp_reward': quiz_data.xp_reward
            }
        except json.JSONDecodeError:
            quiz_json = {'questions': [], 'total_marks': 0, 'xp_reward': 0}
        
        # Debug: Check current_user
        print(f"Current user: {type(current_user)}")
        print(f"Is authenticated: {current_user.is_authenticated}")
        if current_user.is_authenticated:
            print(f"User: {current_user}")
            print(f"Free attempts left: {current_user.free_attempts_left}")
        
        return render_template(
            'quiz/quiz.html',
            user=current_user,
            title=f"Quiz: {post.title}",
            post=post,
            quiz_data=quiz_data,
            meta=meta,
            quiz_json=json.dumps(quiz_json)
        )
    
    # For POST requests, return JSON response
    return jsonify({'status': 'started'})


# ── Route: submit quiz ────────────────────────────────────────────────────────

@quiz_bp.route('/quiz/submit/<int:post_id>', methods=['POST'])
@login_required
def quiz_submit(post_id):
    """
    Grades the quiz, calculates time from server-stored start_time,
    persists QuizAttempt and (optionally) QuizLeaderboard, then returns
    the result JSON consumed by showResults() in quiz.html.
    """
    post      = Post.query.get_or_404(post_id)
    quiz_data = QuizData.query.filter_by(post_id=post_id).first_or_404()

    # ── Double-submission guard ───────────────────────────────────────────────
    submitted_key = _quiz_submitted_key(post_id)
    if session.get(submitted_key):
        return jsonify({'error': 'already_submitted'}), 409

    # ── Check payment access for paid posts ─────────────────────────────────────
    # If the post has a document that is paid, user must have purchased it
    if post.document and post.document.is_paid:
        if not post.document.has_access(current_user):
            return jsonify({
                'error': 'payment_required',
                'message': 'You need to purchase this content to access the quiz.'
            }), 403

    # ── Check free attempts ───────────────────────────────────────────────────
    if not current_user.use_free_attempt():
        return jsonify({
            'error': 'no_free_attempts',
            'message': 'You have no free attempts remaining. Subscribe to get unlimited attempts!'
        }), 403

    # ── Server-side timing ───────────────────────────────────────────────────
    start_key  = _quiz_start_key(post_id)
    start_iso  = session.get(start_key)

    if start_iso:
        try:
            start_dt   = datetime.fromisoformat(start_iso)
            time_taken = int((datetime.utcnow() - start_dt).total_seconds())
            time_taken = max(1, time_taken)          # minimum 1 second
        except (ValueError, TypeError):
            time_taken = 0
    else:
        # Fallback: start_time was never set (e.g. session expired).
        # We still accept the submission but record 0 seconds.
        time_taken = 0

    # Invalidate start time immediately to prevent re-use
    session.pop(start_key, None)

    # ── Parse request body ───────────────────────────────────────────────────
    data        = request.get_json(silent=True) or {}
    user_answers = data.get('answers', {})
    timed_out    = bool(data.get('timed_out', False))

    # ── Grade answers ────────────────────────────────────────────────────────
    # Quiz questions are stored as a flat list (from normalise_quiz_to_flat_questions)
    try:
        questions = json.loads(quiz_data.questions)
    except (json.JSONDecodeError, TypeError):
        questions = []

    total_questions = 0
    total_marks     = 0
    earned_marks    = 0.0
    scored          = []

    # Handle flat list of questions
    for flat_index, q in enumerate(questions):
        q_type = q.get('type', '')
        q_marks = q.get('marks', 0)
        total_marks += q_marks
        
        # Get user answer for this question
        user_ans = str(user_answers.get(str(flat_index), '')).strip()
        
        # Get correct answer
        correct_ans = str(q.get('answer') or '').strip()
        
        # Determine if auto-graded - any question with options and correct_answer can be auto-graded
        has_options = bool(q.get('options'))
        has_correct_answer = bool(correct_ans)
        is_auto = has_options and has_correct_answer
        
        if is_auto:
            # Auto-graded question
            user_ans_upper = user_ans.upper()
            correct_ans_upper = correct_ans.upper()
            is_correct = (user_ans_upper == correct_ans_upper and correct_ans_upper != '')
            
            if is_correct:
                earned_marks += q_marks
            scored.append({'is_correct': is_correct, 'marks_earned': q_marks if is_correct else 0})
        else:
            # Open answer question - no auto-grading
            is_correct = None
            scored.append({'is_correct': is_correct, 'marks_earned': 0})
        
        total_questions += 1

    # ── Percentage calculation ────────────────────────────────────────────────
    if total_questions > 0:
        percentage = round((earned_marks / total_marks) * 100, 2) if total_marks > 0 else 0.0
    else:
        percentage = 0.0

    percentage = min(100.0, max(0.0, percentage))

    # ── XP ───────────────────────────────────────────────────────────────────
    xp_reward  = quiz_data.xp_reward or 0
    xp_earned  = max(1, round(xp_reward * earned_marks / total_marks)) if total_marks > 0 else 0

    # ── Persist QuizAttempt ───────────────────────────────────────────────────
    attempt = QuizAttempt(
        post_id      = post_id,
        user_id      = current_user.id,
        answers      = json.dumps(user_answers),
        score_pct    = percentage,
        earned_marks = earned_marks,
        xp_earned    = xp_earned,
        timed_out    = timed_out,
        time_taken   = time_taken,
    )
    db.session.add(attempt)

    # ── Upsert QuizLeaderboard (best attempt) ─────────────────────────────────
    existing = QuizLeaderboard.query.filter_by(
        post_id=post_id,
        user_id=current_user.id
    ).first()

    if existing is None:
        lb_entry = QuizLeaderboard(
            post_id      = post_id,
            user_id      = current_user.id,
            score_pct    = percentage,
            earned_marks = earned_marks,
            xp_earned    = xp_earned,
            time_taken   = time_taken,
            is_public    = False,   # always starts False; user must opt-in
        )
        db.session.add(lb_entry)
    else:
        # Only update if this attempt is strictly better
        if percentage > existing.score_pct or (
            percentage == existing.score_pct and time_taken < existing.time_taken
        ):
            existing.score_pct    = percentage
            existing.earned_marks = earned_marks
            existing.xp_earned    = xp_earned
            existing.time_taken   = time_taken
            existing.is_public    = False   # reset publish flag on score update
        lb_entry = existing

    # XP to user
    current_user.xp_points += xp_earned
    current_user.update_streak()

    db.session.commit()

    # ── Mark as submitted to block double-submission ──────────────────────────
    session[submitted_key] = True
    session.modified = True

    # ── Build response ────────────────────────────────────────────────────────
    # can_publish is the backend-enforced flag sent to the frontend.
    # The frontend must only show the publish option when this is True.
    can_publish = percentage >= 60.0

    return jsonify({
        'score_pct':    percentage,
        'percentage':   percentage,
        'earned_marks': earned_marks,
        'total_marks':  total_marks,
        'xp_earned':    xp_earned,
        'time_taken':   time_taken,
        'time_display': format_time_taken(time_taken),
        'passed':       percentage >= 50.0,
        'can_publish':  can_publish,
        'scored':       scored,
    })


# ── Route: publish score to leaderboard ──────────────────────────────────────

@quiz_bp.route('/<int:post_id>/quiz/publish', methods=['POST'])
@login_required
def quiz_publish(post_id):
    """
    Allows a user to opt their score into the public leaderboard.
    Backend enforces the 60% minimum — frontend cannot bypass this.
    """
    lb_entry = QuizLeaderboard.query.filter_by(
        post_id=post_id,
        user_id=current_user.id
    ).first_or_404()

    # ── Backend enforcement of the 60% rule ──────────────────────────────────
    if lb_entry.score_pct < 60.0:
        return jsonify({
            'error':   'below_threshold',
            'message': 'Score must be at least 60% to publish to the leaderboard.',
        }), 403

    lb_entry.is_public = True
    db.session.commit()

    return jsonify({'status': 'published'})


# ── Route: unpublish score ────────────────────────────────────────────────────

@quiz_bp.route('/<int:post_id>/quiz/unpublish', methods=['POST'])
@login_required
def quiz_unpublish(post_id):
    lb_entry = QuizLeaderboard.query.filter_by(
        post_id=post_id,
        user_id=current_user.id
    ).first_or_404()

    lb_entry.is_public = False
    db.session.commit()

    return jsonify({'status': 'unpublished'})


# ── Route: leaderboard page ───────────────────────────────────────────────────

@quiz_bp.route('/quiz/leaderboard/<int:post_id>')
def quiz_leaderboard(post_id):
    post = Post.query.get_or_404(post_id)

    # Only show entries that are explicitly public (is_public=True)
    leaderboard_entries = (
        QuizLeaderboard.query
        .filter_by(post_id=post_id, is_public=True)
        .order_by(
            QuizLeaderboard.score_pct.desc(),
            QuizLeaderboard.time_taken.asc()
        )
        .all()
    )

    total_participants = QuizLeaderboard.query.filter_by(post_id=post_id).count()

    user_entry = None
    if current_user.is_authenticated:
        user_entry = QuizLeaderboard.query.filter_by(
            post_id=post_id,
            user_id=current_user.id
        ).first()

    return render_template(
        'quiz/quiz_leaderboard.html',
        post=post,
        leaderboard_entries=leaderboard_entries,
        total_participants=total_participants,
        user_entry=user_entry,
        format_time_taken=format_time_taken,
    )


@quiz_bp.route('/quiz/assess/<int:post_id>', methods=['GET', 'POST'])
@login_required
def quiz_assess(post_id):
    """
    Instructors view to assess open answer questions in quiz attempts
    """
    post = Post.query.get_or_404(post_id)
    
    # Check if user is authorized (admin or instructor)
    if not current_user.is_admin:
        abort(403)
        
    quiz_data = QuizData.query.filter_by(post_id=post_id).first_or_404()
    
    # Parse quiz questions - now stored as flat list
    try:
        questions = json.loads(quiz_data.questions)
    except (json.JSONDecodeError, TypeError):
        questions = []
        
    # Build questions list with indices for assessment
    assessment_questions = []
    for flat_index, q in enumerate(questions):
        q_type = q.get('type', '')
        assessment_questions.append({
            'index': flat_index,
            'text': q.get('question', ''),
            'marks': q.get('marks', 0),
            'qtype': q_type,
            'is_open': not (bool(q.get('options')) and bool(q.get('answer')))  # questions with options and correct_answer are auto-graded
        })
                
    # Get all attempts for this quiz
    attempts = QuizAttempt.query.filter_by(post_id=post_id).all()
    
    if request.method == 'POST':
        attempt_id = request.form.get('attempt_id', type=int)
        question_index = request.form.get('question_index', type=int)
        score = request.form.get('score', type=float)
        feedback = request.form.get('feedback', '')
        
        if attempt_id and question_index is not None:
            # Find or create assessment
            assessment = QuizAssessment.query.filter_by(
                attempt_id=attempt_id,
                question_index=question_index
            ).first()
            
            if not assessment:
                assessment = QuizAssessment(
                    attempt_id=attempt_id,
                    question_index=question_index
                )
                
            assessment.score = score
            assessment.feedback = feedback
            assessment.assessed_by = current_user.id
            assessment.assessed_at = datetime.utcnow()
            
            db.session.add(assessment)
            db.session.commit()
            
            # Recalculate the attempt's total score
            attempt = QuizAttempt.query.get(attempt_id)
            if attempt:
                recalculate_attempt_score(attempt, questions)
                
        return redirect(url_for('quiz.quiz_assess', post_id=post_id))
        
    # Get assessments for all attempts
    assessments = {}
    for attempt in attempts:
        attempt_assessments = QuizAssessment.query.filter_by(attempt_id=attempt.id).all()
        assessments[attempt.id] = {assess.question_index: assess for assess in attempt_assessments}
        
    return render_template(
        'quiz/quiz_assess.html',
        post=post,
        quiz_data=quiz_data,
        questions=assessment_questions,
        attempts=attempts,
        assessments=assessments,
        format_time_taken=format_time_taken
    )


def recalculate_attempt_score(attempt, questions):
    """
    Recalculate quiz attempt score based on assessments and auto-graded questions
    """
    try:
        user_answers = json.loads(attempt.answers)
    except (json.JSONDecodeError, TypeError):
        user_answers = {}
        
    total_marks = 0
    earned_marks = 0.0
    
    # Parse quiz data to get correct answers - now stored as flat list
    quiz_data = QuizData.query.filter_by(post_id=attempt.post_id).first()
    try:
        quiz_questions = json.loads(quiz_data.questions)
    except (json.JSONDecodeError, TypeError):
        quiz_questions = []
        
    # Create a map of question index to correct answer from flat list
    correct_answers = {}
    for flat_index, q in enumerate(quiz_questions):
        q_type = q.get('type', '')
        has_options = bool(q.get('options'))
        has_correct_answer = bool(q.get('answer'))
        is_auto = has_options and has_correct_answer
        correct_answers[flat_index] = {
            'answer': str(q.get('answer') or '').strip().upper(),
            'marks': q.get('marks', 0),
            'is_auto': is_auto
        }
                
    for q in questions:
        total_marks += q['marks']
        
        # Check if question has an assessment
        assessment = QuizAssessment.query.filter_by(
            attempt_id=attempt.id,
            question_index=q['index']
        ).first()
        
        if assessment:
            earned_marks += assessment.score
        elif q['is_open']:
            # Open questions with no assessment get 0
            earned_marks += 0.0
        else:
            # Auto-graded questions - recalculate score
            if q['index'] in correct_answers:
                correct_data = correct_answers[q['index']]
                user_ans = str(user_answers.get(str(q['index']), '')).strip().upper()
                if user_ans == correct_data['answer'] and correct_data['answer'] != '':
                    earned_marks += correct_data['marks']
            
    # Calculate percentage
    score_pct = (earned_marks / total_marks) * 100 if total_marks > 0 else 0.0
    score_pct = min(100.0, max(0.0, score_pct))
    
    # Calculate XP
    xp_reward = quiz_data.xp_reward or 0
    xp_earned = max(1, round(xp_reward * earned_marks / total_marks)) if total_marks > 0 else 0
    
    # Update attempt
    attempt.earned_marks = earned_marks
    attempt.score_pct = score_pct
    attempt.xp_earned = xp_earned
    db.session.commit()
    
    # Update leaderboard
    leaderboard_entry = QuizLeaderboard.query.filter_by(
        post_id=attempt.post_id,
        user_id=attempt.user_id
    ).first()
    
    if leaderboard_entry:
        leaderboard_entry.score_pct = score_pct
        leaderboard_entry.earned_marks = earned_marks
        leaderboard_entry.xp_earned = xp_earned
        db.session.commit()