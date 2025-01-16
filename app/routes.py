from datetime import datetime, timedelta
from flask import (
    Blueprint, render_template, session, jsonify, 
    request, Response, stream_with_context,
    send_from_directory, current_app as app, 
    redirect, url_for
)
from .models import (
    db, WalkingBus, Station, Participant, 
    CalendarStatus, WalkingBusSchedule, 
    SchoolHoliday, WalkingBusOverride, 
    DailyNote, TempToken, AuthToken
)
from .services.holiday_service import HolidayService
from . import get_current_time, get_current_date, TIMEZONE, WEEKDAY_MAPPING
from app import get_git_revision
from .auth import (
    require_auth, SECRET_KEY, is_ip_allowed, 
    record_attempt, get_remaining_lockout_time, 
    get_consistent_hash, login_attempts, 
    MAX_ATTEMPTS, LOCKOUT_TIME, generate_temp_token, 
    temp_login, get_active_temp_tokens, create_auth_token,
    renew_auth_token
)
import jwt
import json
import time
from os import environ
from .init_buses import init_walking_buses

# Create Blueprint
bp = Blueprint("main", __name__)

@bp.route('/favicon.ico')
def favicon():
    return send_from_directory('static/icons', 'favicon.ico')

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


@bp.route("/share")
@require_auth
def share():
    """Template route that uses dictionary directly"""
    token_data = get_active_temp_tokens()
    return render_template("share.html",
                         active_tokens=token_data['tokens'],
                         token_count=token_data['count'],
                         max_tokens=token_data['max'])


@bp.route("/api/temp-tokens")
@require_auth
def get_active_temp_tokens_route():
    """API endpoint that returns JSON response"""
    return jsonify(get_active_temp_tokens())


@bp.route("/api/generate-temp-token")
@require_auth
def generate_temp_token_route():
    return generate_temp_token()


@bp.route("/temp-login/<token>")
def temp_login_route(token):
    if request.headers.get('Accept') == 'application/json':
        return temp_login(token)
    return render_template('temp-login.html')


@bp.route("/api/temp-token/<token>", methods=["DELETE"])
@require_auth
def delete_temp_token(token):
    try:
        app.logger.info(f"Attempting to delete token: {token}")
        token_data = TempToken.query.get(token)
        
        if token_data and token_data.walking_bus_id == session['walking_bus_id']:
            db.session.delete(token_data)
            db.session.commit()
            app.logger.info(f"Token {token} successfully deleted")
            return jsonify({"success": True})
        else:
            app.logger.warning(f"Token {token} not found")
            return jsonify({"error": "Token not found"}), 404
            
    except Exception as e:
        app.logger.error(f"Error deleting token: {str(e)}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/auth-tokens")
@require_auth
def list_auth_tokens():
    tokens = AuthToken.query.order_by(AuthToken.last_used.desc()).all()
    
    return render_template(
        "auth_tokens.html",
        tokens=tokens
    )


@bp.route("/api/auth-token/<token_id>", methods=["DELETE"])
@require_auth
def revoke_auth_token(token_id):
    token = AuthToken.query.get(token_id)
    if token and token.walking_bus_id == session['walking_bus_id']:
        token.invalidate("Manually revoked")
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"error": "Token not found"}), 404


# Station Routes
@bp.route("/api/stations", methods=["GET"])
@require_auth
def get_stations():
    walking_bus_id = get_current_walking_bus_id()
    selected_date = request.args.get('date')
    is_admin = request.args.get('admin', '0') == '1'
    
    if selected_date:
        target_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
    else:
        target_date = get_current_date()

    # Get regular stations with eager loading of participants
    stations = (Station.query
               .filter_by(walking_bus_id=walking_bus_id)
               .order_by(Station.position)
               .all())

    result = []

    # Add unassigned section only for admin view
    if is_admin:
        unassigned_participants = Participant.query.filter_by(
            walking_bus_id=walking_bus_id,
            station_id=None
        ).order_by(Participant.position).all()

        if unassigned_participants:
            result.append(create_unassigned_section(unassigned_participants, target_date))

    # Process regular stations
    for station in stations:
        station_data = {
            "id": station.id,
            "name": station.name,
            "position": station.position,
            "participants": create_participant_list(station.participants, target_date, is_admin)
        }
        result.append(station_data)

    return jsonify(result)


def create_unassigned_section(participants, target_date):
    """Helper function to create unassigned section data"""
    unassigned_data = []
    for p in participants:
        participant_data = create_participant_data(p, target_date, True)
        unassigned_data.append(participant_data)
    
    return {
        "id": "unassigned",
        "name": "Nicht zugeordnete Teilnehmer",
        "position": -1,
        "participants": unassigned_data
    }


def create_participant_list(participants, target_date, is_admin):
    """Helper function to create participant list with appropriate data"""
    return [create_participant_data(p, target_date, is_admin) for p in participants]


