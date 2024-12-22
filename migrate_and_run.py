import os
from app import create_app, db
from flask_migrate import upgrade, init, migrate, stamp
from alembic.util.exc import CommandError

app = create_app()
app.app_context().push()

if not os.path.exists('migrations'):
    print("Creating migrations directory...")
    init()
    
    # Stamp the database with the current state without creating new migrations
    print("Stamping database with current state...")
    stamp('head')
    
    print("Creating initial migration...")
    migrate()

print("Applying migrations...")
upgrade()

print("Starting Flask app...")
app.run(host="0.0.0.0", port=8000)