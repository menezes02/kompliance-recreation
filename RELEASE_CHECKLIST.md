# Kompliance Release Checklist

Status: **PILOT READY — deployed for controlled customer acceptance; commercial release approval remains pending**

## Current pilot release record

- Live URL: `https://kompliance.felipeitprojects.com/`
- Application release commit: `fc5ac80c778032e7d4b56c53cf0a7b6d0c4808b0`
- Documentation/handoff branch commit: recorded in Git history after this checklist update
- Rollback package: `/home/vulcano/apps/kompliance/backups/predeploy-20260722-commercial-hardening`
- Verified post-deployment backup: `/home/vulcano/apps/kompliance/backups/postdeploy-fc5ac80/kompliance-local-data.zip`
- Verified pilot-ready backup: `/home/vulcano/apps/kompliance/backups/pilot-ready/pilot-ready-20260722T113541Z.zip`
- Pilot-ready backup SHA-256: `c38b513e4a8f46c8325163d67c482601300b1300ebb88c87f61166c98002b516`
- Verified workstation copies: `workstation-backups/`
- Protected snapshot: 3,597 immutable records
- Source archive: 3,077 files / 775,800,726 bytes, mounted read-only
- Live services: application, gateway and operations containers healthy
- Pilot accounts: one administrator, one Viewer and one Editor; role boundaries live-tested
- Live readiness: HTTPS `/api/health/ready` returned HTTP 200
- Database integrity: `ok`
- Browser smoke test: passed with no console errors

The technical deployment checks above are complete. The unchecked approval and acceptance items below remain intentionally open for the named customer and technical owners.

This checklist protects the existing customer-facing installation and preserves the imported source archive. A production release must not begin until every item in the approval section is recorded.

## Release approval

- [ ] Product owner has approved the release scope and named the approver.
- [ ] Technical owner has approved the deployment window and named the approver.
- [ ] The Git commit or tag to deploy is recorded.
- [ ] A rollback Git commit or tag is recorded.
- [ ] The server operator has confirmed a maintenance window.

## Backup before deployment

- [ ] Back up the current application directory or Docker image reference.
- [ ] Back up the current `production-data` volume/directory.
- [ ] Back up `source-archive` without changing its contents.
- [ ] Back up the current reverse-proxy configuration and Basic Auth file.
- [ ] Create a local-data ZIP with `backup_kompliance.py` and pass `verify_kompliance_backup.py`.
- [ ] Rehearse extraction into a new empty directory and open the restored SQLite database.
- [ ] Verify that each backup can be listed and read before continuing.
- [ ] Record backup locations and timestamps in the release notes.

## Configuration and security

- [ ] Keep `.env`, password files, databases, logs, and local uploads out of Git.
- [ ] Confirm `KOMPLIANCE_APP_AUTH=1` in the deployed application container.
- [ ] Confirm HTTPS and the expected hostname.
- [ ] Confirm `/api/health/ready` returns HTTP 200 through the deployed route.
- [ ] Confirm **Review & acceptance** reports zero technical blockers.
- [ ] Confirm container names remain `kompliance_app_example` and `kompliance_gateway_example`.
- [ ] Confirm the application data volume is writable only where local records are stored.
- [ ] Confirm the imported source archive is mounted read-only.
- [ ] Create the first application administrator through the one-time setup screen.
- [ ] Store administrator credentials in the approved password manager.
- [ ] Record the privacy contact, retention period and approved privacy notice.
- [ ] Keep email and scheduler disabled unless the external-service approval is recorded.
- [ ] If approved, store SMTP or Gmail OAuth secrets only in the untracked deployment environment and send one controlled test.
- [ ] Confirm worker email verification is enabled and uses the approved sender/provider.
- [ ] Store company API tokens only in an approved secret manager; never in Git or logs.
- [ ] Complete tenant-isolation and consent/revocation security testing before enabling multiple production companies.

## Deployment

- [ ] Pull the approved commit or tag.
- [ ] Run `docker-compose config` and review the resolved configuration.
- [ ] Build the application image.
- [ ] Start the stack without removing unrelated containers.
- [ ] Check container health and logs for startup errors.

