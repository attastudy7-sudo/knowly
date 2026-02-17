# 🏗️ EduShare - Architecture & Design

This document explains the technical architecture, design decisions, and how all the pieces fit together.

## 📐 High-Level Architecture

```
┌─────────────────────────────────────────┐
│          Browser (Client)               │
│  HTML Templates + CSS + JavaScript      │
└──────────────┬──────────────────────────┘
               │ HTTP Requests/Responses
               ▼
┌─────────────────────────────────────────┐
│         Flask Application               │
│  ┌───────────────────────────────────┐  │
│  │   Blueprints (Modular Routes)     │  │
│  │  • auth   • posts   • users       │  │
│  │  • payments                        │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │   Business Logic Layer            │  │
│  │  • Forms   • Models   • Utils     │  │
│  └───────────────────────────────────┘  │
└──────────────┬──────────────────────────┘
               │ SQLAlchemy ORM
               ▼
┌─────────────────────────────────────────┐
│       Database (SQLite/PostgreSQL)      │
│  • Users  • Posts  • Documents          │
│  • Comments  • Likes  • Follows         │
└─────────────────────────────────────────┘
```

---

## 🧩 Component Breakdown

### 1. **Application Factory** (`app/__init__.py`)

**Purpose:** Creates and configures the Flask application instance.

**Why this pattern?**
- Allows multiple app instances (useful for testing)
- Centralizes configuration
- Clean separation of concerns

**Key components:**
```python
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(posts_bp)
    # ...
```

### 2. **Blueprints** (Modular Routes)

**What are blueprints?**
- Flask's way of organizing routes into modules
- Each blueprint handles a specific feature area

**Our blueprints:**

#### `auth/` - Authentication
- Routes: `/auth/login`, `/auth/signup`, `/auth/logout`
- Handles user registration and session management
- Uses Flask-Login for session handling

#### `posts/` - Posts & Documents
- Routes: `/posts/create`, `/posts/<id>`, `/posts/<id>/edit`
- CRUD operations for posts
- File upload handling
- Like and comment functionality

#### `users/` - User Profiles & Social
- Routes: `/users/profile/<username>`, `/users/search`
- Profile management
- Follow/unfollow system
- User search

#### `payments/` - Payment Integration
- Routes: `/payments/checkout/<id>`, `/payments/webhook`
- Prepared for Stripe/Paystack integration
- Currently shows placeholder pages

#### `main` - Home Routes
- Routes: `/`, `/explore`, `/about`
- Feed algorithm
- Landing pages

### 3. **Database Layer** (`app/models.py`)

**ORM: SQLAlchemy**
- Object-Relational Mapping
- Write Python instead of SQL
- Automatic migrations (with Flask-Migrate if needed)

**Models:**

```python
User ──┬── posts (one-to-many)
       ├── comments (one-to-many)
       ├── likes (one-to-many)
       ├── following (many-to-many self-referential)
       └── purchases (one-to-many)

Post ──┬── author (many-to-one to User)
       ├── document (one-to-one)
       ├── comments (one-to-many)
       └── likes (one-to-many)

Document ── post (one-to-one)

Comment ── author, post (many-to-one)

Like ── user, post (many-to-one with unique constraint)
```

**Relationships explained:**

- **One-to-Many:** A user has many posts, but each post has one author
- **Many-to-Many:** A user can follow many users and be followed by many
- **One-to-One:** A post can have one document attached

### 4. **Forms Layer** (`app/forms.py`)

**Purpose:** Validate user input and protect against CSRF attacks.

**WTForms features:**
- Field validation
- Custom validators
- CSRF protection (automatic token generation)
- Error messages

**Example:**
```python
class CreatePostForm(FlaskForm):
    title = StringField('Title', validators=[
        DataRequired(),
        Length(min=3, max=200)
    ])
    # Automatically validates before form.validate_on_submit()
```

### 5. **Template Layer** (`app/templates/`)

