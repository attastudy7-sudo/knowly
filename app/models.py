from datetime import datetime
from flask import current_app, url_for
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

    @property
    def profile_picture_url(self):
        """Return the full Cloudinary URL for the user's profile picture."""
        if self.profile_picture and self.profile_picture != 'default.jpg':
            cloud_name = current_app.config['CLOUDINARY_CLOUD_NAME']
            return f"https://res.cloudinary.com/{cloud_name}/image/upload/w_200,h_200,c_fill/{self.profile_picture}"
        return url_for('static', filename='images/default.jpg')

    def __repr__(self):
        return f'<User {self.username}>'


class Post(db.Model):
    __tablename__ = 'post'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Updated Foreign key to 'profiles.id'
    user_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=True)
    has_document = db.Column(db.Boolean, default=False)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)

    comments = db.relationship('Comment', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    document = db.relationship('Document', backref='post', uselist=False)

    def like_count(self):
        """Return the count of likes for this post."""
        return self.likes.count()

    def comment_count(self):
        """Return the count of comments for this post."""
        return self.comments.count()

    def is_liked_by(self, user):
        """Check if a user has liked this post."""
        return self.likes.filter_by(user_id=user.id).first() is not None

    def __repr__(self):
        return f'<Post {self.title}>'


class Comment(db.Model):
    __tablename__ = 'comment'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Updated Foreign key to 'profiles.id'
    user_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)


class Like(db.Model):
    __tablename__ = 'like'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Updated Foreign key to 'profiles.id'
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

    def has_access(self, user):
        """
        Check if a user has access to this document.
        Free documents: everyone has access.
        Paid documents: only if user has purchased it.
        """
        if not self.is_paid:
            return True

        purchase = Purchase.query.filter_by(
            user_id=user.id,
            document_id=self.id,
            status='completed'
        ).first()

        return purchase is not None

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
        """Update the post count for this subject."""
        self.post_count = self.posts.count()
        db.session.commit()

    def __repr__(self):
        return f'<Subject {self.name}>'