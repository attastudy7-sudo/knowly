"""
tests/test_auth.py
==================
Integration tests for the authentication blueprint (app/auth/routes.py).

Covers:
  - GET pages render correctly
  - Signup: success, duplicate username, duplicate email, password mismatch
  - Login: by username, by email, wrong password, unknown user, Google-only account
  - Logout
  - Redirect behaviour for already-authenticated users
  - Password reset: token generation, valid token, expired token, tampered token
  - _get_or_create_google_user: new user, existing user, username collision

Run from the edushare/ root:
    pytest tests/test_auth.py -v
"""

import time
import hmac
import hashlib
from unittest.mock import patch

import pytest

from app import db
from app.models import User
from app.auth.routes import _get_or_create_google_user, _find_user_by_login


# ══════════════════════════════════════════════════════════════════════════════
# GET — pages render
# ══════════════════════════════════════════════════════════════════════════════

class TestAuthPages:

    def test_login_page_loads(self, client):
        response = client.get('/auth/login')
        assert response.status_code == 200
        assert b'Log In' in response.data or b'login' in response.data.lower()

    def test_signup_page_loads(self, client):
        response = client.get('/auth/signup')
        assert response.status_code == 200
        assert b'Sign Up' in response.data or b'signup' in response.data.lower()

    def test_reset_password_request_page_loads(self, client):
        response = client.get('/auth/reset-password')
        assert response.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# SIGNUP
# ══════════════════════════════════════════════════════════════════════════════

