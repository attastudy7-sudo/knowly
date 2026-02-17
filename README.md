# 🎓 EduShare - Educational Social Media Platform

A modern, mobile-first educational social media platform where students can share documents, interact with content, and build a learning community.

## ✨ Features

### 🔐 Authentication & User Management
- User registration and login
- Secure password hashing with Werkzeug
- Session management with Flask-Login
- Profile creation and editing
- Custom profile pictures

### 📚 Post & Document Management
- Create, edit, and delete posts
- Upload educational documents (PDF, DOCX, PPTX, TXT)
- In-browser PDF preview
- Download tracking
- Rich text descriptions

### 💬 Social Features
- Like posts
- Comment on posts
- Follow/unfollow users
- Personalized feed showing posts from followed users
- Explore page for discovering new content
- User search functionality

### 💰 Payment Integration (Ready for Implementation)
- Database schema prepared for paid documents
- Placeholder payment routes
- Easy integration with Stripe or Paystack
- Purchase tracking system

### 📱 Mobile-First Design
- Responsive layout optimized for mobile devices
- Bottom navigation bar for mobile
- Touch-friendly interface
- Fast loading times
- Optimized for low data usage

## 🛠️ Tech Stack

- **Backend**: Flask 3.0
- **Database**: SQLite (easily upgradable to PostgreSQL/MySQL)
- **ORM**: SQLAlchemy
- **Authentication**: Flask-Login
- **Forms**: WTForms with validation
- **Frontend**: HTML5, CSS3 (vanilla), JavaScript
- **Icons**: Font Awesome 6

## 📁 Project Structure

