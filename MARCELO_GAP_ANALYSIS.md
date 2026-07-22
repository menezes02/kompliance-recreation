# Marcelo Requirements Gap Analysis

Assessment date: 22 July 2026

## Executive status

- Current single-company customer pilot: approximately **90% complete**.
- Full multi-company platform described in Marcelo's notes: approximately **65–70% complete**.
- Production remains on hold pending pilot sign-off, release approval, backup references and a rollback commit.

The current product is a secured operations clone using one authorised customer snapshot plus isolated local workflows. Marcelo's document expands this into a multi-tenant worker identity and compliance network. Those are different delivery milestones.

## Module status

| Module | Estimate | Implemented | Principal gaps |
|---|---:|---|---|
| 1. Universal Worker Profile | 80% | Free self-registration, email verification/recovery, editable complete profile, worker QR/public profile, field-level company consent/revocation, tenant relationships/import, revocable audited REST API, English/Portuguese/Spanish preference architecture | Approved SMS/mobile OTP provider, camera-based QR scanner/request handshake, full translation of every company screen, formal OpenAPI/client SDK |
| 2. Document Management | 78% | Imported libraries, PDF/image viewing/download, worker-owned categories, drag/drop multi-upload/progress, validation, preview/delete, automatic versions, expiry colours/reminders, tenant document review | Automatic expiry extraction from document content, company plant/equipment/site ownership refinements, visual version-history grouping |
| 3. Compliance & Workflow | 82% | Forms/drafts/signatures/evidence/reports, certificate verification/revocation, expiry centre, email queue/retries, audit/roles, per-company worker-document reviews, routed requests, internal worker/company conversations, induction decisions/comments/history, in-app notifications and channel/language preferences | Approved SMS/push providers, provider delivery receipts/escalations, richer supervisor queues and formal customer acceptance |
| 4. Responsive UI | 90% | Responsive navigation, dashboards, tables, forms, document viewers, desktop/mobile workflow checks | Exhaustive tablet/device accessibility and touch acceptance across every mapped route |
| 5. Demo Environment | 5% | Data boundaries and governance documentation | Separate fictional dataset, redacted/sample files, watermarking, automated PII scan and public-demo approval |
| 6. Data Migration | 45% | One customer snapshot with 3,597 immutable records, preserved files/relationships and isolated tenant targets | Repeatable per-client extract-transform-import pipeline, reconciliation reports, additional authorised clients such as Grandbrind |
| 7. Business Outcomes | 55% | Reduced repeated entry, central operations, expiry visibility, consented cross-company worker import, QR identity and third-party REST access | Production network adoption, complete internationalisation, provider-backed mobile authentication and customer onboarding operations |

## Release-candidate work completed

- Immutable imported snapshot and isolated local writable records.
- Fresh-volume snapshot import is append-once; startup never replaces or deletes protected rows.
- Company tenant, tenant-scoped users/settings/records/audits and protected archive boundary.
- Worker self-registration, verification, password recovery, lockout and secure sessions.
- Editable worker passports, unique QR profiles and initial English/Portuguese/Spanish preference wiring.
- Worker-owned versioned documents with drag/drop multi-upload, progress, preview, delete and expiry colours.
- Field-level company consent, secure links, immediate revocation and tenant workforce import/refresh.
- Per-company document view/approval/decline history.
- Revocable integration tokens and audited REST resources for profiles, certifications, documents, inductions and training.
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

### Milestone B — Universal worker foundation (implemented locally)

1. Complete provider/legal choice for SMS OTP; email verification is implemented.
2. Add camera-based QR scan and company access-request/worker-approval handshake.
3. Translate the full company application; the worker surface has the initial language preference/dictionary architecture.
4. Publish an OpenAPI contract, pagination/rate limits and client SDK after the integration contract is approved.
5. Run tenant penetration/privacy testing before any multi-company production launch.

This milestone must precede cross-company import, messaging and network adoption work.

### Milestone C — Supervisor workflow and communications — implemented locally

1. Implemented: department contacts and automatic request routing.
2. Implemented: worker/company conversations linked to requests; broader document/form/asset linking remains an enhancement.
3. Implemented: unread/read notifications and supervisor review states.
4. Implemented: induction approval, decline, comments, additional-information request and immutable history.
5. Implemented locally: notification preferences and in-app delivery. Approved SMS/push provider integrations remain external dependencies.

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
