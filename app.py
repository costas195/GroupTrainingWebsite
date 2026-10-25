import functools
import hashlib
import os
import re
import secrets
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, g, jsonify, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
import psycopg


from localization import error_message, field_label, localize_demo
from invitations import DeliveryError, portal_url, send_invitation, validate_channel
from database import Connection, INTEGRITY_ERRORS, SCHEMA_VERSION, consume_login_attempt, migrate

ROOT = Path(__file__).resolve().parent


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv('SECRET_KEY') or secrets.token_hex(32),
        DATABASE=os.getenv('DATABASE_PATH', str(ROOT / 'data' / 'gym.sqlite3')),
        DATABASE_URL=os.getenv('DATABASE_URL', '').strip(),
        DATABASE_SSLMODE=os.getenv('DATABASE_SSLMODE', 'require'),
        APP_ENV=os.getenv('APP_ENV', 'development'),
        AUTO_MIGRATE=os.getenv('AUTO_MIGRATE', 'true').lower() == 'true',
        DEMO_MODE=os.getenv('DEMO_MODE', 'true').lower() == 'true',
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.getenv('RENDER', '').lower() == 'true',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
        MAX_CONTENT_LENGTH=64 * 1024,
        PUBLIC_BASE_URL=os.getenv('PUBLIC_BASE_URL') or os.getenv('RENDER_EXTERNAL_URL', ''),
        RESEND_API_KEY=os.getenv('RESEND_API_KEY', ''),
        INVITE_FROM_EMAIL=os.getenv('INVITE_FROM_EMAIL', ''),
        SMS_PROVIDER=os.getenv('SMS_PROVIDER', 'websms').lower(),
        WEBSMS_API_KEY=os.getenv('WEBSMS_API_KEY', ''),
        WEBSMS_SENDER=os.getenv('WEBSMS_SENDER', ''),
        TWILIO_ACCOUNT_SID=os.getenv('TWILIO_ACCOUNT_SID', ''),
        TWILIO_AUTH_TOKEN=os.getenv('TWILIO_AUTH_TOKEN', ''),
        TWILIO_FROM_NUMBER=os.getenv('TWILIO_FROM_NUMBER', ''),
    )
    if config:
        app.config.update(config)
    production = app.config['APP_ENV'] == 'production'
    if production:
        if app.config['DEMO_MODE']:
            raise RuntimeError('Production requires DEMO_MODE=false.')
        if not app.config['DATABASE_URL'].startswith(('postgresql://', 'postgres://')):
            raise RuntimeError('Production requires a PostgreSQL DATABASE_URL.')
        if app.config['DATABASE_SSLMODE'] not in ('require', 'verify-ca', 'verify-full'):
            raise RuntimeError('Production requires encrypted PostgreSQL connections.')
        configured_secret = (config or {}).get('SECRET_KEY') or os.getenv('SECRET_KEY')
        if not configured_secret or len(configured_secret) < 32:
            raise RuntimeError('Production requires a stable SECRET_KEY of at least 32 characters.')
        portal_url(app.config)
        app.config['SESSION_COOKIE_SECURE'] = True
        from urllib.parse import urlsplit
        app.config['TRUSTED_HOSTS'] = list(filter(None, {
            urlsplit(app.config['PUBLIC_BASE_URL']).hostname, os.getenv('RENDER_EXTERNAL_HOSTNAME')}))
    if os.getenv('RENDER', '').lower() == 'true':
        # Render is the single trusted ingress. Never trust arbitrary Host headers.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=0)
    if os.getenv('RENDER') and not os.getenv('SECRET_KEY') and not app.config.get('TESTING'):
        raise RuntimeError('Set SECRET_KEY in Render before starting the application.')
    try:
        gym_zone = ZoneInfo(os.getenv('GYM_TIMEZONE', 'Asia/Nicosia'))
    except ZoneInfoNotFoundError:
        if production:
            raise RuntimeError('Set GYM_TIMEZONE to a valid IANA timezone.') from None
        gym_zone = timezone.utc

    def now():
        return datetime.now(gym_zone).replace(tzinfo=None)

    def db():
        if 'db' not in g:
            g.db = Connection(app.config)
        return g.db

    @app.teardown_appcontext
    def close_db(_):
        connection = g.pop('db', None)
        if connection:
            connection.close()

    def error(message, status=400):
        return jsonify(error=error_message(message)), status

    def auth(owner=False):
        def decorator(fn):
            @functools.wraps(fn)
            def wrapped(*args, **kwargs):
                if request.method in ('POST', 'PUT', 'DELETE'):
                    db().begin_write()
                user = db().execute('SELECT * FROM users WHERE id=?', (session.get('uid'),)).fetchone()
                if (not user or (user['is_demo'] and not app.config['DEMO_MODE'])
                        or session.get('version', 0) != user['session_version']):
                    return error('Please sign in to continue.', 401)
                if owner and user['role'] != 'owner':
                    return error('This area is for the studio owner.', 403)
                g.user = user
                return fn(*args, **kwargs)
            return wrapped
        return decorator

    @app.before_request
    def csrf_check():
        if request.path.startswith('/api/') and request.method in ('POST', 'PUT', 'DELETE'):
            if not session.get('csrf') or not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), session['csrf']):
                return error('Your session expired. Refresh the page and try again.', 403)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        if production:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if request.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(400)
    def bad_request(_):
        return error('Please check the information you entered.')

    @app.errorhandler(413)
    def too_large(_):
        return error('That request is too large.', 413)

    @app.errorhandler(psycopg.OperationalError)
    def database_unavailable(_):
        app.logger.error('Database request failed; check database availability.')
        return error('Η υπηρεσία δεν είναι προσωρινά διαθέσιμη. Δοκίμασε ξανά σε λίγο.', 503)

    def payload():
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            raise ValueError('Please enter valid form data.')
        return value

    def text(data, key, minimum=1, maximum=200):
        value = str(data.get(key, '')).strip()
        if not minimum <= len(value) <= maximum:
            raise ValueError(f'Το πεδίο «{field_label(key)}» πρέπει να έχει {minimum}–{maximum} χαρακτήρες.')
        return value

    def number(data, key, minimum, maximum, integer=False):
        try:
            value = int(data[key]) if integer else float(data[key])
        except (ValueError, TypeError, KeyError, OverflowError):
            raise ValueError(f'Δώσε έγκυρη τιμή για το πεδίο «{field_label(key)}».')
        if not minimum <= value <= maximum:
            raise ValueError(f'Το πεδίο «{field_label(key)}» πρέπει να είναι μεταξύ {minimum} και {maximum}.')
        return value

    @app.errorhandler(ValueError)
    def invalid(exc):
        return error(str(exc))

    def public_user(row):
        return {key: row[key] for key in ('id', 'name', 'email', 'role', 'goal', 'priority')}

    def invitation_info(uid):
        row = db().execute('''SELECT channel,recipient,status,expires_at,used_at,last_attempt_at
            FROM member_invitations WHERE user_id=?''', (uid,)).fetchone()
        if not row:
            return None
        info = dict(row)
        if not info['used_at'] and info['expires_at'] <= time.time():
            info['status'] = 'expired'
        return info

    def prepare_invitation(uid, channel, recipient):
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        stamp = int(time.time())
        db().execute('''INSERT INTO member_invitations
            (user_id,token_hash,channel,recipient,status,expires_at,last_attempt_at)
            VALUES(?,?,?,?,'pending',?,?) ON CONFLICT(user_id) DO UPDATE SET
            token_hash=excluded.token_hash,channel=excluded.channel,recipient=excluded.recipient,
            status='pending',expires_at=excluded.expires_at,last_attempt_at=excluded.last_attempt_at,provider_id=NULL''',
            (uid, token_hash, channel, recipient, stamp + 86400, stamp))
        return token, token_hash

    def deliver_invitation(uid, email, token, token_hash):
        info = invitation_info(uid)
        # Fragments keep invitation tokens out of HTTP access logs and referrers.
        base = portal_url(app.config) if not app.config['DEMO_MODE'] else ''
        link = base + '/#activate=' + token
        status, provider_id = 'demo', None
        message = None
        if not app.config['DEMO_MODE']:
            try:
                provider_id = send_invitation(app.config, info['channel'], info['recipient'], email, link)
                status = 'accepted'
            except DeliveryError as exc:
                status, message = 'failed', str(exc)
        db().execute('''UPDATE member_invitations SET status=?,provider_id=?
            WHERE user_id=? AND token_hash=? AND status='pending' ''', (status, provider_id, uid, token_hash))
        db().commit()
        result = dict(invitation=invitation_info(uid))
        if message:
            result['delivery_error'] = message
        if app.config['DEMO_MODE']:
            result['demo_activation_url'] = link
        return result

    def classes_for(start, end, uid):
        rows = db().execute('''SELECT c.*, COUNT(b.id) AS booked,
            MAX(CASE WHEN b.user_id=? THEN b.id END) AS booking_id,
            MAX(CASE WHEN b.user_id=? THEN b.attended END) AS attended
            FROM classes c LEFT JOIN bookings b ON b.class_id=c.id
            WHERE c.starts_at >= ? AND c.starts_at < ? GROUP BY c.id ORDER BY c.starts_at''',
            (uid, uid, start, end)).fetchall()
        return [dict(row) for row in rows]

    @app.get('/')
    def index():
        return render_template('index.html')

    @app.get('/health')
    def health():
        version = db().execute('SELECT COALESCE(MAX(version),0) FROM schema_migrations').fetchone()[0]
        if version != SCHEMA_VERSION:
            return jsonify(status='unavailable'), 503
        return jsonify(status='ok')

    @app.get('/api/session')
    def get_session():
        session.setdefault('csrf', secrets.token_urlsafe(32))
        row = db().execute('SELECT * FROM users WHERE id=?', (session.get('uid'),)).fetchone()
        if row and ((row['is_demo'] and not app.config['DEMO_MODE'])
                    or session.get('version', 0) != row['session_version']):
            row = None
        return jsonify(user=public_user(row) if row else None, csrf=session['csrf'], demo=app.config['DEMO_MODE'], today=now().date().isoformat(), server_now=now().isoformat(), timezone=str(gym_zone))

    @app.post('/api/login')
    def login():
        data = payload()
        email = text(data, 'email', 3, 254).lower()
        stamp = int(time.time())
        allowed = True
        for prefix, value, maximum in (('account:', email, 15), ('ip:', request.remote_addr or 'unknown', 100)):
            bucket = hashlib.sha256((prefix + value).encode()).hexdigest()
            allowed = consume_login_attempt(db(), bucket, maximum, stamp) and allowed
        db().execute('DELETE FROM login_attempts WHERE window_start<?', (stamp - 86400,))
        db().commit()
        if not allowed:
            return error('Too many attempts. Please try again in five minutes.', 429)
        row = db().execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        if not row or not check_password_hash(row['password_hash'], str(data.get('password', ''))):
            return error('Email or password is incorrect.', 401)
        if row['is_demo'] and not app.config['DEMO_MODE']:
            return error('Demo access is disabled.', 403)
        session.clear()
        session.update(uid=row['id'], version=row['session_version'], csrf=secrets.token_urlsafe(32))
        session.permanent = True
        return jsonify(user=public_user(row), csrf=session['csrf'])

    @app.post('/api/logout')
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.post('/api/invitations/accept')
    def accept_invitation():
        data = payload()
        token = str(data.get('token', ''))
        invalid_link = 'Η πρόσκληση έληξε ή δεν είναι έγκυρη. Ζήτησε νέα πρόσκληση από τον προπονητή σου.'
        if not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
            return error(invalid_link, 400)
        new_password = text(data, 'new_password', 10, 128)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        connection = db()
        connection.begin_write()
        invite = connection.execute('''SELECT i.* FROM member_invitations i JOIN users u ON u.id=i.user_id
            WHERE i.token_hash=? AND i.used_at IS NULL AND i.expires_at>?
            AND (u.is_demo=0 OR ?=1)''', (token_hash, int(time.time()), int(app.config['DEMO_MODE']))).fetchone()
        if not invite:
            return error(invalid_link, 400)
        connection.execute('UPDATE users SET password_hash=?,session_version=session_version+1 WHERE id=?',
                           (generate_password_hash(new_password), invite['user_id']))
        connection.execute("UPDATE member_invitations SET token_hash=NULL,used_at=?,status='used' WHERE user_id=?",
                           (int(time.time()), invite['user_id']))
        connection.commit()
        # Activation does not replace an existing session (e.g. an owner preview).
        return jsonify(ok=True)

    @app.get('/api/dashboard')
    @auth()
    def dashboard():
        user = g.user
        month = request.args.get('month', now().strftime('%Y-%m'))
        try:
            first = date.fromisoformat(month + '-01')
        except ValueError:
            return error('Choose a valid month.')
        end = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
        access = [dict(r) for r in db().execute('SELECT * FROM access WHERE user_id=? ORDER BY month', (user['id'],))]
        allowed = user['role'] == 'owner' or any(a['month'] == month for a in access)
        classes = classes_for(first.isoformat(), end.isoformat(), user['id']) if allowed else []
        bookings = db().execute('''SELECT c.*, b.id AS booking_id, b.attended FROM bookings b
            JOIN classes c ON c.id=b.class_id WHERE b.user_id=? ORDER BY c.starts_at''', (user['id'],)).fetchall()
        logs = [dict(r) for r in db().execute('SELECT * FROM progress WHERE user_id=? ORDER BY logged_on,id', (user['id'],))]
        return jsonify(user=public_user(user), access=access, classes=classes, bookings=[dict(r) for r in bookings], logs=logs, today=now().date().isoformat(), server_now=now().isoformat(), month=month)

    @app.post('/api/bookings')
    @auth()
    def book():
        if g.user['role'] != 'client':
            return error('Use a client account to book a class.', 403)
        class_id = number(payload(), 'class_id', 1, 1000000000, True)
        connection = db()
        connection.begin_write()
        cls = connection.execute('SELECT * FROM classes WHERE id=?', (class_id,)).fetchone()
        if not cls:
            return error('This class is no longer available.', 404)
        start = datetime.fromisoformat(cls['starts_at'])
        if start <= now():
            return error('This class has already started.')
        month = start.strftime('%Y-%m')
        access = connection.execute('SELECT * FROM access WHERE user_id=? AND month=?', (g.user['id'], month)).fetchone()
        if not access:
            return error('Your membership does not include this month. Contact your coach.', 403)
        if connection.execute('SELECT 1 FROM bookings WHERE user_id=? AND class_id=?', (g.user['id'], class_id)).fetchone():
            return error('You already have a place in this class.', 409)
        if connection.execute('SELECT COUNT(*) FROM bookings WHERE class_id=?', (class_id,)).fetchone()[0] >= cls['capacity']:
            return error('This class is full. Try another time.', 409)
        monday = (start.date() - timedelta(days=start.weekday())).isoformat()
        sunday_end = (date.fromisoformat(monday) + timedelta(days=7)).isoformat()
        used = connection.execute('''SELECT COUNT(*) FROM bookings b JOIN classes c ON c.id=b.class_id
            WHERE b.user_id=? AND c.starts_at>=? AND c.starts_at<? AND substr(c.starts_at,1,7)=?''',
            (g.user['id'], monday, sunday_end, month)).fetchone()[0]
        if used >= access['weekly_limit']:
            return error(f'You have used your {access["weekly_limit"]} bookings for this week and month.', 409)
        # Prevent overlapping reservations, including classes with different durations.
        end = start + timedelta(minutes=cls['duration'])
        others = connection.execute('SELECT c.starts_at,c.duration FROM bookings b JOIN classes c ON c.id=b.class_id WHERE b.user_id=?', (g.user['id'],)).fetchall()
        if any(datetime.fromisoformat(o['starts_at']) < end and datetime.fromisoformat(o['starts_at']) + timedelta(minutes=o['duration']) > start for o in others):
            return error('You have another class at this time.', 409)
        connection.execute('INSERT INTO bookings(user_id,class_id) VALUES(?,?)', (g.user['id'], class_id))
        connection.commit()
        return jsonify(ok=True), 201

    @app.delete('/api/bookings/<int:booking_id>')
    @auth()
    def cancel(booking_id):
        row = db().execute('SELECT b.*,c.starts_at FROM bookings b JOIN classes c ON c.id=b.class_id WHERE b.id=? AND b.user_id=?', (booking_id, g.user['id'])).fetchone()
        if not row:
            return error('Booking not found.', 404)
        if datetime.fromisoformat(row['starts_at']) <= now():
            return error('You can only cancel a class before it starts.')
        db().execute('DELETE FROM bookings WHERE id=?', (booking_id,))
        db().commit()
        return jsonify(ok=True)

    @app.post('/api/progress')
    @auth()
    def progress():
        data = payload()
        logged_on = date.fromisoformat(text(data, 'logged_on', 10, 10))
        if logged_on > now().date():
            return error('Progress entries cannot be dated in the future.')
        kind = data.get('kind')
        if kind not in ('bodyweight', 'lift'):
            return error('Choose body weight or an exercise.')
        exercise = 'Σωματικό βάρος' if kind == 'bodyweight' else text(data, 'exercise', 2, 80)
        weight = number(data, 'weight', 0.1 if kind == 'bodyweight' else 0, 1000)
        reps = number(data, 'reps', 1, 1000, True) if kind == 'lift' else None
        note = text(data, 'note', 0, 500)
        db().execute('INSERT INTO progress(user_id,logged_on,kind,exercise,weight,reps,note) VALUES(?,?,?,?,?,?,?)', (g.user['id'], logged_on.isoformat(), kind, exercise, weight, reps, note))
        db().commit()
        return jsonify(ok=True), 201

    @app.delete('/api/progress/<int:log_id>')
    @auth()
    def delete_progress(log_id):
        result = db().execute('DELETE FROM progress WHERE id=? AND user_id=?', (log_id, g.user['id']))
        db().commit()
        if not result.rowcount:
            return error('Entry not found.', 404)
        return jsonify(ok=True)

    @app.put('/api/profile')
    @auth()
    def profile():
        data = payload()
        db().execute('UPDATE users SET name=?,goal=?,priority=? WHERE id=?', (text(data, 'name', 2, 80), text(data, 'goal', 0, 300), text(data, 'priority', 0, 300), g.user['id']))
        db().commit()
        return jsonify(ok=True)

    @app.put('/api/password')
    @auth()
    def password():
        data = payload()
        if not check_password_hash(g.user['password_hash'], str(data.get('current_password', ''))):
            return error('Your current password is incorrect.', 403)
        new_password = text(data, 'new_password', 10, 128)
        db().execute('UPDATE users SET password_hash=?,session_version=session_version+1 WHERE id=?', (generate_password_hash(new_password), g.user['id']))
        db().commit()
        session['version'] = g.user['session_version'] + 1
        return jsonify(ok=True)

    @app.get('/api/owner')
    @auth(owner=True)
    def owner():
        users = [dict(r) for r in db().execute("SELECT id,name,email,goal,priority FROM users WHERE role='client' ORDER BY name")]
        for user in users:
            user['invitation'] = invitation_info(user['id'])
            user['access'] = [dict(r) for r in db().execute('SELECT * FROM access WHERE user_id=? ORDER BY month', (user['id'],))]
            user['bookings'] = db().execute('SELECT COUNT(*) FROM bookings WHERE user_id=?', (user['id'],)).fetchone()[0]
        bookings = [dict(r) for r in db().execute('''SELECT b.*,u.name,u.email,c.title,c.starts_at FROM bookings b JOIN users u ON u.id=b.user_id JOIN classes c ON c.id=b.class_id ORDER BY c.starts_at''')]
        return jsonify(members=users, bookings=bookings)

    @app.post('/api/owner/members')
    @auth(owner=True)
    def add_member():
        data = payload()
        name = text(data, 'name', 2, 80)
        email = text(data, 'email', 5, 254).lower()
        if '@' not in email or '.' not in email.rsplit('@', 1)[-1] or any(c.isspace() for c in email):
            return error('Enter a valid email address.')
        channel = text(data, 'delivery_channel', 1, 10) if 'delivery_channel' in data else 'email'
        phone = text(data, 'phone', 0, 16)
        try:
            validate_channel(app.config, channel, phone)
        except DeliveryError as exc:
            return error(str(exc), 503)
        goal, priority = text(data, 'goal', 0, 300), text(data, 'priority', 0, 300)
        try:
            # Only a password chosen through the invitation can unlock this account.
            cursor = db().execute('INSERT INTO users(name,email,password_hash,role,goal,priority,is_demo) VALUES(?,?,?,?,?,?,?) RETURNING id',
                                  (name, email, generate_password_hash(secrets.token_urlsafe(48)), 'client', goal, priority, int(app.config['DEMO_MODE'])))
            uid = cursor.fetchone()[0]
            token, token_hash = prepare_invitation(uid, channel, email if channel == 'email' else phone)
            db().commit()
        except INTEGRITY_ERRORS:
            db().rollback()
            return error('A member with that email already exists.', 409)
        # Persist first so an uncertain delivery never loses the member or requires
        # creating a duplicate. Failures remain visible and can be retried by owner.
        return jsonify(ok=True, id=uid, **deliver_invitation(uid, email, token, token_hash)), 201

    @app.post('/api/owner/members/<int:uid>/invitation')
    @auth(owner=True)
    def resend_invitation(uid):
        data = payload()
        member = db().execute("SELECT id,email FROM users WHERE id=? AND role='client'", (uid,)).fetchone()
        if not member:
            return error('Member not found.', 404)
        previous = invitation_info(uid)
        if not previous or previous['used_at'] is not None:
            return error('Ο λογαριασμός έχει ήδη ενεργοποιηθεί ή δεν έχει πρόσκληση.', 409)
        channel = str(data.get('delivery_channel', previous['channel']))
        phone = text(data, 'phone', 0, 16) if 'phone' in data else (
            previous['recipient'] if previous['channel'] == 'sms' else '')
        try:
            validate_channel(app.config, channel, phone)
        except DeliveryError as exc:
            return error(str(exc), 503)
        connection = db()
        connection.begin_write()
        # Recheck inside the transaction: activation or another resend may race us.
        current = connection.execute('SELECT * FROM member_invitations WHERE user_id=?', (uid,)).fetchone()
        if current['used_at'] is not None:
            return error('Ο λογαριασμός έχει ήδη ενεργοποιηθεί.', 409)
        if current['last_attempt_at'] > time.time() - 60:
            return error('Περίμενε ένα λεπτό πριν στείλεις ξανά πρόσκληση.', 429)
        token, token_hash = prepare_invitation(uid, channel, member['email'] if channel == 'email' else phone)
        connection.commit()
        return jsonify(ok=True, **deliver_invitation(uid, member['email'], token, token_hash))

    @app.put('/api/owner/members/<int:uid>/access')
    @auth(owner=True)
    def access(uid):
        data = payload()
        if not db().execute("SELECT 1 FROM users WHERE id=? AND role='client'", (uid,)).fetchone():
            return error('Member not found.', 404)
        first = date.fromisoformat(text(data, 'month', 7, 7) + '-01')
        months = number(data, 'months', 1, 12, True)
        limit = number(data, 'weekly_limit', 1, 21, True)
        for offset in range(months):
            index = first.year * 12 + first.month - 1 + offset
            month = f'{index // 12:04}-{index % 12 + 1:02}'
            db().execute('INSERT INTO access(user_id,month,weekly_limit) VALUES(?,?,?) ON CONFLICT(user_id,month) DO UPDATE SET weekly_limit=excluded.weekly_limit', (uid, month, limit))
        db().commit()
        return jsonify(ok=True)

    @app.delete('/api/owner/members/<int:uid>/access/<month>')
    @auth(owner=True)
    def revoke(uid, month):
        date.fromisoformat(month + '-01')
        # Releasing future places keeps the class count accurate after access is removed.
        db().execute('DELETE FROM bookings WHERE user_id=? AND class_id IN (SELECT id FROM classes WHERE substr(starts_at,1,7)=? AND starts_at>?)', (uid, month, now().isoformat(timespec='minutes')))
        db().execute('DELETE FROM access WHERE user_id=? AND month=?', (uid, month))
        db().commit()
        return jsonify(ok=True)

    @app.route('/api/owner/classes', methods=['POST'])
    @app.route('/api/owner/classes/<int:class_id>', methods=['PUT'])
    @auth(owner=True)
    def save_class(class_id=None):
        data = payload()
        title = text(data, 'title', 2, 80)
        starts = datetime.fromisoformat(text(data, 'starts_at', 16, 16))
        if starts <= now():
            return error('Schedule classes in the future.')
        capacity = number(data, 'capacity', 1, 50, True)
        duration = number(data, 'duration', 15, 180, True)
        category = text(data, 'category', 2, 30)
        if category not in ('Strength', 'Conditioning', 'Mobility', 'Hybrid'):
            return error('Choose a valid class category.')
        values = (title, starts.isoformat(timespec='minutes'), duration, capacity, category, text(data, 'coach', 2, 80), text(data, 'description', 5, 800), text(data, 'warmup', 3, 800), text(data, 'main', 3, 1600), text(data, 'finisher', 3, 800))
        connection = db()
        connection.begin_write()
        if class_id:
            old = connection.execute('SELECT * FROM classes WHERE id=?', (class_id,)).fetchone()
            if not old:
                return error('Class not found.', 404)
            count = connection.execute('SELECT COUNT(*) FROM bookings WHERE class_id=?', (class_id,)).fetchone()[0]
            if capacity < count:
                return error(f'There are already {count} bookings. Capacity cannot be lower.')
            if count and (old['starts_at'] != values[1] or old['duration'] != duration):
                return error('A booked class cannot be rescheduled. Cancel it and create a new class.')
            connection.execute('UPDATE classes SET title=?,starts_at=?,duration=?,capacity=?,category=?,coach=?,description=?,warmup=?,main=?,finisher=? WHERE id=?', (*values, class_id))
        else:
            connection.execute('INSERT INTO classes(title,starts_at,duration,capacity,category,coach,description,warmup,main,finisher) VALUES(?,?,?,?,?,?,?,?,?,?)', values)
        connection.commit()
        return jsonify(ok=True)

    @app.delete('/api/owner/classes/<int:class_id>')
    @auth(owner=True)
    def delete_class(class_id):
        result = db().execute('DELETE FROM classes WHERE id=?', (class_id,))
        db().commit()
        if not result.rowcount:
            return error('Class not found.', 404)
        return jsonify(ok=True)

    @app.put('/api/owner/bookings/<int:booking_id>')
    @auth(owner=True)
    def attendance(booking_id):
        attended = payload().get('attended')
        if not isinstance(attended, bool):
            return error('Choose an attendance status.')
        booking = db().execute('SELECT b.id,c.starts_at FROM bookings b JOIN classes c ON c.id=b.class_id WHERE b.id=?', (booking_id,)).fetchone()
        if not booking:
            return error('Booking not found.', 404)
        if datetime.fromisoformat(booking['starts_at']) > now():
            return error('Attendance can be marked after a class starts.')
        db().execute('UPDATE bookings SET attended=? WHERE id=?', (int(attended), booking_id))
        db().commit()
        return jsonify(ok=True)

    def initialize_database():
        with app.app_context():
            migrate(db())
            if production and db().execute('SELECT 1 FROM users WHERE is_demo=1 LIMIT 1').fetchone():
                raise RuntimeError('Production must use a clean live database, without demo accounts.')
            if not db().execute('SELECT 1 FROM users LIMIT 1').fetchone():
                if app.config['DEMO_MODE']:
                    seed_demo(db(), now())
                else:
                    owner_email = os.getenv('OWNER_EMAIL', '').strip().lower()
                    owner_password = os.getenv('OWNER_PASSWORD', '')
                    if ('@' not in owner_email or '.' not in owner_email.rsplit('@', 1)[-1]
                            or any(c.isspace() for c in owner_email) or len(owner_password) < 12):
                        raise RuntimeError('With DEMO_MODE=false, set OWNER_EMAIL and OWNER_PASSWORD (12+ characters) for the first owner.')
                    db().execute("INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,'owner')", (os.getenv('OWNER_NAME', 'Studio owner'), owner_email, generate_password_hash(owner_password)))
                    db().commit()
            if app.config['DEMO_MODE']:
                localize_demo(db())
            db().commit()

    app.extensions['initialize_database'] = initialize_database
    if app.config['AUTO_MIGRATE']:
        initialize_database()
    return app


