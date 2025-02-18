from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta
import os
import pytz
import logging
import secrets
import subprocess
from logging.handlers import RotatingFileHandler
from zoneinfo import ZoneInfo
from redis import Redis


db = SQLAlchemy()
migrate = Migrate()


# Define the application's timezone
DEFAULT_TIMEZONE = 'Europe/Berlin'
DEFAULT_REDIS_URL = 'redis://localhost:6379'
timezone_name = os.getenv('APP_TIMEZONE', DEFAULT_TIMEZONE)
redis_url = os.getenv('REDIS_URL', DEFAULT_REDIS_URL)
redis_client = Redis.from_url(redis_url)

try:
    TIMEZONE = ZoneInfo(timezone_name)
except Exception:
    TIMEZONE = pytz.timezone(timezone_name)

# Centralized weekday mapping
WEEKDAY_MAPPING = {
    0: 'monday',
    1: 'tuesday',
    2: 'wednesday',
    3: 'thursday',
    4: 'friday',
    5: 'saturday',
    6: 'sunday'
}


def get_git_revision():
    # First check for build-time revision file
    if os.path.exists('git_revision.txt'):
        with open('git_revision.txt', 'r') as f:
            revision = f.read().strip()
            return {'short': revision[:7], 'full': revision}
    
    # Fallback to git command for development
    try:
        short_hash = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
        full_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()
        return {'short': short_hash, 'full': full_hash}
    except:
        return {'short': 'unknown', 'full': 'unknown'}


def get_current_time():
    """Get current time in application timezone"""
    return datetime.now(TIMEZONE)


def get_current_date():
    """Get current date in application timezone"""
    return get_current_time().date()


class RequestFormatter(logging.Formatter):
    def format(self, record):
        if request:
            record.client_ip = request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or request.remote_addr
        else:
            record.client_ip = '-'
        return f"[{self.formatTime(record)}] [{record.client_ip}] {record.getMessage()}"


def create_app():
    app = Flask(__name__)

    # Security Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365)
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
    
    # Add bus configuration timestamp
    app.config['BUS_CONFIG_TIMESTAMP'] = datetime.now(TIMEZONE).timestamp()
    
    # Database Configuration
    database_url = os.getenv('DATABASE_URL', 'postgresql://walkingbus:password@localhost:5432/walkingbus')
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Session validation middleware
    @app.before_request
    def validate_session():
        # Only check for PWA resources
        pwa_paths = {
            'manifest.json',
            'service-worker.js',
            'static/icons/',
            'static/manifest.json'
        }
        
        if any(path in request.path for path in pwa_paths) or \
           (request.endpoint and 'static' in request.endpoint):
            return None

    # Auth token capture middleware
    @app.after_request
    def capture_auth_token(response):
        if 'X-Auth-Token' in response.headers:
            response.headers['Access-Control-Expose-Headers'] = 'X-Auth-Token'
        return response

    # Configure logging
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        file_handler = RotatingFileHandler('logs/walking_bus.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        
        app.logger.addHandler(file_handler)
        app.logger.addHandler(console_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Walking Bus startup')

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Register blueprints
    from .routes import bp
    app.register_blueprint(bp)

    return app