from flask import Blueprint, render_template, request, session, redirect, url_for, abort, send_from_directory, current_app
from flask_login import login_required, current_user
from sqlalchemy import text
from ..extensions import db
from ..models import Work, Follow, History, User, Comment, Image, WorkLike, Bookmark
import config
import os
from flask_babel import gettext as _

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 24
    works = Work.query.order_by(Work.id.desc()).paginate(page=page, per_page=per_page, error_out=False).items
    return render_template('index.html', works=works)

@bp.route('/search')
def search():
    query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = 24
    if query:
        term = f"%{query}%"
        works = Work.query.filter(
            (Work.tags.like(term)) |
            (Work.title.like(term)) |
            (Work.user_name.like(term))
        ).order_by(Work.id.desc()).paginate(page=page, per_page=per_page, error_out=False).items
    else:
        works = Work.query.order_by(Work.id.desc()).paginate(page=page, per_page=per_page, error_out=False).items
    return render_template('index.html', works=works, search=query)

@bp.route('/ranking')
def ranking():
    works = Work.query.order_by(Work.view_count.desc()).limit(50).all()
    return render_template('ranking.html', works=works)

@bp.route('/following')
@login_required
def following_feed():
    # SELECT w.* FROM works w JOIN follows f ON w.user_id = f.followed_user_id WHERE f.follower_id = ? ORDER BY w.id DESC LIMIT 50
    works = db.session.query(Work).join(Follow, Work.user_id == Follow.followed_user_id)\
        .filter(Follow.follower_id == current_user.id)\
        .order_by(Work.id.desc())\
        .limit(50).all()
    return render_template('index.html', works=works, title=_("Following Feed"))

@bp.route('/history')
@login_required
def history():
    # SELECT w.* FROM works w JOIN history h ON w.id = h.work_id WHERE h.user_id = ? ORDER BY h.viewed_at DESC LIMIT 50
    works = db.session.query(Work).join(History, Work.id == History.work_id)\
        .filter(History.user_id == current_user.id)\
        .order_by(History.viewed_at.desc())\
        .limit(50).all()
    return render_template('index.html', works=works, title=_("History"))

@bp.route('/users/<int:user_id>')
def user(user_id):
    # Using raw sql for compatibility or SQLAlchemy query
    # existing: SELECT user_name FROM works WHERE user_id = ? LIMIT 1
    work = Work.query.filter_by(user_id=user_id).first()
    if not work:
        abort(404)

    user_info = {'user_name': work.user_name}

    is_followed = False
    if current_user.is_authenticated:
        if Follow.query.filter_by(follower_id=current_user.id, followed_user_id=user_id).first():
            is_followed = True

    novels = Work.query.filter_by(user_id=user_id, work_type='Novel').order_by(Work.id.desc()).all()
    illusts = Work.query.filter(Work.user_id==user_id, Work.work_type!='Novel').order_by(Work.id.desc()).all()

    return render_template('user.html', user=user_info, user_id=user_id, novels=novels, illusts=illusts, is_followed=is_followed)

@bp.route('/view/<int:work_id>')
def view_work(work_id):
    work = Work.query.get(work_id)
    if not work: abort(404)

    # Increment view count
    try:
        Work.query.filter_by(id=work_id).update({'view_count': Work.view_count + 1})
        if current_user.is_authenticated:
            # Upsert history
            hist = History.query.get((current_user.id, work_id))
            if hist:
                hist.viewed_at = db.func.now()
            else:
                db.session.add(History(user_id=current_user.id, work_id=work_id))
        db.session.commit()
    except Exception as e:
        print(f"Error updating view count: {e}")
        db.session.rollback()

    is_liked = False
    is_bookmarked = False
    if current_user.is_authenticated:
        is_liked = WorkLike.query.get((current_user.id, work_id)) is not None
        is_bookmarked = Bookmark.query.get((current_user.id, work_id)) is not None

    comments = db.session.query(Comment, User.username).join(User, Comment.user_id == User.id)\
        .filter(Comment.work_id == work_id).order_by(Comment.created_at.desc()).all()

    # Comments result needs to be adaptable to template. Template expects objects with properties.
    # The query returns tuples (Comment, username).
    # We can reconstruct it or pass as is if template handles it.
    # Looking at `illust.html` (implied), it iterates comments.
    # existing: SELECT c.*, u.username ...
    # Template usage: comment.username, comment.content
    # The query above returns a tuple. We need to attach username to comment object or transform it.
    comments_formatted = []
    for c, u in comments:
        c.username = u
        comments_formatted.append(c)

    images = Image.query.filter_by(work_id=work_id).order_by(Image.p_num.asc()).all()

    related_works = []
    if work.tags:
        tags = work.tags.split(' ')[:2]
        if tags:
            conds = [Work.tags.like(f"%{t.strip()}%") for t in tags if t.strip()]
            if conds:
                from sqlalchemy import or_
                related_works = Work.query.filter(or_(*conds), Work.id != work_id)\
                    .order_by(db.func.random()).limit(6).all()

    if work.work_type != 'Novel':
        if not images and work.file_path:
            images = [{'file_path': work.file_path}]
        return render_template('illust.html', work=work, images=images, is_liked=is_liked, is_bookmarked=is_bookmarked, comments=comments_formatted, related_works=related_works)

    file_full_path = os.path.join(config.DATA_DIR, work.file_path)
    content = ""
    if os.path.exists(file_full_path):
        try:
            with open(file_full_path, 'r', encoding='utf-8') as f: content = f.read()
        except:
            try:
                with open(file_full_path, 'r', encoding='gb18030') as f: content = f.read()
            except: content = _("Decode Error.")
    else: content = _("File Missing.")

    lines = content.splitlines()
    return render_template('novel.html', work=work, lines=lines, images=images, is_liked=is_liked, is_bookmarked=is_bookmarked, comments=comments_formatted, related_works=related_works)

@bp.route('/series/<path:series_title>')
def view_series(series_title):
    works = Work.query.filter_by(series_title=series_title).all()
    if not works: abort(404)

    import re
    def sort_key(w):
        try: return int(re.search(r'(\d+)', w.series_order or "").group(1))
        except: return 999999

    return render_template('series.html', series_title=series_title, works=sorted(works, key=sort_key))

@bp.route('/set_lang/<string:lang_code>')
def set_lang(lang_code):
    if lang_code in ['en', 'zh']: session['lang'] = lang_code
    return redirect(request.referrer or url_for('main.index'))

@bp.route('/files/<path:filename>')
def serve_file(filename):
    return send_from_directory(config.DATA_DIR, filename)

@bp.route('/thumbs/<path:filename>')
def serve_thumb(filename):
    if config.THUMBS_DIR:
        return send_from_directory(config.THUMBS_DIR, filename)
    else:
        return send_from_directory(config.DATA_DIR, filename)
