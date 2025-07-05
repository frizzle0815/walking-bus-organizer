#!/usr/bin/env python3
"""
Startup-Script für die Registrierungs-App
"""
import os
import sys

# Hauptverzeichnis zum Python-Pfad hinzufügen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from registration_app import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8001))  # Default auf 8001 geändert
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug)
