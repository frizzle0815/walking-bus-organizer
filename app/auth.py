from functools import wraps
from flask import request, redirect, url_for
from flask import current_app
from datetime import datetime, timedelta
from collections import defaultdict
import jwt
import os

# JWT Configuration
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
APP_PASSWORD = os.getenv('APP_PASSWORD', None)

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
        # Use total_seconds() and convert to minutes
        minutes = int(LOCKOUT_TIME.total_seconds() / 60)
        current_app.logger.warning(
            f"IP {ip} locked out due to too many attempts. "
            f"Next attempt allowed after: {now + timedelta(minutes=minutes)}"
        )
        return False
    return True


def record_attempt():
    ip = request.remote_addr
    login_attempts[ip].append(datetime.now())
    
    # Log the failed attempt
    current_app.logger.warning(
        f"Failed login attempt from IP: {ip}. "
        f"Total attempts: {len(login_attempts[ip])}"
    )


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if APP_PASSWORD is None:
            return f(*args, **kwargs)
            
        token = request.cookies.get('auth_token')
        if not token:
            return redirect(url_for('main.login'))
        try:
            jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            return f(*args, **kwargs)
        except jwt.InvalidTokenError:
            # Handles all JWT-specific exceptions
            return redirect(url_for('main.login'))
        except jwt.ExpiredSignatureError:
            # Optional: handle expired tokens specifically
            return redirect(url_for('main.login'))
    return decorated
