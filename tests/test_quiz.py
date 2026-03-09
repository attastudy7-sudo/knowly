"""
tests/test_quiz.py
==================
Integration tests for the quiz blueprint (app/quiz/quiz_routes.py).

Covers:
  - quiz_start  : GET renders quiz, POST sets session, no quiz 404-guards,
                  paid-content guard, login required
  - quiz_submit : correct/incorrect grading, score & XP calculation,
                  free-attempt deduction, double-submission guard,
                  no-attempts-left guard, paid-content guard, no-quiz guard,
                  timed_out flag recorded, leaderboard upsert (best-only)
  - quiz_publish: publishes >=60%, rejects <60%, upsert logic
  - quiz_unpublish: marks entry private
  - quiz_leaderboard: public page renders, only shows is_public=True entries
  - my_quiz_results: returns latest attempt JSON, 404 if no attempt

Run from the edushare/ root:
    pytest tests/test_quiz.py -v
"""

import json
from unittest.mock import patch

import pytest

from app import db
from app.models import (
    Post, QuizAttempt, QuizData, QuizLeaderboard, User
)


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _make_post_with_quiz(app, make_post, make_quiz, user,
                         total_marks=4, xp_reward=10):
    """Create a Post + QuizData in the same app context; return (post_id, quiz_id)."""
    with app.app_context():
        post = make_post(user_id=user.id)
        quiz = make_quiz(post_id=post.id, total_marks=total_marks,
                         xp_reward=xp_reward)
        post_id = post.id
        quiz_id = quiz.id
    return post_id, quiz_id


def _submit(client, post_id, answers=None, timed_out=False):
    """POST to quiz_submit with JSON answers."""
    payload = {'answers': answers or {}, 'timed_out': timed_out}
    return client.post(
        f'/quiz/submit/{post_id}',
        json=payload,
        content_type='application/json',
    )


def _start(client, post_id, method='POST'):
    if method == 'GET':
        return client.get(f'/quiz/start/{post_id}')
    return client.post(f'/quiz/start/{post_id}')


# ══════════════════════════════════════════════════════════════════════════════
# quiz_start
# ══════════════════════════════════════════════════════════════════════════════

class TestQuizStart:

    def test_get_renders_quiz_page(self, client, db_session, make_user,
                                   make_post, make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)
        response = _start(logged_in, post_id, method='GET')
        assert response.status_code == 200

    def test_post_returns_started_json(self, client, db_session, make_user,
                                       make_post, make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)
        response = _start(logged_in, post_id, method='POST')
        assert response.status_code == 200
        assert response.get_json()['status'] == 'started'

    def test_post_sets_start_time_in_session(self, client, db_session, make_user,
                                              make_post, make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)
        _start(logged_in, post_id)
        with logged_in.session_transaction() as sess:
            assert f'quiz_start_{post_id}' in sess

    def test_no_quiz_redirects(self, client, db_session, make_user,
                               make_post, auth_client, app):
        user = make_user()
        with app.app_context():
            post = make_post(user_id=user.id)
            post_id = post.id
        logged_in = auth_client(user)
        response = _start(logged_in, post_id, method='GET')
        # Should redirect away since no quiz exists
        assert response.status_code == 302

    def test_requires_login(self, client, db_session, make_user,
                            make_post, make_quiz, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        response = _start(client, post_id)
        assert response.status_code == 302
        assert '/auth/login' in response.headers['Location']

    def test_nonexistent_post_returns_404(self, client, db_session, make_user,
                                          auth_client, app):
        user = make_user()
        logged_in = auth_client(user)
        response = _start(logged_in, 99999)
        assert response.status_code == 404

    def test_clears_previous_submitted_flag(self, client, db_session, make_user,
                                             make_post, make_quiz, auth_client, app):
        """Starting again should clear the double-submission guard."""
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)

        # Manually set the submitted flag
        with logged_in.session_transaction() as sess:
            sess[f'quiz_submitted_{post_id}'] = True

        _start(logged_in, post_id)  # start again

        with logged_in.session_transaction() as sess:
            assert not sess.get(f'quiz_submitted_{post_id}')


