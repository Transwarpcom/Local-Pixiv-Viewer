import os
from collections import Counter
from flask import Blueprint, render_template, request, current_app, send_from_directory, abort, flash, session, redirect, url_for
from flask_login import login_required, current_user
from sqlalchemy import desc, asc
from sqlalchemy.orm import joinedload
from app.models import Work, History, User, work_likes, bookmarks, Series
from app.extensions import db
import imagehash
from PIL import Image as PILImage
import random
from sqlalchemy.sql.expression import func

bp = Blueprint('main', __name__)

@bp.route('/gacha')
def gacha():
    return render_template('main/gacha.html')

@bp.route('/gacha/pull')
def gacha_pull():
    count = request.args.get('count', 1, type=int)
    if count > 10: count = 10

    works = Work.query.order_by(func.random()).limit(count).all()

    if not works:
        return {'error': 'No works found in database.'}, 404

    results = []
    for work in works:
        results.append({
            'id': work.id,
            'title': work.title,
            'url': url_for('main.detail', work_id=work.id),
            'thumb_url': url_for('main.serve_thumbs', filename=work.cover_path) if work.cover_path else '',
            'view_count': work.view_count
        })

    return {'results': results}

@bp.route('/slideshow')
def slideshow():
    return render_template('main/slideshow.html')

@bp.route('/slideshow/data')
def slideshow_data():
    # Get top 100 works by view count (random shuffle of top 200?)
    # For now just top 50 descending view count
    works = Work.query.order_by(desc(Work.view_count)).limit(50).all()

    # Shuffle them to make it interesting each time? Or just top sorted.
    # Let's shuffle the top 50 in python
    import random
    random.shuffle(works)

    data = []
    for w in works:
        # Use full image not thumbnail for slideshow if possible? Or thumb if high res enough.
        # "Pixiv Local" thumb is 360x360 usually.
        # But we serve raw files via serve_data. Let's use serve_data (original file) if it's an image.
        if w.work_type == 'Illustration' and w.images.count() > 0:
            # Pick first image
            img = w.images.first()
            if img:
                data.append({
                    'title': w.title,
                    'artist': w.artist_name,
                    'url': url_for('main.serve_data', filename=img.file_path)
                })

    return data

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        # Recommendation Mode
        mode = request.form.get('recommendation_mode')
        if mode in ['tags', 'similarity']:
            current_user.recommendation_mode = mode

        # Image Quality
        quality = request.form.get('image_quality')
        if quality in ['original', 'compressed']:
            current_user.image_quality = quality

        # R-18 Blur
        blur = request.form.get('enable_r18_blur')
        current_user.enable_r18_blur = True if blur == 'on' else False

        db.session.commit()
        flash('Settings updated.', 'success')
        return redirect(url_for('main.settings'))
    return render_template('main/settings.html')

@bp.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['ITEMS_PER_PAGE']
    # Optimization: Sort by ID (indexed PK) instead of created_at (unindexed, unstable).
    # ID is chronologically correct for Pixiv works.
    works = Work.query.order_by(desc(Work.id)).paginate(page=page, per_page=per_page)
    return render_template('main/index.html', works=works)

@bp.route('/work/<int:work_id>/read')
def read_manga(work_id):
    work = Work.query.get_or_404(work_id)
    return render_template('main/reader.html', work=work)

