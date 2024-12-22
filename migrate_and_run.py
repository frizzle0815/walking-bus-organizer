import os
from app import create_app
from flask_migrate import upgrade, init, migrate

app = create_app()
app.app_context().push()

# Always create migrations directory if it doesn't exist
if not os.path.exists('migrations'):
    print("Creating migrations directory...")
    init()
    print("Creating initial migration...")
    migrate()
else:
    print("Migrations directory exists, checking for new changes...")
    migrate()

print("Applying migrations...")
upgrade()

print("Starting Flask app...")
app.run(host="0.0.0.0", port=8000)