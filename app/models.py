from . import db
from datetime import datetime, time, timedelta
from . import get_current_time


class WalkingBus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(100), nullable=False)

    # Relationships
    stations = db.relationship('Station', backref='walking_bus', lazy=True)
    participants = db.relationship('Participant', backref='walking_bus', lazy=True)
    schedule = db.relationship('WalkingBusSchedule', backref='walking_bus', lazy=True, uselist=False)
    overrides = db.relationship('WalkingBusOverride', backref='walking_bus', lazy=True)
    daily_notes = db.relationship('DailyNote', backref='walking_bus', lazy=True)


class Station(db.Model):
    walking_bus_id = db.Column(db.Integer, db.ForeignKey('walking_bus.id'), nullable=False)
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)  # Reihenfolge
    arrival_time = db.Column(db.Time, nullable=True) 
    participants = db.relationship('Participant', backref='station', lazy=True, order_by='Participant.position')


class Participant(db.Model):
    walking_bus_id = db.Column(db.Integer, db.ForeignKey('walking_bus.id'), nullable=False)
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)  # Reihenfolge innerhalb der Station
    station_id = db.Column(db.Integer, db.ForeignKey('station.id'), nullable=True)
    monday = db.Column(db.Boolean, default=True)
    tuesday = db.Column(db.Boolean, default=True)
    wednesday = db.Column(db.Boolean, default=True)
    thursday = db.Column(db.Boolean, default=True)
    friday = db.Column(db.Boolean, default=True)
    saturday = db.Column(db.Boolean, default=True)
    sunday = db.Column(db.Boolean, default=True)
    status_today = db.Column(db.Boolean, default=True)  # True = gruen (nimmt teil)
    status_initialized_date = db.Column(db.DateTime)


