from functools import wraps
from flask import request, redirect, url_for
import jwt
import os

# Kryptographischer Key für JWT - muss existieren
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')

# Optionales Zugangspasswort - None wenn nicht gesetzt
APP_PASSWORD = os.getenv('APP_PASSWORD', None)

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Wenn kein Passwort konfiguriert: direkter Zugriff
        if APP_PASSWORD is None:
            return f(*args, **kwargs)
            
        # Sonst: Token-Check
        token = request.cookies.get('auth_token')
        if not token:
            return redirect(url_for('main.login'))
        try:
            jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            return f(*args, **kwargs)
        except:
            return redirect(url_for('main.login'))
    return decorated