def create_participant_data(participant, target_date, is_admin):
    """Helper function to create participant data based on view type"""
    calendar_entry = CalendarStatus.query.filter_by(
        participant_id=participant.id,
        date=target_date,
        walking_bus_id=participant.walking_bus_id
    ).first()
    
    status = calendar_entry.status if calendar_entry else getattr(
        participant, 
        WEEKDAY_MAPPING[target_date.weekday()], 
        True
    )
    
    # Base data for both views
    data = {
        "id": participant.id,
        "name": participant.name,
        "status": status
    }
    
    # Additional data for admin view
    if is_admin:
        data.update({
            "monday": participant.monday,
            "tuesday": participant.tuesday,
            "wednesday": participant.wednesday,
            "thursday": participant.thursday,
            "friday": participant.friday,
            "saturday": participant.saturday,
            "sunday": participant.sunday,
            "position": participant.position
        })
    
    return data


@bp.route("/api/stations", methods=["POST"])
@require_auth
def create_station():
    walking_bus_id = get_current_walking_bus_id()
    data = request.get_json()
    
    # First update positions of existing stations to make room
    existing_stations = Station.query.filter(Station.position >= 0).order_by(Station.position).all()
    for station in existing_stations:
        station.position += 1
    
    # Create new station at position 0
    new_station = Station(name=data['name'], position=0, walking_bus_id=walking_bus_id)
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
@require_auth
def update_station(station_id):
    walking_bus_id = get_current_walking_bus_id()
    station = Station.query.filter_by(id=station_id, walking_bus_id=walking_bus_id).first_or_404()
    
    data = request.get_json()
    old_name = station.name
    
    if 'name' in data:
        station.name = data['name']
    
    db.session.commit()
    app.logger.info(f"Haltestelle geändert von '{old_name}' zu '{station.name}' (ID: {station_id})")
    return jsonify({"success": True})



@bp.route("/api/stations/<int:station_id>", methods=["DELETE"])
@require_auth
def delete_station(station_id):
    walking_bus_id = get_current_walking_bus_id()
    station = Station.query.filter_by(id=station_id, walking_bus_id=walking_bus_id).first_or_404()
    
    db.session.delete(station)
    db.session.commit()
    return jsonify({"success": True})



