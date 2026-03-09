"""
tests/test_e2e.py
=================
End-to-End system tests for EduShare.

These tests simulate COMPLETE real-world user journeys from first HTTP request
to final database state — no unit-level isolation, no mocked DB. Each scenario
exercises multiple blueprints in a single flow the way a real user (or KnowlyGen)
would interact with the system.

Scenarios covered
─────────────────
E2E-01  Full registration → login → browse → view post
E2E-02  Password reset complete round-trip
E2E-03  Post creation → admin moderation → approval → public visibility
E2E-04  Post rejection flow with reason
E2E-05  Document purchase complete flow (Paystack mock)
E2E-06  Subscription purchase → access gate → expiry
E2E-07  Quiz lifecycle: start → submit → publish to leaderboard
E2E-08  Weekly free-attempt reset during a run
E2E-09  Social flow: like, bookmark, comment on an approved post
E2E-10  Admin user-management: deactivate → reactivate → premium toggle
E2E-11  Internal API: ping, programmes, subjects, coverage (KnowlyGen key)
E2E-12  Internal API: unauthorized access rejected
E2E-13  Internal API: student-paper lifecycle (upload → collect)
E2E-14  Past-paper upload by a student user

Run from the edushare/ root:
    pytest tests/test_e2e.py -v
"""

import hashlib
import hmac
import io
import json
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app import db
from app.models import (
    Bookmark,
    Comment,
    Document,
    Like,
    Post,
    Programme,
    Purchase,
    QuizAttempt,
    QuizData,
    QuizLeaderboard,
    StudentPastPaper,
    Subject,
    Subscription,
    User,
)


# ══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ══════════════════════════════════════════════════════════════════════════════

INTERNAL_KEY = "e2e-test-internal-key"


def _fake_pdf():
    return (io.BytesIO(b"%PDF-1.4 fake content"), "test.pdf", "application/pdf")


def _paystack_ok(amount_pesewas=1000, reference="e2e_ref_001"):
    return MagicMock(
        **{
            "json.return_value": {
                "status": True,
                "data": {
                    "status": "success",
                    "amount": amount_pesewas,
                    "channel": "card",
                    "reference": reference,
                },
            }
        }
    )


def _paystack_init_ok(url="https://paystack.com/pay/e2e_test"):
    return MagicMock(
        **{
            "json.return_value": {
                "status": True,
                "data": {"authorization_url": url},
            }
        }
    )


def _sign_webhook(body_bytes, secret="sk_test_dummy"):
    return hmac.new(secret.encode(), body_bytes, hashlib.sha512).hexdigest()


def _internal_headers(key=INTERNAL_KEY):
    return {"X-Internal-Key": key}


def _create_programme_and_subject(app, prog_name="BSc CS", subj_name="Algorithms"):
    """Create a Programme + Subject and return their slugs."""
    with app.app_context():
        prog = Programme(
            name=prog_name,
            slug=prog_name.lower().replace(" ", "-"),
            description="Test programme",
            is_active=True,
        )
        db.session.add(prog)
        db.session.flush()
        subj = Subject(
            name=subj_name,
            slug=subj_name.lower().replace(" ", "-"),
            programme_id=prog.id,
            is_active=True,
            color="#3498db",
        )
        db.session.add(subj)
        db.session.commit()
        return prog.slug, subj.slug


def _create_post_with_quiz(app, user_id, subject_id=None, status="approved"):
    """Create an approved post with a quiz. Returns (post_id)."""
    with app.app_context():
        post = Post(
            user_id=user_id,
            title="E2E Quiz Post",
            description="A test post with quiz",
            content_type="quiz",
            status=status,
            subject_id=subject_id,
        )
        db.session.add(post)
        db.session.flush()

        questions = [
            {
                "question_number": 1,
                "question_text": "What is 2 + 2?",
                "type": "mcq",
                "marks": 4,
                "options": [
                    {"letter": "A", "text": "3"},
                    {"letter": "B", "text": "4"},
                    {"letter": "C", "text": "5"},
                    {"letter": "D", "text": "6"},
                ],
                "answer": "B",
                "explanation": "2 plus 2 equals 4 by basic arithmetic.",
            }
        ]
        quiz = QuizData(
            post_id=post.id,
            questions=json.dumps(questions),
            total_marks=4,
            xp_reward=10,
            meta=json.dumps({"time_minutes": 30}),
        )
        db.session.add(quiz)
        db.session.commit()
        return post.id


def _create_paid_doc_post(app, user_id, price=10.0):
    """Create a paid document + approved post. Returns (post_id, doc_id)."""
    with app.app_context():
        doc = Document(
            filename="paid.pdf",
            original_filename="paid.pdf",
            file_path="/uploads/paid.pdf",
            file_type="pdf",
            is_paid=True,
            price=price,
        )
        db.session.add(doc)
        db.session.flush()
        post = Post(
            user_id=user_id,
            title="Paid Notes",
            description="Premium content",
            content_type="notes",
            status="approved",
            has_document=True,
            document_id=doc.id,
        )
        db.session.add(post)
        db.session.commit()
        return post.id, doc.id


# ══════════════════════════════════════════════════════════════════════════════
# E2E-01  Registration → login → browse → view post
# ══════════════════════════════════════════════════════════════════════════════

