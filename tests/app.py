# app.py
import os
import json
from datetime import datetime, timezone, timedelta
from io import BytesIO

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_file,
    flash,
    send_from_directory,
    session,
    abort
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from flask_bcrypt import Bcrypt

# ========================
# Flask App & DB Setup
# ========================
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///apex_bnn.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# ========================
# Models
# ========================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='accountant')  # admin, accountant, viewer
    full_name = db.Column(db.String(100))

class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text)
    email = db.Column(db.String(100))
    phone = db.Column(db.String(20))

class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    DOCUMENT_TYPES = ['invoice', 'proforma', 'delivery_note']
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

class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    comment = db.Column(db.Text)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)

class CompanySettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    signature_image_path = db.Column(db.String(500))
    signature_description = db.Column(db.String(255))
    stamp_image_path = db.Column(db.String(500))
    signing_person_name = db.Column(db.String(100))
    signing_person_function = db.Column(db.String(100))

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

class Bid(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_description = db.Column(db.String(200), nullable=False)
    estimated_value = db.Column(db.Float)
    submission_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), default='Pending')

class Competitor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    bid_amount = db.Column(db.Float)
    bid_id = db.Column(db.Integer, db.ForeignKey('bid.id'))

class OurProductService(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    standard_price = db.Column(db.Float)
    currency = db.Column(db.String(3), default='USD')
    cogs = db.Column(db.Float)
    category = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)

class LocalMarketItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    recent_price = db.Column(db.Float)
    currency = db.Column(db.String(3), default='USD')
    source = db.Column(db.String(100))
    last_updated = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

# ========================
# Utility Functions
# ========================

def get_or_create_company_settings():
    settings = CompanySettings.query.first()
    if not settings:
        settings = CompanySettings()
        db.session.add(settings)
        db.session.commit()
    return settings

# ========================
# Authentication
# ========================

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(roles):
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('role') not in roles:
                flash("You don't have permission to access this page.", "error")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['role'] = user.role
            flash(f"Welcome, {user.full_name}!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password.", "error")
    return render_template('auth/login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.context_processor
def inject_user():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    return dict(current_user=user)

# ========================
# Routes: Core
# ========================

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        pending_invoices = Invoice.query.filter_by(status='Pending', document_type='invoice').count()
        total_revenue = db.session.query(db.func.sum(Invoice.total_amount)).filter_by(status='Paid', document_type='invoice').scalar() or 0.0
        overdue_invoices = Invoice.query.filter_by(status='Overdue', document_type='invoice').count()
        pending_proformas = Invoice.query.filter_by(status='Pending', document_type='proforma').count()
        pending_delivery_notes = Invoice.query.filter_by(document_type='delivery_note').count()
        recent_documents = Invoice.query.order_by(Invoice.date_created.desc()).limit(10).all()

        recent_activity_count = Invoice.query.filter(Invoice.date_created >= datetime.now(timezone.utc) - timedelta(days=7)).count()
        top_client = db.session.query(Client.name, db.func.sum(Invoice.total_amount)).join(Invoice).filter(Invoice.status == 'Paid').group_by(Client.id).order_by(db.func.sum(Invoice.total_amount).desc()).first()
        top_client_name = top_client[0] if top_client else "N/A"
        top_client_amount = top_client[1] if top_client else 0.0
        avg_invoice_value = db.session.query(db.func.avg(Invoice.total_amount)).filter_by(document_type='invoice').scalar() or 0.0
        total_suppliers = Supplier.query.count()
        pending_procurements = ProcurementItem.query.filter_by(status='Ordered').count()
        total_bids = Bid.query.count()
        pending_bids = Bid.query.filter_by(status='Pending').count()

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
                               pending_bids=pending_bids)
    except Exception as e:
        print(f"Error fetching dashboard: {e}")
        flash("An error occurred while loading the dashboard.", "error")
        return "An error occurred.", 500

# ========================
# Routes: Document Generation
# ========================

