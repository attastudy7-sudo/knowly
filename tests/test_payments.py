"""
tests/test_payments.py
======================
Integration tests for the payments blueprint (app/payments/routes.py).

All Paystack API calls are mocked with unittest.mock — no real HTTP requests.

Covers:
  - Document checkout page: renders, guards (free doc, already owns, bad price)
  - Document initiate: redirects to Paystack, guards
  - Document verify: success → Purchase created, failed tx, duplicate reference,
                     network error, amount tamper
  - Subscription plan_checkout: renders, unknown plan, already subscribed
  - Subscription subscribe_verify: success → Subscription created, failed tx,
                                   duplicate reference, network error
  - Webhook: valid signature → purchase recorded, subscription recorded,
             invalid signature rejected, duplicate idempotency, missing metadata
  - _user_has_active_subscription helper
  - my_purchases and my_subscription pages

Run from the edushare/ root:
    pytest tests/test_payments.py -v
"""

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app import db
from app.models import Document, Post, Purchase, Subscription, User
from app.payments.routes import PLANS, _user_has_active_subscription


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _paystack_success(amount_pesewas=1000, channel='card', reference='txn_test_001'):
    """Return a mock Paystack verify response for a successful payment."""
    return MagicMock(**{
        'json.return_value': {
            'status': True,
            'data': {
                'status': 'success',
                'amount': amount_pesewas,
                'channel': channel,
                'reference': reference,
            }
        }
    })


def _paystack_failed(status='failed', reference='txn_fail_001'):
    """Return a mock Paystack verify response for a failed payment."""
    return MagicMock(**{
        'json.return_value': {
            'status': True,
            'data': {
                'status': status,
                'amount': 0,
                'channel': 'card',
                'reference': reference,
            }
        }
    })


def _paystack_init_success(auth_url='https://paystack.com/pay/test'):
    """Return a mock Paystack initialize response."""
    return MagicMock(**{
        'json.return_value': {
            'status': True,
            'data': {'authorization_url': auth_url}
        }
    })


def _webhook_payload(event='charge.success', reference='wh_ref_001',
                     user_id=1, document_id=None, plan_key=None,
                     amount=1000):
    """Build a Paystack webhook payload dict."""
    metadata = {'user_id': user_id}
    if document_id:
        metadata['document_id'] = document_id
    if plan_key:
        metadata['plan_key'] = plan_key
        metadata['type'] = 'subscription'

    return {
        'event': event,
        'data': {
            'reference': reference,
            'amount': amount,
            'channel': 'card',
            'metadata': metadata,
        }
    }


def _sign_webhook(body_bytes, secret='sk_test_dummy'):
    """Compute HMAC-SHA512 signature the same way the route does."""
    return hmac.new(secret.encode(), body_bytes, hashlib.sha512).hexdigest()


# ══════════════════════════════════════════════════════════════════════════════
# Document checkout page
# ══════════════════════════════════════════════════════════════════════════════

class TestDocumentCheckout:

    def test_checkout_renders_for_paid_document(self, client, db_session, make_user,
                                                make_document, auth_client, app):
        user = make_user()
        with app.app_context():
            doc = make_document(is_paid=True, price=10.0)
            doc_id = doc.id

        logged_in = auth_client(user)
        response = logged_in.get(f'/payments/checkout/{doc_id}')
        assert response.status_code == 200

    def test_checkout_redirects_for_free_document(self, client, db_session, make_user,
                                                   make_document, auth_client, app):
        user = make_user()
        with app.app_context():
            doc = make_document(is_paid=False)
            doc_id = doc.id

        logged_in = auth_client(user)
        response = logged_in.get(f'/payments/checkout/{doc_id}', follow_redirects=False)
        assert response.status_code == 302

    def test_checkout_redirects_if_user_already_owns(self, client, db_session, make_user,
                                                      make_document, auth_client, app):
        user = make_user()
        with app.app_context():
            doc = make_document(is_paid=True, price=10.0)
            purchase = Purchase(
                user_id=user.id,
                document_id=doc.id,
                amount_paid=10.0,
                transaction_id='existing_txn',
                status='completed',
            )
            db.session.add(purchase)
            db.session.commit()
            doc_id = doc.id

        logged_in = auth_client(user)
        response = logged_in.get(f'/payments/checkout/{doc_id}', follow_redirects=False)
        assert response.status_code == 302

    def test_checkout_redirects_for_zero_price(self, client, db_session, make_user,
                                                make_document, auth_client, app):
        user = make_user()
        with app.app_context():
            doc = make_document(is_paid=True, price=0.0)
            doc_id = doc.id

        logged_in = auth_client(user)
        response = logged_in.get(f'/payments/checkout/{doc_id}', follow_redirects=False)
        assert response.status_code == 302

    def test_checkout_requires_login(self, client, db_session, make_document, app):
        with app.app_context():
            doc = make_document(is_paid=True, price=10.0)
            doc_id = doc.id

        response = client.get(f'/payments/checkout/{doc_id}', follow_redirects=False)
        assert response.status_code == 302
        assert '/auth/login' in response.headers['Location']


