from app import create_app, db
from app.services.indexer import loop, scan_directory
import threading
import sys
import os
import config

app = create_app()

def init_db():
    with app.app_context():
        db.create_all()
        # Add indexes if not created by SQLAlchemy (SQLAlchemy does create indexes defined in models)
        # But auto_indexer.py had manual index creation.
        # SQLAlchemy models defined index=True, so it should be fine.

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'init_db':
        init_db()
        print("Database initialized.")
        sys.exit(0)

    # Ensure DB exists
    if not os.path.exists(config.DB_PATH):
        init_db()
    else:
        # Also ensure tables exist even if file exists
        init_db()

    # Start indexer in background
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true': # Prevent double run in reload mode
        t = threading.Thread(target=loop, args=(app,), daemon=True)
        t.start()

    app.run(host='0.0.0.0', port=5000)