@app.route('/generate_document', methods=['GET', 'POST'])
@login_required
@role_required(['accountant', 'admin'])
def generate_document():
    document_type = request.args.get('type', 'invoice')
    if request.method == 'POST':
        try:
            client_id = request.form.get('client')
            po_number = request.form.get('po_number', '').strip()
            due_date = request.form.get('due_date')
            if due_date:
                due_date = datetime.fromisoformat(due_date)

            items_data = []
            subtotal = 0.0
            for i in range(1, 11):
                desc = request.form.get(f'description_{i}')
                qty_str = request.form.get(f'quantity_{i}')
                price_str = request.form.get(f'unit_price_{i}')
                comment = request.form.get(f'comment_{i}', '').strip()
                if not desc or not qty_str:
                    continue
                qty = int(qty_str)
                if qty <= 0:
                    flash(f"Quantity must be positive for item {i}.", "error")
                    return redirect(url_for('generate_document', type=document_type))
                price = float(price_str) if price_str else 0.0
                total = qty * price
                subtotal += total
                items_data.append({'description': desc, 'quantity': qty, 'unit_price': price, 'total_price': total, 'comment': comment})

            vat_rate = 16.0
            vat_amount = round(subtotal * (vat_rate / 100), 2)
            total_amount = round(subtotal + vat_amount, 2) if document_type != 'delivery_note' else 0.0

            invoice_number = f"{document_type.upper()}-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{Invoice.query.count() + 1:03d}"

            invoice = Invoice(
                document_type=document_type,
                invoice_number=invoice_number,
                po_number=po_number,
                client_id=int(client_id),
                due_date=due_date,
                total_amount=total_amount,
                vat_amount=vat_amount if document_type != 'delivery_note' else 0.0,
                vat_rate=vat_rate if document_type != 'delivery_note' else 0.0,
                status='Pending'
            )
            db.session.add(invoice)
            db.session.flush()

            for item in items_data:
                invoice_item = InvoiceItem(invoice_id=invoice.id, **item)
                db.session.add(invoice_item)

            db.session.commit()
            flash(f"{document_type.title()} generated successfully.", "success")
            return redirect(url_for('view_invoice', invoice_id=invoice.id))
        except Exception as e:
            db.session.rollback()
            print(f"Error generating {document_type}: {e}")
            flash(f"Error generating {document_type}.", "error")
            return redirect(url_for('generate_document', type=document_type))

    clients = Client.query.all()
    return render_template('generate_document.html', clients=clients, document_type=document_type)

