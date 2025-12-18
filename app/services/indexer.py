import os
import re
import time
import threading
from PIL import Image
from sqlalchemy.exc import SQLAlchemyError
from ..extensions import db
from ..models import Work, Image as DbImage
import config

# Helper to avoid circular imports if necessary, but app context should be handled by caller
def parse_filename(filename):
    name, ext = os.path.splitext(filename)
    meta = {'id': 0, 'title': name, 'tags': '', 'series_title': '', 'series_order': '', 'type': 'Illustration', 'p_num': 0}

    if ext.lower() == '.txt': meta['type'] = 'Novel'
    elif ext.lower() in ['.mp4', '.webm', '.zip']: meta['type'] = 'Ugoira'

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
        parts = rest_name.split('_', 1)
        meta['title'] = parts[0]
        tag_series_blob = parts[1]

        series_regex = r'^(.*)-(.+?)_(#.*?)-(\d+)$'
        series_match = re.match(series_regex, tag_series_blob)
        if series_match:
            tags_raw = series_match.group(1)
            meta['series_title'] = series_match.group(2)
            meta['series_order'] = series_match.group(3)
        else:
            tags_raw = tag_series_blob
        meta['tags'] = tags_raw.replace(',', ' ').strip(' -_')
    else:
        meta['title'] = rest_name
    return meta

def generate_thumbnail(source_path, dest_path):
    if os.path.exists(dest_path): return
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        ext = os.path.splitext(source_path)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png', '.webp']:
            with Image.open(source_path) as img:
                img.thumbnail((360, 360))
                if img.mode != 'RGB': img = img.convert('RGB')
                img.save(dest_path, 'JPEG', quality=85)
    except Exception as e:
        print(f"Failed to generate thumbnail for {source_path}: {e}")

def scan_directory(app):
    with app.app_context():
        # Scan logic
        works_buffer = {}

        roots_to_scan = []
        found_subdir = False
        for subdir in ['pixiv', 'fanbox']:
            p = os.path.join(config.DATA_DIR, subdir)
            if os.path.exists(p):
                roots_to_scan.append(subdir)
                found_subdir = True

        if not found_subdir:
            roots_to_scan.append('')

        for root_name in roots_to_scan:
            search_root = os.path.join(config.DATA_DIR, root_name)
            if not os.path.exists(search_root): continue

            try:
                user_folders = os.listdir(search_root)
            except OSError:
                continue

            for user_folder in user_folders:
                user_path = os.path.join(search_root, user_folder)
                if not os.path.isdir(user_path): continue
                u_match = re.match(r'(.*)-(\d+)$', user_folder)
                if not u_match: continue
                user_name, user_id = u_match.group(1), int(u_match.group(2))

                try: files = os.listdir(user_path)
                except OSError: continue

                for f in files:
                    lower_f = f.lower()
                    if not (lower_f.endswith('.jpg') or lower_f.endswith('.png') or lower_f.endswith('.txt') or lower_f.endswith('.zip') or lower_f.endswith('.mp4')): continue

                    if root_name == '':
                        full_path = os.path.join(user_folder, f)
                    else:
                        full_path = os.path.join(root_name, user_folder, f)

                    real_full_path = os.path.join(config.DATA_DIR, full_path)

                    if config.THUMBS_DIR:
                        thumb_dest = os.path.join(config.THUMBS_DIR, full_path + '.jpg')
                        generate_thumbnail(real_full_path, thumb_dest)

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
                        # Prefer meta from p0 or if not available just keep updating?
                        # Original logic: if type!=Novel and p_num==0: update meta
                        if works_buffer[wid]['meta']['type'] != 'Novel' and meta['p_num'] == 0:
                            works_buffer[wid]['meta'] = meta

        # Batch update DB
        for wid, data in works_buffer.items():
            meta = data['meta']

            # Check existing view count
            existing_work = db.session.get(Work, wid)
            old_views = existing_work.view_count if existing_work else 0

            cover = None
            work_type = 'Illustration'
            file_path = None
            page_count = 1

            if data['novel_txt']:
                work_type = 'Novel'
                file_path = data['novel_txt']
                # Try to find cover
                for p, path in data['files']:
                    if p == 0: cover = path; break
                if not cover and data['files']: cover = data['files'][0][1]
            else:
                sorted_files = sorted(data['files'], key=lambda x: x[0])
                if not sorted_files: continue
                file_path = sorted_files[0][1]
                page_count = len(sorted_files)
                work_type = 'Illustration'

            # Update or Insert Work
            if existing_work:
                existing_work.user_id = data['user_id']
                existing_work.user_name = data['user_name']
                existing_work.title = meta['title']
                existing_work.tags = meta['tags']
                existing_work.work_type = work_type
                existing_work.series_title = meta['series_title']
                existing_work.series_order = meta['series_order']
                existing_work.file_path = file_path
                existing_work.cover_path = cover
                existing_work.page_count = page_count
            else:
                new_work = Work(
                    id=wid,
                    user_id=data['user_id'],
                    user_name=data['user_name'],
                    title=meta['title'],
                    tags=meta['tags'],
                    work_type=work_type,
                    series_title=meta['series_title'],
                    series_order=meta['series_order'],
                    file_path=file_path,
                    cover_path=cover,
                    page_count=page_count,
                    view_count=old_views
                )
                db.session.add(new_work)

            # Update Images
            # For simplicity, we can just upsert images
            for p_num, path in data['files']:
                img = db.session.get(DbImage, (wid, p_num))
                if img:
                    img.file_path = path
                else:
                    db.session.add(DbImage(work_id=wid, p_num=p_num, file_path=path))

        try:
            db.session.commit()
        except SQLAlchemyError as e:
            print(f"Database error during scan: {e}")
            db.session.rollback()

def loop(app):
    print(f"Start scanning {config.DATA_DIR} every {config.SCAN_INTERVAL} seconds...")
    while True:
        try:
            scan_directory(app)
        except Exception as e:
            print(f"Error in scan loop: {e}")
        time.sleep(config.SCAN_INTERVAL)
