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

    if not document.is_paid:
        flash('This document is free — no purchase needed.', 'info')
        return redirect(url_for('posts.view', post_id=document.post.id))

    if document.has_access(current_user):
        flash('You already have access to this document.', 'info')
        return redirect(url_for('posts.view', post_id=document.post.id))

    # Price in GHS pesewas (Paystack uses smallest currency unit)
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

    if not document.is_paid:
        return redirect(url_for('posts.view', post_id=document.post.id))

    if document.has_access(current_user):
        flash('You already have access to this document.', 'info')
        return redirect(url_for('posts.view', post_id=document.post.id))

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
            # Redirect user to Paystack's hosted payment page
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
    reference = request.args.get('reference', '').strip()

    if not reference:
        flash('Invalid payment reference.', 'danger')
        return redirect(url_for('payments.checkout', document_id=document.id))

    # Check we haven't already processed this reference
    existing = Purchase.query.filter_by(transaction_id=reference).first()
    if existing:
        flash('This payment has already been processed.', 'info')
        return redirect(url_for('posts.view', post_id=document.post.id))

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

        # Confirm payment is actually successful and amount matches
        expected_pesewas = int(document.price * 100)
        if tx['status'] == 'success' and tx['amount'] >= expected_pesewas:
            purchase = Purchase(
                user_id=current_user.id,
                document_id=document.id,
                amount_paid=tx['amount'] / 100,     # convert back to GHS
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
            return redirect(url_for('posts.view', post_id=document.post.id))

        else:
            # Payment exists but wasn't successful (abandoned, failed, etc.)
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
        flash('Could not verify payment. Please contact support with your reference: '
              f'{reference}', 'danger')
        return redirect(url_for('payments.checkout', document_id=document.id))


@bp.route('/webhook', methods=['POST'])
def webhook():
    """
    Paystack webhook — receives async payment events.
    Set this URL in your Paystack dashboard under Settings → Webhooks.
    This is a backup in case the user closes the browser before verify() runs.
    """
    paystack_signature = request.headers.get('X-Paystack-Signature', '')
    secret             = current_app.config['PAYSTACK_SECRET_KEY'].encode()
    body               = request.get_data()

    # Verify the webhook is genuinely from Paystack
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

        # Idempotency — skip if already processed
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
        current_app.logger.info(f"Webhook: purchase recorded for doc {document_id} by user {user_id}")

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