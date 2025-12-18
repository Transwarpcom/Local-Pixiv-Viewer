import os
import re
from datetime import datetime
from app.extensions import db
from app.models import Work, Image as ImageModel
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

    def _index_file(self, work_id, p_num, artist_id, artist_name, dir_path, filename, work_type):
        work = Work.query.get(work_id)
        
        rel_path = os.path.join(os.path.basename(dir_path), filename)
        full_path = os.path.join(dir_path, filename)
        
        if not work:
            # Parse Title/Tags if available in filename
            # Heuristic: ID_Title_Tags_p0.ext or similar
            title = f"Work {work_id}"
            tags = ""
            
            base = os.path.splitext(filename)[0]
            parts = base.split('_')
            # Check for p_num at end
            if len(parts) > 1 and parts[-1].startswith('p') and parts[-1][1:].isdigit():
                parts = parts[:-1]
                
            # ID is parts[0]
            if len(parts) > 1:
                # Assume parts[1] is title
                title = parts[1]
                if len(parts) > 2:
                    tags = ",".join(parts[2:])
            
            work = Work(
                id=work_id,
                title=title,
                tags=tags,
                work_type=work_type,
                artist_id=artist_id,
                artist_name=artist_name,
                created_at=datetime.utcnow()
            )
            db.session.add(work)
            
        # Handle Image/File entry
        # For novels, we treat the txt file as p_num=0 image entry essentially, or just rely on work.file_path
        if work_type == 'Illustration':
             img = ImageModel.query.filter_by(work_id=work_id, p_num=p_num).first()
             if not img:
                 img = ImageModel(
                     work_id=work_id,
                     p_num=p_num,
                     file_path=rel_path
                 )
                 db.session.add(img)
                 
             if p_num == 0:
                 work.file_path = rel_path
                 # Generate thumbnail
                 thumb_rel_path = os.path.join(str(artist_id), f"{work_id}.jpg")
                 thumb_full_path = os.path.join(self.thumbs_dir, thumb_rel_path)
                 if generate_thumbnail(full_path, thumb_full_path):
                     work.cover_path = thumb_rel_path
        
        elif work_type == 'Novel':
            # For novels, set file_path to the text file
            if not work.file_path:
                work.file_path = rel_path
                # Novel thumbnail? Maybe generate a default one or try to find a cover image if Pixiv provides one separately.
                # Since we don't have a cover image file, we might leave cover_path null or use a placeholder in frontend.
                pass

        db.session.commit()
