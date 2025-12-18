from flask import Blueprint, render_template, abort, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models import User, Comment
from app.extensions import db

bp = Blueprint('admin', __name__)

@bp.before_request
@login_required
def require_admin():
    if not current_user.is_admin:
        abort(403)

@bp.route('/')
def index():
    users = User.query.all()
    comments = Comment.query.order_by(Comment.created_at.desc()).limit(50).all()
    return render_template('admin/index.html', users=users, comments=comments)

@bp.route('/user/<int:user_id>/delete', methods=['POST'])
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.is_admin:
         flash('Cannot delete admin')
         return redirect(url_for('admin.index'))
         
    db.session.delete(user)
    db.session.commit()
    flash('User deleted')
    return redirect(url_for('admin.index'))

@bp.route('/comment/<int:comment_id>/delete', methods=['POST'])
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    db.session.delete(comment)
    db.session.commit()
    flash('Comment deleted')
    return redirect(url_for('admin.index'))
