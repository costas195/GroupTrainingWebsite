# NF Hybrid member portal

A private Greek-language sign-in portal, member booking area and owner workspace. The public page contains only the NF Hybrid logo and login form. Production uses Flask, Gunicorn, PostgreSQL and WebSMS Cyprus.

## Member access

1. The owner enters the member's name, surname, contact email and international mobile number.
2. The system generates a unique username and a random temporary password and submits them by SMS.
3. Latin names produce usernames such as `john.smith`; duplicates receive a suffix. Names containing Greek characters produce random usernames.
4. At first login, the member must choose a different password before viewing data or making bookings. Temporary credentials expire after 24 hours.
5. The member can change their username in Profile. The owner can change it in member management. The numeric account ID, memberships, bookings and progress remain unchanged.

Passwords are stored only as salted scrypt hashes. The owner's live interface cannot retrieve a member's personal or temporary password. Resending initial credentials creates a new temporary password and revokes earlier restricted sessions. Provider acceptance confirms submission; handset delivery must be checked separately.

## Deploy to Render

Follow [PRODUCTION.md](PRODUCTION.md). The production Blueprint creates a paid web service and a separate managed PostgreSQL database in Frankfurt, disables demo data, runs migrations before deployment and uses Cyprus time. Deployment waits for successful repository checks.

Never upload `.env.local.json`, other private environment files, local databases, preview files, virtual environments or old ZIPs. Render receives production secrets through its Environment settings.

## Local development

Use Python 3.12, matching `.python-version`, and Node.js for the JavaScript syntax check. On Windows:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe app.py
```

Open `http://127.0.0.1:5050`. Local defaults are development mode, demo data and SQLite. On Linux/macOS, use `.venv/bin/python`.

Fresh demo databases provide these accounts:

| Role | Username | Password |
| --- | --- | --- |
| Owner | `jamie.parker` | `FormDemo2026!` |
| Member | `alex.morgan` | `FormDemo2026!` |

Existing databases receive usernames once during migration, so their names can differ. `python manage.py init-db` prints the existing owner's username. Demo mode never sends email or SMS, even when provider keys are configured.

Development can read `SMS_PROVIDER`, `WEBSMS_API_KEY` and `WEBSMS_SENDER` from the ignored `.env.local.json` file. Environment variables take precedence. Production and explicit test configurations ignore that file. `.env.example` documents deployment variables and is not loaded automatically.

## Checks and release package

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check static/app.js
.venv\Scripts\python.exe scripts/validate_release.py
.venv\Scripts\python.exe scripts/build_release.py
```

Set `TEST_DATABASE_URL` to a dedicated PostgreSQL test database to run database integration checks. Every PostgreSQL test uses its own temporary schema. Never point it at a member database. GitHub Actions runs the suite against PostgreSQL 17 and Python 3.12 and validates the production Gunicorn configuration.

The package is `dist/nf-hybrid-render.zip`, with a SHA-256 sidecar and a per-file manifest inside the archive. The builder uses an allowlist and rejects embedded values from private local configuration. It excludes databases, credentials, previews, editor files and virtual environments. Build from the intended release commit.

## Scope

Members can view workouts and available places, book or cancel sessions, see memberships and attendance, and maintain private progress records. Owners manage members, monthly access, classes, rosters and attendance. Booking rules enforce weekly limits, capacity, duplicate and overlapping reservations, and safe membership revocation on the server.

Account recovery for activated members, automated reminders, recurring timetable generation, payments, waitlists and separate coach accounts are not included. Use a controlled pilot and an agreed support process before broad rollout. Legacy email activation links and email-based API sign-in remain compatible; the portal itself uses usernames and SMS for new accounts.

Artwork provenance is recorded in [docs/brand.md](docs/brand.md). All fonts and images are served locally.
