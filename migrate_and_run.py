from app import create_app, db
from flask_migrate import upgrade

# App erstellen
app = create_app()

# Migrationen anwenden
with app.app_context():
    upgrade()

# Anwendung starten
app.run(host="0.0.0.0", port=8000)