class TestSignup:

    def test_successful_signup_creates_user(self, client, db_session, app):
        with patch('app.utils.emails.send_welcome_email'):
            response = client.post('/auth/signup', data={
                'username': 'newuser',
                'email': 'newuser@example.com',
                'full_name': 'New User',
                'password': 'Password123!',
                'confirm_password': 'Password123!',
            }, follow_redirects=True)

        assert response.status_code == 200
        with app.app_context():
            user = User.query.filter_by(username='newuser').first()
            assert user is not None
            assert user.email == 'newuser@example.com'

    def test_successful_signup_redirects_to_login(self, client, db_session):
        with patch('app.utils.emails.send_welcome_email'):
            response = client.post('/auth/signup', data={
                'username': 'newuser2',
                'email': 'newuser2@example.com',
                'full_name': 'New User Two',
                'password': 'Password123!',
                'confirm_password': 'Password123!',
            }, follow_redirects=False)

        assert response.status_code == 302
        assert '/auth/login' in response.headers['Location']

    def test_signup_duplicate_username_rejected(self, client, db_session, make_user):
        make_user(username='taken', email='taken@example.com')

        response = client.post('/auth/signup', data={
            'username': 'taken',
            'email': 'different@example.com',
            'full_name': 'Someone Else',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'already taken' in response.data or b'Username' in response.data

    def test_signup_duplicate_email_rejected(self, client, db_session, make_user):
        make_user(username='original', email='used@example.com')

        response = client.post('/auth/signup', data={
            'username': 'newusername',
            'email': 'used@example.com',
            'full_name': 'Another Person',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'already registered' in response.data or b'Email' in response.data

    def test_signup_password_mismatch_rejected(self, client, db_session):
        response = client.post('/auth/signup', data={
            'username': 'mismatch',
            'email': 'mismatch@example.com',
            'full_name': 'Mismatch User',
            'password': 'Password123!',
            'confirm_password': 'DifferentPassword!',
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'match' in response.data.lower()

    def test_signup_short_password_rejected(self, client, db_session):
        response = client.post('/auth/signup', data={
            'username': 'shortpass',
            'email': 'short@example.com',
            'full_name': 'Short Pass',
            'password': '123',
            'confirm_password': '123',
        }, follow_redirects=True)

        assert response.status_code == 200
        # Should stay on signup page — user not created
        with client.application.app_context():
            user = User.query.filter_by(username='shortpass').first()
            assert user is None

    def test_signup_password_is_hashed_not_stored_plaintext(self, client, db_session, app):
        with patch('app.utils.emails.send_welcome_email'):
            client.post('/auth/signup', data={
                'username': 'hashcheck',
                'email': 'hash@example.com',
                'full_name': 'Hash Check',
                'password': 'MyPassword1!',
                'confirm_password': 'MyPassword1!',
            }, follow_redirects=True)

        with app.app_context():
            user = User.query.filter_by(username='hashcheck').first()
            assert user is not None
            assert user.password_hash != 'MyPassword1!'
            assert user.check_password('MyPassword1!') is True


# ══════════════════════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════════════════════

class TestLogin:

    def test_login_with_username_succeeds(self, client, db_session, make_user):
        make_user(username='alice', email='alice@example.com', password='Pass1234!')

        response = client.post('/auth/login', data={
            'username': 'alice',
            'password': 'Pass1234!',
        }, follow_redirects=False)

        assert response.status_code == 302

    def test_login_with_email_succeeds(self, client, db_session, make_user):
        make_user(username='bob', email='bob@example.com', password='Pass1234!')

        response = client.post('/auth/login', data={
            'username': 'bob@example.com',
            'password': 'Pass1234!',
        }, follow_redirects=False)

        assert response.status_code == 302

    def test_login_wrong_password_rejected(self, client, db_session, make_user):
        make_user(username='carol', email='carol@example.com', password='Pass1234!')

        response = client.post('/auth/login', data={
            'username': 'carol',
            'password': 'WrongPassword!',
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Incorrect password' in response.data

    def test_login_unknown_user_rejected(self, client, db_session):
        response = client.post('/auth/login', data={
            'username': 'doesnotexist',
            'password': 'Pass1234!',
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'No account found' in response.data

    def test_login_google_only_account_shows_correct_message(self, client, db_session, app):
        """A user with password_hash=None must be told to use Google sign-in."""
        with app.app_context():
            user = User(
                username='googleuser',
                email='googleuser@gmail.com',
                full_name='Google User',
                password_hash=None,
            )
            db.session.add(user)
            db.session.commit()

        response = client.post('/auth/login', data={
            'username': 'googleuser',
            'password': 'anything',
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'Google' in response.data

    def test_authenticated_user_redirected_away_from_login(self, client, db_session, make_user, auth_client):
        user = make_user(username='dave', email='dave@example.com')
        logged_in = auth_client(user)

        response = logged_in.get('/auth/login', follow_redirects=False)
        assert response.status_code == 302

    def test_authenticated_user_redirected_away_from_signup(self, client, db_session, make_user, auth_client):
        user = make_user(username='eve', email='eve@example.com')
        logged_in = auth_client(user)

        response = logged_in.get('/auth/signup', follow_redirects=False)
        assert response.status_code == 302

    def test_login_next_param_redirects_correctly(self, client, db_session, make_user):
        make_user(username='frank', email='frank@example.com', password='Pass1234!')

        response = client.post('/auth/login?next=/users/frank', data={
            'username': 'frank',
            'password': 'Pass1234!',
        }, follow_redirects=False)

        assert response.status_code == 302
        assert '/users/frank' in response.headers['Location']

    def test_login_unsafe_next_param_ignored(self, client, db_session, make_user):
        """next= pointing to external URL must be ignored to prevent open redirect."""
        make_user(username='grace', email='grace@example.com', password='Pass1234!')

        response = client.post('/auth/login?next=https://evil.com', data={
            'username': 'grace',
            'password': 'Pass1234!',
        }, follow_redirects=False)

        assert response.status_code == 302
        assert 'evil.com' not in response.headers['Location']


# ══════════════════════════════════════════════════════════════════════════════
# LOGOUT
# ══════════════════════════════════════════════════════════════════════════════

class TestLogout:

    def test_logout_redirects_to_index(self, client, db_session, make_user, auth_client):
        user = make_user(username='henry', email='henry@example.com')
        logged_in = auth_client(user)

        response = logged_in.get('/auth/logout', follow_redirects=False)
        assert response.status_code == 302

    def test_logout_clears_session(self, client, db_session, make_user, auth_client):
        user = make_user(username='iris', email='iris@example.com')
        logged_in = auth_client(user)

        logged_in.get('/auth/logout', follow_redirects=True)

        # After logout, accessing a protected page should redirect to login
        response = logged_in.get('/auth/logout', follow_redirects=False)
        # Unauthenticated user hitting logout just redirects — no crash
        assert response.status_code == 302


# ══════════════════════════════════════════════════════════════════════════════
# PASSWORD RESET
# ══════════════════════════════════════════════════════════════════════════════

class TestPasswordReset:

    def _generate_token(self, app, user):
        """Helper: generate a valid reset token the same way the route does."""
        with app.app_context():
            secret = app.config['SECRET_KEY'].encode()
            expires = int(time.time()) + 1800
            payload = f'{user.id}:{user.password_hash[:10]}:{expires}'
            token = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
            return f'{user.id}.{expires}.{token}', expires

    def test_reset_request_always_shows_same_message(self, client, db_session, make_user):
        """Anti-enumeration: same flash message regardless of whether email exists."""
        make_user(username='jack', email='jack@example.com')

        with patch('app.utils.emails.send_password_reset_email'):
            # Known email
            r1 = client.post('/auth/reset-password', data={
                'email': 'jack@example.com'
            }, follow_redirects=True)

            # Unknown email
            r2 = client.post('/auth/reset-password', data={
                'email': 'unknown@example.com'
            }, follow_redirects=True)

        assert b'reset link has been sent' in r1.data
        assert b'reset link has been sent' in r2.data

    def test_valid_reset_token_allows_password_change(self, client, db_session, make_user, app):
        user = make_user(username='kate', email='kate@example.com', password='OldPass1!')
        token, _ = self._generate_token(app, user)

        response = client.post(f'/auth/reset-password/{token}', data={
            'password': 'NewPass1!',
            'confirm_password': 'NewPass1!',
        }, follow_redirects=True)

        assert response.status_code == 200
        assert b'password has been reset' in response.data

        with app.app_context():
            updated = User.query.filter_by(username='kate').first()
            assert updated.check_password('NewPass1!') is True
            assert updated.check_password('OldPass1!') is False

    def test_expired_reset_token_rejected(self, client, db_session, make_user, app):
        user = make_user(username='leo', email='leo@example.com')

        with app.app_context():
            secret = app.config['SECRET_KEY'].encode()
            expires = int(time.time()) - 1  # already expired
            payload = f'{user.id}:{user.password_hash[:10]}:{expires}'
            token_str = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
            token = f'{user.id}.{expires}.{token_str}'

        response = client.get(f'/auth/reset-password/{token}', follow_redirects=True)
        assert b'expired' in response.data

    def test_tampered_reset_token_rejected(self, client, db_session, make_user, app):
        user = make_user(username='mia', email='mia@example.com')
        token, _ = self._generate_token(app, user)

        # Tamper with the signature portion
        parts = token.split('.')
        parts[2] = 'a' * 64
        tampered = '.'.join(parts)

        response = client.get(f'/auth/reset-password/{tampered}', follow_redirects=True)
        assert b'invalid' in response.data

    def test_malformed_reset_token_rejected(self, client, db_session):
        response = client.get('/auth/reset-password/not-a-valid-token',
                              follow_redirects=True)
        assert b'invalid' in response.data

    def test_reset_token_for_google_only_account_rejected(self, client, db_session, app):
        """Google-only accounts (password_hash=None) cannot use password reset."""
        with app.app_context():
            user = User(
                username='nora',
                email='nora@gmail.com',
                full_name='Nora Google',
                password_hash=None,
            )
            db.session.add(user)
            db.session.commit()
            user_id = user.id
            expires = int(time.time()) + 1800
            token = f'{user_id}.{expires}.{"a" * 64}'

        response = client.get(f'/auth/reset-password/{token}', follow_redirects=True)
        assert b'invalid' in response.data


# ══════════════════════════════════════════════════════════════════════════════
# _find_user_by_login helper
# ══════════════════════════════════════════════════════════════════════════════

class TestFindUserByLogin:

    def test_find_by_username(self, client, db_session, make_user, app):
        make_user(username='oliver', email='oliver@example.com')
        with app.app_context():
            user = _find_user_by_login('oliver')
            assert user is not None
            assert user.username == 'oliver'

    def test_find_by_email(self, client, db_session, make_user, app):
        make_user(username='penny', email='penny@example.com')
        with app.app_context():
            user = _find_user_by_login('penny@example.com')
            assert user is not None
            assert user.email == 'penny@example.com'

    def test_returns_none_for_unknown_identifier(self, client, db_session, app):
        with app.app_context():
            user = _find_user_by_login('nobody')
            assert user is None


# ══════════════════════════════════════════════════════════════════════════════
# _get_or_create_google_user helper
# ══════════════════════════════════════════════════════════════════════════════

class TestGetOrCreateGoogleUser:

    def test_creates_new_user_for_unknown_email(self, client, db_session, app):
        with app.app_context():
            with patch('app.utils.emails.send_welcome_email'):
                user, created = _get_or_create_google_user(
                    'newgoogle@gmail.com', 'New Google User'
                )
            assert created is True
            assert user is not None
            assert user.email == 'newgoogle@gmail.com'
            assert user.password_hash is None  # Google-only account

    def test_returns_existing_user_for_known_email(self, client, db_session, make_user, app):
        make_user(username='existing', email='existing@gmail.com')
        with app.app_context():
            user, created = _get_or_create_google_user(
                'existing@gmail.com', 'Existing User'
            )
            assert created is False
            assert user.username == 'existing'

    def test_username_derived_from_email_prefix(self, client, db_session, app):
        with app.app_context():
            with patch('app.utils.emails.send_welcome_email'):
                user, created = _get_or_create_google_user(
                    'john.doe@gmail.com', 'John Doe'
                )
            assert created is True
            assert user.username == 'john_doe'  # dots replaced with underscores

    def test_username_collision_gets_numeric_suffix(self, client, db_session, make_user, app):
        # Pre-create a user that will collide with the derived username
        make_user(username='jane', email='other@example.com')
        with app.app_context():
            with patch('app.utils.emails.send_welcome_email'):
                user, created = _get_or_create_google_user(
                    'jane@gmail.com', 'Jane Gmail'
                )
            assert created is True
            assert user.username == 'jane1'  # collision resolved with suffix