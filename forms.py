# models_core/forms.py

from flask_wtf import FlaskForm, Form
from wtforms import (
    StringField, PasswordField, SubmitField, IntegerField,
    DecimalField, TextAreaField, BooleanField, SelectField,
    DateField, FloatField, FormField, FieldList, HiddenField, ValidationError,validators
)
from wtforms.validators import DataRequired, Optional, NumberRange, Length, Email, URL
from wtforms_sqlalchemy.fields import QuerySelectField
from models_core import Supplier, InventoryStatus, Client
from datetime import date

from flask_babel import lazy_gettext as _
class MyForm(FlaskForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from models_core.models import Supplier, Client
        self.supplier.choices = [(s.id, s.name) for s in Supplier.query.all()]

def get_inventory_status_choices():
    return [
        (InventoryStatus.IN_STOCK.name, "In Stock"),
        (InventoryStatus.LOW_STOCK.name, "Low Stock"),
        (InventoryStatus.OUT_OF_STOCK.name, "Out of Stock"),
        (InventoryStatus.PENDING_RESTOCK.name, "Pending Restock")
    ]
class CompanySettingsForm(FlaskForm):
    name = StringField('Company Name', validators=[DataRequired()])
    company_id = StringField('Company ID', validators=[DataRequired()])
    address = TextAreaField('Address', validators=[DataRequired()])
    phone = StringField('Phone', validators=[Optional()])
    email = StringField('Email', validators=[Optional(), Email()])
    website = StringField(
        'Website',
        validators=[Optional(), URL(require_tld=True, message="Enter a valid website URL (e.g., https://example.com)")],
        render_kw={"placeholder": "https://www.yourcompany.com"}
    )
    signing_person_name = StringField('Signing Person Name', validators=[Optional()])
    signing_person_function = StringField('Function / Title', validators=[Optional()])

    submit = SubmitField('Save Settings')
# -------------------
# Authentication Forms
# -------------------
class CreateUserForm(FlaskForm):
    full_name = StringField('Full Name')
    username = StringField('Username', [validators.InputRequired()])
    password = PasswordField('Password', [validators.InputRequired()])
    role = SelectField('Role', choices=[('accountant', 'Accountant'), ('admin', 'Admin')])

class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


# -------------------
# Inventory Forms
# -------------------
def supplier_choices():
    return Supplier.query.all()

class InventoryItemForm(FlaskForm):
    name = StringField("Product/Service *", validators=[DataRequired(), Length(max=100)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=500)])
    category = StringField("Category", validators=[Optional(), Length(max=50)])
    currency = StringField("Currency", validators=[DataRequired(), Length(min=3, max=3)])

    quantity_on_hand = IntegerField("Quantity on Hand", validators=[Optional(), NumberRange(min=0)])
    reorder_point = IntegerField("Reorder Point", validators=[Optional(), NumberRange(min=0)])
    unit_cost = DecimalField("Unit Cost ($)", validators=[Optional(), NumberRange(min=0)], places=2)
    standard_price = DecimalField("Standard Price ($)", validators=[Optional(), NumberRange(min=0)], places=2)
    cogs = DecimalField("COGS ($)", validators=[Optional(), NumberRange(min=0)], places=2)

    is_active = BooleanField("Is Active", default=True)
    status = SelectField("Status", choices=[(status.name, status.value) for status in InventoryStatus])
    supplier = QuerySelectField("Supplier", query_factory=supplier_choices, allow_blank=True, get_label="name")

    submit = SubmitField("Add Item")


# -------------------
# CRUD Forms
# -------------------
class DeleteItemForm(FlaskForm):
    submit = SubmitField("Delete")


class LocalMarketForm(FlaskForm):
    name = StringField("Item Name", validators=[DataRequired()])
    recent_price = DecimalField("Recent Price", places=2, validators=[Optional()])
    description = TextAreaField("Description", validators=[Optional()])
    currency = SelectField("Currency", choices=[("USD", "USD"), ("CDF", "CDF")], validators=[Optional()])
    source = StringField("Source", validators=[Optional()])


