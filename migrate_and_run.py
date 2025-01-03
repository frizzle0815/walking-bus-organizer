import os
from app import create_app, db
# Import all models through the models package
from app import models  # This will import all models defined in __init__.py
from flask_migrate import upgrade, init, migrate, stamp
from sqlalchemy import text
from alembic.util.exc import CommandError

app = create_app()
app.app_context().push()

def check_db_structure():
    """Check if all expected tables exist and have correct structure"""
    try:
        with db.engine.connect() as conn:
            # Get all existing tables from database
            inspector = db.inspect(db.engine)
            existing_tables = set(inspector.get_table_names())
            
            # Get all tables defined in models
            model_tables = set(db.Model.metadata.tables.keys())
            
            # Compare existing tables with model tables
            return existing_tables.issuperset(model_tables)
    except Exception as e:
        print(f"Error checking database structure: {e}")
        return False

def handle_migrations():
    """Initialize and handle database migrations"""
    if not os.path.exists('migrations'):
        print("Creating new migrations directory...")
        init()
        
    # Check if we need new migrations
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