def seed_demo(connection, now):
    members = [('Alex Morgan', 'client@form.demo', 'client', 'Get stronger. Move better. Stay consistent.', 'Build a consistent squat pattern and make time for mobility.'), ('Jamie Parker', 'owner@form.demo', 'owner', '', ''), ('Sofia Lewis', 'sofia@form.demo', 'client', 'Build confidence with free weights.', 'Upper-body strength'), ('Daniel Chen', 'daniel@form.demo', 'client', 'Improve conditioning.', 'Steady, sustainable progress'), ('Emma Wilson', 'emma@form.demo', 'client', 'Train three times each week.', 'Full-body strength'), ('Noah Bennett', 'noah@form.demo', 'client', 'Move well and feel stronger.', 'Mobility and consistency')]
    hashed = generate_password_hash('FormDemo2026!')
    for name, email, role, goal, priority in members:
        connection.execute('INSERT INTO users(name,email,password_hash,role,goal,priority,is_demo) VALUES(?,?,?,?,?,?,1)', (name, email, hashed, role, goal, priority))
    for uid in (1, 3, 4, 5, 6):
        for offset in range(3):
            index = now.year * 12 + now.month - 1 + offset
            connection.execute('INSERT INTO access VALUES(?,?,?)', (uid, f'{index // 12:04}-{index % 12 + 1:02}', 3 if uid != 4 else 2))
    monday = now.date() - timedelta(days=now.weekday())
    plans = [
        ('Full body foundations', 'Strength', 'A little stronger, together. Build confidence with the essential movement patterns.', '6 min easy row\nHip openers + band pull-aparts\n2 rounds of bodyweight squats', 'Back squat · 4 × 6\nDumbbell bench press · 3 × 10\nSingle-arm row · 3 × 10 each side', '8-minute partner circuit\n10 kettlebell swings + 8 box step-ups\nEasy stretch to finish'),
        ('Engine room', 'Conditioning', 'Find your pace with a coach-led mix of cardio and functional strength.', '5 min bike\nDynamic lunges + shoulder circles', '4 rounds at a steady pace\n400 m row · 12 wall balls\n10 alternating dumbbell snatches\nRest 90 seconds between rounds', '6 min alternating bike / farmer carry\nSlow breathing and calf stretch'),
        ('Strong & steady', 'Hybrid', 'A balanced session of strength work and conditioning. All levels welcome.', '5 min ski erg\nGlute bridges + dead bugs', 'Deadlift · 4 × 5\nSplit squat · 3 × 8 each side\nAssisted pull-up · 3 × 8', '10 min easy-paced circuit\nSled push + farmer carry\nHip flexor stretch'),
        ('Move & reset', 'Mobility', 'Create space to move. A slower session focused on control, mobility, and recovery.', '5 min gentle flow\nControlled joint circles', '90/90 hip transitions · 3 × 8\nThoracic rotations · 3 × 8\nTempo goblet squat · 3 × 6\nShoulder mobility flow · 8 min', 'Guided full-body stretch\n3 min relaxed breathing'),
    ]
    for day_offset in range(-14, 70):
        day = monday + timedelta(days=day_offset)
        if day.weekday() == 6:
            continue
        slots = ['08:00', '17:30', '18:30'] if day.weekday() < 5 else ['09:00', '10:00']
        for slot_index, slot in enumerate(slots):
            plan = plans[(day.weekday() + slot_index) % len(plans)]
            title, category, desc, warmup, main, finisher = plan
            cursor = connection.execute('INSERT INTO classes(title,starts_at,duration,capacity,category,coach,description,warmup,main,finisher) VALUES(?,?,?,?,?,?,?,?,?,?) RETURNING id', (title, f'{day.isoformat()}T{slot}', 50, 6 if slot_index != 2 else 4, category, 'Jamie' if slot_index != 1 else 'Taylor', desc, warmup, main, finisher))
            seeded_class_id = cursor.fetchone()[0]
            member_days = {3: ((0, 2, 4), 0), 4: ((1, 3), 1), 5: ((0, 2, 4), 1), 6: ((1, 4, 5), 0)}
            for uid, (training_days, preferred_slot) in member_days.items():
                if day.weekday() in training_days and slot_index == preferred_slot:
                    connection.execute('INSERT INTO bookings(user_id,class_id,attended) VALUES(?,?,?)', (uid, seeded_class_id, int(day < now.date())))
            if day.weekday() in (0, 2, 4) and slot_index == 0 and day < now.date() and day >= monday - timedelta(days=14) and (day < monday or day.weekday() == 0):
                connection.execute('INSERT INTO bookings(user_id,class_id,attended) VALUES(1,?,1)', (seeded_class_id,))
    next_class = connection.execute('SELECT c.id FROM classes c LEFT JOIN bookings b ON b.class_id=c.id WHERE c.starts_at>? GROUP BY c.id HAVING COUNT(b.id)<c.capacity ORDER BY c.starts_at LIMIT 1', (now.isoformat(),)).fetchone()
    if next_class:
        connection.execute('INSERT INTO bookings(user_id,class_id) VALUES(1,?)', (next_class[0],))
    for offset, weight, squat in [(35, 78.4, 40), (28, 78.1, 42.5), (21, 77.9, 45), (14, 77.8, 47.5), (7, 77.5, 50), (1, 77.3, 52.5)]:
        day = (now.date() - timedelta(days=offset)).isoformat()
        connection.execute("INSERT INTO progress(user_id,logged_on,kind,exercise,weight,note) VALUES(1,?,'bodyweight','Body weight',?,'Morning check-in')", (day, weight))
        connection.execute("INSERT INTO progress(user_id,logged_on,kind,exercise,weight,reps,note) VALUES(1,?,'lift','Back squat',?,6,'Controlled reps. Feeling stronger.')", (day, squat))
    connection.commit()


app = create_app()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.getenv('PORT', '5050')), debug=False)
