from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash
from .models import Station, Participant, db

bp = Blueprint("main", __name__)

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route("/api/stations", methods=["GET"])
def get_stations():
    stations = Station.query.order_by(Station.position).all()
    result = []
    for station in stations:
        participants = [{
            "id": p.id,
            "name": p.name,
            "monday": p.monday,
            "tuesday": p.tuesday,
            "wednesday": p.wednesday,
            "thursday": p.thursday,
            "friday": p.friday,
            "position": p.position
        } for p in station.participants]
        result.append({"id": station.id, "name": station.name, "position": station.position, "participants": participants})
    return jsonify(result)

@bp.route("/api/stations", methods=["POST"])
def save_stations():
    data = request.json
    if not data:
        return jsonify({"error": "Keine Daten erhalten"}), 400

    # Bestehende Stationen und Teilnehmer löschen
    Station.query.delete()
    db.session.commit()

    # Neue Stationen und Teilnehmer speichern
    for station_data in data:
        station = Station(name=station_data['name'], position=station_data['position'])
        db.session.add(station)
        db.session.flush()  # Station-ID abrufen

        for participant_data in station_data['participants']:
            participant = Participant(
                name=participant_data['name'],
                position=participant_data['position'],
                station_id=station.id,
                monday=participant_data.get('monday', False),
                tuesday=participant_data.get('tuesday', False),
                wednesday=participant_data.get('wednesday', False),
                thursday=participant_data.get('thursday', False),
                friday=participant_data.get('friday', False)
            )
            db.session.add(participant)

    db.session.commit()
    return jsonify({"success": True}), 200

@bp.route("/api/participation/<int:participant_id>", methods=["PATCH"])
def update_participation(participant_id):
    participant = Participant.query.get(participant_id)
    if not participant:
        return jsonify({"error": "Teilnehmer nicht gefunden"}), 404
    participant.status_today = not participant.status_today
    db.session.commit()
    return jsonify({"id": participant.id, "status_today": participant.status_today})

@bp.route("/admin")
def admin():
    return render_template("admin.html")

@bp.route("/admin/stations", methods=["POST"])
def create_station():
    data = request.json
    new_station = Station(name=data['name'], position=data['position'])
    db.session.add(new_station)
    db.session.commit()
    return jsonify({"id": new_station.id, "name": new_station.name, "position": new_station.position})

@bp.route('/admin/stations/<int:station_id>/edit', methods=['POST'])
def edit_station(station_id):
    station = Station.query.get_or_404(station_id)
    data = request.json
    if 'name' in data:
        station.name = data['name']
    if 'position' in data:
        station.position = data['position']
    db.session.commit()
    return jsonify({"success": True})

@bp.route('/admin/stations/<int:station_id>/delete', methods=['POST'])
def delete_station(station_id):
    station = Station.query.get_or_404(station_id)
    db.session.delete(station)
    db.session.commit()
    return jsonify({"success": True})

@bp.route("/admin/participants", methods=["POST"])
def create_participant():
    data = request.json
    new_participant = Participant(
        name=data['name'],
        station_id=data.get('station_id'),
        position=data['position'],
        monday=data.get('monday', False),
        tuesday=data.get('tuesday', False),
        wednesday=data.get('wednesday', False),
        thursday=data.get('thursday', False),
        friday=data.get('friday', False)
    )
    db.session.add(new_participant)
    db.session.commit()
    return jsonify({"id": new_participant.id, "name": new_participant.name, "position": new_participant.position})

@bp.route('/admin/participants/<int:participant_id>/edit', methods=['POST'])
def edit_participant(participant_id):
    participant = Participant.query.get_or_404(participant_id)
    data = request.json
    if 'name' in data:
        participant.name = data['name']
    if 'station_id' in data:
        participant.station_id = data['station_id']
    if 'position' in data:
        participant.position = data['position']
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
    for day in days:
        if day in data:
            setattr(participant, day, data[day])
    db.session.commit()
    return jsonify({"success": True})

@bp.route('/admin/participants/<int:participant_id>/delete', methods=['POST'])
def delete_participant(participant_id):
    participant = Participant.query.get_or_404(participant_id)
    db.session.delete(participant)
    db.session.commit()
    return jsonify({"success": True})
