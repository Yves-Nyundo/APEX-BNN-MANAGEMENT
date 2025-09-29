
from .base import db
from datetime import datetime, timezone
class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(500), nullable=False)
    upload_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
   
    description = db.Column(db.Text)
    # invoice = db.relationship('Invoice', backref='attachments')
    parent_invoice = db.relationship("Invoice", back_populates="attachments")
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoice.id"), nullable=False)

    parent_invoice = db.relationship(
    "Invoice",
    back_populates="attachments",
    foreign_keys=[invoice_id]
)
