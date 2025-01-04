import os
from app import create_app, db
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

# Get current version if it exists
current_version = check_alembic_version()

if current_version:
    print(f"Found existing database with version: {current_version}")
else:
    print("Fresh database detected.")

# Check if the migrations directory exists
if not os.path.exists('migrations'):
    print("Initializing migrations directory...")
    init()
else:
    print("Migrations directory already exists.")

# Always create a migration if the database structure needs updating
if not current_version or not os.path.exists(f'migrations/versions/{current_version}_initial_migration.py'):
    print("Creating initial migration script...")
    migrate()

print("Applying any pending migrations...")
upgrade()
