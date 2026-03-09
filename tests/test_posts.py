"""
tests/test_posts.py — Post CRUD, document access control, social actions,
                       download/preview, proxy token, and comment tests.
"""
import io
import time
import hashlib
import hmac

import pytest
from app import db
from app.models import User, Post, Document, Like, Bookmark, Comment, Purchase


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fake_pdf():
    """Return a minimal in-memory PDF-like file object."""
    return (io.BytesIO(b'%PDF-1.4 fake content'), 'test.pdf', 'application/pdf')


def _default_user(make_user):
    """Create and return the default test user."""
    return make_user(username='postuser', email='postuser@test.com')


def _create_post_via_form(client, title='Test Post', description='A description',
                          with_file=True, content_type='notes'):
    """POST to /posts/create and return the response."""
    data = {
        'title':        title,
        'description':  description,
        'content_type': content_type,
        'subject':      '0',
        'is_paid':      False,
        'price':        '',
    }
    if with_file:
        data['document'] = _fake_pdf()
    return client.post(
        '/posts/create',
        data=data,
        content_type='multipart/form-data',
        follow_redirects=True,
    )


# ── Test classes ───────────────────────────────────────────────────────────────

class TestPostCreate:
    """POST /posts/create"""

    def test_create_page_requires_login(self, client, app):
        with app.app_context():
            resp = client.get('/posts/create', follow_redirects=False)
            assert resp.status_code in (302, 401)

    def test_create_page_renders_for_authenticated_user(self, auth_client, make_user, app):
        with app.app_context():
            user = _default_user(make_user)
            c = auth_client(user)
            resp = c.get('/posts/create')
            assert resp.status_code == 200
            assert b'Create' in resp.data

    def test_create_post_without_file_succeeds(self, auth_client, make_user, app):
        with app.app_context():
            user = _default_user(make_user)
            c = auth_client(user)
            resp = _create_post_via_form(c, with_file=False)
            assert resp.status_code == 200
            post = Post.query.filter_by(title='Test Post').first()
            assert post is not None
            assert post.status == 'pending'

    def test_create_post_with_pdf_attaches_document(self, auth_client, make_user, app):
        with app.app_context():
            user = _default_user(make_user)
            c = auth_client(user)
            resp = _create_post_via_form(c, title='With Doc', with_file=True)
            assert resp.status_code == 200
            post = Post.query.filter_by(title='With Doc').first()
            assert post is not None
            assert post.has_document is True
            assert post.document is not None

    def test_create_post_status_is_pending(self, auth_client, make_user, app):
        with app.app_context():
            user = _default_user(make_user)
            c = auth_client(user)
            _create_post_via_form(c, title='Pending Post', with_file=False)
            post = Post.query.filter_by(title='Pending Post').first()
            assert post.status == 'pending'

    def test_create_post_invalid_file_type_rejected(self, auth_client, make_user, app):
        with app.app_context():
            user = _default_user(make_user)
            c = auth_client(user)
            bad_file = (io.BytesIO(b'<?php echo 1; ?>'), 'evil.php', 'application/x-php')
            resp = c.post(
                '/posts/create',
                data={
                    'title':       'Bad File',
                    'description': 'desc',
                    'subject':     '0',
                    'document':    bad_file,
                },
                content_type='multipart/form-data',
                follow_redirects=True,
            )
            assert resp.status_code == 200
            post = Post.query.filter_by(title='Bad File').first()
            if post:
                assert not post.has_document


class TestPostView:
    """GET /posts/<id>"""

    def test_view_approved_post_public(self, client, make_user, make_post, app):
        with app.app_context():
            user = make_user(username='view_author', email='view_author@test.com')
            post = make_post(user_id=user.id, status='approved')
            resp = client.get(f'/posts/{post.id}')
            assert resp.status_code == 200

    def test_view_pending_post_by_author_allowed(self, auth_client, make_user, make_post, app):
        with app.app_context():
            user = make_user(username='pending_author', email='pending_author@test.com')
            post = make_post(user_id=user.id, status='pending')
            c = auth_client(user)
            resp = c.get(f'/posts/{post.id}')
            assert resp.status_code == 200

    def test_view_pending_post_by_stranger_redirects(self, client, make_user, make_post, app):
        with app.app_context():
            owner = make_user(username='pend_owner', email='pend_owner@test.com')
            post = make_post(user_id=owner.id, status='pending')
            resp = client.get(f'/posts/{post.id}', follow_redirects=False)
            assert resp.status_code == 302

    def test_view_nonexistent_post_404(self, client, app):
        with app.app_context():
            resp = client.get('/posts/999999')
            assert resp.status_code == 404


