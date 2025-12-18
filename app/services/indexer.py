import os
import re
from datetime import datetime
from app.extensions import db
from app.models import Work, Image as ImageModel, Series
from app.utils import generate_thumbnail
import imagehash
from PIL import Image as PILImage
from app.services.translator import translator

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
                
            match_img = re.match(r'(\d+)(?:_p(\d+))?.*\.(jpg|png|gif|jpeg|webp)$', filename, re.IGNORECASE)
            match_txt = re.match(r'(\d+).*\.(txt)$', filename, re.IGNORECASE)
            
            if match_img:
                work_id = int(match_img.group(1))
                # Initial guess for p_num
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

        if base_without_series.endswith("-_-"):
            base_without_series = base_without_series[:-3]

        parts = base_without_series.split('_')

        # Part 0: usually just ID or ID-Title
        pid = None
        title = None

        # Initial parsing of first part
        if len(parts) >= 1:
            p0 = parts[0]
            if '-' in p0:
                pid_str, title_str = p0.split('-', 1)
                pid = pid_str
                title = title_str
            else:
                pid = p0
                title = p0 # Default title to ID
        else:
            pid = base
            title = base

        tags = ""
        tags_parts = []

        p_override = None

        # Part 1+: Tags, or p{Page}-{Title}, or just tags
        if len(parts) > 1:
            # Check if parts[1] is p{Page}-{Title}
            # Pattern: p\d+-.*
            p_pattern = re.match(r'^p(\d+)-(.*)$', parts[1])
            if p_pattern and pid == p0: # Only if pid was cleanly extracted from p0
                # If we found p{Page}-{Title}, use the title from here
                # And assume subsequent parts are tags
                # And we override the default title=pid
                p_override = int(p_pattern.group(1))
                title = p_pattern.group(2)
                tags_parts = parts[2:]
            else:
                # Standard case
                tags_parts = parts[1:]

            # Reconstruct tags
            if tags_parts:
                rest = "_".join(tags_parts)

                # If series_id is present, series title might be at end of tags
                if series_id:
                    if '-' in rest:
                        tags, series_title = rest.rsplit('-', 1)
                    else:
                        tags = rest
                else:
                    tags = rest

        # Translate tags
        if tags:
            tags = translator.translate_list(tags)

        return {
            'id': int(pid) if pid and pid.isdigit() else None,
            'title': title,
            'tags': tags,
            'series_id': series_id,
            'series_order': series_order,
            'series_title': series_title,
            'p_override': p_override
        }

    def _index_file(self, work_id, p_num, artist_id, artist_name, dir_path, filename, work_type):
        work = Work.query.get(work_id)
        
        rel_path = os.path.join(os.path.basename(dir_path), filename)
        full_path = os.path.join(dir_path, filename)
        
        meta = self._parse_filename(filename)

        # Use overridden p_num if available from filename parsing
        if meta.get('p_override') is not None:
            p_num = meta['p_override']

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
                 if not work.cover_path or work.cover_path.startswith('thumbs/'):
                     thumb_rel_path = os.path.join(str(artist_id), f"{work_id}.jpg")
                     thumb_full_path = os.path.join(self.thumbs_dir, thumb_rel_path)
                     if generate_thumbnail(full_path, thumb_full_path):
                         work.cover_path = thumb_rel_path

                         # Calculate and save phash
                         try:
                             with PILImage.open(thumb_full_path) as img_pil:
                                 ph = str(imagehash.phash(img_pil))
                                 work.phash = ph
                         except Exception as e:
                             print(f"Error calculating hash for {work_id}: {e}")
        
        elif work_type == 'Novel':
            # For novels, set file_path to the text file
            work.file_path = rel_path

        db.session.commit()
