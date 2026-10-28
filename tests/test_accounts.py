import json
import os
import sqlite3
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs

from werkzeug.security import check_password_hash

from accounts import generate_temporary_password
from app import create_app
from database import Connection, migrate
from invitations import DeliveryError, send_temporary_credentials


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = str(Path(self.folder.name) / 'accounts.sqlite3')
        with patch.dict(os.environ, OWNER_NAME='Portal Owner', OWNER_USERNAME='portal.owner', OWNER_EMAIL='owner@example.com', OWNER_PASSWORD='OwnerPassword2026!'):
            config = dict(TESTING=True, DATABASE=self.path, DEMO_MODE=False,
                SECRET_KEY='test-only', PUBLIC_BASE_URL='https://portal.example.com', DATABASE_URL='',
                SMS_PROVIDER='websms', WEBSMS_API_KEY='test-key', WEBSMS_SENDER='HYBRID')
            config.update(self.database_config())
            self.app = create_app(config)
        self.messages = []
        self.sms = patch('app.send_temporary_credentials', side_effect=self.capture)
        self.sms.start()
        self.addCleanup(self.sms.stop)
        self.owner = self.app.test_client()
        self.assertEqual(self.request(self.owner, '/login', dict(username='portal.owner',password='OwnerPassword2026!')).status_code,200)

    def database_config(self):
        return {}

    def connect_db(self):
        return sqlite3.connect(self.path)

    def execute(self, statement, params=()):
        with closing(self.connect_db()) as conn, conn:
            cursor = conn.execute(statement, params)
            return cursor.fetchall() if cursor.description else []

    def capture(self, config, phone, username, password):
        self.messages.append(dict(phone=phone,username=username,password=password))
        return 'test-provider-id'

    def request(self, client, path, data, method='POST'):
        csrf = client.get('/api/session').json['csrf']
        return client.open('/api'+path,method=method,json=data,headers={'X-CSRF-Token':csrf})

    def create(self, **fields):
        data = dict(first_name='John',surname='Smith',email='john@example.com',phone='+35799123456')
        data.update(fields)
        result = self.request(self.owner, '/owner/members', data)
        self.assertEqual(result.status_code,201,result.get_data(as_text=True))
        return result.json

    def sign_in(self, message=None):
        message = message or self.messages[-1]
        client = self.app.test_client()
        result = self.request(client,'/login',dict(username=message['username'],password=message['password']))
        self.assertEqual(result.status_code,200)
        return client

    def test_username_generation_collision_and_greek_random(self):
        first = self.create()
        second = self.create(email='john2@example.com')
        greek = self.create(first_name='Γιώργος',surname='Παπαδόπουλος',email='greek@example.com')
        self.assertEqual(first['username'],'john.smith')
        self.assertEqual(second['username'],'john.smith2')
        self.assertRegex(greek['username'],r'^member-[0-9a-f]{8}$')
        self.assertNotEqual(first['id'],second['id'])

    def test_email_is_optional_and_hidden_internal_placeholder(self):
        member = self.create(email='')
        visible = next(item for item in self.owner.get('/api/owner').json['members'] if item['id'] == member['id'])
        self.assertEqual(visible['email'], '')
        stored = self.execute('SELECT email FROM users WHERE id=?', (member['id'],))[0][0]
        self.assertTrue(stored.endswith('@no-email.invalid'))

    def test_personal_password_has_no_length_or_composition_rules(self):
        member = self.create(email='short-password@example.com')
        temporary = self.messages[-1]['password']
        client = self.sign_in()
        long_password = 'words spaces symbols !@# ' * 20
        self.assertEqual(self.request(client, '/password', {'new_password': long_password}, method='PUT').status_code, 200)
        self.assertEqual(self.request(client, '/password', {'current_password': long_password, 'new_password': ' '}, method='PUT').status_code, 200)
        self.assertEqual(self.request(self.app.test_client(), '/login', {'username': member['username'], 'password': ' '}).status_code, 200)

    def test_temporary_password_is_short_readable_and_mixed(self):
        for _ in range(25):
            password = generate_temporary_password()
            self.assertRegex(password, r'^[A-HJ-NP-Za-km-z2-9]{5}$')
            self.assertRegex(password, r'[A-Z]')
            self.assertRegex(password, r'[a-z]')
            self.assertRegex(password, r'[0-9]')

    def test_first_login_is_restricted_persists_on_reload_and_password_is_hashed(self):
        member = self.create()
        message = self.messages[-1]
        client = self.sign_in()
        other_session = self.sign_in()
        self.assertTrue(client.get('/api/session').json['user']['must_change_password'])
        for path in ('/api/dashboard','/api/owner'):
            self.assertEqual(client.get(path).status_code,403)
        self.assertEqual(self.request(client,'/profile',dict(name='Changed'),method='PUT').status_code,403)
        self.assertEqual(client.put('/api/password',json=dict(new_password='Abcd1234')).status_code,403)
        new_password='Abcd1234'
        self.assertEqual(self.request(client,'/password',dict(new_password=new_password),method='PUT').status_code,200)
        self.assertEqual(client.get('/api/dashboard').status_code,200)
        self.assertEqual(other_session.get('/api/dashboard').status_code,401)
        self.assertEqual(self.request(self.app.test_client(),'/login',dict(username=member['username'],password=message['password'])).status_code,401)
        hashed,required,expiry=self.execute('SELECT password_hash,must_change_password,temporary_password_expires_at FROM users WHERE id=?',(member['id'],))[0]
        self.assertTrue(hashed.startswith('scrypt:'))
        self.assertTrue(check_password_hash(hashed,new_password))
        self.assertEqual((required,expiry),(0,None))
        with closing(self.connect_db()) as conn:
            if hasattr(conn,'iterdump'):
                dump='\n'.join(conn.iterdump())
                self.assertNotIn(new_password,dump)
                self.assertNotIn(message['password'],dump)
        owner_data=json.dumps(self.owner.get('/api/owner').json)
        self.assertNotIn(new_password,owner_data)
        self.assertNotIn(message['password'],owner_data)

    def test_expiry_and_resend_invalidate_old_password_and_restricted_sessions(self):
        member=self.create(); old=dict(self.messages[-1]); client=self.sign_in()
        self.execute('UPDATE users SET temporary_password_expires_at=? WHERE id=?',(int(time.time())-1,member['id']))
        self.assertEqual(self.request(client,'/password',dict(new_password='Abc12345'),method='PUT').status_code,401)
        self.assertEqual(self.request(self.owner,f"/owner/members/{member['id']}/invitation",{}).status_code,429)
        self.execute('UPDATE member_invitations SET last_attempt_at=? WHERE user_id=?',(int(time.time())-61,member['id']))
        result=self.request(self.owner,f"/owner/members/{member['id']}/invitation",{})
        self.assertEqual(result.status_code,200)
        self.assertEqual(self.request(self.app.test_client(),'/login',dict(username=old['username'],password=old['password'])).status_code,401)
        restricted=self.sign_in()
        self.assertEqual(restricted.get('/api/dashboard').status_code,403)
        self.execute('UPDATE member_invitations SET last_attempt_at=? WHERE user_id=?',(int(time.time())-61,member['id']))
        self.assertEqual(self.request(self.owner,f"/owner/members/{member['id']}/invitation",{}).status_code,200)
        self.assertEqual(self.request(restricted,'/password',dict(new_password='Abc12345'),method='PUT').status_code,401)

    def test_username_changes_keep_id_membership_and_progress(self):
        member=self.create(); client=self.sign_in()
        self.request(client,'/password',dict(new_password='Abcd1234'),method='PUT')
        self.execute('INSERT INTO access VALUES(?,?,?)',(member['id'],'2026-11',3))
        self.execute("INSERT INTO progress(user_id,logged_on,kind,exercise,weight,note) VALUES(?,'2026-11-01','bodyweight','Weight',70,'Private')",(member['id'],))
        self.execute("""INSERT INTO classes(id,title,starts_at,duration,capacity,category,coach,description,warmup,main,finisher)
            VALUES(501,'Class','2026-11-01T09:00',50,6,'Strength','Coach','Description','Warmup','Main','Finish')""")
        self.execute('INSERT INTO bookings(user_id,class_id) VALUES(?,501)',(member['id'],))
        result=self.request(client,'/profile',dict(username='JOHN.NEW',name='John Smith',goal='',priority=''),method='PUT')
        self.assertEqual(result.status_code,200)
        self.assertEqual(client.get('/api/session').json['user']['id'],member['id'])
        self.assertEqual(self.request(self.owner,f"/owner/members/{member['id']}/username",dict(username='john.owner.changed'),method='PUT').status_code,200)
        self.assertEqual(self.request(client,f"/owner/members/{member['id']}/username",dict(username='stolen'),method='PUT').status_code,403)
        self.assertEqual(self.request(client,'/profile',dict(username='PORTAL.OWNER',name='John Smith'),method='PUT').status_code,409)
        self.assertEqual(self.request(client,'/profile',dict(username='Ελληνικά',name='John Smith'),method='PUT').status_code,400)
        self.assertEqual(self.execute('SELECT user_id FROM access'),[(member['id'],)])
        self.assertEqual(self.execute('SELECT user_id FROM progress'),[(member['id'],)])
        self.assertEqual(self.execute('SELECT user_id,class_id FROM bookings'),[(member['id'],501)])
        self.assertEqual(self.request(self.app.test_client(),'/login',dict(username='john.smith',password='Abcd1234')).status_code,401)
        self.assertEqual(self.request(self.app.test_client(),'/login',dict(username='john.owner.changed',password='Abcd1234')).status_code,200)

    def test_delivery_failure_keeps_account_and_does_not_expose_password(self):
        self.app.config['DEMO_MODE']=False
        with patch('app.send_temporary_credentials',side_effect=DeliveryError('Η αποστολή δεν επιβεβαιώθηκε.')):
            result=self.create()
        self.assertEqual(result['invitation']['status'],'failed')
        self.assertNotIn('demo_credentials',result)
        self.assertNotIn('temporary_password',result)
        self.assertEqual(self.execute("SELECT COUNT(*) FROM users WHERE role='client'"),[(1,)])

    def test_simultaneous_username_changes_only_one_wins(self):
        first=self.create(); second=self.create(email='second@example.com')
        def change(uid):
            owner=self.app.test_client()
            self.request(owner,'/login',dict(username='portal.owner',password='OwnerPassword2026!'))
            return self.request(owner,f'/owner/members/{uid}/username',dict(username='shared.name'),method='PUT').status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(change,[first['id'],second['id']]))
        self.assertEqual(sorted(results),[200,409])

    def test_simultaneous_creation_allocates_distinct_usernames(self):
        def create(index):
            owner=self.app.test_client()
            self.request(owner,'/login',dict(username='portal.owner',password='OwnerPassword2026!'))
            result=self.request(owner,'/owner/members',dict(name='Same Name',email=f'same{index}@example.com',phone='+35799123456'))
            return result.status_code,result.json.get('username')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(create,[1,2]))
        self.assertEqual(sorted(results),[(201,'same.name'),(201,'same.name2')])

    def test_simultaneous_first_password_changes_only_one_session_wins(self):
        self.create()
        clients=[self.sign_in(),self.sign_in()]
        def change(index):
            return self.request(clients[index],'/password',dict(new_password=f'Pass{index}x7'),method='PUT').status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(change,[0,1]))
        self.assertEqual(sorted(results),[200,401])