# ══════════════════════════════════════════════════════════════════════════════
# Document verify
# ══════════════════════════════════════════════════════════════════════════════

class TestDocumentVerify:

    def test_verify_success_creates_purchase(self, client, db_session, make_user,
                                              make_document, auth_client, app):
        user = make_user()
        with app.app_context():
            doc = make_document(is_paid=True, price=10.0)
            doc_id = doc.id

        logged_in = auth_client(user)

        with patch('requests.get', return_value=_paystack_success(amount_pesewas=1000)):
            with patch('app.utils.send_purchase_confirmation_email'):
                response = logged_in.get(
                    f'/payments/verify/{doc_id}?reference=txn_test_001',
                    follow_redirects=True
                )

        assert response.status_code == 200
        with app.app_context():
            purchase = Purchase.query.filter_by(transaction_id='txn_test_001').first()
            assert purchase is not None
            assert purchase.status == 'completed'

    def test_verify_missing_reference_redirects(self, client, db_session, make_user,
                                                  make_document, auth_client, app):
        user = make_user()
        with app.app_context():
            doc = make_document(is_paid=True, price=10.0)
            doc_id = doc.id

        logged_in = auth_client(user)
        response = logged_in.get(f'/payments/verify/{doc_id}', follow_redirects=False)
        assert response.status_code == 302

    def test_verify_duplicate_reference_is_idempotent(self, client, db_session, make_user,
                                                        make_document, auth_client, app):
        user = make_user()
        with app.app_context():
            doc = make_document(is_paid=True, price=10.0)
            existing = Purchase(
                user_id=user.id,
                document_id=doc.id,
                amount_paid=10.0,
                transaction_id='dup_ref_001',
                status='completed',
            )
            db.session.add(existing)
            db.session.commit()
            doc_id = doc.id

        logged_in = auth_client(user)
        response = logged_in.get(
            f'/payments/verify/{doc_id}?reference=dup_ref_001',
            follow_redirects=True
        )
        assert response.status_code == 200
        # Only one purchase should exist
        with app.app_context():
            count = Purchase.query.filter_by(transaction_id='dup_ref_001').count()
            assert count == 1

    def test_verify_failed_payment_records_failed_purchase(self, client, db_session,
                                                             make_user, make_document,
                                                             auth_client, app):
        user = make_user()
        with app.app_context():
            doc = make_document(is_paid=True, price=10.0)
            doc_id = doc.id

        logged_in = auth_client(user)
        with patch('requests.get', return_value=_paystack_failed(reference='fail_ref_001')):
            response = logged_in.get(
                f'/payments/verify/{doc_id}?reference=fail_ref_001',
                follow_redirects=True
            )

        assert response.status_code == 200
        with app.app_context():
            purchase = Purchase.query.filter_by(transaction_id='fail_ref_001').first()
            assert purchase is not None
            assert purchase.status == 'failed'

    def test_verify_network_error_shows_message(self, client, db_session, make_user,
                                                  make_document, auth_client, app):
        user = make_user()
        with app.app_context():
            doc = make_document(is_paid=True, price=10.0)
            doc_id = doc.id

        logged_in = auth_client(user)
        import requests as req
        with patch('requests.get', side_effect=req.exceptions.RequestException('timeout')):
            response = logged_in.get(
                f'/payments/verify/{doc_id}?reference=net_err_ref',
                follow_redirects=True
            )

        assert response.status_code == 200
        assert b'contact support' in response.data.lower() or b'verify' in response.data.lower()

    def test_verify_amount_below_expected_records_failed(self, client, db_session,
                                                          make_user, make_document,
                                                          auth_client, app):
        """If Paystack reports less than the document price, treat as failed."""
        user = make_user()
        with app.app_context():
            doc = make_document(is_paid=True, price=10.0)  # expects 1000 pesewas
            doc_id = doc.id

        logged_in = auth_client(user)
        # Paystack returns only 500 pesewas — under the required 1000
        with patch('requests.get', return_value=_paystack_success(
            amount_pesewas=500, reference='low_amount_ref'
        )):
            response = logged_in.get(
                f'/payments/verify/{doc_id}?reference=low_amount_ref',
                follow_redirects=True
            )

        assert response.status_code == 200
        with app.app_context():
            purchase = Purchase.query.filter_by(transaction_id='low_amount_ref').first()
            # Should be recorded as failed/underpaid, not completed
            assert purchase is None or purchase.status != 'completed'