@bp.route('/work/<int:work_id>/autotag', methods=['POST'])
@login_required
def auto_tag(work_id):
    work = Work.query.get_or_404(work_id)

    # Distinguish between Novel and Image
    if work.work_type == 'Novel':
        if work.file_path:
            full_path = os.path.join(current_app.config['DATA_DIR'], work.file_path)
            if os.path.exists(full_path):
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Tag text
                    from app.services.tagger import text_tagger
                    new_tags = text_tagger.tag_text(content)

                    if new_tags:
                        current_tags = set((work.tags or '').split(','))
                        current_tags = {t.strip() for t in current_tags if t.strip()}
                        for t in new_tags:
                            current_tags.add(t)

                        work.tags = ",".join(current_tags)
                        db.session.commit()
                        flash(f"Added tags: {', '.join(new_tags)}", 'success')
                    else:
                        flash("No keywords extracted.", 'info')
                except Exception as e:
                    flash(f"Error reading novel: {e}", 'error')
            else:
                flash("Novel file not found.", 'error')
        else:
            flash("No file associated.", 'error')

    else: # Image/Illustration
        # For image tagging, prefer the original image if available for better accuracy, or preview/thumb
        # WD14 resize to 448x448, so source resolution matters less as long as it's not tiny.
        # Use first image logic
        target_path = None
        if work.images.count() > 0:
             target_path = os.path.join(current_app.config['DATA_DIR'], work.images.first().file_path)
        elif work.cover_path: # Fallback to thumb
             target_path = os.path.join(current_app.config['THUMBS_DIR'], work.cover_path)

        if target_path and os.path.exists(target_path):
            from app.services.tagger import image_tagger
            new_tags = image_tagger.tag_image(target_path)

            if new_tags and "error" not in new_tags and "model_error" not in new_tags:
                current_tags = set((work.tags or '').split(','))
                current_tags = {t.strip() for t in current_tags if t.strip()}

                for t in new_tags:
                    current_tags.add(t)

                work.tags = ",".join(current_tags)
                db.session.commit()
                flash(f"Added tags: {', '.join(new_tags)}", 'success')
            elif "model_error" in new_tags:
                flash("Tagger model not loaded. Please check logs.", 'error')
            else:
                flash("No tags detected or error occurred.", 'info')
        else:
            flash("No image found to tag.", 'error')

    return redirect(url_for('main.detail', work_id=work.id))

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

    # Related Works
    related_works = []
    recommendation_mode = 'tags'
    if current_user.is_authenticated and current_user.recommendation_mode:
        recommendation_mode = current_user.recommendation_mode

    if recommendation_mode == 'similarity' and work.phash:
        # Sort by hamming distance. SQLite doesn't have bit count, so we have to do it in python or simple heuristic.
        # Since we can't efficiently query hamming distance in standard SQL/SQLite without extensions:
        # We fetch a candidate set (e.g. recent works or random works) and sort in Python.
        # Ideally, we should use a BK-tree or specialized DB, but for "Pixiv Local" with SQLite, Python sorting on a subset is acceptable.

        # Fetch candidate works (e.g. 1000 recent works to scan)
        # Avoid fetching all if DB is huge.
        candidates = Work.query.filter(Work.id != work.id, Work.phash != None).order_by(desc(Work.id)).limit(1000).all()

        target_hash = imagehash.hex_to_hash(work.phash)

        def calculate_distance(w):
            try:
                return target_hash - imagehash.hex_to_hash(w.phash)
            except:
                return 100 # Max distance if error

        # Sort candidates by distance (ascending)
        candidates.sort(key=calculate_distance)
        related_works = candidates[:4]

    else:
        # Tag based (Fallback or Default)
        if work.tags:
            current_tags = [t.strip() for t in work.tags.split(',') if t.strip()]
            if current_tags:
                filters = [Work.tags.contains(tag) for tag in current_tags]
                related_works = Work.query.filter(db.or_(*filters), Work.id != work.id).order_by(desc(Work.id)).limit(4).all()

    return render_template('main/detail.html', work=work, novel_content=novel_content,
                           previous_in_series=previous_in_series, next_in_series=next_in_series,
                           related_works=related_works)

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
        
    # Optimization: Sort by ID (indexed PK) instead of created_at.
    works = query.order_by(desc(Work.id)).paginate(page=page, per_page=per_page)
    return render_template('main/search.html', works=works, q=q)

@bp.route('/search/image', methods=['POST'])
def search_image():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.referrer or url_for('main.index'))
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.referrer or url_for('main.index'))

    if file:
        try:
            img = PILImage.open(file.stream)
            target_hash = imagehash.phash(img)

            # Find closest matches
            # Similar logic to recommendation: fetch candidates and sort by distance
            candidates = Work.query.filter(Work.phash != None).order_by(desc(Work.id)).limit(2000).all()

            def calculate_distance(w):
                try:
                    return target_hash - imagehash.hex_to_hash(w.phash)
                except:
                    return 100

            # Filter candidates with reasonable distance (e.g., < 20) and sort
            matches = []
            for w in candidates:
                dist = calculate_distance(w)
                if dist < 30: # arbitrary threshold for "somewhat similar"
                    matches.append((w, dist))

            matches.sort(key=lambda x: x[1])

            # Extract just works
            works_list = [m[0] for m in matches[:50]] # Top 50 results

            # Manually paginate (basic)
            page = 1
            per_page = current_app.config['ITEMS_PER_PAGE']

            # Mock pagination object or render a simple template
            # For simplicity, let's reuse search.html with a custom list
            # But search.html expects a pagination object usually.
            # We can construct a simple class to mimic pagination or pass works list directly if template supports it.
            # search.html uses `works.items` usually.

            class MockPagination:
                def __init__(self, items):
                    self.items = items
                    self.has_prev = False
                    self.has_next = False
                    self.page = 1
                    self.prev_num = 0
                    self.next_num = 0
                    self.pages = 1

                def iter_pages(self, left_edge=1, right_edge=1, left_current=2, right_current=2):
                    return []

            pagination = MockPagination(works_list)

            return render_template('main/search.html', works=pagination, q=f"Image Search (Top {len(works_list)})")

        except Exception as e:
            flash(f'Error processing image: {e}')
            return redirect(request.referrer or url_for('main.index'))

