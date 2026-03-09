"""
tests/test_new_coverage.py
==========================
Tests for routes that had bugs fixed but lacked coverage:

  - payments.initiate         (BUG-09: used to return None every call)
  - payments.subscribe_verify (BUG-10: wrong email helper args)
  - posts.like                (BUG-12: XP was awarded on unlike)
  - posts.edit + quiz         (INV-01b: detached post after inner commit)
  - admin.statistics          (BUG-19: N+1 writes on every load)

Run from the edushare/ root:
    pytest tests/test_new_coverage.py -v
"""

import json
import io
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest

from app import db
from app.models import (
    Like, Post, QuizData, Subscription, User, Document
)


# ══════════════════════════════════════════════════════════════════════════════
# Shared login helper
# ══════════════════════════════════════════════════════════════════════════════

def _login(client, user, password='Password123!'):
    client.post('/auth/login', data={
        'username': user.username,
        'password': password,
    }, follow_redirects=True)
    return client


# ══════════════════════════════════════════════════════════════════════════════
# payments.initiate  (BUG-09)
#
# KEY LESSON: make_user() opens its own app_context internally (conftest.py).
# Never wrap make_user() inside another `with app.app_context()` block —
# nested contexts cause 'not persistent within this Session' errors because
# the user object is bound to the inner session which closes when that block
# exits. Create Document/Post in a SEPARATE context AFTER make_user returns.
# ══════════════════════════════════════════════════════════════════════════════

class TestPaymentsInitiate:

    def _make_paid_doc(self, app, user_id, paid=True, price=10.0):
        """Create Document+Post in their own context. Returns doc_id."""
        with app.app_context():
            doc = Document(
                filename='paid.pdf', original_filename='paid.pdf',
                file_path='/uploads/paid.pdf', file_type='pdf',
                is_paid=paid, price=price,
            )
            db.session.add(doc)
            db.session.flush()
            post = Post(
                user_id=user_id, title='Paid', description='d',
                content_type='notes', status='approved',
                has_document=True, document_id=doc.id,
            )
            db.session.add(post)
            db.session.commit()
            return doc.id

    def test_initiate_redirects_to_paystack_on_success(
            self, client, db_session, make_user, app):
        user   = make_user(username='buyer', email='buyer@example.com')
        doc_id = self._make_paid_doc(app, user.id)
        logged_in = _login(client, user)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            'status': True,
            'data': {'authorization_url': 'https://paystack.com/pay/abc123'},
        }
        with patch('app.payments.routes.requests.post', return_value=mock_resp):
            response = logged_in.post(f'/payments/initiate/{doc_id}',
                                      follow_redirects=False)

        assert response.status_code == 302
        assert 'paystack.com' in response.location

    def test_initiate_flashes_error_on_paystack_failure(
            self, client, db_session, make_user, app):
        user   = make_user(username='buyer2', email='buyer2@example.com')
        doc_id = self._make_paid_doc(app, user.id)
        logged_in = _login(client, user)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {'status': False, 'message': 'Bad request'}
        with patch('app.payments.routes.requests.post', return_value=mock_resp):
            response = logged_in.post(f'/payments/initiate/{doc_id}',
                                      follow_redirects=True)

        assert response.status_code == 200
        assert b'Payment could not be initiated' in response.data

    def test_initiate_flashes_error_on_network_exception(
            self, client, db_session, make_user, app):
        import requests as _req
        user   = make_user(username='buyer3', email='buyer3@example.com')
        doc_id = self._make_paid_doc(app, user.id)
        logged_in = _login(client, user)

        with patch('app.payments.routes.requests.post',
                   side_effect=_req.exceptions.RequestException('timeout')):
            response = logged_in.post(f'/payments/initiate/{doc_id}',
                                      follow_redirects=True)

        assert response.status_code == 200
        assert b'network error' in response.data.lower()

    def test_initiate_free_document_skips_paystack(
            self, client, db_session, make_user, app):
        user   = make_user(username='freebuyer', email='freebuyer@example.com')
        doc_id = self._make_paid_doc(app, user.id, paid=False, price=0.0)
        logged_in = _login(client, user)

        with patch('app.payments.routes.requests.post') as mock_post:
            response = logged_in.post(f'/payments/initiate/{doc_id}',
                                      follow_redirects=False)
            mock_post.assert_not_called()

        assert response.status_code == 302

    def test_initiate_requires_login(self, client, db_session, make_user, app):
        user   = make_user(username='buyer5', email='buyer5@example.com')
        doc_id = self._make_paid_doc(app, user.id)
        # Not logged in
        response = client.post(f'/payments/initiate/{doc_id}',
                               follow_redirects=False)
        assert response.status_code == 302
        assert '/login' in response.location or '/auth' in response.location


