from dotenv import load_dotenv
import os
load_dotenv()

from flask import Flask, render_template, request, abort, jsonify, send_from_directory, redirect, url_for, flash, session
import sqlite3
import os
import re
import shutil
from urllib.parse import quote
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_babel import Babel, gettext as _
import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# === Babel ===
app.config['BABEL_DEFAULT_LOCALE'] = 'en'
app.config['BABEL_TRANSLATION_DIRECTORIES'] = 'translations'
def get_locale():
    if session.get('lang'): return session.get('lang')
    return request.accept_languages.best_match(['en', 'zh'])
babel = Babel(app, locale_selector=get_locale)

# === Login ===
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = _('Please log in to access this page.')

class User(UserMixin):
    def __init__(self, id, username, is_admin):
        self.id = id; self.username = username; self.is_admin = is_admin

@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    u = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return User(u['id'], u['username'], u['is_admin']) if u else None

def get_db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

@app.template_filter('url_quote')
def url_quote_filter(s): return quote(s, safe='/') if s else ""

@app.template_filter('thumbnail')
def thumbnail_filter(s):
    if not s: return ""
    return f"{config.THUMBS_URL_PREFIX}{quote(s, safe='/')}"

@app.template_filter('is_r18')
def is_r18_filter(tags): return tags and ('R-18' in tags or 'R-18G' in tags)

@app.route('/set_lang/<string:lang_code>')
def set_lang(lang_code):
    if lang_code in ['en', 'zh']: session['lang'] = lang_code
    return redirect(request.referrer or url_for('index'))

