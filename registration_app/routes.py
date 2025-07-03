from flask import Blueprint, render_template, request, jsonify, current_app
import logging
import sys
import os

# Hauptverzeichnis zum Python-Pfad hinzufügen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import db, Prospect
from .services.geocoding_service import GeocodingService

bp = Blueprint('registration', __name__)

@bp.route('/')
def index():
    """Hauptseite mit Registrierungsformular"""
    return render_template('registration/index.html')

@bp.route('/map')
def map_view():
    """Kartenansicht aller Interessenten"""
    return render_template('registration/map.html')

@bp.route('/api/register', methods=['POST'])
def register_prospect():
    """API-Endpunkt für Registrierung eines Interessenten"""
    try:
        data = request.get_json()
        
        # Validierung
        required_fields = ['name', 'address', 'phone']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} ist erforderlich'}), 400
        
        # Neuen Interessenten erstellen
        prospect = Prospect(
            name=data['name'],
            address=data['address'],
            phone=data['phone'],
            email=data.get('email', ''),
            notes=data.get('notes', '')
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
        
        current_app.logger.info(f"Neuer Interessent registriert: {prospect.name} ({prospect.address})")
        
        return jsonify({
            'message': 'Registrierung erfolgreich',
            'prospect_id': prospect.id,
            'geocoded': bool(lat and lon)
        }), 201
        
    except Exception as e:
        current_app.logger.error(f"Fehler bei Registrierung: {str(e)}")
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