class UsernameMigrationTests(unittest.TestCase):
    def test_existing_ids_passwords_and_foreign_keys_survive_migration(self):
        with tempfile.TemporaryDirectory() as folder:
            config=dict(DATABASE=str(Path(folder)/'legacy.sqlite3'),DATABASE_URL='')
            connection=Connection(config)
            try:
                for filename in ('001_initial.sql','002_sessions_and_login_limits.sql'):
                    for statement in (Path(__file__).parents[1]/'migrations'/filename).read_text(encoding='utf-8').split(';'):
                        if statement.strip(): connection.execute(statement)
                connection.execute('CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY,applied_at BIGINT NOT NULL)')
                connection.execute('INSERT INTO schema_migrations VALUES(2,0)')
                for uid in (41,42):
                    connection.execute("INSERT INTO users(id,name,email,password_hash,role) VALUES(?,'Γιάννης Γεωργίου',?,'existing-hash','client')",(uid,f'{uid}@example.com'))
                connection.execute("INSERT INTO access VALUES(41,'2026-11',3)")
                connection.commit()
                migrate(connection);connection.commit()
                migrate(connection);connection.commit()
                rows=connection.execute('SELECT id,username,password_hash,must_change_password FROM users ORDER BY id').fetchall()
                self.assertEqual([r['id'] for r in rows],[41,42])
                self.assertNotEqual(rows[0]['username'],rows[1]['username'])
                for row in rows:
                    self.assertRegex(row['username'],r'^member-[0-9a-f]{8}$')
                    self.assertEqual(row['password_hash'],'existing-hash')
                    self.assertEqual(row['must_change_password'],0)
                self.assertEqual(connection.execute('SELECT user_id FROM access').fetchone()[0],41)
                self.assertEqual(connection.execute('PRAGMA foreign_key_check').fetchall(),[])
            finally:
                connection.close()


class CredentialDeliveryTests(unittest.TestCase):
    @patch('invitations.urlopen')
    def test_sms_body_contains_credentials_without_url_or_storage_leaks(self, sender):
        sender.return_value.__enter__.return_value.read.return_value=b'{"status":"ok"}'
        config=dict(DEMO_MODE=False,PUBLIC_BASE_URL='https://portal.example.com',SMS_PROVIDER='websms',WEBSMS_API_KEY='test-key',WEBSMS_SENDER='HYBRID')
        send_temporary_credentials(config,'+35799123456','john.smith','TemporarySecret!')
        request=sender.call_args.args[0]
        body=parse_qs(request.data.decode())
        self.assertIn('john.smith',body['message'][0])
        self.assertIn('TemporarySecret!',body['message'][0])
        self.assertIn('Valid 24h',body['message'][0])
        self.assertNotIn('http',body['message'][0])
        self.assertNotIn('portal.example.com',body['message'][0])
        self.assertLess(len(body['message'][0]),80)
        self.assertNotIn('TemporarySecret!',request.full_url)
