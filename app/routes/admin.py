from flask import Blueprint, render_template, abort, redirect, url_for
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Work, User, Comment, WorkLike, Bookmark, Follow
import config
import shutil
from flask_babel import gettext as _

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/')
@login_required
def admin():
    if not current_user.is_admin: return abort(403)

    try: t, u, f = shutil.disk_usage(config.DATA_DIR)
    except: t, u, f = 0, 0, 0
    disk = {'total': f"{t//(2**30)}GB", 'used': f"{u//(2**30)}GB", 'free': f"{f//(2**30)}GB", 'percent': (u/t)*100 if t else 0}

    tv = db.session.query(db.func.sum(Work.view_count)).scalar() or 0

    stats = {
        'works': Work.query.count(),
        'users': User.query.count(),
        'comments': Comment.query.count(),
        'views': tv,
        'disk': disk
    }

    users = User.query.order_by(User.id.desc()).limit(50).all()

    # SELECT c.*, u.username, w.title FROM comments c JOIN users u ON c.user_id=u.id JOIN works w ON c.work_id=w.id ORDER BY c.created_at DESC LIMIT 20
    comments = db.session.query(Comment, User.username, Work.title).join(User, Comment.user_id==User.id)\
        .join(Work, Comment.work_id==Work.id).order_by(Comment.created_at.desc()).limit(20).all()

    # Adapt comments for template
    comments_formatted = []
    for c, u, t in comments:
        c.username = u
        c.title = t
        comments_formatted.append(c)

    return render_template('admin/dashboard.html', stats=stats, users=users, comments=comments_formatted)

@bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin: return abort(403)
    if user_id == current_user.id: return _("Cannot delete yourself"), 400

    User.query.filter_by(id=user_id).delete()
    Comment.query.filter_by(user_id=user_id).delete()
    WorkLike.query.filter_by(user_id=user_id).delete()
    Bookmark.query.filter_by(user_id=user_id).delete()
    Follow.query.filter((Follow.follower_id==user_id) | (Follow.followed_user_id==user_id)).delete()

    db.session.commit()
    return redirect(url_for('admin.admin'))

@bp.route('/delete_comment/<int:comment_id>', methods=['POST'])
@login_required
def delete_comment(comment_id):
    if not current_user.is_admin: return abort(403)
    Comment.query.filter_by(id=comment_id).delete()
    db.session.commit()
    return redirect(url_for('admin.admin'))