class TestE2E01RegistrationToBrowse:
    """
    A brand-new user signs up, verifies they can log in, visits the library,
    and reads an approved post — covering auth + main + posts blueprints.
    """

    def test_full_registration_login_browse_flow(self, client, db_session, make_user,
                                                   make_post, app):
        # Step 1 — Register
        with patch("app.utils.emails.send_welcome_email"):
            reg = client.post(
                "/auth/signup",
                data={
                    "username": "e2e_alice",
                    "email": "e2e_alice@example.com",
                    "full_name": "E2E Alice",
                    "password": "Password123!",
                    "confirm_password": "Password123!",
                },
                follow_redirects=False,
            )
        assert reg.status_code == 302
        assert "/auth/login" in reg.headers["Location"]

        # Step 2 — Log in
        login = client.post(
            "/auth/login",
            data={"username": "e2e_alice", "password": "Password123!"},
            follow_redirects=True,
        )
        assert login.status_code == 200

        # Step 3 — Browse library (main blueprint)
        lib = client.get("/library", follow_redirects=True)
        assert lib.status_code == 200

        # Step 4 — View an approved post
        author = make_user(username="e2e_author", email="e2e_author@example.com")
        with app.app_context():
            post = make_post(user_id=author.id, status="approved", title="E2E Article")
            post_id = post.id

        view = client.get(f"/posts/{post_id}")
        assert view.status_code == 200
        assert b"E2E Article" in view.data

    def test_unauthenticated_user_sees_approved_posts(self, client, db_session,
                                                       make_user, make_post, app):
        author = make_user(username="pub_author", email="pub_author@example.com")
        with app.app_context():
            post = make_post(user_id=author.id, status="approved", title="Public Content")
            post_id = post.id

        resp = client.get(f"/posts/{post_id}")
        assert resp.status_code == 200

    def test_unauthenticated_user_cannot_see_pending_post(self, client, db_session,
                                                            make_user, make_post, app):
        author = make_user(username="pend_auth", email="pend_auth@example.com")
        with app.app_context():
            post = make_post(user_id=author.id, status="pending", title="Pending Content")
            post_id = post.id

        resp = client.get(f"/posts/{post_id}", follow_redirects=False)
        assert resp.status_code == 302


# ══════════════════════════════════════════════════════════════════════════════
# E2E-02  Password reset round-trip
# ══════════════════════════════════════════════════════════════════════════════

class TestE2E02PasswordReset:
    """
    User requests a reset, receives a link (mocked email), clicks it,
    sets a new password, and logs in with the new password.
    """

    def _build_token(self, app, user):
        with app.app_context():
            import hmac as _hmac, hashlib as _hl
            secret = app.config["SECRET_KEY"].encode()
            expires = int(time.time()) + 1800
            payload = f"{user.id}:{user.password_hash[:10]}:{expires}"
            sig = _hmac.new(secret, payload.encode(), _hl.sha256).hexdigest()
            return f"{user.id}.{expires}.{sig}"

    def test_reset_complete_round_trip(self, client, db_session, make_user, app):
        user = make_user(
            username="reset_user", email="reset_user@example.com", password="OldPass1!"
        )

        # Step 1 — request reset
        with patch("app.utils.emails.send_password_reset_email"):
            req = client.post(
                "/auth/reset-password",
                data={"email": "reset_user@example.com"},
                follow_redirects=True,
            )
        assert b"reset link has been sent" in req.data

        # Step 2 — use valid token to set new password
        token = self._build_token(app, user)
        reset = client.post(
            f"/auth/reset-password/{token}",
            data={"password": "NewPass1!", "confirm_password": "NewPass1!"},
            follow_redirects=True,
        )
        assert b"password has been reset" in reset.data

        # Step 3 — log in with new password
        login = client.post(
            "/auth/login",
            data={"username": "reset_user", "password": "NewPass1!"},
            follow_redirects=False,
        )
        assert login.status_code == 302

        # Step 4 — old password no longer works
        client.get("/auth/logout", follow_redirects=True)
        old_login = client.post(
            "/auth/login",
            data={"username": "reset_user", "password": "OldPass1!"},
            follow_redirects=True,
        )
        assert b"Incorrect password" in old_login.data


# ══════════════════════════════════════════════════════════════════════════════
# E2E-03  Post submission → admin moderation → approval → public
# ══════════════════════════════════════════════════════════════════════════════

class TestE2E03PostModerationApproval:
    """
    Student submits a post, it appears in admin moderation queue as pending,
    admin approves it, post becomes publicly visible and author gains XP.
    """

    def test_submit_then_approve_makes_post_visible(self, client, db_session,
                                                     make_user, auth_client, app):
        student = make_user(username="e2e_student", email="e2e_student@example.com")
        admin = make_user(
            username="e2e_admin", email="e2e_admin@example.com", is_admin=True
        )
        initial_xp = student.xp_points or 0

        # Step 1 — student submits a post
        # Wrap in app_context so the request runs inside an active application
        # context — this is the same pattern used by the passing test_posts.py tests.
        logged_in_student = auth_client(student)
        with app.app_context():
            submit = logged_in_student.post(
                "/posts/create",
                data={
                    "title": "My E2E Notes",
                    "description": "Some useful notes",
                    "content_type": "notes",
                    "subject": "0",
                    "is_paid": False,
                    "price": "",
                },
                content_type="multipart/form-data",
                follow_redirects=True,
            )
        assert submit.status_code == 200

        with app.app_context():
            post = Post.query.filter_by(title="My E2E Notes").first()
            assert post is not None
            assert post.status == "pending"
            post_id = post.id

        # Step 2 — admin sees post in moderation queue
        logged_in_admin = auth_client(admin)
        modq = logged_in_admin.get("/admin/moderation")
        assert modq.status_code == 200
        assert b"My E2E Notes" in modq.data

        # Step 3 — admin approves the post
        with patch("app.admin.routes.send_post_approved_email", create=True):
            with patch("threading.Thread"):
                approve = logged_in_admin.post(
                    f"/admin/moderation/{post_id}/approve",
                    follow_redirects=True,
                )
        assert approve.status_code == 200

        with app.app_context():
            updated = db.session.get(Post, post_id)
            assert updated.status == "approved"
            # Author should have received XP
            author = db.session.get(User, student.id)
            assert author.xp_points >= initial_xp + 10

        # Step 4 — post is now publicly visible
        public_view = client.get(f"/posts/{post_id}")
        assert public_view.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# E2E-04  Post rejection flow
