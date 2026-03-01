"""
Email notification service for eDuShare platform.

Handles automatic email notifications for:
- New user signups (welcome emails)
- Purchase confirmations
- Subscription activations
"""

import requests
from flask import current_app
from app import db
from app.models import User, Purchase, Document


def _send_brevo_email(to_email, subject, html_content):
    """
    Send an email using Brevo (Sendinblue) API.
    
    Args:
        to_email: Recipient's email address
        subject: Email subject
        html_content: HTML content of the email
        
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    api_key = current_app.config.get('BREVO_API_KEY')
    if not api_key:
        current_app.logger.error('BREVO_API_KEY not configured')
        return False
        
    sender = (
        current_app.config.get('MAIL_DEFAULT_SENDER') or
        current_app.config.get('MAIL_USERNAME')
    )
    
    if not sender:
        current_app.logger.error('MAIL_DEFAULT_SENDER or MAIL_USERNAME not configured')
        return False
        
    try:
        response = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": api_key,
                "Content-Type": "application/json"
            },
            json={
                "sender": {"email": sender},
                "to": [{"email": to_email}],
                "subject": subject,
                "htmlContent": html_content
            },
            timeout=15
        )
        
        if response.status_code == 201:
            current_app.logger.info(f"Email sent successfully to {to_email}")
            return True
        else:
            current_app.logger.error(f"Brevo error for {to_email}: {response.text}")
            return False
            
    except Exception as e:
        current_app.logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def send_welcome_email(user):
    """
    Send a welcome email to a new user.
    
    Args:
        user: User object (from app.models.User)
        
    Returns:
        bool: True if email was sent successfully
    """
    subject = "Welcome to eDuShare!"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                margin: 0;
                padding: 20px;
            }}
            .email-container {{
                background-color: white;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .header {{
                background-color: #6366f1;
                color: white;
                padding: 20px;
                text-align: center;
                border-radius: 8px 8px 0 0;
                margin: -20px -20px 20px -20px;
            }}
            .content {{
                color: #333;
                line-height: 1.6;
            }}
            .button {{
                display: inline-block;
                background-color: #6366f1;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 4px;
                margin: 20px 0;
            }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #eee;
                color: #666;
                font-size: 14px;
                text-align: center;
            }}
        </style>
    </head>
    <body>
<div class="email-container">
    <div class="header">
        <h1>Welcome to eDuShare!</h1>
    </div>
    
    <div class="content">
        <p>Hi {user.full_name or user.username},</p>
        
        <p>Chale, welcome to eDuShare — your platform wey you fit use share and discover educational materials with students all over the world.</p>
        
        <p>See some cool things wey you fit do for here:</p>
        <ul>
            <li>📚 Browse and download study materials</li>
            <li>🤝 Connect with other students</li>
            <li>📝 Share your own notes and documents</li>
            <li>🎯 Take quizzes and earn XP</li>
        </ul>
        
        <p>You fit start by checking our 
            <a href="{current_app.config['PREFERRED_URL_SCHEME']}://{current_app.config.get('SERVER_NAME', 'localhost:5000')}/explore">
                Explore
            </a> 
            page to find materials for your courses.
        </p>
        
        <p>
            <a href="{current_app.config['PREFERRED_URL_SCHEME']}://{current_app.config.get('SERVER_NAME', 'localhost:5000')}/explore" class="button">
                Start Exploring
            </a>
        </p>
        
        <p>If you get any questions or you need help, no hesitate to contact our support team. We dey here for you.</p>
        
        <p>Happy learning!</p>
        <p>The eDuShare Team</p>
    </div>
    
    <div class="footer">
        <p>eDuShare — Empowering Students Through Shared Knowledge</p>
        <p>You dey receive this email because you create account on eDuShare.</p>
    </div>
</div>
</body>    </html>
    """
    
    return _send_brevo_email(user.email, subject, html_content)


