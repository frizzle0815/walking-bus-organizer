import os
from app import create_app, db, models
from flask_migrate import upgrade, init, migrate
from sqlalchemy import text

app = create_app()
app.app_context().push()


def check_alembic_version():
    """Check if alembic_version table exists and has data"""
    try:
        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            return result.scalar()
    except Exception:
        return None


def check_db_structure():
    """Check if all expected tables exist and have correct structure"""
    try:
        with db.engine.connect() as conn:
            inspector = db.inspect(conn)
            existing_tables = set(inspector.get_table_names())
            model_tables = set(db.Model.metadata.tables.keys())
            return existing_tables.issuperset(model_tables)
    except Exception as e:
        print(f"Error checking database structure: {e}")
        return False


def handle_migrations():
    """Initialize and handle database migrations"""
    current_version = check_alembic_version()
    
    if current_version:
        print(f"Found existing database with version: {current_version}")
        if not os.path.exists('migrations'):
            print("Recreating migrations structure...")
            init()
    else:
        print("Fresh database detected, initializing migrations...")
        init()
    
    # Always check for structural changes
    if not check_db_structure():
        print("Database structure needs updating, creating migration...")
        migrate()
    
    print("Applying any pending migrations...")
    upgrade()


if __name__ == "__main__":
    handle_migrations()
    print("Starting Flask app...")
    app.run(host="0.0.0.0", port=8000)
