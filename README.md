# FORM — small group training portal

A working, mobile-friendly draft of a gym member portal and owner CRM. FORM is placeholder branding that can be changed for your gym.

The demo interface, calendar, validation messages, and fictional training records are in Greek. Demo emails and passwords stay the same. Existing sample records are translated automatically on startup; bookings and custom-written content are preserved.

## Try it

The front page includes **Client demo** and **Owner demo** buttons when demo mode is enabled.

| Account | Email | Password |
| --- | --- | --- |
| Client | `client@form.demo` | `FormDemo2026!` |
| Owner | `owner@form.demo` | `FormDemo2026!` |

The first launch creates fictional members, roughly twelve weeks of sample classes around the launch date, memberships for the current month and the following two months, and example progress records. These dates are generated once, when the database is first created. Sunday is a rest day. The client demo opens the next available training day when today's sessions have ended.

This is a shared demo: changes made by one visitor are visible to other visitors using the same account. Use fictional information while evaluating it.

## What works

**Client portal**

- Password login and sign-out.
- Monday–Sunday training calendar, month selection, and class-type filters.
- Available seats, coach, time, duration, and the complete warm-up, main workout, and finisher for each session.
- Booking and cancellation before the session starts; booking prevents duplicate reservations, overlapping sessions, and overbooking.
- Monthly membership visibility and booking access, with weekly limits enforced on the server.
- Upcoming bookings and past sessions, with coach-marked attendance.
- Optional body-weight check-ins, a weight trend chart, exercise weights and reps, personal bests, and training notes.
- Editable goals, training priorities, name, and password.

**Owner CRM**

- Studio overview showing members, classes, weekly bookings, and occupancy.
- Member registration with temporary passwords. Share credentials directly; the draft does not send email.
- Access for one month or up to twelve consecutive months, with a specific weekly allowance for those months.
- Update or revoke individual membership months. Revoking a month releases future bookings in that month; past records remain.
- Create and edit individual classes, including date, time, seats, coach, workout, and duration.
- Class rosters and attendance after a session starts.
- Cancel a class and release its bookings.

**Booking rules**

- Weeks run Monday–Sunday in the studio's timezone (`Europe/Bucharest` by default).
- The class's calendar month determines which membership and allowance apply. If a week crosses two months, each month's allowance is counted separately within that week.
- All reservations in a week/month count toward the allowance, including earlier sessions that week. Cancelled reservations do not count.
- Lowering an allowance keeps existing bookings; it prevents further reservations until the member is below the new limit.
- A booked class cannot move time or change duration. Cancel it and create a replacement instead. Capacity cannot be reduced below the current number of bookings.
- Seat allocation uses a database transaction, including when two members try for the last place simultaneously.

## Deploy to Render

### Option A — Blueprint (the included configuration)

1. Create a GitHub repository and upload the **contents of this folder**, so `app.py`, `requirements.txt`, and `render.yaml` are at the repository root. Do not upload `.venv`, `data`, or local environment files.
2. In Render, choose **New → Blueprint** and connect the repository.
3. Render reads `render.yaml`, creates a Python web service, and generates a session secret. Deploy it, then open its service URL.
4. Use the two demo buttons on the front page to explore both roles.

If you place this folder inside an existing repository, set the service's **Root Directory** to `GroupTrainingWebsite` when creating a web service manually. For a Blueprint in a parent repository, move `render.yaml` to that repository's root and add `rootDir: GroupTrainingWebsite` to its service.

### Option B — create a web service manually

| Render field | Value |
| --- | --- |
| Runtime | Python 3 |
| Root Directory | Blank if these files are at the repository root; otherwise `GroupTrainingWebsite` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn --workers 1 --threads 4 --bind 0.0.0.0:$PORT app:app` |
| Health Check Path | `/health` |
| Instance Type | Free, for trying the draft |

Set these environment variables:

- `SECRET_KEY`: a long random secret. Generate one locally with `python -c "import secrets; print(secrets.token_hex(32))"`. Keep it private and stable between deployments.
- `DEMO_MODE`: `true`
- `GYM_TIMEZONE`: `Europe/Bucharest`, or your gym's IANA timezone.

### Saving data across Render restarts

The included **free demo uses SQLite on the service's temporary filesystem**. Changes can disappear on restart, spin-down, or redeployment, and sample data will be recreated if the database is lost. This is suitable for reviewing the draft. See [Render's free-service storage limitations](https://render.com/docs/free).

For durable SQLite storage, use a paid web service with a persistent disk mounted at `/var/data`, and set `DATABASE_PATH=/var/data/gym.sqlite3`. Keep **one service instance and one Gunicorn worker** with this SQLite architecture. Set up disk backups. For multiple instances or a larger production service, migrate to Postgres.

Render references: [Flask deployment](https://render.com/docs/deploy-flask), [Blueprint configuration](https://render.com/docs/blueprint-spec), [free-service limitations](https://render.com/docs/free), [persistent disks](https://render.com/docs/disks).

## Local development

Python 3.10 or newer is required. Render uses the latest Python 3.12 patch through `.python-version`. From this folder on Windows:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

Open [the local portal](http://127.0.0.1:5050).

On macOS/Linux, use `.venv/bin/python` instead. Gunicorn is used on Render/Linux; local Windows development uses Flask's development server. The database is created at `data/gym.sqlite3` unless `DATABASE_PATH` is set.

## Moving beyond the demo

This is a functional draft for review, not a completed production launch. Before inviting actual members, use durable storage and switch to a **new, empty database path** with:

```text
DEMO_MODE=false
DATABASE_PATH=/var/data/live-gym.sqlite3
OWNER_EMAIL=your-real-email@example.com
OWNER_NAME=Your Name
OWNER_PASSWORD=a-unique-private-password-of-at-least-12-characters
SECRET_KEY=a-stable-random-private-secret
GYM_TIMEZONE=Europe/Bucharest
```

On the first boot against the empty database, the app creates that owner and no sample data. On later boots, it preserves all data and does not reset the owner's password. Remove `OWNER_PASSWORD` from the service environment after successful initialization. Switching `DEMO_MODE` off also blocks existing demo accounts, including their signed-in sessions; it does not turn a demo account into a live owner.

The draft includes password hashing, session cookies, CSRF protection, owner-only routes, private progress records, input validation, and a basic process-local login attempt limit. A production launch should add invitation and password-reset email, verified delivery of schedule changes, a reviewed privacy/retention policy for member progress, operational monitoring, and a stronger shared rate limiter. Payments, automated reminders, recurring timetable generation, waitlists, and a coach's individual progress dashboard are outside this draft.

## Checks

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check static/app.js
```

The automated checks cover role and session protection, membership visibility, weekly limits, duplicate bookings, cancellation ownership, overlapping classes, concurrent last-seat bookings, membership revocation, access across year boundaries, member creation, private progress records, booked-class edits, and future attendance restrictions.

## Files

```text
app.py                Flask API, authentication, SQLite storage, sample data
localization.py       Greek messages and safe sample-record translation
static/app.js         Client and owner interfaces
static/style.css      Responsive styling
static/fonts.css      Self-contained local font fallbacks
templates/index.html  Page shell
render.yaml           Render Blueprint
requirements.txt      Python dependencies
tests/test_portal.py  Booking and access checks
```

All assets are self-contained; no third-party font or image service is required.
