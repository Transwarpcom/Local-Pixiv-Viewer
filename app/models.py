from .extensions import db
from flask_login import UserMixin
from datetime import datetime

class Work(db.Model):
    __tablename__ = 'works'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, index=True)
    user_name = db.Column(db.String)
    title = db.Column(db.String)
    tags = db.Column(db.String, index=True)
    work_type = db.Column(db.String)
    series_title = db.Column(db.String)
    series_order = db.Column(db.String)
    file_path = db.Column(db.String)
    cover_path = db.Column(db.String)
    page_count = db.Column(db.Integer, default=1)
    view_count = db.Column(db.Integer, default=0, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Image(db.Model):
    __tablename__ = 'images'
    work_id = db.Column(db.Integer, primary_key=True)
    p_num = db.Column(db.Integer, primary_key=True)
    file_path = db.Column(db.String)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String, unique=True, nullable=False)
    password_hash = db.Column(db.String, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    avatar = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class WorkLike(db.Model):
    __tablename__ = 'work_likes'
    user_id = db.Column(db.Integer, primary_key=True)
    work_id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Bookmark(db.Model):
    __tablename__ = 'bookmarks'
    user_id = db.Column(db.Integer, primary_key=True)
    work_id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer)
    work_id = db.Column(db.Integer)
    content = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Follow(db.Model):
    __tablename__ = 'follows'
    follower_id = db.Column(db.Integer, primary_key=True)
    followed_user_id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class History(db.Model):
    __tablename__ = 'history'
    user_id = db.Column(db.Integer, primary_key=True)
    work_id = db.Column(db.Integer, primary_key=True)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)
