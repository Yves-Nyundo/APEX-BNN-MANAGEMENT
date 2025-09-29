from .base import db

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text)
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