@bp.route("/api/stations/<int:station_id>/stats")
@require_auth
def get_station_stats(station_id):
    try:
        walking_bus_id = get_current_walking_bus_id()
        station = Station.query.filter_by(id=station_id, walking_bus_id=walking_bus_id).first_or_404()
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
@require_auth
def get_stations_total_stats():
    try:
        walking_bus_id = get_current_walking_bus_id()
        # Get all stations for current walking bus
        stations = Station.query.filter_by(walking_bus_id=walking_bus_id).all()
        
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
@require_auth
def update_stations_order():
    try:
        walking_bus_id = get_current_walking_bus_id()
        data = request.get_json()
        if not isinstance(data, list):
            return jsonify({"error": "Invalid data format. Expected a list."}), 400

        # Validate all station IDs exist before updating
        station_ids = [station_data['id'] for station_data in data]
        stations = Station.query.filter(
            Station.id.in_(station_ids),
            Station.walking_bus_id == walking_bus_id
        ).all()
        
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
@require_auth
def create_participant():
    walking_bus_id = get_current_walking_bus_id()
    data = request.get_json()
    today = get_current_date()
    weekday = WEEKDAY_MAPPING[today.weekday()]
    
    # Verify station belongs to current walking bus
    station = Station.query.filter_by(
        id=data['station_id'], 
        walking_bus_id=walking_bus_id
    ).first_or_404()
    
    new_participant = Participant(
        name=data['name'],
        station_id=data['station_id'],
        position=data['position'],
        walking_bus_id=walking_bus_id  # Add walking bus association
    )
    db.session.add(new_participant)
    db.session.flush()
    app.logger.info(f"Neuer Teilnehmer erstellt: {new_participant.name} (ID: {new_participant.id})")
    
    calendar_entry = CalendarStatus(
        participant_id=new_participant.id,
        date=today,
        status=getattr(new_participant, weekday, True),
        is_manual_override=False,
        walking_bus_id=walking_bus_id  # Add walking bus association
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
@require_auth
def update_participant(station_id, participant_id):
    walking_bus_id = get_current_walking_bus_id()
    
    participant = Participant.query.filter_by(
        id=participant_id,
        walking_bus_id=walking_bus_id
    ).first_or_404()
    
    data = request.get_json()
    old_name = participant.name
    old_station_id = participant.station_id
    
    # Verify new station belongs to same walking bus if station_id is being updated
    if 'station_id' in data:
        Station.query.filter_by(
            id=data['station_id'],
            walking_bus_id=walking_bus_id
        ).first_or_404()
    
    # Handle position updates
    if 'position' in data:
        new_position = data['position']
        new_station_id = data.get('station_id', old_station_id)
        
        # Update positions in new station
        station_participants = Participant.query.filter_by(
            station_id=new_station_id,
            walking_bus_id=walking_bus_id
        ).order_by(Participant.position).all()
        
        # Remove participant from list if it exists
        station_participants = [p for p in station_participants if p.id != participant_id]
        
        # Insert participant at new position
        station_participants.insert(new_position, participant)
        
        # Update all positions
        for idx, p in enumerate(station_participants):
            p.position = idx
    
    # Update participant fields
    for field in ['name', 'station_id', 'monday', 'tuesday', 'wednesday',
                 'thursday', 'friday', 'saturday', 'sunday']:
        if field in data:
            setattr(participant, field, data[field])
    
    db.session.commit()
    return jsonify({"success": True})


@bp.route("/api/participants/<int:participant_id>", methods=["DELETE"])
@require_auth
def delete_participant(participant_id):
    try:
        walking_bus_id = get_current_walking_bus_id()
        
        # Delete calendar entries for this participant within the walking bus
        CalendarStatus.query.filter_by(
            participant_id=participant_id,
            walking_bus_id=walking_bus_id
        ).delete()
        
        # Get and verify participant belongs to current walking bus
        participant = Participant.query.filter_by(
            id=participant_id,
            walking_bus_id=walking_bus_id
        ).first_or_404()
        
        name = participant.name  # Store name before deletion
        app.logger.info(f"Lösche Teilnehmer {name} (ID: {participant_id})")
        
        db.session.delete(participant)
        db.session.commit()
        return jsonify({"success": True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/api/participation/<int:participant_id>", methods=["PATCH"])
@require_auth
def toggle_participation(participant_id):
    walking_bus_id = get_current_walking_bus_id()
    data = request.get_json()
    target_date = datetime.strptime(data['date'], '%Y-%m-%d').date() if data.get('date') else get_current_date()
    
    participant = Participant.query.filter_by(
        id=participant_id,
        walking_bus_id=walking_bus_id
    ).first_or_404()
    
    calendar_entry = CalendarStatus.query.filter_by(
        participant_id=participant_id,
        date=target_date,
        walking_bus_id=walking_bus_id
    ).first()

    new_status = not (calendar_entry.status if calendar_entry else getattr(participant, WEEKDAY_MAPPING[target_date.weekday()], True))
    
    if calendar_entry:
        calendar_entry.status = new_status
        calendar_entry.is_manual_override = True
    else:
        calendar_entry = CalendarStatus(
            participant_id=participant_id,
            date=target_date,
            status=new_status,
            is_manual_override=True,
            walking_bus_id=walking_bus_id
        )
        db.session.add(calendar_entry)

    if target_date == get_current_date():
        participant.status_today = new_status
    
    db.session.commit()
    
    return jsonify({
        "status_today": new_status,
        "participant_id": participant.id,
        "date": target_date.isoformat()
    })


@bp.route("/api/participant/<int:participant_id>/weekday-status/<string:weekday>")
@require_auth
def get_participant_weekday_status(participant_id, weekday):
    walking_bus_id = get_current_walking_bus_id()
    
    participant = Participant.query.filter_by(
        id=participant_id,
        walking_bus_id=walking_bus_id
    ).first_or_404()
    
    status = getattr(participant, weekday, True)
    return jsonify({"status": status})


# Schedule and Calendar Routes
@bp.route("/api/initialize-daily-status", methods=["POST"])
@require_auth
def initialize_daily_status():
    try:
        # Get and validate date from request
        data = request.get_json()
        requested_date = None
        if data and 'date' in data:
            try:
                requested_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

        # Token handling
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        payload = jwt.decode(token, options={"verify_signature": False})
        exp_timestamp = payload['exp']
        exp_date = datetime.fromtimestamp(exp_timestamp)
        remaining_days = (exp_date - datetime.utcnow()).days

        # Add these logging statements
        app.logger.info(f"[TOKEN] Current time: {datetime.utcnow()}")
        app.logger.info(f"[TOKEN] Expiration date: {exp_date}")
        app.logger.info(f"[TOKEN] Days remaining: {remaining_days}")

        new_token = None
        if remaining_days < 30:
            verified_payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            new_token = renew_auth_token(token, verified_payload)
            app.logger.info("Created new token with extended expiration")
            app.logger.info(f"[TOKEN] Created new token with {remaining_days} days remaining")

        walking_bus_id = get_current_walking_bus_id()
        target_date = requested_date if requested_date else get_current_date()
        current_time = get_current_time().time()
        
        app.logger.info(f"Initializing daily status for {target_date} at {current_time}")

        # Update holiday cache
        holiday_service = HolidayService()
        holiday_service.update_holiday_cache()

        # Clean up past entries for current date only
        if not requested_date:
            deleted_count = CalendarStatus.query.filter(
                CalendarStatus.date < target_date,
                CalendarStatus.walking_bus_id == walking_bus_id
            ).delete()
            app.logger.info(f"Deleted {deleted_count} past calendar entries")
            db.session.commit()

        # Get schedule information
        schedule = WalkingBusSchedule.query.filter_by(walking_bus_id=walking_bus_id).first()
        schedule_data = None
        if schedule:
            weekday = target_date.weekday()
            weekday_name = WEEKDAY_MAPPING[weekday]
            start_time = getattr(schedule, f"{weekday_name}_start", None)
            end_time = getattr(schedule, f"{weekday_name}_end", None)
            
            schedule_data = {
                "active": getattr(schedule, weekday_name, False),
                "start": start_time.strftime("%H:%M") if start_time else None,
                "end": end_time.strftime("%H:%M") if end_time else None
            }

        # Get daily note
        daily_note = DailyNote.query.filter_by(
            date=target_date,
            walking_bus_id=walking_bus_id
        ).first()

        # Check walking bus status
        walking_bus_day, reason, reason_type = check_walking_bus_day(target_date, include_reason=True)
        app.logger.info(f"Walking bus day status: {walking_bus_day}")

        # Initialize time_passed before any checks
        time_passed = False

        # Get today's date for comparison
        today = get_current_date()

        # Check walking bus status
        walking_bus_day, reason, reason_type = check_walking_bus_day(target_date, include_reason=True)
        app.logger.info(f"Walking bus day status: {walking_bus_day}")

        # Then modify the time check to only apply for current day
        if walking_bus_day and schedule_data and schedule_data["end"]:
            end_time = datetime.strptime(schedule_data["end"], "%H:%M").time()
            app.logger.info(f"Target date: {target_date}, Today: {today}")
            app.logger.info(f"Parsed end_time: {end_time}")
            
            # Ensure target_date is a date object for comparison
            if isinstance(target_date, str):
                target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
            
            # Only check time if we're looking at today
            if target_date == today:
                app.logger.info(f"Checking time for today: {current_time} > {end_time}")
                if current_time > end_time:
                    app.logger.info("Time check conditions met - updating status")
                    walking_bus_day = False
                    reason = "Der Walking Bus hat heute bereits stattgefunden."
                    reason_type = "TIME_PASSED"
                    time_passed = True

        # Now handle reason formatting
        if time_passed:
            display_reason = reason
        elif reason_type == "HOLIDAY" and isinstance(reason, dict):
            display_reason = reason.get("full_reason", "")
        else:
            display_reason = str(reason)

        response = {
            "success": True,
            "currentDate": target_date.isoformat(),
            "isWalkingBusDay": walking_bus_day,
            "reason": display_reason,
            "reason_type": reason_type,  # This will now correctly show TIME_PASSED
            "note": daily_note.note if daily_note else None,
            "schedule": schedule_data
        }

        if new_token:
            response['new_auth_token'] = new_token

        app.logger.info(f"Final response: {response}")
        return jsonify(response)

    except Exception as e:
        app.logger.error(f"Error in initialize_daily_status: {str(e)}")
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@bp.route("/api/week-overview")
@require_auth
def get_week_overview():
    walking_bus_id = get_current_walking_bus_id()
    today = get_current_date()
    current_time = get_current_time().time()
    
    week_data = []
    
    for i in range(6):
        current_date = today + timedelta(days=i)
        # Get full walking bus day info including reason and reason_type
        is_active, reason, reason_type = check_walking_bus_day(
            current_date,
            include_reason=True,
            walking_bus_id=walking_bus_id
        )
        
        # Check if time has passed for today
        if current_date == today:
            schedule = WalkingBusSchedule.query.filter_by(walking_bus_id=walking_bus_id).first()
            if schedule:
                weekday = WEEKDAY_MAPPING[current_date.weekday()]
                end_time = getattr(schedule, f"{weekday}_end", None)
                if end_time and current_time > end_time:
                    is_active = False
                    reason = "Der Walking Bus hat heute bereits stattgefunden."
                    reason_type = "TIME_PASSED"
        
        # Get schedule information
        schedule = WalkingBusSchedule.query.filter_by(walking_bus_id=walking_bus_id).first()
        weekday = WEEKDAY_MAPPING[current_date.weekday()]
        is_schedule_day = schedule and getattr(schedule, weekday, False)
        
        # Check for manual override
        override = WalkingBusOverride.query.filter_by(
            date=current_date,
            walking_bus_id=walking_bus_id
        ).first()
        
        # Check for notes
        note = DailyNote.query.filter_by(
            date=current_date,
            walking_bus_id=walking_bus_id
        ).first()
        
        # Calculate total confirmed participants
        total_confirmed = 0
        if is_active:
            participants = Participant.query.filter(
                Participant.walking_bus_id == walking_bus_id,
                Participant.station_id.isnot(None)
            ).all()
            
            calendar_entries = CalendarStatus.query.filter_by(
                walking_bus_id=walking_bus_id,
                date=current_date
            ).all()
            
            calendar_lookup = {entry.participant_id: entry.status for entry in calendar_entries}
            
            for participant in participants:
                if participant.id in calendar_lookup:
                    if calendar_lookup[participant.id]:
                        total_confirmed += 1
                elif getattr(participant, weekday, True):
                    total_confirmed += 1
        
        week_data.append({
            'date': current_date.isoformat(),
            'is_active': is_active,
            'is_schedule_day': is_schedule_day,
            'reason': reason,
            'reason_type': reason_type,
            'total_confirmed': total_confirmed,
            'is_today': current_date == today,
            'has_override': override is not None,
            'has_note': note is not None and note.note.strip() != ''
        })
    
    return jsonify(week_data)


@bp.route("/api/walking-bus-schedule", methods=["GET"])
@require_auth
def get_schedule():
    app.logger.info("Starting get_schedule request")
    
    walking_bus_id = get_current_walking_bus_id()
    app.logger.debug(f"Current walking_bus_id: {walking_bus_id}")
    
    if not walking_bus_id:
        app.logger.error("No walking bus ID found in session")
        return jsonify({
            "error": "No walking bus selected",
            "redirect": True
        }), 401

    try:
        schedule = WalkingBusSchedule.query.filter_by(walking_bus_id=walking_bus_id).first()
        app.logger.debug(f"Found schedule: {schedule is not None}")
        
        if not schedule:
            app.logger.info(f"Creating new schedule for walking_bus_id: {walking_bus_id}")
            schedule = WalkingBusSchedule(
                walking_bus_id=walking_bus_id,
                monday_start=WalkingBusSchedule.DEFAULT_START,
                monday_end=WalkingBusSchedule.DEFAULT_END,
                tuesday_start=WalkingBusSchedule.DEFAULT_START,
                tuesday_end=WalkingBusSchedule.DEFAULT_END,
                wednesday_start=WalkingBusSchedule.DEFAULT_START,
                wednesday_end=WalkingBusSchedule.DEFAULT_END,
                thursday_start=WalkingBusSchedule.DEFAULT_START,
                thursday_end=WalkingBusSchedule.DEFAULT_END,
                friday_start=WalkingBusSchedule.DEFAULT_START,
                friday_end=WalkingBusSchedule.DEFAULT_END,
                saturday_start=WalkingBusSchedule.DEFAULT_START,
                saturday_end=WalkingBusSchedule.DEFAULT_END,
                sunday_start=WalkingBusSchedule.DEFAULT_START,
                sunday_end=WalkingBusSchedule.DEFAULT_END
            )
            db.session.add(schedule)
            db.session.commit()
            app.logger.info("New schedule created successfully")

        response_data = {
            "monday": {
                "active": schedule.monday,
                "start": schedule.monday_start.strftime("%H:%M") if schedule.monday_start else None,
                "end": schedule.monday_end.strftime("%H:%M") if schedule.monday_end else None
            },
            "tuesday": {
                "active": schedule.tuesday,
                "start": schedule.tuesday_start.strftime("%H:%M") if schedule.tuesday_start else None,
                "end": schedule.tuesday_end.strftime("%H:%M") if schedule.tuesday_end else None
            },
            "wednesday": {
                "active": schedule.wednesday,
                "start": schedule.wednesday_start.strftime("%H:%M") if schedule.wednesday_start else None,
                "end": schedule.wednesday_end.strftime("%H:%M") if schedule.wednesday_end else None
            },
            "thursday": {
                "active": schedule.thursday,
                "start": schedule.thursday_start.strftime("%H:%M") if schedule.thursday_start else None,
                "end": schedule.thursday_end.strftime("%H:%M") if schedule.thursday_end else None
            },
            "friday": {
                "active": schedule.friday,
                "start": schedule.friday_start.strftime("%H:%M") if schedule.friday_start else None,
                "end": schedule.friday_end.strftime("%H:%M") if schedule.friday_end else None
            },
            "saturday": {
                "active": schedule.saturday,
                "start": schedule.saturday_start.strftime("%H:%M") if schedule.saturday_start else None,
                "end": schedule.saturday_end.strftime("%H:%M") if schedule.saturday_end else None
            },
            "sunday": {
                "active": schedule.sunday,
                "start": schedule.sunday_start.strftime("%H:%M") if schedule.sunday_start else None,
                "end": schedule.sunday_end.strftime("%H:%M") if schedule.sunday_end else None
            }
        }
        app.logger.debug(f"Returning response data: {response_data}")
        return jsonify(response_data)
        
    except Exception as e:
        app.logger.error(f"Error in get_schedule: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Internal server error",
            "details": str(e)
        }), 500


@bp.route("/api/walking-bus-schedule", methods=["PUT"])
@require_auth
def update_schedule():
    walking_bus_id = get_current_walking_bus_id()
    data = request.get_json()
    
    schedule = WalkingBusSchedule.query.filter_by(walking_bus_id=walking_bus_id).first()
    if not schedule:
        schedule = WalkingBusSchedule(walking_bus_id=walking_bus_id)
        db.session.add(schedule)
    
    for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
        day_data = data.get(day, {})
        setattr(schedule, day, day_data.get('active', False))
        
        start_time = day_data.get('start')
        end_time = day_data.get('end')
        
        # Time validation
        if start_time and end_time:
            start = datetime.strptime(start_time, "%H:%M").time()
            end = datetime.strptime(end_time, "%H:%M").time()
            
            if start >= end:
                return jsonify({
                    "error": f"Die Startzeit muss vor der Endzeit liegen ({day})"
                }), 400
                
            setattr(schedule, f"{day}_start", start)
            setattr(schedule, f"{day}_end", end)
    
    db.session.commit()
    return jsonify({"success": True})


@bp.route("/api/calendar-status", methods=["POST"])
@require_auth
def update_calendar_status():
    walking_bus_id = get_current_walking_bus_id()
    data = request.get_json()
    participant_id = data['participant_id']
    
    # Get participant information with walking bus verification
    participant = Participant.query.filter_by(
        id=participant_id,
        walking_bus_id=walking_bus_id
    ).first_or_404()
    
    # Correct way to handle timezone with zoneinfo
    naive_date = datetime.strptime(data['date'], '%Y-%m-%d')
    aware_date = datetime.combine(naive_date.date(), datetime.min.time(), tzinfo=TIMEZONE)
    date = aware_date.date()
    
    status = data['status']
    
    calendar_entry = CalendarStatus.query.filter_by(
        participant_id=participant_id,
        date=date,
        walking_bus_id=walking_bus_id
    ).first()
    
    if calendar_entry:
        calendar_entry.status = status
        calendar_entry.is_manual_override = True
    else:
        calendar_entry = CalendarStatus(
            participant_id=participant_id,
            date=date,
            status=status,
            is_manual_override=True,
            walking_bus_id=walking_bus_id
        )
        db.session.add(calendar_entry)
    
    if date == get_current_date():
        participant.status_today = status
    
    db.session.commit()
    app.logger.info(f"Kalenderstatus für {participant.name} (ID: {participant_id}) am {date} auf {status} gesetzt")
    return jsonify({"success": True})



@bp.route("/api/calendar-status/<int:participant_id>", methods=["GET"])
@require_auth
def get_calendar_status(participant_id):
    walking_bus_id = get_current_walking_bus_id()
    
    entries = CalendarStatus.query.filter_by(
        participant_id=participant_id,
        walking_bus_id=walking_bus_id
    ).all()
    
    return jsonify([{
        'date': entry.date.isoformat(),
        'status': entry.status
    } for entry in entries])



@bp.route("/api/calendar-data/<int:participant_id>", methods=["GET"])
@require_auth
def get_calendar_data(participant_id):
    try:
        walking_bus_id = get_current_walking_bus_id()
        if not walking_bus_id:
            return jsonify({"error": "No walking bus selected", "redirect": True}), 401
        app.logger.info(f"Fetching calendar data for participant {participant_id}")
        
        # Verify participant belongs to current walking bus
        participant = Participant.query.filter_by(
            id=participant_id,
            walking_bus_id=walking_bus_id
        ).first_or_404()
        
        today = get_current_date()
        
        # Calculate dates for next 28 days starting from beginning of current week
        week_start = today - timedelta(days=today.weekday())
        dates_to_check = [week_start + timedelta(days=x) for x in range(28)]
        
        app.logger.info(f"Checking dates from {dates_to_check[0]} to {dates_to_check[-1]}")

        # Get existing calendar entries for the participant within walking bus
        calendar_entries = CalendarStatus.query.filter(
            CalendarStatus.participant_id == participant_id,
            CalendarStatus.walking_bus_id == walking_bus_id,
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
@require_auth
def update_future_entries():
    walking_bus_id = get_current_walking_bus_id()
    data = request.get_json()
    participant_id = data['participant_id']
    day = data['day']
    status = data['status']
    
    # Verify participant belongs to current walking bus
    participant = Participant.query.filter_by(
        id=participant_id,
        walking_bus_id=walking_bus_id
    ).first_or_404()
    
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
            walking_bus_id=walking_bus_id,
            date=date
        ).first()
        
        if not calendar_entry or not calendar_entry.is_manual_override:
            if calendar_entry:
                calendar_entry.status = status
            else:
                new_entry = CalendarStatus(
                    participant_id=participant_id,
                    walking_bus_id=walking_bus_id,
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
        retry_count = 0
        max_retries = 3
        retry_delay = 2

        while retry_count < max_retries:
            walking_bus_id = get_current_walking_bus_id()
            if walking_bus_id:
                try:
                    last_data = None
                    while True:
                        with db.session.begin():
                            current_time = get_current_time()
                            current_date = get_current_date()
                            
                            # Get schedule for time check
                            schedule = WalkingBusSchedule.query.filter_by(walking_bus_id=walking_bus_id).first()
                            
                            # Get stations data
                            stations = Station.query.filter_by(
                                walking_bus_id=walking_bus_id
                            ).order_by(Station.position).all()
                            
                            # Get week overview data
                            week_data = []
                            today = get_current_date()
                            
                            # Pre-fetch all participants and calendar entries
                            participants = Participant.query.filter(
                                Participant.walking_bus_id == walking_bus_id,
                                Participant.station_id.isnot(None)
                            ).all()
                            
                            calendar_entries = CalendarStatus.query.filter(
                                CalendarStatus.walking_bus_id == walking_bus_id,
                                CalendarStatus.date >= today,
                                CalendarStatus.date <= today + timedelta(days=5)
                            ).all()
                            
                            # Create lookup dictionary
                            calendar_lookup = {}
                            for entry in calendar_entries:
                                if entry.date not in calendar_lookup:
                                    calendar_lookup[entry.date] = {}
                                calendar_lookup[entry.date][entry.participant_id] = entry.status

                            # Process each day
                            for i in range(6):
                                check_date = today + timedelta(days=i)
                                is_active, reason, reason_type = check_walking_bus_day(
                                    check_date,
                                    include_reason=True,
                                    walking_bus_id=walking_bus_id
                                )
                                
                                # Check for TIME_PASSED specifically for today
                                if check_date == today and is_active and schedule:
                                    weekday = WEEKDAY_MAPPING[today.weekday()]
                                    end_time = getattr(schedule, f"{weekday}_end", None)
                                    if end_time:
                                        current_time_obj = current_time.time()
                                        if current_time_obj > end_time:
                                            is_active = False
                                            reason = "Der Walking Bus hat heute bereits stattgefunden."
                                            reason_type = "TIME_PASSED"
                                
                                # Calculate confirmed participants
                                total_confirmed = 0
                                if is_active and reason_type != 'TIME_PASSED':
                                    weekday = WEEKDAY_MAPPING[check_date.weekday()]
                                    for participant in participants:
                                        if check_date in calendar_lookup and participant.id in calendar_lookup[check_date]:
                                            if calendar_lookup[check_date][participant.id]:
                                                total_confirmed += 1
                                        elif getattr(participant, weekday, True):
                                            total_confirmed += 1
                                
                                week_data.append({
                                    'date': check_date.isoformat(),
                                    'total_confirmed': total_confirmed,
                                    'is_active': is_active,
                                    'reason': reason,
                                    'reason_type': reason_type
                                })

                            # Combine all data
                            current_data = {
                                "time": current_time.strftime("%H:%M"),
                                "date": current_date.isoformat(),
                                "stations": [
                                    {
                                        "id": station.id,
                                        "name": station.name,
                                        "participants": [
                                            {
                                                "id": p.id,
                                                "name": p.name,
                                                "status_today": p.status_today
                                            } for p in station.participants
                                        ]
                                    } for station in stations
                                ],
                                "week_overview": week_data
                            }
                            
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
            else:
                retry_count += 1
                time.sleep(retry_delay)
                yield f"event: retry\ndata: Waiting for authentication...\n\n"
                continue
        
        # After max retries without successful authentication
        yield f"event: unauthorized\ndata: Authentication failed\n\n"

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


def check_walking_bus_day(date, include_reason=False, walking_bus_id=None):
    """
    Central function to determine if Walking Bus operates on a given date
    Args:
        date: The date to check
        include_reason: If True, returns tuple (is_active, reason, reason_type), otherwise just boolean
        walking_bus_id: ID of the walking bus to check. If None, gets current from session.
    Returns:
        bool or (bool, str, str) depending on include_reason parameter
    """
    if walking_bus_id is None:
        walking_bus_id = get_current_walking_bus_id()

    # Check for manual override first
    override = WalkingBusOverride.query.filter_by(
        date=date,
        walking_bus_id=walking_bus_id
    ).first()
    if override:
        return (override.is_active, 
                override.reason,
                "MANUAL_OVERRIDE") if include_reason else override.is_active

    # Check for school holidays
    holiday = SchoolHoliday.query\
        .filter(SchoolHoliday.start_date <= date)\
        .filter(SchoolHoliday.end_date >= date)\
        .first()

    if holiday:
        short_reason = holiday.name
        full_reason = f"Es sind {holiday.name}."
        return (False, {"short_reason": short_reason, "full_reason": full_reason}, "HOLIDAY") if include_reason else False

    # Get base schedule for specific walking bus
    schedule = WalkingBusSchedule.query.filter_by(walking_bus_id=walking_bus_id).first()
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


@bp.route('/api/calendar/months/<int:year>/<int:month>/<int:count>')
@require_auth
def get_calendar_months(year, month, count):
    walking_bus_id = get_current_walking_bus_id()
    
    # Calculate start and end date for exactly one month
    start_date = datetime(year, month + 1, 1).date()
    
    if month == 11:  # December
        end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        end_date = datetime(year, month + 2, 1).date() - timedelta(days=1)
    
    calendar_data = []
    current_date = start_date
    
    while current_date <= end_date:
        is_active, reason, reason_type = check_walking_bus_day(
            current_date, 
            include_reason=True,
            walking_bus_id=walking_bus_id
        )
        daily_note = DailyNote.query.filter_by(
            date=current_date,
            walking_bus_id=walking_bus_id
        ).first()
        
        # Map reason types to display text - keeping the original mapping
        display_reason = {
            "NO_SCHEDULE": "Keine Planung",
            "INACTIVE_WEEKDAY": "Kein Bus",
            "WEEKEND": "Wochenende",
            "HOLIDAY": reason["short_reason"] if reason_type == "HOLIDAY" else reason,
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
@require_auth
def toggle_walking_bus_override():
    walking_bus_id = get_current_walking_bus_id()
    data = request.get_json()
    date = datetime.strptime(data['date'], '%Y-%m-%d').date()
    reason = data.get('reason')
    
    # Get original state with walking bus context
    original_state, original_reason, original_type = check_walking_bus_day(
        date, 
        include_reason=True,
        walking_bus_id=walking_bus_id
    )
    
    # Check for existing override within walking bus context
    override = WalkingBusOverride.query.filter_by(
        date=date,
        walking_bus_id=walking_bus_id
    ).first()
    
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
            reason=reason,
            walking_bus_id=walking_bus_id
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
@require_auth
def update_daily_note():
    walking_bus_id = get_current_walking_bus_id()
    data = request.get_json()
    date = datetime.strptime(data['date'], '%Y-%m-%d').date()
    note = data.get('note', '').strip()
    
    daily_note = DailyNote.query.filter_by(
        date=date,
        walking_bus_id=walking_bus_id
    ).first()
    
    if note:
        if daily_note:
            daily_note.note = note
        else:
            daily_note = DailyNote(
                date=date, 
                note=note,
                walking_bus_id=walking_bus_id
            )
            db.session.add(daily_note)
    else:
        if daily_note:
            db.session.delete(daily_note)
    
    db.session.commit()
    
    return jsonify({
        "date": date.isoformat(),
        "note": note if note else None
    })


def get_current_walking_bus_id():
    app.logger.debug("Getting current walking bus ID")
    
    # For single bus mode
    if not environ.get('WALKING_BUSES'):
        app.logger.debug("Single bus mode detected")
        default_bus = WalkingBus.query.filter_by(name='Default Bus').first()
        if default_bus:
            app.logger.debug(f"Using default bus with ID: {default_bus.id}")
            return default_bus.id
        app.logger.error("No default bus found")
        return None
    
    # For multi bus mode
    bus_id = session.get("walking_bus_id")
    app.logger.debug(f"Multi bus mode - Found bus ID in session: {bus_id}")
    return bus_id


@bp.route("/login", methods=["GET", "POST"])
def login():
    ip = request.remote_addr
    is_multi_bus = init_walking_buses()
    configured_bus_ids = app.config.get('CONFIGURED_BUS_IDS', [])
    buses = WalkingBus.query.filter(
        WalkingBus.id.in_(configured_bus_ids)
    ).order_by(WalkingBus.id).all() if is_multi_bus else None

    common_data = {
        'git_revision': get_git_revision(),
        'is_multi_bus': is_multi_bus,
        'buses': [{'id': bus.id, 'name': bus.name} for bus in (buses or [])],
        'selected_bus_id': None
    }

    if request.method == 'GET':
        return render_template('login.html',
                     hide_menu=True,
                     **common_data)

    # Handle POST requests
    if not is_ip_allowed():
        remaining_minutes = get_remaining_lockout_time(ip)
        if remaining_minutes > 0:
            return jsonify({
                'success': False,
                'error': f"Zu viele Versuche. Bitte warten Sie {remaining_minutes} Minuten.",
                **common_data
            }), 401

    password = request.form.get('password')
    selected_bus_id = request.form.get('walking_bus')
    common_data['selected_bus_id'] = selected_bus_id

    if is_multi_bus and not selected_bus_id:
        return jsonify({
            'success': False,
            'error': "Bitte Walking Bus und Passwort eingeben",
            **common_data
        }), 400

    bus = (WalkingBus.query.get(selected_bus_id) if is_multi_bus
           else WalkingBus.query.filter(WalkingBus.id.in_(configured_bus_ids)).first())

    if bus and bus.password == password:
        # Success case - create token and session
        user_agent = request.headers.get('User-Agent')
        password_hash = get_consistent_hash(bus.password)
        auth_token = create_auth_token(
            bus.id,
            bus.name,
            password_hash,
            client_info=user_agent
        )
           
        session['walking_bus_id'] = bus.id
        session['walking_bus_name'] = bus.name
        session['bus_password_hash'] = password_hash
        session.permanent = True

        return jsonify({
            'success': True,
            'auth_token': auth_token,
            'redirect_url': url_for('main.index')
        })

    # Handle failed login
    record_attempt()
    remaining_attempts = MAX_ATTEMPTS - len(login_attempts[ip])
    lockout_minutes = LOCKOUT_TIME.total_seconds() / 60
   
    return jsonify({
        'success': False,
        'error': f"Ungültiges Passwort. Noch {remaining_attempts} Versuche innerhalb von {int(lockout_minutes)} Minuten übrig.",
        **common_data
    }), 401


@bp.route("/logout")
def logout():
    # Get current token from header or session
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token and 'auth_token' in session:
        token = session['auth_token']
    
    if token:
        # Invalidate token in database
        token_record = AuthToken.query.get(token)
        if token_record:
            token_record.invalidate("User logout")
            db.session.commit()
    
    session.clear()
    return jsonify({
        "message": "Logged out successfully",
        "clear_cache": True
    }), 200, {
        'Cache-Control': 'no-cache, no-store, must-revalidate, private',
        'Pragma': 'no-cache',
        'Expires': '-1'
    }
