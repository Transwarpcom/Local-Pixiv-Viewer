import sqlalchemy
from sqlalchemy import text

def update_schema(app, db):
    """
    Idempotent schema migration.
    Checks for missing tables and columns and adds them.
    Supports SQLite.
    """
    with app.app_context():
        # 1. Create tables if they don't exist
        db.create_all()

        # Re-inspect after creation/check
        inspector = sqlalchemy.inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"Tables found: {tables}")

        # 2. Check for missing columns in existing tables
        # Users Table
        if 'users' in tables:
            columns = [c['name'] for c in inspector.get_columns('users')]
            print(f"Users columns found: {columns}")

            with db.engine.connect() as conn:
                if 'recommendation_mode' not in columns:
                    print("Migrating: Adding users.recommendation_mode")
                    conn.execute(text("ALTER TABLE users ADD COLUMN recommendation_mode VARCHAR(20) DEFAULT 'tags'"))
                    conn.commit()

                if 'image_quality' not in columns:
                    print("Migrating: Adding users.image_quality")
                    conn.execute(text("ALTER TABLE users ADD COLUMN image_quality VARCHAR(20) DEFAULT 'original'"))
                    conn.commit()

                if 'enable_r18_blur' not in columns:
                    print("Migrating: Adding users.enable_r18_blur")
                    conn.execute(text("ALTER TABLE users ADD COLUMN enable_r18_blur BOOLEAN DEFAULT 1"))
                    conn.commit()

        # Works Table
        if 'works' in tables:
            columns = [c['name'] for c in inspector.get_columns('works')]
            print(f"Works columns found: {columns}")

            with db.engine.connect() as conn:
                if 'phash' not in columns:
                    print("Migrating: Adding works.phash")
                    conn.execute(text("ALTER TABLE works ADD COLUMN phash VARCHAR(64)"))
                    conn.commit()

        print("Schema verification/update complete.")
