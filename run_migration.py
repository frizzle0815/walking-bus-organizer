#!/usr/bin/env python3
"""
Script zum Ausführen der Migration für die Prospects-Tabelle
"""
import os
import sys

# Hauptverzeichnis zum Python-Pfad hinzufügen
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Prospect

def run_migration():
    app = create_app()
    
    with app.app_context():
        print("Erstelle Prospects-Tabelle...")
        
        # Prüfe ob Tabelle bereits existiert
        if not db.engine.dialect.has_table(db.engine, 'prospects'):
            db.create_all()
            print("✅ Prospects-Tabelle wurde erstellt")
        else:
            print("ℹ️  Prospects-Tabelle existiert bereits")

if __name__ == '__main__':
    run_migration()
