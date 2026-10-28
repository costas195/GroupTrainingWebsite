import hashlib
import json
import os
import sqlite3
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from unittest.mock import patch
from urllib.error import URLError
from urllib.parse import parse_qs

from app import create_app


class InvitationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = os.path.join(self.folder.name, 'live.sqlite3')
        with patch.dict(os.environ, {'OWNER_EMAIL': 'owner@example.com', 'OWNER_PASSWORD': 'OwnerPassword2026!'}):
            self.app = create_app({
                'TESTING': True, 'DATABASE': self.path, 'SECRET_KEY': 'test-only', 'DEMO_MODE': False,
                **self.database_config(),
                'PUBLIC_BASE_URL': 'https://gym.example.com', 'RESEND_API_KEY': 'test-email-key',
                'INVITE_FROM_EMAIL': 'FORM <members@example.com>',
                'SMS_PROVIDER': 'twilio',
                'TWILIO_ACCOUNT_SID': 'AC' + 'a' * 32, 'TWILIO_AUTH_TOKEN': 'test-sms-key',
                'TWILIO_FROM_NUMBER': '+306900000000',
            })
        self.owner = self.app.test_client()
        self.assertEqual(self.post(self.owner, '/login', {
            'email': 'owner@example.com', 'password': 'OwnerPassword2026!'}).status_code, 200)
        self.messages = []
        self.sender = patch('app.send_invitation', side_effect=self.capture).start()
        self.sms_sender = patch('app.send_temporary_credentials', side_effect=self.capture_credentials).start()
        self.addCleanup(patch.stopall)

    def database_config(self):
        return {'DATABASE_URL': ''}

    def connect_db(self):
        return sqlite3.connect(self.path)

    def capture(self, config, channel, recipient, email, link):
        self.messages.append(dict(channel=channel, recipient=recipient, email=email, link=link))
        return 'provider-message-id'

    def capture_credentials(self, config, recipient, username, password):
        self.messages.append(dict(channel='sms', recipient=recipient, username=username, password=password))
        return 'provider-sms-id'

    def post(self, client, path, data):
        csrf = client.get('/api/session').json['csrf']
        return client.post('/api' + path, json=data, headers={'X-CSRF-Token': csrf})

    def create(self, **fields):
        payload = dict(name='New Member', email='member@example.com', delivery_channel='email')
        payload.update(fields)
        return self.post(self.owner, '/owner/members', payload)

    def token(self, index=-1):
        return self.messages[index]['link'].split('#activate=')[1]

    def accept(self, token, password='MyPrivatePassword2026!'):
        return self.post(self.app.test_client(), '/invitations/accept', dict(token=token, new_password=password))

    def execute(self, sql, parameters=()):
        with closing(self.connect_db()) as connection, connection:
            return connection.execute(sql, parameters).fetchall()

    def allow_resend(self):
        self.execute('UPDATE member_invitations SET last_attempt_at=?', (int(time.time()) - 61,))

    def test_email_invitation_password_activation_and_single_use(self):
        result = self.create(password='OwnerChosenPassword!')
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.json['invitation']['status'], 'accepted')
        self.assertNotIn('token', result.get_data(as_text=True))
        self.assertNotIn('demo_activation_url', result.json)
        self.assertEqual(self.messages[0]['recipient'], 'member@example.com')
        token = self.token()
        self.assertEqual(self.execute('SELECT token_hash FROM member_invitations')[0][0], hashlib.sha256(token.encode()).hexdigest())
        self.assertEqual(self.app.test_client().get('/api/invitations/accept').status_code, 405)
        self.assertEqual(self.post(self.app.test_client(), '/login', dict(email='member@example.com', password='OwnerChosenPassword!')).status_code, 401)
        self.assertEqual(self.accept(token).status_code, 200)
        self.assertEqual(self.accept(token).status_code, 400)
        self.assertEqual(self.execute('SELECT token_hash,status FROM member_invitations'), [(None, 'used')])
        self.assertEqual(self.post(self.app.test_client(), '/login', dict(email='member@example.com', password='MyPrivatePassword2026!')).status_code, 200)
        self.allow_resend()
        self.assertEqual(self.post(self.owner, f"/owner/members/{result.json['id']}/invitation", {}).status_code, 409)

    def test_sms_uses_phone_and_generated_username(self):
        result = self.create(delivery_channel='sms', phone='+306912345678')
        self.assertEqual(result.status_code, 201)
        self.assertEqual(self.messages[0]['channel'], 'sms')
        self.assertEqual(self.messages[0]['recipient'], '+306912345678')
        self.assertEqual(self.messages[0]['username'], 'new.member')

    def test_websms_configuration_for_cyprus_members(self):
        self.app.config.update(SMS_PROVIDER='websms', WEBSMS_API_KEY='test-websms-key', WEBSMS_SENDER='FORM')
        self.assertEqual(self.create(delivery_channel='sms', phone='+35799123456').status_code, 201)
        self.assertEqual(self.messages[0]['recipient'], '+35799123456')

    def test_invalid_contact_or_unconfigured_channel_does_not_create_member(self):
        for data in [dict(delivery_channel='sms', phone='6912345678'), dict(delivery_channel='push'), dict(email='bad\n@example.com')]:
            payload = dict(name='New Member', email='member@example.com')
            payload.update(data)
            self.assertEqual(self.post(self.owner, '/owner/members', payload).status_code, 400)
        self.app.config['RESEND_API_KEY'] = ''
        self.assertEqual(self.create().status_code, 503)
        self.assertEqual(self.execute("SELECT COUNT(*) FROM users WHERE role='client'"), [(0,)])
        self.sender.assert_not_called()

    def test_expired_link_and_invalid_password_do_not_activate(self):
        self.create()
        token = self.token()
        self.assertEqual(self.accept(token, 'short').status_code, 400)
        self.execute('UPDATE member_invitations SET expires_at=?', (int(time.time()) - 1,))
        self.assertEqual(self.accept(token).status_code, 400)
        self.assertEqual(self.accept('invalid-token').status_code, 400)
        self.assertEqual(self.execute('SELECT used_at FROM member_invitations'), [(None,)])

    def test_resend_can_switch_channel_and_invalidates_old_link(self):
        uid = self.create().json['id']
        old_token = self.token()
        self.assertEqual(self.post(self.owner, f'/owner/members/{uid}/invitation', {}).status_code, 429)
        self.allow_resend()
        result = self.post(self.owner, f'/owner/members/{uid}/invitation', dict(delivery_channel='sms', phone='+306912345678'))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['invitation']['channel'], 'sms')
        self.assertEqual(self.accept(old_token).status_code, 400)
        self.assertEqual(self.messages[-1]['username'], 'new.member')
        self.assertEqual(self.post(self.app.test_client(), '/login', dict(username='new.member',password=self.messages[-1]['password'])).json['password_change_required'], True)

    def test_delivery_failure_keeps_member_and_allows_retry(self):
        from invitations import DeliveryError
        self.sender.side_effect = DeliveryError('Η αποστολή δεν επιβεβαιώθηκε.')
        result = self.create()
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.json['invitation']['status'], 'failed')
        self.assertIn('delivery_error', result.json)
        self.assertEqual(self.execute("SELECT COUNT(*) FROM users WHERE role='client'"), [(1,)])
        self.assertEqual(self.create().status_code, 409)
        self.assertEqual(self.sender.call_count, 1)
        self.sender.side_effect = self.capture
        self.allow_resend()
        self.assertEqual(self.post(self.owner, f"/owner/members/{result.json['id']}/invitation", {}).json['invitation']['status'], 'accepted')

    def test_owner_only_actions_and_activation_csrf(self):
        uid = self.create().json['id']
        guest = self.app.test_client()
        self.assertEqual(self.post(guest, '/owner/members', {}).status_code, 401)
        self.assertEqual(guest.post('/api/invitations/accept', json=dict(token=self.token(), new_password='MyPassword2026!')).status_code, 403)
        self.accept(self.token())
        self.post(guest, '/login', dict(email='member@example.com', password='MyPrivatePassword2026!'))
        self.assertEqual(self.post(guest, '/owner/members', {}).status_code, 403)
        self.assertEqual(self.post(guest, f'/owner/members/{uid}/invitation', {}).status_code, 403)

    def test_concurrent_activation_only_one_password_wins(self):
        self.create()
        token = self.token()
        passwords = ['FirstPrivatePassword!', 'SecondPrivatePassword!']
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda password: self.accept(token, password).status_code, passwords))
        self.assertEqual(sorted(results), [200, 400])
        winning_password = passwords[results.index(200)]
        self.assertEqual(self.post(self.app.test_client(), '/login', dict(email='member@example.com', password=winning_password)).status_code, 200)

    def test_demo_preview_never_contacts_provider(self):
        self.app.config['DEMO_MODE'] = True
        result = self.create(delivery_channel='sms', phone='+306912345678')
        self.assertEqual(result.json['invitation']['status'], 'demo')
        self.assertEqual(result.json['demo_credentials']['username'], 'new.member')
        self.sender.assert_not_called()
        self.sms_sender.assert_not_called()
        self.app.config['DEMO_MODE'] = False
        self.assertEqual(self.post(self.app.test_client(), '/login', dict(username='new.member',password=result.json['demo_credentials']['temporary_password'])).status_code, 403)

    def test_invitation_is_private_and_persists_after_restart(self):
        self.create()
        token = self.token()
        # Schema initialization must preserve issued invitations.
        create_app(dict(self.app.config))
        self.assertEqual(self.accept(token).status_code, 200)
        member = self.app.test_client()
        self.post(member, '/login', dict(email='member@example.com', password='MyPrivatePassword2026!'))
        self.assertNotIn('invitation', member.get('/api/dashboard').get_data(as_text=True))
        data = self.owner.get('/api/owner').json
        self.assertEqual(data['members'][0]['invitation']['status'], 'used')
        self.assertNotIn('token_hash', json.dumps(data))


