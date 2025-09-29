
# apex/cli.py

from flask import Flask
from .config import Config
from .base import db  # assuming this is your SQLAlchemy instance

def register_commands(app):
    @app.cli.command("reset-db")
    def reset_db():
        with app.app_context():
            db.drop_all()
            db.create_all()
            print("✅ Database reset complete.")
