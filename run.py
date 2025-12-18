import os
import threading
import time
import sys
from app import create_app, db
from app.services.indexer import Indexer
from app.models import User

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

@app.cli.command("init_db")
def init_db_command():
    init_db()

def init_db():
    db.create_all()
    print("Database initialized.")

if __name__ == '__main__':
    # Handle init_db command specifically to match user instructions
    if len(sys.argv) > 1 and sys.argv[1] == 'init_db':
        with app.app_context():
            init_db()
        sys.exit(0)

    # Start indexer thread
    if not os.environ.get("WERKZEUG_RUN_MAIN") == "true": 
        # Only start in the main process, not the reloader
        indexer_thread = threading.Thread(target=run_indexer, daemon=True)
        indexer_thread.start()
    
    app.run(host='0.0.0.0', port=8362, debug=True)
