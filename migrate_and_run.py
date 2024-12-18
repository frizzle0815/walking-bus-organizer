from app import app, db
from flask_migrate import upgrade

# Migrationen anwenden
with app.app_context():
    upgrade()

# Anwendung starten
app.run(host="0.0.0.0", port=8000)