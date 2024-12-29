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
    if not os.path.exists('migrations'):
        print("Recreating migrations structure...")
        init()
        
        # Create an empty migration matching current DB state
        with open(f'migrations/versions/{current_version}_initial_migration.py', 'w') as f:
            f.write(f"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '{current_version}'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    pass

def downgrade():
    pass
""")
else:
    print("Fresh database detected, initializing migrations...")
    init()
    migrate()

print("Applying any pending migrations...")
upgrade()
