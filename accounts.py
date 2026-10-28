"""Mutable, case-insensitive login names; numeric user IDs remain authoritative."""
import re
import secrets
import unicodedata


def validate_username(value):
    username = str(value).strip().lower()
    if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{2,31}', username):
        raise ValueError('Το όνομα χρήστη πρέπει να έχει 3–32 λατινικούς χαρακτήρες, αριθμούς, τελεία, παύλα ή κάτω παύλα.')
    return username


def generate_username(connection, name):
    greek = any('GREEK' in unicodedata.name(char, '') for char in name)
    parts = name.split()
    latin = unicodedata.normalize('NFKD', '.'.join(parts[:1] + parts[-1:]) if len(parts) > 1 else name)
    base = re.sub(r'[^a-z0-9.]', '', latin.encode('ascii', 'ignore').decode().lower()).strip('.')[:26]
    if greek or len(base) < 3:
        base = 'member-' + secrets.token_hex(4)
    candidate, suffix = base, 1
    while connection.execute('SELECT 1 FROM users WHERE lower(username)=?', (candidate,)).fetchone():
        suffix += 1
        ending = str(suffix)
        candidate = base[:32-len(ending)] + ending
    return candidate
