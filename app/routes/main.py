import os
from flask import Blueprint, render_template, request, current_app, send_from_directory, abort, flash, session, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import desc, asc
from app.models import Work, History, User, work_likes, bookmarks, Series
from app.extensions import db

bp = Blueprint('main', __name__)

@bp.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['ITEMS_PER_PAGE']
    works = Work.query.order_by(desc(Work.created_at)).paginate(page=page, per_page=per_page)
    return render_template('main/index.html', works=works)

@bp.route('/work/<int:work_id>')
def detail(work_id):
    work = Work.query.get_or_404(work_id)
    
    # Update view count
    work.view_count += 1
    db.session.commit()
    
    # Record history if logged in
    if current_user.is_authenticated:
        hist = History.query.filter_by(user_id=current_user.id, work_id=work_id).first()
        if hist:
            hist.viewed_at = db.func.now()
        else:
            hist = History(user_id=current_user.id, work_id=work_id)
            db.session.add(hist)
        db.session.commit()
    
    novel_content = None
    if work.work_type == 'Novel' and work.file_path:
        # Read novel content
        # Prevent path traversal is handled by data_dir joining in indexer, but let's be safe
        full_path = os.path.join(current_app.config['DATA_DIR'], work.file_path)
        if os.path.exists(full_path):
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    novel_content = f.read()
            except Exception as e:
                novel_content = f"Error reading file: {e}"
        else:
            novel_content = "File not found."

    previous_in_series = None
    next_in_series = None
    if work.series_id:
        previous_in_series = Work.query.filter(
            Work.series_id == work.series_id,
            Work.series_order < work.series_order
        ).order_by(desc(Work.series_order)).first()

        next_in_series = Work.query.filter(
            Work.series_id == work.series_id,
            Work.series_order > work.series_order
        ).order_by(asc(Work.series_order)).first()
            
    return render_template('main/detail.html', work=work, novel_content=novel_content,
                           previous_in_series=previous_in_series, next_in_series=next_in_series)

@bp.route('/series/<int:series_id>')
def series_detail(series_id):
    series = Series.query.get_or_404(series_id)
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['ITEMS_PER_PAGE']
    works = series.works.order_by(asc(Work.series_order)).paginate(page=page, per_page=per_page)
    return render_template('main/series_detail.html', series=series, works=works)

@bp.route('/ranking')
def ranking():
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['ITEMS_PER_PAGE']
    works = Work.query.order_by(desc(Work.view_count)).paginate(page=page, per_page=per_page)
    return render_template('main/ranking.html', works=works)

@bp.route('/search')
def search():
    q = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['ITEMS_PER_PAGE']
    
    query = Work.query
    if q:
        query = query.filter(Work.title.contains(q) | Work.tags.contains(q) | Work.artist_name.contains(q))
        
    works = query.order_by(desc(Work.created_at)).paginate(page=page, per_page=per_page)
    return render_template('main/search.html', works=works, q=q)

@bp.route('/history')
@login_required
def history():
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['ITEMS_PER_PAGE']
    history_query = History.query.filter_by(user_id=current_user.id).order_by(desc(History.viewed_at))
    pagination = history_query.paginate(page=page, per_page=per_page)
    return render_template('main/history.html', pagination=pagination)

@bp.route('/data/<path:filename>')
def serve_data(filename):
    return send_from_directory(current_app.config['DATA_DIR'], filename)

@bp.route('/thumbs/<path:filename>')
def serve_thumbs(filename):
    return send_from_directory(current_app.config['THUMBS_DIR'], filename)

@bp.route('/set_language/<lang_code>')
def set_language(lang_code):
    if lang_code in ['zh', 'en']:
        session['locale'] = lang_code
    return redirect(request.referrer or url_for('main.index'))