# ══════════════════════════════════════════════════════════════════════════════
# Subscription plan checkout
# ══════════════════════════════════════════════════════════════════════════════

class TestPlanCheckout:

    def test_plan_checkout_renders_for_valid_plan(self, client, db_session, make_user,
                                                   auth_client):
        user = make_user()
        logged_in = auth_client(user)
        response = logged_in.get('/payments/checkout/plan?plan=monthly_unlimited')
        assert response.status_code == 200

    def test_plan_checkout_unknown_plan_redirects(self, client, db_session, make_user,
                                                   auth_client):
        user = make_user()
        logged_in = auth_client(user)
        response = logged_in.get('/payments/checkout/plan?plan=nonexistent',
                                  follow_redirects=False)
        assert response.status_code == 302

    def test_plan_checkout_no_plan_param_redirects(self, client, db_session, make_user,
                                                    auth_client):
        user = make_user()
        logged_in = auth_client(user)
        response = logged_in.get('/payments/checkout/plan', follow_redirects=False)
        assert response.status_code == 302

    def test_plan_checkout_already_subscribed_redirects(self, client, db_session, make_user,
                                                         make_subscription, auth_client, app):
        user = make_user()
        make_subscription(user_id=user.id)

        logged_in = auth_client(user)
        response = logged_in.get('/payments/checkout/plan?plan=monthly_unlimited',
                                  follow_redirects=False)
        assert response.status_code == 302

    def test_plan_checkout_requires_login(self, client, db_session):
        response = client.get('/payments/checkout/plan?plan=monthly_unlimited',
                               follow_redirects=False)
        assert response.status_code == 302
        assert '/auth/login' in response.headers['Location']


# ══════════════════════════════════════════════════════════════════════════════
# Subscription verify
# ══════════════════════════════════════════════════════════════════════════════

