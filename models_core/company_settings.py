from .base import db

class CompanySettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    signature_image_path = db.Column(db.String(500))
    signature_description = db.Column(db.String(255))
    stamp_image_path = db.Column(db.String(500))
    signing_person_name = db.Column(db.String(100))
    signing_person_function = db.Column(db.String(100))
    logo_image_path = db.Column(db.String(500))
