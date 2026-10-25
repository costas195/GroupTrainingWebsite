# Cyprus production deployment

This release runs a Flask web service and managed PostgreSQL on Render. It uses the same **websms.com.cy** SMS protocol as the Barbershop project and Resend for invitation emails. It starts with a clean live database and creates one owner; no fictional members or classes are loaded.

## Accounts and estimated cost

| Item | What to arrange |
| --- | --- |
| Render | Account with billing enabled and access to the GitHub repository. The Blueprint creates one paid web service and one paid PostgreSQL database, both in Frankfurt. |
| Website address | Render provides a working HTTPS address immediately. A custom domain can be connected later. |
| Sending domain | A domain you own, with access to its DNS settings, for Resend verification. The website and email sender may use separate subdomains. |
| Resend | Sending API key and a verified sender such as `Gym Name <members@your-domain.com>`. |
| WebSMS | Existing WebSMS API key, sufficient credits, and a sender name authorized for this gym. Configure the sender for the gym rather than the barbershop's brand. |
| Owner | Real name, email, and a unique initial password of at least 12 characters. |

The prepared baseline uses web plan `0.5c-512mb` ($7/month) and PostgreSQL plan `0.1c-256mb` ($6/month) with 1 GB storage. Allow **about $13/month for Render compute**, plus any storage beyond the included allowance, bandwidth overages, taxes, domain registration, email plan, and SMS credits. Confirm the checkout total before creating paid resources. These are small starting plans; resize them if measured usage requires it. Prices checked on 25 October 2026: [Render pricing](https://render.com/pricing), [compute plans](https://render.com/docs/compute-plans). Provider billing remains separate: [Resend](https://resend.com/pricing), [WebSMS](https://www.websms.com.cy/en).

## Deploy with the included Blueprint

1. Upload or push the updated project files to `https://github.com/costas195/GroupTrainingWebsite`. Include `database.py`, `manage.py`, the `migrations/` directory, `invitations.py`, `requirements.txt`, `render.yaml`, templates, and static files. Do not upload local databases, `.env`, provider keys, `.venv`, or `previews/`.
2. In Render, choose **New → Blueprint**, connect that repository, select the branch containing this release, and use `render.yaml` at the repository root.
3. Review the two new resource names: `form-gym-portal-production` and `form-gym-production-db`. These are separate from the demo service and use a new database. The prepared database blocks external network connections and connects internally to the web service.
4. Enter the values requested by the Blueprint. Keep secrets in Render's Environment page, not in Git, screenshots, logs, or chat.
5. Approve the displayed paid-resource cost and create the Blueprint. Render installs dependencies, runs `python manage.py init-db`, and starts Gunicorn with two workers. The migration command creates or updates the schema and initializes the owner once.
6. Open the web service's generated HTTPS URL and sign in with the owner email and initial password. The demo buttons must be absent and there must be no sample members or classes.
7. After successful owner sign-in, remove `OWNER_PASSWORD` from the web service's environment. Future migrations preserve the existing owner and do not need this password. Keep `SECRET_KEY` stable.
8. Complete the live checks below before sharing the portal with members.

If your existing demo is managed by another Blueprint, create a **separate** production Blueprint. Do not apply this configuration blindly to an existing database or rename existing resources. Keep the existing demo on its current code until you explicitly update it; `render.demo.yaml` is supplied for a separate demo deployment.

## Environment settings

| Setting | Value / source |
| --- | --- |
| `APP_ENV` | `production` — supplied by the Blueprint. |
| `DEMO_MODE` | `false` — supplied by the Blueprint. |
| `AUTO_MIGRATE` | `false` — migrations run in the pre-deploy step instead of every worker startup. |
| `DATABASE_URL` | Supplied automatically from the new database's internal connection string. Never use the demo SQLite file. |
| `DATABASE_SSLMODE` | Defaults to `require`. Production refuses to disable database encryption. |
| `SECRET_KEY` | Render generates this automatically. Keep it private and stable. |
| `GYM_TIMEZONE` | `Asia/Nicosia` — Cyprus local time, including daylight saving. |
| `PUBLIC_BASE_URL` | Initially omit it: the app uses Render's `RENDER_EXTERNAL_URL`. After connecting a custom domain, set its HTTPS origin, without a path or query. |
| `OWNER_EMAIL` | Your actual owner sign-in email. |
| `OWNER_NAME` | Owner's display name. |
| `OWNER_PASSWORD` | Initial private password, minimum 12 characters. Remove after first sign-in. |
| `RESEND_API_KEY` | Sending API key from Resend. |
| `INVITE_FROM_EMAIL` | Sender on the domain verified in Resend. |
| `SMS_PROVIDER` | `websms` — supplied by the Blueprint. |
| `WEBSMS_API_KEY` | From your existing WebSMS account. |
| `WEBSMS_SENDER` | Sender name authorized for this gym. |

The owner can create members using a configured channel while the other channel is being prepared. An unconfigured selected channel returns an error before creating a member. The app does not read `.env` files automatically; `.env.example` is a reference only.

## Email and SMS

For email, add your domain to Resend and publish the DNS records it provides. Wait until the domain is verified, then configure the API key and sender in Render. Keep open/click tracking off for activation messages. [Resend domain setup](https://resend.com/docs/dashboard/domains/introduction).

For SMS, this release posts form data to `https://websms.com.cy/api/send-sm`, matching the Barbershop integration. Members enter international numbers such as `+35799123456`; the adapter submits `35799123456` to WebSMS. The API key is sent in the HTTPS request body, never in the URL. A response with `status: "ok"` confirms provider acceptance. Provider responses and API keys are not included in user-facing errors or application logs. [WebSMS API overview](https://www.websms.com.cy/en/sms-api).

SMS invitations use compact English text to reduce message segmentation. The Greek portal and email remain in Greek. Long email addresses or portal domains can still produce more than one billable SMS segment; confirm actual credit use in the WebSMS dashboard.

The member receives their login email and a single-use password setup link that expires after 24 hours. The owner can resend after one minute, switch channel, or correct the SMS number. Resending invalidates the old link. The database stores only token hashes. Provider acceptance does not confirm inbox/handset delivery: delivery receipts, bounce callbacks, and automatic retries are not implemented. Check provider dashboards for downstream problems.

## Live verification

1. Confirm the pre-deploy command succeeds, `/health` returns `{"status":"ok"}`, and the portal uses HTTPS.
2. Sign in as owner, create a class, refresh, and confirm it remains. Redeploy once and confirm the class and owner remain.
3. Create a controlled test member using your own email. Confirm receipt, activate the account, sign in, and confirm the activation link cannot be reused. Assign that member a membership month before testing bookings.
4. Repeat with a phone you control and SMS delivery. Check the sender name, full link, and credit charge. No real messages were sent by the automated test suite.
5. Test a booking and cancellation on a phone and desktop. Confirm the local class time is correct for Cyprus.
6. Set an external uptime check on `/health` and enable Render deploy-failure notifications. Review application and provider errors without logging request bodies or activation tokens.
7. Review the privacy notice and retention policy for member data, and publish a support contact and your booking/cancellation rules.

## Backups and recovery

Paid Render PostgreSQL provides point-in-time recovery: currently 3 days on Hobby workspaces and 7 days on Pro or higher. Free databases have no recovery capability. See [Render recovery and backups](https://render.com/docs/postgresql-backups).

Before sharing the app widely, create an on-demand logical export, store a copy in a private backup location, and rehearse recovery into a separate database. A real restore rehearsal is still required on your Render account. For an incident, recover to a **new** database, check its contents, update `DATABASE_URL`, redeploy, and verify member sign-in and bookings before resuming service. The Blueprint blocks public database access; exports and restores can be managed through Render or its private service shell.

Do not use application rollback as a database rollback. Migrations are versioned and currently additive; a future schema change must remain compatible with the previous release during deployment. The app refuses to migrate a database newer than its code.

## Tests and current limits

Local checks:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check static/app.js
```

Set `TEST_DATABASE_URL` to a dedicated PostgreSQL test database to run the PostgreSQL integration classes as well. Each check creates and removes its own temporary schema; do not point tests at production. GitHub Actions runs the SQLite checks and the same booking/invitation rules against PostgreSQL 17 on Python 3.12.

Production uses database-backed login throttling shared across workers, secure cookies, a trusted host list, session revocation after password changes, and an advisory transaction lock around studio writes. The single-studio write lock deliberately serializes writes so capacity, overlap, and membership checks remain consistent across workers. The small initial plans and this locking strategy should be reviewed before substantially increasing traffic or adding multiple gyms.

This is an initial production release for a controlled pilot. Self-service forgotten-password recovery, verified message delivery callbacks, scheduled reminders, recurring timetables, payments, waitlists, and separate coach accounts remain future work. For now, signed-in users change passwords in their profile; an activated account cannot be reset by resending its original invitation. Finish account-recovery support before broad member rollout.
