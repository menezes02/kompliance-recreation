# Kompliance Local Recreation

A dependency-free Python/SQLite recreation of the mapped Kompliance customer
portal. It is intentionally separate from the production service.

## Run

```powershell
python .\server.py
```

Open `http://127.0.0.1:8090/`.

## Docker

From the `kompliance-recreation` directory:

```powershell
docker compose up -d --build
```

The Compose deployment creates:

- Application container: `kompliance_app_example`
- Authenticated gateway container: `kompliance_gateway_example`
- Data volume: `kompliance_data_example`
- Internal application port: `8090`
- Internal gateway port: `80`
- External network: `proxy`

The source archive is mounted at `/app/source-archive` read-only. The
container has a read-only root filesystem and does not publish a host port;
the existing reverse proxy is the only public entry point. The proxy must
forward to `kompliance_gateway_example:80`, not directly to the application
container.

HTTP Basic Authentication is enforced by the gateway. The username is
`kompliance_admin`; only its Apache-compatible password hash is stored in
`deployment/htpasswd`.

Application authentication is also enabled in Docker. On first access through
the gateway, the app requires creation of an initial administrator using a
name, email address and a password of at least 12 characters. Passwords use
PBKDF2-SHA256, sessions are HTTP-only/SameSite, mutations require a CSRF token,
and local create/update/delete actions are written to the audit log. Supported
roles are viewer, editor and administrator; imported snapshot records remain
immutable for every role.

Current server deployment:

`https://kompliance.felipeitprojects.com/`

## Production data snapshot

The deployed database is initialized from:

`../production-data/records.json`

The snapshot contains 3,597 records exported through authenticated, read-only
table requests. It is imported only when a fresh database has no recorded
snapshot version. Startup never replaces or deletes protected rows in an
existing data volume; a different authorised export requires a separately
reviewed migration into a fresh volume.

Snapshot records are immutable in the local API and interface. They display a
`Read only` badge and cannot be updated or deleted. Records created locally for
synthetic development remain editable.

To refresh the snapshot, supply credentials through the current process
environment, complete the approval-reference values in `.env.example`, and run:

```powershell
python .\export_kompliance_data.py
docker compose up -d --build app
docker compose restart gateway
```

Credentials, session cookies, CSRF values, induction access tokens, and
presentation/action HTML are not stored in the snapshot.

## Current capabilities

