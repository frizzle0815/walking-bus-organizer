from flask import Blueprint, render_template, request, jsonify, current_app, session, redirect, url_for
import logging
import sys
import os

# Hauptverzeichnis zum Python-Pfad hinzufügen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import db, Prospect, WalkingBusRoute
from .services.geocoding_service import GeocodingService
from .auth import is_admin, login_admin, logout_admin, require_admin, admin_or_public_data

bp = Blueprint('registration', __name__)

# Verfügbare Schulklassen
SCHOOL_CLASSES = [
    '1A', '1B', '1C',
    '2A', '2B', '2C', 
    '3A', '3B', '3C',
    '4A', '4B', '4C'
]

@bp.route('/')
def index():
    """Startseite - Karte mit Routen und Anmeldungen"""
    return render_template('registration/map.html')

@bp.route('/register')
def register_form():
    """Registrierungsformular für neue Teilnehmer"""
    routes = WalkingBusRoute.query.filter_by(is_active=True).all()
    return render_template('registration/index.html', 
                         school_classes=SCHOOL_CLASSES,
                         walking_bus_routes=routes)

@bp.route('/routes')
@require_admin
def routes_admin():
    """Routenverwaltung - nur für Admins"""
    return render_template('registration/routes.html')

# Auth Endpunkte
@bp.route('/api/auth/login', methods=['POST'])
def auth_login():
    """Admin-Login"""
    try:
        data = request.get_json()
        password = data.get('password')
        
        if not password:
            return jsonify({'error': 'Passwort erforderlich'}), 400
            
        if login_admin(password):
            return jsonify({'message': 'Erfolgreich angemeldet'}), 200
        else:
            return jsonify({'error': 'Falsches Passwort'}), 401
            
    except Exception as e:
        current_app.logger.error(f"Login-Fehler: {str(e)}")
        return jsonify({'error': 'Login fehlgeschlagen'}), 500

@bp.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    """Admin-Logout"""
    logout_admin()
    return jsonify({'message': 'Erfolgreich abgemeldet'}), 200

