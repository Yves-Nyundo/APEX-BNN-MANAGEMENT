from .base import db
from datetime import datetime

class LocalMarketItem(db.Model):
    __tablename__ = 'local_market_items'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    recent_price = db.Column(db.Numeric(10, 2))
    currency = db.Column(db.String(10))
    source = db.Column(db.String(120))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
