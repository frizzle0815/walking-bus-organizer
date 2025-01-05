from . import db


class Station(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)  # Reihenfolge
    participants = db.relationship('Participant', backref='station', lazy=True, order_by='Participant.position')


class Participant(db.Model):
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
    id = db.Column(db.Integer, primary_key=True)
    participant_id = db.Column(db.Integer, db.ForeignKey('participant.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Boolean, nullable=False)
    is_manual_override = db.Column(db.Boolean, default=False)  # Track if manually set
    
    participant = db.relationship('Participant', backref='calendar_entries')


class WalkingBusSchedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    monday = db.Column(db.Boolean, default=False)
    monday_start = db.Column(db.Time, nullable=False, default="07:20")
    monday_end = db.Column(db.Time, nullable=False, default="08:00")
    
    tuesday = db.Column(db.Boolean, default=False)
    tuesday_start = db.Column(db.Time, nullable=False, default="07:20")
    tuesday_end = db.Column(db.Time, nullable=False, default="08:00")
    
    wednesday = db.Column(db.Boolean, default=False)
    wednesday_start = db.Column(db.Time, nullable=False, default="07:20")
    wednesday_end = db.Column(db.Time, nullable=False, default="08:00")
    
    thursday = db.Column(db.Boolean, default=False)
    thursday_start = db.Column(db.Time, nullable=False, default="07:20")
    thursday_end = db.Column(db.Time, nullable=False, default="08:00")
    
    friday = db.Column(db.Boolean, default=False)
    friday_start = db.Column(db.Time, nullable=False, default="07:20")
    friday_end = db.Column(db.Time, nullable=False, default="08:00")
    
    saturday = db.Column(db.Boolean, default=False)
    saturday_start = db.Column(db.Time, nullable=False, default="07:20")
    saturday_end = db.Column(db.Time, nullable=False, default="08:00")
    
    sunday = db.Column(db.Boolean, default=False)
    sunday_start = db.Column(db.Time, nullable=False, default="07:20")
    sunday_end = db.Column(db.Time, nullable=False, default="08:00")


class SchoolHoliday(db.Model):
    __tablename__ = 'school_holidays'
    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    last_update = db.Column(db.Date, nullable=False)


class WalkingBusOverride(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False)
    reason = db.Column(db.String(200), nullable=False)


class DailyNote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    note = db.Column(db.String(200), nullable=False)