@bp.route('/history')
@login_required
def history():
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['ITEMS_PER_PAGE']
    history_query = History.query.filter_by(user_id=current_user.id).order_by(desc(History.viewed_at))
    pagination = history_query.paginate(page=page, per_page=per_page)
    return render_template('main/history.html', pagination=pagination)

@bp.route('/xp')
@login_required
def xp_dashboard():
    # 1. Top Tags from History
    # Optimization: Use joinedload to prevent N+1 queries for 'work' relationship
    history_items = History.query.options(joinedload(History.work)).filter_by(user_id=current_user.id).all()
    history_tags = []
    # Data for charts
    artist_counts = Counter()
    activity_hours = Counter()

    for item in history_items:
        if item.work:
            if item.work.tags:
                tags = [t.strip() for t in item.work.tags.split(',') if t.strip()]
                history_tags.extend(tags)
            if item.work.artist_name:
                artist_counts[item.work.artist_name] += 1
            if item.viewed_at:
                activity_hours[item.viewed_at.hour] += 1

    history_tag_counts = Counter(history_tags).most_common(50)
    top_artists = artist_counts.most_common(10)

    # Sort activity by hour 0-23
    activity_data = [activity_hours[h] for h in range(24)]

    # 2. Top Tags from Liked Works
    liked_works = current_user.liked_works.all()
    liked_tags = []
    for work in liked_works:
        if work.tags:
            tags = [t.strip() for t in work.tags.split(',') if t.strip()]
            liked_tags.extend(tags)

    liked_tag_counts = Counter(liked_tags).most_common(50)

    return render_template('main/xp_dashboard.html',
                           history_tag_counts=history_tag_counts,
                           liked_tag_counts=liked_tag_counts,
                           top_artists=top_artists,
                           activity_data=activity_data)

@bp.route('/likes')
@login_required
def likes():
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['ITEMS_PER_PAGE']
    # liked_works is a dynamic relationship query
    works = current_user.liked_works.paginate(page=page, per_page=per_page)
    return render_template('main/likes.html', works=works)

@bp.route('/bookmarks')
@login_required
def bookmarks():
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['ITEMS_PER_PAGE']
    # bookmarked_works is a dynamic relationship query
    works = current_user.bookmarked_works.paginate(page=page, per_page=per_page)
    return render_template('main/bookmarks.html', works=works)

@bp.route('/data/<path:filename>')
def serve_data(filename):
    return send_from_directory(current_app.config['DATA_DIR'], filename)

@bp.route('/thumbs/<path:filename>')
def serve_thumbs(filename):
    return send_from_directory(current_app.config['THUMBS_DIR'], filename)

@bp.route('/preview/<path:filename>')
def serve_preview(filename):
    """
    Serve a resized version (max 1600px) of the image.
    Cache it in THUMBS_DIR/previews.
    """
    data_dir = current_app.config['DATA_DIR']
    thumbs_dir = current_app.config['THUMBS_DIR']
    preview_dir = os.path.join(thumbs_dir, 'previews')

    # Target preview path
    # Preserve directory structure or flatten? Flattening is risky for collisions.
    # Replicating structure is safer.
    rel_path = filename
    original_path = os.path.join(data_dir, rel_path)
    preview_path = os.path.join(preview_dir, rel_path)

    if not os.path.exists(original_path):
        abort(404)

    if not os.path.exists(preview_path):
        try:
            os.makedirs(os.path.dirname(preview_path), exist_ok=True)
            with PILImage.open(original_path) as img:
                # If animated (GIF/WebP), just copy original or skip resize to avoid breaking animation
                # Check for is_animated attribute
                if getattr(img, 'is_animated', False):
                    # We could copy the file, or just serve original.
                    # Serving original is simpler and avoids huge duplication if GIF is big.
                    # But the route expects to serve from preview_dir.
                    # Let's symlink or copy? Or just abort and serve original.
                    # Aborting here allows the exception handler or explicit check to serve original.
                    return send_from_directory(data_dir, filename)

                # Convert to RGB if needed
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')

                # Resize if larger than 1600
                max_size = (1600, 1600)
                img.thumbnail(max_size, PILImage.Resampling.LANCZOS)

                img.save(preview_path, 'JPEG', quality=85)
        except Exception as e:
            # Fallback to original if processing fails (e.g. weird format)
            print(f"Preview generation failed: {e}")
            return send_from_directory(data_dir, filename)

    return send_from_directory(preview_dir, rel_path)

@bp.route('/set_language/<lang_code>')
def set_language(lang_code):
    if lang_code in ['zh', 'en']:
        session['locale'] = lang_code
    return redirect(request.referrer or url_for('main.index'))
