from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db, login_manager

# Association tables for interactions
work_likes = db.Table('work_likes',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('work_id', db.Integer, db.ForeignKey('works.id'), primary_key=True)
)

bookmarks = db.Table('bookmarks',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('work_id', db.Integer, db.ForeignKey('works.id'), primary_key=True)
)

# User-User follows
follows = db.Table('follows',
    db.Column('follower_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('followed_id', db.Integer, db.ForeignKey('users.id'), primary_key=True)
)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    comments = db.relationship('Comment', backref='author', lazy='dynamic')
    liked_works = db.relationship('Work', secondary=work_likes, backref=db.backref('liked_by', lazy='dynamic'), lazy='dynamic')
    bookmarked_works = db.relationship('Work', secondary=bookmarks, backref=db.backref('bookmarked_by', lazy='dynamic'), lazy='dynamic')
    
    followed = db.relationship(
        'User', secondary=follows,
        primaryjoin=(follows.c.follower_id == id),
        secondaryjoin=(follows.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic'
    )
    
    # History can be a separate model or a JSON field. 
    # Given the requirements "Interactions: ... history", and typical usage, 
    # a separate model is better for querying/ordering.
    history = db.relationship('History', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Series(db.Model):
    __tablename__ = 'series'
    id = db.Column(db.Integer, primary_key=True) # Pixiv Series ID
    title = db.Column(db.String(255))
    works = db.relationship('Work', backref='series', lazy='dynamic')

class Work(db.Model):
    __tablename__ = 'works'
    id = db.Column(db.Integer, primary_key=True)  # Pixiv ID
    title = db.Column(db.String(255))
    tags = db.Column(db.String(255)) # Comma separated or JSON
    work_type = db.Column(db.String(20)) # Illustration/Novel
    file_path = db.Column(db.String(500)) # Relative path
    cover_path = db.Column(db.String(500)) # Path to cover/thumbnail
    view_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow) # Index time
    
    # Artist info is derived from folder name, we might want to store it if we want to filter by artist
    # But schema didn't explicitly ask for Artist table. 
    # We can store artist_name/artist_id if parsed.
    artist_name = db.Column(db.String(255), nullable=True)
    artist_id = db.Column(db.Integer, nullable=True)

    series_id = db.Column(db.Integer, db.ForeignKey('series.id'), nullable=True)
    series_order = db.Column(db.Integer, nullable=True)

    images = db.relationship('Image', backref='work', lazy='dynamic', cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='work', lazy='dynamic', cascade='all, delete-orphan')

class Image(db.Model):
    __tablename__ = 'images'
    id = db.Column(db.Integer, primary_key=True)
    work_id = db.Column(db.Integer, db.ForeignKey('works.id'), nullable=False)
    p_num = db.Column(db.Integer, nullable=False)
    file_path = db.Column(db.String(500), nullable=False)

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    work_id = db.Column(db.Integer, db.ForeignKey('works.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class History(db.Model):
    __tablename__ = 'history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    work_id = db.Column(db.Integer, db.ForeignKey('works.id'), nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)
