"""Member invitations and HTTPS adapters for Resend, WebSMS Cyprus, and Twilio."""
import base64
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


class DeliveryError(Exception):
    """Safe to display; never includes provider responses or credentials."""


def portal_url(config):
    value = config.get('PUBLIC_BASE_URL', '').strip().rstrip('/')
    try:
        parsed = urlsplit(value)
        hostname, port = parsed.hostname, parsed.port
        local = hostname in ('localhost', '127.0.0.1') and (config['DEMO_MODE'] or config.get('TESTING'))
        valid = (hostname and not any(c.isspace() for c in value)
                 and not (parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path)
                 and (parsed.scheme == 'https' or (local and parsed.scheme == 'http')))
    except ValueError:
        valid = False
    if not valid:
        raise DeliveryError('Χρειάζεται έγκυρη δημόσια διεύθυνση HTTPS για τις προσκλήσεις. Επικοινώνησε με τον διαχειριστή.')
    return value


def validate_channel(config, channel, phone=''):
    if channel not in ('email', 'sms'):
        raise ValueError('Διάλεξε αποστολή με email ή SMS.')
    if channel == 'sms' and not re.fullmatch(r'\+[1-9][0-9]{7,14}', phone):
        raise ValueError('Συμπλήρωσε κινητό με κωδικό χώρας, π.χ. +35799123456.')
    if config['DEMO_MODE']:
        return
    portal_url(config)
    provider = config.get('SMS_PROVIDER', 'websms')
    if channel == 'sms' and provider not in ('websms', 'twilio'):
        raise DeliveryError('Η υπηρεσία SMS δεν έχει ρυθμιστεί σωστά. Επικοινώνησε με τον διαχειριστή.')
    keys = ('RESEND_API_KEY', 'INVITE_FROM_EMAIL') if channel == 'email' else (
        ('WEBSMS_API_KEY', 'WEBSMS_SENDER') if provider == 'websms' else
        ('TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_FROM_NUMBER'))
    if not all(config.get(key, '').strip() for key in keys):
        raise DeliveryError('Η αποστολή με αυτόν τον τρόπο δεν έχει ρυθμιστεί. Επικοινώνησε με τον διαχειριστή.')
    if channel == 'sms' and provider == 'twilio' and not re.fullmatch(r'AC[0-9a-fA-F]{32}', config['TWILIO_ACCOUNT_SID']):
        raise DeliveryError('Η υπηρεσία SMS δεν έχει ρυθμιστεί σωστά. Επικοινώνησε με τον διαχειριστή.')


def send_invitation(config, channel, recipient, email, link):
    email_text = (f'Καλώς ήρθες στο NF Hybrid!\n\nΌνομα χρήστη: {email}\n'
                  f'Όρισε τον προσωπικό σου κωδικό: {link}\n\n'
                  'Ο σύνδεσμος ισχύει για 24 ώρες και χρησιμοποιείται μία φορά.\n'
                  'Αν δεν περίμενες αυτή την πρόσκληση, αγνόησε το μήνυμα.')
    return _send(config, channel, recipient,
                 f'NF Hybrid: Login: {email}. Set password (24h): {link}', email_text)


def send_temporary_credentials(config, recipient, username, temporary_password):
    # Credentials occur only in the HTTPS provider request body, never in a URL,
    # persisted outbox, provider response, or application log.
    message = (f'NF Hybrid\nUser: {username}\nTemp pass: {temporary_password}\n'
               'Valid 24h')
    return _send(config, 'sms', recipient, message)


def _send(config, channel, recipient, sms_text, email_text=''):
    # No automatic retries: a timeout may mean the provider accepted the message.
    # The owner can issue a fresh invitation; the previous link is then invalid.
    if channel == 'email':
        body = json.dumps({
            'from': config['INVITE_FROM_EMAIL'], 'to': [recipient],
            'subject': 'NF Hybrid · Ο λογαριασμός σου είναι έτοιμος',
            'text': email_text,
        }).encode('utf-8')
        req = Request('https://api.resend.com/emails', data=body, headers={
            'Authorization': 'Bearer ' + config['RESEND_API_KEY'],
            'Content-Type': 'application/json', 'User-Agent': 'NF-Hybrid-Portal/1.0',
        }, method='POST')
        id_key = 'id'
    elif config.get('SMS_PROVIDER', 'websms') == 'websms':
        # Same form-encoded API and international-number normalization as the
        # user's Barbershop/bookings/sms.py integration. Keep the key in the body.
        body = urlencode({'to': recipient.lstrip('+'), 'from': config['WEBSMS_SENDER'],
                          'key': config['WEBSMS_API_KEY'],
                          'message': sms_text}).encode('ascii')
        req = Request('https://websms.com.cy/api/send-sm', data=body,
                      headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
        id_key = None
    else:
        body = urlencode({'To': recipient, 'From': config['TWILIO_FROM_NUMBER'],
                          'Body': sms_text}).encode('ascii')
        auth = base64.b64encode((config['TWILIO_ACCOUNT_SID'] + ':' + config['TWILIO_AUTH_TOKEN']).encode()).decode()
        req = Request('https://api.twilio.com/2010-04-01/Accounts/' + config['TWILIO_ACCOUNT_SID'] + '/Messages.json',
                      data=body, headers={'Authorization': 'Basic ' + auth,
                                          'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
        id_key = 'sid'
    try:
        with urlopen(req, timeout=10) as response:
            result = json.loads(response.read(65536))
        if id_key is None:
            if not isinstance(result, dict) or result.get('status') != 'ok':
                raise DeliveryError('Δεν επιβεβαιώθηκε η αποστολή. Έλεγξε την υπηρεσία αποστολής και ξαναστείλε πρόσκληση.')
            # This API confirms acceptance without guaranteeing a message ID.
            return None
        provider_id = result.get(id_key) if isinstance(result, dict) else None
        if not isinstance(provider_id, str) or not provider_id or result.get('status') in ('failed', 'undelivered', 'canceled'):
            raise DeliveryError('Δεν επιβεβαιώθηκε η αποστολή. Έλεγξε την υπηρεσία αποστολής και ξαναστείλε πρόσκληση.')
        return provider_id
    except (HTTPError, URLError, OSError, ValueError):
        raise DeliveryError('Δεν επιβεβαιώθηκε η αποστολή. Έλεγξε την υπηρεσία αποστολής και ξαναστείλε πρόσκληση.') from None