**Template Engine: Jinja2**
- Server-side rendering
- Template inheritance
- Variables, loops, conditionals

**Structure:**
```
templates/
├── base.html           # Base layout
├── index.html          # Extends base
├── auth/
│   ├── login.html      # Extends base
│   └── signup.html     # Extends base
└── ...
```

**Template inheritance:**
```html
<!-- base.html -->
<html>
  <head>...</head>
  <body>
    <nav>...</nav>
    {% block content %}{% endblock %}
  </body>
</html>

<!-- index.html -->
{% extends "base.html" %}
{% block content %}
  <!-- Your content here -->
{% endblock %}
```

### 6. **Static Files** (`app/static/`)

**CSS:**
- Mobile-first approach
- CSS variables for theming
- Responsive design (Flexbox/Grid)
- No framework dependencies

**JavaScript:**
- Vanilla JS (no jQuery)
- Progressive enhancement
- Minimal dependencies

---

## 🔐 Security Architecture

### Authentication Flow

```
1. User submits login form
   ↓
2. CSRF token validated (WTForms)
   ↓
3. Password checked (Werkzeug hash)
   ↓
4. Session created (Flask-Login)
   ↓
5. User ID stored in session cookie
```

### Password Security

- **Hashing:** Werkzeug's `generate_password_hash()`
- **Algorithm:** pbkdf2:sha256
- **Salt:** Automatic (unique per password)
- **Never stored in plain text**

### CSRF Protection

- Every form has a hidden CSRF token
- Token validated on submission
- Prevents cross-site request forgery

### File Upload Security

```python
# 1. Validate file extension
allowed_extensions = {'pdf', 'docx', 'pptx', 'txt'}

# 2. Generate unique filename
filename = uuid.uuid4().hex + '.' + extension

# 3. Limit file size
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
```

---

## 📊 Data Flow Examples

### Creating a Post

```
User fills form → Submit
    ↓
CSRF validation (WTForms)
    ↓
Form validation (title, description)
    ↓
File upload (if document)
    ├── Generate unique filename
    ├── Save to disk
    └── Create Document record
    ↓
Create Post record
    ↓
Commit to database
    ↓
Redirect to feed
```

### Like System

```
User clicks like button
    ↓
POST request to /posts/<id>/like
    ↓
Check if already liked
    ├── Yes → Remove Like record (unlike)
    └── No → Create Like record
    ↓
Update database
    ↓
Redirect back
```

### Feed Algorithm

```python
def feed():
    # Get IDs of users you follow
    following_ids = [user.id for user in current_user.following.all()]
    
    # Query posts from followed users + own posts
    posts = Post.query.filter(
        or_(
            Post.user_id.in_(following_ids),
            Post.user_id == current_user.id
        )
    ).order_by(Post.created_at.desc())  # Newest first
    
    return posts
```

---

## 🎨 Design Patterns Used

### 1. **Application Factory Pattern**
- **What:** Function that creates app instance
- **Why:** Testing, multiple configurations
- **Where:** `app/__init__.py`

### 2. **Blueprint Pattern**
- **What:** Modular route organization
- **Why:** Separation of concerns, scalability
- **Where:** `app/auth/`, `app/posts/`, etc.

### 3. **Repository Pattern (via ORM)**
- **What:** Abstraction over data access
- **Why:** Database independence
- **Where:** SQLAlchemy models

