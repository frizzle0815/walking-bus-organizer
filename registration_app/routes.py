from flask import Blueprint, render_template, request, jsonify, current_app
import logging
import sys
import os

# Hauptverzeichnis zum Python-Pfad hinzufügen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import db, Prospect, Route
from .services.geocoding_service import GeocodingService

bp = Blueprint('registration', __name__)

@bp.route('/')
def index():
    """Hauptseite mit Registrierungsformular"""
    routes = Route.query.filter_by(is_active=True).order_by(Route.name).all()
    return render_template('registration/index.html', routes=routes)

@bp.route('/map')
def map_view():
    """Kartenansicht aller Interessenten"""
    return render_template('registration/map.html')

@bp.route('/routes')
def routes_view():
    """Routenverwaltung"""
    return render_template('registration/routes.html')

@bp.route('/api/register', methods=['POST'])
def register():
    """API-Endpunkt für die Registrierung"""
    try:
        data = request.get_json()
        
        # Validierung der Pflichtfelder
        required_fields = ['name', 'phone', 'address']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} ist erforderlich'}), 400
        
        # Route-Auswahl verarbeiten
        route_id = None
        route_preference = None
        
        if data.get('route_selection'):
            if data['route_selection'] == 'unknown':
                route_preference = "Weiß ich noch nicht"
            else:
                try:
                    route_id = int(data['route_selection'])
                    # Prüfen ob Route existiert
                    route = Route.query.get(route_id)
                    if not route:
                        return jsonify({'error': 'Ungültige Route ausgewählt'}), 400
                except ValueError:
                    return jsonify({'error': 'Ungültige Route-ID'}), 400
        
        # Neuen Interessenten erstellen
        prospect = Prospect(
            name=data['name'],
            phone=data['phone'],
            email=data.get('email'),
            address=data['address'],
            notes=data.get('notes'),
            route_id=route_id,
            route_preference=route_preference
        )
        
        # Geocoding durchführen
        geocoding_service = GeocodingService()
        lat, lon, geocoded_address = geocoding_service.geocode_address(data['address'])
        
        if lat and lon:
            prospect.latitude = lat
            prospect.longitude = lon
            prospect.geocoded_address = geocoded_address
        
        db.session.add(prospect)
        db.session.commit()
        
        current_app.logger.info(f"[INDEX.html][REGISTRATION] Neue Registrierung: {prospect.name} - Route: {route_preference or (prospect.route.name if prospect.route else 'Keine')}")
        
        return jsonify({
            'message': 'Registrierung erfolgreich',
            'prospect_id': prospect.id,
            'geocoded': bool(lat and lon)
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"[INDEX.html][ERROR] Registrierung fehlgeschlagen: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Registrierung fehlgeschlagen'}), 500

@bp.route('/api/prospects', methods=['GET'])
def get_prospects():
    """API-Endpunkt für alle Interessenten (für Karte)"""
    try:
        prospects = Prospect.query.filter_by(status='active').all()
        
        # Nur Interessenten mit Koordinaten für die Karte
        map_data = []
        for prospect in prospects:
            if prospect.latitude and prospect.longitude:
                map_data.append({
                    'id': prospect.id,
                    'name': prospect.name,
                    'address': prospect.address,
                    'phone': prospect.phone,
                    'latitude': prospect.latitude,
                    'longitude': prospect.longitude,
                    'created_at': prospect.created_at.isoformat()
                })
        
        return jsonify(map_data), 200
        
    except Exception as e:
        current_app.logger.error(f"Fehler beim Abrufen der Interessenten: {str(e)}")
        return jsonify({'error': 'Daten konnten nicht geladen werden'}), 500

@bp.route('/api/prospects/<int:prospect_id>', methods=['GET'])
def get_prospect(prospect_id):
    """API-Endpunkt für einen spezifischen Interessenten"""
    try:
        prospect = Prospect.query.get_or_404(prospect_id)
        return jsonify(prospect.to_dict()), 200
        
    except Exception as e:
        current_app.logger.error(f"Fehler beim Abrufen des Interessenten: {str(e)}")
        return jsonify({'error': 'Interessent nicht gefunden'}), 404

@bp.route('/api/prospects/<int:prospect_id>/status', methods=['PUT'])
def update_prospect_status(prospect_id):
    """API-Endpunkt zum Aktualisieren des Status eines Interessenten"""
    try:
        prospect = Prospect.query.get_or_404(prospect_id)
        data = request.get_json()
        
        if 'status' in data:
            prospect.status = data['status']
        if 'notes' in data:
            prospect.notes = data['notes']
            
        db.session.commit()
        
        return jsonify({'message': 'Status aktualisiert'}), 200
        
    except Exception as e:
        current_app.logger.error(f"Fehler beim Aktualisieren des Status: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Status konnte nicht aktualisiert werden'}), 500

# Route API Endpunkte
@bp.route('/api/routes', methods=['GET'])
def get_routes():
    """API-Endpunkt für alle aktiven Routen"""
    try:
        routes = Route.query.filter_by(is_active=True).all()
        return jsonify([route.to_dict() for route in routes]), 200
        
    except Exception as e:
        current_app.logger.error(f"[MAP][ROUTES] Fehler beim Abrufen der Routen: {str(e)}")
        return jsonify({'error': 'Routen konnten nicht geladen werden'}), 500

@bp.route('/api/routes', methods=['POST'])
def create_route():
    """API-Endpunkt zum Erstellen einer neuen Route"""
    try:
        data = request.get_json()
        
        # Validierung
        if not data.get('name'):
            return jsonify({'error': 'Name ist erforderlich'}), 400
        if not data.get('waypoints') or len(data['waypoints']) < 2:
            return jsonify({'error': 'Mindestens 2 Wegpunkte erforderlich'}), 400
        
        route = Route(
            name=data['name'],
            description=data.get('description', ''),
            color=data.get('color', '#FF0000'),
            waypoints=data['waypoints']
        )
        
        db.session.add(route)
        db.session.commit()
        
        current_app.logger.info(f"[MAP][ROUTES] Neue Route erstellt: {route.name}")
        
        return jsonify({
            'message': 'Route erfolgreich erstellt',
            'route': route.to_dict()
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"[MAP][ROUTES] Fehler beim Erstellen der Route: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Route konnte nicht erstellt werden'}), 500

@bp.route('/api/routes/<int:route_id>', methods=['PUT'])
def update_route(route_id):
    """API-Endpunkt zum Aktualisieren einer Route"""
    try:
        route = Route.query.get_or_404(route_id)
        data = request.get_json()
        
        if 'name' in data:
            route.name = data['name']
        if 'description' in data:
            route.description = data['description']
        if 'color' in data:
            route.color = data['color']
        if 'waypoints' in data:
            route.waypoints = data['waypoints']
        if 'is_active' in data:
            route.is_active = data['is_active']
            
        db.session.commit()
        
        return jsonify({
            'message': 'Route aktualisiert',
            'route': route.to_dict()
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"[MAP][ROUTES] Fehler beim Aktualisieren der Route: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Route konnte nicht aktualisiert werden'}), 500

@bp.route('/api/routes/<int:route_id>', methods=['DELETE'])
def delete_route(route_id):
    """API-Endpunkt zum Löschen einer Route"""
    try:
        route = Route.query.get_or_404(route_id)
        route.is_active = False  # Soft delete
        db.session.commit()
        
        return jsonify({'message': 'Route gelöscht'}), 200
        
    except Exception as e:
        current_app.logger.error(f"[MAP][ROUTES] Fehler beim Löschen der Route: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Route konnte nicht gelöscht werden'}), 500