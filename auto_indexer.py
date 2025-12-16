import os
import re
import sqlite3
import time
import config

def init_db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL;') # 开启 WAL 模式防止锁死
    c = conn.cursor()
    
    # 1. 作品主表
    c.execute('''CREATE TABLE IF NOT EXISTS works (
        id INTEGER PRIMARY KEY, user_id INTEGER, user_name TEXT, title TEXT, tags TEXT,
        work_type TEXT, series_title TEXT, series_order TEXT, file_path TEXT, cover_path TEXT,
        page_count INTEGER DEFAULT 1, view_count INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    # 2. 图片附表
    c.execute('''CREATE TABLE IF NOT EXISTS images (work_id INTEGER, p_num INTEGER, file_path TEXT, PRIMARY KEY (work_id, p_num))''')
    # 3. 用户表
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
        is_admin BOOLEAN DEFAULT 0, avatar TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    # 4. 互动表
    c.execute('''CREATE TABLE IF NOT EXISTS work_likes (user_id INTEGER, work_id INTEGER, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (user_id, work_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS bookmarks (user_id INTEGER, work_id INTEGER, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (user_id, work_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS comments (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, work_id INTEGER, content TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    # 5. 社交表
    c.execute('''CREATE TABLE IF NOT EXISTS follows (follower_id INTEGER, followed_user_id INTEGER, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (follower_id, followed_user_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS history (user_id INTEGER, work_id INTEGER, viewed_at DATETIME DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (user_id, work_id))''')

    c.execute('CREATE INDEX IF NOT EXISTS idx_user_id ON works (user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_tags ON works (tags)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_view_count ON works (view_count)')
    conn.commit()
    conn.close()

def parse_filename(filename):
    name, ext = os.path.splitext(filename)
    meta = {'id': 0, 'title': name, 'tags': '', 'series_title': '', 'series_order': '', 'type': 'Illustration', 'p_num': 0}
    
    if ext.lower() == '.txt': meta['type'] = 'Novel'
    elif ext.lower() in ['.mp4', '.webm', '.zip']: meta['type'] = 'Ugoira'
    
    # 兼容 12345-Title 和 12345_p0-Title
    match = re.match(r'^(\d+)(?:_p(\d+))?-(.*)$', name)
    if match:
        meta['id'] = int(match.group(1))
        meta['p_num'] = int(match.group(2)) if match.group(2) else 0
        rest_name = match.group(3)
    else:
        match_simple = re.match(r'^(\d+)(.*)$', name)
        if match_simple:
            meta['id'] = int(match_simple.group(1))
            rest_name = match_simple.group(2)
        else: rest_name = name

    if '_' in rest_name:
        meta['title'], tag_series_blob = rest_name.split('_', 1)
        series_regex = r'^(.*)-(.+?)_(#.*?)-(\d+)$'
        series_match = re.match(series_regex, tag_series_blob)
        if series_match:
            tags_raw = series_match.group(1)
            meta['series_title'] = series_match.group(2)
            meta['series_order'] = series_match.group(3)
        else: tags_raw = tag_series_blob
        meta['tags'] = tags_raw.replace(',', ' ').strip(' -_')
    else: meta['title'] = rest_name
    return meta

def scan_directory():
    # 增加超时防止 locked
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL;')
    c = conn.cursor()
    
    search_root = os.path.join(config.DATA_DIR, "pixiv")
    if not os.path.exists(search_root): search_root = config.DATA_DIR

    works_buffer = {} 

    for user_folder in os.listdir(search_root):
        user_path = os.path.join(search_root, user_folder)
        if not os.path.isdir(user_path): continue
        u_match = re.match(r'(.*)-(\d+)$', user_folder)
        if not u_match: continue
        user_name, user_id = u_match.group(1), int(u_match.group(2))

        try: files = os.listdir(user_path)
        except OSError: continue
        
        for f in files:
            if not (f.endswith('.jpg') or f.endswith('.png') or f.endswith('.txt') or f.endswith('.zip') or f.endswith('.mp4')): continue
            
            if search_root == config.DATA_DIR: full_path = os.path.join(user_folder, f)
            else: full_path = os.path.join("pixiv", user_folder, f)
            
            meta = parse_filename(f)
            wid = meta['id']
            
            if wid not in works_buffer:
                works_buffer[wid] = {'meta': meta, 'user_id': user_id, 'user_name': user_name, 'files': [], 'novel_txt': None}
            
            if meta['type'] == 'Novel':
                works_buffer[wid]['novel_txt'] = full_path
                works_buffer[wid]['meta'] = meta 
                works_buffer[wid]['meta']['type'] = 'Novel'
            elif meta['type'] == 'Illustration':
                works_buffer[wid]['files'].append((meta['p_num'], full_path))
                if works_buffer[wid]['meta']['type'] != 'Novel' and meta['p_num'] == 0:
                    works_buffer[wid]['meta'] = meta

    for wid, data in works_buffer.items():
        meta = data['meta']
        old_views = 0
        try:
            res = c.execute('SELECT view_count FROM works WHERE id = ?', (wid,)).fetchone()
            if res: old_views = res[0]
        except: pass

        if data['novel_txt']:
            cover = None
            for p, path in data['files']:
                if p == 0: cover = path; break
            if not cover and data['files']: cover = data['files'][0][1]
            
            c.execute("INSERT OR REPLACE INTO works (id, user_id, user_name, title, tags, work_type, series_title, series_order, file_path, cover_path, page_count, view_count) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (wid, data['user_id'], data['user_name'], meta['title'], meta['tags'], 'Novel', meta['series_title'], meta['series_order'], data['novel_txt'], cover, 1, old_views))
        else:
            sorted_files = sorted(data['files'], key=lambda x: x[0])
            if not sorted_files: continue
            main_file = sorted_files[0][1]
            c.execute("INSERT OR REPLACE INTO works (id, user_id, user_name, title, tags, work_type, series_title, series_order, file_path, cover_path, page_count, view_count) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (wid, data['user_id'], data['user_name'], meta['title'], meta['tags'], 'Illustration', meta['series_title'], meta['series_order'], main_file, None, len(sorted_files), old_views))
            
        for p_num, path in data['files']:
            c.execute("INSERT OR REPLACE INTO images (work_id, p_num, file_path) VALUES (?,?,?)", (wid, p_num, path))

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print(f"Start scanning {config.DATA_DIR} every {config.SCAN_INTERVAL} seconds...")
    while True:
        try: scan_directory()
        except Exception as e: print(f"Error: {e}")
        time.sleep(config.SCAN_INTERVAL)
