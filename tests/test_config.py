"""
tests/test_config.py
====================
Isolated configuration for the EduShare test suite.

Inherits from the production Config but overrides everything that would
require external services, real credentials, or persistent state.
"""

from config import Config


class TestConfig(Config):
    # ── Core test flags ───────────────────────────────────────────────────────
    TESTING = True
    DEBUG = False

    # ── In-memory database — fresh slate for every test session ──────────────
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

    # ── Disable CSRF so test client POST requests are not rejected ────────────
    WTF_CSRF_ENABLED = False
    WTF_CSRF_CHECK_DEFAULT = False

    # ── Disable rate limiting so tests don't hit 429s ────────────────────────
    RATELIMIT_ENABLED = False

    # ── Cloudinary — empty cloud name so _is_local() returns True in tests ──
    # _is_local() checks: not bool(config.get('CLOUDINARY_CLOUD_NAME'))
    # An empty string is falsy, so all file ops use the local filesystem path.
    CLOUDINARY_CLOUD_NAME = ''
    CLOUDINARY_API_KEY = 'test_api_key'
    CLOUDINARY_API_SECRET = 'test_api_secret'

    # ── Paystack — dummy values, no real calls made ───────────────────────────
    PAYSTACK_PUBLIC_KEY = 'pk_test_dummy'
    PAYSTACK_SECRET_KEY = 'sk_test_dummy'

    # ── Email — suppress all outgoing email ───────────────────────────────────
    MAIL_SUPPRESS_SEND = True
    MAIL_DEFAULT_SENDER = 'test@test.com'

    # ── Secret key — fixed value for deterministic session tokens ─────────────
    SECRET_KEY = 'test-secret-key-not-for-production'

    # ── Faster password hashing in tests ──────────────────────────────────────
    BCRYPT_LOG_ROUNDS = 4