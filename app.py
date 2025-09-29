# app.py - APEX BNN Services Management App
# Refactored for correctness, safety, and modularity — all logic preserved.
import sys
print("🔍 sys.path =", sys.path)
print("📦 sys.modules keys:", [k for k in sys.modules.keys() if 'model' in k])
from reportlab.lib.utils import ImageReader
import os
import csv
import base64
from flask_login import current_user
import logging
from datetime import datetime, timezone, timedelta
from io import BytesIO, StringIO
from functools import wraps  # Required for @wraps(f)
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from decimal import Decimal,ROUND_HALF_UP
from datetime import datetime, timezone

# Flask & Extensions
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file,
    send_from_directory,
    session,
    abort,
    Response,
    jsonify,
    current_app,
    
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_login import login_user,LoginManager,logout_user,login_required,current_user
from flask_bcrypt import Bcrypt
from wtforms.validators import DataRequired, Optional, NumberRange
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func, extract, Enum as SqlEnum,text
from flask_wtf import Form
from zoneinfo import ZoneInfo
from sqlalchemy import select,delete,update, func, or_, and_
from dotenv import load_dotenv
load_dotenv()

# App-level: Use shared db and create_app from models_core
from models_core.config import Config
from models_core import db
from models_core import create_app,create_default_admin
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from io import BytesIO
from reportlab.lib.colors import Color, black
from flask import request, Response, jsonify, flash, redirect, render_template


# ✅ Explicitly get FLASK_ENV, default to 'production'
env = os.getenv('FLASK_ENV', 'production')
print(f"🌐 Using FLASK_ENV: {env}")  # Debug print

# Initialize app using factory
app = create_app(env)  # This calls db.init_app(app) internally
print("🔧 Environment:", app.config.get("ENV"))
print("📦 DB URI:", app.config.get("SQLALCHEMY_DATABASE_URI"))
# Initialize extensions
csrf = CSRFProtect(app)
bcrypt = Bcrypt(app)

# Ensure upload folders exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'attachments'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'company'), exist_ok=True)


# === Import models and initialize database ===
with app.app_context():
    # 🔴 Import all models INSIDE app context, so db recognizes them
    from models_core.models import (
        User,
        Client,
        Invoice,
        InvoiceItem,
        Supplier,
        ProcurementItem,
        OurProductService,
        LocalMarketItem,
        Competitor,
        Bid,
        CompetitorBid,
        CompanySettings,
        Attachment,
        InventoryItem,
        get_or_create_company_settings,
        
    )



# Import forms
from forms import (
    LoginForm,
    ClientForm,
    SupplierForm,
    ProcurementForm,
    ProductForm,
    BidForm,
    CompetitorForm,
    LocalMarketForm,
    InventoryItemForm,
    DeleteItemForm,
    CompetitorFilterForm,
    InvoiceItemForm,
    GenerateDocumentForm,
    CreateUserForm,
)

from flask_babel import Babel
from utils.pdf_generator import generate_invoice_pdf
# ========================
# Utility Functions
# ========================



def safe_decimal(val, default='0'):
    if val is None or val == '' or val == 'None':
        return Decimal(default)
    try:
        return Decimal(str(val))
    except Exception as e:
        print(f"⚠️ Failed to convert '{val}' to Decimal: {e}")
        return Decimal(default)

def get_lowest_competitor(bid):
    return min(bid.competitor_bids, key=lambda c: c.bid_price, default=None)

def is_price_too_high(bid, threshold=0.15):
    lowest = get_lowest_competitor(bid)
    if not lowest:
        return False
    return bid.our_bid_price > lowest.bid_price * (1 + threshold)

def get_top_competitors():
    return db.session.query(
        CompetitorBid.competitor_name,
        func.count(CompetitorBid.id).label('bid_count'),
        func.avg(CompetitorBid.bid_price).label('avg_price')
    ).group_by(CompetitorBid.competitor_name).order_by(func.count(CompetitorBid.id).desc()).limit(10).all()

def get_monthly_summary():
    one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
    summary = db.session.query(
        extract('year', Invoice.date_created).label('year'),
        extract('month', Invoice.date_created).label('month'),
        func.sum(Invoice.total_amount).label('revenue'),
        func.sum(Invoice.vat_amount).label('vat_collected')
    ).filter(
        Invoice.status == 'Paid',
        Invoice.document_type == 'invoice',
        Invoice.date_created >= one_year_ago
    ).group_by('year', 'month').order_by('year', 'month').all()
    return summary

def get_inventory_alerts():
    items = OurProductService.query.all()
    low_stock = [i for i in items if i.quantity_on_hand and i.reorder_point and 0 < i.quantity_on_hand <= i.reorder_point]
    out_of_stock = [i for i in items if i.quantity_on_hand == 0]
    return items, low_stock, out_of_stock

def get_bid_data(status_filter, currency_filter):
    query = Bid.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    if currency_filter:
        query = query.filter_by(currency=currency_filter)
    return query.all()
babel = Babel(app)
def ensure_directories():
    """Create necessary directories if they don't exist."""
    dirs = [
        app.config['UPLOAD_FOLDER'],
        os.path.join(app.config['UPLOAD_FOLDER'], 'company'),
        os.path.join(app.config['UPLOAD_FOLDER'], 'attachments')
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
# pdf_utils.py
def get_item_initials(description):
    """
    Generate initials from item description.
    Example: 'Iphone 15 Pro' → 'I15P'
    """
    if not description:
        return "ITEM"
    
    words = description.strip().split()
    initials = ""

    for word in words:
        # If word starts with letter, take first letter
        if word[0].isalpha():
            initials += word[0]
        # If word is number, include whole number (e.g., 15)
        elif word[0].isdigit():
            digits = ''.join(c for c in word if c.isdigit())
            if digits:
                initials += digits

    return initials.upper()[:10]  # Max length 10



# def generate_doc_number(doc_type, items):
#     # Get initials from first item
#     item_desc = items[0]['description'] if items else ""
#     initials = get_item_initials(item_desc)

#     # Map document type
#     prefix_map = {
#         'invoice': 'INV',
#         'proforma': 'PROF',
#         'delivery_note': 'DELIV'
#     }
#     doc_prefix = prefix_map.get(doc_type, 'DOC')

#     # Format month/year: SEP25
#     month_year = datetime.now().strftime('%b%y').upper()  # e.g., SEP25

#     return f"APEX-{doc_prefix}-{initials}-{month_year}"



def generate_doc_number(document_type, items_data):
    """
    Generate document number like: APEX-INV-I15P-SEP25-001
    Format: APEX-{TYPE}-{PRODUCT}-{DAY}-{DAILY_SEQ}
    """
    prefixes = {
        'invoice': 'INV',
        'proforma': 'PROF',
        'delivery_note': 'DN'
    }
    prefix = prefixes.get(document_type.lower(), 'DOC')

    # Use first item's description to get product code
    if items_data:
        first_desc = items_data[0]['description'].upper()
        words = first_desc.replace('-', ' ').split()
        product_code = ''.join([w[0] + w[-1] if len(w) > 1 else w[0] for w in words])[:4].upper()
    else:
        product_code = "GEN"

    # Get today's day suffix (e.g., SEP25)
    now = datetime.now()
    day_suffix = now.strftime("%b%y").upper()  # e.g., SEP25

    # Count how many documents of this type were created today
    start_of_day = datetime(now.year, now.month, now.day)
    daily_count = db.session.query(Invoice).filter(
        Invoice.document_type == document_type,
        Invoice.created_at >= start_of_day
    ).count()

    # Increment by 1
    seq_num = f"{daily_count + 1:03d}"  # → 001, 002...

    # Final number
    doc_number = f"APEX-{prefix}-{product_code}-{day_suffix}-{seq_num}"

    return doc_number

# ========================
# Authentication & Decorators
# ========================


def role_required(roles):
    def decorator(f):
        @wraps(f)
        @login_required  # ← Add this here!
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles:
                flash("You don't have permission to access this page.", "error")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data
        user = User.query.filter_by(username=username).first()

        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)  # ← This replaces session['user_id']
            flash(f"Welcome, {user.full_name}!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password.", "error")
    return render_template('auth/login.html', form=form)

@app.route('/logout')
def logout():
    logout_user()  # Clears Flask-Login session
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))


@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/test_bytesio')
def test_bytesio():
    from io import BytesIO
    buf = BytesIO()
    buf.write(b"Hello")
    print("✅ BytesIO works:", buf.getvalue())
    return "BytesIO test passed"
# ========================
# User Management (Admin Only)
# ========================

@app.route('/users/add', methods=['GET', 'POST'])
@login_required
@role_required(['admin'])
def add_user():
    form = CreateUserForm()
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            password = request.form.get('password')
            role = request.form.get('role')
            full_name = request.form.get('full_name')
            if not username or not password or not role:
                flash("Username, password, and role are required.", "error")
                return render_template('users/add.html', roles=['admin', 'accountant'])
            if User.query.filter_by(username=username).first():
                flash("Username already exists.", "error")
                return render_template('users/add.html', roles=['admin', 'accountant'])
            hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
            new_user = User(username=username, password=hashed_pw, role=role, full_name=full_name)
            db.session.add(new_user)
            db.session.commit()
            flash(f"User '{username}' created successfully.", "success")
            return redirect(url_for('list_users'))
        except Exception as e:
            db.session.rollback()
            print(f"Error creating user: {e}")
            flash("An error occurred while creating the user.", "error")
            return render_template('users/add.html', roles=['admin', 'accountant'])
    return render_template('users/add.html', roles=['admin', 'accountant'], form=form)


