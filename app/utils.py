import os
from PIL import Image
import urllib.parse

def generate_thumbnail(source_path, dest_path, size=(360, 360)):
    """Generates a JPEG thumbnail."""
    try:
        if not os.path.exists(source_path):
            return False
            
        # Ensure destination directory exists
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        
        with Image.open(source_path) as img:
            # Convert to RGB if necessary (e.g. PNG with alpha)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
                
            img.thumbnail(size)
            img.save(dest_path, "JPEG", quality=85)
        return True
    except Exception as e:
        print(f"Error generating thumbnail for {source_path}: {e}")
        return False

def url_quote(s):
    return urllib.parse.quote(s)