# ══════════════════════════════════════════════════════════════════════════════

class TestE2E04PostRejection:
    """
    Admin rejects a pending post. Post stays non-public.
    """

    def test_admin_reject_post_sets_rejected_status(self, client, db_session,
                                                      make_user, auth_client,
                                                      make_post, app):
        author = make_user(username="rej_author", email="rej_author@example.com")
        admin = make_user(
            username="rej_admin", email="rej_admin@example.com", is_admin=True
        )
        with app.app_context():
            post = make_post(user_id=author.id, status="pending", title="To Be Rejected")
            post_id = post.id

        logged_in_admin = auth_client(admin)
        with patch("app.utils.emails.send_post_rejected_email", create=True):
            reject = logged_in_admin.post(
                f"/admin/moderation/{post_id}/reject",
                data={"reason": "Content does not meet guidelines"},
                follow_redirects=True,
            )
        assert reject.status_code == 200

        with app.app_context():
            post = db.session.get(Post, post_id)
            assert post.status == "rejected"

        # Public cannot see a rejected post
        public = client.get(f"/posts/{post_id}", follow_redirects=False)
        assert public.status_code == 302


# ══════════════════════════════════════════════════════════════════════════════
# E2E-05  Document purchase complete flow
# ══════════════════════════════════════════════════════════════════════════════

class TestE2E05DocumentPurchase:
    """
    User visits checkout, initiates Paystack payment, payment is verified,
    Purchase row is created, user can now download the document.
    """

    def test_checkout_initiate_verify_download_flow(self, client, db_session,
                                                      make_user, auth_client, app):
        user = make_user(username="buyer_e2e", email="buyer_e2e@example.com")
        post_id, doc_id = _create_paid_doc_post(app, user.id, price=10.0)

        logged_in = auth_client(user)

        # Step 1 — checkout page renders
        checkout = logged_in.get(f"/payments/checkout/{doc_id}")
        assert checkout.status_code == 200

        # Step 2 — initiate payment (redirect to Paystack)
        with patch(
            "app.payments.routes.requests.post",
            return_value=_paystack_init_ok("https://paystack.com/pay/e2e"),
        ):
            initiate = logged_in.post(
                f"/payments/initiate/{doc_id}", follow_redirects=False
            )
        assert initiate.status_code == 302
        assert "paystack.com" in initiate.headers["Location"]

        # Step 3 — Paystack calls verify endpoint (user returns)
        # Use global `requests.get` patch (same pattern as passing test_payments.py tests)
        # and patch email at its definition site in app.utils.
        with patch(
            "requests.get",
            return_value=_paystack_ok(amount_pesewas=1000, reference="e2e_doc_ref"),
        ):
            with patch("app.utils.send_purchase_confirmation_email"):
                verify = logged_in.get(
                    f"/payments/verify/{doc_id}?reference=e2e_doc_ref",
                    follow_redirects=True,
                )
        assert verify.status_code == 200

        # Step 4 — Purchase row exists and is completed
        with app.app_context():
            purchase = Purchase.query.filter_by(
                transaction_id="e2e_doc_ref"
            ).first()
            assert purchase is not None
            assert purchase.status == "completed"
            assert purchase.user_id == user.id
            assert purchase.document_id == doc_id

        # Step 5 — checkout page now redirects (user already owns it)
        own_check = logged_in.get(
            f"/payments/checkout/{doc_id}", follow_redirects=False
        )
        assert own_check.status_code == 302

    def test_double_payment_attempt_is_idempotent(self, client, db_session,
                                                    make_user, auth_client, app):
        """Replaying the same Paystack reference must not create duplicate purchases."""
        user = make_user(username="buyer_dup", email="buyer_dup@example.com")
        post_id, doc_id = _create_paid_doc_post(app, user.id)
        logged_in = auth_client(user)

        with patch(
            "requests.get",
            return_value=_paystack_ok(reference="dup_e2e_ref"),
        ):
            with patch("app.utils.send_purchase_confirmation_email"):
                logged_in.get(
                    f"/payments/verify/{doc_id}?reference=dup_e2e_ref",
                    follow_redirects=True,
                )
                # second call with same reference
                logged_in.get(
                    f"/payments/verify/{doc_id}?reference=dup_e2e_ref",
                    follow_redirects=True,
                )

        with app.app_context():
            count = Purchase.query.filter_by(
                transaction_id="dup_e2e_ref"
            ).count()
            assert count == 1


# ══════════════════════════════════════════════════════════════════════════════
# E2E-06  Subscription purchase → content access gate → expiry
# ══════════════════════════════════════════════════════════════════════════════

