from .base import db
from datetime import datetime, timezone

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    document_type = db.Column(db.String(20), default='invoice', nullable=False)
    invoice_number = db.Column(db.String(20), unique=True, nullable=False)
    po_number = db.Column(db.String(50))
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    date_created = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    due_date = db.Column(db.DateTime)
    total_amount = db.Column(db.Float, default=0.0)
    vat_amount = db.Column(db.Float, default=0.0)
    vat_rate = db.Column(db.Float, default=16.0)
    status = db.Column(db.String(20), default='Pending')
    signing_person_name = db.Column(db.String(100))
    signing_person_function = db.Column(db.String(100))

    client = db.relationship('Client', backref='invoices')
    items = db.relationship('InvoiceItem', backref='invoice', cascade='all, delete-orphan')
    attachments = db.relationship(
    "Attachment",
    back_populates="parent_invoice",
    foreign_keys="[Attachment.invoice_id]",
    cascade="all, delete-orphan"
)

class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    comment = db.Column(db.Text)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
