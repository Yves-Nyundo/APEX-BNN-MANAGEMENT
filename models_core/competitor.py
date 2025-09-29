from .base import db

class Competitor(db.Model):
    __tablename__ = 'competitors'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    sector = db.Column(db.String(100))
    location = db.Column(db.String(100))
    contact_email = db.Column(db.String(120))
    website = db.Column(db.String(255))
    bids = db.relationship('Bid', backref='competitor', lazy='dynamic')
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

class CompetitorBid(db.Model):
    __tablename__ = 'competitor_bid'
    id = db.Column(db.Integer, primary_key=True)
    competitor_name = db.Column(db.String(100), nullable=False)
    bid_price = db.Column(db.Float, nullable=False)
    notes = db.Column(db.String(255))
    bid_id = db.Column(db.Integer, db.ForeignKey('bid.id'), nullable=False)
