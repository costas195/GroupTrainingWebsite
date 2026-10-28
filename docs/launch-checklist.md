# NF Hybrid release record — 28 October 2026

## Completed locally

- [x] Minimal Greek sign-in page and NF Hybrid branding; desktop and phone layout reviewed.
- [x] Username generation, collision handling, immutable IDs and owner/member username editing.
- [x] SMS temporary credentials, 24-hour expiry, mandatory first-login change and resend invalidation.
- [x] Salted password hashes, private configuration exclusion and production configuration guards.
- [x] All **77 tests passed without skips**, including PostgreSQL 17.11 booking, account, concurrency and migration checks.
- [x] Production-mode smoke test: PostgreSQL over TLS, secure owner login, `/health`, an empty member database and persistence after reinitialization.
- [x] JavaScript syntax and installed dependency consistency checks passed.
- [x] Both Blueprints validated against Render's current published schema.
- [x] Twelve installed runtime packages checked against PyPI advisory data; no published advisories returned for those versions. This is a point-in-time check, not a guarantee against undiscovered vulnerabilities.
- [x] Release builder tested for secret exclusion, archive integrity and reproducibility.
- [x] Obsolete starter files and promotional CSS removed; old release ZIPs preserved under ignored `previews/archive/`.
- [x] The earlier single SMS provider test was received by the user. No further live SMS was sent during release checks.

Local tests used Windows/Python 3.14 with an isolated PostgreSQL server. The repository workflow separately checks the target Linux/Python 3.12 environment, including Gunicorn configuration. Select a release commit only after that workflow is green.

## Required in the live Render account

- [ ] Sign in to Render and connect the repository.
- [ ] Select the tested `codex/production-launch` commit and review the proposed paid resources.
- [ ] Enter the initial owner's name, email, username and private password.
- [ ] Enter the existing WebSMS key directly in Render; keep the key out of Git and release packages.
- [ ] Create the web service and new PostgreSQL database after approving the cost.
- [ ] Verify HTTPS, health, first owner sign-in and absence of demo data.
- [ ] Remove `OWNER_PASSWORD` after the first successful sign-in.
- [ ] Verify one complete member invitation from the deployed service, including the updated **NF Hybrid** sender.
- [ ] Check first-password setup, booking, cancellation and persistence across a redeploy.
- [ ] Rehearse backup restoration and agree support/privacy/retention and account-recovery procedures before broad rollout.

This record does not claim that a live deployment or Render restore rehearsal has occurred. The application is prepared for a controlled pilot; activated-member forgotten-password recovery remains outside this release.