@app.route('/users')
@login_required
@role_required(['admin'])
def list_users():
    try:
        users = User.query.all()
        return render_template('users/list.html', users=users)
    except Exception as e:
        print(f"Error fetching users: {e}")
        flash("An error occurred while loading users.", "error")
        return "An error occurred.", 500


# ========================
# Context Processors
# ========================

# @app.context_processor
# def inject_user():
#     user = None
#     if 'user_id' in session:
#         try:
#             user = db.session.get(User, session['user_id'])
#         except Exception as e:
#             print(f"Error fetching user: {e}")
#     return {'current_user': user}


@app.context_processor
def inject_datetime():
    return {'datetime': datetime, 'now': datetime.now}


# ========================
# Dashboard
# ========================

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        now = datetime.now(timezone.utc)
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        pending_invoices = Invoice.query.filter_by(status='Pending', document_type='invoice').count()
        total_revenue = db.session.query(func.sum(Invoice.total_amount)).filter_by(status='Paid', document_type='invoice').scalar() or 0.0
        overdue_invoices = Invoice.query.filter_by(status='Overdue', document_type='invoice').count()
        pending_proformas = Invoice.query.filter_by(status='Pending', document_type='proforma').count()
        pending_delivery_notes = Invoice.query.filter_by(document_type='delivery_note').count()
        recent_documents = Invoice.query.order_by(Invoice.date_created.desc()).limit(10).all()
        recent_activity_count = Invoice.query.filter(Invoice.date_created >= now - timedelta(days=7)).count()

        top_client = db.session.query(Client.name, func.sum(Invoice.total_amount)).join(Invoice).filter(Invoice.status == 'Paid').group_by(Client.id).order_by(func.sum(Invoice.total_amount).desc()).first()
        top_client_name = top_client[0] if top_client else "N/A"
        top_client_amount = top_client[1] if top_client else 0.0
        avg_invoice_value = db.session.query(func.avg(Invoice.total_amount)).filter_by(document_type='invoice').scalar() or 0.0
        total_suppliers = Supplier.query.count()
        pending_procurements = ProcurementItem.query.filter_by(status='Ordered').count()
        total_bids = Bid.query.count()
        pending_bids = Bid.query.filter_by(status='Pending').count()

        monthly_summary = get_monthly_summary()
        monthly_labels = [f"{row.year}-{row.month:02d}" for row in monthly_summary]
        monthly_revenue = [float(row.revenue) for row in monthly_summary]
        monthly_vat_data = [float(row.vat_collected) for row in monthly_summary]
        monthly_vat = db.session.query(func.sum(Invoice.vat_amount)).filter(
            Invoice.status == 'Paid',
            Invoice.document_type == 'invoice',
            Invoice.date_created >= start_of_month
        ).scalar() or 0.0

        inventory_items, low_stock_items, out_of_stock_items = get_inventory_alerts()
        status_filter = request.args.get('status')
        currency_filter = request.args.get('currency')
        bids = get_bid_data(status_filter, currency_filter)
        top_competitors = get_top_competitors()

        return render_template('dashboard.html',
            pending_invoices=pending_invoices,
            total_revenue=total_revenue,
            overdue_invoices=overdue_invoices,
            pending_proformas=pending_proformas,
            pending_delivery_notes=pending_delivery_notes,
            recent_documents=recent_documents,
            recent_activity_count=recent_activity_count,
            top_client_name=top_client_name,
            top_client_amount=top_client_amount,
            avg_invoice_value=avg_invoice_value,
            total_suppliers=total_suppliers,
            pending_procurements=pending_procurements,
            total_bids=total_bids,
            pending_bids=pending_bids,
            inventory_items=inventory_items,
            low_stock_items=low_stock_items,
            out_of_stock_items=out_of_stock_items,
            monthly_vat=monthly_vat,
            monthly_labels=monthly_labels,
            monthly_revenue=monthly_revenue,
            monthly_vat_data=monthly_vat_data,
            bids=bids,
            top_competitors=top_competitors,
            get_lowest_competitor=get_lowest_competitor,
            is_price_too_high=is_price_too_high,
            status_filter=status_filter,
            currency_filter=currency_filter
        )
    except Exception as e:
        print(f"Error fetching dashboard: {e}")
        flash("An error occurred while loading the dashboard.", "error")
        return "An error occurred.", 500


# ========================
# Dashboard API Routes
# ========================

@app.route('/api/monthly_revenue')
@login_required
def api_monthly_revenue():
    now = datetime.now(timezone.utc)
    start_of_month = now.replace(day=1)
    data = db.session.query(
        extract('month', Invoice.date_created).label('month'),
        func.sum(Invoice.total_amount).label('revenue')
    ).filter(
        Invoice.status == 'Paid',
        Invoice.document_type == 'invoice',
        extract('year', Invoice.date_created) == now.year,
        Invoice.date_created >= start_of_month
    ).group_by('month').order_by('month').all()
    return {'labels': [row[0] for row in data], 'values': [float(row[1]) for row in data]}

@app.route('/api/client/<int:client_id>')
@login_required
def api_client(client_id):
    client = db.session.get(Client, client_id)
    if not client:
        # Instead of abort(404), return empty info
        return jsonify({'email': '', 'phone': '', 'address': ''}), 200
    return jsonify({
        'email': client.email or '',
        'phone': client.phone or '',
        'address': client.address or ''
    })

@app.route('/api/top_clients')
@login_required
def api_top_clients():
    top_client = db.session.query(Client.name, func.sum(Invoice.total_amount)) \
        .join(Invoice).filter(Invoice.status == 'Paid') \
        .group_by(Client.id).order_by(func.sum(Invoice.total_amount).desc()).first()
    return {
        'client': top_client[0] if top_client else 'N/A',
        'amount': float(top_client[1]) if top_client else 0.0
    }
@app.route('/api/document_type_distribution')
@login_required
def api_document_type_distribution():
    data = db.session.query(
        Invoice.document_type,
        func.count(Invoice.id).label('count')
    ).filter(
        Invoice.document_type.in_(['invoice', 'proforma', 'delivery_note'])
    ).group_by(Invoice.document_type).all()
    return jsonify({
        'labels': [row.document_type.title() for row in data],
        'data': [row.count for row in data]
    })

# ========================
# Export Routes
# ========================

@app.route('/dashboard/export')
@login_required
def export_bids():
    bids = Bid.query.all()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Item Description', 'Our Price', 'Currency', 'Status', 'Bid Date'])
    for bid in bids:
        cw.writerow([bid.item_description, bid.our_bid_price, bid.currency, bid.status, bid.bid_date])
    output = si.getvalue()
    return Response(output, mimetype='text/csv', headers={"Content-Disposition": "attachment;filename=bids.csv"})


@app.route('/dashboard/export_inventory')
@login_required
def export_inventory():
    items = InventoryItem.query.all()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["SKU", "Product", "Quantity", "Incoming", "Reorder", "Category", "Location", "Status", "Supplier", "Last Updated"])
    for item in items:
        cw.writerow([
            item.sku, item.product_name, item.quantity, item.incoming_quantity,
            item.reorder_threshold, item.category, item.location,
            item.status.value if hasattr(item.status, 'value') else item.status,
            item.supplier.name if item.supplier else "",
            item.last_updated.strftime("%Y-%m-%d %H:%M")
        ])
    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=inventory.csv"})


# ========================
# Clients
# ========================

@app.route('/clients')
@login_required
def list_clients():
    delete_form = DeleteItemForm()
    clients = Client.query.all()
    return render_template('clients/list.html', clients=clients, delete_form=delete_form)


@app.route('/clients/add', methods=['GET', 'POST'])
@login_required
@role_required(['accountant', 'admin'])
def add_client():
    form = ClientForm()
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            email = request.form.get('email', '').strip()
            address = request.form.get('address', '').strip()
            phone = request.form.get('phone', '').strip()
            if not name:
                flash("Client name is required.", "error")
                return render_template('clients/add.html')
            client = Client(name=name, email=email, address=address, phone=phone)
            db.session.add(client)
            db.session.commit()
            flash(f"Client '{name}' added successfully.", "success")
            return redirect(url_for('list_clients'))
        except Exception as e:
            db.session.rollback()
            print(f"Error adding client: {e}")
            flash("An error occurred while adding the client.", "error")
    return render_template('clients/add.html', form=form)