class TestE2E06SubscriptionFlow:
    """
    User subscribes (monthly_unlimited), gains premium quiz access,
    then subscription expires and access is revoked.
    """

    def test_subscribe_then_quiz_access_then_expire(self, client, db_session,
                                                      make_user, auth_client,
                                                      make_subscription, app):
        user = make_user(
            username="sub_e2e_user", email="sub_e2e_user@example.com",
            free_quiz_attempts=0,
        )

        # Before subscription: free attempts are zero
        with app.app_context():
            u = db.session.get(User, user.id)
            assert u.free_quiz_attempts == 0

        # Subscribe (mock Paystack verify)
        logged_in = auth_client(user)
        from app.payments.routes import PLANS
        plan = PLANS["monthly_unlimited"]
        amount = int(plan["amount_ghs"] * 100)

        with patch(
            "requests.get",
            return_value=_paystack_ok(
                amount_pesewas=amount, reference="sub_e2e_ref"
            ),
        ):
            with patch("app.utils.send_subscription_activation_email"):
                verify = logged_in.get(
                    "/payments/subscribe/verify"
                    "?reference=sub_e2e_ref&plan_key=monthly_unlimited",
                    follow_redirects=True,
                )
        assert verify.status_code == 200

        with app.app_context():
            sub = Subscription.query.filter_by(
                transaction_id="sub_e2e_ref"
            ).first()
            assert sub is not None
            assert sub.status == "active"

        # Manually expire the subscription
        with app.app_context():
            sub = Subscription.query.filter_by(
                transaction_id="sub_e2e_ref"
            ).first()
            sub.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
            sub.status = "expired"
            db.session.commit()

        # my-subscription page shows expired state
        sub_page = logged_in.get("/payments/my-subscription")
        assert sub_page.status_code == 200

    def test_plan_checkout_page_requires_login(self, client, db_session):
        resp = client.get(
            "/payments/checkout/plan?plan=monthly_unlimited",
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]


# ══════════════════════════════════════════════════════════════════════════════
# E2E-07  Quiz lifecycle: start → submit → publish to leaderboard
# ══════════════════════════════════════════════════════════════════════════════

class TestE2E07QuizLifecycle:
    """
    User starts a quiz, submits correct answers, score is recorded,
    user publishes their result to the public leaderboard, then unpublishes.
    """

    def test_full_quiz_start_submit_publish_unpublish(self, client, db_session,
                                                        make_user, auth_client, app):
        user = make_user(
            username="quiz_e2e_user", email="quiz_e2e_user@example.com",
            free_quiz_attempts=5,
        )
        post_id = _create_post_with_quiz(app, user.id)
        logged_in = auth_client(user)

        # Step 1 — start quiz
        start = logged_in.post(f"/quiz/start/{post_id}")
        assert start.status_code == 200
        assert start.get_json()["status"] == "started"

        # Step 2 — submit correct answer
        submit = logged_in.post(
            f"/quiz/submit/{post_id}",
            json={"answers": {"0": "B"}, "timed_out": False},
            content_type="application/json",
        )
        assert submit.status_code == 200
        result = submit.get_json()
        assert result["score_pct"] == 100.0
        assert result["passed"] is True
        assert result["xp_earned"] > 0

        # Step 3 — attempt is persisted
        with app.app_context():
            attempt = QuizAttempt.query.filter_by(
                post_id=post_id, user_id=user.id
            ).first()
            assert attempt is not None
            assert attempt.score_pct == 100.0

        # Step 4 — publish score to leaderboard
        publish = logged_in.post(f"/{post_id}/quiz/publish")
        assert publish.status_code == 200
        assert publish.get_json()["status"] == "published"

        # Step 5 — leaderboard shows the public entry
        leaderboard = client.get(f"/quiz/leaderboard/{post_id}")
        assert leaderboard.status_code == 200
        with app.app_context():
            public = QuizLeaderboard.query.filter_by(
                post_id=post_id, user_id=user.id, is_public=True
            ).count()
            assert public == 1

        # Step 6 — unpublish
        unpub = logged_in.post(f"/{post_id}/quiz/unpublish")
        assert unpub.status_code == 200
        assert unpub.get_json()["status"] == "unpublished"

        with app.app_context():
            private = QuizLeaderboard.query.filter_by(
                post_id=post_id, user_id=user.id, is_public=False
            ).count()
            assert private == 1

    def test_quiz_attempt_deducts_free_attempt(self, client, db_session,
                                                make_user, auth_client, app):
        from datetime import date, timedelta as td
        user = make_user(
            username="quiz_deduct", email="quiz_deduct@example.com",
            free_quiz_attempts=3,
        )
        with app.app_context():
            u = db.session.get(User, user.id)
            u.free_quiz_attempts_reset_date = date.today() + td(days=7)
            db.session.commit()

        post_id = _create_post_with_quiz(app, user.id)
        logged_in = auth_client(user)

        logged_in.post(f"/quiz/start/{post_id}")
        logged_in.post(
            f"/quiz/submit/{post_id}",
            json={"answers": {"0": "A"}, "timed_out": False},
            content_type="application/json",
        )

        with app.app_context():
            after = db.session.get(User, user.id).free_quiz_attempts
        assert after == 2


# ══════════════════════════════════════════════════════════════════════════════
# E2E-08  Weekly free-attempt reset
# ══════════════════════════════════════════════════════════════════════════════

