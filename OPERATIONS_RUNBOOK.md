# Kompliance Operations Runbook

Status: local release candidate. Production remains on hold until the approvals in `RELEASE_CHECKLIST.md` are recorded.

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

After approval, configure the SMTP values in an untracked `.env`, test with a controlled recipient, then explicitly set both switches to `1`. Passwords must never be committed or included in screenshots or logs.

`KOMPLIANCE_BASE_URL` must be the canonical HTTPS application origin before email is considered ready. This prevents reset links being built from an untrusted request host.

The scheduler deduplicates reminders for the same resource, record and due date. Delivery attempts, failures and sent timestamps appear under **System & privacy**. Failed notifications remain available for an administrator retry.

## Monitoring

- `GET /api/health` is the liveness check.
- `GET /api/health/ready` verifies database access and required data roots.
- **System & privacy** runs SQLite quick-check, shows protected/local record counts, free space, sessions, audit count, email state and scheduler state.
- Review container logs and the application audit log after any release or delivery run.

## Retention and privacy

The administrator retention action can remove only:

- old local notification history;
- expired sessions;
- expired or already-used reset tokens.

It cannot select or delete protected snapshot records, submissions, certificates, evidence or uploaded documents. Every executed cleanup creates an audit event. Configure the privacy contact and retention period under **System & privacy**, then have the final wording reviewed by the organisation's privacy owner.

## Production release

Do not deploy from this runbook alone. Complete `RELEASE_CHECKLIST.md`, record the approved commit and rollback commit, verify both application and data backups, and obtain the named product and technical approvals first.
