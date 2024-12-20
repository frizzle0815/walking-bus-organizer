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
    monday = db.Column(db.Boolean, default=False)
    tuesday = db.Column(db.Boolean, default=False)
    wednesday = db.Column(db.Boolean, default=False)
    thursday = db.Column(db.Boolean, default=False)
    friday = db.Column(db.Boolean, default=False)
    status_today = db.Column(db.Boolean, default=True)  # True = Grün (nimmt teil)
    status_initialized_date = db.Column(db.DateTime)
