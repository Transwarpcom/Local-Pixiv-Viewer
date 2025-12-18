import os
import re
from datetime import datetime
from app.extensions import db
from app.models import Work, Image as ImageModel, Series
from app.utils import generate_thumbnail

class Indexer:
    def __init__(self, config):
        self.data_dir = config['DATA_DIR']
        self.thumbs_dir = config['THUMBS_DIR']
        
    def run(self):
        if not self.data_dir or not os.path.exists(self.data_dir):
            print(f"Data directory {self.data_dir} does not exist.")
            return

        # 1. Scan Artists directories
        artist_dirs = [d for d in os.listdir(self.data_dir) if os.path.isdir(os.path.join(self.data_dir, d))]
        
        for artist_dir in artist_dirs:
            self._process_artist_dir(artist_dir)
            
    def _process_artist_dir(self, artist_dir_name):
        match = re.search(r'(.+)-(\d+)$', artist_dir_name)
        if match:
            artist_name = match.group(1)
            artist_id = int(match.group(2))
        else:
            return 

        full_artist_path = os.path.join(self.data_dir, artist_dir_name)
        
        files = os.listdir(full_artist_path)
        
        for filename in files:
            if filename.startswith('.'):
                continue
                
            # Regex for Pixiv filename (Images and Novels)
            # Image: 12345_p0.jpg, 12345.jpg
            # Novel: 12345.txt (Usually)
            
            # Simple heuristic matching
            # Matches: {ID} or {ID}_p{Page} or {ID}_...
            match_img = re.match(r'(\d+)(?:_p(\d+))?.*\.(jpg|png|gif|jpeg|webp)$', filename, re.IGNORECASE)
            match_txt = re.match(r'(\d+).*\.(txt)$', filename, re.IGNORECASE)
            
            if match_img:
                work_id = int(match_img.group(1))
                p_num = int(match_img.group(2)) if match_img.group(2) is not None else 0
                self._index_file(work_id, p_num, artist_id, artist_name, full_artist_path, filename, 'Illustration')
            elif match_txt:
                work_id = int(match_txt.group(1))
                self._index_file(work_id, 0, artist_id, artist_name, full_artist_path, filename, 'Novel')

    def _parse_filename(self, filename):
        base = os.path.splitext(filename)[0]

        series_id = None
        series_order = None
        series_title = None

        # Check for series info at the end: _%23{Order}-{SeriesID}
        series_pattern = re.search(r'_(%23|#)(\d+)-(\d+)$', base)

        if series_pattern:
            series_order = int(series_pattern.group(2))
            series_id = int(series_pattern.group(3))
            base_without_series = base[:series_pattern.start()]
        else:
            base_without_series = base

        parts = base_without_series.split('_')

        # Part 0: {ID}-{Title}
        if len(parts) >= 1:
            p0 = parts[0]
            if '-' in p0:
                pid, title = p0.split('-', 1)
            else:
                pid = p0
                title = p0
        else:
            pid = base
            title = base

        tags = ""
        # Part 1+: Tags and maybe Series Title
        if len(parts) > 1:
            rest = "_".join(parts[1:])

            if series_id:
                if '-' in rest:
                    tags, series_title = rest.rsplit('-', 1)
                else:
                    tags = rest
            else:
                tags = rest

        # Remove trailing p0/p1 if it was part of title/tags due to parsing error
        # Actually our logic above for Title/Tags might capture _p0 if we don't clean it.
        # But _pX is usually at the very end.
        # If we had series info, we removed the end already.
        # If we didn't have series info, `base` might end with `_p0`.

        return {
            'id': int(pid) if pid.isdigit() else None,
            'title': title,
            'tags': tags,
            'series_id': series_id,
            'series_order': series_order,
            'series_title': series_title
        }

    def _index_file(self, work_id, p_num, artist_id, artist_name, dir_path, filename, work_type):
        work = Work.query.get(work_id)
        
        rel_path = os.path.join(os.path.basename(dir_path), filename)
        full_path = os.path.join(dir_path, filename)
        
        meta = self._parse_filename(filename)

        if not work:
            work = Work(
                id=work_id,
                title=meta['title'],
                tags=meta['tags'],
                work_type=work_type,
                artist_id=artist_id,
                artist_name=artist_name,
                created_at=datetime.utcnow()
            )
            db.session.add(work)
        else:
            # Update metadata if available and seemingly better
            # If current title is just ID or default, and new title is longer, update.
            # Also always update tags if they were empty.
            if meta['title'] and len(meta['title']) > len(str(work_id)):
                 work.title = meta['title']
            
            if meta['tags']:
                work.tags = meta['tags']

            # Upgrade type to Novel if txt found
            if work_type == 'Novel':
                work.work_type = 'Novel'

        # Handle Series
        if meta['series_id']:
            series = Series.query.get(meta['series_id'])
            if not series:
                series = Series(id=meta['series_id'], title=meta['series_title'])
                db.session.add(series)

            work.series_id = meta['series_id']
            work.series_order = meta['series_order']

        # Handle Image/File entry
        if work.work_type == 'Illustration' or (work.work_type == 'Novel' and work_type == 'Illustration'):
             # Even for Novel, we might want to store illustrations (as inserts or covers)
             img = ImageModel.query.filter_by(work_id=work_id, p_num=p_num).first()
             if not img:
                 img = ImageModel(
                     work_id=work_id,
                     p_num=p_num,
                     file_path=rel_path
                 )
                 db.session.add(img)
                 
             if p_num == 0:
                 # If we haven't set a cover yet, or if this is p0, set it.
                 # For Novel, we might want to prioritize using this as cover if no cover exists.
                 if not work.cover_path or work.cover_path.startswith('thumbs/'): # Overwrite generated thumb if we have better one?
                     # Actually we just generate thumb for this image
                     thumb_rel_path = os.path.join(str(artist_id), f"{work_id}.jpg")
                     thumb_full_path = os.path.join(self.thumbs_dir, thumb_rel_path)
                     if generate_thumbnail(full_path, thumb_full_path):
                         work.cover_path = thumb_rel_path
        
        elif work_type == 'Novel':
            # For novels, set file_path to the text file
            work.file_path = rel_path
            # We don't change cover_path here unless we have a logic for novel covers (which we usually don't from txt files)

        db.session.commit()
