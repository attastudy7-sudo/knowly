import hmac
import hashlib
import json
import requests
from flask import render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app import db
from app.payments import bp
from app.models import Document, Purchase


def _paystack_headers():
    """Return auth headers for Paystack API calls."""
    return {
        'Authorization': f"Bearer {current_app.config['PAYSTACK_SECRET_KEY']}",
        'Content-Type': 'application/json',
    }


@bp.route('/checkout/<int:document_id>')
@login_required
def checkout(document_id):
    """
    Show the checkout page for a paid document.
    Redirects away if the user already has access.
    """
    document = Document.query.get_or_404(document_id)

    # Guard: document must be paid
    if not document.is_paid:
        flash('This document is free — no purchase needed.', 'info')
        # document.post may be None if relationship not set; fall back to index
        post = document.post
        if post:
            return redirect(url_for('posts.view', post_id=post.id))
        return redirect(url_for('main.index'))

    # Guard: user already has access
    if document.has_access(current_user):
        flash('You already have access to this document.', 'info')
        post = document.post
        if post:
            return redirect(url_for('posts.view', post_id=post.id))
        return redirect(url_for('main.index'))

    # Guard: price must be a positive value
    if not document.price or document.price <= 0:
        flash('This document has an invalid price. Please contact support.', 'danger')
        return redirect(url_for('main.index'))

    # Price in pesewas (Paystack uses smallest currency unit; min 100 = GHS 1.00)
    amount_pesewas = int(document.price * 100)

    return render_template(
        'payments/checkout.html',
        title=f'Purchase — {document.original_filename}',
        document=document,
        amount_pesewas=amount_pesewas,
        paystack_public_key=current_app.config['PAYSTACK_PUBLIC_KEY'],
    )


@bp.route('/initiate/<int:document_id>', methods=['POST'])
@login_required
def initiate(document_id):
    """
    Create a Paystack transaction and redirect the user to
    Paystack's hosted payment page.
    """
    document = Document.query.get_or_404(document_id)
    post = document.post

    if not document.is_paid:
        if post:
            return redirect(url_for('posts.view', post_id=post.id))
        return redirect(url_for('main.index'))

    if document.has_access(current_user):
        flash('You already have access to this document.', 'info')
        if post:
            return redirect(url_for('posts.view', post_id=post.id))
        return redirect(url_for('main.index'))

    if not document.price or document.price <= 0:
        flash('This document has an invalid price.', 'danger')
        return redirect(url_for('main.index'))

    amount_pesewas = int(document.price * 100)
    callback_url   = url_for('payments.verify', document_id=document.id, _external=True)

    payload = {
        'email':        current_user.email,
        'amount':       amount_pesewas,
        'currency':     'GHS',
        'callback_url': callback_url,
        'metadata': {
            'user_id':     current_user.id,
            'document_id': document.id,
            'custom_fields': [
                {
                    'display_name': 'Document',
                    'variable_name': 'document_name',
                    'value': document.original_filename,
                },
                {
                    'display_name': 'Buyer',
                    'variable_name': 'buyer_username',
                    'value': current_user.username,
                },
            ],
        },
    }

    try:
        response = requests.post(
            'https://api.paystack.co/transaction/initialize',
            headers=_paystack_headers(),
            json=payload,
            timeout=15,
        )
        data = response.json()

        if data.get('status'):
            return redirect(data['data']['authorization_url'])
        else:
            current_app.logger.error(f"Paystack init failed: {data}")
            flash('Payment could not be initiated. Please try again.', 'danger')
            return redirect(url_for('payments.checkout', document_id=document.id))

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Paystack request error: {e}")
        flash('A network error occurred. Please try again.', 'danger')
        return redirect(url_for('payments.checkout', document_id=document.id))


