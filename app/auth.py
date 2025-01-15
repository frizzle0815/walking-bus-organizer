from functools import wraps
from flask import request, jsonify
from flask import current_app
from flask import session
from flask import render_template, url_for
from datetime import datetime, timedelta
from collections import defaultdict
from hashlib import sha256
from math import ceil
from . import db
from .models import TempToken
import jwt
import os
import qrcode
import io
import base64
import secrets
import string

# JWT Configuration
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')

# Brute Force Protection Configuration
login_attempts = defaultdict(list)
MAX_ATTEMPTS = 5
LOCKOUT_TIME = timedelta(minutes=30)


def is_ip_allowed():
    ip = request.remote_addr
    now = datetime.now()
    
    # Remove old attempts
    login_attempts[ip] = [attempt for attempt in login_attempts[ip]
                         if now - attempt < LOCKOUT_TIME]
    
    # Check if too many attempts
    if len(login_attempts[ip]) >= MAX_ATTEMPTS:
        newest_attempt = max(login_attempts[ip])
        lockout_end = newest_attempt + LOCKOUT_TIME
        
        current_app.logger.info(
            f"IP {ip} locked out due to too many attempts. "
            f"Next attempt allowed after: {lockout_end.strftime('%H:%M:%S')}"
        )
        return False
    return True


def record_attempt():
    """
    Records a failed login attempt only if the IP is not currently locked out
    """
    ip = request.remote_addr
    if is_ip_allowed():  # Only record if not currently locked out
        login_attempts[ip].append(datetime.now())
        
        # Log the failed attempt
        current_app.logger.info(
            f"Failed login attempt from IP: {ip}. "
            f"Total attempts: {len(login_attempts[ip])}"
        )


def get_remaining_lockout_time(ip):
    """
    Calculate the remaining lockout time for a given IP address
    Returns remaining minutes rounded up to the next full minute
    """
    now = datetime.now()
    if ip in login_attempts and login_attempts[ip]:
        newest_attempt = max(login_attempts[ip])
        lockout_end = newest_attempt + LOCKOUT_TIME
        if now < lockout_end:
            remaining = lockout_end - now
            return ceil(remaining.total_seconds() / 60)
    return 0


def get_consistent_hash(text):
    """
    Creates a consistent SHA-256 hash for the given text
    Returns a hex string representation of the hash
    """
    return sha256(str(text).encode()).hexdigest()


def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token and 'auth_token' in session:
            token = session['auth_token']
            current_app.logger.info("[AUTH.PY][AUTH] Using token from session")
        
        if not token:
            current_app.logger.info("[AUTH.PY][AUTH] No token found in any storage")
            return jsonify({"error": "No token provided", "redirect": True}), 401
        
        try:
            # Decode and verify token
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            
            # Verify walking bus ID from environment
            walking_bus_id = payload.get('walking_bus_id')
            buses_env = os.environ.get('WALKING_BUSES', '').strip()
            
            if buses_env:
                bus_configs = dict(
                    (int(b.split(':')[0]), get_consistent_hash(b.split(':')[2]))
                    for b in buses_env.split(',')
                    if len(b.split(':')) == 3
                )
                
                if walking_bus_id not in bus_configs:
                    current_app.logger.info(f"[AUTH.PY][AUTH] Invalid bus ID: {walking_bus_id}")
                    return jsonify({"error": "Invalid bus ID", "redirect": True}), 401
                    
                if payload.get('bus_password_hash') != bus_configs[walking_bus_id]:
                    current_app.logger.info(f"[AUTH.PY][AUTH] Invalid password hash")
                    return jsonify({"error": "Invalid credentials", "redirect": True}), 401
            
            # Store valid token and walking bus info in session
            session['auth_token'] = token
            session['walking_bus_id'] = walking_bus_id
            session['walking_bus_name'] = payload.get('walking_bus_name')
            session['bus_password_hash'] = payload.get('bus_password_hash')
            current_app.logger.info("[AUTH.PY][AUTH] Stored valid token and bus info in session")
            
            return f(*args, **kwargs)
            
        except jwt.ExpiredSignatureError:
            current_app.logger.info(f"[AUTH.PY][AUTH] Token expired")
            return jsonify({"error": "Token expired", "redirect": True}), 401
        except jwt.InvalidTokenError:
            current_app.logger.info(f"[AUTH.PY][AUTH] Invalid token")
            return jsonify({"error": "Invalid token", "redirect": True}), 401
    
    return decorated_function


