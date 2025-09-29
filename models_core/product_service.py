from .base import db

class OurProductService(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    standard_price = db.Column(db.Float)
    currency = db.Column(db.String(3), default='USD')
    cogs = db.Column(db.Float)
    category = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    quantity_on_hand = db.Column(db.Integer)
    reorder_point = db.Column(db.Integer)
    unit_cost = db.Column(db.Float)