# ══════════════════════════════════════════════════════════════════════════════
# quiz_submit — grading
# ══════════════════════════════════════════════════════════════════════════════

class TestQuizSubmitGrading:
    """Tests focused on correct score calculation."""

    def _start_and_submit(self, logged_in, post_id, answers):
        _start(logged_in, post_id)
        return _submit(logged_in, post_id, answers)

    def test_correct_answer_gives_full_marks(self, client, db_session, make_user,
                                              make_post, make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user,
                                          total_marks=2)
        logged_in = auth_client(user)
        # conftest make_quiz creates 1 MCQ: correct answer is 'B'
        response = self._start_and_submit(logged_in, post_id, {'0': 'B'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['earned_marks'] == 2
        assert data['score_pct'] == 100.0

    def test_wrong_answer_gives_zero_marks(self, client, db_session, make_user,
                                            make_post, make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user,
                                          total_marks=2)
        logged_in = auth_client(user)
        response = self._start_and_submit(logged_in, post_id, {'0': 'A'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['earned_marks'] == 0
        assert data['score_pct'] == 0.0

    def test_case_insensitive_answer_matching(self, client, db_session, make_user,
                                               make_post, make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)
        # lowercase 'b' should match 'B'
        response = self._start_and_submit(logged_in, post_id, {'0': 'b'})
        data = response.get_json()
        assert data['score_pct'] == 100.0  # lowercase 'b' matched 'B' — full marks

    def test_score_pct_capped_at_100(self, client, db_session, make_user,
                                      make_post, make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)
        response = self._start_and_submit(logged_in, post_id, {'0': 'B'})
        data = response.get_json()
        assert data['score_pct'] <= 100.0

    def test_xp_earned_positive_on_correct(self, client, db_session, make_user,
                                            make_post, make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user,
                                          xp_reward=10)
        logged_in = auth_client(user)
        response = self._start_and_submit(logged_in, post_id, {'0': 'B'})
        data = response.get_json()
        assert data['xp_earned'] > 0

    def test_passed_flag_true_above_50_pct(self, client, db_session, make_user,
                                            make_post, make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)
        response = self._start_and_submit(logged_in, post_id, {'0': 'B'})
        assert response.get_json()['passed'] is True

    def test_passed_flag_false_below_50_pct(self, client, db_session, make_user,
                                             make_post, make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)
        response = self._start_and_submit(logged_in, post_id, {'0': 'A'})
        assert response.get_json()['passed'] is False

    def test_timed_out_flag_recorded(self, client, db_session, make_user,
                                      make_post, make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)
        _start(logged_in, post_id)
        response = _submit(logged_in, post_id, timed_out=True)
        assert response.status_code == 200
        with app.app_context():
            attempt = QuizAttempt.query.filter_by(post_id=post_id).first()
            assert attempt.timed_out is True


# ══════════════════════════════════════════════════════════════════════════════
# quiz_submit — persistence & side-effects
# ══════════════════════════════════════════════════════════════════════════════

class TestQuizSubmitPersistence:

    def test_attempt_is_persisted(self, client, db_session, make_user,
                                   make_post, make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)
        _start(logged_in, post_id)
        _submit(logged_in, post_id, {'0': 'B'})
        with app.app_context():
            attempt = QuizAttempt.query.filter_by(post_id=post_id,
                                                   user_id=user.id).first()
            assert attempt is not None

    def test_xp_added_to_user(self, client, db_session, make_user,
                               make_post, make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user,
                                          xp_reward=10)
        logged_in = auth_client(user)
        _start(logged_in, post_id)
        response = _submit(logged_in, post_id, {'0': 'B'})
        xp_earned = response.get_json()['xp_earned']
        with app.app_context():
            u = db.session.get(User, user.id)
            assert u.xp_points >= xp_earned

    def test_free_attempt_decremented_for_non_premium(self, client, db_session,
                                                        make_user, make_post,
                                                        make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)
        with app.app_context():
            initial = db.session.get(User, user.id).free_quiz_attempts

        _start(logged_in, post_id)
        _submit(logged_in, post_id, {'0': 'A'})

        with app.app_context():
            after = db.session.get(User, user.id).free_quiz_attempts
        assert after == initial - 1

    def test_leaderboard_entry_created_on_first_submit(self, client, db_session,
                                                         make_user, make_post,
                                                         make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)
        _start(logged_in, post_id)
        _submit(logged_in, post_id, {'0': 'B'})
        with app.app_context():
            entry = QuizLeaderboard.query.filter_by(post_id=post_id,
                                                     user_id=user.id).first()
            assert entry is not None

    def test_leaderboard_updated_only_on_improvement(self, client, db_session,
                                                       make_user, make_post,
                                                       make_quiz, auth_client, app):
        """Second attempt with lower score should NOT update the leaderboard."""
        user = make_user(free_quiz_attempts=10)
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)

        # First attempt: correct (100%)
        _start(logged_in, post_id)
        _submit(logged_in, post_id, {'0': 'B'})

        # Start again (clears submitted guard)
        _start(logged_in, post_id)
        # Second attempt: wrong (0%)
        _submit(logged_in, post_id, {'0': 'A'})

        with app.app_context():
            entry = QuizLeaderboard.query.filter_by(post_id=post_id,
                                                     user_id=user.id).first()
            assert entry.score_pct == 100.0


# ══════════════════════════════════════════════════════════════════════════════
# quiz_submit — guards
# ══════════════════════════════════════════════════════════════════════════════

class TestQuizSubmitGuards:

    def test_double_submission_rejected_409(self, client, db_session, make_user,
                                             make_post, make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)
        _start(logged_in, post_id)
        _submit(logged_in, post_id, {'0': 'B'})          # first
        response = _submit(logged_in, post_id, {'0': 'B'})  # second
        assert response.status_code == 409
        assert response.get_json()['error'] == 'already_submitted'

    def test_no_free_attempts_rejected_403(self, client, db_session, make_user,
                                            make_post, make_quiz, auth_client, app):
        user = make_user(free_quiz_attempts=0)
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)
        _start(logged_in, post_id)
        response = _submit(logged_in, post_id, {'0': 'B'})
        assert response.status_code == 403
        assert response.get_json()['error'] == 'no_free_attempts'

    def test_admin_bypasses_free_attempt_limit(self, client, db_session, make_user,
                                                make_post, make_quiz, auth_client, app):
        user = make_user(is_admin=True, free_quiz_attempts=0)
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)
        _start(logged_in, post_id)
        response = _submit(logged_in, post_id, {'0': 'B'})
        assert response.status_code == 200

    def test_no_quiz_returns_404(self, client, db_session, make_user,
                                  make_post, auth_client, app):
        user = make_user()
        with app.app_context():
            post = make_post(user_id=user.id)
            post_id = post.id
        logged_in = auth_client(user)
        response = _submit(logged_in, post_id, {'0': 'B'})
        assert response.status_code == 404
        assert response.get_json()['error'] == 'no_quiz'

    def test_submit_requires_login(self, client, db_session, make_user,
                                    make_post, make_quiz, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        response = _submit(client, post_id, {'0': 'B'})
        assert response.status_code == 302


# ══════════════════════════════════════════════════════════════════════════════
# quiz_publish / quiz_unpublish
# ══════════════════════════════════════════════════════════════════════════════

class TestQuizPublish:

    def _submit_and_get_entry(self, logged_in, post_id, answer, app, user_id):
        """Start, submit, return the leaderboard entry."""
        _start(logged_in, post_id)
        _submit(logged_in, post_id, {'0': answer})
        with app.app_context():
            return QuizLeaderboard.query.filter_by(post_id=post_id,
                                                    user_id=user_id).first()

    def test_publish_above_60_succeeds(self, client, db_session, make_user,
                                        make_post, make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)
        _start(logged_in, post_id)
        _submit(logged_in, post_id, {'0': 'B'})  # 100%

        response = logged_in.post(f'/{post_id}/quiz/publish')
        assert response.status_code == 200
        assert response.get_json()['status'] == 'published'

        with app.app_context():
            entry = QuizLeaderboard.query.filter_by(post_id=post_id,
                                                     user_id=user.id).first()
            assert entry.is_public is True

    def test_publish_below_60_rejected(self, client, db_session, make_user,
                                        make_post, make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)
        _start(logged_in, post_id)
        _submit(logged_in, post_id, {'0': 'A'})  # 0%

        response = logged_in.post(f'/{post_id}/quiz/publish')
        assert response.status_code == 403
        assert response.get_json()['error'] == 'below_threshold'

    def test_unpublish_sets_is_public_false(self, client, db_session, make_user,
                                             make_post, make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)
        _start(logged_in, post_id)
        _submit(logged_in, post_id, {'0': 'B'})  # 100%
        logged_in.post(f'/{post_id}/quiz/publish')

        response = logged_in.post(f'/{post_id}/quiz/unpublish')
        assert response.status_code == 200
        assert response.get_json()['status'] == 'unpublished'

        with app.app_context():
            entry = QuizLeaderboard.query.filter_by(post_id=post_id,
                                                     user_id=user.id).first()
            assert entry.is_public is False

    def test_publish_requires_login(self, client, db_session, make_user,
                                     make_post, make_quiz, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        response = client.post(f'/{post_id}/quiz/publish')
        assert response.status_code == 302


# ══════════════════════════════════════════════════════════════════════════════
# quiz_leaderboard
# ══════════════════════════════════════════════════════════════════════════════

class TestQuizLeaderboard:

    def test_leaderboard_page_renders(self, client, db_session, make_user,
                                       make_post, make_quiz, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        response = client.get(f'/quiz/leaderboard/{post_id}')
        assert response.status_code == 200

    def test_only_public_entries_shown(self, client, db_session, make_user,
                                        make_post, make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)

        # Submit but do NOT publish
        _start(logged_in, post_id)
        _submit(logged_in, post_id, {'0': 'B'})

        response = client.get(f'/quiz/leaderboard/{post_id}')
        assert response.status_code == 200
        # Entry should not appear in leaderboard content (is_public=False by default)
        with app.app_context():
            public_count = QuizLeaderboard.query.filter_by(
                post_id=post_id, is_public=True).count()
            assert public_count == 0

    def test_published_entry_appears(self, client, db_session, make_user,
                                      make_post, make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)
        _start(logged_in, post_id)
        _submit(logged_in, post_id, {'0': 'B'})
        logged_in.post(f'/{post_id}/quiz/publish')

        with app.app_context():
            public_count = QuizLeaderboard.query.filter_by(
                post_id=post_id, is_public=True).count()
            assert public_count == 1


# ══════════════════════════════════════════════════════════════════════════════
# my_quiz_results
# ══════════════════════════════════════════════════════════════════════════════

class TestMyQuizResults:

    def test_returns_latest_attempt_json(self, client, db_session, make_user,
                                          make_post, make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)
        _start(logged_in, post_id)
        _submit(logged_in, post_id, {'0': 'B'})

        response = logged_in.get(f'/quiz/my-results/{post_id}')
        assert response.status_code == 200
        data = response.get_json()
        assert 'score_pct' in data
        assert 'earned_marks' in data

    def test_no_attempt_returns_404(self, client, db_session, make_user,
                                     make_post, make_quiz, auth_client, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        logged_in = auth_client(user)
        response = logged_in.get(f'/quiz/my-results/{post_id}')
        assert response.status_code == 404

    def test_requires_login(self, client, db_session, make_user,
                            make_post, make_quiz, app):
        user = make_user()
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        response = client.get(f'/quiz/my-results/{post_id}')
        assert response.status_code == 302

# ══════════════════════════════════════════════════════════════════════════════
# BUG-01  _compute_section_marks — PS marks always 0
# ══════════════════════════════════════════════════════════════════════════════

class TestComputeSectionMarks:
    """Unit tests for _compute_section_marks in quiz_service.py."""

    def test_ps_marks_sum_subpart_marks(self):
        from app.services.quiz_service import _compute_section_marks
        questions = [
            {"subparts": [{"marks": 2}, {"marks": 3}]},
            {"subparts": [{"marks": 1}]},
        ]
        assert _compute_section_marks("problem_solving", questions) == 6

    def test_ps_marks_ignores_non_numeric_subpart_marks(self):
        from app.services.quiz_service import _compute_section_marks
        questions = [
            {"subparts": [{"marks": 2}, {"marks": "bad"}, {"marks": 1}]},
        ]
        assert _compute_section_marks("problem_solving", questions) == 3

    def test_ps_marks_empty_subparts_returns_zero(self):
        from app.services.quiz_service import _compute_section_marks
        assert _compute_section_marks("problem_solving", [{"subparts": []}]) == 0

    def test_non_ps_marks_sum_question_marks(self):
        from app.services.quiz_service import _compute_section_marks
        questions = [{"marks": 2}, {"marks": 3}, {"marks": 1}]
        assert _compute_section_marks("mcq", questions) == 6

    def test_non_ps_ignores_non_numeric_marks(self):
        from app.services.quiz_service import _compute_section_marks
        questions = [{"marks": 2}, {"marks": "bad"}, {"marks": 1}]
        assert _compute_section_marks("mcq", questions) == 3


# ══════════════════════════════════════════════════════════════════════════════
# BUG-02  free_attempts_left — None crash, @property commit, deduction bypass
# ══════════════════════════════════════════════════════════════════════════════

class TestFreeAttemptsLeft:
    """Unit tests for User.free_attempts_left and use_free_attempt()."""

    def test_new_user_no_reset_date_does_not_crash(self, db_session, make_user, app):
        """free_attempts_left must not raise TypeError when reset_date is NULL."""
        user = make_user(free_quiz_attempts=3)
        with app.app_context():
            u = db.session.get(User, user.id)
            u.free_quiz_attempts_reset_date = None
            db.session.commit()
            assert u.free_attempts_left == 3

    def test_new_user_reset_date_initialised_on_first_access(self, db_session, make_user, app):
        """Accessing free_attempts_left on a new user sets a reset date 7 days out."""
        from datetime import date, timedelta
        user = make_user()
        with app.app_context():
            u = db.session.get(User, user.id)
            u.free_quiz_attempts_reset_date = None
            db.session.commit()
            _ = u.free_attempts_left
            assert u.free_quiz_attempts_reset_date == date.today() + timedelta(days=7)

    def test_expired_reset_date_resets_attempts_to_3(self, db_session, make_user, app):
        """When reset_date is in the past, attempts reset to 3."""
        from datetime import date, timedelta
        user = make_user(free_quiz_attempts=0)
        with app.app_context():
            u = db.session.get(User, user.id)
            u.free_quiz_attempts_reset_date = date.today() - timedelta(days=1)
            db.session.commit()
            assert u.free_attempts_left == 3

    def test_property_does_not_commit(self, db_session, make_user, app):
        """free_attempts_left must not call db.session.commit()."""
        from unittest.mock import patch
        user = make_user(free_quiz_attempts=3)
        with app.app_context():
            u = db.session.get(User, user.id)
            u.free_quiz_attempts_reset_date = None
            db.session.commit()
            with patch.object(db.session, 'commit') as mock_commit:
                _ = u.free_attempts_left
                mock_commit.assert_not_called()

    def test_use_free_attempt_commits_atomically(self, db_session, make_user, app):
        """use_free_attempt() decrements and commits in one call."""
        from datetime import date, timedelta
        user = make_user(free_quiz_attempts=3)
        with app.app_context():
            u = db.session.get(User, user.id)
            u.free_quiz_attempts_reset_date = date.today() + timedelta(days=7)
            db.session.commit()
            result = u.use_free_attempt()
            assert result is True
            db.session.refresh(u)
            assert u.free_quiz_attempts == 2

    def test_use_free_attempt_returns_false_when_zero(self, db_session, make_user, app):
        from datetime import date, timedelta
        user = make_user(free_quiz_attempts=0)
        with app.app_context():
            u = db.session.get(User, user.id)
            u.free_quiz_attempts_reset_date = date.today() + timedelta(days=7)
            db.session.commit()
            assert u.use_free_attempt() is False

    def test_use_free_attempt_premium_always_true(self, db_session, make_user, app):
        user = make_user(free_quiz_attempts=0, subscription_tier='premium')
        with app.app_context():
            u = db.session.get(User, user.id)
            assert u.use_free_attempt() is True

    def test_quiz_submit_uses_use_free_attempt_not_direct_decrement(
            self, client, db_session, make_user, make_post, make_quiz, auth_client, app):
        """Submitting a quiz calls use_free_attempt(), not a raw column decrement."""
        from datetime import date, timedelta
        user = make_user(free_quiz_attempts=3)
        post_id, _ = _make_post_with_quiz(app, make_post, make_quiz, user)
        with app.app_context():
            u = db.session.get(User, user.id)
            u.free_quiz_attempts_reset_date = date.today() + timedelta(days=7)
            db.session.commit()
        logged_in = auth_client(user)
        _start(logged_in, post_id)
        _submit(logged_in, post_id, {'0': 'B'})
        with app.app_context():
            after = db.session.get(User, user.id).free_quiz_attempts
        assert after == 2


# ══════════════════════════════════════════════════════════════════════════════
# BUG-03  grade_quiz — PS subparts scored via flat structure
# ══════════════════════════════════════════════════════════════════════════════

class TestGradeQuiz:
    """Unit tests for grade_quiz() in quiz_service.py."""

    def test_mcq_correct_answer_earns_marks(self):
        from app.services.quiz_service import grade_quiz
        questions = [{"type": "mcq", "answer": "B", "marks": 2,
                      "options": [{"letter": "A"}, {"letter": "B"}]}]
        earned, total = grade_quiz(questions, {"0": "B"})
        assert earned == 2
        assert total == 2

    def test_mcq_wrong_answer_earns_zero(self):
        from app.services.quiz_service import grade_quiz
        questions = [{"type": "mcq", "answer": "B", "marks": 2,
                      "options": [{"letter": "A"}, {"letter": "B"}]}]
        earned, total = grade_quiz(questions, {"0": "A"})
        assert earned == 0
        assert total == 2

    def test_ps_flat_subpart_earns_marks(self):
        """PS subparts are flat entries — grade_quiz must score them like MCQ."""
        from app.services.quiz_service import grade_quiz
        questions = [
            {"type": "ps", "answer": "A", "marks": 3,
             "options": [{"letter": "A"}, {"letter": "B"}]},
            {"type": "ps", "answer": "B", "marks": 2,
             "options": [{"letter": "A"}, {"letter": "B"}]},
        ]
        earned, total = grade_quiz(questions, {"0": "A", "1": "B"})
        assert earned == 5
        assert total == 5

    def test_ps_flat_wrong_answer_earns_zero(self):
        from app.services.quiz_service import grade_quiz
        questions = [
            {"type": "ps", "answer": "A", "marks": 3,
             "options": [{"letter": "A"}, {"letter": "B"}]},
        ]
        earned, total = grade_quiz(questions, {"0": "B"})
        assert earned == 0
        assert total == 3

    def test_mixed_types_total_marks_correct(self):
        from app.services.quiz_service import grade_quiz
        questions = [
            {"type": "mcq", "answer": "A", "marks": 2,
             "options": [{"letter": "A"}, {"letter": "B"}]},
            {"type": "ps",  "answer": "B", "marks": 3,
             "options": [{"letter": "A"}, {"letter": "B"}]},
            {"type": "tf",  "answer": "True", "marks": 1,
             "options": [{"letter": "A", "text": "True"}, {"letter": "B", "text": "False"}]},
        ]
        earned, total = grade_quiz(questions, {"0": "A", "1": "B", "2": "True"})
        assert total == 6
        assert earned == 6

    def test_case_insensitive_matching(self):
        from app.services.quiz_service import grade_quiz
        questions = [{"type": "mcq", "answer": "B", "marks": 2,
                      "options": [{"letter": "A"}, {"letter": "B"}]}]
        earned, _ = grade_quiz(questions, {"0": "b"})
        assert earned == 2

    def test_empty_questions_returns_zero(self):
        from app.services.quiz_service import grade_quiz
        earned, total = grade_quiz([], {})
        assert earned == 0
        assert total == 0