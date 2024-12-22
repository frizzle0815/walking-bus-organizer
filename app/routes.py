from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify, request
from .models import Station, Participant, CalendarStatus, db, WalkingBusSchedule
from . import get_current_time, get_current_date, TIMEZONE, WEEKDAY_MAPPING

# Create Blueprint
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
    today = get_current_date()
    stations = Station.query.order_by(Station.position).all()
    result = []
    
    for station in stations:
        participants = []
        for p in station.participants:
            # Get today's calendar status
            calendar_entry = CalendarStatus.query.filter_by(
                participant_id=p.id,
                date=today
            ).first()
            
            today_status = calendar_entry.status if calendar_entry else getattr(p, WEEKDAY_MAPPING[today.weekday()], True)
            
            participants.append({
                "id": p.id,
                "name": p.name,
                "monday": p.monday,
                "tuesday": p.tuesday,
                "wednesday": p.wednesday,
                "thursday": p.thursday,
                "friday": p.friday,
                "saturday": p.saturday,
                "sunday": p.sunday,
                "today_status": today_status,
                "position": p.position
            })
            
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
    today = get_current_date()
    weekday = WEEKDAY_MAPPING[today.weekday()]
    
    # Create new participant
    new_participant = Participant(
        name=data['name'],
        station_id=data['station_id'],
        position=data['position']
    )
    db.session.add(new_participant)
    db.session.flush()  # Get ID for the new participant
    
    # Create calendar entry for today based on weekday default
    calendar_entry = CalendarStatus(
        participant_id=new_participant.id,
        date=today,
        status=getattr(new_participant, weekday, True),
        is_manual_override=False
    )
    db.session.add(calendar_entry)
    
    # Set status_today to match calendar entry
    new_participant.status_today = calendar_entry.status
    
    db.session.commit()
    
    return jsonify({
        "id": new_participant.id,
        "name": new_participant.name,
        "position": new_participant.position,
        "monday": new_participant.monday,
        "tuesday": new_participant.tuesday,
        "wednesday": new_participant.wednesday,
        "thursday": new_participant.thursday,
        "friday": new_participant.friday,
        "saturday": new_participant.saturday,
        "sunday": new_participant.sunday,
        "status_today": new_participant.status_today
    })


@bp.route("/api/stations/<int:station_id>/participants/<int:participant_id>", methods=["PUT"])
def update_participant(station_id, participant_id):
    participant = Participant.query.get_or_404(participant_id)
    data = request.get_json()
    
    # Update to include all days
    for field in ['name', 'station_id', 'position', 'monday', 'tuesday', 'wednesday', 
                 'thursday', 'friday', 'saturday', 'sunday']:  # Added weekend days
        if field in data:
            setattr(participant, field, data[field])
    
    db.session.commit()
    return jsonify({"success": True})

@bp.route("/admin/participants/<int:participant_id>/delete", methods=["POST"])
def delete_participant(participant_id):
    try:
        # First delete all calendar entries for this participant
        CalendarStatus.query.filter_by(participant_id=participant_id).delete()
        
        # Then delete the participant
        participant = Participant.query.get_or_404(participant_id)
        db.session.delete(participant)
        db.session.commit()
        
        return jsonify({"success": True})
        
    except Exception as e:
        db.session.rollback()  # Rollback on error
        print(f"Error deleting participant {participant_id}: {str(e)}")  # Log the error
        return jsonify({"error": str(e)}), 500


def is_walking_bus_day(date):
    schedule = WalkingBusSchedule.query.first()
    if not schedule:
        return False
  
    weekday = date.weekday()
    # Use centralized WEEKDAY_MAPPING instead of local definition
    return getattr(schedule, WEEKDAY_MAPPING[weekday], False)