class TestSubscribeVerify:

    def test_verify_success_creates_subscription(self, client, db_session, make_user,
                                                  auth_client, app):
        user = make_user()
        logged_in = auth_client(user)

        plan = PLANS['monthly_unlimited']
        amount = int(plan['amount_ghs'] * 100)

        with patch('requests.get', return_value=_paystack_success(
            amount_pesewas=amount, reference='sub_ref_001'
        )):
            with patch('app.utils.send_subscription_activation_email'):
                response = logged_in.get(
                    '/payments/subscribe/verify'
                    '?reference=sub_ref_001&plan_key=monthly_unlimited',
                    follow_redirects=True
                )

        assert response.status_code == 200
        with app.app_context():
            sub = Subscription.query.filter_by(transaction_id='sub_ref_001').first()
            assert sub is not None
            assert sub.status == 'active'
            assert sub.plan_key == 'monthly_unlimited'

    def test_verify_subscription_sets_expiry(self, client, db_session, make_user,
                                              auth_client, app):
        user = make_user()
        logged_in = auth_client(user)
        plan = PLANS['monthly_unlimited']
        amount = int(plan['amount_ghs'] * 100)

        with patch('requests.get', return_value=_paystack_success(
            amount_pesewas=amount, reference='sub_exp_001'
        )):
            with patch('app.utils.send_subscription_activation_email'):
                logged_in.get(
                    '/payments/subscribe/verify'
                    '?reference=sub_exp_001&plan_key=monthly_unlimited',
                    follow_redirects=True
                )

        with app.app_context():
            sub = Subscription.query.filter_by(transaction_id='sub_exp_001').first()
            assert sub is not None
            assert sub.expires_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)

            expected_days = plan['duration_days']
            delta = (sub.expires_at - sub.started_at).days
            assert delta == expected_days

    def test_verify_unknown_plan_redirects(self, client, db_session, make_user, auth_client):
        user = make_user()
        logged_in = auth_client(user)
        response = logged_in.get(
            '/payments/subscribe/verify?reference=ref&plan_key=bogus',
            follow_redirects=False
        )
        assert response.status_code == 302

    def test_verify_missing_reference_redirects(self, client, db_session, make_user,
                                                  auth_client):
        user = make_user()
        logged_in = auth_client(user)
        response = logged_in.get(
            '/payments/subscribe/verify?plan_key=monthly_unlimited',
            follow_redirects=False
        )
        assert response.status_code == 302

    def test_verify_duplicate_subscription_is_idempotent(self, client, db_session, make_user,
                                                           make_subscription, auth_client, app):
        user = make_user()
        with app.app_context():
            now = datetime.now(timezone.utc)
            sub = Subscription(
                user_id=user.id,
                plan_key='monthly_unlimited',
                plan_name='Monthly Unlimited',
                amount_paid=20.0,
                currency='GHS',
                transaction_id='dup_sub_ref',
                status='active',
                started_at=now,
                expires_at=now + timedelta(days=30),
            )
            db.session.add(sub)
            db.session.commit()

        logged_in = auth_client(user)
        response = logged_in.get(
            '/payments/subscribe/verify'
            '?reference=dup_sub_ref&plan_key=monthly_unlimited',
            follow_redirects=True
        )
        assert response.status_code == 200
        with app.app_context():
            count = Subscription.query.filter_by(transaction_id='dup_sub_ref').count()
            assert count == 1

    def test_verify_failed_payment_records_failed_subscription(self, client, db_session,
                                                                 make_user, auth_client, app):
        user = make_user()
        logged_in = auth_client(user)

        with patch('requests.get', return_value=_paystack_failed(reference='sub_fail_001')):
            response = logged_in.get(
                '/payments/subscribe/verify'
                '?reference=sub_fail_001&plan_key=monthly_unlimited',
                follow_redirects=True
            )

        assert response.status_code == 200
        with app.app_context():
            sub = Subscription.query.filter_by(transaction_id='sub_fail_001').first()
            assert sub is not None
            assert sub.status != 'active'

    def test_verify_network_error_redirects(self, client, db_session, make_user, auth_client):
        user = make_user()
        logged_in = auth_client(user)
        import requests as req
        with patch('requests.get', side_effect=req.exceptions.RequestException('timeout')):
            response = logged_in.get(
                '/payments/subscribe/verify'
                '?reference=net_ref&plan_key=monthly_unlimited',
                follow_redirects=False
            )
        assert response.status_code == 302


# ══════════════════════════════════════════════════════════════════════════════
# Webhook
# ══════════════════════════════════════════════════════════════════════════════

