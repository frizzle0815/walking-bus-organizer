from functools import wraps
from flask import request, redirect, url_for
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
        
        current_app.logger.warning(
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
        current_app.logger.warning(
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
        token = request.cookies.get('auth_token') or \
                request.headers.get('Authorization', '').replace('Bearer ', '')
        
        if not token:
            return redirect(url_for('main.login'))
            
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            return redirect(url_for('main.login'))
        except jwt.InvalidTokenError:
            return redirect(url_for('main.login'))
            
    return decorated_function
