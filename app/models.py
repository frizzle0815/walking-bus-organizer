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
