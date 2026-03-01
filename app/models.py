from datetime import datetime, date, timedelta
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
    return f"data:image/svg+xml,{urllib.parse.quote(svg, safe='')}"

class User(UserMixin, db.Model):
    """
    User model - represents a student on the platform.
    Table renamed to 'profiles' to avoid Turso/SQL reserved word conflicts.
    """
    __tablename__ = 'profiles'

    id = db.Column(db.Integer, primary_key=True)
    
    # Property to calculate free attempts left
    @property
    def free_attempts_left(self):
        # Reset free attempts if reset date is in the past
        today = date.today()
        if self.free_quiz_attempts_reset_date and self.free_quiz_attempts_reset_date < today:
            self.free_quiz_attempts = 3
            # Reset to next week (7 days from now)
            self.free_quiz_attempts_reset_date = today + timedelta(days=7)
            db.session.commit()
        
        return self.free_quiz_attempts
    
    def use_free_attempt(self):
        """
        Consume one free attempt. Returns True if successful, False if no attempts left.
        Premium users can take unlimited quizzes - this method returns True for them.
        """
        # Premium users have unlimited attempts
        if self.is_premium or self.has_active_subscription:
            return True
        
        # Check if user has free attempts remaining
        if self.free_attempts_left <= 0:
            return False
        
        # Decrement the free attempts
        self.free_quiz_attempts -= 1
        db.session.commit()
        return True
    
    # Property to check if user has active subscription
    @property
    def has_active_subscription(self):
        if self.subscription_tier != 'free' and self.subscription_end_date:
            return datetime.utcnow() < self.subscription_end_date
        return False
    
    @property
    def profile_picture_url(self):
        if not self.profile_picture or self.profile_picture == 'default.jpg':
            return _initials_avatar_url(self.username, self.full_name)
        if self.profile_picture.startswith('http'):
            return self.profile_picture
        return _initials_avatar_url(self.username, self.full_name)

    @property
    def is_premium(self):
        return self.subscription_tier != 'free' or self.can_access_all_content
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Subscription information
    subscription_tier = db.Column(db.String(20), default='free', nullable=False)
    subscription_start_date = db.Column(db.DateTime)
    subscription_end_date = db.Column(db.DateTime)
    free_quiz_attempts = db.Column(db.Integer, default=3, nullable=False)
    free_quiz_attempts_reset_date = db.Column(db.Date)

    # Profile information
    full_name = db.Column(db.String(120))
    bio = db.Column(db.Text)
    profile_picture = db.Column(db.String(500), default='default.jpg')
    school = db.Column(db.String(200), nullable=True)
    programme = db.Column(db.String(200), nullable=True)

    # Account metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    
    # Premium access - granted by admin to access all paid content
    can_access_all_content = db.Column(db.Boolean, default=False, nullable=False)

    # Streak tracking
    last_activity_date = db.Column(db.Date, nullable=True)
    current_streak = db.Column(db.Integer, default=0, nullable=False)
    longest_streak = db.Column(db.Integer, default=0, nullable=False)
    
    # XP tracking
    xp_points = db.Column(db.Integer, default=0, nullable=False)
    xp_level = db.Column(db.Integer, default=1, nullable=False)
    xp_title = db.Column(db.String(50), nullable=True)

    # Relationships
    posts = db.relationship('Post', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    following = db.relationship(
        'User',
        secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'),
        lazy='dynamic'
    )

    purchases = db.relationship('Purchase', backref='buyer', lazy='dynamic', cascade='all, delete-orphan')
    subscriptions = db.relationship(
        'Subscription', back_populates='user',
        lazy='dynamic', cascade='all, delete-orphan',
        order_by='Subscription.created_at.desc()'
    )

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
        return self.followers.count()

    def following_count(self):
        return self.following.count()

    # ── Streak System ──────────────────────────────────────────────────────────
    def update_streak(self):
        today = date.today()
        if self.last_activity_date is None:
            self.current_streak = 1
        elif self.last_activity_date == today:
            return
        elif self.last_activity_date == today - __import__('datetime').timedelta(days=1):
            self.current_streak += 1
        else:
            self.current_streak = 1
        self.last_activity_date = today
        if self.current_streak > self.longest_streak:
            self.longest_streak = self.current_streak
        db.session.commit()

    @property
    def streak_days(self):
        return self.current_streak

    def add_xp(self, points):
        self.xp_points += points
        db.session.commit()
    
    def get_level(self):
        if self.xp_points < 1000:
            return 1
        elif self.xp_points < 5000:
            return 2
        elif self.xp_points < 15000:
            return 3
        else:
            return 4
    
    def get_title(self):
        level = self.get_level()
        titles = {1: "Beginner", 2: "Intermediate", 3: "Advanced", 4: "Expert"}
        return titles.get(level, "Novice")
    
    def get_next_level_xp(self):
        levels = [1000, 5000, 15000, 25000]
        for threshold in levels:
            if self.xp_points < threshold:
                return threshold
        return None
    
    def get_current_level_xp(self):
        levels = [0, 1000, 5000, 15000]
        level = self.get_level()
        return levels[level - 1] if level <= len(levels) else levels[-1]
    
    def get_xp_progress(self):
        current = self.get_current_level_xp()
        next_lvl = self.get_next_level_xp()
        if next_lvl is None:
            return 100
        span = next_lvl - current
        earned = self.xp_points - current
        return min(100, int((earned / span) * 100)) if span > 0 else 100



class Post(db.Model):
    __tablename__ = 'post'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=True)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=True)
    has_document = db.Column(db.Boolean, default=False)
    # document = db.relationship('Document', foreign_keys=[document_id], backref='post_ref', uselist=False)
    likes = db.relationship('Like', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    status = db.Column(db.String(20), nullable=False, default='pending')
    rejection_reason = db.Column(db.Text, nullable=True)

    def like_count(self):
        return self.likes.count()

    def comment_count(self):
        return self.comments.count()

    def is_liked_by(self, user):
        return self.likes.filter_by(user_id=user.id).first() is not None

    def is_bookmarked_by(self, user):
        return False

    def has_quiz(self):
        """Check if this post has an associated quiz."""
        return hasattr(self, 'quiz') and self.quiz is not None

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
    json_sidecar_path = db.Column(db.String(500), nullable=True)
    is_paid = db.Column(db.Boolean, default=False)
    price = db.Column(db.Float, default=0.0)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    download_count = db.Column(db.Integer, default=0)

    post = db.relationship('Post', foreign_keys='Post.document_id', backref='document', uselist=False, overlaps="post_ref")

    def has_access(self, user):
        if getattr(user, 'is_admin', False) or getattr(user, 'can_access_all_content', False):
            return True
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


# ── Helper: format seconds for display ────────────────────────────────────────
def format_time_taken(seconds: int) -> str:
    """
    Convert integer seconds to a human-readable string.
    Returns MM:SS if under 1 hour, HH:MM:SS otherwise.
    """
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class QuizLeaderboard(db.Model):
    __tablename__ = 'quiz_leaderboard'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)

    # Score stored as percentage (0–100, rounded to 2 dp)
    score_pct = db.Column(db.Float, nullable=False)

    earned_marks = db.Column(db.Float, nullable=False)
    xp_earned = db.Column(db.Integer, nullable=False)

    # Server-calculated elapsed seconds; never trusted from frontend
    time_taken = db.Column(db.Integer, nullable=False)   # seconds

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Public flag - determines if entry is visible on leaderboard
    is_public = db.Column(db.Boolean, default=False, nullable=False)
    
    user = db.relationship('User', backref='leaderboard_entries')
    post = db.relationship('Post', backref=db.backref('leaderboard_entries', cascade='all, delete-orphan'))
    
    __table_args__ = (
        db.UniqueConstraint('post_id', 'user_id', name='unique_leaderboard_entry'),
        db.Index('idx_leaderboard_post_score', 'post_id', 'score_pct', 'time_taken'),
    )

    @property
    def formatted_time(self) -> str:
        return format_time_taken(self.time_taken)

    def __repr__(self):
        return f'<QuizLeaderboard post_id={self.post_id} user_id={self.user_id} score={self.score_pct:.2f}%>'