@app.route('/clients/edit/<int:client_id>', methods=['GET', 'POST'])
@login_required
@role_required(['accountant', 'admin'])
def edit_client(client_id):
    client = Client.query.get_or_404(client_id)
    form = ClientForm(obj=client)
    if request.method == 'POST':
        try:
            client.name = request.form.get('name')
            client.email = request.form.get('email', '').strip()
            client.address = request.form.get('address', '').strip()
            client.phone = request.form.get('phone', '').strip()
            if not client.name:
                flash("Client name is required.", "error")
                return render_template('clients/edit.html',form=form, client=client)
            db.session.commit()
            flash(f"Client '{client.name}' updated successfully.", "success")
            return redirect(url_for('list_clients'))
        except Exception as e:
            db.session.rollback()
            print(f"Error updating client: {e}")
            flash("An error occurred while updating the client.", "error")
    return render_template('clients/edit.html',form=form, client=client)


@app.route('/clients/delete/<int:client_id>', methods=['POST'])
@login_required
@role_required(['admin'])
def delete_client(client_id):
    delete_form = DeleteItemForm()
    client = Client.query.get_or_404(client_id)
    try:
        db.session.delete(client)
        db.session.commit()
        flash(f"Client '{client.name}' deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting client: {e}")
        flash("An error occurred while deleting the client.", "error")
    return redirect(url_for('list_clients', delete_form=delete_form))


# ========================
# Suppliers
# ========================

@app.route('/suppliers')
@login_required
def list_suppliers():
    delete_form = DeleteItemForm()
    suppliers = Supplier.query.all()
    return render_template('suppliers/list.html', suppliers=suppliers, delete_form=delete_form)


