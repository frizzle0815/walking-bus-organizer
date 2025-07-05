from flask import Flask
import os
import logging
import sys

# Hauptverzeichnis zum Python-Pfad hinzufügen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Verwende die SQLAlchemy-Instanz aus der Haupt-App
from app import db

def create_app():
    app = Flask(__name__)
    
    # Konfiguration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    database_url = os.getenv('DATABASE_URL', 'postgresql://walkingbus:password@localhost:5432/walkingbus')
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Session-Konfiguration für Admin-Login
    app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 Stunde
    
    # Logging
    logging.basicConfig(level=logging.INFO)
    app.logger.setLevel(logging.INFO)
    
    # Extensions - verwende die existierende db-Instanz
    db.init_app(app)
    
    # Blueprints
    from .routes import bp
    app.register_blueprint(bp)
    
    # Import models für Initialisierung
    from app.models import Prospect, WalkingBusRoute
    
    return app
