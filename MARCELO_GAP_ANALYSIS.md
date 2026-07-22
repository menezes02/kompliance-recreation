# Marcelo Requirements Gap Analysis

Assessment date: 22 July 2026

## Executive status

- Current single-company customer pilot: approximately **85% complete**.
- Full multi-company platform described in Marcelo's notes: approximately **40–45% complete**.
- Production remains on hold pending pilot sign-off, release approval, backup references and a rollback commit.

The current product is a secured operations clone using one authorised customer snapshot plus isolated local workflows. Marcelo's document expands this into a multi-tenant worker identity and compliance network. Those are different delivery milestones.

## Module status

| Module | Estimate | Implemented | Principal gaps |
|---|---:|---|---|
| 1. Universal Worker Profile | 20% | Worker records, contact/training/Safe Pass views, application password recovery | Worker self-registration/account, mobile authentication, complete employment/skills/medical profile, worker QR, consented company sharing/revocation, external API, multi-company relationships, multilingual UI |
| 2. Document Management | 65% | Imported document libraries, PDF/image viewing, downloads, local version uploads, evidence, expiry states, reminders | Drag/drop multi-upload with progress, structured worker/company document ownership, replacement/deletion UI for local documents, automatic expiry extraction |
| 3. Compliance & Workflow | 40% | Forms/drafts/signatures/evidence/reports, certificate verification/revocation, expiry centre, email queue/retries, audit and roles | Internal messaging, requests, department routing, SMS/push/preferences, unread/viewed review state, supervisor document review, induction approval/decline/comments/history |
| 4. Responsive UI | 90% | Responsive navigation, dashboards, tables, forms, document viewers, desktop/mobile workflow checks | Exhaustive tablet/device accessibility and touch acceptance across every mapped route |
| 5. Demo Environment | 5% | Data boundaries and governance documentation | Separate fictional dataset, redacted/sample files, watermarking, automated PII scan and public-demo approval |
| 6. Data Migration | 40% | One customer snapshot with 3,597 immutable records and preserved source files/relationships | Repeatable per-client extract-transform-import pipeline, tenant mapping, reconciliation reports, additional authorised clients such as Grandbrind |
| 7. Business Outcomes | 30% | Reduced repeated entry inside local form workflows, centralised single-company operations, expiry visibility | Shared worker network, cross-company onboarding, third-party REST API, consent lifecycle, internationalisation and adoption tooling |

## Release-candidate work completed

- Immutable imported snapshot and isolated local writable records.
- Future snapshot refresh replaces only protected imported rows and preserves local pilot records.
- Administrator/editor/viewer authentication, CSRF, session revocation and audit history.
- Failed-login lockout, one-time password reset and recovery-request throttling.
- Real-definition form assignment, draft/resume, signatures, evidence, validation and multipage PDF reports.
- Numbered branded certificate PDFs, QR verification, replacement and revocation.
- Expiry centre for Safe Pass, GA1, risk assessment and local certificate dates.
- Deduplicated email queue, opt-in SMTP delivery, delivery history, retry controls and opt-in scheduler.
- System/privacy screen with database integrity, storage, readiness, branding, contacts and local-only retention.
- Consistent SQLite backup, file hashes, verification and empty-directory restore rehearsal.
- Desktop and 390 px browser acceptance with no console warnings or errors.

## Recommended delivery sequence

### Milestone A — Finish and pilot the current single-company release

1. Repair/start a working Docker engine and execute the clean-container smoke test.
2. Complete the pilot acceptance checklist with the company user.
3. Approve branding, privacy contact, retention period and SMTP provider/recipients.
4. Fix pilot defects, record backup/rollback references and obtain release approval.
5. Deploy the approved commit and run the production smoke test.

### Milestone B — Universal worker foundation

1. Introduce tenant/company, worker-account and company-worker relationship tables.
2. Build worker self-registration and account verification.
3. Build the complete editable worker profile and document ownership model.
4. Add worker QR/secure-link access with explicit consent grants and revocation.
5. Publish versioned, scoped REST API endpoints and API audit records.

This milestone must precede cross-company import, messaging and network adoption work.

### Milestone C — Supervisor workflow and communications

1. Department contacts and request routing.
2. Internal conversations linked to workers/documents/forms/assets.
3. Unread/viewed and supervisor review states.
4. Induction approval, decline, comments, additional-information request and history.
5. Notification preferences, then approved SMS/push provider integrations.

### Milestone D — International product and migration

1. Extract all interface text into translation keys; add English, Portuguese and Spanish.
2. Build repeatable tenant migration packages with source/target counts and relationship reconciliation.
3. Migrate additional clients only with per-client written authorisation.
4. Build a completely separate fictional demo tenant and automated PII/document watermark checks.

## Important product decision

The earlier instruction to use the available real customer data instead of demo documents is suitable only for the private authorised pilot. It does not satisfy Marcelo's public demo requirement. A sales/public demo must use a separate fictional tenant with no real personal or company information.

## Rough effort range

- Current single-company pilot to approved release: several focused development/acceptance days once Docker and approvals are available.
- Universal worker and supervisor-workflow MVP: approximately 12–20 full-time engineering weeks for one experienced developer, before extensive customer feedback.
- Hardened multi-tenant commercial platform with APIs, three languages, multi-client migrations and public demo controls: more realistically a multi-month product programme with security, privacy, QA and customer-operations support.

These ranges are planning estimates, not commitments; provider choices, legal/privacy decisions, migration quality and customer feedback can materially change them.
