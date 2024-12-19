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
    try:
        data = request.get_json()
        if not isinstance(data, list):
            return jsonify({"error": "Datenformat ungültig. Erwartet wird eine Liste."}), 400

        # Update positions for all stations
        for station_data in data:
            station = Station.query.get(station_data['id'])
            if station:
                station.position = station_data['position']
        
        db.session.commit()
        return jsonify({"success": True}), 200

    except Exception as e:
        return jsonify({"error": f"Ein Fehler ist aufgetreten: {str(e)}"}), 500
@bp.route("/api/stations/<int:station_id>/participants/<int:participant_id>", methods=["PUT"])
def update_participant_api(station_id, participant_id):
    try:
        participant = Participant.query.get_or_404(participant_id)
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        if 'station_id' in data:
            participant.station_id = int(data['station_id'])  # Ensure it's an integer
        if 'position' in data:
            participant.position = int(data['position'])  # Ensure it's an integer

        if 'name' in data:
            participant.name = data['name']
        if 'monday' in data:
            participant.monday = data['monday']
        if 'tuesday' in data:
            participant.tuesday = data['tuesday']
        if 'wednesday' in data:
            participant.wednesday = data['wednesday']
        if 'thursday' in data:
            participant.thursday = data['thursday']
        if 'friday' in data:
            participant.friday = data['friday']

        db.session.commit()
        return jsonify({"success": True, "participant_id": participant.id}), 200

    except Exception as e:
        db.session.rollback()  # Important: Rollback on error
        return jsonify({"error": str(e)}), 500@bp.route("/api/stations/<int:station_id>", methods=["PUT"])
def update_station(station_id):
    station = Station.query.get_or_404(station_id)
    data = request.json
    if 'name' in data:
        station.name = data['name']
    db.session.commit()
    return jsonify({"id": station.id, "name": station.name})

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
