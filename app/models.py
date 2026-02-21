from datetime import datetime
import urllib.parse
from flask import current_app
from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


@login_manager.user_loader
def load_user(user_id):
    """Required by Flask-Login to load a user from the session."""
    return User.query.get(int(user_id))


# Association table for many-to-many follow relationship
followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('profiles.id'), primary_key=True),
    db.Column('followed_id', db.Integer, db.ForeignKey('profiles.id'), primary_key=True)
)

# Palette cycled deterministically by username so each user always gets the same color
_AVATAR_COLORS = [
    "#667eea", "#764ba2", "#f093fb", "#f5576c",
    "#4facfe", "#43e97b", "#fa709a", "#a18cd1",
]


def _initials_avatar_url(username: str, full_name: str | None) -> str:
    """
    Generate a data-URI SVG avatar from the user's initials.
    Requires no files, no CDN, and works in any <img src="">.
    """
    if full_name and full_name.strip():
        parts = full_name.strip().split()
        initials = (parts[0][0] + parts[-1][0]).upper() if len(parts) >= 2 else parts[0][:2].upper()
    else:
        initials = username[:2].upper()

    color = _AVATAR_COLORS[sum(ord(c) for c in username) % len(_AVATAR_COLORS)]

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">'
        f'<circle cx="100" cy="100" r="100" fill="{color}"/>'
        f'<text x="100" y="100" font-family="Inter,Arial,sans-serif" font-size="80" '
        f'font-weight="700" fill="white" text-anchor="middle" '
        f'dominant-baseline="central" letter-spacing="-2">{initials}</text>'
        f'</svg>'
    )
    return f"data:image/svg+xml,{urllib.parse.quote(svg)}"


class User(UserMixin, db.Model):
    """
    User model - represents a student on the platform.
    Table renamed to 'profiles' to avoid Turso/SQL reserved word conflicts.
    """
    __tablename__ = 'profiles'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # Profile information
    full_name = db.Column(db.String(120))
    bio = db.Column(db.Text)
    profile_picture = db.Column(db.String(200), default='default.jpg')

    # Account metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    # Relationships
    posts = db.relationship('Post', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    # Self-referential many-to-many for follows
    following = db.relationship(
        'User',
        secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'),
        lazy='dynamic'
    )

    purchases = db.relationship('Purchase', backref='buyer', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def follow(self, user):
        if not self.is_following(user):
            self.following.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.following.remove(user)

    def is_following(self, user):
        return self.following.filter(followers.c.followed_id == user.id).count() > 0

    def followers_count(self):
        """Return the count of users following this user."""
        return self.followers.count()

    def following_count(self):
        """Return the count of users this user is following."""
        return self.following.count()

    # ── Gamification stubs (not yet implemented) ──────────────────────────────
    @property
    def streak_days(self):
        """Stub — daily streak feature not yet implemented."""
        return 0

    @property
    def xp_points(self):
        """Stub — XP system not yet implemented."""
        return 0
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def profile_picture_url(self) -> str:
        """
        Return the user's profile picture URL.

        - Has uploaded a picture → Cloudinary URL with fill crop
        - No picture (new account / default.jpg) → SVG initials avatar
        """
        if self.profile_picture and self.profile_picture != 'default.jpg':
            cloud_name = current_app.config['CLOUDINARY_CLOUD_NAME']
            return (
                f"https://res.cloudinary.com/{cloud_name}"
                f"/image/upload/w_200,h_200,c_fill/{self.profile_picture}"
            )
        # Fallback: generated initials avatar — no static file required
        return _initials_avatar_url(self.username, self.full_name)

    def __repr__(self):
        return f'<User {self.username}>'


class Post(db.Model):
    __tablename__ = 'post'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=True)
    has_document = db.Column(db.Boolean, default=False)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)

    comments = db.relationship('Comment', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    # FIXED: use back_populates + explicit foreign_keys to avoid ambiguity
    document = db.relationship('Document', back_populates='post', foreign_keys=[document_id], uselist=False)
    status = db.Column(db.String(20), nullable=False, default='pending')
    rejection_reason = db.Column(db.Text, nullable=True)

    def like_count(self):
        return self.likes.count()

    def comment_count(self):
        return self.comments.count()

    def is_liked_by(self, user):
        return self.likes.filter_by(user_id=user.id).first() is not None

    def is_bookmarked_by(self, user):
        """Stub — bookmark feature not yet implemented."""
        return False

    def __repr__(self):
        return f'<Post {self.title}>'


class Comment(db.Model):
    __tablename__ = 'comment'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)


class Like(db.Model):
    __tablename__ = 'like'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='unique_like'),)


class Purchase(db.Model):
    __tablename__ = 'purchase'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50))
    transaction_id = db.Column(db.String(200), unique=True)
    status = db.Column(db.String(50), default='pending')
    purchased_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    document = db.relationship('Document', backref='purchases')


class Notification(db.Model):
    __tablename__ = 'notification'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    message = db.Column(db.String(300), nullable=False)
    notification_type = db.Column(db.String(50))
    link = db.Column(db.String(300))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    user = db.relationship('User', backref='notifications')


class Document(db.Model):
    __tablename__ = 'document'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(300), nullable=False)
    original_filename = db.Column(db.String(300), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(50))
    file_size = db.Column(db.Integer)
    is_paid = db.Column(db.Boolean, default=False)
    price = db.Column(db.Float, default=0.0)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    download_count = db.Column(db.Integer, default=0)

    # FIXED: explicit reverse side of the Post.document relationship
    post = db.relationship('Post', back_populates='document', foreign_keys='Post.document_id', uselist=False)

    def has_access(self, user):
        """
        Free documents: everyone has access.
        Paid documents: only if user has a completed purchase.
        """
        if not self.is_paid:
            return True
        return Purchase.query.filter_by(
            user_id=user.id,
            document_id=self.id,
            status='completed'
        ).first() is not None

    def __repr__(self):
        return f'<Document {self.original_filename}>'


class Subject(db.Model):
    __tablename__ = 'subject'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    slug = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50), default='book')
    color = db.Column(db.String(7), default='#6366f1')
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    post_count = db.Column(db.Integer, default=0)
    posts = db.relationship('Post', backref='subject', lazy='dynamic')

    def update_post_count(self):
        self.post_count = self.posts.count()
        db.session.commit()

    def __repr__(self):
        return f'<Subject {self.name}>'