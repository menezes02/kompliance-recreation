# Kompliance Operations Runbook

Status: private pilot deployed for controlled customer acceptance. Commercial release remains conditional on the approvals in `RELEASE_CHECKLIST.md`.

## Fresh local container validation

The validation compose file publishes only the application on localhost and does not contact the production service.

```powershell
docker-compose -f compose.local.yaml config
docker-compose -f compose.local.yaml build app
docker-compose -f compose.local.yaml up -d app
curl.exe http://127.0.0.1:18090/api/health/ready
docker-compose -f compose.local.yaml logs --tail 100 app
docker-compose -f compose.local.yaml down
```

The persistent validation volume is named `kompliance_data_example`. Do not remove it when testing restart persistence.

## Backup

The backup contains only writable local application data. It never includes `source-archive` or `production-data`, and the consistent database copy is scrubbed of cached protected snapshot rows. The live database is never changed. A restored application re-imports protected rows from its separately controlled production snapshot.

```powershell
python backup_kompliance.py --data-root local-app/data --output C:\Backups\kompliance-local-YYYYMMDD.zip
python verify_kompliance_backup.py C:\Backups\kompliance-local-YYYYMMDD.zip
```

Container volume backup:

```powershell
docker-compose -f compose.local.yaml exec app python /app/backup_kompliance.py --data-root /app/local-app/data --output /app/local-app/data/backups/kompliance-local.zip
docker-compose -f compose.local.yaml exec app python /app/verify_kompliance_backup.py /app/local-app/data/backups/kompliance-local.zip
```

The production compose project also runs `kompliance_operations_example`. It
performs a readiness probe every minute and creates a checksum-verified backup
of writable local data every 24 hours by default. Backups are stored under
`local-app/data/backups/automated` in the named volume. The service never
includes, modifies or deletes the protected source archive, production
snapshot, or older backups. Its latest state is visible under **System &
privacy**.

Configure only through the untracked deployment environment:

```text
KOMPLIANCE_AUTOMATED_BACKUPS=1
KOMPLIANCE_BACKUP_INTERVAL_SECONDS=86400
KOMPLIANCE_MONITOR_INTERVAL_SECONDS=60
```

Verify the runner independently with `python verify_operations.py`.

To rehearse a restore, provide a new or empty target directory. The verifier refuses non-empty targets and never modifies the live data directory.

```powershell
python verify_kompliance_backup.py C:\Backups\kompliance-local-YYYYMMDD.zip --restore-to C:\Temp\kompliance-restore-rehearsal
```

## Email and scheduler

Both features fail closed. Keep these defaults until the external-service approval is recorded:

```text
KOMPLIANCE_EMAIL_DELIVERY=0
KOMPLIANCE_SCHEDULER=0
```

After approval, configure either SMTP or the Gmail API OAuth values in an untracked `.env`, test with a controlled recipient, then explicitly set both switches to `1`. Gmail OAuth setup is documented in `GMAIL_OAUTH_SETUP.md` and requests only `gmail.send`. Passwords, client secrets and tokens must never be committed or included in screenshots or logs.

`KOMPLIANCE_BASE_URL` must be the canonical HTTPS application origin before email is considered ready. This prevents reset links being built from an untrusted request host.

The scheduler deduplicates reminders for the same resource, record and due date. Delivery attempts, failures and sent timestamps appear under **System & privacy**. Failed notifications remain available for an administrator retry.

## Monitoring

- `GET /api/health` is the liveness check.
- `GET /api/health/ready` verifies database access and required data roots.
- **System & privacy** runs SQLite quick-check, shows protected/local record counts, free space, sessions, audit count, email state and scheduler state.
- Review container logs and the application audit log after any release or delivery run.
- `kompliance_operations_example` persists its last readiness check, verified
  backup reference, checksum and error state for the administrator dashboard.

## Multi-factor authentication

Administrators, editors and viewers can enrol a TOTP-compatible authenticator
under **Change password**. Enrolment requires the current password and one valid
authenticator code. Ten one-time backup codes are shown once. Enabling or
disabling MFA revokes the account's other sessions and is written to the audit
log. Administrators can see MFA status, but never secrets or backup codes, in
**Access management**.

## Integration API safeguards

Bearer-token API calls are limited per token (120 requests/minute by default).
The shared-worker list uses `page` and `page_size`, capped at 100 records per
response, and exposes rate-limit headers. Override the limit only through
`KOMPLIANCE_API_RATE_LIMIT_PER_MINUTE`.

## Retention and privacy

The administrator retention action can remove only:

- old local notification history;
- expired sessions;
- expired or already-used reset tokens.

It cannot select or delete protected snapshot records, submissions, certificates, evidence or uploaded documents. Every executed cleanup creates an audit event. Configure the privacy contact and retention period under **System & privacy**, then have the final wording reviewed by the organisation's privacy owner.

## Production release

Before a customer review, open `/review` as an administrator. Technical blockers must
be zero. Attention items are customer or owner decisions; a controlled hold is expected
for the automatic scheduler until recipients and intervals are approved.

Run the review-centre regression locally:

```powershell
python verify_review_centre.py
```

The read-only browser regression is `verify_review_browser.mjs`. It checks desktop and
390-pixel layout, the acceptance form, safe diagnostic controls, console errors and
page overflow. It performs no customer-record mutation and sends no email.

Do not deploy from this runbook alone. Complete `RELEASE_CHECKLIST.md`, record the approved commit and rollback commit, verify both application and data backups, and obtain the named product and technical approvals first.