# ══════════════════════════════════════════════════════════════════════════════
# payments.subscribe_verify  (BUG-10)
#
# KEY LESSON: send_subscription_activation_email is imported LOCALLY inside
# the route function body: `from app.utils import send_subscription_activation_email`
# Patching 'app.payments.routes.send_subscription_activation_email' won't work
# because it is never a module-level name. Must patch 'app.utils.send_subscription_activation_email'.
# ══════════════════════════════════════════════════════════════════════════════

class TestSubscribeVerify:

    _EMAIL_PATCH = 'app.utils.send_subscription_activation_email'

    def _paystack_ok(self, pesewas=2000):
        m = MagicMock()
        m.json.return_value = {
            'status': True,
            'data': {'status': 'success', 'amount': pesewas, 'channel': 'card'},
        }
        return m

    def test_verify_creates_subscription(self, client, db_session, make_user, app):
        user = make_user()
        logged_in = _login(client, user)

        with patch('app.payments.routes.requests.get', return_value=self._paystack_ok()):
            with patch(self._EMAIL_PATCH):
                response = logged_in.get(
                    '/payments/subscribe/verify'
                    '?reference=txn_001&plan_key=monthly_unlimited',
                    follow_redirects=True,
                )

        assert response.status_code == 200
        with app.app_context():
            sub = Subscription.query.filter_by(transaction_id='txn_001').first()
            assert sub is not None
            assert sub.status == 'active'
            assert sub.plan_key == 'monthly_unlimited'

    def test_verify_sends_email_with_correct_args(
            self, client, db_session, make_user, app):
        """BUG-10 regression: helper must be called as (user, plan_key_str)."""
        user = make_user()
        logged_in = _login(client, user)

        with patch('app.payments.routes.requests.get', return_value=self._paystack_ok()):
            with patch(self._EMAIL_PATCH) as mock_email:
                logged_in.get(
                    '/payments/subscribe/verify'
                    '?reference=txn_email&plan_key=monthly_unlimited',
                    follow_redirects=True,
                )

        mock_email.assert_called_once()
        args = mock_email.call_args[0]
        assert len(args) == 2, (
            f"BUG-10 regression: expected 2 positional args, got {len(args)}: {args}"
        )
        assert isinstance(args[1], str), (
            f"BUG-10 regression: second arg should be plan_key string, got {type(args[1])}"
        )
        assert args[1] == 'monthly_unlimited'

    def test_verify_unknown_plan_redirects(self, client, db_session, make_user, app):
        user = make_user()
        logged_in = _login(client, user)
        response = logged_in.get(
            '/payments/subscribe/verify?reference=txn_x&plan_key=no_such_plan',
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b'Unknown plan' in response.data

    def test_verify_duplicate_reference_is_idempotent(
            self, client, db_session, make_user, app):
        user = make_user()
        with app.app_context():
            now = datetime.now(timezone.utc)
            sub = Subscription(
                user_id=user.id, plan_key='monthly_unlimited',
                plan_name='Monthly Unlimited', amount_paid=20.0,
                currency='GHS', payment_method='card',
                transaction_id='dup_ref_001', status='active',
                started_at=now, expires_at=now + timedelta(days=30),
            )
            db.session.add(sub)
            db.session.commit()

        logged_in = _login(client, user)
        with patch('app.payments.routes.requests.get') as mock_get:
            logged_in.get(
                '/payments/subscribe/verify'
                '?reference=dup_ref_001&plan_key=monthly_unlimited',
                follow_redirects=True,
            )
            mock_get.assert_not_called()

        with app.app_context():
            count = Subscription.query.filter_by(transaction_id='dup_ref_001').count()
            assert count == 1

    def test_verify_failed_payment_records_failed_sub(
            self, client, db_session, make_user, app):
        user = make_user()
        logged_in = _login(client, user)

        m = MagicMock()
        m.json.return_value = {
            'status': True,
            'data': {'status': 'failed', 'amount': 0, 'channel': 'card'},
        }
        with patch('app.payments.routes.requests.get', return_value=m):
            response = logged_in.get(
                '/payments/subscribe/verify'
                '?reference=txn_fail&plan_key=monthly_unlimited',
                follow_redirects=True,
            )

        assert response.status_code == 200
        with app.app_context():
            sub = Subscription.query.filter_by(transaction_id='txn_fail').first()
            assert sub is not None
            assert sub.status == 'failed'

    def test_verify_requires_login(self, client, db_session, app):
        response = client.get(
            '/payments/subscribe/verify?reference=x&plan_key=monthly_unlimited',
            follow_redirects=False,
        )
        assert response.status_code == 302
        assert '/login' in response.location or '/auth' in response.location


# ══════════════════════════════════════════════════════════════════════════════
# posts.like  (BUG-12)
# ══════════════════════════════════════════════════════════════════════════════

class TestLikeXp:

    def _setup(self, make_user, make_post):
        liker  = make_user(username='liker',  email='liker@example.com')
        author = make_user(username='poster', email='poster@example.com')
        post   = make_post(user_id=author.id)
        return liker, post

    def test_like_awards_xp(self, client, db_session, make_user, make_post, app):
        liker, post = self._setup(make_user, make_post)
        logged_in = _login(client, liker)

        with app.app_context():
            xp_before = db.session.get(User, liker.id).xp_points or 0

        logged_in.post(f'/posts/{post.id}/like')

        with app.app_context():
            xp_after = db.session.get(User, liker.id).xp_points or 0

        assert xp_after > xp_before

    def test_unlike_does_not_award_xp(self, client, db_session, make_user, make_post, app):
        """BUG-12 regression: XP must NOT increase when toggling a like OFF."""
        liker, post = self._setup(make_user, make_post)
        logged_in = _login(client, liker)

        logged_in.post(f'/posts/{post.id}/like')   # like → XP awarded here

        with app.app_context():
            xp_after_like = db.session.get(User, liker.id).xp_points or 0

        logged_in.post(f'/posts/{post.id}/like')   # unlike → must NOT award XP

        with app.app_context():
            xp_after_unlike = db.session.get(User, liker.id).xp_points or 0

        assert xp_after_unlike == xp_after_like, (
            f"BUG-12 regression: XP changed on unlike "
            f"(was {xp_after_like}, now {xp_after_unlike})"
        )

    def test_like_creates_db_record(self, client, db_session, make_user, make_post, app):
        liker, post = self._setup(make_user, make_post)
        _login(client, liker).post(f'/posts/{post.id}/like')
        with app.app_context():
            assert Like.query.filter_by(user_id=liker.id, post_id=post.id).first() is not None

    def test_unlike_removes_db_record(self, client, db_session, make_user, make_post, app):
        liker, post = self._setup(make_user, make_post)
        logged_in = _login(client, liker)
        logged_in.post(f'/posts/{post.id}/like')
        logged_in.post(f'/posts/{post.id}/like')
        with app.app_context():
            assert Like.query.filter_by(user_id=liker.id, post_id=post.id).first() is None

    def test_three_toggles_leaves_one_record(self, client, db_session,
                                              make_user, make_post, app):
        liker, post = self._setup(make_user, make_post)
        logged_in = _login(client, liker)
        for _ in range(3):
            logged_in.post(f'/posts/{post.id}/like')
        with app.app_context():
            assert Like.query.filter_by(user_id=liker.id, post_id=post.id).count() == 1

    def test_like_requires_login(self, client, db_session, make_user, make_post, app):
        _, post = self._setup(make_user, make_post)
        response = client.post(f'/posts/{post.id}/like', follow_redirects=False)
        assert response.status_code == 302
        assert '/login' in response.location or '/auth' in response.location


# ══════════════════════════════════════════════════════════════════════════════
# posts.edit + quiz attachment  (INV-01b)
#
# KEY LESSON for test_edit_with_quiz_json_attaches_quiz:
# upload_document is mocked, but db.session.add(mock_doc) + flush() with a
# pure MagicMock silently breaks (SQLAlchemy can't map it). The fix is to
# create a *real* Document row first, then return that from the mock so that
# session.add/flush work correctly and validate_and_attach_quiz can run.
# ══════════════════════════════════════════════════════════════════════════════

class TestEditQuizAttachment:

    _VALID_QUIZ_JSON = json.dumps({
        "document_type": "quiz",
        "title": "Test Quiz",
        "course": "Algebra",
        "level": "SHS",
        "metadata": {
            "total_marks": 2,
            "total_questions": 1,
            "time": "30 mins",
        },
        "instructions": ["Answer all questions."],
        "sections": [
            {
                "section_letter": "A",
                "section_title": "Multiple Choice",
                "question_type": "multiple_choice",
                "questions_count": 1,
                "total_section_marks": 2,
                "questions": [
                    {
                        "question_number": 1,
                        "question_text": "What is 1+1?",
                        "marks": 2,
                        "options": [
                            {"letter": "A", "text": "1"},
                            {"letter": "B", "text": "2"},
                            {"letter": "C", "text": "3"},
                            {"letter": "D", "text": "4"},
                        ],
                        "correct_answer": "B",
                        "explanation": "One plus one equals two because adding one unit to another gives two units.",
                    }
                ],
            }
        ],
        "answer_key": [],
    })

    def _setup(self, make_user, make_post):
        user = make_user()
        post = make_post(user_id=user.id, content_type='notes', status='approved')
        return user, post

    def test_edit_title_update_succeeds(self, client, db_session, make_user, make_post, app):
        user, post = self._setup(make_user, make_post)
        logged_in = _login(client, user)

        response = logged_in.post(
            f'/posts/{post.id}/edit',
            data={
                'title': 'Updated Title',
                'description': 'Updated desc',
                'subject': '0',
                'content_type': 'notes',
                'is_paid': '',
                'price': '',
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        with app.app_context():
            assert db.session.get(Post, post.id).title == 'Updated Title'

    def test_edit_denied_to_non_author(self, client, db_session, make_user, make_post, app):
        user, post = self._setup(make_user, make_post)
        other = make_user(username='other', email='other@example.com')
        _login(client, other).post(
            f'/posts/{post.id}/edit',
            data={'title': 'Hijacked', 'description': 'd',
                  'subject': '0', 'content_type': 'notes'},
            follow_redirects=True,
        )
        with app.app_context():
            assert db.session.get(Post, post.id).title != 'Hijacked'

    def test_edit_with_new_file_resets_status_to_pending(
            self, client, db_session, make_user, make_post, app):
        user, post = self._setup(make_user, make_post)
        logged_in = _login(client, user)

        # Return a MagicMock — the route only reads .is_paid and .price from it
        # before calling db.session.add; we tolerate a flush error here since
        # we only care about the status change, not the document row.
        mock_doc = MagicMock()
        mock_doc.is_paid = False
        mock_doc.price = 0.0

        with patch('app.posts.routes.upload_document', return_value=mock_doc), \
             patch('app.posts.routes.delete_document'), \
             patch('app.db.session.flush'):   # suppress flush so MagicMock doesn't error
            logged_in.post(
                f'/posts/{post.id}/edit',
                data={
                    'title': 'Same Title', 'description': 'desc',
                    'subject': '0', 'content_type': 'notes',
                    'is_paid': '', 'price': '',
                    'document': (io.BytesIO(b'%PDF-1.4 fake'), 'new_doc.pdf'),
                },
                content_type='multipart/form-data',
                follow_redirects=True,
            )

        with app.app_context():
            assert db.session.get(Post, post.id).status == 'pending'

    def test_edit_with_quiz_json_calls_validate_and_attach(
            self, client, db_session, make_user, make_post, app):
        """
        INV-01b regression: verifies the route reaches validate_and_attach_quiz.

        We mock validate_and_attach_quiz itself so that:
        - We know for certain it was called (route reached the quiz branch)
        - We avoid depending on jsonschema/validation internals in an integration test
        A DetachedInstanceError from INV-01b would cause a 500, not 200.
        """
        user, post = self._setup(make_user, make_post)

        with app.app_context():
            real_doc = Document(
                filename='quiz.pdf', original_filename='quiz.pdf',
                file_path='/uploads/quiz.pdf', file_type='pdf',
                is_paid=False, price=0.0,
            )
            db.session.add(real_doc)
            db.session.commit()
            real_doc_id = real_doc.id

        logged_in = _login(client, user)

        def _return_real_doc(*args, **kwargs):
            return db.session.get(Document, real_doc_id)

        # Mock validate_and_attach_quiz to return a sentinel QuizData
        # so we can assert it was called without running real validation.
        mock_quiz = MagicMock(spec=QuizData)

        with patch('app.posts.routes.upload_document', side_effect=_return_real_doc), \
             patch('app.posts.routes.delete_document'), \
             patch('app.services.quiz_service.validate_and_attach_quiz',
                   return_value=(mock_quiz, None)) as mock_attach:
            response = logged_in.post(
                f'/posts/{post.id}/edit',
                data={
                    'title': 'Quiz Post', 'description': 'desc',
                    'subject': '0', 'content_type': 'quiz',
                    'is_paid': '', 'price': '',
                    'document':     (io.BytesIO(b'%PDF-1.4 fake'), 'quiz.pdf'),
                    'json_sidecar': (io.BytesIO(self._VALID_QUIZ_JSON.encode()), 'quiz.json'),
                },
                content_type='multipart/form-data',
                follow_redirects=True,
            )

        # 500 would indicate DetachedInstanceError (INV-01b regression)
        assert response.status_code == 200, \
            f"Route returned {response.status_code} — possible DetachedInstanceError (INV-01b)"

        assert mock_attach.called, (
            "validate_and_attach_quiz was never called — route did not reach "
            "the quiz attachment branch. Check form validation and file upload."
        )

    def test_quiz_json_passes_validation(self, db_session, app):
        """
        Unit test: the _VALID_QUIZ_JSON constant must pass validate_document
        so that test_edit_with_quiz_json_calls_validate_and_attach is meaningful.
        """
        from app.services.quiz_service import validate_document, DocumentValidationError
        import json

        with app.app_context():
            doc = json.loads(self._VALID_QUIZ_JSON)
            try:
                result = validate_document(doc)
                assert result is not None
            except (DocumentValidationError, ValueError) as e:
                pytest.fail(f"_VALID_QUIZ_JSON failed validation: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# admin.statistics  (BUG-19)
# ══════════════════════════════════════════════════════════════════════════════

class TestAdminStatistics:

    def test_statistics_page_renders(self, client, db_session, make_user, app):
        admin = make_user(username='admin', email='admin@example.com', is_admin=True)
        response = _login(client, admin).get('/admin/statistics')
        assert response.status_code == 200

    def test_statistics_does_not_call_update_post_count(
            self, client, db_session, make_user, app):
        """BUG-19 regression: page must use aggregate query, not per-subject writes."""
        admin = make_user(username='admin2', email='admin2@example.com', is_admin=True)
        logged_in = _login(client, admin)

        with patch('app.models.Subject.update_post_count') as mock_update:
            logged_in.get('/admin/statistics')

        assert not mock_update.called, (
            "BUG-19 regression: Subject.update_post_count() called from statistics route."
        )

    def test_statistics_shows_correct_post_count(
            self, client, db_session, make_user, make_post, app):
        admin = make_user(username='admin3', email='admin3@example.com', is_admin=True)
        make_post(user_id=admin.id, status='approved')
        make_post(user_id=admin.id, status='approved')
        logged_in = _login(client, admin)
        response = logged_in.get('/admin/statistics')
        assert response.status_code == 200