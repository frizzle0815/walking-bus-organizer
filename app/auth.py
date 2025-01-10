from functools import wraps
from flask import request, redirect, url_for, jsonify
from flask import current_app
from datetime import datetime, timedelta
from collections import defaultdict
from math import ceil
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


def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            current_app.logger.info(f"[AUTH.PY][AUTH] No token in request headers")
            return jsonify({"error": "No token provided", "redirect": True}), 401
        
        try:
            # Decode and verify token
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            
            # Verify walking bus ID from environment
            walking_bus_id = payload.get('walking_bus_id')
            buses_env = os.environ.get('WALKING_BUSES', '').strip()
            
            if buses_env:
                bus_configs = dict(
                    (int(b.split(':')[0]), hash(b.split(':')[2]))
                    for b in buses_env.split(',')
                    if len(b.split(':')) == 3
                )
                
                if walking_bus_id not in bus_configs:
                    current_app.logger.info(f"[AUTH.PY][AUTH] Invalid bus ID: {walking_bus_id}")
                    return jsonify({"error": "Invalid bus ID", "redirect": True}), 401
                    
                if payload.get('bus_password_hash') != bus_configs[walking_bus_id]:
                    current_app.logger.info(f"[AUTH.PY][AUTH] Invalid password hash")
                    return jsonify({"error": "Invalid credentials", "redirect": True}), 401
            
            return f(*args, **kwargs)
            
        except jwt.ExpiredSignatureError:
            current_app.logger.info(f"[AUTH.PY][AUTH] Token expired")
            return jsonify({"error": "Token expired", "redirect": True}), 401
        except jwt.InvalidTokenError:
            current_app.logger.info(f"[AUTH.PY][AUTH] Invalid token")
            return jsonify({"error": "Invalid token", "redirect": True}), 401
    
    return decorated_function