@bp.route('/verify/<int:document_id>')
@login_required
def verify(document_id):
    """
    Paystack redirects here after payment with a ?reference= param.
    We verify the transaction server-side before granting access.
    """
    document  = Document.query.get_or_404(document_id)
    post      = document.post
    reference = request.args.get('reference', '').strip()

    if not reference:
        flash('Invalid payment reference.', 'danger')
        return redirect(url_for('payments.checkout', document_id=document.id))

    # Idempotency: don't process the same reference twice
    existing = Purchase.query.filter_by(transaction_id=reference).first()
    if existing:
        flash('This payment has already been processed.', 'info')
        if post:
            return redirect(url_for('posts.view', post_id=post.id))
        return redirect(url_for('main.index'))

    try:
        response = requests.get(
            f'https://api.paystack.co/transaction/verify/{reference}',
            headers=_paystack_headers(),
            timeout=15,
        )
        data = response.json()

        if not data.get('status'):
            flash('Payment verification failed. Please contact support.', 'danger')
            return redirect(url_for('payments.checkout', document_id=document.id))

        tx = data['data']
        expected_pesewas = int(document.price * 100)

        if tx['status'] == 'success' and tx['amount'] >= expected_pesewas:
            purchase = Purchase(
                user_id=current_user.id,
                document_id=document.id,
                amount_paid=tx['amount'] / 100,
                payment_method=tx.get('channel', 'paystack'),
                transaction_id=reference,
                status='completed',
            )
            db.session.add(purchase)
            db.session.commit()

            flash(
                f'Payment successful! You now have full access to '
                f'"{document.original_filename}".',
                'success'
            )
            if post:
                return redirect(url_for('posts.view', post_id=post.id))
            return redirect(url_for('main.index'))

        else:
            # Payment exists but wasn't successful
            purchase = Purchase(
                user_id=current_user.id,
                document_id=document.id,
                amount_paid=0,
                payment_method=tx.get('channel', 'paystack'),
                transaction_id=reference,
                status=tx['status'],
            )
            db.session.add(purchase)
            db.session.commit()

            flash(
                f'Payment was not completed (status: {tx["status"]}). '
                f'No charge was made.',
                'warning'
            )
            return redirect(url_for('payments.checkout', document_id=document.id))

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Paystack verify error: {e}")
        flash(
            f'Could not verify payment. Please contact support with your reference: {reference}',
            'danger'
        )
        return redirect(url_for('payments.checkout', document_id=document.id))


@bp.route('/webhook', methods=['POST'])
def webhook():
    """
    Paystack webhook — receives async payment events.
    Set this URL in your Paystack dashboard under Settings → Webhooks.
    """
    paystack_signature = request.headers.get('X-Paystack-Signature', '')
    secret             = current_app.config['PAYSTACK_SECRET_KEY'].encode()
    body               = request.get_data()

    # FIX: was hmac.new() which does not exist — correct call is hmac.new()
    # Python's hmac module: hmac.new(key, msg=None, digestmod='')
    expected_sig = hmac.new(secret, body, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(expected_sig, paystack_signature):
        current_app.logger.warning('Invalid Paystack webhook signature')
        return jsonify({'status': 'invalid signature'}), 400

    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        return jsonify({'status': 'bad json'}), 400

    if event.get('event') == 'charge.success':
        tx        = event['data']
        reference = tx.get('reference')
        metadata  = tx.get('metadata', {})

        user_id     = metadata.get('user_id')
        document_id = metadata.get('document_id')

        if not all([reference, user_id, document_id]):
            return jsonify({'status': 'missing metadata'}), 200

        # Idempotency
        if Purchase.query.filter_by(transaction_id=reference).first():
            return jsonify({'status': 'already processed'}), 200

        document = Document.query.get(document_id)
        if not document:
            return jsonify({'status': 'document not found'}), 200

        purchase = Purchase(
            user_id=user_id,
            document_id=document_id,
            amount_paid=tx['amount'] / 100,
            payment_method=tx.get('channel', 'paystack'),
            transaction_id=reference,
            status='completed',
        )
        db.session.add(purchase)
        db.session.commit()
        current_app.logger.info(
            f"Webhook: purchase recorded for doc {document_id} by user {user_id}"
        )

    return jsonify({'status': 'ok'}), 200


@bp.route('/my-purchases')
@login_required
def my_purchases():
    """Show the current user's purchase history."""
    purchases = Purchase.query.filter_by(
        user_id=current_user.id,
        status='completed'
    ).order_by(Purchase.purchased_at.desc()).all()

    return render_template(
        'payments/my_purchases.html',
        title='My Purchases',
        purchases=purchases,
    )