class CompetitorFilterForm(FlaskForm):
    search = StringField("Search", render_kw={"placeholder": "Search by name or industry"})
    sector = SelectField("Industry/Sector", choices=[], default="", render_kw={"class": "form-select"})
    location = SelectField("Location", choices=[], default="", render_kw={"class": "form-select"})
    min_bids = IntegerField("Min Bids")
    max_bids = IntegerField("Max Bids")
    status = SelectField("Status", choices=[("", "All"), ("Submitted", "Submitted"), ("Shortlisted", "Shortlisted")])
    submit = SubmitField("Filter", render_kw={"class": "bg-blue-600 text-white px-4 py-2 rounded"})


class CompetitorForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    bid_amount = DecimalField("Bid Amount", validators=[Optional()])
    bid_id = IntegerField("Bid ID", validators=[Optional()])
    bid_count = IntegerField("Bid Count", validators=[Optional()])
    sector = StringField("Sector", validators=[Optional()])
    location = StringField("Location", validators=[Optional()])
    contact_email = StringField("Contact Email", validators=[Optional(), Email()])
    website = StringField("Website", validators=[Optional()])
    status = SelectField("Status", choices=[
        ("Submitted", "Submitted"),
        ("Shortlisted", "Shortlisted"),
        ("Rejected", "Rejected")
    ], validators=[Optional()])
    submit = SubmitField("Add Competitor")


class ProductForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    description = StringField("Description", validators=[Optional()])
    category = StringField("Category", validators=[Optional()])
    currency = StringField("Currency", default="USD")
    standard_price = DecimalField("Standard Price", validators=[Optional()])
    cogs = DecimalField("COGS", validators=[Optional()])
    is_active = BooleanField("Is Active")


class ProcurementForm(FlaskForm):
    name = StringField("Item Name", validators=[DataRequired()])
    supplier_id = SelectField("Supplier", coerce=int, validators=[DataRequired()])
    purchase_price = DecimalField("Purchase Price", places=2, validators=[DataRequired()])
    shipping_cost = DecimalField("Shipping Cost", places=2, validators=[Optional()])
    currency = StringField("Currency", default="USD")
    shipping_mode = SelectField("Shipping Mode", choices=[("sea", "Sea"), ("air", "Air"), ("land", "Land")])
    purchase_date = DateField("Purchase Date", format="%Y-%m-%d", validators=[DataRequired()])
    status = SelectField("Status", choices=[
        ("Ordered", "Ordered"),
        ("Shipped", "Shipped"),
        ("Delivered", "Delivered"),
        ("Delayed", "Delayed")
    ])


class SupplierForm(FlaskForm):
    name = StringField("Supplier Name", validators=[DataRequired()])
    contact_person = StringField("Contact Person", validators=[Optional()])
    email = StringField("Email", validators=[Optional(), Email()])
    phone = StringField("Phone", validators=[Optional()])
    address = StringField("Address", validators=[Optional()])
    submit = SubmitField("Add Supplier")


class ClientForm(FlaskForm):
    name = StringField("Client Name", validators=[DataRequired()])
    email = StringField("Email", validators=[Optional(), Email()])
    phone = StringField("Phone", validators=[Optional()])
    address = StringField("Address", validators=[Optional()])
    submit = SubmitField("Add Client")


class BidForm(FlaskForm):
    item_description = StringField("Item Description", validators=[DataRequired()])
    our_bid_price = FloatField("Our Bid Price", validators=[DataRequired()])
    currency = SelectField("Currency", choices=[
        ("USD", "USD"),
        ("EUR", "EUR"),
        ("CDF", "CDF"),
        ("ZAR", "ZAR")
    ], default="USD", validators=[DataRequired()])
    estimated_budget = FloatField("Estimated Budget", validators=[Optional()])
    project_type = StringField("Project Type", validators=[Optional()])
    location = StringField("Location", validators=[Optional()])
    status = SelectField("Status", choices=[
        ("Pending", "Pending"),
        ("Won", "Won"),
        ("Lost", "Lost")
    ], default="Pending", validators=[DataRequired()])
    bid_date = DateField("Bid Date", format="%Y-%m-%d", validators=[DataRequired()])
    submitted_by = StringField("Submitted By", validators=[Optional()])