# --- Auth ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username, password = request.form['username'], request.form['password']
        conn = get_db()
        try:
            count = conn.execute('SELECT count(*) FROM users').fetchone()[0]
            is_admin = 1 if count == 0 else 0
            conn.execute('INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)', 
                         (username, generate_password_hash(password), is_admin))
            conn.commit()
            flash(_('Registration successful! Please login.'))
            return redirect(url_for('login'))
        except sqlite3.IntegrityError: flash(_('Username already exists.'))
        finally: conn.close()
    return render_template('auth/register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (request.form['username'],)).fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], request.form['password']):
            login_user(User(user['id'], user['username'], user['is_admin']))
            return redirect(url_for('index'))
        else: flash(_('Invalid username or password.'))
    return render_template('auth/login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- Routes ---
def get_works_query(query_str, page, per_page=24):
    conn = get_db()
    offset = (page - 1) * per_page
    if query_str:
        sql = "SELECT * FROM works WHERE tags LIKE ? OR title LIKE ? OR user_name LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?"
        term = f"%{query_str}%"
        works = conn.execute(sql, (term, term, term, per_page, offset)).fetchall()
    else:
        works = conn.execute("SELECT * FROM works ORDER BY id DESC LIMIT ? OFFSET ?", (per_page, offset)).fetchall()
    conn.close()
    return works

@app.route('/')
def index(): return render_template('index.html', works=get_works_query(None, 1))

@app.route('/search')
def search(): return render_template('index.html', works=get_works_query(request.args.get('q', ''), 1), search=request.args.get('q', ''))

@app.route('/ranking')
def ranking():
    conn = get_db()
    try: works = conn.execute('SELECT * FROM works ORDER BY view_count DESC LIMIT 50').fetchall()
    except: works = []
    conn.close()
    return render_template('ranking.html', works=works)

@app.route('/following')
@login_required
def following_feed():
    conn = get_db()
    # Optimized: Use ORDER BY w.id DESC instead of created_at.
    # 1. Performance: w.id is the Primary Key (indexed), avoiding a slow sort on unindexed created_at.
    # 2. Correctness: created_at is updated on every scan (file mtime/scan time), whereas id (Pixiv ID) is fixed and monotonic with creation time.
    sql = "SELECT w.* FROM works w JOIN follows f ON w.user_id = f.followed_user_id WHERE f.follower_id = ? ORDER BY w.id DESC LIMIT 50"
    works = conn.execute(sql, (current_user.id,)).fetchall()
    conn.close()
    return render_template('index.html', works=works, title=_("Following Feed"))

@app.route('/history')
@login_required
def history():
    conn = get_db()
    sql = "SELECT w.* FROM works w JOIN history h ON w.id = h.work_id WHERE h.user_id = ? ORDER BY h.viewed_at DESC LIMIT 50"
    works = conn.execute(sql, (current_user.id,)).fetchall()
    conn.close()
    return render_template('index.html', works=works, title=_("History"))

@app.route('/users/<int:user_id>')
def user(user_id):
    conn = get_db()
    user = conn.execute('SELECT user_name FROM works WHERE user_id = ? LIMIT 1', (user_id,)).fetchone()
    if not user: return abort(404)
    is_followed = False
    if current_user.is_authenticated:
        if conn.execute('SELECT 1 FROM follows WHERE follower_id=? AND followed_user_id=?', (current_user.id, user_id)).fetchone(): is_followed = True
    novels = conn.execute('SELECT * FROM works WHERE user_id = ? AND work_type = "Novel" ORDER BY id DESC', (user_id,)).fetchall()
    illusts = conn.execute('SELECT * FROM works WHERE user_id = ? AND work_type != "Novel" ORDER BY id DESC', (user_id,)).fetchall()
    conn.close()
    return render_template('user.html', user=user, user_id=user_id, novels=novels, illusts=illusts, is_followed=is_followed)

@app.route('/view/<int:work_id>')
def view_work(work_id):
    conn = get_db()
    work = conn.execute('SELECT * FROM works WHERE id = ?', (work_id,)).fetchone()
    if not work: conn.close(); return abort(404)

    try:
        conn.execute('UPDATE works SET view_count = view_count + 1 WHERE id = ?', (work_id,))
        if current_user.is_authenticated:
            conn.execute('INSERT OR REPLACE INTO history (user_id, work_id, viewed_at) VALUES (?, ?, CURRENT_TIMESTAMP)', (current_user.id, work_id))
        conn.commit()
    except: pass

    is_liked = False; is_bookmarked = False
    if current_user.is_authenticated:
        is_liked = conn.execute('SELECT 1 FROM work_likes WHERE user_id=? AND work_id=?', (current_user.id, work_id)).fetchone()
        is_bookmarked = conn.execute('SELECT 1 FROM bookmarks WHERE user_id=? AND work_id=?', (current_user.id, work_id)).fetchone()

    comments = conn.execute('SELECT c.*, u.username FROM comments c JOIN users u ON c.user_id = u.id WHERE c.work_id = ? ORDER BY c.created_at DESC', (work_id,)).fetchall()
    images = conn.execute('SELECT * FROM images WHERE work_id = ? ORDER BY p_num ASC', (work_id,)).fetchall()

    related_works = []
    if work['tags']:
        tags = work['tags'].split(' ')[:2]
        if tags:
            conds = ["tags LIKE ?" for t in tags if t.strip()]
            if conds:
                sql = f"SELECT * FROM works WHERE ({' OR '.join(conds)}) AND id != ? ORDER BY random() LIMIT 6"
                related_works = conn.execute(sql, [f"%{t}%" for t in tags if t.strip()] + [work_id]).fetchall()

    if work['work_type'] != 'Novel':
        conn.close()
        if not images and work['file_path']: images = [{'file_path': work['file_path']}]
        return render_template('illust.html', work=work, images=images, is_liked=is_liked, is_bookmarked=is_bookmarked, comments=comments, related_works=related_works)

    file_full_path = os.path.join(config.DATA_DIR, work['file_path'])
    content = ""
    if os.path.exists(file_full_path):
        try:
            with open(file_full_path, 'r', encoding='utf-8') as f: content = f.read()
        except:
            try:
                with open(file_full_path, 'r', encoding='gb18030') as f: content = f.read()
            except: content = _("Decode Error.")
    else: content = _("File Missing.")
    conn.close()
    lines = content.splitlines()
    return render_template('novel.html', work=work, lines=lines, images=images, is_liked=is_liked, is_bookmarked=is_bookmarked, comments=comments, related_works=related_works)

@app.route('/series/<path:series_title>')
def view_series(series_title):
    conn = get_db()
    works = conn.execute('SELECT * FROM works WHERE series_title = ?', (series_title,)).fetchall()
    conn.close()
    if not works: return abort(404)
    def sort_key(w):
        try: return int(re.search(r'(\d+)', w['series_order'] or "").group(1))
        except: return 999999
    return render_template('series.html', series_title=series_title, works=sorted(works, key=sort_key))

# --- API ---
@app.route('/api/load_more')
def api_load_more():
    page = request.args.get('page', 1, type=int)
    query = request.args.get('q', '')
    works = get_works_query(query, page)
    data = []
    for work in works:
        item = {'id': work['id'], 'title': work['title'], 'user_id': work['user_id'], 'user_name': work['user_name'], 'work_type': work['work_type'], 'page_count': work['page_count'], 'link_url': f"/view/{work['id']}", 'img_src': "", 'tags': work['tags']}
        raw = work['cover_path'] if (work['work_type'] == 'Novel' and work['cover_path']) else work['file_path']
        if raw: item['img_src'] = f"{config.THUMBS_URL_PREFIX}{quote(raw, safe='/')}"
        data.append(item)
    return jsonify(data)

@app.route('/api/like/<int:work_id>', methods=['POST'])
@login_required
def api_like(work_id):
    conn = get_db()
    uid = current_user.id
    if conn.execute('SELECT 1 FROM work_likes WHERE user_id=? AND work_id=?', (uid, work_id)).fetchone():
        conn.execute('DELETE FROM work_likes WHERE user_id=? AND work_id=?', (uid, work_id)); status = 'unliked'
    else:
        conn.execute('INSERT INTO work_likes (user_id, work_id) VALUES (?, ?)', (uid, work_id)); status = 'liked'
    conn.commit(); conn.close()
    return jsonify({'status': status})

@app.route('/api/bookmark/<int:work_id>', methods=['POST'])
@login_required
def api_bookmark(work_id):
    conn = get_db()
    uid = current_user.id
    if conn.execute('SELECT 1 FROM bookmarks WHERE user_id=? AND work_id=?', (uid, work_id)).fetchone():
        conn.execute('DELETE FROM bookmarks WHERE user_id=? AND work_id=?', (uid, work_id)); status = 'removed'
    else:
        conn.execute('INSERT INTO bookmarks (user_id, work_id) VALUES (?, ?)', (uid, work_id)); status = 'added'
    conn.commit(); conn.close()
    return jsonify({'status': status})

@app.route('/api/follow/<int:user_id>', methods=['POST'])
@login_required
def api_follow(user_id):
    conn = get_db()
    uid = current_user.id
    if conn.execute('SELECT 1 FROM follows WHERE follower_id=? AND followed_user_id=?', (uid, user_id)).fetchone():
        conn.execute('DELETE FROM follows WHERE follower_id=? AND followed_user_id=?', (uid, user_id)); status = 'unfollowed'
    else:
        conn.execute('INSERT INTO follows (follower_id, followed_user_id) VALUES (?, ?)', (uid, user_id)); status = 'followed'
    conn.commit(); conn.close()
    return jsonify({'status': status})

@app.route('/api/comment/<int:work_id>', methods=['POST'])
@login_required
def api_comment(work_id):
    c = request.form.get('content')
    if c:
        conn = get_db()
        conn.execute('INSERT INTO comments (user_id, work_id, content) VALUES (?, ?, ?)', (current_user.id, work_id, c))
        conn.commit(); conn.close()
    return redirect(url_for('view_work', work_id=work_id))

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin: return abort(403)
    conn = get_db()
    try: t, u, f = shutil.disk_usage(config.DATA_DIR)
    except: t, u, f = 0, 0, 0
    disk = {'total': f"{t//(2**30)}GB", 'used': f"{u//(2**30)}GB", 'free': f"{f//(2**30)}GB", 'percent': (u/t)*100 if t else 0}
    try: tv = conn.execute('SELECT sum(view_count) FROM works').fetchone()[0] or 0
    except: tv = 0
    stats = {'works': conn.execute('SELECT count(*) FROM works').fetchone()[0], 'users': conn.execute('SELECT count(*) FROM users').fetchone()[0], 'comments': conn.execute('SELECT count(*) FROM comments').fetchone()[0], 'views': tv, 'disk': disk}
    users = conn.execute('SELECT * FROM users ORDER BY id DESC LIMIT 50').fetchall()
    comments = conn.execute('SELECT c.*, u.username, w.title FROM comments c JOIN users u ON c.user_id=u.id JOIN works w ON c.work_id=w.id ORDER BY c.created_at DESC LIMIT 20').fetchall()
    conn.close()
    return render_template('admin/dashboard.html', stats=stats, users=users, comments=comments)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if not current_user.is_admin: return abort(403)
    if user_id == current_user.id: return _("Cannot delete yourself"), 400
    conn = get_db()
    for t in ['users', 'comments', 'work_likes', 'bookmarks']: conn.execute(f'DELETE FROM {t} WHERE {"id" if t=="users" else "user_id"} = ?', (user_id,))
    conn.execute('DELETE FROM follows WHERE follower_id = ? OR followed_user_id = ?', (user_id, user_id))
    conn.commit(); conn.close()
    return redirect(url_for('admin'))

@app.route('/admin/delete_comment/<int:comment_id>', methods=['POST'])
@login_required
def admin_delete_comment(comment_id):
    if not current_user.is_admin: return abort(403)
    conn = get_db(); conn.execute('DELETE FROM comments WHERE id = ?', (comment_id,)); conn.commit(); conn.close()
    return redirect(url_for('admin'))

@app.route('/manifest.json')
def manifest(): return send_from_directory('static', 'manifest.json')
@app.route('/sw.js')
def sw(): 
    r = send_from_directory('static', 'sw.js'); r.headers['Content-Type'] = 'application/javascript'; return r

# For development or simple deployment, serve files directly from Flask
# In production with Nginx, this route might be bypassed by Nginx configuration
@app.route('/files/<path:filename>')
def serve_file(filename):
    return send_from_directory(config.DATA_DIR, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
