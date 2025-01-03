from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
import os
import pytz
import logging
from logging.handlers import RotatingFileHandler
from zoneinfo import ZoneInfo

db = SQLAlchemy()
migrate = Migrate()

# Define the application's timezone
# Get timezone from environment variable or use default
DEFAULT_TIMEZONE = 'Europe/Berlin'
timezone_name = os.getenv('APP_TIMEZONE', DEFAULT_TIMEZONE)

try:
    TIMEZONE = ZoneInfo(timezone_name)
except Exception:
    TIMEZONE = pytz.timezone(timezone_name)

# Add this to centralize weekday mapping
WEEKDAY_MAPPING = {
    0: 'monday',
    1: 'tuesday',
    2: 'wednesday',
    3: 'thursday',
    4: 'friday',
    5: 'saturday',
    6: 'sunday'
}


def get_current_time():
    """Get current time in application timezone"""
    return datetime.now(TIMEZONE)


def get_current_date():
    """Get current date in application timezone"""
    return get_current_time().date()


class RequestFormatter(logging.Formatter):
    def format(self, record):
        # Add request information to the record
        if request:
            record.client_ip = request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or request.remote_addr
        else:
            record.client_ip = '-'
        return f"[{self.formatTime(record)}] [{record.client_ip}] {record.getMessage()}"


def create_app():
    app = Flask(__name__)

    # Configure logging
    if not app.debug:
        # Create logs directory if it doesn't exist
        if not os.path.exists('logs'):
            os.mkdir('logs')
            
        # Set up file handler
        file_handler = RotatingFileHandler('logs/walking_bus.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        
        # Set up console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        
        # Add handlers to app logger
        app.logger.addHandler(file_handler)
        app.logger.addHandler(console_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Walking Bus startup')

    # Get DATABASE_URL from environment, fallback to localhost for local development
    database_url = os.getenv('DATABASE_URL', 'postgresql://walkingbus:password@localhost:5432/walkingbus')

    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    migrate.init_app(app, db)

    from .routes import bp
    app.register_blueprint(bp)

    return app
