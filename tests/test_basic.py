import unittest
import os
import shutil
from app import create_app, db
from app.models import User, Work
import config

class TestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:', 'WTF_CSRF_ENABLED': False})
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_home(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_register_login(self):
        # Register
        response = self.client.post('/register', data={
            'username': 'testuser',
            'password': 'password'
        }, follow_redirects=True)
        self.assertIn(b'Registration successful', response.data)

        # Login
        response = self.client.post('/login', data={
            'username': 'testuser',
            'password': 'password'
        }, follow_redirects=True)
        self.assertIn(b'testuser', response.data) # Assuming username is shown in navbar

        # Check admin (first user should be admin)
        user = User.query.filter_by(username='testuser').first()
        self.assertTrue(user.is_admin)

    def test_work_model(self):
        work = Work(id=123, title='Test Work', user_id=1, user_name='Artist')
        db.session.add(work)
        db.session.commit()

        w = Work.query.get(123)
        self.assertIsNotNone(w)
        self.assertEqual(w.title, 'Test Work')

if __name__ == '__main__':
    unittest.main()
