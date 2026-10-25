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
- Member registration with an email or SMS invitation, chosen by the owner. The message contains the login email and a single-use link to choose a password, valid for 24 hours. SMS recipients still use their email to sign in.
- Invitation status and resending, including switching between email and SMS for an unactivated member. Demo mode provides an activation preview without sending real messages.
- Access for one month or up to twelve consecutive months, with a specific weekly allowance for those months.
- Update or revoke individual membership months. Revoking a month releases future bookings in that month; past records remain.
- Create and edit individual classes, including date, time, seats, coach, workout, and duration.
- Class rosters and attendance after a session starts.
- Cancel a class and release its bookings.

**Booking rules**

- Weeks run Monday–Sunday in the studio's timezone (`Asia/Nicosia` for Cyprus by default).
- The class's calendar month determines which membership and allowance apply. If a week crosses two months, each month's allowance is counted separately within that week.
- All reservations in a week/month count toward the allowance, including earlier sessions that week. Cancelled reservations do not count.
- Lowering an allowance keeps existing bookings; it prevents further reservations until the member is below the new limit.
- A booked class cannot move time or change duration. Cancel it and create a replacement instead. Capacity cannot be reduced below the current number of bookings.
- Seat allocation uses a database transaction, including when two members try for the last place simultaneously.

## Deploy the production version

The default `render.yaml` now creates a **paid production web service and paid managed PostgreSQL database**, both in Frankfurt. It disables demo data, applies database migrations before deployment, and uses Cyprus time (`Asia/Nicosia`). The app uses your existing **websms.com.cy** integration from the Barbershop project, with Resend for email.

Follow [PRODUCTION.md](PRODUCTION.md) for Render account requirements, estimated costs, exact environment settings, first-owner setup, provider configuration, launch verification, and backups. `.env.example` lists the variables without storing secrets. Deployment and real email/SMS checks still require your Render and provider accounts.

For a separate demo, use `render.demo.yaml`. Demo SQLite storage on a free service is temporary and is unsuitable for live members. Never point production at a demo database. No persistent disk is required for the PostgreSQL production deployment.

## Local development

Python 3.10 or newer is required. Render uses the latest Python 3.12 patch through `.python-version`. From this folder on Windows:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

Open [the local portal](http://127.0.0.1:5050).

On macOS/Linux, use `.venv/bin/python` instead. Gunicorn is used on Render/Linux; local Windows development uses Flask's development server. The database is created at `data/gym.sqlite3` unless `DATABASE_PATH` is set.

## Production and demo separation

Use a new PostgreSQL database for production. The `python manage.py init-db` pre-deploy command creates one owner using `OWNER_EMAIL`, `OWNER_NAME`, and `OWNER_PASSWORD`; remove `OWNER_PASSWORD` after signing in successfully. Later deploys preserve the owner and member data. Production refuses demo mode, missing PostgreSQL configuration, weak or missing session secrets, unencrypted database settings, and databases containing demo accounts.

For local development, leave `DATABASE_URL` unset and use SQLite. Local startup applies versioned migrations automatically. Set `AUTO_MIGRATE=false` when running the explicit pre-deploy command in production.

The app includes password hashing, secure production session cookies, CSRF protection, owner-only routes, private progress records, input validation, email/SMS invitations, database-backed login throttling, and session revocation after password changes. Password recovery, delivery callbacks, payments, automated reminders, recurring timetable generation, waitlists, and separate coach accounts remain future work; see the rollout notes in [PRODUCTION.md](PRODUCTION.md).

## Member invitations by email or SMS

The owner enters a name and email, chooses **Email** or **SMS**, and provides an international phone number for SMS (for example, `+35799123456`). Email remains the login username for both channels. The default SMS provider is WebSMS Cyprus, matching the Barbershop integration. The app creates the member and submits an invitation immediately; membership months can then be assigned separately. The owner does not choose or receive the member's password.

Configure these environment variables on the host before creating live members. `.env.example` lists the settings; the app does not automatically load `.env` files.

| Setting | Purpose |
| --- | --- |
| `PUBLIC_BASE_URL` | The portal's trusted HTTPS origin, such as `https://members.yourgym.com`, without a path, query, or fragment. Links never use the incoming request's Host header. |
| `RESEND_API_KEY` | Resend API key for email invitations. |
| `INVITE_FROM_EMAIL` | Authorized sender, such as `Your Gym <members@yourgym.com>`, on your verified sending domain. |
| `SMS_PROVIDER` | `websms` for the existing Cyprus provider. |
| `WEBSMS_API_KEY` | API key from your WebSMS account. |
| `WEBSMS_SENDER` | Sender name authorized for the gym. |

Email and SMS integrations use HTTPS, with no new Python dependencies. Configure only the channels you intend to use; an unconfigured channel returns an actionable error before creating a member. Set up the email domain and SMS sender, enable the intended destinations in the provider account, and test delivery to a controlled email address and phone before launch. Provider instructions: [Resend email API](https://resend.com/docs/api-reference/emails/send-email), [WebSMS API](https://www.websms.com.cy/en/sms-api).

Invitations use random single-use tokens; only their SHA-256 hashes are stored. The member chooses a password of at least ten characters and then signs in normally. A GET or message preview does not activate the account. Tokens are in the link fragment so they do not enter ordinary HTTP access logs. Do not add analytics or error reporting that records activation form bodies or page fragments.

The owner can see whether the provider accepted the request, whether sending was unconfirmed, whether the link expired, or whether the account was activated. **Provider acceptance does not confirm inbox or handset delivery.** This version does not process delivery receipts or bounces; inspect provider dashboards for downstream failures. Sending is synchronous with a ten-second network timeout and no automatic retry. A worker interruption can leave an invitation marked pending; it remains visible for the owner to retry.

If submission fails or times out, the member stays saved and the owner can resend from **Manage access** after one minute. A resend creates a new token and invalidates the previous link; it can also switch channel or correct the SMS number. An uncertain original submission may still arrive, so members should use the latest invitation. Already activated accounts cannot be reset through this invitation action; password recovery is a separate future feature. After a service restart, invitations and statuses remain available in the database.

With `DEMO_MODE=true`, **no email or SMS is sent**, even if provider keys are present. New members receive a demo activation preview in the owner interface. Use the preview to test the full password setup journey. Members created in demo mode are blocked when demo mode is disabled. Always launch production against a new empty database as described above.

## Checks

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check static/app.js
```

The automated checks cover role and session protection, membership visibility, weekly limits, duplicate bookings, cancellation ownership, overlapping classes, concurrent last-seat bookings, membership revocation, access across year boundaries, member creation, private progress records, booked-class edits, future attendance restrictions, email/SMS invitation requests, provider failures, contact validation, token expiry, resend invalidation, concurrent activation, demo previews, and invitation persistence. Provider calls are mocked; these checks do not send messages.

## Files

```text
app.py                Flask API, authentication, booking rules, owner bootstrap
database.py           PostgreSQL/SQLite access, transactions, versioned migrations
manage.py             Explicit pre-deploy migration command
migrations/           Versioned database schema changes
PRODUCTION.md         Live deployment and operations guide
invitations.py        HTTPS email/SMS delivery adapters and invitation configuration
localization.py       Greek messages and safe sample-record translation
static/app.js         Client and owner interfaces
static/style.css      Responsive styling
static/fonts.css      Self-contained local font fallbacks
templates/index.html  Page shell
render.yaml           Paid PostgreSQL production Blueprint
render.demo.yaml      Separate free demo Blueprint
requirements.txt      Python dependencies
tests/test_portal.py  Booking and access checks
```

All assets are self-contained; no third-party font or image service is required.
