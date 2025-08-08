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
from pywebpush import webpush, WebPushException
import json
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from py_vapid import Vapid


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


def generate_vapid_keys():
    """Generates VAPID keys using py-vapid library"""
    vapid = Vapid()
    vapid.generate_keys()
    
    # Private Key als DER (rohe Bytes für EC Private Key) exportieren
    vapid_private = vapid.private_key.private_bytes(
        encoding=serialization.Encoding.DER,  # Ändern zu DER-Format
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    # Public Key als roher Byte-Array (EC Point) exportieren
    vapid_public_bytes = vapid.public_key.public_bytes(
        encoding=serialization.Encoding.X962,  # Rohformat für EC Public Key
        format=serialization.PublicFormat.UncompressedPoint
    )

    # Public Key in Base64 URL-Safe Format umwandeln
    vapid_public_base64 = base64.urlsafe_b64encode(vapid_public_bytes).decode('utf-8').rstrip("=")

    # Private Key auch in Base64 URL-Safe Format umwandeln
    vapid_private_base64 = base64.urlsafe_b64encode(vapid_private).decode('utf-8').rstrip("=")

    return {
        "private_key": vapid_private_base64,  # Base64 URL-safe kodiert
        "public_key": vapid_public_base64  # Korrektes Web Push Format
    }

def verify_vapid_keys(keys):
    try:
        # Stelle sicher, dass der private Schlüssel in Base64 decodiert und als Bytes verarbeitet wird
        private_key = base64.urlsafe_b64decode(keys['private_key'] + '==')
        
        # Überprüfen, ob der private Schlüssel ein EC-Schlüssel ist
        private_key_obj = ec.derive_private_key(int.from_bytes(private_key, byteorder='big'), ec.SECP256R1())
        
        # Wenn es ein EC-Schlüssel ist, dann funktioniert alles
        if isinstance(private_key_obj, ec.EllipticCurvePrivateKey):
            return True
        return False
    except Exception as e:
        print(f"[VAPID] Key verification failed: {str(e)}")
        return False

def get_or_generate_vapid_keys():
    import logging
    logger = logging.getLogger('vapid')
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    key_path = os.getenv('VAPID_KEY_STORAGE', 
                        os.path.join(base_dir, 'data', 'vapid_keys.json'))
    
    logger.info(f"[INIT.PY][VAPID] Looking for keys at: {key_path}")

    # Try to load existing keys
    if os.path.exists(key_path):
        logger.info(f"[INIT.PY][VAPID] Found existing key file")
        with open(key_path, 'r') as f:
            keys = json.load(f)
            if verify_vapid_keys(keys):
                logger.info(f"[INIT.PY][VAPID] Successfully loaded and verified existing keys")
                return keys
            else:
                logger.warning(f"[INIT.PY][VAPID] Key verification failed for existing keys")
    else:
        logger.warning(f"[INIT.PY][VAPID] No existing key file found at {key_path}")

    # Generate new keys if loading or verification fails
    logger.info(f"[INIT.PY][VAPID] Generating new keys")
    keys = generate_vapid_keys()
    os.makedirs(os.path.dirname(key_path), exist_ok=True)

    with open(key_path, 'w') as f:
        json.dump(keys, f)
    
    logger.info(f"[INIT.PY][VAPID] New keys generated and saved to {key_path}")
    return keys


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

    # Add VAPID public key to app config for frontend access
    from .services.push_service import VAPID_CONFIG
    app.config['VAPID_PUBLIC_KEY'] = VAPID_CONFIG['public_key']
    app.config['VAPID_EMAIL'] = os.getenv('VAPID_EMAIL', 'default@example.com')

    # Add assetlinks fingerprint setup
    if os.environ.get('SHA256_FINGERPRINT'):
        assetlinks_path = os.path.join(app.root_path, '.well-known/assetlinks.json')
        with open(assetlinks_path, 'r') as f:
            data = json.load(f)
            
        data[0]['target']['sha256_cert_fingerprints'] = [os.environ.get('SHA256_FINGERPRINT')]
        
        with open(assetlinks_path, 'w') as f:
            json.dump(data, f, indent=2)
            
        app.logger.info('Updated assetlinks.json with fingerprint')

    return app