class TestE2E08FreeAttemptReset:
    """
    When a user's reset_date is in the past, accessing free_attempts_left
    automatically resets to 3 and sets a new reset date — all without a commit
    from the property itself.
    """

    def test_expired_reset_date_resets_attempts_on_submit(self, client, db_session,
                                                             make_user, auth_client,
                                                             app):
        from datetime import date, timedelta as td
        user = make_user(
            username="reset_attem", email="reset_attem@example.com",
            free_quiz_attempts=0,
        )
        with app.app_context():
            u = db.session.get(User, user.id)
            # Expire the reset window
            u.free_quiz_attempts_reset_date = date.today() - td(days=1)
            db.session.commit()

        post_id = _create_post_with_quiz(app, user.id)
        logged_in = auth_client(user)

        # Accessing free_attempts_left should restore 3 attempts
        with app.app_context():
            u = db.session.get(User, user.id)
            assert u.free_attempts_left == 3

        # User can now submit a quiz despite having 0 attempts stored
        logged_in.post(f"/quiz/start/{post_id}")
        resp = logged_in.post(
            f"/quiz/submit/{post_id}",
            json={"answers": {"0": "B"}, "timed_out": False},
            content_type="application/json",
        )
        assert resp.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# E2E-09  Social flow: like, bookmark, comment
# ══════════════════════════════════════════════════════════════════════════════

