from flask import Flask, request, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timedelta
import os
import pytz
import logging
import secrets
import jwt
from logging.handlers import RotatingFileHandler
from zoneinfo import ZoneInfo

db = SQLAlchemy()
migrate = Migrate()

# Define the application's timezone
DEFAULT_TIMEZONE = 'Europe/Berlin'
timezone_name = os.getenv('APP_TIMEZONE', DEFAULT_TIMEZONE)

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
        app.logger.info(f"[REQUEST] Path: {request.path}")
        app.logger.info(f"[REQUEST] Endpoint: {request.endpoint}")
        
        # Define PWA-related paths that should bypass authentication
        pwa_paths = {
            'manifest.json',
            'service-worker.js',
            'static/icons/',
            'static/manifest.json'
        }
        
        # Skip validation for PWA resources and static files
        if any(path in request.path for path in pwa_paths) or \
           (request.endpoint and 'static' in request.endpoint):
            app.logger.info("[PWA] Bypassing auth for PWA/static resource")
            return None

        if request.endpoint and 'static' not in request.endpoint:
            # Check JWT token first
            token = request.cookies.get('auth_token')
            app.logger.info(f"[TOKEN] Found in cookies: {bool(token)}")
            
            if not token:
                token = request.headers.get('Authorization', '').replace('Bearer ', '')
                app.logger.info(f"[TOKEN] Found in headers: {bool(token)}")
            
            if token:
                try:
                    app.logger.info("[TOKEN] Attempting to decode")
                    payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
                    app.logger.info(f"[TOKEN] Payload: {payload}")
                    
                    walking_bus_id = payload.get('walking_bus_id')
                    bus_password_hash = payload.get('bus_password_hash')
                    app.logger.info(f"[BUS] Walking bus ID: {walking_bus_id}")
                    
                    # Get current bus configuration
                    buses_env = os.environ.get('WALKING_BUSES', '').strip()
                    if buses_env:
                        bus_configs = dict(
                            (int(b.split(':')[0]), hash(b.split(':')[2]))
                            for b in buses_env.split(',')
                            if len(b.split(':')) == 3
                        )
                        app.logger.info(f"[BUS] Available configs: {list(bus_configs.keys())}")
                        
                        # Validate bus ID and password hash from token
                        if walking_bus_id in bus_configs:
                            app.logger.info("[VALIDATION] Bus ID found in configs")
                            if bus_password_hash == bus_configs[walking_bus_id]:
                                app.logger.info("[VALIDATION] Password hash matches")
                                session['walking_bus_id'] = walking_bus_id
                                session['bus_password_hash'] = bus_password_hash
                                session.permanent = True
                                return None
                            else:
                                app.logger.info("[VALIDATION] Password hash mismatch")
                        else:
                            app.logger.info("[VALIDATION] Bus ID not found in configs")
                except jwt.InvalidTokenError as e:
                    app.logger.info(f"[ERROR] Token validation failed: {str(e)}")
            else:
                app.logger.info("[TOKEN] No token found")
            
            # Clear session if validation fails
            app.logger.info("[SESSION] Clearing and redirecting to login")
            session.clear()
            if request.endpoint != 'main.login':
                return redirect(url_for('main.login'))

    # Auth token capture middleware
    @app.after_request
    def capture_auth_token(response):
        if 'X-Auth-Token' in response.headers:
            response.headers['Access-Control-Expose-Headers'] = 'X-Auth-Token'
        return response

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Register blueprints
    from .routes import bp
    app.register_blueprint(bp)

    return app
