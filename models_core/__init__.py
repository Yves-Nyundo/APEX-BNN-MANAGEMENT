# models_core/__init__.py
print("✅ LOADING: models_core/__init__.py")

import os
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_wtf.csrf import CSRFProtect
from flask_babel import Babel, _
from flask_login import LoginManager, current_user, login_required

# ✅ Single db instance
db = SQLAlchemy()
bcrypt = Bcrypt()
csrf = CSRFProtect()
babel = Babel()
login_manager = LoginManager()
# Config
from .config import config as app_config


def get_locale():
    return request.args.get('lang') or request.accept_languages.best_match(
        app_config['default'].BABEL_SUPPORTED_LOCALES or ['en']
    )




def create_default_admin():
    from .models import User
    from sqlalchemy import select

    stmt = select(User).where(User.username == 'admin')
    result = db.session.execute(stmt)
    existing = result.scalar()

    if existing:
        print("ℹ️ Admin already exists.")
        return

    hashed_pw = bcrypt.generate_password_hash('admin123').decode('utf-8')
    admin = User(
        username='admin',
        password=hashed_pw,
        role='admin',
        full_name='System Admin'
    )
    db.session.add(admin)
    db.session.commit()
    print("✅ Default admin created!")
        
def create_app(config_name=None):
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
        static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    )

    # ✅ Define UPLOAD_FOLDER as absolute path to static/uploads/
    upload_folder = os.path.join(app.static_folder, 'uploads')
    app.config['UPLOAD_FOLDER'] = upload_folder  # No trailing comma!
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    print("📁 UPLOAD_FOLDER =", app.config['UPLOAD_FOLDER'])  # Debug print

    # Load config
    env = config_name or os.getenv('FLASK_ENV') or 'production'
    print(f"🚀 [models_core] FINAL env = {repr(env)}")

    config_class = app_config.get(env)
    if not config_class:
        raise ValueError(f"Unknown config: {env}")

    config_instance = config_class()
    config_instance.validate()
    app.config.from_object(config_instance)

    print(f"🔧 Loaded config: {env}")
    print(f"📦 Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")

    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = 'dev-key-please-change-12345'

    # ✅ Initialize extensions
    db.init_app(app)
    print("✅ db.init_app(app) called — id(db) =", id(db))

    bcrypt.init_app(app)
    csrf.init_app(app)
    babel.init_app(app, locale_selector=get_locale)

    login_manager.init_app(app)
    login_manager.login_view = 'login'
    login_manager.login_message = "Please log in to access this page."

    @login_manager.user_loader
    def load_user(user_id):
        from .models import User
        return db.session.get(User, int(user_id))

    @app.context_processor
    def inject_translator():
        return dict(_=_)

    from .cli import register_commands
    register_commands(app)

    return app
# models_core/__init__.py — add at the very bottom

# 🔽 Expose models for easy import
from .models import (
    User,
    Client,
    Supplier,
    Invoice,
    InvoiceItem,
    ProcurementItem,
    Bid,
    Competitor,
    CompetitorBid,
    OurProductService,
    LocalMarketItem,
    CompanySettings,
    Attachment,
    InventoryItem,
    InventoryStatus,
    get_or_create_company_settings,
)

# # models_core/__init__.py
# print("✅ LOADING: models_core/__init__.py")
# import os
# from flask import Flask, request
# from flask_sqlalchemy import SQLAlchemy
# from flask_bcrypt import Bcrypt
# from flask_wtf.csrf import CSRFProtect
# from flask_babel import Babel, _


# # ✅ Define db here — no need for base.py
# db = SQLAlchemy()
# bcrypt = Bcrypt()
# csrf = CSRFProtect()
# babel = Babel()

# # Import config after db to avoid circular issues
# from .config import config as app_config  # Use the config dict


# def get_locale():
#     return request.args.get('lang') or request.accept_languages.best_match(
#         app_config['default'].BABEL_SUPPORTED_LOCALES
#         if hasattr(app_config['default'], 'BABEL_SUPPORTED_LOCALES')
#         else ['en']
#     )


# def create_app(config_name=None):
#     app = Flask(
#         __name__,
#         template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
#         static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
#     )

#     # ✅ 1. Load and validate config
#     print("🚀 [models_core] INIT LOADED — PID:", os.getpid())
#     print("🚀 [models_core] config_name =", repr(config_name))
#     env = config_name or os.getenv('FLASK_ENV') or 'production'
#     print("🚀 [models_core] FINAL env =", repr(env))
#     config_class = app_config.get(env)
#     if not config_class:
#         raise ValueError(f"Unknown config: {env}")

#     config_instance = config_class()         # Instantiate config
#     config_instance.validate()               # Run sanity checks
#     app.config.from_object(config_instance)  # Load resolved values

#     # Optional: Log active config
#     print(f"🔧 Loaded config: {env}")
#     print(f"📦 Database URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")

#     # ✅ 2. Set SECRET_KEY if not set
#     if not app.config.get('SECRET_KEY'):
#         app.config['SECRET_KEY'] = 'dev-key-please-change-12345'

#     # ✅ 3. Initialize extensions
#     db.init_app(app)
#     bcrypt.init_app(app)
#     csrf.init_app(app)
#     babel.init_app(app, locale_selector=get_locale)
#     print("🚀 [models_core] db.init_app(app) called — db =", id(db))
#     # ✅ 4. Add translation to templates
#     @app.context_processor
#     def inject_translator():
#         return dict(_=_)

#     # ✅ 5. Import models and create tables
#     with app.app_context():
#         from models_core.models import (
#             User, Client, Supplier, Invoice, InvoiceItem, ProcurementItem,
#             Bid, Competitor, CompetitorBid, OurProductService, LocalMarketItem,
#             CompanySettings, Attachment, InventoryItem, InventoryStatus, get_or_create_company_settings,
#         )
#         db.create_all()

#         from .cli import register_commands
#         register_commands(app)

#     # ✅ 6. Expose models for CLI or admin use
#     # app.models = {cls.__name__: cls for cls in [
#     #     User, Client, Supplier, Invoice, InvoiceItem, ProcurementItem,
#     #     Bid, Competitor, CompetitorBid, OurProductService, LocalMarketItem,
#     #     CompanySettings, Attachment, InventoryItem, InventoryStatus
#     # ]}

#     return app
# from .models import (
#     User, Client, Supplier, Invoice, InvoiceItem, ProcurementItem,
#     Bid, Competitor, CompetitorBid, OurProductService, LocalMarketItem,
#     CompanySettings, Attachment, InventoryItem, InventoryStatus,get_or_create_company_settings
# )