def send_purchase_confirmation_email(user, purchase, document):
    """
    Send a purchase confirmation email to a user who bought a document.
    
    Args:
        user: User object
        purchase: Purchase object
        document: Document object
        
    Returns:
        bool: True if email was sent successfully
    """
    subject = "Purchase Confirmation — eDuShare"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                margin: 0;
                padding: 20px;
            }}
            .email-container {{
                background-color: white;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .header {{
                background-color: #6366f1;
                color: white;
                padding: 20px;
                text-align: center;
                border-radius: 8px 8px 0 0;
                margin: -20px -20px 20px -20px;
            }}
            .content {{
                color: #333;
                line-height: 1.6;
            }}
            .purchase-details {{
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 4px;
                margin: 20px 0;
            }}
            .purchase-details p {{
                margin: 5px 0;
            }}
            .button {{
                display: inline-block;
                background-color: #6366f1;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 4px;
                margin: 20px 0;
            }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #eee;
                color: #666;
                font-size: 14px;
                text-align: center;
            }}
        </style>
    </head>
<body>
    <div class="email-container">
        <div class="header">
            <h1>Purchase Confirmed!</h1>
        </div>
        
        <div class="content">
            <p>Hi {user.full_name or user.username},</p>
            
            <p>Chale, we say big thank you for your purchase! Your payment go through successfully, and now you get full access to the document.</p>
            
            <div class="purchase-details">
                <p><strong>Document:</strong> {document.original_filename}</p>
                <p><strong>Amount Paid:</strong> GHS {purchase.amount_paid:.2f}</p>
                <p><strong>Transaction ID:</strong> {purchase.transaction_id}</p>
                <p><strong>Purchase Date:</strong> {purchase.purchased_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <p>
                <a href="{current_app.config['PREFERRED_URL_SCHEME']}://{current_app.config.get('SERVER_NAME', 'localhost:5000')}/payments/my-purchases" class="button">
                    View My Purchases
                </a>
            </p>
            
            <p>Make we tell you something — every time you buy a document, you no just dey pay for notes. You dey support the growth of eDuShare as one of our founding members. Your support dey help us improve the platform, add more features, and bring more quality materials for students like you.</p>
            
            <p>So anytime you purchase, you dey invest in a bigger student community. And we truly appreciate you for that.</p>
            
            <p>If you get any questions about your purchase or you need help accessing the document, no hesitate to contact our support team. We dey here to help.</p>
            
            <p>Thank you once again for choosing eDuShare. More wins ahead!</p>
            <p>The eDuShare Team</p>
        </div>
        
        <div class="footer">
            <p>eDuShare — Empowering Students Through Shared Knowledge</p>
            <p>You dey receive this email because you make a purchase on eDuShare.</p>
        </div>
    </div>
</body>    </html>
    """
    
    return _send_brevo_email(user.email, subject, html_content)


def send_subscription_activation_email(user, tier=None):
    """
    Send a subscription activation email to a user who bought a subscription.
    
    Args:
        user: User object
        tier: Optional subscription tier (default: user.subscription_tier)
        
    Returns:
        bool: True if email was sent successfully
    """
    subscription_tier = tier or user.subscription_tier
    subject = f"Subscription Activated — {subscription_tier.capitalize()} Plan"
    
    # Subscription benefits based on tier
    benefits = {
        'pro': [
            '✨ Unlimited document downloads',
            '🎯 Unlimited quiz attempts',
            '🚀 Priority support',
            '📊 Advanced analytics',
            '💾 Cloud storage for your documents'
        ],
        'enterprise': [
            '✨ All Pro features',
            '🏢 Team collaboration tools',
            '🔒 Custom security settings',
            '📈 Custom reporting',
            '🎓 Dedicated account manager',
            '⏰ 24/7 priority support'
        ]
    }
    
    tier_benefits = benefits.get(subscription_tier, [])
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                margin: 0;
                padding: 20px;
            }}
            .email-container {{
                background-color: white;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .header {{
                background-color: #6366f1;
                color: white;
                padding: 20px;
                text-align: center;
                border-radius: 8px 8px 0 0;
                margin: -20px -20px 20px -20px;
            }}
            .content {{
                color: #333;
                line-height: 1.6;
            }}
            .benefits {{
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 4px;
                margin: 20px 0;
            }}
            .benefits ul {{
                margin: 10px 0;
                padding-left: 20px;
            }}
            .benefits li {{
                margin: 8px 0;
            }}
            .button {{
                display: inline-block;
                background-color: #6366f1;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 4px;
                margin: 20px 0;
            }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #eee;
                color: #666;
                font-size: 14px;
                text-align: center;
            }}
        </style>
    </head>
<body>
    <div class="email-container">
        <div class="header">
            <h1>Welcome to eDuShare {subscription_tier.capitalize()}!</h1>
        </div>
        
        <div class="content">
            <p>Hi {user.full_name or user.username},</p>
            
            <p>Big congratulations! Your {subscription_tier.capitalize()} subscription don activate successfully. You now get full access to all the premium features wey eDuShare get to offer.</p>
            
            <div class="benefits">
                <h3>Your {subscription_tier.capitalize()} Benefits:</h3>
                <ul>
                    {''.join(f'<li>{benefit}</li>' for benefit in tier_benefits)}
                </ul>
            </div>
            
            <p>
                <a href="{current_app.config['PREFERRED_URL_SCHEME']}://{current_app.config.get('SERVER_NAME', 'localhost:5000')}/explore" class="button">
                    Start Exploring
                </a>
            </p>
            
            <p>Your subscription go stay active till {user.subscription_end_date.strftime('%Y-%m-%d')}. Make you enjoy every benefit wey come with am.</p>
            
            <p>By upgrading, you no just unlock premium features — you join the core group of students wey dey push this project forward. Your support dey help us build better tools, improve quality, and grow the eDuShare community stronger every day.</p>
            
            <p>We truly appreciate you for believing in the vision.</p>
            
            <p>If you get any questions about your subscription or you need any help at all, no hesitate to contact our support team. We dey for you.</p>
            
            <p>Thank you for choosing eDuShare. Let’s level up!</p>
            <p>The eDuShare Team</p>
        </div>
        
        <div class="footer">
            <p>eDuShare — Empowering Students Through Shared Knowledge</p>
            <p>You dey receive this email because you activate a subscription on eDuShare.</p>
        </div>
    </div>
</body>
    </html>
    """
    
    return _send_brevo_email(user.email, subject, html_content)


def send_programme_relevant_post_email(user, post):
    """
    Send an email notification to a student when a relevant post is uploaded
    that matches their programme of study.
    
    Args:
        user: User object
        post: Post object
        
    Returns:
        bool: True if email was sent successfully
    """
    subject = f"New Relevant Material: {post.title}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                margin: 0;
                padding: 20px;
            }}
            .email-container {{
                background-color: white;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .header {{
                background-color: #6366f1;
                color: white;
                padding: 20px;
                text-align: center;
                border-radius: 8px 8px 0 0;
                margin: -20px -20px 20px -20px;
            }}
            .content {{
                color: #333;
                line-height: 1.6;
            }}
            .post-details {{
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 4px;
                margin: 20px 0;
            }}
            .post-details h3 {{
                margin-top: 0;
            }}
            .post-details p {{
                margin: 5px 0;
            }}
            .button {{
                display: inline-block;
                background-color: #6366f1;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 4px;
                margin: 20px 0;
            }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #eee;
                color: #666;
                font-size: 14px;
                text-align: center;
            }}
        </style>
    </head>
<body>
    <div class="email-container">
        <div class="header">
            <h1>New Relevant Material Just Landed!</h1>
        </div>
        
        <div class="content">
            <p>Hi {user.full_name or user.username},</p>
            
            <p>Chale, something important just drop — and e match your programme: <strong>{user.programme}</strong>.</p>
            
            <p>This new material fit be exactly what you need before your next class, test, or exams. Don’t miss am.</p>
            
            <div class="post-details">
                <h3>{post.title}</h3>
                <p>{post.description}</p>
                {f'<p><strong>Subject:</strong> {post.subject.name}' if post.subject else ''}
            </div>
            
            <p>
                <a href="{current_app.config['PREFERRED_URL_SCHEME']}://{current_app.config.get('SERVER_NAME', 'localhost:5000')}/posts/{post.id}" class="button">
                    View Post Now
                </a>
            </p>
            
            <p>This material was uploaded very recently, and students wey dey your programme already dey check am out. The earlier you see am, the better advantage you get.</p>
            
            <p>No dull — opportunities like this no dey stay long. Click make you see wetin dey inside.</p>
            
            <p>If you need any help or you get questions, our support team dey ready to assist you.</p>
            
            <p>Stay sharp and keep learning!</p>
            <p>The eDuShare Team</p>
        </div>
        
        <div class="footer">
            <p>eDuShare — Empowering Students Through Shared Knowledge</p>
            <p>You dey receive this email because the content match your programme of study.</p>
        </div>
    </div>
</body>
    </html>
    """
    
    return _send_brevo_email(user.email, subject, html_content)