### 4. **Template Inheritance**
- **What:** Base template with blocks
- **Why:** DRY (Don't Repeat Yourself)
- **Where:** All templates extend `base.html`

### 5. **Form Object Pattern**
- **What:** Encapsulate form logic
- **Why:** Validation, CSRF protection
- **Where:** `app/forms.py`

---

## 🚀 Performance Optimizations

### 1. **Database Queries**
- Lazy loading for relationships
- Pagination for large result sets
- Indexes on frequently queried fields

```python
# Pagination
posts = Post.query.paginate(
    page=page,
    per_page=10,
    error_out=False
)
```

### 2. **Static File Serving**
- Browser caching headers
- Minification (in production)
- CDN for static files (recommended for scale)

### 3. **Mobile Optimization**
- Small file sizes
- Responsive images
- Touch-optimized UI

---

## 🔄 Request Lifecycle

```
1. Browser sends HTTP request
   ↓
2. Flask receives request
   ↓
3. URL routing matches pattern
   ↓
4. @login_required decorator (if present)
   ├── Check session
   ├── Yes → Continue
   └── No → Redirect to login
   ↓
5. View function executes
   ├── Process form data
   ├── Query database
   └── Business logic
   ↓
6. Render template
   ├── Pass context variables
   └── Jinja2 processes template
   ↓
7. Return HTTP response
```

---

## 💾 Database Schema

### Users Table
```sql
CREATE TABLE user (
    id INTEGER PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(120),
    bio TEXT,
    profile_picture VARCHAR(200),
    created_at DATETIME NOT NULL,
    is_active BOOLEAN
);
```

### Posts Table
```sql
CREATE TABLE post (
    id INTEGER PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME,
    user_id INTEGER NOT NULL,
    has_document BOOLEAN,
    document_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (document_id) REFERENCES document(id)
);
```

### Followers Association Table
```sql
CREATE TABLE followers (
    follower_id INTEGER,
    followed_id INTEGER,
    PRIMARY KEY (follower_id, followed_id),
    FOREIGN KEY (follower_id) REFERENCES user(id),
    FOREIGN KEY (followed_id) REFERENCES user(id)
);
```

---

## 🧪 Testing Strategy (Future)

### Unit Tests
- Test individual functions
- Mock database calls
- Test form validation

### Integration Tests
- Test route endpoints
- Test database operations
- Test file uploads

### Example:
```python
def test_create_post():
    with app.test_client() as client:
        # Login
        client.post('/auth/login', data={...})
        
        # Create post
        response = client.post('/posts/create', data={
            'title': 'Test Post',
            'description': 'Test'
        })
        
        assert response.status_code == 302  # Redirect
        assert Post.query.filter_by(title='Test Post').first()
```

---

## 📈 Scaling Considerations

### Current Limitations (SQLite)
- Single file database
- Not ideal for concurrent writes
- No built-in replication

### Migration Path

**Small Scale (< 1000 users):**
- Current setup is fine
- SQLite works well

**Medium Scale (1K - 100K users):**
- Migrate to PostgreSQL
- Add Redis for caching
- Use task queue (Celery)

**Large Scale (100K+ users):**
- Multiple app servers (load balancer)
- Database replication
- CDN for static files
- Object storage (S3) for uploads
- Microservices architecture

---

## 🔌 Extension Points

### Easy to Add:

1. **Email notifications**
   - Flask-Mail already configured
   - Add email templates
   - Send on user actions

2. **Search improvements**
   - Elasticsearch integration
   - Full-text search
   - Filters and facets

3. **Real-time features**
   - Flask-SocketIO for WebSockets
   - Live notifications
   - Chat system

4. **API**
   - Flask-RESTful
   - JWT authentication
   - Mobile app integration

5. **Admin panel**
   - Flask-Admin
   - User management
   - Content moderation

---

## 🛠️ Development Workflow

```
1. Create feature branch
2. Write code
3. Test locally
4. Create pull request
5. Review
6. Merge to main
7. Deploy
```

**Recommended tools:**
- Git for version control
- Virtual environment for isolation
- Flask debug mode for development
- Gunicorn for production

---

## 📝 Code Style

- PEP 8 for Python
- Descriptive variable names
- Comments for complex logic
- Docstrings for functions
- Type hints (optional)

---

**This architecture is designed to be:**
- ✅ Easy to understand for beginners
- ✅ Scalable for growth
- ✅ Secure by default
- ✅ Maintainable long-term
