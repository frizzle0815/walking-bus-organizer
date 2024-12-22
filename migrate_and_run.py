import os
from app import create_app, db
from flask_migrate import upgrade, init, migrate
from alembic.util.exc import CommandError

app = create_app()
app.app_context().push()

try:
    # Try to upgrade directly first
    print("Attempting to upgrade database...")
    upgrade()
except CommandError:
    # If that fails, initialize and create new migration
    if not os.path.exists('migrations'):
        print("Initializing migrations...")
        init()
    
    print("Creating migration scripts...")
    migrate()
    
    print("Applying migrations...")
    upgrade()

print("Starting Flask app...")
app.run(host="0.0.0.0", port=8000)