class QuizData(db.Model):
    __tablename__ = 'quiz_data'
    id          = db.Column(db.Integer, primary_key=True)
    post_id     = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), unique=True, nullable=False)
    questions   = db.Column(db.Text, nullable=False)
    total_marks = db.Column(db.Integer, default=0)
    xp_reward   = db.Column(db.Integer, default=0)
    meta        = db.Column(db.Text)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    post        = db.relationship('Post', backref=db.backref('quiz', uselist=False, cascade='all, delete-orphan'))


class QuizAttempt(db.Model):
    __tablename__ = 'quiz_attempts'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False)

    answers = db.Column(db.Text)

    score_pct = db.Column(db.Float, default=0)  # ONLY percentage field

    earned_marks = db.Column(db.Float, default=0)
    xp_earned = db.Column(db.Integer, default=0)

    timed_out = db.Column(db.Boolean, default=False)

    time_taken = db.Column(db.Integer, default=0)  # seconds, server-calculated

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='quiz_attempts')
    post = db.relationship('Post', backref=db.backref(
        'quiz_attempts',
        cascade='all, delete-orphan'
    ))


class QuizAssessment(db.Model):
    __tablename__ = 'quiz_assessments'

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('quiz_attempts.id', ondelete='CASCADE'), nullable=False)
    question_index = db.Column(db.Integer, nullable=False)
    score = db.Column(db.Float, nullable=False)
    feedback = db.Column(db.Text, nullable=True)
    assessed_by = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=True)
    assessed_at = db.Column(db.DateTime, default=datetime.utcnow)

    attempt = db.relationship('QuizAttempt', backref=db.backref(
        'assessments',
        cascade='all, delete-orphan'
    ))
    assessor = db.relationship('User', backref='assessments')

    __table_args__ = (
        db.UniqueConstraint('attempt_id', 'question_index', name='unique_question_assessment'),
    )

    @property
    def formatted_time(self) -> str:
        return format_time_taken(self.time_taken)

class Subscription(db.Model):
    __tablename__ = 'subscriptions'

    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('profiles.id'), nullable=False, index=True)
    plan_key       = db.Column(db.String(64),  nullable=False)
    plan_name      = db.Column(db.String(128), nullable=False)
    amount_paid    = db.Column(db.Float,  nullable=False, default=0.0)
    currency       = db.Column(db.String(8),   nullable=False, default='GHS')
    payment_method = db.Column(db.String(64),  nullable=True)
    transaction_id = db.Column(db.String(128), nullable=True, unique=True, index=True)
    status         = db.Column(db.String(32),  nullable=False, default='pending')
    started_at     = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at     = db.Column(db.DateTime, nullable=False)
    created_at     = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship('User', back_populates='subscriptions')

    @property
    def is_active(self):
        return self.status == 'active' and self.expires_at > datetime.utcnow()

    def __repr__(self):
        return f'<Subscription {self.plan_key} user={self.user_id} expires={self.expires_at}>'