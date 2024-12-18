from flask import Blueprint, jsonify, request
from .models import Station, Participant, db

bp = Blueprint("main", __name__)

@bp.route('/')
def index():
    # Render the index.html template when the root URL is accessed
    return render_template('index.html')

# API: Zentrale Ansicht
@bp.route("/api/stations", methods=["GET"])
def get_stations():
    stations = Station.query.all()
    result = []
    for station in stations:
        participants = [{
            "id": p.id,
            "name": p.name,
            "status_today": p.status_today
        } for p in station.participants]
        result.append({"id": station.id, "name": station.name, "participants": participants})
    return jsonify(result)

@bp.route("/api/participation/<int:participant_id>", methods=["PATCH"])
def update_participation(participant_id):
    participant = Participant.query.get(participant_id)
    if not participant:
        return jsonify({"error": "Participant not found"}), 404
    participant.status_today = not participant.status_today
    db.session.commit()
    return jsonify({"id": participant.id, "status_today": participant.status_today})

# Admin: Haltestelle erstellen
@bp.route("/admin/stations", methods=["POST"])
def create_station():
    data = request.json
    new_station = Station(name=data['name'])
    db.session.add(new_station)
    db.session.commit()
    return jsonify({"id": new_station.id, "name": new_station.name})

# Admin: Teilnehmer erstellen
@bp.route("/admin/participants", methods=["POST"])
def create_participant():
    data = request.json
    new_participant = Participant(
        name=data['name'],
        station_id=data.get('station_id'),
        monday=data.get('monday', False),
        tuesday=data.get('tuesday', False),
        wednesday=data.get('wednesday', False),
        thursday=data.get('thursday', False),
        friday=data.get('friday', False)
    )
    db.session.add(new_participant)
    db.session.commit()
    return jsonify({"id": new_participant.id, "name": new_participant.name})
