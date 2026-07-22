# Kompliance Release Checklist

Status: **HOLD — package verified locally, production release not yet authorised**

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
- [ ] Confirm container names remain `kompliance_app_example` and `kompliance_gateway_example`.
- [ ] Confirm the application data volume is writable only where local records are stored.
- [ ] Confirm the imported source archive is mounted read-only.
- [ ] Create the first application administrator through the one-time setup screen.
- [ ] Store administrator credentials in the approved password manager.
- [ ] Record the privacy contact, retention period and approved privacy notice.
- [ ] Keep email and scheduler disabled unless the external-service approval is recorded.
- [ ] If approved, store SMTP secrets only in the untracked deployment environment and send one controlled test.
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
- [ ] Retention cleanup reports zero protected records.
- [ ] Password recovery tokens expire, work once, and revoke prior sessions.
- [ ] Five failed logins lock the account for the configured period.
- [ ] Audit events appear for authenticated mutations.
- [ ] Worker registration, verification, login, recovery and logout work.
- [ ] Worker QR/public fields reveal only the selected public profile fields.
- [ ] A company sees only fields/documents in its active worker consent grant.
- [ ] Worker revocation immediately blocks the secure link, company view and REST API.
- [ ] Company import creates/refreshes only its local tenant worker record.
- [ ] Tenant A cannot list Tenant B records, users, settings, files, audit events or source archive.
- [ ] API token creation/read/revocation works and successful reads are audited.
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
