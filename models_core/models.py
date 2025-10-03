# models_core/models.py

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Enum as SqlEnum
from datetime import datetime, timezone, timezone, timedelta
from enum import Enum as PyEnum
from flask_login import UserMixin
# Use shared db instance
from models_core import db
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='accountant')
    full_name = db.Column(db.String(100))
    def __repr__(self):
        return f"<User {self.username}>"
class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text)
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    invoices = db.relationship('Invoice', back_populates='client')  # ← string, not backref
class Invoice(db.Model):
    __tablename__ = 'invoice'

    id = db.Column(db.Integer, primary_key=True)
    document_type = db.Column(db.String(20), default='invoice', nullable=False)
    invoice_number = db.Column(db.String(20), nullable=False)  # Removed unique=True for versioning
    po_number = db.Column(db.String(50))
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    date_created = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    issue_date = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    subtotal = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    vat_amount = db.Column(db.Float, default=0.0)
    vat_rate = db.Column(db.Float, default=16.0)
    status = db.Column(db.String(20), default='Pending')
    signing_person_name = db.Column(db.String(100))
    signing_person_function = db.Column(db.String(100))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    pdf_file = db.Column(db.String(200), nullable=True)  # Will store "generated_pdfs/filename.pdf"
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Versioning
    version = db.Column(db.Integer, default=1, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=True)

    # Relationships
    client = db.relationship('Client', back_populates='invoices')
    items = db.relationship('InvoiceItem', backref='invoice', cascade='all, delete-orphan')
    attachments = db.relationship(
        "Attachment",
        back_populates="parent_invoice",
        foreign_keys="[Attachment.invoice_id]",
        cascade="all, delete-orphan"
    )

    # Self-referential relationships (CORRECTED)
    parent = db.relationship('Invoice', remote_side=[id], back_populates='versions')
    versions = db.relationship('Invoice', back_populates='parent', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Invoice {self.invoice_number} | {self.document_type.upper()} v{self.version}>"

class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    creator = db.relationship('User', backref='created_invoices')
    # ✅ Allow nulls for delivery notes
    unit_price = db.Column(db.Float, nullable=True)
    total_price = db.Column(db.Float, nullable=True)

    comment = db.Column(db.Text)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)

    def __repr__(self):
        return f"<InvoiceItem {self.description[:30]}... x{self.quantity}>"
class CompanySettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.String(50), nullable=False, default="APEX-BNN-001")
    # company_name = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    signature_image_path = db.Column(db.String(500))
    signature_description = db.Column(db.String(255))
    stamp_image_path = db.Column(db.String(500))
    signing_person_name = db.Column(db.String(100))
    signing_person_function = db.Column(db.String(100))
    logo_image_path = db.Column(db.String(500))
    address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    website = db.Column(db.String(255))
def __repr__(self):
        return f"<CompanySettings {self.name}>"


class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact_person = db.Column(db.String(100))
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)

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
    status = db.Column(db.String(50), nullable=False, default="IN_STOCK")
class LocalMarketItem(db.Model):
    __tablename__ = 'local_market_items'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    recent_price = db.Column(db.Numeric(10, 2))
    currency = db.Column(db.String(10))
    source = db.Column(db.String(120))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Bid(db.Model):
    __tablename__ = 'bid'
    id = db.Column(db.Integer, primary_key=True)
    item_description = db.Column(db.String(255), nullable=False)
    our_bid_price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), nullable=False, default='USD')
    estimated_budget = db.Column(db.Float)
    project_type = db.Column(db.String(100))
    location = db.Column(db.String(100))
    status = db.Column(
    SqlEnum('Pending', 'Won', 'Lost', name='bid_status'),
    nullable=False,
    default='Pending'
)
    bid_date = db.Column(db.Date, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    submitted_by = db.Column(db.String(100))

    procurement_item_id = db.Column(db.Integer, db.ForeignKey('procurement_item.id'))
    procurement_item = db.relationship('ProcurementItem', backref='bids')

    competitor_id = db.Column(db.Integer, db.ForeignKey('competitors.id'))
    competitor_bids = db.relationship('CompetitorBid', backref='bid', cascade='all, delete-orphan')


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

class Attachment(db.Model):
    __tablename__ = 'attachments'

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)  # Original filename
    filepath = db.Column(db.String(500), nullable=False)  # Relative or absolute path
    upload_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    description = db.Column(db.Text)

    # Foreign Key to Invoice
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoice.id"), nullable=False)

    # Relationship back to Invoice
    parent_invoice = db.relationship("Invoice", back_populates="attachments", foreign_keys=[invoice_id])

    def __repr__(self):
        return f"<Attachment {self.filename} for Invoice {self.invoice_id}>"
    
class InventoryStatus(PyEnum):
    IN_STOCK = "IN_STOCK"
    LOW_STOCK = "LOW_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    PENDING_RESTOCK = "PENDING_RESTOCK"

class InventoryItem(db.Model):
    __tablename__ = 'inventory_item'

    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(255), nullable=False)
    sku = db.Column(db.String(100), unique=True, nullable=False)
    quantity = db.Column(db.Integer, default=0)
    incoming_quantity = db.Column(db.Integer, default=0)
    reorder_threshold = db.Column(db.Integer, default=10)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    category = db.Column(db.String(100))
    location = db.Column(db.String(100))

    # Use the correct Enum class and a valid default
    status = db.Column(
        db.Enum(InventoryStatus),
        nullable=False,
        default=InventoryStatus.IN_STOCK  # ✅ Use a valid enum member
    )

    last_updated = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=True)
    supplier = db.relationship('Supplier', backref='inventory_items')

    def total_value(self):
        return self.quantity * float(self.unit_price)
# models_core/models.py

# Move this BELOW all model definitions
def get_or_create_company_settings():
    """Get existing company settings or create default one."""
    settings = db.session.execute(db.select(CompanySettings).limit(1)).scalar()
    if not settings:
        settings = CompanySettings(
            name="APEX BNN",
            # company_name="APEX BNN Services",
            company_id="APEX-BNN-001",
            signing_person_name="Authorized Signatory",
            signing_person_function="Finance Manager"
        )
        db.session.add(settings)
        db.session.commit()
        print("✅ Default company settings created.")
    else:
        print("✅ Loaded existing company settings.")
    return settings