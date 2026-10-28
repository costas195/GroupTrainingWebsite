import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from app import create_app
from localization import localize_demo


class PortalTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.folder.name, 'test.sqlite3')
        self.app = create_app(self.app_config())
        self.client = self.signed_in('client@form.demo')
        self.owner = self.signed_in('owner@form.demo')
        # A clean future week, independent of the seeded demo schedule.
        today = datetime.now()
        self.start = (today + timedelta(days=100)).replace(hour=10, minute=0, second=0, microsecond=0)
        self.start -= timedelta(days=self.start.weekday())
        # Move away from a month boundary so all limit test sessions share a month.
        if self.start.day > 25:
            self.start += timedelta(days=7)
        self.month = self.start.strftime('%Y-%m')
        with closing(self.connect_db()) as db, db:
            db.execute('DELETE FROM bookings')
            db.execute('DELETE FROM classes')
            db.execute('INSERT INTO access VALUES(1,?,2) ON CONFLICT(user_id,month) DO UPDATE SET weekly_limit=excluded.weekly_limit', (self.month,))
            db.execute('INSERT INTO access VALUES(3,?,3) ON CONFLICT(user_id,month) DO UPDATE SET weekly_limit=excluded.weekly_limit', (self.month,))

    def app_config(self):
        return {'TESTING': True, 'DATABASE': self.path, 'DATABASE_URL': '', 'SECRET_KEY': 'test-only', 'DEMO_MODE': True}

    def connect_db(self):
        return sqlite3.connect(self.path)

    def tearDown(self):
        self.folder.cleanup()

    def signed_in(self, email):
        client = self.app.test_client()
        token = client.get('/api/session').json['csrf']
        result = client.post('/api/login', json={'email': email, 'password': 'FormDemo2026!'}, headers={'X-CSRF-Token': token})
        self.assertEqual(result.status_code, 200)
        return client

    def mutate(self, client, path, body=None, method='POST'):
        with client.session_transaction() as session:
            token = session['csrf']
        return client.open('/api' + path, method=method, json=body, headers={'X-CSRF-Token': token})

    def new_class(self, day=0, capacity=6, minute=0):
        start = self.start + timedelta(days=day, minutes=minute)
        data = dict(title='Test strength', starts_at=start.isoformat(timespec='minutes'), duration=50, capacity=capacity, category='Strength', coach='Jamie', description='A focused training session.', warmup='Easy row and mobility', main='Squat 4 x 6', finisher='Gentle stretch')
        result = self.mutate(self.owner, '/owner/classes', data)
        self.assertEqual(result.status_code, 200, result.json)
        with closing(self.connect_db()) as db, db:
            return db.execute('SELECT MAX(id) FROM classes').fetchone()[0]

    def book(self, cls, client=None):
        return self.mutate(client or self.client, '/bookings', {'class_id': cls})

    def test_login_csrf_and_role_boundaries(self):
        anonymous = self.app.test_client()
        self.assertEqual(anonymous.get('/api/dashboard').status_code, 401)
        self.assertEqual(self.client.post('/api/bookings', json={'class_id': 1}).status_code, 403)
        self.assertEqual(self.client.get('/api/owner').status_code, 403)
        self.assertEqual(self.mutate(self.client, '/owner/classes', {}).status_code, 403)
        self.assertEqual(self.mutate(self.owner, '/bookings', {'class_id': 1}).status_code, 403)

    def test_month_access_controls_visibility_and_booking(self):
        cls = self.new_class()
        self.assertEqual(len(self.client.get('/api/dashboard?month=' + self.month).json['classes']), 1)
        self.mutate(self.owner, f'/owner/members/1/access/{self.month}', method='DELETE')
        self.assertEqual(self.client.get('/api/dashboard?month=' + self.month).json['classes'], [])
        self.assertEqual(self.book(cls).status_code, 403)

    def test_weekly_limit_duplicate_and_cancellation(self):
        one, two, three = [self.new_class(day=i) for i in range(3)]
        self.assertEqual(self.book(one).status_code, 201)
        self.assertEqual(self.book(one).status_code, 409)
        self.assertEqual(self.book(two).status_code, 201)
        self.assertEqual(self.book(three).status_code, 409)
        booking_id = self.client.get('/api/dashboard?month=' + self.month).json['bookings'][0]['booking_id']
        other = self.signed_in('sofia@form.demo')
        self.assertEqual(self.mutate(other, f'/bookings/{booking_id}', method='DELETE').status_code, 404)
        self.assertEqual(self.mutate(self.client, f'/bookings/{booking_id}', method='DELETE').status_code, 200)
        self.assertEqual(self.book(three).status_code, 201)

    def test_capacity_is_atomic_under_competing_bookings(self):
        cls = self.new_class(capacity=1)
        clients = [self.signed_in(email) for email in ('client@form.demo', 'sofia@form.demo')]
        with ThreadPoolExecutor(max_workers=2) as executor:
            codes = list(executor.map(lambda client: self.book(cls, client).status_code, clients))
        self.assertEqual(sorted(codes), [201, 409])
        with closing(self.connect_db()) as db, db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM bookings WHERE class_id=?', (cls,)).fetchone()[0], 1)

    def test_overlapping_classes_are_rejected(self):
        first = self.new_class()
        second = self.new_class(minute=20)
        self.assertEqual(self.book(first).status_code, 201)
        self.assertEqual(self.book(second).status_code, 409)

    def test_revoke_releases_future_places(self):
        cls = self.new_class()
        self.assertEqual(self.book(cls).status_code, 201)
        self.assertEqual(self.mutate(self.owner, f'/owner/members/1/access/{self.month}', method='DELETE').status_code, 200)
        self.assertEqual(self.client.get('/api/dashboard').json['bookings'], [])

    def test_access_across_year_boundary_and_lower_limit(self):
        result = self.mutate(self.owner, '/owner/members/1/access', {'month': '2027-12', 'months': 3, 'weekly_limit': 4}, method='PUT')
        self.assertEqual(result.status_code, 200)
        access = self.client.get('/api/dashboard').json['access']
        self.assertTrue(all(any(a['month'] == month and a['weekly_limit'] == 4 for a in access) for month in ['2027-12', '2028-01', '2028-02']))

    def test_member_creation_and_private_progress(self):
        data = dict(name='Test Member', email='new@example.com', phone='+35799123456', password='Temporary2026!', goal='Stronger', priority='Technique')
        result = self.mutate(self.owner, '/owner/members', data)
        self.assertEqual(result.status_code, 201)
        self.assertEqual(self.mutate(self.owner, '/owner/members', data).status_code, 409)
        today = datetime.now().date().isoformat()
        self.assertEqual(self.mutate(self.client, '/progress', dict(kind='lift', logged_on=today, exercise='Deadlift', weight=60, reps=5, note='Good session')).status_code, 201)
        logs = self.client.get('/api/dashboard').json['logs']
        other = self.signed_in('sofia@form.demo')
        self.assertEqual(other.get('/api/dashboard').json['logs'], [])
        self.assertEqual(self.mutate(other, '/progress/' + str(logs[-1]['id']), method='DELETE').status_code, 404)
        invalid = self.mutate(self.client, '/progress', dict(kind='bodyweight', logged_on=today, weight='NaN', note=''))
        self.assertEqual(invalid.status_code, 400)

    def test_booked_class_cannot_shrink_or_move(self):
        cls = self.new_class()
        self.book(cls)
        self.book(cls, self.signed_in('sofia@form.demo'))
        data = dict(title='Updated class', starts_at=self.start.isoformat(timespec='minutes'), duration=50, capacity=1, category='Strength', coach='Jamie', description='A focused session.', warmup='Mobility', main='Squats', finisher='Stretch')
        self.assertEqual(self.mutate(self.owner, f'/owner/classes/{cls}', data, 'PUT').status_code, 400)
        data.update(capacity=6, starts_at=(self.start + timedelta(hours=1)).isoformat(timespec='minutes'))
        self.assertEqual(self.mutate(self.owner, f'/owner/classes/{cls}', data, 'PUT').status_code, 400)
        self.assertEqual(self.mutate(self.owner, f'/owner/classes/{cls}', method='DELETE').status_code, 200)
        self.assertEqual(self.client.get('/api/dashboard').json['bookings'], [])

    def test_future_attendance_rejected_and_demo_can_be_disabled(self):
        cls = self.new_class()
        self.book(cls)
        bid = self.client.get('/api/dashboard').json['bookings'][0]['booking_id']
        self.assertEqual(self.mutate(self.owner, f'/owner/bookings/{bid}', {'attended': True}, 'PUT').status_code, 400)
        self.app.config['DEMO_MODE'] = False
        self.assertEqual(self.client.get('/api/dashboard').status_code, 401)
        self.assertIsNone(self.client.get('/api/session').json['user'])
        fresh = self.app.test_client()
        token = fresh.get('/api/session').json['csrf']
        result = fresh.post('/api/login', json={'email': 'owner@form.demo', 'password': 'FormDemo2026!'}, headers={'X-CSRF-Token': token})
        self.assertEqual(result.status_code, 403)


    def test_greek_interface_and_validation(self):
        anonymous = self.app.test_client()
        page = anonymous.get('/').get_data(as_text=True)
        self.assertIn('lang="el"', page)
        self.assertIn('<title>Σύνδεση</title>', page)
        self.assertEqual(anonymous.get('/api/dashboard').json['error'], 'Συνδέσου για να συνεχίσεις.')
        self.assertEqual(self.client.get('/api/dashboard').json['user']['name'], 'Αλέξανδρος Δημητρίου')
        result = self.mutate(self.client, '/progress', {'kind':'bodyweight','logged_on':datetime.now().date().isoformat(),'weight':'NaN','note':''})
        self.assertEqual(result.status_code, 400)
        self.assertIn('Βάρος',result.json['error'])

    def test_greek_demo_migration_preserves_bookings_and_custom_content(self):
        cls = self.new_class()
        self.assertEqual(self.book(cls).status_code, 201)
        with closing(self.connect_db()) as connection, connection:
            connection.row_factory = sqlite3.Row
            before = [dict(row) for row in connection.execute('SELECT * FROM bookings')]
            connection.execute("DELETE FROM app_settings WHERE key='demo_locale'")
            connection.execute("UPDATE users SET goal='Ο δικός μου στόχος' WHERE id=1")
            connection.execute("UPDATE classes SET title='Engine room',coach='Jamie',description='Find your pace with a coach-led mix of cardio and functional strength.',main='Το δικό μου πρόγραμμα' WHERE id=?",(cls,))
            localize_demo(connection)
            row = connection.execute('SELECT * FROM classes WHERE id=?',(cls,)).fetchone()
            self.assertEqual(row['title'],'Χτίσιμο αντοχής')
            self.assertEqual(row['coach'],'Γιάννης')
            self.assertEqual(row['main'],'Το δικό μου πρόγραμμα')
            self.assertEqual(connection.execute('SELECT goal FROM users WHERE id=1').fetchone()[0],'Ο δικός μου στόχος')
            self.assertEqual(before,[dict(row) for row in connection.execute('SELECT * FROM bookings')])
            localize_demo(connection)
            self.assertEqual(before,[dict(row) for row in connection.execute('SELECT * FROM bookings')])

if __name__ == '__main__':
    unittest.main()