class CalendarStatus(db.Model):
    walking_bus_id = db.Column(db.Integer, db.ForeignKey('walking_bus.id'), nullable=False)
    id = db.Column(db.Integer, primary_key=True)
    participant_id = db.Column(db.Integer, db.ForeignKey('participant.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Boolean, nullable=False)
    is_manual_override = db.Column(db.Boolean, default=False)  # Track if manually set
    
    participant = db.relationship('Participant', backref='calendar_entries')


class WalkingBusSchedule(db.Model):
    walking_bus_id = db.Column(db.Integer, db.ForeignKey('walking_bus.id'), nullable=False)
    id = db.Column(db.Integer, primary_key=True)
    
    # Default times as Python time objects
    DEFAULT_START = time(7, 20)  # 07:20
    DEFAULT_END = time(8, 0)     # 08:00

    monday = db.Column(db.Boolean, default=False)
    monday_start = db.Column(db.Time, nullable=False, default=DEFAULT_START)
    monday_end = db.Column(db.Time, nullable=False, default=DEFAULT_END)
    
    tuesday = db.Column(db.Boolean, default=False)
    tuesday_start = db.Column(db.Time, nullable=False, default=DEFAULT_START)
    tuesday_end = db.Column(db.Time, nullable=False, default=DEFAULT_END)
    
    wednesday = db.Column(db.Boolean, default=False)
    wednesday_start = db.Column(db.Time, nullable=False, default=DEFAULT_START)
    wednesday_end = db.Column(db.Time, nullable=False, default=DEFAULT_END)
    
    thursday = db.Column(db.Boolean, default=False)
    thursday_start = db.Column(db.Time, nullable=False, default=DEFAULT_START)
    thursday_end = db.Column(db.Time, nullable=False, default=DEFAULT_END)
    
    friday = db.Column(db.Boolean, default=False)
    friday_start = db.Column(db.Time, nullable=False, default=DEFAULT_START)
    friday_end = db.Column(db.Time, nullable=False, default=DEFAULT_END)
    
    saturday = db.Column(db.Boolean, default=False)
    saturday_start = db.Column(db.Time, nullable=False, default=DEFAULT_START)
    saturday_end = db.Column(db.Time, nullable=False, default=DEFAULT_END)
    
    sunday = db.Column(db.Boolean, default=False)
    sunday_start = db.Column(db.Time, nullable=False, default=DEFAULT_START)
    sunday_end = db.Column(db.Time, nullable=False, default=DEFAULT_END)


class SchoolHoliday(db.Model):
    __tablename__ = 'school_holidays'
    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    last_update = db.Column(db.Date, nullable=False)


class WalkingBusOverride(db.Model):
    walking_bus_id = db.Column(db.Integer, db.ForeignKey('walking_bus.id'), nullable=False)
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False)
    reason = db.Column(db.String(200), nullable=False)


class DailyNote(db.Model):
    walking_bus_id = db.Column(db.Integer, db.ForeignKey('walking_bus.id'), nullable=False)
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    note = db.Column(db.String(200), nullable=False)


class TempToken(db.Model):
    __tablename__ = 'temp_tokens'
    id = db.Column(db.String(10), primary_key=True)
    expiry = db.Column(db.DateTime, nullable=False)
    walking_bus_id = db.Column(db.Integer, db.ForeignKey('walking_bus.id'), nullable=False)
    walking_bus_name = db.Column(db.String(100), nullable=False)
    bus_password_hash = db.Column(db.String(256), nullable=False)
    created_by = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_pwa_token = db.Column(db.Boolean, default=False)
    token_identifier = db.Column(db.String(64), nullable=True)

    # Add relationship to WalkingBus
    walking_bus = db.relationship('WalkingBus', backref='temp_tokens')


class AuthToken(db.Model):
    __tablename__ = 'auth_tokens'
    
    id = db.Column(db.String(512), primary_key=True)  # The JWT token itself
    walking_bus_id = db.Column(db.Integer, db.ForeignKey('walking_bus.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=get_current_time)
    last_used = db.Column(db.DateTime, default=get_current_time, onupdate=get_current_time)
    expires_at = db.Column(db.DateTime, default=lambda: get_current_time() + timedelta(days=60))
    is_active = db.Column(db.Boolean, default=True)
    client_info = db.Column(db.String(500), nullable=True)
    renewed_from = db.Column(db.String(512), db.ForeignKey('auth_tokens.id'), nullable=True)
    renewed_to = db.Column(db.String(512), db.ForeignKey('auth_tokens.id'), nullable=True)
    invalidated_at = db.Column(db.DateTime, default=None, onupdate=get_current_time)
    invalidation_reason = db.Column(db.String(100))
    token_identifier = db.Column(db.String(64), unique=True, nullable=False)
    is_pwa_installed = db.Column(db.Boolean, default=False)
    pwa_status_updated_at = db.Column(db.DateTime, default=None)
    
    walking_bus = db.relationship('WalkingBus', backref='auth_tokens')

    def invalidate(self, reason):
        self.is_active = False
        self.invalidation_reason = reason
        self.invalidated_at = datetime.now()


class Weather(db.Model):
    __tablename__ = 'weather'
    
    timestamp = db.Column(db.DateTime, primary_key=True)
    forecast_type = db.Column(db.String(10), primary_key=True)
    precipitation = db.Column(db.Float, default=0.0)
    total_precipitation = db.Column(db.Float, nullable=True)
    pop = db.Column(db.Float, nullable=True)
    weather_icon = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=get_current_time)

    def __repr__(self):
        precipitation = (self.precipitation 
                        if self.forecast_type == "minutely" 
                        else self.total_precipitation)
        return (f'<Weather {self.forecast_type} {self.timestamp}: '
                f'{precipitation} mm/h>')


class WeatherCalculation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    walking_bus_id = db.Column(db.Integer, db.ForeignKey('walking_bus.id'), nullable=False)
    date = db.Column(db.Date, nullable=False) 
    icon = db.Column(db.String(50))
    precipitation = db.Column(db.Float)
    pop = db.Column(db.Float)
    calculation_type = db.Column(db.String(20))  # 'minutely' or 'hourly'
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('walking_bus_id', 'date'),)


class PushSubscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token_identifier = db.Column(db.String(64), db.ForeignKey('auth_tokens.token_identifier'), nullable=False)
    endpoint = db.Column(db.String(500), nullable=False)
    p256dh = db.Column(db.String(200), nullable=False)
    auth = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=get_current_time)
    walking_bus_id = db.Column(db.Integer, db.ForeignKey('walking_bus.id'), nullable=False)
    participant_ids = db.Column(db.JSON, nullable=False, default=list)  # Store list of participant IDs
    is_active = db.Column(db.Boolean, default=True)
    paused_at = db.Column(db.DateTime, nullable=True)
    pause_reason = db.Column(db.String(500), nullable=True)
    last_error_code = db.Column(db.Integer, nullable=True)
    
    # Relationships
    auth_token = db.relationship('AuthToken', backref=db.backref('push_subscriptions', lazy=True))
    walking_bus = db.relationship('WalkingBus', backref=db.backref('push_subscriptions', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('token_identifier', 'endpoint', name='uq_subscription_token_endpoint'),
    )


class SchedulerJob(db.Model):
    __tablename__ = 'scheduler_jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    walking_bus_id = db.Column(db.Integer, db.ForeignKey('walking_bus.id'), nullable=False)
    job_id = db.Column(db.String(191), unique=True, nullable=False)
    next_run_time = db.Column(db.DateTime)
    job_type = db.Column(db.String(50))  # e.g., 'notification'
    
    walking_bus = db.relationship('WalkingBus', backref='scheduler_jobs')


class PushNotificationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    walking_bus_id = db.Column(db.Integer, db.ForeignKey('walking_bus.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('push_subscription.id', ondelete='SET NULL'), nullable=True)
    timestamp = db.Column(db.DateTime, default=get_current_time)
    status_code = db.Column(db.Integer, nullable=True)
    error_message = db.Column(db.String(500), nullable=True)
    notification_type = db.Column(db.String(50))  # 'schedule', 'broadcast', etc.
    notification_data = db.Column(db.JSON)
    success = db.Column(db.Boolean, default=False)
    subscription_deleted_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    subscription = db.relationship('PushSubscription', backref='notification_logs')


class WalkingBusRoute(db.Model):
    """Walking Bus Routen für die Registrierungs-App"""
    __tablename__ = 'walking_bus_routes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    route_coordinates = db.Column(db.JSON, nullable=False)  # Array von [lat, lon] Koordinaten
    color = db.Column(db.String(7), default='#3388ff')  # Hex-Farbcode
    is_active = db.Column(db.Boolean, default=True)
    
    # Metadaten
    created_at = db.Column(db.DateTime, default=get_current_time)
    updated_at = db.Column(db.DateTime, default=get_current_time, onupdate=get_current_time)
    
    # Relationship zu Prospects
    prospects = db.relationship('Prospect', backref='walking_bus_route', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'route_coordinates': self.route_coordinates,
            'color': self.color,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'prospect_count': len(self.prospects)
        }


class Prospect(db.Model):
    """Interessenten für Walking Bus Registrierung"""
    __tablename__ = 'prospects'
    
    id = db.Column(db.Integer, primary_key=True)
    child_first_name = db.Column(db.String(100), nullable=False)  # Vorname des Kindes
    child_last_name = db.Column(db.String(100), nullable=False)   # Nachname des Kindes (nur Admin)
    school_class = db.Column(db.String(5), nullable=False)  # z.B. "1A", "2B", "3C", "4D"
    phone = db.Column(db.String(20), nullable=False)
    phone_secondary = db.Column(db.String(20), nullable=True)  # Neue zweite Handynummer
    email = db.Column(db.String(100), nullable=True)
    
    # Geocoding-Daten (nur Koordinaten, keine Klartext-Adresse)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    
    # Walking Bus Route Zuordnung (nullable für "Nur Interesse")
    walking_bus_route_id = db.Column(db.Integer, db.ForeignKey('walking_bus_routes.id'), nullable=True)
    
    # Begleitung-Auswahl
    accompaniment_type = db.Column(db.String(20), nullable=False)  # 'companion' oder 'substitute'
    
    # Metadaten
    created_at = db.Column(db.DateTime, default=get_current_time)
    updated_at = db.Column(db.DateTime, default=get_current_time, onupdate=get_current_time)
    status = db.Column(db.String(20), default='active')  # active, contacted, enrolled, declined
    notes = db.Column(db.Text, nullable=True)
    
    def to_dict(self, include_sensitive=False):
        """
        Gibt Prospect-Daten zurück
        include_sensitive: Wenn True, werden sensible Daten wie Telefon/Email eingeschlossen
        """
        data = {
            'id': self.id,
            'child_first_name': self.child_first_name,
            'school_class': self.school_class,
            'walking_bus_route_id': self.walking_bus_route_id,
            'walking_bus_route_name': self.walking_bus_route.name if self.walking_bus_route else 'Nur Interesse',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'status': self.status,
        }
        
        if include_sensitive:
            data.update({
                'child_last_name': self.child_last_name,  # Nachname nur für Admins
                'phone': self.phone,
                'phone_secondary': self.phone_secondary,
                'email': self.email,
                'accompaniment_type': self.accompaniment_type,
                'latitude': self.latitude,
                'longitude': self.longitude,
                'notes': self.notes
            })
        
        return data

class Route(db.Model):
    __tablename__ = 'routes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default='#FF0000')  # Hex-Farbe
    waypoints = db.Column(db.JSON)  # Liste von [lat, lng] Koordinaten
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'color': self.color,
            'waypoints': self.waypoints,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