## Smoke test

- [ ] Anonymous API access is rejected.
- [ ] Admin login and logout work.
- [ ] Viewer, editor, and admin permissions behave as documented.
- [ ] Dashboard totals load.
- [ ] GA1, GA2, and GA3 records can be searched, filtered, and viewed.
- [ ] An archived PDF opens in the browser viewer and can be downloaded.
- [ ] Induction, asset QR, training, and custom-form views load.
- [ ] A local-only assignment and submission can be created by an authorised role.
- [ ] A real form definition can be saved as a draft, completed, signed, and submitted.
- [ ] Evidence can be attached only to the matching local assignment.
- [ ] A completed submission report PDF can be generated and opened.
- [ ] A local certificate PDF can be generated, publicly verified, replaced, and revoked.
- [ ] The expiry centre classifies overdue, due-soon, current, and missing-date records.
- [ ] Reminder preparation creates local notification records and sends nothing automatically.
- [ ] Duplicate reminder preparation does not create duplicate queue records.
- [ ] Delivery history records attempts, sent status and safe failure detail.
- [ ] System & privacy shows database integrity, storage and service state.
- [ ] Review & acceptance aggregates role, MFA, email, privacy, scheduler, backup and sign-off status.
- [ ] A controlled test email records a sent result or a safely redacted provider failure.
- [ ] Review evidence can be printed and downloaded without secrets or full diagnostic recipients.
- [ ] Retention cleanup reports zero protected records.
- [ ] Password recovery tokens expire, work once, and revoke prior sessions.
- [ ] Five failed logins lock the account for the configured period.
- [ ] Audit events appear for authenticated mutations.
- [ ] Worker registration, verification, login, recovery and logout work.
- [ ] Worker QR/public fields reveal only the selected public profile fields.
- [ ] QR scan and manual paste both create a pending company request without exposing private fields.
- [ ] Worker approval can narrow the requested fields; decline and duplicate response create no access.
- [ ] Tenant A cannot see Tenant B access requests and an active grant blocks duplicate requests.
- [ ] A company sees only fields/documents in its active worker consent grant.
- [ ] Worker revocation immediately blocks the secure link, company view and REST API.
- [ ] Company import creates/refreshes only its local tenant worker record.
- [ ] Tenant A cannot list Tenant B records, users, settings, files, audit events or source archive.
- [ ] API token creation/read/revocation works and successful reads are audited.
- [ ] `/api/openapi.json` is valid OpenAPI 3.1 and matches the implemented consent and bearer routes.
- [ ] Worker requests route only to an active contact in the selected tenant department.
- [ ] Request status history and induction decision history retain every transition.
- [ ] Company and worker conversation replies are visible only to the matching tenant and worker.
- [ ] In-app unread/read state works for both company and worker accounts.
- [ ] SMS and push remain unavailable until approved providers are explicitly configured.
- [ ] English, Portuguese and Spanish can be selected, survive navigation and reload, and do not alter customer record values.
- [ ] A tenant migration package passes path, size and checksum validation before dry run.
- [ ] Dry-run reconciliation matches source counts and creates no target records.
- [ ] Migration apply is attempted only against an isolated tenant with recorded customer authorisation and a fresh backup.
- [ ] Relationship IDs, attachments and per-resource counts reconcile after migration; package replay is rejected.
- [ ] `python -m unittest local-app/test_universal_workers.py -v` passes in a fresh test volume.
- [ ] No imported source record can be edited or deleted.

## Rollback trigger and procedure

Rollback immediately if authentication fails, imported records become mutable, archived files cannot be served, or the main workflows fail their smoke tests.

1. Stop only the Kompliance containers.
2. Restore the recorded application image/commit and configuration.
3. Restore local writable data only if a migration changed it.
4. Keep the imported source archive unchanged.
5. Restart the prior stack and repeat the read-only smoke checks.
6. Record the incident and do not retry the release without a new approval.
