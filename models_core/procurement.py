from .base import db
from datetime import datetime, timedelta, timezone

class ProcurementItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'))
    purchase_price = db.Column(db.Float)
    purchase_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    shipping_mode = db.Column(db.String(10), default='sea')
    shipping_cost = db.Column(db.Float, default=0.0)
    total_cost = db.Column(db.Float)
    expected_arrival_date = db.Column(db.DateTime)
    arrival_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='Ordered')
    currency = db.Column(db.String(10), default='USD')

    def calculate_total_cost(self):
        return (self.purchase_price or 0) + (self.shipping_cost or 0)

    def calculate_expected_arrival(self):
        if self.shipping_mode == 'sea':
            return self.purchase_date + timedelta(days=30)
        elif self.shipping_mode == 'air':
            return self.purchase_date + timedelta(days=7)
        else:
            return self.purchase_date + timedelta(days=14)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.total_cost = self.calculate_total_cost()
        self.expected_arrival_date = self.calculate_expected_arrival()
