from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify, request, Response, stream_with_context
from flask import send_from_directory
from flask import current_app as app
from .models import db, Station, Participant, CalendarStatus, WalkingBusSchedule, SchoolHoliday, WalkingBusOverride, DailyNote
from .services.holiday_service import HolidayService
from . import get_current_time, get_current_date, TIMEZONE, WEEKDAY_MAPPING
import json
import time

# Create Blueprint
bp = Blueprint("main", __name__)

# Frontend Routes
@bp.route('/')
def index():
    return render_template('index.html')


@bp.route("/admin")
def admin():
    return render_template("admin.html")


@bp.route("/calendar")
def calendar_view():
    return render_template("calendar.html")


# Station Routes
@bp.route("/api/stations", methods=["GET"])
def get_stations():
    today = get_current_date()
    stations = Station.query.order_by(Station.position).all()
    result = []
    
    for station in stations:
        # Order participants by position
        ordered_participants = sorted(station.participants, key=lambda p: p.position)
        participants = []
        
        for p in ordered_participants:
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
def create_station():
    data = request.get_json()
    
    # First update positions of existing stations to make room
    existing_stations = Station.query.filter(Station.position >= 0).order_by(Station.position).all()
    for station in existing_stations:
        station.position += 1
    
    # Create new station at position 0
    new_station = Station(name=data['name'], position=0)
    db.session.add(new_station)
    db.session.commit()
    
    app.logger.info(f"Neue Haltestelle erstellt: {new_station.name} (ID: {new_station.id})")
    return jsonify({
        "id": new_station.id,
        "name": new_station.name,
        "position": new_station.position,
        "participants": []
    })



@bp.route("/api/stations/<int:station_id>", methods=["PUT"])
def update_station(station_id):
    station = Station.query.get_or_404(station_id)
    data = request.get_json()
    old_name = station.name
    if 'name' in data:
        station.name = data['name']
    db.session.commit()
    app.logger.info(f"Haltestelle geändert von '{old_name}' zu '{station.name}' (ID: {station_id})")
    return jsonify({"success": True})


@bp.route("/api/stations/<int:station_id>", methods=["DELETE"])
def delete_station(station_id):
    station = Station.query.get_or_404(station_id)
    db.session.delete(station)
    db.session.commit()
    return jsonify({"success": True})