class TestPostEdit:
    """GET/POST /posts/<id>/edit"""

    def test_edit_page_requires_login(self, client, make_user, make_post, app):
        with app.app_context():
            owner = make_user(username='edit_owner', email='edit_owner@test.com')
            post = make_post(user_id=owner.id, status='approved')
            resp = client.get(f'/posts/{post.id}/edit', follow_redirects=False)
            assert resp.status_code == 302

    def test_edit_page_denied_to_non_author(self, auth_client, make_user, make_post, app):
        with app.app_context():
            owner = make_user(username='real_author', email='real_author@test.com')
            stranger = make_user(username='stranger_ed', email='stranger_ed@test.com')
            post = make_post(user_id=owner.id, status='approved')
            c = auth_client(stranger)
            resp = c.get(f'/posts/{post.id}/edit', follow_redirects=True)
            assert b'cannot edit' in resp.data.lower() or resp.status_code in (302, 403)

    def test_edit_updates_title(self, auth_client, make_user, make_post, app):
        with app.app_context():
            user = make_user(username='edit_me', email='edit_me@test.com')
            post = make_post(user_id=user.id, status='approved', title='Old Title')
            c = auth_client(user)
            resp = c.post(
                f'/posts/{post.id}/edit',
                data={
                    'title':       'New Title',
                    'description': 'Updated desc',
                    'subject':     '0',
                    'is_paid':     False,
                    'price':       '',
                },
                content_type='multipart/form-data',
                follow_redirects=True,
            )
            assert resp.status_code == 200
            updated = db.session.get(Post, post.id)
            assert updated.title == 'New Title'

    def test_edit_with_new_file_resets_status_to_pending(self, auth_client, make_user, make_post, app):
        with app.app_context():
            user = make_user(username='edit_file', email='edit_file@test.com')
            post = make_post(user_id=user.id, status='approved', title='Approved Post')
            c = auth_client(user)
            resp = c.post(
                f'/posts/{post.id}/edit',
                data={
                    'title':       'Approved Post',
                    'description': 'desc',
                    'subject':     '0',
                    'is_paid':     False,
                    'price':       '',
                    'document':    _fake_pdf(),
                },
                content_type='multipart/form-data',
                follow_redirects=True,
            )
            assert resp.status_code == 200
            updated = db.session.get(Post, post.id)
            assert updated.status == 'pending'


class TestPostDelete:
    """POST /posts/<id>/delete"""

    def test_delete_requires_login(self, client, make_user, make_post, app):
        with app.app_context():
            owner = make_user(username='del_owner', email='del_owner@test.com')
            post = make_post(user_id=owner.id)
            resp = client.post(f'/posts/{post.id}/delete', follow_redirects=False)
            assert resp.status_code == 302

    def test_delete_denied_to_non_author(self, auth_client, make_user, make_post, app):
        with app.app_context():
            owner = make_user(username='del_owner2', email='del_owner2@test.com')
            stranger = make_user(username='del_stranger', email='del_stranger@test.com')
            post = make_post(user_id=owner.id)
            c = auth_client(stranger)
            resp = c.post(f'/posts/{post.id}/delete', follow_redirects=True)
            assert b'cannot delete' in resp.data.lower()
            assert db.session.get(Post, post.id) is not None

    def test_delete_by_author_removes_post(self, auth_client, make_user, make_post, app):
        with app.app_context():
            user = make_user(username='del_author', email='del_author@test.com')
            post = make_post(user_id=user.id, status='approved')
            post_id = post.id
            c = auth_client(user)
            resp = c.post(f'/posts/{post_id}/delete', follow_redirects=True)
            assert resp.status_code == 200
            assert db.session.get(Post, post_id) is None


