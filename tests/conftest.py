"""
tests/conftest.py
=================
Shared pytest fixtures for the EduShare test suite.

Provides:
  - app         : Flask app configured for testing (one per session)
  - db_session  : Clean database for every test (tables wiped between tests)
  - client      : Flask test client (unauthenticated)
  - auth_client : Helper to log in as a specific user
  - make_user   : Factory to create User rows
  - make_post   : Factory to create Post rows
  - make_document : Factory to create Document rows

Run from the edushare/ root:
    pytest tests/ -v
"""

import json
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from app import create_app, db as _db
from app.models import (
    User, Post, Document, Purchase, Subscription, QuizData
)
from tests.test_config import TestConfig


# ══════════════════════════════════════════════════════════════════════════════
# App + DB fixtures
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope='session')
def app():
    """
    Create the Flask application once for the entire test session.
    Cloudinary and Flask-Dance (Google OAuth) are patched out so they
    never make real network calls.
    """
    from unittest.mock import MagicMock
    with patch.dict('sys.modules', {
        'cloudinary.uploader': MagicMock(),
        'cloudinary.api':      MagicMock(),
    }):
        _app = create_app(TestConfig)

    _app.config['TESTING'] = True
    return _app


@pytest.fixture(scope='function')
def db_session(app):
    """
    Provide a clean database for every single test.

    Creates all tables before the test, drops them after.
    This guarantees complete isolation — no test can pollute another.
    """
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope='function')
def client(app, db_session):
    """
    Unauthenticated Flask test client.
    Use this for testing public routes (login page, signup page, etc.)
    """
    with app.test_client() as c:
        yield c


# ══════════════════════════════════════════════════════════════════════════════
# Model factories
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope='function')
def make_user(db_session, app):
    """
    Factory fixture: creates and persists a User row.

    Usage:
        user = make_user()                          # default test user
        admin = make_user(username='admin', is_admin=True)
        premium = make_user(username='vip', subscription_tier='premium')
    """
    created = []

    def _make_user(
        username='testuser',
        email='test@example.com',
        password='Password123!',
        full_name='Test User',
        is_admin=False,
        subscription_tier='free',
        free_quiz_attempts=3,
        can_access_all_content=False,
    ):
        with app.app_context():
            user = User(
                username=username,
                email=email,
                full_name=full_name,
                is_admin=is_admin,
                subscription_tier=subscription_tier,
                free_quiz_attempts=free_quiz_attempts,
                can_access_all_content=can_access_all_content,
            )
            user.set_password(password)
            _db.session.add(user)
            _db.session.commit()
            _db.session.refresh(user)
            _db.session.expunge(user)
            created.append(user.id)
            return user

    return _make_user


@pytest.fixture(scope='function')
def make_post(db_session, app):
    """
    Factory fixture: creates and persists a Post row.

    Usage:
        post = make_post(user_id=user.id, title='My Notes')
    """
    def _make_post(
        user_id,
        title='Test Post',
        description='Test description',
        content_type='notes',
        status='approved',
    ):
        with app.app_context():
            post = Post(
                user_id=user_id,
                title=title,
                description=description,
                content_type=content_type,
                status=status,
            )
            _db.session.add(post)
            _db.session.commit()
            _db.session.refresh(post)
            _db.session.expunge(post)
            return post

    return _make_post


@pytest.fixture(scope='function')
def make_document(db_session, app):
    """
    Factory fixture: creates and persists a Document row.

    Usage:
        doc = make_document()                        # free document
        paid_doc = make_document(is_paid=True, price=10.0)
    """
    def _make_document(
        filename='test.pdf',
        original_filename='test.pdf',
        file_path='/uploads/test.pdf',
        file_type='pdf',
        is_paid=False,
        price=0.0,
    ):
        with app.app_context():
            doc = Document(
                filename=filename,
                original_filename=original_filename,
                file_path=file_path,
                file_type=file_type,
                is_paid=is_paid,
                price=price,
            )
            _db.session.add(doc)
            _db.session.commit()
            _db.session.refresh(doc)
            _db.session.expunge(doc)
            return doc

    return _make_document


@pytest.fixture(scope='function')
def make_quiz(db_session, app):
    """
    Factory fixture: creates a QuizData row linked to a post.

    Generates a minimal valid quiz with 1 MCQ question worth 2 marks.

    Usage:
        quiz = make_quiz(post_id=post.id)
        quiz = make_quiz(post_id=post.id, total_marks=10)
    """
    def _make_quiz(post_id, total_marks=2, xp_reward=10):
        with app.app_context():
            questions = [
                {
                    "question_number": 1,
                    "question_text": "What is 2 + 2?",
                    "type": "mcq",
                    "marks": total_marks,
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
                post_id=post_id,
                questions=json.dumps(questions),
                total_marks=total_marks,
                xp_reward=xp_reward,
                meta=json.dumps({"time_minutes": 30}),
            )
            _db.session.add(quiz)
            _db.session.commit()
            _db.session.refresh(quiz)
            _db.session.expunge(quiz)
            return quiz

    return _make_quiz


@pytest.fixture(scope='function')
def make_subscription(db_session, app):
    """
    Factory fixture: creates an active Subscription row for a user.

    Usage:
        sub = make_subscription(user_id=user.id)
        expired = make_subscription(user_id=user.id, expired=True)
    """
    def _make_subscription(user_id, plan_key='monthly_unlimited', expired=False):
        with app.app_context():
            now = datetime.now(timezone.utc)
            expires_at = now - timedelta(days=1) if expired else now + timedelta(days=30)
            sub = Subscription(
                user_id=user_id,
                plan_key=plan_key,
                plan_name='Monthly Unlimited',
                amount_paid=20.0,
                currency='GHS',
                payment_method='card',
                transaction_id=f'test_txn_{user_id}_{plan_key}',
                status='active',
                started_at=now,
                expires_at=expires_at,
            )
            _db.session.add(sub)
            _db.session.commit()
            return sub

    return _make_subscription


# ══════════════════════════════════════════════════════════════════════════════
# Auth helper
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope='function')
def auth_client(client, app):
    """
    Helper fixture: returns a function that logs in a user and returns
    the test client with an active session.

    Usage:
        logged_in = auth_client(user)
        response = logged_in.get('/some/protected/route')
    """
    def _login(user, password='Password123!'):
        client.post('/auth/login', data={
            'username': user.username,
            'password': password,
        }, follow_redirects=True)
        return client

    return _login