@bp.route("/api/initialize-daily-status", methods=["POST"])
def initialize_daily_status():
    try:
        today = get_current_date()
        walking_bus_day = is_walking_bus_day(today)
        return jsonify({
            "success": True,
            "currentDate": today.isoformat(),
            "isWalkingBusDay": walking_bus_day
        })
    except Exception as e:
        print(f"Error in initialize_daily_status: {str(e)}")  # Debug log
        return jsonify({"error": str(e)}), 500

@bp.route("/api/walking-bus-schedule", methods=["GET"])
def get_schedule():
    schedule = WalkingBusSchedule.query.first()
    if not schedule:
        schedule = WalkingBusSchedule()
        db.session.add(schedule)
        db.session.commit()
    return jsonify({
        "monday": schedule.monday,
        "tuesday": schedule.tuesday,
        "wednesday": schedule.wednesday,
        "thursday": schedule.thursday,
        "friday": schedule.friday,
        "saturday": schedule.saturday,
        "sunday": schedule.sunday
    })

@bp.route("/api/walking-bus-schedule", methods=["POST"])
def update_schedule():
    data = request.get_json()
    schedule = WalkingBusSchedule.query.first()
    if not schedule:
        schedule = WalkingBusSchedule()
        db.session.add(schedule)
    
    # Update schedule days
    for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
        new_status = data.get(day, False)
        setattr(schedule, day, new_status)
    
    db.session.commit()
    return jsonify({"success": True})

@bp.route("/api/participation/<int:participant_id>", methods=["PATCH"])
def toggle_participation(participant_id):
    participant = Participant.query.get_or_404(participant_id)
    participant.status_today = not participant.status_today
    
    # Add today's date to CalendarStatus
    today = get_current_date()
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
    # Parse incoming dates with timezone awareness
    date = TIMEZONE.localize(datetime.strptime(data['date'], '%Y-%m-%d')).date()
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
    if date == get_current_date():
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
    today = get_current_date()
    
    # Map day names to weekday numbers (0 = Monday, 6 = Sunday)
    day_mapping = {
        'monday': 0,
        'tuesday': 1,
        'wednesday': 2,
        'thursday': 3,
        'friday': 4,
        'saturday': 5,
        'sunday': 6
    }
    
    target_weekday = day_mapping[day]
    
    # Get all future dates for this weekday for the next 3 months
    future_dates = []
    current_date = today
    for _ in range(90):  # Check next 90 days
        if current_date.weekday() == target_weekday:  # Direct comparison since we're using 0-6 system
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

@bp.route("/api/calendar-data/<int:participant_id>", methods=["GET"])
def get_calendar_data(participant_id):
    try:
        participant = Participant.query.get_or_404(participant_id)
        schedule = WalkingBusSchedule.query.first()
        today = get_current_date()
        
        # Calculate start of current week (Monday)
        week_start = today - timedelta(days=today.weekday())
        # Get dates for current and next week
        dates_to_check = [week_start + timedelta(days=x) for x in range(14)]
        
        # Get existing calendar entries
        calendar_entries = CalendarStatus.query.filter(
            CalendarStatus.participant_id == participant_id,
            CalendarStatus.date.in_(dates_to_check)
        ).all()
        
        # Create calendar data
        calendar_data = []
        for date in dates_to_check:
            weekday = WEEKDAY_MAPPING[date.weekday()]
            is_schedule_day = getattr(schedule, weekday, False)
            default_status = getattr(participant, weekday, False)
            
            # Find any override for this date
            calendar_entry = next(
                (entry for entry in calendar_entries if entry.date == date),
                None
            )
            
            calendar_data.append({
                'date': date.isoformat(),
                'weekday': weekday,
                'is_schedule_day': is_schedule_day,
                'is_past': date < today,
                'status': calendar_entry.status if calendar_entry else default_status,
                'is_today': date == today
            })
        
        return jsonify(calendar_data)
        
    except Exception as e:
        print(f"Error in get_calendar_data: {str(e)}")
        return jsonify({'error': str(e)}), 500