class TestDocumentAccess:
    """Document has_access logic + download/preview gates."""

    def test_free_document_accessible_to_all(self, make_document, make_user, app):
        with app.app_context():
            doc = make_document(is_paid=False)
            user = make_user(username='free_user', email='free_user@test.com')
            assert doc.has_access(user) is True

    def test_paid_document_denied_without_purchase(self, make_document, make_user, app):
        with app.app_context():
            doc = make_document(is_paid=True, price=5.0)
            user = make_user(username='broke_user', email='broke_user@test.com')
            assert doc.has_access(user) is False

    def test_paid_document_accessible_after_purchase(self, make_document, make_user, db_session, app):
        with app.app_context():
            from app import db as _db
            doc = make_document(is_paid=True, price=5.0)
            user = make_user(username='buyer_user', email='buyer_user@test.com')
            purchase = Purchase(
                user_id=user.id,
                document_id=doc.id,
                amount_paid=5.0,
                payment_method='card',
                transaction_id='test_ref_access',
                status='completed',
            )
            _db.session.add(purchase)
            _db.session.commit()
            assert doc.has_access(user) is True

    def test_admin_can_access_paid_document(self, make_document, make_user, app):
        with app.app_context():
            doc = make_document(is_paid=True, price=5.0)
            admin = make_user(username='admin_access', email='admin_access@test.com', is_admin=True)
            assert doc.has_access(admin) is True

    def test_download_requires_login(self, client, make_document, app):
        with app.app_context():
            doc = make_document(is_paid=False)
            resp = client.get(f'/posts/document/{doc.id}/download', follow_redirects=False)
            assert resp.status_code == 302

    def test_download_paid_doc_without_purchase_redirects_to_checkout(
        self, auth_client, make_user, make_document, app
    ):
        with app.app_context():
            user = make_user(username='dl_user', email='dl_user@test.com')
            doc = make_document(is_paid=True, price=5.0)
            c = auth_client(user)
            resp = c.get(f'/posts/document/{doc.id}/download', follow_redirects=False)
            assert resp.status_code == 302
            assert 'checkout' in resp.headers['Location'].lower()

    def test_preview_denied_for_paid_doc_without_purchase(
        self, auth_client, make_user, make_document, app
    ):
        with app.app_context():
            user = make_user(username='prev_user', email='prev_user@test.com')
            doc = make_document(is_paid=True, price=5.0)
            c = auth_client(user)
            resp = c.get(f'/posts/document/{doc.id}/preview')
            assert resp.status_code == 403

    def test_preview_local_pdf_returns_local_type(self, auth_client, make_user, make_document, app):
        with app.app_context():
            user = make_user(username='prev_pdf_user', email='prev_pdf_user@test.com')
            doc = make_document(is_paid=False, file_type='pdf')
            c = auth_client(user)
            resp = c.get(f'/posts/document/{doc.id}/preview')
            assert resp.status_code == 200
            data = resp.get_json()
            assert data['type'] == 'local'

    def test_preview_non_previewable_type_returns_400(self, auth_client, make_user, make_document, app):
        with app.app_context():
            user = make_user(username='prev_txt_user', email='prev_txt_user@test.com')
            # txt is NOT in the previewable set
            doc = make_document(is_paid=False, file_type='txt')
            c = auth_client(user)
            resp = c.get(f'/posts/document/{doc.id}/preview')
            assert resp.status_code == 400


class TestProxyDocument:
    """GET /posts/document/<id>/proxy — HMAC token validation."""

    def _make_token(self, document_id, expires, secret='test-secret-key-not-for-production'):
        return hmac.new(
            secret.encode(),
            f'{document_id}:{expires}'.encode(),
            hashlib.sha256,
        ).hexdigest()

    def test_proxy_rejects_expired_token(self, make_document, app):
        with app.app_context():
            doc = make_document(is_paid=False)
            expires = int(time.time()) - 10
            token = self._make_token(doc.id, expires)
            with app.test_client() as c:
                resp = c.get(
                    f'/posts/document/{doc.id}/proxy?token={token}&expires={expires}'
                )
                assert resp.status_code == 410

    def test_proxy_rejects_tampered_token(self, make_document, app):
        with app.app_context():
            doc = make_document(is_paid=False)
            expires = int(time.time()) + 300
            with app.test_client() as c:
                resp = c.get(
                    f'/posts/document/{doc.id}/proxy?token=deadbeef&expires={expires}'
                )
                assert resp.status_code == 403

    def test_proxy_rejects_bad_expires(self, make_document, app):
        with app.app_context():
            doc = make_document(is_paid=False)
            with app.test_client() as c:
                resp = c.get(
                    f'/posts/document/{doc.id}/proxy?token=abc&expires=notanumber'
                )
                assert resp.status_code == 400


