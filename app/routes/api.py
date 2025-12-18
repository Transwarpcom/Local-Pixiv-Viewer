from flask import Blueprint, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from ..extensions import db
from ..models import Work, WorkLike, Bookmark, Follow, Comment
import config
from urllib.parse import quote

bp = Blueprint('api', __name__, url_prefix='/api')

@bp.route('/load_more')
def api_load_more():
    page = request.args.get('page', 1, type=int)
    query = request.args.get('q', '')

    if query:
        term = f"%{query}%"
        works = Work.query.filter(
            (Work.tags.like(term)) |
            (Work.title.like(term)) |
            (Work.user_name.like(term))
        ).order_by(Work.id.desc()).paginate(page=page, per_page=24, error_out=False).items
    else:
        works = Work.query.order_by(Work.id.desc()).paginate(page=page, per_page=24, error_out=False).items

    data = []
    for work in works:
        item = {
            'id': work.id,
            'title': work.title,
            'user_id': work.user_id,
            'user_name': work.user_name,
            'work_type': work.work_type,
            'page_count': work.page_count,
            'link_url': f"/view/{work.id}",
            'img_src': "",
            'tags': work.tags
        }
        raw = work.cover_path if (work.work_type == 'Novel' and work.cover_path) else work.file_path
        if raw:
            item['img_src'] = f"{config.THUMBS_URL_PREFIX}{quote(raw, safe='/')}"
        data.append(item)
    return jsonify(data)

@bp.route('/like/<int:work_id>', methods=['POST'])
@login_required
def api_like(work_id):
    like = WorkLike.query.get((current_user.id, work_id))
    if like:
        db.session.delete(like)
        status = 'unliked'
    else:
        like = WorkLike(user_id=current_user.id, work_id=work_id)
        db.session.add(like)
        status = 'liked'
    db.session.commit()
    return jsonify({'status': status})

@bp.route('/bookmark/<int:work_id>', methods=['POST'])
@login_required
def api_bookmark(work_id):
    bm = Bookmark.query.get((current_user.id, work_id))
    if bm:
        db.session.delete(bm)
        status = 'removed'
    else:
        bm = Bookmark(user_id=current_user.id, work_id=work_id)
        db.session.add(bm)
        status = 'added'
    db.session.commit()
    return jsonify({'status': status})

@bp.route('/follow/<int:user_id>', methods=['POST'])
@login_required
def api_follow(user_id):
    follow = Follow.query.get((current_user.id, user_id))
    if follow:
        db.session.delete(follow)
        status = 'unfollowed'
    else:
        follow = Follow(follower_id=current_user.id, followed_user_id=user_id)
        db.session.add(follow)
        status = 'followed'
    db.session.commit()
    return jsonify({'status': status})

@bp.route('/comment/<int:work_id>', methods=['POST'])
@login_required
def api_comment(work_id):
    c = request.form.get('content')
    if c:
        comment = Comment(user_id=current_user.id, work_id=work_id, content=c)
        db.session.add(comment)
        db.session.commit()
    return redirect(url_for('main.view_work', work_id=work_id))
