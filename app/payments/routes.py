from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.payments import bp
from app.models import Document, Purchase


@bp.route('/checkout/<int:document_id>')
@login_required
def checkout(document_id):
    """
    Checkout page for purchasing a document.
    This is a placeholder - implement Stripe/Paystack integration here.
    """
    document = Document.query.get_or_404(document_id)
    
    # Check if document is paid
    if not document.is_paid:
        flash('This document is free!', 'info')
        return redirect(url_for('posts.download_document', document_id=document.id))
    
    # Check if already purchased
    existing_purchase = Purchase.query.filter_by(
        user_id=current_user.id,
        document_id=document.id
    ).first()
    
    if existing_purchase and existing_purchase.status == 'completed':
        flash('You have already purchased this document.', 'info')
        return redirect(url_for('posts.download_document', document_id=document.id))
    
    return render_template('payments/checkout.html',
                         title='Checkout',
                         document=document)


@bp.route('/process/<int:document_id>', methods=['POST'])
@login_required
def process_payment(document_id):
    """
    Process payment for a document.
    
    PLACEHOLDER - Implement actual payment processing here:
    1. For Stripe:
       - Create payment intent
       - Handle webhook for confirmation
       - Update purchase status
    
    2. For Paystack:
       - Initialize transaction
       - Verify transaction
       - Update purchase status
    """
    document = Document.query.get_or_404(document_id)
    
    # TODO: Implement payment provider integration
    # This is a mock implementation
    
    # Example structure for Stripe:
    # import stripe
    # stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    # intent = stripe.PaymentIntent.create(
    #     amount=int(document.price * 100),  # Convert to cents
    #     currency='usd',
    #     metadata={'document_id': document.id, 'user_id': current_user.id}
    # )
    
    # Example structure for Paystack:
    # import requests
    # url = "https://api.paystack.co/transaction/initialize"
    # headers = {
    #     "Authorization": f"Bearer {current_app.config['PAYSTACK_SECRET_KEY']}",
    #     "Content-Type": "application/json"
    # }
    # data = {
    #     "email": current_user.email,
    #     "amount": int(document.price * 100),  # Convert to kobo
    #     "metadata": {"document_id": document.id, "user_id": current_user.id}
    # }
    # response = requests.post(url, json=data, headers=headers)
    
    flash('Payment processing not yet implemented. This is a placeholder.', 'warning')
    return redirect(url_for('payments.checkout', document_id=document.id))


@bp.route('/success/<int:document_id>')
@login_required
def payment_success(document_id):
    """
    Payment success callback.
    Called after successful payment from provider.
    """
    document = Document.query.get_or_404(document_id)
    
    # TODO: Verify payment with provider before granting access
    
    flash('Payment successful! You can now download the document.', 'success')
    return redirect(url_for('posts.download_document', document_id=document.id))


@bp.route('/cancel/<int:document_id>')
@login_required
def payment_cancel(document_id):
    """
    Payment cancelled callback.
    """
    flash('Payment was cancelled.', 'info')
    return redirect(url_for('posts.view', post_id=Document.query.get(document_id).post.id))


@bp.route('/webhook', methods=['POST'])
def webhook():
    """
    Webhook endpoint for payment provider callbacks.
    
    For Stripe:
    - Verify webhook signature
    - Handle payment_intent.succeeded event
    - Create Purchase record
    
    For Paystack:
    - Verify transaction reference
    - Create Purchase record
    """
    # TODO: Implement webhook handling
    # This is critical for security - always verify webhooks!
    
    # Example for Stripe:
    # import stripe
    # payload = request.data
    # sig_header = request.headers.get('Stripe-Signature')
    # 
    # try:
    #     event = stripe.Webhook.construct_event(
    #         payload, sig_header, current_app.config['STRIPE_WEBHOOK_SECRET']
    #     )
    # except ValueError as e:
    #     return 'Invalid payload', 400
    # except stripe.error.SignatureVerificationError as e:
    #     return 'Invalid signature', 400
    # 
    # if event['type'] == 'payment_intent.succeeded':
    #     payment_intent = event['data']['object']
    #     # Create purchase record
    #     purchase = Purchase(
    #         user_id=payment_intent['metadata']['user_id'],
    #         document_id=payment_intent['metadata']['document_id'],
    #         amount_paid=payment_intent['amount'] / 100,
    #         payment_method='stripe',
    #         transaction_id=payment_intent['id'],
    #         status='completed'
    #     )
    #     db.session.add(purchase)
    #     db.session.commit()
    
    return 'Webhook received', 200


@bp.route('/my-purchases')
@login_required
def my_purchases():
    """
    View user's purchase history.
    """
    purchases = Purchase.query.filter_by(user_id=current_user.id).order_by(
        Purchase.purchased_at.desc()
    ).all()
    
    return render_template('payments/my_purchases.html',
                         title='My Purchases',
                         purchases=purchases)