class TestSocialActions:
    """Like, bookmark, and comment routes."""

    def test_like_post_creates_like(self, auth_client, make_user, make_post, app):
        with app.app_context():
            user = make_user(username='liker', email='liker@test.com')
            post = make_post(user_id=user.id, status='approved')
            c = auth_client(user)
            resp = c.post(f'/posts/{post.id}/like', follow_redirects=True)
            assert resp.status_code == 200
            assert Like.query.filter_by(post_id=post.id).count() == 1

    def test_like_post_twice_toggles_off(self, auth_client, make_user, make_post, app):
        with app.app_context():
            user = make_user(username='toggle_liker', email='toggle_liker@test.com')
            post = make_post(user_id=user.id, status='approved')
            c = auth_client(user)
            c.post(f'/posts/{post.id}/like')
            c.post(f'/posts/{post.id}/like')
            assert Like.query.filter_by(post_id=post.id).count() == 0

    def test_like_returns_json_for_ajax(self, auth_client, make_user, make_post, app):
        with app.app_context():
            user = make_user(username='ajax_liker', email='ajax_liker@test.com')
            post = make_post(user_id=user.id, status='approved')
            c = auth_client(user)
            resp = c.post(
                f'/posts/{post.id}/like',
                headers={'X-Requested-With': 'XMLHttpRequest'},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert 'liked' in data
            assert 'like_count' in data

    def test_like_requires_login(self, client, make_user, make_post, app):
        with app.app_context():
            user = make_user(username='like_owner', email='like_owner@test.com')
            post = make_post(user_id=user.id, status='approved')
            resp = client.post(f'/posts/{post.id}/like', follow_redirects=False)
            assert resp.status_code == 302

    def test_bookmark_post_creates_bookmark(self, auth_client, make_user, make_post, app):
        with app.app_context():
            user = make_user(username='bookmarker', email='bookmarker@test.com')
            post = make_post(user_id=user.id, status='approved')
            c = auth_client(user)
            resp = c.post(f'/posts/{post.id}/bookmark', follow_redirects=True)
            assert resp.status_code == 200
            assert Bookmark.query.filter_by(post_id=post.id).count() == 1

    def test_bookmark_post_twice_toggles_off(self, auth_client, make_user, make_post, app):
        with app.app_context():
            user = make_user(username='toggle_bm', email='toggle_bm@test.com')
            post = make_post(user_id=user.id, status='approved')
            c = auth_client(user)
            c.post(f'/posts/{post.id}/bookmark')
            c.post(f'/posts/{post.id}/bookmark')
            assert Bookmark.query.filter_by(post_id=post.id).count() == 0

    def test_bookmark_returns_json_for_ajax(self, auth_client, make_user, make_post, app):
        with app.app_context():
            user = make_user(username='ajax_bm', email='ajax_bm@test.com')
            post = make_post(user_id=user.id, status='approved')
            c = auth_client(user)
            resp = c.post(
                f'/posts/{post.id}/bookmark',
                headers={'X-Requested-With': 'XMLHttpRequest'},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert 'bookmarked' in data

    def test_bookmark_requires_login(self, client, make_user, make_post, app):
        with app.app_context():
            user = make_user(username='bm_owner', email='bm_owner@test.com')
            post = make_post(user_id=user.id, status='approved')
            resp = client.post(f'/posts/{post.id}/bookmark', follow_redirects=False)
            assert resp.status_code == 302

    def test_comment_creates_record(self, auth_client, make_user, make_post, app):
        with app.app_context():
            user = make_user(username='commenter', email='commenter@test.com')
            post = make_post(user_id=user.id, status='approved')
            c = auth_client(user)
            resp = c.post(
                f'/posts/{post.id}/comment',
                data={'content': 'Great post!'},
                follow_redirects=True,
            )
            assert resp.status_code == 200
            assert Comment.query.filter_by(post_id=post.id).count() == 1

    def test_comment_requires_login(self, client, make_user, make_post, app):
        with app.app_context():
            user = make_user(username='comment_owner', email='comment_owner@test.com')
            post = make_post(user_id=user.id, status='approved')
            resp = client.post(
                f'/posts/{post.id}/comment',
                data={'content': 'hi'},
                follow_redirects=False,
            )
            assert resp.status_code == 302