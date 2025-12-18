import os
import threading
import time
import sys
from app import create_app, db
from app.services.indexer import Indexer
from app.models import User
from app.migration import update_schema
from app.services.translator import translator

app = create_app()

def run_indexer():
    # Loop needs to be outside app context to allow refreshing context/session
    while True:
        try:
            with app.app_context():
                print("Starting index cycle...")
                indexer = Indexer(app.config)
                indexer.run()
                print("Index cycle complete.")
        except Exception as e:
            print(f"Indexer error: {e}")
        
        time.sleep(app.config['SCAN_INTERVAL'])

def run_translator_update():
    """Background task to update translation database."""
    with app.app_context():
        # Check if cache exists is handled inside, but we can force check or just call download
        if not translator.loaded or not os.path.exists(translator.cache_path):
            print("Downloading dictionary in background...")
            translator.download_full_dictionary()

# Auto-migrate on startup
if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
    # Run migration only once (in main process if prod, or in reloader child if debug)
    # Actually, simplest is to just run it. Idempotency protects us.
    try:
        update_schema(app, db)
    except Exception as e:
        print(f"Migration error: {e}")

if __name__ == '__main__':
    # Start indexer thread
    if not os.environ.get("WERKZEUG_RUN_MAIN") == "true": 
        # Only start in the main process, not the reloader
        indexer_thread = threading.Thread(target=run_indexer, daemon=True)
        indexer_thread.start()

        translator_thread = threading.Thread(target=run_translator_update, daemon=True)
        translator_thread.start()
    
    app.run(host='0.0.0.0', port=8362, debug=True)
