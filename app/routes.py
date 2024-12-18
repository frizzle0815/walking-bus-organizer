from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash
from .models import Station, Participant, db

bp = Blueprint("main", __name__)

@bp.route('/')
def index():
    return render_template('index.html')

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

@bp.route("/admin")
def admin():
    stations = Station.query.all()
    participants = Participant.query.all()
    return render_template("admin.html", stations=stations, participants=participants)

@bp.route("/admin/stations", methods=["POST"])
def create_station():
    data = request.json
    new_station = Station(name=data['name'])
    db.session.add(new_station)
    db.session.commit()
    return jsonify({"id": new_station.id, "name": new_station.name})

@bp.route('/admin/stations/<int:station_id>/edit', methods=['POST'])
def edit_station(station_id):
    station = Station.query.get_or_404(station_id)
    new_name = request.form.get('name')
    if new_name:
        station.name = new_name
        db.session.commit()
        flash(f"Haltestelle '{station.name}' wurde aktualisiert.")
    return redirect(url_for('main.admin'))

@bp.route('/admin/stations/<int:station_id>/delete', methods=['POST'])
def delete_station(station_id):
    station = Station.query.get_or_404(station_id)
    if station.participants:
        flash("Haltestelle kann nicht gelöscht werden, da noch Teilnehmer zugeordnet sind.")
    else:
        db.session.delete(station)
        db.session.commit()
        flash(f"Haltestelle '{station.name}' wurde gelöscht.")
    return redirect(url_for('main.admin'))

@bp.route("/admin/participants", methods=["POST"])
def create_participant():
    data = request.json
    new_participant = Participant(
        name=data['name'],
        station_id=data.get('station_id'),
        monday=False,
        tuesday=False,
        wednesday=False,
        thursday=False,
        friday=False
    )
    db.session.add(new_participant)
    db.session.commit()
    return jsonify({"id": new_participant.id, "name": new_participant.name})

@bp.route('/admin/participants/<int:participant_id>/edit', methods=['POST'])
def edit_participant(participant_id):
    participant = Participant.query.get_or_404(participant_id)
    new_name = request.form.get('name')
    new_station_id = request.form.get('station_id')
    days = {
        'monday': request.form.get('monday') == 'on',
        'tuesday': request.form.get('tuesday') == 'on',
        'wednesday': request.form.get('wednesday') == 'on',
        'thursday': request.form.get('thursday') == 'on',
        'friday': request.form.get('friday') == 'on',
    }
    if new_name:
        participant.name = new_name
    if new_station_id:
        participant.station_id = new_station_id
    for day, value in days.items():
        setattr(participant, day, value)
    db.session.commit()
    flash(f"Teilnehmer '{participant.name}' wurde aktualisiert.")
    return redirect(url_for('main.admin'))

@bp.route('/admin/participants/<int:participant_id>/delete', methods=['POST'])
def delete_participant(participant_id):
    participant = Participant.query.get_or_404(participant_id)
    db.session.delete(participant)
    db.session.commit()
    flash(f"Teilnehmer '{participant.name}' wurde gelöscht.")
    return redirect(url_for('main.admin'))
