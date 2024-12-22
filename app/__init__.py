from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
import os
import pytz

db = SQLAlchemy()
migrate = Migrate()

# Define the application's timezone
TIMEZONE = pytz.timezone('Europe/Berlin')

def get_current_time():
    """Get current time in application timezone"""
    return datetime.now(TIMEZONE)

def get_current_date():
    """Get current date in application timezone"""
    return get_current_time().date()

def create_app():
    app = Flask(__name__)
    
    # Get DATABASE_URL from environment, fallback to localhost for local development
    database_url = os.getenv('DATABASE_URL', 'postgresql://walkingbus:password@localhost:5432/walkingbus')
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    migrate.init_app(app, db)

    from .routes import bp
    app.register_blueprint(bp)

    return app