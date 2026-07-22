# Marcelo Requirements Gap Analysis

Assessment date: 22 July 2026

## Executive status

- Current single-company customer pilot: approximately **95% complete** and deployed for acceptance testing.
- Full multi-company platform described in Marcelo's notes: approximately **80% complete**.
- The private pilot is live. Commercial release remains conditional on customer sign-off, approved notification providers, privacy/legal review and operational ownership.

The current product is a secured operations clone using one authorised customer snapshot plus isolated local workflows. Marcelo's document expands this into a multi-tenant worker identity and compliance network. Those are different delivery milestones.

## Module status

| Module | Estimate | Implemented | Principal gaps |
|---|---:|---|---|
| 1. Universal Worker Profile | 94% | Free self-registration, email verification/recovery, account TOTP MFA and single-use backup codes, editable complete profile, worker QR/public profile, camera/manual QR access request, worker field-level approval/decline, consent/revocation, tenant relationships/import, revocable audited REST API, OpenAPI 3.1 contract, API pagination/per-token throttling, expanded English/Portuguese/Spanish catalogue | Approved SMS/mobile OTP provider, client SDK, full native-speaker translation review |
| 2. Document Management | 84% | Imported libraries, PDF/image viewing/download, worker-owned categories, drag/drop multi-upload/progress, validation, preview/delete, automatic versions, auditable best-effort expiry extraction, expiry colours/reminders, tenant document review | OCR/provider extraction for scanned images, company plant/equipment/site ownership refinements, visual version-history grouping |
| 3. Compliance & Workflow | 82% | Forms/drafts/signatures/evidence/reports, certificate verification/revocation, expiry centre, email queue/retries, audit/roles, per-company worker-document reviews, routed requests, internal worker/company conversations, induction decisions/comments/history, in-app notifications and channel/language preferences | Approved SMS/push providers, provider delivery receipts/escalations, richer supervisor queues and formal customer acceptance |
| 4. Responsive UI | 95% | Responsive navigation, dashboards, tables, forms, document viewers, QR camera/manual fallback, desktop/mobile workflow checks, persistent English/Portuguese/Spanish localisation for the shell, worker portal and primary workflows | Native-speaker review and the remaining rare/error-state strings; exhaustive tablet/device accessibility and touch acceptance |
| 5. Demo Environment | 5% | Data boundaries and governance documentation | Separate fictional dataset, redacted/sample files, watermarking, automated PII scan and public-demo approval |
| 6. Data Migration | 82% | One immutable customer snapshot plus a repeatable checksum-inventoried package builder, dry-run reconciliation, transactional isolated-tenant import, relationship remapping, attachment registration, provenance, replay prevention and run history | Map and rehearse each additional authorised client's source schema; obtain written approval and customer-level acceptance reports |
| 7. Business Outcomes | 55% | Reduced repeated entry, central operations, expiry visibility, consented cross-company worker import, QR identity and third-party REST access | Production network adoption, complete internationalisation, provider-backed mobile authentication and customer onboarding operations |

## Release-candidate work completed

- Immutable imported snapshot and isolated local writable records.
- Fresh-volume snapshot import is append-once; startup never replaces or deletes protected rows.
- Company tenant, tenant-scoped users/settings/records/audits and protected archive boundary.
- Worker self-registration, verification, password recovery, lockout and secure sessions.
- Editable worker passports, unique QR profiles and initial English/Portuguese/Spanish preference wiring.
- Worker-owned versioned documents with drag/drop multi-upload, progress, preview, delete and expiry colours.
- Field-level company consent, secure links, immediate revocation and tenant workforce import/refresh.
- Camera/manual QR access request with pending state, worker-selected field approval, decline and tenant audit/notification history.
- Per-company document view/approval/decline history.
- Revocable integration tokens and audited REST resources for profiles, certifications, documents, inductions and training.
- Published OpenAPI 3.1 contract for consent-handshake and bearer integration routes.
- Administrator/editor/viewer authentication, CSRF, session revocation and audit history.
- Failed-login lockout, one-time password reset and recovery-request throttling.
- Real-definition form assignment, draft/resume, signatures, evidence, validation and multipage PDF reports.
- Numbered branded certificate PDFs, QR verification, replacement and revocation.
- Expiry centre for Safe Pass, GA1, risk assessment and local certificate dates.
- Deduplicated email queue, opt-in SMTP delivery, delivery history, retry controls and opt-in scheduler.
- System/privacy screen with database integrity, storage, readiness, branding, contacts and local-only retention.
- Consistent SQLite backup, file hashes, verification and empty-directory restore rehearsal.
- Desktop and 390 px browser acceptance with no console warnings or errors.
- TOTP multi-factor authentication with one-time backup codes and audit events.
- Paginated, per-token rate-limited integration API.
- Best-effort document expiry extraction with source/confidence metadata.
- Unattended readiness monitoring and checksum-verified daily writable-data backups.
- Persistent tenant company profile and contact settings.

## Recommended delivery sequence

### Milestone A — Customer acceptance of the deployed single-company release

1. Completed: clean-container validation, production deployment and live HTTPS smoke testing.
2. Complete the pilot acceptance checklist with the company user.
3. Approve the privacy contact, retention period and future SMTP provider/recipients.
4. Fix any customer-reported pilot defects and obtain named release approval.
5. Enrol administrator MFA and record the customer acceptance decision.

### Milestone B — Universal worker foundation (implemented locally)

1. Complete provider/legal choice for SMS OTP; email verification is implemented.
2. Implemented locally: camera/manual QR scan and company access-request/worker-approval handshake.
3. In progress: expanded company and worker translation catalogue; native-speaker review and rare/error states remain.
4. OpenAPI contract, pagination and rate limits are implemented; a client SDK remains after integration approval.
5. Run tenant penetration/privacy testing before any multi-company production launch.

This milestone must precede cross-company import, messaging and network adoption work.

### Milestone C — Supervisor workflow and communications — implemented locally

1. Implemented: department contacts and automatic request routing.
2. Implemented: worker/company conversations linked to requests; broader document/form/asset linking remains an enhancement.
3. Implemented: unread/read notifications and supervisor review states.
4. Implemented: induction approval, decline, comments, additional-information request and immutable history.
5. Implemented locally: notification preferences and in-app delivery. Approved SMS/push provider integrations remain external dependencies.

### Milestone D — International product and migration

1. In progress: persistent English, Portuguese and Spanish translation layer covers the shell and primary operational workflows; long-tail catalogue/native review remains.
2. Implemented locally: repeatable tenant migration packages with checksums, dry run, source/target counts, relationship and attachment reconciliation, replay protection and audit history.
3. Migrate additional clients only with per-client written authorisation.
4. Build a completely separate fictional demo tenant and automated PII/document watermark checks.

## Important product decision

The earlier instruction to use the available real customer data instead of demo documents is suitable only for the private authorised pilot. It does not satisfy Marcelo's public demo requirement. A sales/public demo must use a separate fictional tenant with no real personal or company information.

## Rough effort range

- Current single-company pilot to customer-approved release: normally a few focused acceptance and defect-resolution days, depending on tester availability and findings.
- Remaining provider-backed notifications, OCR/document refinements and long-tail product quality: several focused engineering weeks after provider and privacy decisions.
- Hardened multi-company commercial operation remains a multi-month programme because penetration testing, legal/privacy approval, additional customer migrations, onboarding and support cannot be completed by code alone.

These ranges are planning estimates, not commitments; provider choices, legal/privacy decisions, migration quality and customer feedback can materially change them.
