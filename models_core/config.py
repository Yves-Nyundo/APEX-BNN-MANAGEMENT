import os
from datetime import timedelta
from dotenv import load_dotenv

# Optional: Load .env early
load_dotenv()

# Optional: Debug token generation
if os.getenv("PRINT_SECRET_TOKEN", "false").lower() == "true":
    import secrets
    print("🔐 Generated token:", secrets.token_urlsafe(32))


class Config:
    """Base configuration (shared by all environments)"""
    
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-please-change-12345')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)

    # CSRF Protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_SECRET_KEY = os.environ.get('WTF_CSRF_SECRET_KEY', 'another-dev-secret-change-me')
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour

    # Uploads - ✅ Fixed: Clear path logic
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')  # ✅ Always /your-app/static/uploads
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx', 'xlsx', 'csv'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    # Email (keep as-is)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'no-reply@apexbnn.com')

    # AWS S3 (optional)
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_S3_BUCKET = os.environ.get('AWS_S3_BUCKET')
    AWS_S3_REGION = os.environ.get('AWS_S3_REGION', 'us-east-1')
    AWS_S3_CUSTOM_DOMAIN = (
        f"{AWS_S3_BUCKET}.s3.{AWS_S3_REGION}.amazonaws.com"
        if AWS_S3_BUCKET else None
    )

    # PDF Generation
    PDF_GENERATION_ENGINE = os.environ.get('PDF_GENERATION_ENGINE', 'weasyprint')

    def validate(self):
        if not self.SECRET_KEY or len(self.SECRET_KEY) < 16:
            raise ValueError("SECRET_KEY must be set and secure")
        if not self.WTF_CSRF_SECRET_KEY:
            raise ValueError("WTF_CSRF_SECRET_KEY must be set")
        if not hasattr(self, 'SQLALCHEMY_DATABASE_URI') or not self.SQLALCHEMY_DATABASE_URI:
            raise ValueError("SQLALCHEMY_DATABASE_URI must be set")


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///apex_bnn.db')
    SESSION_TYPE = os.environ.get('SESSION_TYPE', 'filesystem')


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    PRESERVE_CONTEXT_ON_EXCEPTION = False


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')

    def validate(self):
        super().validate()
        if not self.SQLALCHEMY_DATABASE_URI:
            raise ValueError("DATABASE_URL is required in production")


# Shortcut dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
