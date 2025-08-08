from flask import session, request, jsonify, current_app
from functools import wraps
import os

def is_admin():
    """Prüft ob aktueller Benutzer als Admin angemeldet ist"""
    return session.get('is_admin', False)

def check_admin_password(password):
    """Prüft ob gegebenes Passwort korrekt ist"""
    admin_password = os.getenv('ADMIN_PASSWORD')
    if not admin_password:
        current_app.logger.warning("ADMIN_PASSWORD Umgebungsvariable nicht gesetzt")
        return False
    return password == admin_password

def login_admin(password):
    """Meldet Admin an, wenn Passwort korrekt ist"""
    if check_admin_password(password):
        session['is_admin'] = True
        session.permanent = True  # Session bleibt bestehen
        return True
    return False

def logout_admin():
    """Meldet Admin ab"""
    session.pop('is_admin', None)

def require_admin(f):
    """Decorator für Admin-only Routen"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin():
            return jsonify({'error': 'Admin-Berechtigung erforderlich'}), 403
        return f(*args, **kwargs)
    return decorated_function

def admin_or_public_data(f):
    """Decorator der je nach Admin-Status unterschiedliche Daten zurückgibt"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Admin-Status an die Route weitergeben
        kwargs['is_admin'] = is_admin()
        return f(*args, **kwargs)
    return decorated_function
