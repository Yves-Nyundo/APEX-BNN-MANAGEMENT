import unittest
import os
from app import app, db
from models import User, Client

class AppTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
        self.app = app.test_client()
        with app.app_context():
            db.create_all()

    def test_login_success(self):
        rv = self.app.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
        self.assertIn(b'Dashboard', rv.data)

    def test_dashboard_requires_login(self):
        rv = self.app.get('/dashboard', follow_redirects=True)
        self.assertIn(b'Login', rv.data)

    def tearDown(self):
        with app.app_context():
            db.drop_all()

if __name__ == '__main__':
    unittest.main()