- High-fidelity navigation shell and dashboard
- Responsive desktop/tablet/mobile layout
- Local SQLite records
- Local create, edit, search, pagination, and delete behavior for synthetic records
- Sites, roles, workers, subcontractors, training questions
- Custom forms and distributions
- Visual section/question form builder with three mapped example templates
- Assets and shared-document metadata
- HSA form repositories populated from 2,719 archived PDFs
- GA1 site, expiry-state, expiry-date/range and expiry-order filters
- GA1 document-set viewer preserving all 180 archived PDF/JPG/JPEG attachments
- In-app PDF and image previews with explicit open/download fallbacks
- Read-only universal worker profile foundation for all 286 imported workers
- Free worker self-registration, email verification/recovery, lockout and secure worker sessions
- Editable worker passport covering contact, emergency, employment, skills, qualifications, certifications, training, inductions and optional medical details
- Unique worker QR profiles, secure company-specific links, field-level consent and immediate revocation
- Isolated company tenants, platform-admin tenant creation and tenant-specific settings/users/records/audits
- Company consent inbox, local workforce import/refresh, shared document view and per-company approval/decline history
- Worker-owned versioned documents with drag/drop multi-file upload, progress, validation, expiry colours, preview and delete
- Revocable company API tokens and audited versioned REST resources for profiles, certifications, training, inductions and documents
- Worker language preference with initial English, Portuguese and Spanish interface vocabulary
- Workforce filters for site, role/trade, account state, Safe Pass state and name order
- Dashboard compliance alerts calculated from GA1 expiry dates and worker Safe Pass indicators
- RAMS/Risk Assessment filters, calculated expiry status, read-only details and explicit missing-attachment handling for all 125 imported records
- Form Distribution operations view with lifecycle filters, read-only assignment details and dashboard indicators for all 59 imported records
- Read-only previews for all 7 induction definitions, including 110 mapped pages, 21 configured questions and explicit missing-media disclosure
- Asset operations register for all 148 imported assets with their preserved source QR images
- Training catalogue for all 28 imported compliance questions with source-indicator filtering and evidence boundaries
- Read-only previews for all 3 imported custom-form definitions, linked to their distribution counts
- Worker profiles connected to exact-match available site induction definitions without inferring completion
- Optional application login with administrator/editor/viewer enforcement, CSRF-protected sessions and a local audit log; enabled by default in Docker
- TOTP multi-factor authentication with one-time backup codes, other-session revocation and administrator-visible enrolment status
- Controlled local workflow workspace with real imported form definitions, draft/resume, final required-field validation, signature pads, evidence attachments and complete submission PDFs
- Tenant-scoped supervisor workflow centre with department routing, worker/company requests and conversations, induction decisions/history, in-app notifications and delivery preferences
- Persistent English, Portuguese and Spanish company-interface localisation with account-backed language preference
- Checksum-verified tenant migration run history; the separate CLI is dry-run-first and refuses the protected snapshot tenant
- paginated and per-token rate-limited consent API reads
- auditable best-effort expiry extraction from uploaded document text and metadata
- an operations sidecar that probes readiness and creates verified, non-destructive daily backups of writable local data
- Branded induction certificates with unique numbers, expiry dates, scannable verification QR codes, public status pages, replacement history and revocation
- Expiry centre covering Safe Pass, GA1, risk-assessment and local-certificate dates, with configurable windows and local notification preparation
- Deduplicated email queue with delivery history, retry state and an opt-in scheduler
- System and privacy centre with branding, privacy contact, retention preview, database integrity, storage and service readiness
- Recovery-request throttling and HTTP security headers
- Verifiable local-data backup and empty-directory restore rehearsal tools
- Administrator access management for roles, suspension, session revocation and secure one-time reset-link preparation
- Password recovery with generic account-safe responses, 30-minute one-time tokens and automatic session revocation
- Five-attempt login lockout with a 15-minute cooling period
- Read-only shared-document hub with metadata filters, provenance, available version history and PDF preview/download
- GA1 and Risk Assessment document-set metadata
- Visual multi-page induction builder with seven mapped structural examples
- Company profile, local password form, and contact form
- Searchable/category-filtered browser for the authorized source archive

All actions performed in this application affect only
`data/kompliance.db`. They do not call the production Kompliance service.
Archive-backed compliance screens do not offer synthetic/demo document creation.

## Source archive

The archive downloader stores authorized production examples in:

`../source-archive/`

The local `/archive` page indexes those files without exposing them outside the
local server.

The completed archive contains 2,895 source files (2,725 PDFs, 158 PNG files,
7 SVG files, and 5 CSS files). The final verification pass completed with zero
missing files, zero empty files, and zero invalid PDF signatures.

## Reset an isolated test volume

Only for a disposable development/test volume, stop the server and remove that
test database before starting again. Never remove or reset the customer pilot
volume. The authorised snapshot will be imported into a genuinely fresh volume.

## Pilot boundaries

- Prepared reminder and password-reset messages are stored locally. External delivery is fail-closed and occurs only when SMTP is configured and `KOMPLIANCE_EMAIL_DELIVERY=1`.
- Scheduled preparation/delivery is disabled until `KOMPLIANCE_SCHEDULER=1` is explicitly set.
- SMTP or transactional-email delivery still requires an approved provider, sender domain and data-processing decision.
- Certificate and verification branding follows the organisation settings and includes a generated vector mark; approved final artwork can replace it later without changing certificate data.
- Production deployment remains gated by `../RELEASE_CHECKLIST.md`.