@bp.route("/api/stations/<int:station_id>/stats")
def get_station_stats(station_id):
    try:
        station = Station.query.get_or_404(station_id)
        total = len(station.participants)
        today = get_current_date()
        
        # Use a different variable name to avoid conflict with function name
        is_active_day = check_walking_bus_day(today)
        
        active = sum(1 for p in station.participants if p.status_today) if is_active_day else 0
        
        return jsonify({
            "total": total,
            "active": active
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/stations/stats/total")
def get_stations_total_stats():
    try:
        # Get all stations
        stations = Station.query.all()
        # Sum up all participants across stations
        total = sum(len(station.participants) for station in stations)
        
        today = get_current_date()
        is_active_day = check_walking_bus_day(today)
        
        # Sum up active participants across all stations
        active = sum(sum(1 for p in station.participants if p.status_today) 
                    for station in stations) if is_active_day else 0
        
        return jsonify({
            "total": total,
            "active": active
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/stations/order", methods=["PUT"])
def update_stations_order():
    try:
        data = request.get_json()
        if not isinstance(data, list):
            return jsonify({"error": "Invalid data format. Expected a list."}), 400

        # Validate all station IDs exist before updating
        station_ids = [station_data['id'] for station_data in data]
        stations = Station.query.filter(Station.id.in_(station_ids)).all()
        
        # Create a mapping of id to station for efficient updates
        station_map = {station.id: station for station in stations}
        
        # Update positions
        for station_data in data:
            station_id = station_data['id']
            if station_id in station_map:
                station_map[station_id].position = station_data['position']
        
        db.session.commit()
        return jsonify({"success": True}), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error updating station order: {str(e)}")
        return jsonify({"error": str(e)}), 500


# Participant Routes
@bp.route("/api/participants", methods=["POST"])
def create_participant():
    data = request.get_json()
    today = get_current_date()
    weekday = WEEKDAY_MAPPING[today.weekday()]
    
    new_participant = Participant(
        name=data['name'],
        station_id=data['station_id'],
        position=data['position']
    )
    db.session.add(new_participant)
    db.session.flush()
    app.logger.info(f"Neuer Teilnehmer erstellt: {new_participant.name} (ID: {new_participant.id})")
    
    calendar_entry = CalendarStatus(
        participant_id=new_participant.id,
        date=today,
        status=getattr(new_participant, weekday, True),
        is_manual_override=False
    )
    db.session.add(calendar_entry)
    
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
    old_name = participant.name
    
    # Handle position updates
    if 'position' in data:
        # Get all participants in the same station
        station_participants = Participant.query.filter_by(station_id=station_id).all()
        # Update positions to ensure uniqueness
        for p in station_participants:
            if p.id != participant_id and p.position >= data['position']:
                p.position += 1
    
    # Update participant fields
    for field in ['name', 'station_id', 'position', 'monday', 'tuesday', 'wednesday', 
                 'thursday', 'friday', 'saturday', 'sunday']:
        if field in data:
            setattr(participant, field, data[field])
    
    db.session.commit()
    app.logger.info(f"Teilnehmer aktualisiert von '{old_name}' zu '{participant.name}', '{participant.station_id}', '{participant.position}' (ID: {participant_id})")
    return jsonify({"success": True})



@bp.route("/api/participants/<int:participant_id>", methods=["DELETE"])
def delete_participant(participant_id):
    try:
        CalendarStatus.query.filter_by(participant_id=participant_id).delete()
        participant = Participant.query.get_or_404(participant_id)
        name = participant.name  # Store name before deletion
        app.logger.info(f"Lösche Teilnehmer {name} (ID: {participant_id})")
        db.session.delete(participant)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/api/participation/<int:participant_id>", methods=["PATCH"])
def toggle_participation(participant_id):
    participant = Participant.query.get_or_404(participant_id)
    participant.status_today = not participant.status_today

    # Add logging
    app.logger.info(f"Teilnehmer {participant.name} (ID: {participant_id}) Status Heute geändert zu {participant.status_today}")
    
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


@bp.route("/api/participant/<int:participant_id>/weekday-status/<string:weekday>")
def get_participant_weekday_status(participant_id, weekday):
    participant = Participant.query.get_or_404(participant_id)
    status = getattr(participant, weekday, True)
    return jsonify({"status": status})


# Schedule and Calendar Routes
@bp.route("/api/initialize-daily-status", methods=["POST"])
def initialize_daily_status():
    try:
        today = get_current_date()
        app.logger.info(f"Initializing daily status for {today}")

        # Update holiday cache first
        holiday_service = HolidayService()
        holiday_service.update_holiday_cache()

        # Delete all calendar entries from past dates
        deleted_count = CalendarStatus.query.filter(CalendarStatus.date < today).delete()
        app.logger.info(f"Deleted {deleted_count} past calendar entries")
        db.session.commit()

        # Get the daily note for today
        daily_note = DailyNote.query.filter_by(date=today).first()

        app.logger.info("Checking walking bus day status")
        walking_bus_day, reason, reason_type = check_walking_bus_day(today, include_reason=True)
        app.logger.info(f"Walking bus day status: {walking_bus_day}")

        response = {
            "success": True,
            "currentDate": today.isoformat(),
            "isWalkingBusDay": walking_bus_day,
            "reason": reason,
            "reason_type": reason_type,
            "note": daily_note.note if daily_note else None
        }
        app.logger.info(f"Returning response: {response}")
        return jsonify(response)
    except Exception as e:
        app.logger.error(f"Error in initialize_daily_status: {str(e)}")
        db.session.rollback()
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


@bp.route("/api/walking-bus-schedule", methods=["PUT"])
def update_schedule():
    data = request.get_json()
    schedule = WalkingBusSchedule.query.first()
    if not schedule:
        schedule = WalkingBusSchedule()
        db.session.add(schedule)
    
    for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
        setattr(schedule, day, data.get(day, False))
    
    db.session.commit()
    return jsonify({"success": True})


@bp.route("/api/calendar-status", methods=["POST"])
def update_calendar_status():
    data = request.get_json()
    participant_id = data['participant_id']
    
    # Get participant information early
    participant = Participant.query.get_or_404(participant_id)
    
    # Correct way to handle timezone with zoneinfo
    naive_date = datetime.strptime(data['date'], '%Y-%m-%d')
    aware_date = datetime.combine(naive_date.date(), datetime.min.time(), tzinfo=TIMEZONE)
    date = aware_date.date()
    
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

    if date == get_current_date():
        participant.status_today = status

    db.session.commit()
    app.logger.info(f"Kalenderstatus für {participant.name} (ID: {participant_id}) am {date} auf {status} gesetzt")
    return jsonify({"success": True})



@bp.route("/api/calendar-status/<int:participant_id>", methods=["GET"])
def get_calendar_status(participant_id):
    entries = CalendarStatus.query.filter_by(participant_id=participant_id).all()
    return jsonify([{
        'date': entry.date.isoformat(),
        'status': entry.status
    } for entry in entries])


@bp.route("/api/calendar-data/<int:participant_id>", methods=["GET"])
def get_calendar_data(participant_id):
    try:
        app.logger.info(f"Fetching calendar data for participant {participant_id}")
        participant = Participant.query.get_or_404(participant_id)
        today = get_current_date()
        
        # Calculate dates for next 28 days starting from beginning of current week
        week_start = today - timedelta(days=today.weekday())
        dates_to_check = [week_start + timedelta(days=x) for x in range(28)]
        
        app.logger.info(f"Checking dates from {dates_to_check[0]} to {dates_to_check[-1]}")

        # Get existing calendar entries for the participant
        calendar_entries = CalendarStatus.query.filter(
            CalendarStatus.participant_id == participant_id,
            CalendarStatus.date.in_(dates_to_check)
        ).all()
        
        app.logger.info(f"Found {len(calendar_entries)} existing calendar entries")
        
        calendar_data = []
        for date in dates_to_check:
            weekday = WEEKDAY_MAPPING[date.weekday()]
            default_status = getattr(participant, weekday, False)
            
            # Find existing calendar entry if any
            calendar_entry = next(
                (entry for entry in calendar_entries if entry.date == date),
                None
            )
            
            # Get walking bus status from central function
            is_active, reason, reason_type = check_walking_bus_day(date, include_reason=True)
            
            entry_data = {
                'date': date.isoformat(),
                'weekday': weekday,
                'is_schedule_day': is_active,
                'reason': reason,
                'is_past': date < today,
                'status': calendar_entry.status if calendar_entry else default_status,
                'is_today': date == today
            }
            calendar_data.append(entry_data)
            app.logger.debug(f"Processed date {date}: {entry_data}")
        
        app.logger.info(f"Successfully compiled calendar data with {len(calendar_data)} entries")
        return jsonify(calendar_data)
        
    except Exception as e:
        app.logger.error(f"Error in get_calendar_data: {str(e)}")
        return jsonify({'error': str(e)}), 500



@bp.route("/api/update-future-entries", methods=["PUT"])
def update_future_entries():
    data = request.get_json()
    participant_id = data['participant_id']
    day = data['day']
    status = data['status']
    
    today = get_current_date()
    
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
    
    future_dates = []
    current_date = today
    for _ in range(90):
        if current_date.weekday() == target_weekday:
            future_dates.append(current_date)
        current_date += timedelta(days=1)
    
    for date in future_dates:
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


@bp.route('/stream')
def stream():
    def event_stream():
        try:
            last_data = None
            while True:
                with db.session.begin():
                    current_time = get_current_time()
                    stations = Station.query.order_by(Station.position).all()
                    current_data = {
                        "time": current_time.strftime("%H:%M"),
                        "stations": []
                    }
                    
                    for station in stations:
                        station_data = {
                            "id": station.id,
                            "name": station.name,
                            "participants": [
                                {
                                    "id": p.id,
                                    "name": p.name,
                                    "status_today": p.status_today
                                } for p in station.participants
                            ]
                        }
                        current_data["stations"].append(station_data)
                    
                    current_data_str = json.dumps(current_data)
                    
                    if current_data_str != last_data:
                        yield f"data: {current_data_str}\n\n"
                        last_data = current_data_str
                    else:
                        yield f"event: check\ndata: No changes detected at {datetime.now().strftime('%H:%M:%S')}\n\n"
                
                time.sleep(5)
        except Exception as e:
            print(f"Stream error: {e}")
            db.session.remove()
            yield f"event: error\ndata: Connection error occurred\n\n"

    return Response(
        stream_with_context(event_stream()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache, no-transform',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
            'Access-Control-Allow-Origin': '*'
        }
    )


# Progressive Web App (PWA) Funktionalität
@bp.route('/static/service-worker.js')
def service_worker():
    return send_from_directory('static', 'service-worker.js')

@bp.route('/static/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')


def check_walking_bus_day(date, include_reason=False):
    """
    Central function to determine if Walking Bus operates on a given date
    Args:
        date: The date to check
        include_reason: If True, returns tuple (is_active, reason, reason_type), otherwise just boolean
    Returns: 
        bool or (bool, str, str) depending on include_reason parameter
    """
    # Check for manual override first
    override = WalkingBusOverride.query.filter_by(date=date).first()
    if override:
        return (override.is_active, 
                override.reason,  # Use the stored reason
                "MANUAL_OVERRIDE") if include_reason else override.is_active

    # Check for school holidays
    holiday = SchoolHoliday.query\
        .filter(SchoolHoliday.start_date <= date)\
        .filter(SchoolHoliday.end_date >= date)\
        .first()

    if holiday:
        return (False, f"Es sind {holiday.name}.", "HOLIDAY") if include_reason else False

    # Get base schedule
    schedule = WalkingBusSchedule.query.first()
    if not schedule:
        return (False, "Achtung: Keine Planung angelegt!", "NO_SCHEDULE") if include_reason else False
    
    # Check weekday schedule
    weekday = date.weekday()
    weekday_names = ['Montags', 'Dienstags', 'Mittwochs', 'Donnerstags', 'Freitags', 'Samstags', 'Sonntags']
    if not getattr(schedule, WEEKDAY_MAPPING[weekday], False):
        if weekday < 5:
            return (False, f"{weekday_names[weekday]} findet kein Walking Bus statt.", "INACTIVE_WEEKDAY") if include_reason else False
        else:
            return (False, "Am Wochenende findet kein Walking Bus statt.", "WEEKEND") if include_reason else False
  
    # Base case: Walking Bus is active
    return (True, "Active", "ACTIVE") if include_reason else True


def update_holiday_cache():
    service = HolidayService()
    service.update_holiday_cache()


@bp.route("/api/calendar/year", methods=["GET"])
def get_year_calendar():
    current_date = get_current_date()
    # Set start date to first day of current month
    start_date = current_date.replace(day=1)
    end_date = current_date + timedelta(days=365)
    
    calendar_data = []
    current_date = start_date
    
    while current_date <= end_date:
        is_active, reason, reason_type = check_walking_bus_day(current_date, include_reason=True)
        
        # Get note for this date
        daily_note = DailyNote.query.filter_by(date=current_date).first()

        # Map reason types to display text
        display_reason = {
            "NO_SCHEDULE": "Keine Planung",
            "INACTIVE_WEEKDAY": "Kein Bus",
            "WEEKEND": "Wochenende",
            "HOLIDAY": reason.replace("Es sind ", ""),  # Keep full holiday name
            "MANUAL_OVERRIDE": reason, 
            "ACTIVE": ""
        }.get(reason_type, "")
        
        calendar_data.append({
            'date': current_date.isoformat(),
            'is_active': is_active,
            'reason': display_reason,
            'reason_type': reason_type,
            'note': daily_note.note if daily_note else None
        })
        current_date += timedelta(days=1)
    
    return jsonify(calendar_data)


@bp.route("/api/walking-bus-override", methods=["POST"])
def toggle_walking_bus_override():
    data = request.get_json()
    date = datetime.strptime(data['date'], '%Y-%m-%d').date()
    reason = data.get('reason')
    
    # Get original state
    original_state, original_reason, original_type = check_walking_bus_day(date, include_reason=True)
    
    # Check for existing override
    override = WalkingBusOverride.query.filter_by(date=date).first()
    
    if override:
        # Removing override - restore original state
        db.session.delete(override)
        new_state = original_state
        display_reason = original_reason
        reason_type = original_type
    else:
        # Creating new override
        if not reason:
            return jsonify({"error": "Begründung angeben"}), 400
            
        override = WalkingBusOverride(
            date=date, 
            is_active=not original_state,
            reason=reason
        )
        db.session.add(override)
        new_state = not original_state
        display_reason = reason
        reason_type = "MANUAL_OVERRIDE"
    
    db.session.commit()
    
    return jsonify({
        "is_active": new_state,
        "reason": display_reason,
        "original_reason": original_reason,
        "reason_type": reason_type
    })


@bp.route("/api/daily-note", methods=["POST"])
def update_daily_note():
    data = request.get_json()
    date = datetime.strptime(data['date'], '%Y-%m-%d').date()
    note = data.get('note', '').strip()
    
    daily_note = DailyNote.query.filter_by(date=date).first()
    
    if note:
        if daily_note:
            daily_note.note = note
        else:
            daily_note = DailyNote(date=date, note=note)
            db.session.add(daily_note)
    else:
        if daily_note:
            db.session.delete(daily_note)
    
    db.session.commit()
    
    return jsonify({
        "date": date.isoformat(),
        "note": note if note else None
    })


