from .base import db
from datetime import datetime
from sqlalchemy import Enum

class Bid(db.Model):
    __tablename__ = 'bid'
    id = db.Column(db.Integer, primary_key=True)
    item_description = db.Column(db.String(255), nullable=False)
    our_bid_price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), nullable=False, default='USD')
    estimated_budget = db.Column(db.Float)
    project_type = db.Column(db.String(100))
    location = db.Column(db.String(100))
    status = db.Column(Enum('Pending', 'Won', 'Lost', name='bid_status'), nullable=False, default='Pending')
    bid_date = db.Column(db.Date, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    submitted_by = db.Column(db.String(100))

    procurement_item_id = db.Column(db.Integer, db.ForeignKey('procurement_item.id'))
    procurement_item = db.relationship('ProcurementItem', backref='bids')

    competitor_id = db.Column(db.Integer, db.ForeignKey('competitors.id'))
    competitor_bids = db.relationship('CompetitorBid', backref='bid', cascade='all, delete-orphan')
