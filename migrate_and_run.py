import os
from app import create_app, db, models  # models import ensures all models are loaded
from flask_migrate import upgrade, init, migrate

app = create_app()
app.app_context().push()


def check_db_structure():
    """Check if all expected tables exist and have correct structure"""
    try:
        with db.engine.connect() as conn:
            inspector = db.inspect(db.engine)
            existing_tables = set(inspector.get_table_names())
            model_tables = set(db.Model.metadata.tables.keys())
            return existing_tables.issuperset(model_tables)
    except Exception as e:
        print(f"Error checking database structure: {e}")
        return False


def handle_migrations():
    """Initialize and handle database migrations"""
    if not os.path.exists('migrations'):
        print("Creating new migrations directory...")
        init()
        
    with app.app_context():
        if not check_db_structure():
            print("Database structure needs updating, creating migration...")
            migrate()
            
    print("Applying any pending migrations...")
    upgrade()


if __name__ == "__main__":
    handle_migrations()
    print("Starting Flask app...")
    app.run(host="0.0.0.0", port=8000)
