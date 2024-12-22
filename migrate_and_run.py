import os
from app import create_app, db
from flask_migrate import upgrade, init, migrate, stamp, current
from alembic.util.exc import CommandError

app = create_app()
app.app_context().push()

if not os.path.exists('migrations'):
    print("Creating migrations directory...")
    init()
    
    print("Creating initial migration...")
    migrate()
    
    print("Marking database as current...")
    with app.app_context():
        stamp()  # Using stamp() without parameters uses current head

print("Applying migrations...")
upgrade()

print("Starting Flask app...")
app.run(host="0.0.0.0", port=8000)