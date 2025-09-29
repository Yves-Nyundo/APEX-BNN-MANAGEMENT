from .base import db
from datetime import datetime, timezone
import enum

class InventoryStatus(enum.Enum):
    ACTIVE = "active"
    DISCONTINUED = "discontinued"
    PENDING_RESTOCK = "pending restock"

class InventoryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(255), nullable=False)
    sku = db.Column(db.String(100), unique=True, nullable=False)
    quantity = db.Column(db.Integer, default=0)
    incoming_quantity = db.Column(db.Integer, default=0)
    reorder_threshold = db.Column(db.Integer, default=10)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    category = db.Column(db.String(100))
    location = db.Column(db.String(100))
    status = db.Column(db.Enum(InventoryStatus), default=InventoryStatus.ACTIVE)
    last_updated = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=True)
    supplier = db.relationship('Supplier', backref='inventory_items')

    def total_value(self):
        return self.quantity * self.unit_price