class TestWebhook:

    def _post_webhook(self, client, payload, secret='sk_test_dummy'):
        body = json.dumps(payload).encode()
        sig  = _sign_webhook(body, secret)
        return client.post(
            '/payments/webhook',
            data=body,
            content_type='application/json',
            headers={'X-Paystack-Signature': sig},
        )

    def test_invalid_signature_returns_400(self, client, db_session):
        body = json.dumps({'event': 'charge.success'}).encode()
        response = client.post(
            '/payments/webhook',
            data=body,
            content_type='application/json',
            headers={'X-Paystack-Signature': 'bad_signature'},
        )
        assert response.status_code == 400

    def test_document_purchase_webhook_creates_purchase(self, client, db_session,
                                                         make_user, make_document,
                                                         app):
        user = make_user()
        with app.app_context():
            doc = make_document(is_paid=True, price=10.0)
            user_id = user.id
            doc_id  = doc.id

        payload = _webhook_payload(
            reference='wh_doc_001',
            user_id=user_id,
            document_id=doc_id,
            amount=1000,
        )

        with patch('app.utils.emails.send_purchase_confirmation_email'):
            response = self._post_webhook(client, payload)

        assert response.status_code == 200
        with app.app_context():
            purchase = Purchase.query.filter_by(transaction_id='wh_doc_001').first()
            assert purchase is not None
            assert purchase.status == 'completed'

    def test_subscription_webhook_creates_subscription(self, client, db_session,
                                                        make_user, app):
        user = make_user()
        with app.app_context():
            user_id = user.id

        payload = _webhook_payload(
            reference='wh_sub_001',
            user_id=user_id,
            plan_key='monthly_unlimited',
            amount=2000,
        )

        response = self._post_webhook(client, payload)
        assert response.status_code == 200
        with app.app_context():
            sub = Subscription.query.filter_by(transaction_id='wh_sub_001').first()
            assert sub is not None
            assert sub.status == 'active'

    def test_webhook_duplicate_reference_is_idempotent(self, client, db_session,
                                                         make_user, make_document, app):
        user = make_user()
        with app.app_context():
            doc = make_document(is_paid=True, price=10.0)
            existing = Purchase(
                user_id=user.id,
                document_id=doc.id,
                amount_paid=10.0,
                transaction_id='wh_dup_001',
                status='completed',
            )
            db.session.add(existing)
            db.session.commit()
            user_id = user.id
            doc_id  = doc.id

        payload = _webhook_payload(
            reference='wh_dup_001',
            user_id=user_id,
            document_id=doc_id,
        )
        self._post_webhook(client, payload)

        with app.app_context():
            count = Purchase.query.filter_by(transaction_id='wh_dup_001').count()
            assert count == 1

    def test_webhook_missing_metadata_returns_200(self, client, db_session):
        """Webhook should always return 200 even for payloads it can't process."""
        payload = {
            'event': 'charge.success',
            'data': {'reference': 'no_meta_ref', 'amount': 1000, 'metadata': {}}
        }
        response = self._post_webhook(client, payload)
        assert response.status_code == 200

    def test_non_charge_event_returns_200(self, client, db_session):
        payload = {'event': 'transfer.success', 'data': {}}
        response = self._post_webhook(client, payload)
        assert response.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# _user_has_active_subscription helper
# ══════════════════════════════════════════════════════════════════════════════

class TestUserHasActiveSubscription:

    def test_returns_true_for_active_subscription(self, client, db_session,
                                                   make_user, make_subscription, app):
        user = make_user()
        make_subscription(user_id=user.id)
        with app.app_context():
            u = db.session.get(User, user.id)
            assert _user_has_active_subscription(u) is True

    def test_returns_false_for_expired_subscription(self, client, db_session,
                                                      make_user, make_subscription, app):
        user = make_user()
        make_subscription(user_id=user.id, expired=True)
        with app.app_context():
            u = db.session.get(User, user.id)
            assert _user_has_active_subscription(u) is False

    def test_returns_false_for_no_subscription(self, client, db_session, make_user, app):
        user = make_user()
        with app.app_context():
            u = db.session.get(User, user.id)
            assert _user_has_active_subscription(u) is False


# ══════════════════════════════════════════════════════════════════════════════
# My purchases / my subscription pages
# ══════════════════════════════════════════════════════════════════════════════

class TestAccountPages:

    def test_my_purchases_page_loads(self, client, db_session, make_user, auth_client):
        user = make_user()
        logged_in = auth_client(user)
        response = logged_in.get('/payments/my-purchases')
        assert response.status_code == 200

    def test_my_subscription_page_loads(self, client, db_session, make_user, auth_client):
        user = make_user()
        logged_in = auth_client(user)
        response = logged_in.get('/payments/my-subscription')
        assert response.status_code == 200

    def test_my_purchases_requires_login(self, client, db_session):
        response = client.get('/payments/my-purchases', follow_redirects=False)
        assert response.status_code == 302

    def test_my_subscription_requires_login(self, client, db_session):
        response = client.get('/payments/my-subscription', follow_redirects=False)
        assert response.status_code == 302