```
edushare/
├── app/
│   ├── __init__.py              # App factory & configuration
│   ├── models.py                # Database models
│   ├── forms.py                 # WTForms for validation
│   ├── routes.py                # Main routes (home, feed)
│   ├── auth/                    # Authentication blueprint
│   │   ├── __init__.py
│   │   └── routes.py            # Login, signup, logout
│   ├── posts/                   # Posts & documents blueprint
│   │   ├── __init__.py
│   │   └── routes.py            # CRUD, likes, comments, uploads
│   ├── users/                   # User profiles & social features
│   │   ├── __init__.py
│   │   └── routes.py            # Profiles, follow, search
│   ├── payments/                # Payment integration (future)
│   │   ├── __init__.py
│   │   └── routes.py            # Checkout, webhooks
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css        # Mobile-first responsive CSS
│   │   ├── js/
│   │   │   └── main.js          # Interactive features
│   │   └── uploads/             # User-uploaded files
│   │       ├── profiles/        # Profile pictures
│   │       └── documents/       # Documents
│   └── templates/
│       ├── base.html            # Base template
│       ├── index.html           # Feed/explore
│       ├── auth/                # Auth templates
│       ├── posts/               # Post templates
│       ├── users/               # User templates
│       └── payments/            # Payment templates
├── config.py                    # Configuration settings
├── run.py                       # Application entry point
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Virtual environment (recommended)

### Installation

1. **Clone or download the project**
   ```bash
   cd edushare
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**
   
   On macOS/Linux:
   ```bash
   source venv/bin/activate
   ```
   
   On Windows:
   ```bash
   venv\Scripts\activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **Set environment variables (optional)**
   
   Create a `.env` file in the project root:
   ```env
   SECRET_KEY=your-secret-key-here
   FLASK_ENV=development
   ```

6. **Initialize the database**
   ```bash
   flask init-db
   ```

7. **Seed with sample data (optional)**
   ```bash
   flask seed-db
   ```
   
   This creates three test accounts:
   - alice / password123
   - bob / password123
   - charlie / password123

8. **Run the application**
   ```bash
   python run.py
   ```
   
   Or using Flask CLI:
   ```bash
   flask run
   ```

9. **Access the application**
   
   Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

## 📖 Usage Guide

### Creating an Account

1. Click "Sign Up" in the navigation
2. Fill in your details (username, email, full name, password)
3. Click "Sign Up"
4. Log in with your credentials

### Creating a Post

1. Click the "+" button (mobile) or "Create" (desktop)
2. Enter a title and description
3. Optionally upload a document (PDF, DOCX, PPTX, TXT)
4. Click "Create Post"

### Interacting with Posts

- **Like**: Click the heart icon
- **Comment**: Click on a post to view it, then add a comment
- **Download**: Click the download button on posts with documents
- **Share**: Copy the post URL from your browser

### Following Users

1. Visit a user's profile
2. Click "Follow"
3. Their posts will appear in your personalized feed

### Searching

1. Use the search bar in the top navigation
2. Search for users or posts by keywords
3. Click on results to view profiles or posts

## 🔧 Configuration

### Database Configuration

By default, the app uses SQLite. To use PostgreSQL or MySQL:

1. Update `config.py`:
   ```python
   SQLALCHEMY_DATABASE_URI = 'postgresql://user:password@localhost/edushare'
   # or
   SQLALCHEMY_DATABASE_URI = 'mysql://user:password@localhost/edushare'
   ```

2. Install the appropriate driver:
   ```bash
   pip install psycopg2-binary  # For PostgreSQL
   # or
   pip install pymysql          # For MySQL
   ```

### File Upload Settings

Modify in `config.py`:
```python
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max file size
ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'docx', 'pptx', 'txt', 'doc', 'ppt'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
```

### Session Configuration

```python
PERMANENT_SESSION_LIFETIME = timedelta(days=7)  # Stay logged in for 7 days
```

## 💳 Implementing Payment Integration

The app is structured to easily add payment processing. Here's how:

### Option 1: Stripe Integration

1. **Install Stripe SDK**
   ```bash
   pip install stripe
   ```

2. **Add Stripe keys to `.env`**
   ```env
   STRIPE_PUBLIC_KEY=pk_test_...
   STRIPE_SECRET_KEY=sk_test_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```

3. **Update `app/payments/routes.py`**
   
   Uncomment the Stripe code in `process_payment()` and `webhook()`:
   ```python
   import stripe
   stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
   
   # Create payment intent
   intent = stripe.PaymentIntent.create(
       amount=int(document.price * 100),
       currency='usd',
       metadata={'document_id': document.id, 'user_id': current_user.id}
   )
   ```

4. **Add Stripe.js to checkout template**
   ```html
   <script src="https://js.stripe.com/v3/"></script>
   ```

### Option 2: Paystack Integration

1. **Install Requests**
   ```bash
   pip install requests
   ```

2. **Add Paystack keys to `.env`**
   ```env
   PAYSTACK_PUBLIC_KEY=pk_test_...
   PAYSTACK_SECRET_KEY=sk_test_...
   ```

3. **Update `app/payments/routes.py`**
   
   Implement Paystack initialization:
   ```python
   import requests
   
   url = "https://api.paystack.co/transaction/initialize"
   headers = {
       "Authorization": f"Bearer {current_app.config['PAYSTACK_SECRET_KEY']}",
       "Content-Type": "application/json"
   }
   data = {
       "email": current_user.email,
       "amount": int(document.price * 100),  # In kobo
       "metadata": {"document_id": document.id}
   }
   response = requests.post(url, json=data, headers=headers)
   ```

## 🎨 Customization

### Changing Colors

Edit CSS variables in `app/static/css/style.css`:
```css
:root {
    --primary: #6366f1;        /* Main brand color */
    --primary-dark: #4f46e5;   /* Darker shade */
    --secondary: #8b5cf6;      /* Secondary color */
    --accent: #ec4899;         /* Accent color */
}
```

### Adding New Features

1. Create a new blueprint in `app/feature_name/`
2. Define routes in `routes.py`
3. Register the blueprint in `app/__init__.py`
4. Create templates in `app/templates/feature_name/`

### Modifying Feed Algorithm

Edit the `feed()` function in `app/routes.py`:
```python
def feed():
    # Custom algorithm here
    # Example: Sort by likes instead of chronological
    posts = Post.query.filter(...).order_by(
        Post.likes.count().desc()
    )
```

## 🔒 Security Best Practices

### In Production

1. **Use a strong SECRET_KEY**
   ```bash
   python -c 'import secrets; print(secrets.token_hex(32))'
   ```

2. **Enable HTTPS**
   - Use a reverse proxy (Nginx/Apache)
   - Get SSL certificate (Let's Encrypt)

3. **Use environment variables**
   ```bash
   export SECRET_KEY='your-secret-key'
   export DATABASE_URL='your-database-url'
   ```

4. **Set Flask environment to production**
   ```env
   FLASK_ENV=production
   ```

5. **Use a production WSGI server**
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:8000 run:app
   ```

