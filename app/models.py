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
    tuesday = db.Column(db.Boolean, default=False)
    wednesday = db.Column(db.Boolean, default=False)
    thursday = db.Column(db.Boolean, default=False)
    friday = db.Column(db.Boolean, default=False)
    saturday = db.Column(db.Boolean, default=False)
    sunday = db.Column(db.Boolean, default=False)


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