class DeliveryAdapterTests(unittest.TestCase):
    def setUp(self):
        self.config = dict(RESEND_API_KEY='private-email-key', INVITE_FROM_EMAIL='FORM <members@example.com>',
                           SMS_PROVIDER='twilio',
                           TWILIO_ACCOUNT_SID='AC' + 'b' * 32, TWILIO_AUTH_TOKEN='private-sms-key', TWILIO_FROM_NUMBER='+306900000000')

    @patch('invitations.urlopen')
    def test_websms_matches_barbershop_protocol_without_exposing_key(self, open_mock):
        from invitations import DeliveryError, send_invitation
        config = dict(SMS_PROVIDER='websms', WEBSMS_API_KEY='private-websms-key', WEBSMS_SENDER='FORM')
        open_mock.return_value.__enter__.return_value.read.return_value = b'{"status":"ok"}'
        self.assertIsNone(send_invitation(config, 'sms', '+35799123456', 'member@example.com', 'https://gym.example/#activate=test'))
        req = open_mock.call_args.args[0]
        self.assertEqual(req.full_url, 'https://websms.com.cy/api/send-sm')
        payload = parse_qs(req.data.decode())
        self.assertEqual(payload['to'], ['35799123456'])
        self.assertEqual(payload['from'], ['FORM'])
        self.assertEqual(payload['key'], ['private-websms-key'])
        self.assertIn('member@example.com', payload['message'][0])
        self.assertNotIn('private-websms-key', req.full_url)
        open_mock.return_value.__enter__.return_value.read.return_value = b'{"status":"error","error":"private-websms-key"}'
        with self.assertRaises(DeliveryError) as failure:
            send_invitation(config, 'sms', '+35799123456', 'member@example.com', 'secret-link')
        self.assertNotIn('private-websms-key', str(failure.exception))

    @patch('invitations.urlopen')
    def test_email_payload_and_https(self, open_mock):
        from invitations import send_invitation
        open_mock.return_value.__enter__.return_value.read.return_value = b'{"id":"email-id"}'
        self.assertEqual(send_invitation(self.config, 'email', 'member@example.com', 'member@example.com', 'https://gym.example/#activate=test'), 'email-id')
        req = open_mock.call_args.args[0]
        self.assertEqual(req.full_url, 'https://api.resend.com/emails')
        body = json.loads(req.data)
        self.assertEqual(body['to'], ['member@example.com'])
        self.assertIn('https://gym.example/#activate=test', body['text'])
        self.assertNotIn('password', body['text'])
        self.assertEqual(open_mock.call_args.kwargs['timeout'], 10)

    @patch('invitations.urlopen')
    def test_sms_payload_and_provider_failure_redaction(self, open_mock):
        from invitations import DeliveryError, send_invitation
        open_mock.return_value.__enter__.return_value.read.return_value = b'{"sid":"sms-id"}'
        self.assertEqual(send_invitation(self.config, 'sms', '+306912345678', 'member@example.com', 'https://gym.example/#activate=test'), 'sms-id')
        req = open_mock.call_args.args[0]
        self.assertEqual(parse_qs(req.data.decode())['To'], ['+306912345678'])
        self.assertIn('member@example.com', parse_qs(req.data.decode())['Body'][0])
        open_mock.side_effect = URLError('private-sms-key and sensitive provider details')
        with self.assertRaises(DeliveryError) as failure:
            send_invitation(self.config, 'sms', '+306912345678', 'member@example.com', 'secret-link')
        self.assertNotIn('private-sms-key', str(failure.exception))

    def test_public_url_requires_https_and_rejects_injected_components(self):
        from invitations import DeliveryError, portal_url
        for value in ('http://gym.example', 'https://user:pass@gym.example', 'https://gym.example/?x=1', 'https://gym.example/#bad', 'https://gym.example/path', 'https://[broken', 'https://gym.example:bad', 'https://gym. example'):
            with self.assertRaises(DeliveryError):
                portal_url(dict(PUBLIC_BASE_URL=value, DEMO_MODE=False))
        self.assertEqual(portal_url(dict(PUBLIC_BASE_URL='https://gym.example/', DEMO_MODE=False)), 'https://gym.example')


if __name__ == '__main__':
    unittest.main()