@app.route('/view_invoice/<int:invoice_id>')
@login_required
def view_invoice(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    return render_template('view_invoice.html', invoice=invoice)

# ========================
# Routes: Document Download
# ========================

@app.route('/download_invoice/<int:invoice_id>', endpoint='download_invoice')
@app.route('/download_proforma_invoice/<int:invoice_id>', endpoint='download_proforma_invoice')
@app.route('/download_delivery_note/<int:invoice_id>', endpoint='download_delivery_note')
@login_required
def download_document(invoice_id):
    try:
        invoice = Invoice.query.get_or_404(invoice_id)
        company_settings = get_or_create_company_settings()

        html = render_template('document_template.html',
                               invoice=invoice,
                               company_settings=company_settings)

        import pdfkit
        options = {
            'enable-local-file-access': None,
            'quiet': '',
            'page-size': 'A4',
            'margin-top': '0.5in',
            'margin-right': '0.5in',
            'margin-bottom': '0.5in',
            'margin-left': '0.5in',
        }
        pdf = pdfkit.from_string(html, False, options=options)

        filename = f"{invoice.document_type}_{invoice.invoice_number}.pdf"
        return send_file(
            BytesIO(pdf),
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    except Exception as e:
        print(f"PDF generation failed: {e}")
        flash("PDF generation failed.", "error")
        return redirect(url_for('view_invoice', invoice_id=invoice_id))

# ========================
# Routes: Company Settings
# ========================

@app.route('/upload_company_stamp', methods=['GET', 'POST'])
@login_required
@role_required(['admin'])
def upload_company_stamp():
    settings = get_or_create_company_settings()
    if request.method == 'POST':
        if 'signature_file' in request.files and request.files['signature_file'].filename != '':
            file = request.files['signature_file']
            if file and file.filename.endswith(('.png', '.jpg', '.jpeg')):
                filename = secure_filename(f"signature_{settings.id}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                settings.signature_image_path = filepath
                db.session.commit()
                flash("Signature uploaded successfully.", "success")
        if 'stamp_file' in request.files and request.files['stamp_file'].filename != '':
            file = request.files['stamp_file']
            if file and file.filename.endswith(('.png', '.jpg', '.jpeg')):
                filename = secure_filename(f"stamp_{settings.id}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                settings.stamp_image_path = filepath
                db.session.commit()
                flash("Stamp uploaded successfully.", "success")
        return redirect(url_for('upload_company_stamp'))
    return render_template('settings/upload_stamp.html', settings=settings)

@app.route('/company_stamp')
def company_stamp():
    try:
        settings = get_or_create_company_settings()
        if settings.stamp_image_path and os.path.exists(settings.stamp_image_path):
            directory = os.path.dirname(settings.stamp_image_path)
            filename = os.path.basename(settings.stamp_image_path)
            return send_from_directory(directory, filename)
        else:
            abort(404)
    except Exception as e:
        print(f"Error serving stamp: {e}")
        abort(500)

@app.route('/company_signature')
def company_signature():
    try:
        settings = get_or_create_company_settings()
        if settings.signature_image_path and os.path.exists(settings.signature_image_path):
            directory = os.path.dirname(settings.signature_image_path)
            filename = os.path.basename(settings.signature_image_path)
            return send_from_directory(directory, filename)
        else:
            abort(404)
    except Exception as e:
        print(f"Error serving signature: {e}")
        abort(500)

# ========================
# Routes: Data Management
# ========================

@app.route('/clients')
@login_required
def list_clients():
    clients = Client.query.all()
    return render_template('clients/list.html', clients=clients)

@app.route('/suppliers')
@login_required
def list_suppliers():
    suppliers = Supplier.query.all()
    return render_template('suppliers/list.html', suppliers=suppliers)

@app.route('/bids')
@login_required
def list_bids():
    bids = Bid.query.all()
    return render_template('bids/list.html', bids=bids)

@app.route('/inventory_items')
@login_required
def list_inventory():
    items = OurProductService.query.all()
    return render_template('inventory/list.html', items=items)

@app.route('/local_market')
@login_required
def list_local_market():
    items = LocalMarketItem.query.all()
    return render_template('local_market/list.html', items=items)

@app.route('/competitors')
@login_required
def list_competitors():
    competitors = Competitor.query.all()
    return render_template('competitors/list.html', competitors=competitors)

# ========================
# Routes: Business Analysis
# ========================

@app.route('/profitability_analysis')
@login_required
def profitability_analysis():
    total_revenue = db.session.query(db.func.sum(Invoice.total_amount)).filter_by(status='Paid', document_type='invoice').scalar() or 0.0
    total_cogs = db.session.query(db.func.sum(OurProductService.cogs)).scalar() or 0.0
    gross_profit = total_revenue - total_cogs
    return render_template('analysis/profitability.html',
                           total_revenue=total_revenue,
                           total_cogs=total_cogs,
                           gross_profit=gross_profit)

@app.route('/procurement_spending_analysis')
@login_required
def procurement_spending_analysis():
    one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
    total_spent = db.session.query(db.func.sum(ProcurementItem.total_cost)).filter(ProcurementItem.purchase_date >= one_year_ago).scalar() or 0.0
    return render_template('analysis/procurement.html', total_spent=total_spent)

@app.route('/business_prediction')
@login_required
def business_prediction():
    recent_invoices = Invoice.query.order_by(Invoice.date_created.desc()).limit(10).all()
    return render_template('analysis/prediction.html', recent_invoices=recent_invoices)

@app.route('/business_outlook')
@login_required
def business_outlook():
    upcoming_invoices = Invoice.query.filter(Invoice.status == 'Pending', Invoice.document_type == 'invoice').order_by(Invoice.date_created).limit(5).all()
    return render_template('analysis/business_outlook.html', upcoming_invoices=upcoming_invoices)

# ========================
# Initialize DB
# ========================

@app.before_first_request
def create_tables():
    db.create_all()
    if User.query.filter_by(username='admin').first() is None:
        hashed_pw = bcrypt.generate_password_hash('admin123').decode('utf-8')
        admin = User(username='admin', password=hashed_pw, role='admin', full_name='System Admin')
        db.session.add(admin)
        db.session.commit()
        print("Default admin created: username='admin', password='admin123'")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        get_or_create_company_settings()
    app.run(debug=True, port=8000)