# Configuration constants
MAX_TEMP_TOKENS = 3
TOKEN_VALIDITY_MINUTES = 30
TOKEN_LENGTH = 10


def generate_short_token(length=TOKEN_LENGTH):
    """Generate a random token of specified length"""
    alphabet = string.ascii_letters + string.digits
    while True:
        token = ''.join(secrets.choice(alphabet) for _ in range(length))
        # Check database for uniqueness instead of temp_tokens
        if not TempToken.query.get(token):
            return token


def generate_temp_token():
    """Generate a temporary token for sharing"""
    cleanup_expired_tokens()
    
    # Check existing tokens count for current walking bus
    current_tokens = TempToken.query.filter(
        TempToken.walking_bus_id == session['walking_bus_id'],
        TempToken.expiry > datetime.now()
    ).count()
    
    if current_tokens >= MAX_TEMP_TOKENS:
        return jsonify({
            "error": f"Die maximale Anzahl von {MAX_TEMP_TOKENS} temporären Links wurde erreicht."
        }), 400
    
    token = generate_short_token()
    expiry_time = datetime.now() + timedelta(minutes=TOKEN_VALIDITY_MINUTES)
    
    # Create new token in database
    new_token = TempToken(
        id=token,
        expiry=expiry_time,
        walking_bus_id=session['walking_bus_id'],
        walking_bus_name=session['walking_bus_name'],
        bus_password_hash=session['bus_password_hash'],
        created_by=session['walking_bus_id']
    )
    db.session.add(new_token)
    db.session.commit()
    
    # Generate share URL and QR code
    share_url = url_for('main.temp_login_route', token=token, _external=True)
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(share_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = io.BytesIO()
    qr_img.save(buffered, format="PNG")
    qr_code_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    return jsonify({
        'token': token,
        'share_url': share_url,
        'qr_code': qr_code_base64,
        'expires_in': TOKEN_VALIDITY_MINUTES
    })


def get_active_temp_tokens():
    """Get all active temporary tokens with remaining validity time"""
    cleanup_expired_tokens()
    current_time = datetime.now()
    
    tokens = TempToken.query.filter(
        TempToken.walking_bus_id == session['walking_bus_id'],
        TempToken.expiry > current_time
    ).all()
    
    active_tokens = []
    for token in tokens:
        remaining_time = (token.expiry - current_time).total_seconds() / 60
        url = url_for('main.temp_login_route', token=token.id, _external=True)
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        buffered = io.BytesIO()
        qr_img.save(buffered, format="PNG")
        qr_code_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        active_tokens.append({
            'token': token.id,
            'url': url,
            'remaining_minutes': int(remaining_time),
            'created_at': token.created_at,
            'qr_code': qr_code_base64
        })
    
    # Return dictionary instead of jsonify response
    return {
        'tokens': sorted(active_tokens, key=lambda x: x['remaining_minutes'], reverse=True),
        'count': len(tokens),
        'max': MAX_TEMP_TOKENS
    }


def temp_login(token):
    """Handle temporary token login"""
    try:
        token_data = TempToken.query.get(token)
        if not token_data:
            return jsonify({"error": "Ungültiger Login Link"}), 401
        
        if datetime.now() > token_data.expiry:
            db.session.delete(token_data)
            db.session.commit()
            return jsonify({"error": "Der Login Link ist bereits abgelaufen"}), 401
        
        auth_token = jwt.encode({
            'exp': datetime.now() + timedelta(hours=72),
            'walking_bus_id': token_data.walking_bus_id,
            'walking_bus_name': token_data.walking_bus_name,
            'bus_password_hash': token_data.bus_password_hash
        }, SECRET_KEY, algorithm='HS256')
        
        return jsonify({
            "success": True,
            "auth_token": auth_token,
            "redirect_url": "/"
        })
    
    except Exception as e:
        return jsonify({"error": "Ungültiger Login Link"}), 401


def cleanup_expired_tokens():
    """Remove expired temporary tokens from database"""
    TempToken.query.filter(TempToken.expiry < datetime.now()).delete()
    db.session.commit()
