from flask import Blueprint, render_template, jsonify, request
from datetime import datetime
from .models import Station, Participant, CalendarStatus, db
bp = Blueprint("main", __name__)

@bp.route('/')
def index():
    return render_template('index.html')

@bp.route("/admin")
def admin():
    return render_template("admin.html")

# Station Routes
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
            "status_today": p.status_today,
            "position": p.position
        } for p in station.participants]
        result.append({
            "id": station.id, 
            "name": station.name, 
            "position": station.position, 
            "participants": participants
        })
    return jsonify(result)
@bp.route("/api/stations", methods=["POST"])
def update_stations_order():
    try:
        data = request.get_json()
        print("Received data for station order update:", data)  # Debug log
        
        if not isinstance(data, list):
            error_msg = "Invalid data format. Expected a list."
            print("Error:", error_msg)  # Debug log
            return jsonify({"error": error_msg}), 400

        # Update positions for all stations
        for station_data in data:
            print(f"Processing station: {station_data}")  # Debug log
            station = Station.query.get(station_data['id'])
            if station:
                station.position = station_data['position']
            else:
                print(f"Station not found: {station_data['id']}")  # Debug log
        
        db.session.commit()
        print("Station order update successful")  # Debug log
        return jsonify({"success": True}), 200

    except Exception as e:
        error_msg = f"An error occurred: {str(e)}"
        print("Error:", error_msg)  # Debug log
        return jsonify({"error": error_msg}), 500
        
@bp.route("/api/stations/<int:station_id>", methods=["PUT"])
def update_station(station_id):
    station = Station.query.get_or_404(station_id)
    data = request.get_json()
    if 'name' in data:
        station.name = data['name']
    db.session.commit()
    return jsonify({"success": True})

@bp.route("/admin/stations", methods=["POST"])
def create_station():
    data = request.get_json()
    new_station = Station(name=data['name'], position=data['position'])
    db.session.add(new_station)
    db.session.commit()
    return jsonify({
        "id": new_station.id,
        "name": new_station.name,
        "position": new_station.position,
        "participants": []
    })

@bp.route("/admin/stations/<int:station_id>/delete", methods=["POST"])
def delete_station(station_id):
    station = Station.query.get_or_404(station_id)
    db.session.delete(station)
    db.session.commit()
    return jsonify({"success": True})

# Participant Routes
@bp.route("/admin/participants", methods=["POST"])
def create_participant():
    data = request.get_json()
    new_participant = Participant(
        name=data['name'],
        station_id=data['station_id'],
        position=data['position'],
        monday=data.get('monday', True),
        tuesday=data.get('tuesday', True),
        wednesday=data.get('wednesday', True),
        thursday=data.get('thursday', True),
        friday=data.get('friday', True)
    )
    db.session.add(new_participant)
    db.session.commit()
    return jsonify({
        "id": new_participant.id,
        "name": new_participant.name,
        "position": new_participant.position,
        "monday": new_participant.monday,
        "tuesday": new_participant.tuesday,
        "wednesday": new_participant.wednesday,
        "thursday": new_participant.thursday,
        "friday": new_participant.friday
    })

@bp.route("/api/stations/<int:station_id>/participants/<int:participant_id>", methods=["PUT"])
def update_participant(station_id, participant_id):
    participant = Participant.query.get_or_404(participant_id)
    data = request.get_json()
    
    for field in ['name', 'station_id', 'position', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday']:
        if field in data:
            setattr(participant, field, data[field])
    
    db.session.commit()
    return jsonify({"success": True})

@bp.route("/admin/participants/<int:participant_id>/delete", methods=["POST"])
def delete_participant(participant_id):
    participant = Participant.query.get_or_404(participant_id)
    db.session.delete(participant)
    db.session.commit()
    return jsonify({"success": True})

@bp.route("/api/initialize-daily-status", methods=["POST"])
def initialize_daily_status():
    weekday = datetime.now().weekday()
    
    day_mapping = {
        0: 'monday',
        1: 'tuesday',
        2: 'wednesday',
        3: 'thursday',
        4: 'friday'
    }
    
    if weekday in day_mapping:
        current_day = day_mapping[weekday]
        participants = Participant.query.all()
        
        for participant in participants:
            # Get the scheduled participation for current day
            should_participate = getattr(participant, current_day)
            
            # Only update if not already initialized today
            if (participant.status_initialized_date is None or 
                participant.status_initialized_date.date() != datetime.now().date()):
                participant.status_today = should_participate
                participant.status_initialized_date = datetime.now()
        
        db.session.commit()
        return jsonify({
            "success": True,
            "day": current_day
        })
    
    return jsonify({"success": False, "message": "Not a school day"})


@bp.route("/api/participation/<int:participant_id>", methods=["PATCH"])
def toggle_participation(participant_id):
    participant = Participant.query.get_or_404(participant_id)
    participant.status_today = not participant.status_today
    db.session.commit()
    
    return jsonify({
        "status_today": participant.status_today,
        "participant_id": participant.id
    })

@bp.route("/api/calendar-status", methods=["POST"])
def update_calendar_status():
    data = request.get_json()
    participant_id = data['participant_id']
    date = data['date']
    status = data['status']
    
    # Update or create calendar entry in database
    calendar_entry = CalendarStatus.query.filter_by(
        participant_id=participant_id,
        date=date
    ).first()
    
    if calendar_entry:
        calendar_entry.status = status
    else:
        calendar_entry = CalendarStatus(
            participant_id=participant_id,
            date=date,
            status=status
        )
        db.session.add(calendar_entry)
    
    db.session.commit()
    return jsonify({"success": True})

@bp.route("/api/calendar-status/<int:participant_id>", methods=["GET"])
def get_calendar_status(participant_id):
    entries = CalendarStatus.query.filter_by(participant_id=participant_id).all()
    return jsonify([{
        'date': entry.date.isoformat(),
        'status': entry.status
    } for entry in entries])