@bp.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Admin-Status prüfen"""
    return jsonify({'is_admin': is_admin()}), 200

# Registrierung
@bp.route('/api/register', methods=['POST'])
def register_prospect():
    """API-Endpunkt für Registrierung eines Teilnehmers"""
    try:
        data = request.get_json()
        
        # Validierung
        required_fields = ['child_name', 'school_class', 'phone', 'address']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} ist erforderlich'}), 400
        
        # Schulklasse validieren
        if data['school_class'] not in SCHOOL_CLASSES:
            return jsonify({'error': 'Ungültige Schulklasse'}), 400
            
        # Route validieren (kann null sein für "Nur Interesse")
        walking_bus_route_id = data.get('walking_bus_route_id')
        if walking_bus_route_id and walking_bus_route_id != 'interest_only':
            route = WalkingBusRoute.query.get(walking_bus_route_id)
            if not route or not route.is_active:
                return jsonify({'error': 'Ungültige Walking Bus Route'}), 400
        else:
            walking_bus_route_id = None  # "Nur Interesse anmelden"
        
        # Geocoding durchführen
        geocoding_service = GeocodingService()
        lat, lon, geocoded_address = geocoding_service.geocode_address(data['address'])
        
        if not lat or not lon:
            return jsonify({
                'error': 'Adresse konnte nicht gefunden werden – bitte überprüfen',
                'geocoding_failed': True
            }), 400
        
        # Neuen Teilnehmer erstellen
        prospect = Prospect(
            child_name=data['child_name'],
            school_class=data['school_class'],
            phone=data['phone'],
            email=data.get('email', ''),
            latitude=lat,
            longitude=lon,
            walking_bus_route_id=walking_bus_route_id
        )
        
        db.session.add(prospect)
        db.session.commit()
        
        current_app.logger.info(f"Neuer Teilnehmer registriert: {prospect.child_name} ({prospect.school_class})")
        
        return jsonify({
            'message': 'Registrierung erfolgreich',
            'prospect_id': prospect.id
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Fehler bei Registrierung: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Registrierung fehlgeschlagen'}), 500

# Prospects API
@bp.route('/api/prospects', methods=['GET'])
@admin_or_public_data
def get_prospects(is_admin=False):
    """API-Endpunkt für alle Teilnehmer (sensible Daten nur für Admins)"""
    try:
        prospects = Prospect.query.filter_by(status='active').all()
        
        prospect_data = []
        for prospect in prospects:
            prospect_data.append(prospect.to_dict(include_sensitive=is_admin))
        
        return jsonify(prospect_data), 200
        
    except Exception as e:
        current_app.logger.error(f"Fehler beim Abrufen der Teilnehmer: {str(e)}")
        return jsonify({'error': 'Daten konnten nicht geladen werden'}), 500

@bp.route('/api/prospects/<int:prospect_id>', methods=['GET'])
@require_admin
def get_prospect(prospect_id):
    """API-Endpunkt für einen spezifischen Teilnehmer (Admin only)"""
    try:
        prospect = Prospect.query.get_or_404(prospect_id)
        return jsonify(prospect.to_dict(include_sensitive=True)), 200
        
    except Exception as e:
        current_app.logger.error(f"Fehler beim Abrufen des Teilnehmers: {str(e)}")
        return jsonify({'error': 'Teilnehmer nicht gefunden'}), 404

@bp.route('/api/prospects/<int:prospect_id>', methods=['PUT'])
@require_admin
def update_prospect(prospect_id):
    """API-Endpunkt zum Aktualisieren eines Teilnehmers (Admin only)"""
    try:
        prospect = Prospect.query.get_or_404(prospect_id)
        data = request.get_json()
        
        # Neue Adresse geocodieren falls angegeben
        if 'address' in data and data['address']:
            geocoding_service = GeocodingService()
            lat, lon, geocoded_address = geocoding_service.geocode_address(data['address'])
            
            if not lat or not lon:
                return jsonify({
                    'error': 'Neue Adresse konnte nicht gefunden werden',
                    'geocoding_failed': True
                }), 400
                
            prospect.latitude = lat
            prospect.longitude = lon
        
        # Andere Felder aktualisieren
        if 'child_name' in data:
            prospect.child_name = data['child_name']
        if 'school_class' in data and data['school_class'] in SCHOOL_CLASSES:
            prospect.school_class = data['school_class']
        if 'phone' in data:
            prospect.phone = data['phone']
        if 'email' in data:
            prospect.email = data['email']
        if 'walking_bus_route_id' in data:
            route = WalkingBusRoute.query.get(data['walking_bus_route_id'])
            if route and route.is_active:
                prospect.walking_bus_route_id = data['walking_bus_route_id']
        if 'notes' in data:
            prospect.notes = data['notes']
            
        db.session.commit()
        
        return jsonify({'message': 'Teilnehmer aktualisiert'}), 200
        
    except Exception as e:
        current_app.logger.error(f"Fehler beim Aktualisieren: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Aktualisierung fehlgeschlagen'}), 500

@bp.route('/api/prospects/<int:prospect_id>', methods=['DELETE'])
@require_admin
def delete_prospect(prospect_id):
    """API-Endpunkt zum Löschen eines Teilnehmers (Admin only)"""
    try:
        prospect = Prospect.query.get_or_404(prospect_id)
        db.session.delete(prospect)
        db.session.commit()
        
        return jsonify({'message': 'Teilnehmer gelöscht'}), 200
        
    except Exception as e:
        current_app.logger.error(f"Fehler beim Löschen: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Löschen fehlgeschlagen'}), 500

# Walking Bus Routes API
@bp.route('/api/routes', methods=['GET'])
def get_routes():
    """API-Endpunkt für alle Walking Bus Routen (mit Admin-Filter)"""
    try:
        # Für Admin: alle Routen, für Public: nur aktive
        if is_admin():
            routes = WalkingBusRoute.query.all()
        else:
            routes = WalkingBusRoute.query.filter_by(is_active=True).all()
            
        route_data = [route.to_dict() for route in routes]
        return jsonify(route_data), 200
        
    except Exception as e:
        current_app.logger.error(f"Fehler beim Abrufen der Routen: {str(e)}")
        return jsonify({'error': 'Routen konnten nicht geladen werden'}), 500

@bp.route('/api/routes', methods=['POST'])
@require_admin
def create_route():
    """API-Endpunkt zum Erstellen einer neuen Route (Admin only)"""
    try:
        data = request.get_json()
        
        route = WalkingBusRoute(
            name=data['name'],
            description=data.get('description', ''),
            route_coordinates=data['route_coordinates'],
            color=data.get('color', '#3388ff')
        )
        
        db.session.add(route)
        db.session.commit()
        
        return jsonify(route.to_dict()), 201
        
    except Exception as e:
        current_app.logger.error(f"Fehler beim Erstellen der Route: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Route konnte nicht erstellt werden'}), 500

@bp.route('/api/routes/<int:route_id>', methods=['PUT'])
@require_admin
def update_route(route_id):
    """API-Endpunkt zum Aktualisieren einer Route (Admin only)"""
    try:
        route = WalkingBusRoute.query.get_or_404(route_id)
        data = request.get_json()
        
        if 'name' in data:
            route.name = data['name']
        if 'description' in data:
            route.description = data['description']
        if 'route_coordinates' in data:
            route.route_coordinates = data['route_coordinates']
        if 'color' in data:
            route.color = data['color']
        if 'is_active' in data:
            route.is_active = data['is_active']
            
        db.session.commit()
        
        return jsonify(route.to_dict()), 200
        
    except Exception as e:
        current_app.logger.error(f"Fehler beim Aktualisieren der Route: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Route konnte nicht aktualisiert werden'}), 500

@bp.route('/api/routes/<int:route_id>', methods=['DELETE'])
@require_admin
def delete_route(route_id):
    """API-Endpunkt zum Löschen einer Route (Admin only)"""
    try:
        route = WalkingBusRoute.query.get_or_404(route_id)
        
        # Prüfen ob noch Teilnehmer zugeordnet sind
        if route.prospects:
            return jsonify({'error': 'Route hat noch zugeordnete Teilnehmer'}), 400
            
        db.session.delete(route)
        db.session.commit()
        
        return jsonify({'message': 'Route gelöscht'}), 200
        
    except Exception as e:
        current_app.logger.error(f"Fehler beim Löschen der Route: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Route konnte nicht gelöscht werden'}), 500

# System Info
@bp.route('/api/config', methods=['GET'])
def get_config():
    """API-Endpunkt für Systemkonfiguration"""
    school_coords = os.getenv('SCHOOL_COORDINATES', '52.5200,13.4050').split(',')
    
    try:
        school_lat = float(school_coords[0])
        school_lon = float(school_coords[1])
    except (ValueError, IndexError):
        school_lat, school_lon = 52.5200, 13.4050  # Berlin Default
    
    return jsonify({
        'school_coordinates': [school_lat, school_lon],
        'school_classes': SCHOOL_CLASSES,
        'is_admin': is_admin()
    }), 200
