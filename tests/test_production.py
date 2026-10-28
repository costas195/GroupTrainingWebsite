import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from unittest.mock import patch

from app import create_app
from database import SCHEMA_VERSION


class ProductionConfigTests(unittest.TestCase):
    def config(self, **changes):
        config = dict(TESTING=True, AUTO_MIGRATE=False, APP_ENV='production', DEMO_MODE=False,
                      DATABASE_URL='postgresql://test:test@localhost/test', SECRET_KEY='x' * 64,
                      PUBLIC_BASE_URL='https://gym.example.com', SMS_PROVIDER='websms',
                      WEBSMS_API_KEY='test-only-key', WEBSMS_SENDER='NF Hybrid')
        config.update(changes)
        return config

    def test_live_configuration_fails_closed(self):
        for change in (dict(DEMO_MODE=True), dict(DATABASE_URL=''), dict(SECRET_KEY='short'),
                       dict(DATABASE_SSLMODE='disable'), dict(WEBSMS_API_KEY=''), dict(WEBSMS_SENDER='')):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                create_app(self.config(**change))
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(RuntimeError):
            config = self.config()
            del config['SECRET_KEY']
            create_app(config)

    def test_secure_cookies_hsts_and_host_allowlist(self):
        app = create_app(self.config())
        self.assertTrue(app.config['SESSION_COOKIE_SECURE'])
        self.assertEqual(app.test_client().get('/', base_url='https://gym.example.com').status_code, 200)
        self.assertEqual(app.test_client().get('/', base_url='https://attacker.example.com').status_code, 400)
        response = app.test_client().get('/', base_url='https://gym.example.com')
        self.assertEqual(response.headers['Strict-Transport-Security'], 'max-age=31536000')
        self.assertEqual(response.headers['X-Robots-Tag'], 'noindex, nofollow, nosnippet')
        robots = app.test_client().get('/robots.txt', base_url='https://gym.example.com')
        self.assertEqual(robots.status_code, 200)
        self.assertIn('Disallow: /', robots.get_data(as_text=True))

    def test_predeploy_initialization_preserves_owner_on_repeated_runs(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'live.sqlite3')
            config = dict(TESTING=True, AUTO_MIGRATE=False, DATABASE=path, DATABASE_URL='', DEMO_MODE=False)
            with patch.dict(os.environ, {'OWNER_EMAIL': 'owner@example.com', 'OWNER_PASSWORD': 'OwnerPassword2026!'}):
                app = create_app(config)
                app.extensions['initialize_database']()
            with patch.dict(os.environ, {'OWNER_EMAIL': '', 'OWNER_PASSWORD': ''}):
                app.extensions['initialize_database']()
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute('SELECT COUNT(*) FROM users').fetchone()[0], 1)
                self.assertEqual(connection.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0], SCHEMA_VERSION)

    def test_login_limits_are_shared_across_app_processes(self):
        with tempfile.TemporaryDirectory() as folder:
            config = dict(TESTING=True, DATABASE=str(Path(folder) / 'demo.sqlite3'), DATABASE_URL='', DEMO_MODE=True)
            first, second = create_app(config).test_client(), create_app(config).test_client()
            csrf1, csrf2 = first.get('/api/session').json['csrf'], second.get('/api/session').json['csrf']
            for index in range(15):
                client, token = (first, csrf1) if index % 2 else (second, csrf2)
                self.assertEqual(client.post('/api/login', json=dict(email='client@form.demo', password='wrong'), headers={'X-CSRF-Token': token}).status_code, 401)
            self.assertEqual(first.post('/api/login', json=dict(email='client@form.demo', password='FormDemo2026!'), headers={'X-CSRF-Token': csrf1}).status_code, 429)

    def test_password_change_revokes_other_sessions(self):
        with tempfile.TemporaryDirectory() as folder:
            app = create_app(dict(TESTING=True, DATABASE=str(Path(folder) / 'demo.sqlite3'), DATABASE_URL='', DEMO_MODE=True))
            first, second = app.test_client(), app.test_client()
            for client in (first, second):
                token = client.get('/api/session').json['csrf']
                client.post('/api/login', json=dict(email='client@form.demo', password='FormDemo2026!'), headers={'X-CSRF-Token': token})
            token = first.get('/api/session').json['csrf']
            response = first.put('/api/password', json=dict(current_password='FormDemo2026!', new_password='Prod1234'), headers={'X-CSRF-Token': token})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(first.get('/api/dashboard').status_code, 200)
            self.assertEqual(second.get('/api/dashboard').status_code, 401)