@app.route('/suppliers/add', methods=['GET', 'POST'])
@login_required
@role_required(['accountant', 'admin'])
def add_supplier():
    form=SupplierForm()
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            contact_person = request.form.get('contact_person', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            address = request.form.get('address', '').strip()
            if not name:
                flash("Supplier name is required.", "error")
                return render_template('suppliers/add.html')
            supplier = Supplier(name=name, contact_person=contact_person, email=email, phone=phone, address=address)
            db.session.add(supplier)
            db.session.commit()
            flash(f"Supplier '{name}' added successfully.", "success")
            return redirect(url_for('list_suppliers'))
        except Exception as e:
            db.session.rollback()
            print(f"Error adding supplier: {e}")
            flash("An error occurred while adding the supplier.", "error")
    return render_template('suppliers/add.html', form=form)


@app.route('/suppliers/edit/<int:supplier_id>', methods=['GET', 'POST'])
@login_required
@role_required(['accountant', 'admin'])
def edit_supplier(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    if request.method == 'POST':
        try:
            supplier.name = request.form.get('name')
            supplier.contact_person = request.form.get('contact_person', '').strip()
            supplier.email = request.form.get('email', '').strip()
            supplier.phone = request.form.get('phone', '').strip()
            supplier.address = request.form.get('address', '').strip()
            if not supplier.name:
                flash("Supplier name is required.", "error")
                return render_template('suppliers/edit.html', supplier=supplier)
            db.session.commit()
            flash(f"Supplier '{supplier.name}' updated successfully.", "success")
            return redirect(url_for('list_suppliers'))
        except Exception as e:
            db.session.rollback()
            print(f"Error updating supplier: {e}")
            flash("An error occurred while updating the supplier.", "error")
    return render_template('suppliers/edit.html', supplier=supplier)


@app.route('/suppliers/delete/<int:supplier_id>', methods=['POST'])
@login_required
@role_required(['admin'])
def delete_supplier(supplier_id):
    form = DeleteItemForm()
    supplier = Supplier.query.get_or_404(supplier_id)
    if form.validate_on_submit() and form.confirm.data == 'yes':
        try:
            db.session.delete(supplier)
            db.session.commit()
            flash(f"🗑️ Supplier '{supplier.name}' deleted successfully.", "success")
        except Exception as e:
            db.session.rollback()
            print(f"Error deleting supplier: {e}")
            flash("❌ An error occurred while deleting the supplier.", "error")
    else:
        flash("⚠️ Delete confirmation failed or missing.", "error")
    return redirect(url_for('list_suppliers', form=form))


# ========================
# Procurement Items
# ========================

@app.route('/procurement_items')
@login_required
def list_procurement_items():
    items = ProcurementItem.query.all()
    delete_form = DeleteItemForm()
    return render_template('procurement/list.html', items=items, delete_form=delete_form)


@app.route('/procurement_items/add', methods=['GET', 'POST'])
@login_required
@role_required(['accountant', 'admin'])
def add_procurement_item():
    form = ProcurementForm()
    if form.validate_on_submit():
        try:
            new_item = ProcurementItem(
                name=form.name.data,
                supplier_id=form.supplier_id.data,
                purchase_price=form.purchase_price.data,
                shipping_mode=form.shipping_mode.data,
                purchase_date=form.purchase_date.data or datetime.now(timezone.utc),
                expected_arrival_date=form.expected_arrival_date.data,
                status=form.status.data,
                currency=form.currency.data,
                shipping_cost=form.shipping_cost.data or 0.0
            )
            new_item.total_cost = new_item.calculate_total_cost()
            new_item.expected_arrival_date = new_item.calculate_expected_arrival()
            db.session.add(new_item)
            db.session.commit()
            flash(f"✅ Procurement item '{new_item.name}' added successfully.", "success")
            return redirect(url_for('list_procurement_items'))
        except Exception as e:
            db.session.rollback()
            print(f"Error adding procurement item: {e}")
            flash("❌ An error occurred while adding the procurement item.", "error")
    return render_template('procurement/add.html', form=form)


@app.route('/procurement_items/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
@role_required(['accountant', 'admin'])
def edit_procurement_item(item_id):
    item = ProcurementItem.query.get_or_404(item_id)
    form = ProcurementForm(obj=item)
    if form.validate_on_submit():
        try:
            form.populate_obj(item)
            item.total_cost = item.calculate_total_cost()
            item.expected_arrival_date = item.calculate_expected_arrival()
            db.session.commit()
            flash(f"Procurement item '{item.name}' updated successfully.", "success")
            return redirect(url_for('list_procurement_items'))
        except Exception as e:
            db.session.rollback()
            print(f"Error updating procurement item: {e}")
            flash("An error occurred while updating the item.", "error")
    return render_template('procurement/edit.html', form=form, item=item)


@app.route('/procurement_items/delete/<int:item_id>', methods=['POST'])
@login_required
@role_required(['admin'])
def delete_procurement_item(item_id):
    form = DeleteItemForm()
    item = ProcurementItem.query.get_or_404(item_id)
    try:
        db.session.delete(item)
        db.session.commit()
        flash(f"🗑️ Procurement item '{item.name}' deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting procurement item: {e}")
        flash("❌ An error occurred while deleting the item.", "error")
    return redirect(url_for('list_procurement_items', form=form, item=item))


# ========================
# Inventory
# ========================

@app.route('/inventory_items')
@login_required
def list_inventory():
    q = request.args.get('q', '').strip()
    status = request.args.get('status', '')
    category = request.args.get('category', '')
    query = OurProductService.query
    if q:
        query = query.filter(OurProductService.name.ilike(f"%{q}%"))
    if status == 'low_stock':
        query = query.filter(OurProductService.quantity_on_hand <= OurProductService.reorder_point)
    if status == 'out_of_stock':
        query = query.filter(OurProductService.quantity_on_hand == 0)
    if category:
        query = query.filter(OurProductService.category == category)
    items = query.all()
    categories = db.session.query(OurProductService.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    delete_form = DeleteItemForm()
    return render_template('inventory/list.html', items=items, categories=categories, delete_form=delete_form)


@app.route('/inventory_items/add', methods=['GET', 'POST'])
@login_required
@role_required(['accountant', 'admin'])
def add_inventory_item():
    form = InventoryItemForm()
    form.supplier_id.choices = [(s.id, s.name) for s in Supplier.query.all()]
    if form.validate_on_submit():
        new_item = OurProductService(
            name=form.name.data,
            description=form.description.data,
            standard_price=form.standard_price.data,
            cogs=form.cogs.data,
            category=form.category.data,
            quantity_on_hand=form.quantity_on_hand.data,
            reorder_point=form.reorder_point.data,
            unit_cost=form.unit_cost.data
        )
        db.session.add(new_item)
        db.session.commit()
        flash(f"✅ Inventory item '{new_item.name}' added successfully.", "success")
        return redirect(url_for('list_inventory'))
    return render_template('inventory/add.html', form=form)


@app.route('/inventory_items/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
@role_required(['accountant', 'admin'])
def edit_inventory_item(item_id):
    item = OurProductService.query.get_or_404(item_id)
    form = InventoryItemForm(obj=item)
    form.supplier_id.choices = [(s.id, s.name) for s in Supplier.query.all()]
    if form.validate_on_submit():
        try:
            form.populate_obj(item)
            db.session.commit()
            flash(f"Inventory item '{item.name}' updated successfully.", "success")
            return redirect(url_for('list_inventory'))
        except Exception as e:
            db.session.rollback()
            print(f"Error updating inventory item: {e}")
            flash("An error occurred while updating the item.", "error")
    return render_template('inventory/edit.html', item=item, form=form)


@app.route('/inventory_items/delete/<int:item_id>', methods=['POST'])
@login_required
@role_required(['admin'])
def delete_inventory_item(item_id):
    delete_form = DeleteItemForm()
    item = OurProductService.query.get_or_404(item_id)
    try:
        db.session.delete(item)
        db.session.commit()
        flash(f"Inventory item '{item.name}' deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting inventory item: {e}")
        flash("An error occurred while deleting the item.", "error")
    return redirect(url_for('list_inventory', delete_form=delete_form))


# ========================
# Bids
# ========================

@app.route('/bids')
@login_required
def list_bids():
    delete_form = DeleteItemForm()
    bids = Bid.query.all()
    return render_template('bids/list.html', bids=bids, delete_form=delete_form)


@app.route('/bids/add', methods=['GET', 'POST'])
@login_required
@role_required(['accountant', 'admin'])
def add_bid():
    form = BidForm()
    if form.validate_on_submit():
        try:
            new_bid = Bid(
                item_description=form.item_description.data,
                estimated_value=form.estimated_value.data,
                our_bid_price=form.our_bid_price.data,
                currency=form.currency.data,
                status=form.status.data
            )
            db.session.add(new_bid)
            db.session.commit()
            flash(f"✅ Bid '{new_bid.item_description}' added successfully.", "success")
            return redirect(url_for('list_bids'))
        except Exception as e:
            db.session.rollback()
            print(f"Error adding bid: {e}")
            flash("❌ An error occurred while adding the bid.", "error")
    return render_template('bids/add.html', form=form)


@app.route('/bids/edit/<int:bid_id>', methods=['GET', 'POST'])
@login_required
@role_required(['accountant', 'admin'])
def edit_bid(bid_id):
    bid = Bid.query.get_or_404(bid_id)
    form = BidForm(obj=bid)
    if form.validate_on_submit():
        try:
            form.populate_obj(bid)
            db.session.commit()
            flash(f"Bid '{bid.item_description}' updated successfully.", "success")
            return redirect(url_for('list_bids'))
        except Exception as e:
            db.session.rollback()
            print(f"Error updating bid: {e}")
            flash("An error occurred while updating the bid.", "error")
    return render_template('bids/edit.html', bid=bid, form=form)


@app.route('/bids/delete/<int:bid_id>', methods=['POST'])
@login_required
@role_required(['admin'])
def delete_bid(bid_id):
    delete_form = DeleteItemForm()
    bid = Bid.query.get_or_404(bid_id)
    try:
        db.session.delete(bid)
        db.session.commit()
        flash(f"Bid '{bid.item_description}' deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting bid: {e}")
        flash("An error occurred while deleting the bid.", "error")
    return redirect(url_for('list_bids'))


# ========================
# Competitors
# ========================

@app.route('/competitors')
@login_required
def list_competitors():
    competitors = Competitor.query.all()
    delete_form = DeleteItemForm()
    return render_template('competitors/list.html', competitors=competitors, delete_form=delete_form)


@app.route('/competitors/add', methods=['GET', 'POST'])
@login_required
@role_required(['accountant', 'admin'])
def add_competitor():
    form = CompetitorForm()
    if form.validate_on_submit():
        new_competitor = Competitor(
            name=form.name.data,
            bid_amount=form.bid_amount.data,
            sector=form.sector.data,
            location=form.location.data
        )
        db.session.add(new_competitor)
        db.session.commit()
        flash(f"✅ Competitor '{new_competitor.name}' added successfully.", "success")
        return redirect(url_for('list_competitors'))
    return render_template('competitors/add.html', form=form)


@app.route('/competitors/edit/<int:comp_id>', methods=['GET', 'POST'])
@login_required
@role_required(['accountant', 'admin'])
def edit_competitor(comp_id):
    competitor = Competitor.query.get_or_404(comp_id)
    form = CompetitorForm(obj=competitor)
    if form.validate_on_submit():
        form.populate_obj(competitor)
        db.session.commit()
        flash(f"Competitor '{competitor.name}' updated successfully.", "success")
        return redirect(url_for('list_competitors'))
    return render_template('competitors/edit.html', competitor=competitor, form=form)


@app.route('/competitors/delete/<int:comp_id>', methods=['POST'])
@login_required
@role_required(['admin'])
def delete_competitor(comp_id):
    delete_form = DeleteItemForm()
    competitor = Competitor.query.get_or_404(comp_id)
    try:
        db.session.delete(competitor)
        db.session.commit()
        flash(f"Competitor '{competitor.name}' deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting competitor: {e}")
        flash("An error occurred while deleting the competitor.", "error")
    return redirect(url_for('list_competitors'))


# ========================
# Document Generation
# ========================

@app.route('/generate_document', methods=['GET', 'POST'])
@login_required
@role_required(['accountant', 'admin'])
def generate_document():
    document_type = request.args.get('type', 'invoice').lower()
    if document_type == "proforma_invoice":
        document_type = "proforma"
    form = GenerateDocumentForm()

    # Debug
    print("DEBUG: Processing items...")
    for i, item_form in enumerate(form.items):
        print(f"Item {i} type: {type(item_form)}")
        print(f"Is FormField? {isinstance(item_form, Form)}")
        print(f"Fields: {dir(item_form)}")
        print(f"Description field type: {type(item_form.description)}")

    # Load clients
    clients = Client.query.order_by(Client.name).all()
    form.client.choices = [(c.id, c.name) for c in clients] or [(-1, "No clients available")]

    client = None
    client_id = request.args.get('client_id') or form.client.data
    if client_id and client_id != -1:
        try:
            client = db.session.get(Client, int(client_id))
        except:
            pass

    # Add initial item on GET
    if request.method == 'GET' and len(form.items) == 0:
        form.items.append_entry()

    if request.method == 'POST':
        print("DEBUG: POST received")

        # Adjust validators for delivery note
        if document_type == 'delivery_note':
            form.vat_rate.validators = [Optional()]
            for item in form.items:
                item.form.unit_price.validators = [Optional()]

        if form.validate_on_submit():
            print("DEBUG: form validated successfully")

            try:
                if form.client.data == -1:
                    flash("No clients available. Please add a client first.", "error")
                    return redirect(url_for('generate_document', type=document_type))

                client = db.session.get(Client, form.client.data)
                if not client:
                    flash("Client not found.", "error")
                    return redirect(url_for('generate_document', type=document_type))

                po_number = form.po_number.data.strip() if form.po_number.data else None
                due_date = form.due_date.data
                issue_date = form.issue_date.data
                # issue_date = form.issue_date or datetime.utcnow()
                # due_date = form.due_date or issue_date + timedelta(days=30)

                signing_person_name = form.signing_person_name.data.strip()
                signing_person_function = form.signing_person_function.data.strip()

                # VAT rate as Decimal
                if document_type != 'delivery_note':
                    vat_rate_val = safe_decimal(form.vat_rate.data)
                else:
                    vat_rate_val = Decimal('0.00')

                subtotal = Decimal('0.00')
                items_data = []

                for item_form in form.items:
                    description = (item_form.form.description.data or "").strip()
                    raw_qty = safe_decimal(item_form.form.quantity.data)
                    comment = (item_form.form.comment.data or "").strip()

                    if not description:
                        flash("Item description is required.", "error")
                        return redirect(url_for('generate_document', type=document_type))
                    if raw_qty <= 0:
                        flash("Quantity must be greater than 0.", "error")
                        return redirect(url_for('generate_document', type=document_type))

                    qty = int(raw_qty)

                    if document_type in ['invoice', 'proforma']:
                        price_val = safe_decimal(item_form.form.unit_price.data)
                        if price_val < 0:
                            flash("Unit price must be zero or positive.", "error")
                            return redirect(url_for('generate_document', type=document_type))
                        total = qty * price_val
                        subtotal += total  # ✅ Now both are Decimal

                        items_data.append({
                        'description': description,
                        'quantity': qty,
                        'unit_price': float(price_val),
                        'total_price': float(total),
                        'comment': comment
                        })
                    else:
                        items_data.append({
                        'description': description,
                        'quantity': qty,
                        'unit_price': None,
                        'total_price': None,
                        'comment': comment
                        })
                # Calculate totals only for invoices/proformas
                if document_type != 'delivery_note':
                    vat_amount = (subtotal * (vat_rate_val / Decimal('100'))).quantize(Decimal('0.00'))
                    total_amount = (subtotal + vat_amount).quantize(Decimal('0.00'))
                else:
                    vat_amount = Decimal('0.00')
                    total_amount = Decimal('0.00')
                    subtotal = Decimal('0.00')

                # Generate invoice number
                # count = db.session.query(Invoice).count() + 1
                # invoice_number = f"{document_type.upper()}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{count:03d}"

                # Generate smart document number
                invoice_number = generate_doc_number(document_type, items_data)
                invoice = Invoice(
                    document_type=document_type,
                    invoice_number=invoice_number,
                    po_number=po_number,
                    client_id=client.id,
                    issue_date=issue_date,
                    due_date=due_date,
                    subtotal=float(subtotal),
                    total_amount=float(total_amount),
                    vat_amount=float(vat_amount),
                    vat_rate=float(vat_rate_val),
                    status='Pending',
                    signing_person_name=signing_person_name,
                    signing_person_function=signing_person_function,
                    created_by= current_user.id
                )
                
                db.session.add(invoice)
                db.session.flush()

                for item in items_data:
                    invoice_item = InvoiceItem(invoice_id=invoice.id, created_by=current_user.id,**item)
                    db.session.add(invoice_item)

                # db.session.commit()
                flash(f"{document_type.title()} generated successfully.", "success")
                
                # ✅ Prepare data for PDF
                form_data = {
                    'client_name': client.name,
                    'client_address': client.address,
                    'document_type': document_type,
                    'po_number': po_number or 'N/A',
                    'issue_date': issue_date.isoformat(),
                    'due_date': due_date.isoformat() if due_date else 'N/A',
                    'items': items_data,
                    'subtotal': float(subtotal),
                    'vat_rate': float(vat_rate_val) if document_type != 'delivery_note' else 0.0,
                    'signing_person_name': signing_person_name,
                    'signing_person_function': signing_person_function,
                    'doc_number': invoice_number  # 👈 This goes to PDF
                }

                # ✅ Generate PDF with updated number
                pdf_buffer = generate_invoice_pdf(form_data, document_type=document_type,
                                                    save_to_disk=True  )
                
                print(f"📄 Generated PDF path: '{pdf_buffer}' (type: {type(pdf_buffer)})")
                print(f"💾 Storing in DB: invoice.pdf_file = '{pdf_buffer}'")
                invoice.pdf_file = pdf_buffer
                db.session.commit()
                return redirect(url_for('view_document', invoice_id=invoice.id))
                
            except Exception as e:
                db.session.rollback()
                print(f"❌ Error generating {document_type}: {e}")
                import traceback; traceback.print_exc()
                flash(f"Error generating {document_type}.", "error")
                client = db.session.get(Client, form.client.data) if form.client.data != -1 else None

        else:
            print("Form validation failed.")
            print("Form errors:", form.errors)

    return render_template(
        'generate_document.html',
        form=form,
        document_type=document_type,
        client=client
    )


@app.route('/edit_document/<int:invoice_id>', methods=['GET', 'POST'])
@login_required
@role_required(['accountant', 'admin'])
def edit_document(invoice_id):
    original = db.session.get(Invoice, invoice_id)
    if not original:
        abort(404)

    clients = Client.query.order_by(Client.name).all()
    form = GenerateDocumentForm()
    form.client.choices = [(c.id, c.name) for c in clients]

    # --- GET: Pre-fill form with current invoice data ---
    if request.method == 'GET':
        form.client.data = original.client_id
        form.po_number.data = original.po_number
        form.issue_date.data = original.issue_date
        form.due_date.data = original.due_date
        form.signing_person_name.data = original.signing_person_name
        form.signing_person_function.data = original.signing_person_function
        form.vat_rate.data = float(original.vat_rate) if original.vat_rate else None

        # Clear existing items and repopulate
        while len(form.items) > 0:
            form.items.pop_entry()

        for item in original.items:
            entry = form.items.append_entry()
            entry.form.description.data = item.description
            entry.form.quantity.data = float(item.quantity)
            entry.form.unit_price.data = float(item.unit_price) if item.unit_price else None
            entry.form.comment.data = item.comment

        print(f"📄 GET: Loaded {len(original.items)} items from invoice {original.invoice_number}")

        return render_template(
            'edit_document.html',
            invoice=original,
            form=form,
            client=original.client
        )

    # --- POST: Process edited document ---

    print("\n" + "="*60)
    print("📥 RECEIVED FORM DATA IN /edit_document")
    print("="*60)
    print(f"🔧 Raw keys received: {[k for k in request.form.keys() if 'items-' in k or 'client' in k]}")

    # Extract ALL submitted items safely from raw form data
    submitted_items = []
    prefix = "items-"
    description_keys = [k for k in request.form.keys() if k.startswith(prefix) and '-form-description' in k]

    max_index = -1
    for key in description_keys:
        try:
            idx = int(key.split('-')[1])
            max_index = max(max_index, idx)
        except (ValueError, IndexError):
            continue

    if max_index == -1:
        flash("At least one valid item is required.", "error")
        return render_template('edit_document.html', form=form, invoice=original, client=original.client)

    print(f"📊 Found {max_index + 1} item rows (indices 0 to {max_index})")

    subtotal = Decimal('0.00')

    for i in range(max_index + 1):
        desc_key = f"items-{i}-form-description"
        qty_key = f"items-{i}-form-quantity"
        price_key = f"items-{i}-form-unit_price"
        comment_key = f"items-{i}-form-comment"

        description = (request.form.get(desc_key, '') or '').strip()
        quantity_str = (request.form.get(qty_key, '') or '').strip()
        unit_price_str = (request.form.get(price_key, '') or '').strip()
        comment = (request.form.get(comment_key, '') or '').strip()

        # Skip empty rows
        if not description and not quantity_str:
            print(f"🟡 Skipping empty row {i}")
            continue

        # Validate quantity
        try:
            qty_val = safe_decimal(quantity_str)
            if qty_val <= 0:
                flash(f"Quantity must be greater than 0 for '{description}'", "error")
                return redirect(url_for('edit_document', invoice_id=invoice_id))
        except Exception as e:
            print(f"❌ Invalid quantity for '{description}': {quantity_str}")
            flash(f"Invalid quantity for '{description}'.", "error")
            return redirect(url_for('edit_document', invoice_id=invoice_id))

        # Validate unit price
        try:
            price_val = safe_decimal(unit_price_str) if unit_price_str else Decimal('0.00')
        except Exception:
            price_val = Decimal('0.00')

        quantity = int(qty_val)
        total_price = qty_val * price_val
        subtotal += total_price

        submitted_items.append({
            'description': description,
            'quantity': quantity,
            'unit_price': float(price_val),
            'total_price': float(total_price),
            'comment': comment
        })

        print(f"✅ Parsed Item {i}: '{description}' x{quantity} @ ${price_val:.2f} → Total: ${total_price:.2f}")

    if len(submitted_items) == 0:
        flash("At least one valid item is required.", "error")
        return redirect(url_for('edit_document', invoice_id=invoice_id))

    print(f"✅ Final Subtotal: ${subtotal:.2f}")

    # Get client
    try:
        client_id = int(form.client.data)
        client = db.session.get(Client, client_id)
        if not client:
            flash("Client not found.", "error")
            return redirect(url_for('edit_document', invoice_id=invoice_id))
    except Exception as e:
        print(f"❌ Invalid client ID: {form.client.data}, error: {e}")
        flash("Invalid client selected.", "error")
        return redirect(url_for('edit_document', invoice_id=invoice_id))

    # Determine next version number
    latest_version = db.session.scalar(
        select(Invoice)
        .where(
            ((Invoice.parent_id == original.parent_id) | (Invoice.id == original.parent_id)),
            Invoice.document_type == original.document_type
        )
        .order_by(Invoice.version.desc())
    )
    next_version = (latest_version.version if latest_version else 0) + 1

    # Generate document number
    new_base_number = generate_doc_number(original.document_type, submitted_items)
    new_invoice_number = f"{new_base_number}-v{next_version}"

    # Create new invoice
    new_invoice = Invoice(
        document_type=original.document_type,
        invoice_number=new_invoice_number,
        po_number=form.po_number.data.strip() if form.po_number.data else None,
        client_id=client.id,
        issue_date=form.issue_date.data,
        due_date=form.due_date.data,
        signing_person_name=form.signing_person_name.data.strip(),
        signing_person_function=form.signing_person_function.data.strip(),
        created_by=current_user.id,
        version=next_version,
        parent_id=original.parent_id or original.id
    )

    # Set financial fields
    if new_invoice.document_type != 'delivery_note':
        vat_rate_val = safe_decimal(form.vat_rate.data or 0)
        vat_amount = (subtotal * (vat_rate_val / 100)).quantize(Decimal('0.00'))
        total_amount = (subtotal + vat_amount).quantize(Decimal('0.00'))

        new_invoice.subtotal = float(subtotal)
        new_invoice.vat_amount = float(vat_amount)
        new_invoice.total_amount = float(total_amount)
        new_invoice.vat_rate = float(vat_rate_val)
    else:
        new_invoice.subtotal = 0.0
        new_invoice.vat_amount = 0.0
        new_invoice.total_amount = 0.0
        new_invoice.vat_rate = 0.0

    # Add items
    new_invoice.items.clear()
    for item in submitted_items:
        invoice_item = InvoiceItem(
            description=item['description'],
            quantity=item['quantity'],
            unit_price=item['unit_price'],
            total_price=item['total_price'],
            comment=item['comment'],
            created_by=current_user.id
        )
        new_invoice.items.append(invoice_item)

    db.session.add(new_invoice)
    db.session.commit()

    print(f"\n🎉 New invoice {new_invoice.id} saved:")
    print(f"   Number: {new_invoice.invoice_number}")
    print(f"   Items: {[(i.description, i.quantity, i.unit_price) for i in new_invoice.items]}")
    print(f"   Subtotal: {new_invoice.subtotal}, Total: {new_invoice.total_amount}")

    # ✅ Generate PDF with updated data
    try:
        pdf_context = {
            'document_type': new_invoice.document_type,
            'doc_number': new_invoice.invoice_number,
            'po_number': new_invoice.po_number,
            'client_name': client.name,
            'client_address': client.address,
            'issue_date': new_invoice.issue_date.strftime('%Y-%m-%d') if new_invoice.issue_date else 'N/A',
            'due_date': new_invoice.due_date.strftime('%Y-%m-%d') if new_invoice.due_date else 'N/A',
            'signing_person_name': new_invoice.signing_person_name,
            'signing_person_function': new_invoice.signing_person_function,
            'vat_rate': float(new_invoice.vat_rate),
            'subtotal': float(new_invoice.subtotal),
            'total_amount': float(new_invoice.total_amount),
            'items': [
                {
                    'description': i.description,
                    'quantity': i.quantity,
                    'unit_price': float(i.unit_price),
                    'total_price': float(i.total_price),
                    'comment': i.comment
                }
                for i in new_invoice.items
            ]
        }

        print("\n📊 FINAL ITEMS BEING SENT TO PDF GENERATOR:")
        for i, item in enumerate(pdf_context['items']):
            print(f"  {i+1}. '{item['description']}' x{item['quantity']} @ ${item['unit_price']:.2f}")

        # Call your PDF generator
        pdf_filename = generate_invoice_pdf(pdf_context,
                                            document_type=new_invoice.document_type,
                                            save_to_disk=True )  # Should return "generated_pdfs/filename.pdf"
        new_invoice.pdf_file = pdf_filename
        db.session.commit()

        print(f"🖨️ PDF generated and saved: {pdf_filename}")
        print(f"📄 Generated PDF path: '{pdf_filename}' (type: {type(pdf_filename)})")
        print(f"💾 Storing in DB: invoice.pdf_file = '{pdf_filename}'")
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        print(f"⚠️ Failed to generate PDF: {e}")
        flash("Invoice was saved, but could not generate PDF.", "warning")

    flash(f"New version created: {new_invoice.invoice_number}", "success")
    return redirect(url_for('view_document', invoice_id=new_invoice.id))
    

@app.route('/update_document_status/<int:invoice_id>', methods=['POST'])
@login_required
@role_required(['accountant', 'admin'])

def update_document_status(invoice_id):
    form=GenerateDocumentForm()
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        flash("Document not found.", "error")
        return redirect(url_for('dashboard'))

    new_status = request.form.get('status')
    valid_statuses = ['Pending', 'Sent', 'Paid', 'Overdue', 'Cancelled']

    if new_status not in valid_statuses:
        flash("Invalid status.", "error")
    else:
        invoice.status = new_status
        db.session.commit()
        flash("Document status updated.", "success")

    return redirect(url_for('view_document', invoice_id=invoice_id, form=form))

@app.route('/view_document/<int:invoice_id>')
@login_required
def view_document(invoice_id):
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        abort(404)
    # invoice = Invoice.query.get_or_404(invoice_id)
    # Optional: Role-based access
    if invoice.created_by != current_user.id and current_user.role != 'admin':
        flash("You don't have permission to view this document.", "error")
        return redirect(url_for('dashboard'))

    company_settings = get_or_create_company_settings()
    return render_template('view_document.html', invoice=invoice, company_settings=company_settings)




# @app.route('/download_document/<int:invoice_id>')
# @login_required
# def download_document(invoice_id):
#     invoice = db.session.get(Invoice, invoice_id)
#     if not invoice or not invoice.pdf_file:
#         abort(404)

#     pdf_path = os.path.join(app.static_folder, invoice.pdf_file)
#     if not os.path.exists(pdf_path):
#         flash("PDF file not found.", "error")
#         return redirect(url_for('view_document', invoice_id=invoice_id))

#     return send_file(
#         pdf_path,
#         as_attachment=True,
#         download_name=f"{invoice.invoice_number}.pdf",
#         mimetype='application/pdf'
#     )

@app.route('/download_document/<int:invoice_id>')
@login_required
def download_document(invoice_id):
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice or not invoice.pdf_file:
        print(f"❌ Invoice {invoice_id} not found or no pdf_file")
        abort(404)

    try:
        # Parse stored path like "generated_pdfs/filename.pdf"
        rel_path = str(invoice.pdf_file).strip()
        if not rel_path.startswith("generated_pdfs/"):
            print(f"❌ Invalid path format: {rel_path}")
            flash("Invalid file path.", "error")
            return redirect(url_for('view_document', invoice_id=invoice_id))

        # ✅ CORRECT: Build path using static_folder
        full_path = os.path.join(current_app.static_folder, rel_path)

        # Security: ensure it stays within static/
        static_abs = os.path.abspath(current_app.static_folder)
        file_abs = os.path.abspath(full_path)
        if not file_abs.startswith(static_abs):
            print(f"⚠️ Path traversal attempt? {full_path}")
            flash("Access denied.", "error")
            return redirect(url_for('view_document', invoice_id=invoice_id))

        if not os.path.exists(full_path):
            print(f"❌ File does NOT exist at: {full_path}")
            print(f"📁 Check if directory exists: {os.path.dirname(full_path)}")
            flash("PDF file not found on server.", "error")
            return redirect(url_for('view_document', invoice_id=invoice_id))

        print(f"✅ Serving PDF from: {full_path}")
        return send_file(
            full_path,
            as_attachment=True,
            download_name=f"{invoice.invoice_number}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"🚨 Error in download_document: {e}")
        flash("An error occurred while downloading the file.", "error")
        return redirect(url_for('view_document', invoice_id=invoice_id))
    
@app.route("/search_documents")
def search_documents():
    query = request.args.get("q", "").strip()
    results = []
    if query:
        results = db.session.scalars(
            db.select(Invoice).where(Invoice.invoice_number.contains(query))
        ).all()
    return render_template("search_results.html", results=results, query=query)

# @app.route("/preview_document", methods=["POST"])
# @login_required
# def preview_document():
#     print("\n" + "=" * 50)
#     print("📥 RECEIVED FORM DATA:")
#     for key, value in request.form.items():
#         print(f"  {key} = {value} (type: {type(value)})")
#     print("=" * 50)

#     document_type = request.form.get("document_type", "invoice").lower()
#     if document_type == "proforma_invoice":
#         document_type = "proforma"
#     if document_type not in ["invoice", "proforma", "delivery_note"]:
#         return "Invalid document type", 400
#     # 🔥 DEBUG: Log incoming request
#     print("\n" + "="*50)
#     print("📄 /generate_document - METHOD:", request.method)
#     print("📌 Document Type:", document_type)
    
#     if request.method == 'POST':
#         print("📥 POST DATA RECEIVED:")
#         for key, value in request.form.items():
#             print(f"  {key} = {value} (type: {type(value)})")
        
#         # Also log keys for hidden/missing fields
#         print("🔍 Form keys:", list(request.form.keys()))
    
#     print("="*50)

#     form = GenerateDocumentForm()
#     clients = Client.query.all()
#     form.client.choices = [(c.id, c.name) for c in clients] or [(-1, "No clients available")]
#     form.process(request.form)

#     if not form.validate():
#         print("❌ VALIDATION FAILED:", form.errors)
#         return "Validation failed", 400

#     # Get client
#     client = None
#     try:
#         client_id = int(form.client.data)
#         if client_id > 0:
#             client = db.session.get(Client, client_id)
#     except Exception as e:
#         print(f"❌ Invalid client ID: {form.client.data}, error: {e}")

#     # Build items
#     items_list = []
#     for item in form.items:
#         desc = (item.form.description.data or "").strip()
#         qty = item.form.quantity.data or 0
#         comment = (item.form.comment.data or "").strip()
#         if not desc and qty == 0:
#             continue
#         from decimal import Decimal

# # Safely convert to string first, then Decimal
#     def safe_decimal(val, default='0'):
#         try:
#             return Decimal(str(val))
#         except:
#             return Decimal(default)

#     item_data = {
#         "description": desc,
#         "quantity": safe_decimal(qty),
#         "comment": comment,
#     }
#     if document_type != "delivery_note":
#         item_data["unit_price"] = safe_decimal(item.form.unit_price.data)
#     items_list.append(item_data)

#     form_data = {
#         "document_type": document_type,
#         "client_name": getattr(client, "name", "Unknown"),
#         "client_address": getattr(client, "address", "N/A"),
#         "po_number": form.po_number.data or "",
#         "issue_date": form.issue_date.data.strftime("%Y-%m-%d") if form.issue_date.data else "N/A",
#         "due_date": form.due_date.data.strftime("%Y-%m-%d") if form.due_date.data else "N/A",
#         "signing_person_name": form.signing_person_name.data or "",
#         "signing_person_function": form.signing_person_function.data or "",
#         "items": items_list,
#     }
#     if document_type != "delivery_note":
#         form_data["vat_rate"] = float(form.vat_rate.data or 0)

#     try:
#         pdf_bytes = generate_invoice_pdf(
#             form_data=form_data,
#             preview=True,
#             document_type=document_type
#         )
#         return Response(
#             pdf_bytes,
#             mimetype="application/pdf",
#             headers={"Content-Disposition": 'inline; filename="preview.pdf"'},
#         )
#     except Exception as e:
#         print(f"❌ PDF generation failed: {e}")
#         import traceback
#         traceback.print_exc()
#         return "Failed to generate PDF", 500

@app.route("/preview_document", methods=["POST"])
@login_required
def preview_document():
    print("\n" + "=" * 50)
    print("📥 RECEIVED FORM DATA:")
    for key, value in request.form.items():
        print(f"  {key} = {value} (type: {type(value)})")
    print("=" * 50)

    document_type = request.form.get("document_type", "invoice").lower()
    if document_type == "proforma_invoice":
        document_type = "proforma"
    if document_type not in ["invoice", "proforma", "delivery_note"]:
        return "Invalid document type", 400

    form = GenerateDocumentForm()
    clients = Client.query.all()
    form.client.choices = [(c.id, c.name) for c in clients] or [(-1, "No clients available")]
    form.process(request.form)

    if not form.validate():
        print("❌ VALIDATION FAILED:", form.errors)
        return "Validation failed", 400

    client = None
    try:
        client_id = int(form.client.data)
        if client_id > 0:
            client = db.session.get(Client, client_id)
    except Exception as e:
        print(f"❌ Invalid client ID: {form.client.data}, error: {e}")

    items_list = []
    for item in form.items:
        desc = (item.form.description.data or "").strip()
        qty = safe_decimal(item.form.quantity.data)
        comment = (item.form.comment.data or "").strip()
        if not desc and qty <= 0:
            continue

        item_data = {
            "description": desc,
            "quantity": float(qty),
            "comment": comment,
        }
        if document_type != "delivery_note":
            item_data["unit_price"] = float(safe_decimal(item.form.unit_price.data))
            item_data["total"] = float(qty * safe_decimal(item.form.unit_price.data))
        items_list.append(item_data)

    form_data = {
        "document_type": document_type,
        "client_name": getattr(client, "name", "Unknown"),
        "client_address": getattr(client, "address", "N/A"),
        "po_number": form.po_number.data or "",
        "issue_date": form.issue_date.data.strftime("%Y-%m-%d") if form.issue_date.data else "N/A",
        "due_date": form.due_date.data.strftime("%Y-%m-%d") if form.due_date.data else "N/A",
        "signing_person_name": form.signing_person_name.data or "",
        "signing_person_function": form.signing_person_function.data or "",
        "items": items_list,
        "doc_number": f"TEMP-{document_type.upper()}-{id(form)}",
        "vat_rate": float(form.vat_rate.data or 0) if document_type != "delivery_note" else 0.0
    }

    try:
        pdf_bytes = generate_invoice_pdf(form_data, preview=True, save_to_disk=False)
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": "inline; filename=preview.pdf"}
        )
    except Exception as e:
        print(f"❌ PDF generation failed: {e}")
        import traceback
        traceback.print_exc()
        return "Failed to generate PDF", 500
    
@app.route('/upload_attachment/<int:invoice_id>', methods=['POST'])
@login_required
@role_required(['accountant', 'admin'])
def upload_attachment(invoice_id):
    invoice = db.session.get(Invoice, invoice_id)
    if not invoice:
        flash("Document not found.", "error")
        return redirect(url_for('dashboard'))

    if 'attachment' not in request.files:
        flash("No file selected.", "error")
        return redirect(url_for('view_document', invoice_id=invoice_id))

    file = request.files['attachment']
    if file.filename == '':
        flash("No file selected.", "error")
        return redirect(url_for('view_document', invoice_id=invoice_id))

    if file and allowed_file(file.filename):
        # Secure filename and create custom name
        ext = file.filename.rsplit('.', 1)[1].lower()
        original_filename = secure_filename(file.filename)
        filename = secure_filename(f"invoice_{invoice_id}_{int(datetime.utcnow().timestamp())}.{ext}")

        # Build path: uploads/attachments/invoice_1/
        upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'attachments', f'invoice_{invoice_id}')
        os.makedirs(upload_dir, exist_ok=True)

        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)

        # Save relative path (so it's portable)
        relative_path = os.path.join('attachments', f'invoice_{invoice_id}', filename)

        # Save to DB
        attachment = Attachment(
            invoice_id=invoice.id,
            file_path=relative_path,
            filename=original_filename,
            file_type=ext,
            uploaded_by_id=current_user.id
        )
        db.session.add(attachment)
        db.session.commit()

        flash("File uploaded successfully.", "success")
    else:
        flash(f"Invalid file type. Allowed: {', '.join(current_app.config['ALLOWED_EXTENSIONS'])}", "error")

    return redirect(url_for('view_document', invoice_id=invoice_id))
@app.route('/test_pdf')
@login_required
def test_pdf():
    form_data = {
        'client_name': 'Test Client',
        'client_address': '123 Test St',
        'po_number': 'PO-001',
        'due_date': '2025-12-31',
        'vat_rate': 16.0,
        'items': [
            {'description': 'Widget', 'quantity': 2, 'unit_price': 50.0}
        ]
    }
    pdf_bytes = generate_invoice_pdf(form_data, preview=True, document_type='invoice')
    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={'Content-Disposition': 'inline; filename="test.pdf"'}
    )
# ========================
# Company Settings
# ========================

@app.route('/upload_company_stamp', methods=['GET', 'POST'])
@login_required
@role_required(['admin'])
def upload_company_stamp():
    settings = get_or_create_company_settings()

    if request.method == 'POST':
        try:
            # Handle signing person info
            settings.signing_person_name = request.form.get('signing_person_name', '').strip()
            settings.signing_person_function = request.form.get('signing_person_function', '').strip()

            # ✅ Always use app.static_folder as base
            base_upload_dir = os.path.join(app.static_folder, 'uploads', 'company')
            os.makedirs(base_upload_dir, exist_ok=True)

            # Handle signature upload
            if 'signature_file' in request.files and request.files['signature_file'].filename != '':
                file = request.files['signature_file']
                if file and allowed_file(file.filename):
                    filename = secure_filename('company_signature.png')
                    filepath = os.path.join(base_upload_dir, filename)

                    print(f"📄 Saving signature to: {filepath}")
                    file.save(filepath)

                    if os.path.exists(filepath):
                        print(f"✅ SUCCESS: Signature saved!")
                    else:
                        print(f"❌ FAILED: Could not save signature!")

                    settings.signature_image_path = "company/company_signature.png"

            # Handle stamp upload
            if 'stamp_file' in request.files and request.files['stamp_file'].filename != '':
                file = request.files['stamp_file']
                if file and allowed_file(file.filename):
                    filename = secure_filename('company_stamp.png')
                    filepath = os.path.join(base_upload_dir, filename)

                    print(f"📄 Saving stamp to: {filepath}")
                    file.save(filepath)

                    if os.path.exists(filepath):
                        print(f"✅ SUCCESS: Stamp saved!")
                    else:
                        print(f"❌ FAILED: Could not save stamp!")

                    settings.stamp_image_path = "company/company_stamp.png"

            db.session.commit()
            flash("✅ Signature, stamp, and signer details updated.", "success")
            return redirect(url_for('upload_company_stamp'))

        except Exception as e:
            db.session.rollback()
            print(f"💥 Error uploading files: {e}")
            flash("❌ An error occurred during upload.", "error")

    return render_template('settings/upload_stamp.html', settings=settings)
# @app.route('/upload_company_logo', methods=['GET', 'POST'])
# @login_required
# @role_required(['admin'])
# def upload_company_logo():
#     settings = get_or_create_company_settings()

#     if request.method == 'POST':
#         try:
#             if 'logo_file' in request.files and request.files['logo_file'].filename != '':
#                 file = request.files['logo_file']
#                 if file and allowed_file(file.filename):
#                     filename = secure_filename('company_logo.png')
#                     upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'company')
#                     os.makedirs(upload_dir, exist_ok=True)
#                     filepath = os.path.join(upload_dir, filename)
#                     file.save(filepath)

#                     # Save relative path
#                     settings.logo_image_path = "uploads/company/company_logo.png"

#             db.session.commit()
#             flash("✅ Logo uploaded successfully.", "success")
#             return redirect(url_for('upload_company_logo'))

#         except Exception as e:
#             db.session.rollback()
#             print(f"Error uploading logo: {e}")
#             flash("❌ An error occurred during upload.", "error")

#     return render_template('settings/upload_company_logo.html', settings=settings)

@app.route('/upload_company_logo', methods=['GET', 'POST'])
@login_required
@role_required(['admin'])
def upload_company_logo():
    settings = get_or_create_company_settings()

    if request.method == 'POST':
        try:
            if 'logo_file' in request.files and request.files['logo_file'].filename != '':
                file = request.files['logo_file']
                if file and allowed_file(file.filename):
                    filename = secure_filename('company_logo.png')

                    # ✅ Use app.static_folder for uploads
                    upload_dir = os.path.join(app.static_folder, 'uploads', 'company')
                    os.makedirs(upload_dir, exist_ok=True)
                    filepath = os.path.join(upload_dir, filename)

                    print(f"📄 Saving logo to: {filepath}")
                    file.save(filepath)

                    if os.path.exists(filepath):
                        print(f"✅ SUCCESS: File saved!")
                    else:
                        print(f"❌ FAILED TO SAVE")

                    # ✅ Store relative path (no 'uploads/' prefix)
                    settings.logo_image_path = "company/company_logo.png"

            db.session.commit()
            flash("✅ Logo uploaded successfully.", "success")
            return redirect(url_for('upload_company_logo'))

        except Exception as e:
            db.session.rollback()
            print(f"💥 Error uploading logo: {e}")
            flash("❌ Upload failed.", "error")

    return render_template('settings/upload_company_logo.html', settings=settings)

# ========================
# Image Serving Routes
# ========================

@app.route('/company_logo')
def company_logo():
    settings = get_or_create_company_settings()
    if settings and settings.logo_image_path and os.path.exists(settings.logo_image_path):
        directory = os.path.dirname(settings.logo_image_path)
        filename = os.path.basename(settings.logo_image_path)
        return send_from_directory(directory, filename)
    abort(404)


@app.route('/company_signature')
def company_signature():
    settings = get_or_create_company_settings()
    if settings and settings.signature_image_path and os.path.exists(settings.signature_image_path):
        directory = os.path.dirname(settings.signature_image_path)
        filename = os.path.basename(settings.signature_image_path)
        return send_from_directory(directory, filename)
    abort(404)


@app.route('/company_stamp')
def company_stamp():
    settings = get_or_create_company_settings()
    if settings and settings.stamp_image_path and os.path.exists(settings.stamp_image_path):
        directory = os.path.dirname(settings.stamp_image_path)
        filename = os.path.basename(settings.stamp_image_path)
        return send_from_directory(directory, filename)
    abort(404)

# --- LOCAL MARKET ---
@app.route('/local_market')
@login_required
def list_local_market():
    items = LocalMarketItem.query.order_by(LocalMarketItem.name).all()
    delete_form = DeleteItemForm()
    return render_template('local_market/list.html', items=items, delete_form=delete_form)


@app.route('/local_market/add', methods=['GET', 'POST'])
@login_required
@role_required(['accountant', 'admin'])
def add_local_market_item():
    form = LocalMarketForm()
    if form.validate_on_submit():
        try:
            new_item = LocalMarketItem(
                name=form.name.data.strip(),
                recent_price=form.recent_price.data,
                currency=form.currency.data.strip(),
                source=form.source.data.strip(),
                description=form.description.data.strip()
            )
            db.session.add(new_item)
            db.session.commit()
            flash(f"✅ Local market item '{new_item.name}' added successfully.", "success")
            return redirect(url_for('list_local_market'))
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error adding local market item: {e}")
            flash("An error occurred while adding the item.", "error")
    return render_template('local_market/add.html', form=form)


@app.route('/local_market/edit/<int:item_id>', methods=['GET', 'POST'])
@login_required
@role_required(['accountant', 'admin'])
def edit_local_market_item(item_id):
    item = LocalMarketItem.query.get_or_404(item_id)
    form = LocalMarketForm(obj=item)
    if form.validate_on_submit():
        try:
            form.populate_obj(item)
            db.session.commit()
            flash(f"✅ '{item.name}' updated successfully.", "success")
            return redirect(url_for('list_local_market'))
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error updating local market item: {e}")
            flash("An error occurred while updating the item.", "error")
    return render_template('local_market/edit.html', item=item, form=form)


@app.route('/local_market/delete/<int:item_id>', methods=['POST'])
@login_required
@role_required(['admin'])
def delete_local_market_item(item_id):
    item = LocalMarketItem.query.get_or_404(item_id)
    try:
        db.session.delete(item)
        db.session.commit()
        flash(f"🗑️ Local market item '{item.name}' deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error deleting local market item: {e}")
        flash("An error occurred while deleting the item.", "error")
    return redirect(url_for('list_local_market'))


# --- PRODUCTS & SERVICES ---
@app.route('/products_services')
@login_required
def list_products_services():
    try:
        products = OurProductService.query.all()
        delete_form = DeleteItemForm()
        return render_template('products_services/list.html', products=products, delete_form=delete_form)
    except Exception as e:
        print(f"❌ Error fetching products/services: {e}")
        flash("An error occurred while loading products/services.", "error")
        return "An internal error occurred.", 500


@app.route('/products_services/add', methods=['GET', 'POST'])
@login_required
@role_required(['accountant', 'admin'])
def add_product_service():
    form = ProductForm()
    if form.validate_on_submit():
        try:
            new_product = OurProductService(
                name=form.name.data.strip(),
                description=form.description.data.strip(),
                category=form.category.data.strip(),
                currency=form.currency.data.strip(),
                standard_price=form.standard_price.data or 0.0,
                cogs=form.cogs.data or 0.0,
                is_active=form.is_active.data,
                quantity_on_hand=form.quantity_on_hand.data or 0,
                reorder_point=form.reorder_point.data or 0,
                unit_cost=form.unit_cost.data or 0.0
            )
            db.session.add(new_product)
            db.session.commit()
            flash(f"✅ Product/Service '{new_product.name}' added successfully.", "success")
            return redirect(url_for('list_products_services'))
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error adding product/service: {e}")
            flash("An error occurred while adding the product/service.", "error")
    return render_template('products_services/add.html', form=form)


@app.route('/products_services/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
@role_required(['accountant', 'admin'])
def edit_product_service(product_id):
    product = OurProductService.query.get_or_404(product_id)
    form = ProductForm(obj=product)
    if form.validate_on_submit():
        try:
            form.populate_obj(product)
            if not product.name.strip():
                flash("Product/Service name is required.", "error")
                return render_template('products_services/edit.html', product=product, form=form), 400
            db.session.commit()
            flash(f"✅ Product/Service '{product.name}' updated successfully.", "success")
            return redirect(url_for('list_products_services'))
        except ValueError as ve:
            flash(f"⚠️ Invalid number format: {ve}", "error")
            return render_template('products_services/edit.html', product=product, form=form), 400
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error updating product/service: {e}")
            flash("An error occurred while updating the product/service.", "error")
            return render_template('products_services/edit.html', product=product, form=form), 500
    return render_template('products_services/edit.html', product=product, form=form)


@app.route('/products_services/<int:product_id>/delete', methods=['POST'])
@login_required
@role_required(['admin'])
def delete_product_service(product_id):
    """
    Delete a product or service.
    Only accessible to admin users.
    """
    product = OurProductService.query.get_or_404(product_id)
    try:
        db.session.delete(product)
        db.session.commit()
        flash(f"🗑️ Product/Service '{product.name}' deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error deleting product/service: {e}")
        flash("An error occurred while deleting the product/service.", "error")
    return redirect(url_for('list_products_services'))


# ========================
# Routes: Business Analysis
# ========================

@app.route('/profitability_analysis')
@login_required
def profitability_analysis():
    total_revenue = db.session.query(func.sum(Invoice.total_amount)) \
        .filter_by(status='Paid', document_type='invoice').scalar() or 0.0
    total_cogs = db.session.query(func.sum(OurProductService.cogs)).scalar() or 0.0
    gross_profit = total_revenue - total_cogs
    profit_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0.0

    return render_template('analysis/profitability.html',
                           total_revenue=total_revenue,
                           total_cogs=total_cogs,
                           gross_profit=gross_profit,
                           profit_margin=round(profit_margin, 2))


@app.route('/procurement_spending_analysis')
@login_required
def procurement_spending_analysis():
    one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
    total_spent = db.session.query(func.sum(ProcurementItem.total_cost)) \
        .filter(ProcurementItem.purchase_date >= one_year_ago).scalar() or 0.0
    return render_template('analysis/procurement.html', total_spent=total_spent)


@app.route('/business_prediction')
@login_required
def business_prediction():
    # Example: Use last 10 invoices for mock prediction
    recent_invoices = Invoice.query.filter_by(document_type='invoice') \
        .order_by(Invoice.date_created.desc()).limit(10).all()
    predicted_revenue = sum(inv.total_amount for inv in recent_invoices) * 1.1  # +10% growth
    return render_template('analysis/prediction.html',
                           recent_invoices=recent_invoices,
                           predicted_revenue=predicted_revenue)


@app.route('/business_outlook')
@login_required
def business_outlook():
    upcoming_invoices = Invoice.query.filter(
        Invoice.status == 'Pending',
        Invoice.document_type == 'invoice'
    ).order_by(Invoice.due_date.asc()).limit(5).all()
    return render_template('analysis/business_outlook.html', upcoming_invoices=upcoming_invoices)

# ========================
# Run the App
# ========================


if __name__ == '__main__':
    with app.app_context():
        # ✅ Step 1: Create all tables first
        db.create_all()
        print("✅ Tables created")

        # ✅ Step 2: Now safe to query
        get_or_create_company_settings()
        print("✅ Company settings created or loaded")
        from models_core import create_default_admin
        create_default_admin()
        ensure_directories()
        print("✅ Admin ensured and directories checked")
        # ✅ Step 3: Create default admin if not exists
        # if User.query.filter_by(username='admin').first() is None:
        #     hashed_pw = bcrypt.generate_password_hash('admin123').decode('utf-8')
        #     admin = User(username='admin', password=hashed_pw, role='admin', full_name='System Admin')
        #     db.session.add(admin)
        #     db.session.commit()
        #     print("✅ Default admin created: username='admin', password='admin123'")

    print("🚀 APEX Management App running...")
    app.run(host='0.0.0.0', port=5000, debug=False)