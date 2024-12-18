from . import db

class Station(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    participants = db.relationship('Participant', backref='station', lazy=True)

class Participant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    station_id = db.Column(db.Integer, db.ForeignKey('station.id'), nullable=True)
    monday = db.Column(db.Boolean, default=False)
    tuesday = db.Column(db.Boolean, default=False)
    wednesday = db.Column(db.Boolean, default=False)
    thursday = db.Column(db.Boolean, default=False)
    friday = db.Column(db.Boolean, default=False)
    status_today = db.Column(db.Boolean, default=True)  # True = Grün (nimmt teil)