class InventoryForm(FlaskForm):
    product_name = StringField("Product Name", validators=[DataRequired()])
    sku = StringField("SKU", validators=[DataRequired()])
    quantity = IntegerField("Quantity", validators=[NumberRange(min=0)])
    incoming_quantity = IntegerField("Incoming Quantity", validators=[NumberRange(min=0)])
    reorder_threshold = IntegerField("Reorder Threshold", validators=[NumberRange(min=0)])
    unit_price = DecimalField("Unit Price", validators=[NumberRange(min=0)])
    category = StringField("Category")
    location = StringField("Location")
    status = SelectField("Status", choices=[(status.name, status.value) for status in InventoryStatus])
    supplier = QuerySelectField("Supplier", query_factory=supplier_choices, allow_blank=True, get_label="name")

class InvoiceItemForm(Form):
    description = StringField("Description", validators=[DataRequired()])
    quantity = DecimalField("Quantity", validators=[DataRequired(), NumberRange(min=1)])
    unit_price = DecimalField(
        "Unit Price",
        default=0,
        validators=[Optional(), NumberRange(min=0)]
    )
    comment = StringField("Comment")
    status = SelectField(
        "Status",
        choices=get_inventory_status_choices(),
        validators=[DataRequired()],
        default=InventoryStatus.IN_STOCK.name
    )
    # status = SelectField("Status", validators=[DataRequired()])
    submit = SubmitField("Add Item")



class GenerateDocumentForm(FlaskForm):
    document_type = HiddenField("Document Type", default="invoice")

    # Client selection
    client = SelectField("Client", coerce=int, validators=[DataRequired()])
    client_address = StringField("Client Address")  # Optional display-only
    po_number = StringField("PO Number")
    
    # Dates
    issue_date = DateField(
        _("Issue Date"),
        default=date.today,
        format='%Y-%m-%d',
        validators=[DataRequired()]
    )
    due_date = DateField(
        _("Due Date"),
        format='%Y-%m-%d',
        validators=[Optional()]  # Let custom validator handle conditionals
    )

    # Signing info
    signing_person_name = StringField(
        _("Signing Person Name"),
        validators=[DataRequired()]
    )
    signing_person_function = StringField(
        _("Signing Person Function"),
        validators=[DataRequired()]
    )

    # VAT (optional by type)
    vat_rate = DecimalField(
        _("VAT Rate (%)"),
        default=0.0,
        validators=[Optional(), NumberRange(min=0, max=100)]
    )

    # Line items
    items = FieldList(FormField(InvoiceItemForm), min_entries=1)
    submit = SubmitField(_("Generate Document"))

    def validate_due_date(self, field):
        """Require due_date only for invoices and proformas."""
        doc_type = (self.document_type.data or "").strip().lower()
        if doc_type in ("invoice", "proforma", "proforma_invoice"):
            if not field.data:
                raise ValidationError(_("Due date is required for invoices and proformas."))

    def validate_vat_rate(self, field):
        """VAT rate must be valid for invoices/proformas."""
        doc_type = (self.document_type.data or "").strip().lower()
        if doc_type not in ("delivery_note",):
            if field.data is None or field.data < 0:
                raise ValidationError(_("VAT rate must be 0 or higher for invoices and proformas."))

    def validate_items(self, field):
        """Validate item-level rules per document type."""
        doc_type = (self.document_type.data or "").strip().lower()
        for i, item in enumerate(field):
            f = item.form
            desc = (f.description.data or "").strip()
            qty = f.quantity.data

            # Always require description and positive quantity
            if not desc:
                f.description.errors.append(_("Description is required."))
            if qty is None or qty <= 0:
                f.quantity.errors.append(_("Quantity must be greater than 0."))

            # Unit price required only for non-delivery notes
            if doc_type != "delivery_note":
                unit_price = f.unit_price.data or 0.0
                if unit_price < 0:
                    f.unit_price.errors.append(_("Unit price cannot be negative."))