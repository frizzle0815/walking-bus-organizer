import os
from app import create_app, db
from flask_migrate import upgrade, init, migrate

app = create_app()
app.app_context().push()

# Prüfe, ob das migrations-Verzeichnis existiert
if not os.path.exists('migrations'):
    print("Initialisiere Migrationen...")
    init()  # Führt flask db init aus

# Führe eine Migration durch (falls Änderungen vorliegen)
print("Erstelle Migrationsskripte...")
migrate()

# Wende die Migrationen an
print("Wende Migrationen an...")
upgrade()

# Starte die App
print("Starte Flask-App...")
app.run(host="0.0.0.0", port=8000)