## 📊 Database Models

### User
- Authentication and profile information
- Relationships: posts, comments, likes, followers, following

### Post
- Title, description, timestamps
- Relationships: author, document, comments, likes

### Document
- File information and payment settings
- Access control for paid documents

### Comment
- User comments on posts
- Relationships: author, post

### Like
- User likes on posts
- Composite unique constraint (user_id, post_id)

### Purchase
- Document purchase records
- Transaction tracking

### Notification
- User notifications (followers, likes, comments)

## 🚀 Deployment

### Deploying to Heroku

1. **Create a Heroku app**
   ```bash
   heroku create edushare-app
   ```

2. **Add PostgreSQL addon**
   ```bash
   heroku addons:create heroku-postgresql:hobby-dev
   ```

3. **Set environment variables**
   ```bash
   heroku config:set SECRET_KEY='your-secret-key'
   ```

4. **Create `Procfile`**
   ```
   web: gunicorn run:app
   ```

5. **Deploy**
   ```bash
   git push heroku main
   ```

6. **Initialize database**
   ```bash
   heroku run flask init-db
   ```

### Deploying to DigitalOcean/AWS

1. Set up a Linux server
2. Install Python, Nginx, and PostgreSQL
3. Clone the repository
4. Set up virtual environment and install dependencies
5. Configure Nginx as reverse proxy
6. Use Gunicorn or uWSGI as WSGI server
7. Set up SSL with Let's Encrypt

## 🧪 Testing

### Manual Testing Checklist

- [ ] User registration and login
- [ ] Profile creation and editing
- [ ] Post creation with/without documents
- [ ] Like and unlike posts
- [ ] Add comments
- [ ] Follow/unfollow users
- [ ] Search functionality
- [ ] Document upload and download
- [ ] Mobile responsiveness

### Automated Testing (Future)

Create tests in `tests/` directory:
```python
def test_user_registration():
    # Test user creation
    pass

def test_post_creation():
    # Test post CRUD
    pass
```

## 📈 Scaling Recommendations

### When You Grow

1. **Database**: Migrate from SQLite to PostgreSQL
2. **File Storage**: Use cloud storage (AWS S3, Cloudinary)
3. **Caching**: Implement Redis for session and data caching
4. **CDN**: Use a CDN for static files
5. **Load Balancing**: Multiple application servers
6. **Background Tasks**: Use Celery for async tasks
7. **Search**: Integrate Elasticsearch for better search
8. **Monitoring**: Add application monitoring (Sentry, New Relic)

## 🐛 Troubleshooting

### Common Issues

**Issue**: "No module named 'app'"
- **Solution**: Make sure you're in the project directory and virtual environment is activated

**Issue**: Database errors
- **Solution**: Run `flask init-db` to create tables

**Issue**: File upload fails
- **Solution**: Check file size limits and ensure uploads directory exists

**Issue**: Static files not loading
- **Solution**: Check that paths in templates are correct: `url_for('static', filename='...')`

## 🤝 Contributing

This is an educational project. Feel free to:
- Fork and modify for your own use
- Report bugs or suggest features
- Improve documentation
- Add new features

## 📄 License

This project is open source and available for educational purposes.

## 👨‍💻 Support

For questions or issues:
- Check the troubleshooting section
- Review the code comments
- Examine the example implementations

## 🎯 Future Enhancements

Potential features to add:
- [ ] Email notifications
- [ ] Real-time chat
- [ ] Video uploads
- [ ] Study groups/communities
- [ ] Bookmarks/saved posts
- [ ] Advanced search filters
- [ ] Analytics dashboard
- [ ] Mobile app (React Native/Flutter)
- [ ] API for third-party integrations
- [ ] Gamification (badges, points)

## 📚 Learning Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Flask-Login Documentation](https://flask-login.readthedocs.io/)
- [WTForms Documentation](https://wtforms.readthedocs.io/)

---

**Built with ❤️ for students, by students**

Happy learning and sharing! 🎓