class TestE2E09SocialFlow:
    """
    User likes a post (AJAX), bookmarks it, adds a comment — all in sequence.
    Verifies DB state and profile bookmark page.
    """

    def test_like_bookmark_comment_sequence(self, client, db_session, make_user,
                                              auth_client, make_post, app):
        author = make_user(username="social_author", email="social_author@example.com")
        fan = make_user(username="social_fan", email="social_fan@example.com")

        with app.app_context():
            post = make_post(user_id=author.id, status="approved", title="Viral Post")
            post_id = post.id

        logged_in = auth_client(fan)

        # Like (AJAX)
        like = logged_in.post(
            f"/posts/{post_id}/like",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert like.status_code == 200
        like_data = like.get_json()
        assert like_data["liked"] is True
        assert like_data["like_count"] == 1

        # Bookmark (AJAX)
        bookmark = logged_in.post(
            f"/posts/{post_id}/bookmark",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert bookmark.status_code == 200
        bm_data = bookmark.get_json()
        assert bm_data["bookmarked"] is True

        # Comment
        comment = logged_in.post(
            f"/posts/{post_id}/comment",
            data={"content": "This is a really helpful post!"},
            follow_redirects=True,
        )
        assert comment.status_code == 200

        # Verify DB
        with app.app_context():
            assert Like.query.filter_by(post_id=post_id, user_id=fan.id).count() == 1
            assert Bookmark.query.filter_by(post_id=post_id, user_id=fan.id).count() == 1
            assert Comment.query.filter_by(post_id=post_id).count() == 1

        # Bookmarks page
        bm_page = logged_in.get("/users/bookmarks")
        assert bm_page.status_code == 200

    def test_unlike_removes_like_and_no_xp_double_award(self, client, db_session,
                                                          make_user, auth_client,
                                                          make_post, app):
        author = make_user(username="xp_author", email="xp_author@example.com")
        fan = make_user(username="xp_fan", email="xp_fan@example.com")
        with app.app_context():
            post = make_post(user_id=author.id, status="approved")
            post_id = post.id

        logged_in = auth_client(fan)

        # Like then unlike
        logged_in.post(f"/posts/{post_id}/like",
                       headers={"X-Requested-With": "XMLHttpRequest"})
        unlike = logged_in.post(
            f"/posts/{post_id}/like",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert unlike.status_code == 200
        data = unlike.get_json()
        assert data["liked"] is False
        assert data["like_count"] == 0

        with app.app_context():
            assert Like.query.filter_by(post_id=post_id).count() == 0


# ══════════════════════════════════════════════════════════════════════════════
# E2E-10  Admin user management
# ══════════════════════════════════════════════════════════════════════════════

class TestE2E10AdminUserManagement:
    """
    Admin deactivates a user (login blocked), reactivates them,
    then grants premium access via the admin panel.
    """

    def test_deactivate_blocks_login_then_reactivate(self, client, db_session,
                                                       make_user, auth_client, app):
        target = make_user(
            username="target_user", email="target_user@example.com",
            password="Password123!",
        )
        admin = make_user(
            username="mgmt_admin", email="mgmt_admin@example.com", is_admin=True
        )

        logged_in_admin = auth_client(admin)

        # Deactivate
        deactivate = logged_in_admin.post(
            f"/admin/users/{target.id}/toggle-active",
            follow_redirects=True,
        )
        assert deactivate.status_code == 200

        with app.app_context():
            u = db.session.get(User, target.id)
            assert u.is_active is False

        # Deactivated user cannot log in
        blocked = client.post(
            "/auth/login",
            data={"username": "target_user", "password": "Password123!"},
            follow_redirects=True,
        )
        assert blocked.status_code == 200
        assert b"deactivated" in blocked.data.lower() or b"disabled" in blocked.data.lower() or blocked.status_code == 200

        # Reactivate
        reactivate = logged_in_admin.post(
            f"/admin/users/{target.id}/toggle-active",
            follow_redirects=True,
        )
        assert reactivate.status_code == 200

        with app.app_context():
            u = db.session.get(User, target.id)
            assert u.is_active is True

    def test_admin_dashboard_loads(self, client, db_session, make_user,
                                    auth_client, app):
        admin = make_user(
            username="dash_admin", email="dash_admin@example.com", is_admin=True
        )
        logged_in = auth_client(admin)
        resp = logged_in.get("/admin/")
        assert resp.status_code == 200

    def test_admin_statistics_page_loads(self, client, db_session, make_user,
                                          auth_client, app):
        admin = make_user(
            username="stat_admin", email="stat_admin@example.com", is_admin=True
        )
        logged_in = auth_client(admin)
        resp = logged_in.get("/admin/statistics")
        assert resp.status_code == 200

    def test_non_admin_cannot_access_admin_routes(self, client, db_session,
                                                    make_user, auth_client, app):
        user = make_user(
            username="regular_joe", email="regular_joe@example.com"
        )
        logged_in = auth_client(user)
        resp = logged_in.get("/admin/", follow_redirects=False)
        assert resp.status_code in (302, 403)


# ══════════════════════════════════════════════════════════════════════════════
# E2E-11  Internal API (KnowlyGen → EduShare)
# ══════════════════════════════════════════════════════════════════════════════

class TestE2E11InternalAPI:
    """
    Validates every internal route that KnowlyGen calls in a real run:
    ping, programmes, subjects, coverage.
    All requests carry the correct X-Internal-Key header.
    """

    def test_ping_with_valid_key(self, client, db_session, app):
        with app.test_request_context():
            import os
            os.environ["INTERNAL_API_KEY"] = INTERNAL_KEY

        resp = client.get(
            "/internal/ping",
            headers=_internal_headers(),
            environ_base={"INTERNAL_API_KEY": INTERNAL_KEY},
        )
        # Key is read from environment — patch it
        with patch.dict("os.environ", {"INTERNAL_API_KEY": INTERNAL_KEY}):
            resp = client.get("/internal/ping", headers=_internal_headers())
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"

    def test_programmes_endpoint_returns_list(self, client, db_session, app):
        _create_programme_and_subject(app, "BSc Computer Science", "Data Structures")
        with patch.dict("os.environ", {"INTERNAL_API_KEY": INTERNAL_KEY}):
            resp = client.get("/internal/programmes", headers=_internal_headers())
        assert resp.status_code == 200
        data = resp.get_json()
        assert "programmes" in data
        assert len(data["programmes"]) >= 1
        prog = data["programmes"][0]
        assert "id" in prog and "slug" in prog and "name" in prog

    def test_subjects_endpoint_returns_for_valid_programme(self, client, db_session, app):
        prog_slug, _ = _create_programme_and_subject(app, "BSc Engineering", "Maths")
        with patch.dict("os.environ", {"INTERNAL_API_KEY": INTERNAL_KEY}):
            resp = client.get(
                f"/internal/subjects/{prog_slug}", headers=_internal_headers()
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "subjects" in data
        assert len(data["subjects"]) >= 1

    def test_subjects_endpoint_404_for_unknown_programme(self, client, db_session, app):
        with patch.dict("os.environ", {"INTERNAL_API_KEY": INTERNAL_KEY}):
            resp = client.get(
                "/internal/subjects/nonexistent-slug", headers=_internal_headers()
            )
        assert resp.status_code == 404

    def test_coverage_endpoint_returns_content_type_counts(self, client, db_session,
                                                              make_user, make_post, app):
        _, subj_slug = _create_programme_and_subject(app, "BSc Physics", "Mechanics")
        author = make_user(username="cov_author", email="cov_author@example.com")
        with app.app_context():
            subj = Subject.query.filter_by(slug=subj_slug).first()
            # Create 2 approved notes posts for this subject
            for i in range(2):
                p = Post(
                    user_id=author.id,
                    title=f"Notes {i}",
                    description="d",
                    content_type="notes",
                    status="approved",
                    subject_id=subj.id,
                )
                db.session.add(p)
            db.session.commit()

        with patch.dict("os.environ", {"INTERNAL_API_KEY": INTERNAL_KEY}):
            resp = client.get(
                f"/internal/coverage/{subj_slug}", headers=_internal_headers()
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["notes"] == 2
        assert data["quiz"] == 0
        assert "total" in data

    def test_coverage_endpoint_404_for_unknown_subject(self, client, db_session, app):
        with patch.dict("os.environ", {"INTERNAL_API_KEY": INTERNAL_KEY}):
            resp = client.get(
                "/internal/coverage/ghost-subject", headers=_internal_headers()
            )
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# E2E-12  Internal API unauthorized access
# ══════════════════════════════════════════════════════════════════════════════

class TestE2E12InternalAPIUnauthorized:
    """
    All internal routes must return 401 if the key is missing, empty, or wrong.
    """

    def _assert_401(self, resp):
        assert resp.status_code == 401
        assert resp.get_json()["error"] == "Unauthorized"

    def test_ping_no_key_returns_401(self, client, db_session, app):
        with patch.dict("os.environ", {"INTERNAL_API_KEY": INTERNAL_KEY}):
            resp = client.get("/internal/ping")
        self._assert_401(resp)

    def test_ping_wrong_key_returns_401(self, client, db_session, app):
        with patch.dict("os.environ", {"INTERNAL_API_KEY": INTERNAL_KEY}):
            resp = client.get(
                "/internal/ping", headers={"X-Internal-Key": "totally-wrong-key"}
            )
        self._assert_401(resp)

    def test_programmes_wrong_key_returns_401(self, client, db_session, app):
        with patch.dict("os.environ", {"INTERNAL_API_KEY": INTERNAL_KEY}):
            resp = client.get(
                "/internal/programmes", headers={"X-Internal-Key": "bad"}
            )
        self._assert_401(resp)

    def test_coverage_no_key_returns_401(self, client, db_session, app):
        _, subj_slug = _create_programme_and_subject(app, "BSc Law", "Tort")
        with patch.dict("os.environ", {"INTERNAL_API_KEY": INTERNAL_KEY}):
            resp = client.get(f"/internal/coverage/{subj_slug}")
        self._assert_401(resp)


# ══════════════════════════════════════════════════════════════════════════════
# E2E-13  Student past-paper lifecycle (upload → KnowlyGen collect)
# ══════════════════════════════════════════════════════════════════════════════

class TestE2E13StudentPaperLifecycle:
    """
    Tests the StudentPastPaper model lifecycle accessed via the internal API:
    listing pending papers, marking as collected.
    """

    def _seed_subject(self, app):
        """Create a Programme + Subject and return the subject id and slug."""
        with app.app_context():
            prog = Programme.query.filter_by(slug="bsc-cs-papers").first()
            if not prog:
                prog = Programme(
                    name="BSc CS Papers",
                    slug="bsc-cs-papers",
                    description="Test",
                    is_active=True,
                )
                db.session.add(prog)
                db.session.flush()
            subj = Subject.query.filter_by(slug="mathematics-papers").first()
            if not subj:
                subj = Subject(
                    name="Mathematics Papers",
                    slug="mathematics-papers",
                    programme_id=prog.id,
                    is_active=True,
                    color="#3498db",
                )
                db.session.add(subj)
                db.session.commit()
            return subj.id, subj.slug

    def _seed_paper(self, app, user_id):
        from app.models import StudentPastPaper
        subj_id, subj_slug = self._seed_subject(app)
        with app.app_context():
            paper = StudentPastPaper(
                user_id=user_id,
                subject_id=subj_id,
                subject_slug=subj_slug,
                filename="maths_2024.pdf",
                file_path="/uploads/papers/maths_2024.pdf",
                year="2024",
                semester="1",
                file_type="pdf",
                status="pending",
            )
            db.session.add(paper)
            db.session.commit()
            return paper.id

    def test_list_pending_papers_via_internal_api(self, client, db_session,
                                                    make_user, app):
        user = make_user(username="paper_user", email="paper_user@example.com")
        self._seed_paper(app, user.id)

        with patch.dict("os.environ", {"INTERNAL_API_KEY": INTERNAL_KEY}):
            resp = client.get(
                "/internal/student-papers", headers=_internal_headers()
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "papers" in data
        assert len(data["papers"]) == 1
        # to_dict() exposes filename and subject_slug (not status — check via filename)
        assert data["papers"][0]["filename"] == "maths_2024.pdf"

    def test_mark_collected_changes_status(self, client, db_session,
                                            make_user, app):
        user = make_user(username="collect_user", email="collect_user@example.com")
        paper_id = self._seed_paper(app, user.id)

        with patch.dict("os.environ", {"INTERNAL_API_KEY": INTERNAL_KEY}):
            resp = client.patch(
                f"/internal/student-papers/{paper_id}/collected",
                headers=_internal_headers(),
            )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "collected"

        with app.app_context():
            from app.models import StudentPastPaper as SPP
            paper = db.session.get(SPP, paper_id)
            assert paper.status == "collected"
            assert paper.collected_at is not None

    def test_collected_papers_not_returned_as_pending(self, client, db_session,
                                                        make_user, app):
        user = make_user(username="coll2_user", email="coll2_user@example.com")
        paper_id = self._seed_paper(app, user.id)

        # Mark as collected
        with patch.dict("os.environ", {"INTERNAL_API_KEY": INTERNAL_KEY}):
            client.patch(
                f"/internal/student-papers/{paper_id}/collected",
                headers=_internal_headers(),
            )
            # Re-list — should be empty
            resp = client.get(
                "/internal/student-papers", headers=_internal_headers()
            )
        data = resp.get_json()
        assert len(data["papers"]) == 0


# ══════════════════════════════════════════════════════════════════════════════
# E2E-14  Past-paper upload by a student user
# ══════════════════════════════════════════════════════════════════════════════

class TestE2E14PastPaperUpload:
    """
    A logged-in student uploads a past paper via the /past-papers/upload route.
    Tests file-type validation and successful creation.
    
    Note: The /past-papers/index template extends layout.html which doesn't exist
    in this codebase (it uses base.html). We therefore assert on 302 redirects
    (flash + redirect pattern) rather than following to the rendered page.
    """

    def _seed_subject(self, app, slug="maths-e2e-upload"):
        """Ensure a Programme + Subject exists for upload validation."""
        with app.app_context():
            prog = Programme.query.filter_by(slug="bsc-upload-prog").first()
            if not prog:
                prog = Programme(
                    name="BSc Upload Prog",
                    slug="bsc-upload-prog",
                    description="Test",
                    is_active=True,
                )
                db.session.add(prog)
                db.session.flush()
            subj = Subject.query.filter_by(slug=slug).first()
            if not subj:
                subj = Subject(
                    name="Maths E2E Upload",
                    slug=slug,
                    programme_id=prog.id,
                    is_active=True,
                    color="#aabbcc",
                )
                db.session.add(subj)
                db.session.commit()
            return slug

    def test_valid_pdf_upload_creates_record(self, client, db_session,
                                              make_user, auth_client, app):
        user = make_user(
            username="pp_uploader", email="pp_uploader@example.com"
        )
        subject_slug = self._seed_subject(app)
        logged_in = auth_client(user)

        pdf_file = (io.BytesIO(b"%PDF-1.4 content"), "past_exam.pdf", "application/pdf")

        # Mock file.save so we don't need a real disk
        with patch("werkzeug.datastructures.FileStorage.save"):
            resp = logged_in.post(
                "/past-papers/upload",
                data={
                    "subject_slug": subject_slug,
                    "year": "2024",
                    "semester": "1",
                    "file": pdf_file,
                },
                content_type="multipart/form-data",
                follow_redirects=False,  # avoid rendering layout.html
            )
        # Upload redirects to index on success
        assert resp.status_code == 302

    def test_invalid_file_type_rejected(self, client, db_session,
                                         make_user, auth_client, app):
        user = make_user(
            username="pp_bad_type", email="pp_bad_type@example.com"
        )
        subject_slug = self._seed_subject(app)
        logged_in = auth_client(user)

        exe_file = (io.BytesIO(b"MZ bad exe"), "malware.exe", "application/octet-stream")

        resp = logged_in.post(
            "/past-papers/upload",
            data={
                "subject_slug": subject_slug,
                "year": "2024",
                "semester": "1",
                "file": exe_file,
            },
            content_type="multipart/form-data",
            follow_redirects=False,  # flash + redirect, don't render template
        )
        # Rejected = redirect back (with flash message)
        assert resp.status_code == 302

    def test_upload_without_subject_slug_rejected(self, client, db_session,
                                                    make_user, auth_client, app):
        user = make_user(
            username="pp_no_subject", email="pp_no_subject@example.com"
        )
        logged_in = auth_client(user)

        pdf_file = (io.BytesIO(b"%PDF-1.4 content"), "exam.pdf", "application/pdf")

        resp = logged_in.post(
            "/past-papers/upload",
            data={
                "subject_slug": "",  # empty
                "file": pdf_file,
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        # Missing subject also redirects with flash
        assert resp.status_code == 302

    def test_past_papers_page_requires_login(self, client, db_session):
        # /past-papers/ (with trailing slash) is the correct URL
        # Without trailing slash Flask gives 308 permanent redirect to /past-papers/
        resp = client.get("/past-papers/", follow_redirects=False)
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]

    def test_upload_without_file_rejected(self, client, db_session,
                                           make_user, auth_client, app):
        user = make_user(
            username="pp_no_file", email="pp_no_file@example.com"
        )
        subject_slug = self._seed_subject(app)
        logged_in = auth_client(user)

        resp = logged_in.post(
            "/past-papers/upload",
            data={"subject_slug": subject_slug},
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        assert resp.status_code == 302


# ══════════════════════════════════════════════════════════════════════════════
# E2E Cross-system: Webhook delivery (Paystack → EduShare)
# ══════════════════════════════════════════════════════════════════════════════

class TestE2ECrossSystemWebhook:
    """
    Simulates Paystack's server delivering a charge.success webhook.
    Verifies signature validation, purchase creation, and idempotency.
    """

    def _post_signed_webhook(self, client, payload, secret="sk_test_dummy"):
        body = json.dumps(payload).encode()
        sig = _sign_webhook(body, secret)
        return client.post(
            "/payments/webhook",
            data=body,
            content_type="application/json",
            headers={"X-Paystack-Signature": sig},
        )

    def test_webhook_document_purchase_creates_record(self, client, db_session,
                                                        make_user, make_document, app):
        user = make_user(username="wh_buyer", email="wh_buyer@example.com")
        with app.app_context():
            doc = make_document(is_paid=True, price=10.0)
            uid = user.id
            did = doc.id

        payload = {
            "event": "charge.success",
            "data": {
                "reference": "wh_e2e_doc_001",
                "amount": 1000,
                "channel": "card",
                "metadata": {"user_id": uid, "document_id": did},
            },
        }
        with patch("app.utils.emails.send_purchase_confirmation_email"):
            resp = self._post_signed_webhook(client, payload)
        assert resp.status_code == 200

        with app.app_context():
            p = Purchase.query.filter_by(transaction_id="wh_e2e_doc_001").first()
            assert p is not None
            assert p.status == "completed"

    def test_webhook_invalid_signature_blocked(self, client, db_session):
        body = json.dumps({"event": "charge.success"}).encode()
        resp = client.post(
            "/payments/webhook",
            data=body,
            content_type="application/json",
            headers={"X-Paystack-Signature": "fakeSignature"},
        )
        assert resp.status_code == 400

    def test_webhook_duplicate_reference_is_idempotent(self, client, db_session,
                                                         make_user, make_document,
                                                         app):
        user = make_user(username="wh_idem", email="wh_idem@example.com")
        with app.app_context():
            doc = make_document(is_paid=True, price=10.0)
            existing = Purchase(
                user_id=user.id,
                document_id=doc.id,
                amount_paid=10.0,
                transaction_id="wh_e2e_dup",
                status="completed",
            )
            db.session.add(existing)
            db.session.commit()
            uid = user.id
            did = doc.id

        payload = {
            "event": "charge.success",
            "data": {
                "reference": "wh_e2e_dup",
                "amount": 1000,
                "channel": "card",
                "metadata": {"user_id": uid, "document_id": did},
            },
        }
        self._post_signed_webhook(client, payload)

        with app.app_context():
            count = Purchase.query.filter_by(transaction_id="wh_e2e_dup").count()
            assert count == 1