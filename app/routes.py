from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify, request
from .models import Station, Participant, CalendarStatus, db

# Create Blueprint on a new line
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
    today = datetime.now().date()  # Extract only the date part
    return jsonify({
        "success": True,
        "currentDate": today.isoformat()  # Return date in 'YYYY-MM-DD' format
    })


@bp.route("/api/participation/<int:participant_id>", methods=["PATCH"])
def toggle_participation(participant_id):
    participant = Participant.query.get_or_404(participant_id)
    participant.status_today = not participant.status_today
    
    # Add today's date to CalendarStatus
    today = datetime.now().date()
    calendar_entry = CalendarStatus.query.filter_by(
        participant_id=participant_id,
        date=today
    ).first()
    
    if calendar_entry:
        calendar_entry.status = participant.status_today
        calendar_entry.is_manual_override = True
    else:
        calendar_entry = CalendarStatus(
            participant_id=participant_id,
            date=today,
            status=participant.status_today,
            is_manual_override=True
        )
        db.session.add(calendar_entry)
    
    db.session.commit()
    
    return jsonify({
        "status_today": participant.status_today,
        "participant_id": participant.id
    })
@bp.route("/api/calendar-status", methods=["POST"])
def update_calendar_status():
    data = request.get_json()
    participant_id = data['participant_id']
    date = datetime.strptime(data['date'], '%Y-%m-%d').date()  # Ensure date is parsed correctly
    status = data['status']

    calendar_entry = CalendarStatus.query.filter_by(
        participant_id=participant_id,
        date=date
    ).first()

    if calendar_entry:
        calendar_entry.status = status
        calendar_entry.is_manual_override = True
    else:
        calendar_entry = CalendarStatus(
            participant_id=participant_id,
            date=date,
            status=status,
            is_manual_override=True
        )
        db.session.add(calendar_entry)

    # Update status_today if this is for today
    if date == datetime.now().date():
        participant = Participant.query.get(participant_id)
        participant.status_today = status

    db.session.commit()
    return jsonify({"success": True})

@bp.route("/api/calendar-status/<int:participant_id>", methods=["GET"])
def get_calendar_status(participant_id):
    entries = CalendarStatus.query.filter_by(participant_id=participant_id).all()
    return jsonify([{
        'date': entry.date.isoformat(),
        'status': entry.status
    } for entry in entries])

@bp.route("/api/update-future-entries", methods=["POST"])
def update_future_entries():
    data = request.get_json()
    participant_id = data['participant_id']
    day = data['day']
    status = data['status']
    
    # Get today's date
    today = datetime.now().date()
    
    # Map day names to weekday numbers (0 = Monday, 6 = Sunday)
    day_mapping = {
        'monday': 1,
        'tuesday': 2,
        'wednesday': 3,
        'thursday': 4,
        'friday': 5
    }
    
    target_weekday = day_mapping[day]
    
    # Get all future dates for this weekday for the next 3 months
    future_dates = []
    current_date = today
    for _ in range(90):  # Check next 90 days
        if current_date.weekday() == (target_weekday - 1):  # Subtract 1 to align with Python's Monday = 0 system
            future_dates.append(current_date)
        current_date += timedelta(days=1)
    
    # Update or create calendar entries for these dates
    for date in future_dates:
        # Only update if there's no manual override
        calendar_entry = CalendarStatus.query.filter_by(
            participant_id=participant_id,
            date=date
        ).first()
        
        if not calendar_entry or not calendar_entry.is_manual_override:
            if calendar_entry:
                calendar_entry.status = status
            else:
                new_entry = CalendarStatus(
                    participant_id=participant_id,
                    date=date,
                    status=status,
                    is_manual_override=False
                )
                db.session.add(new_entry)
    
    db.session.commit()
    return jsonify({"success": True})

@bp.route("/api/stations/<int:station_id>/stats")
def get_station_stats(station_id):
    station = Station.query.get_or_404(station_id)
    total = len(station.participants)
    active = sum(1 for p in station.participants if p.status_today)
    return jsonify({
        "total": total,
        "active": active
    })

@bp.route("/api/participant/<int:participant_id>/weekday-status/<string:weekday>")
def get_participant_weekday_status(participant_id, weekday):
    print(f"Checking weekday status: participant={participant_id}, weekday={weekday}")
    participant = Participant.query.get_or_404(participant_id)
    status = getattr(participant, weekday, True)
    print(f"Status for {weekday}: {status}")
    return jsonify({"status": status})
