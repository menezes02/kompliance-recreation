# Kompliance Recreation

Private, containerized recreation of the Kompliance health and safety application.

The current release candidate adds a tenant-isolated Universal Worker Foundation, company QR access requests with worker-controlled field approval, supervisor workflow/inbox, routed requests, worker conversations, induction approval history, real-definition form completion, verifiable certificates, expiry/reminder operations, account recovery and lockout, system/privacy controls, and verified local-data backups while preserving the imported customer snapshot as immutable.

See [SUPERVISOR_WORKFLOW.md](SUPERVISOR_WORKFLOW.md) for workflow states, routes and the external notification-provider boundary.

The company application now includes persistent English, Portuguese and Spanish localisation for the shell and primary operational workflows. See [TENANT_MIGRATION.md](TENANT_MIGRATION.md) for the checksum-verified, dry-run-first customer migration process.

The repository contains:

- the locally recreated Python web application;
- the current customer-data snapshot used by the clone;
- downloaded source PDFs and example documents;
- the application map and read-only production policy;
- Docker and nginx deployment configuration.

## Data sensitivity

This repository contains customer records and compliance documents. It must remain
private. Production access credentials, SSH credentials, generated HTTP Basic Auth
files, logs, and runtime databases are intentionally excluded from Git.

The original production application is treated as read-only. See
`READ_ONLY_POLICY.md`. Approval responsibilities for exports, downloads, demo
publication, migration, and deployment are defined in `DATA_GOVERNANCE.md`.

Imported snapshot records are immutable in both the local API and interface.
Startup imports the authorised customer snapshot once into a fresh data volume. A changed export is never used to replace or delete protected rows in an existing volume.
Production-reading scripts require the acknowledgement and approval-reference
environment values documented in `.env.example`.

## Run locally

```powershell
python -m pip install -r requirements.txt
python local-app/server.py
```

Then open `http://127.0.0.1:8090/`.

Worker self-registration is available at `http://127.0.0.1:8090/worker/`. The company application exposes QR requests and consented profiles at `/shared-workers`. See `QR_ACCESS_REQUESTS.md` for the approval lifecycle and `UNIVERSAL_WORKER_API.md` for REST integration. The OpenAPI 3.1 contract is served at `/api/openapi.json`.

Operational validation, backup, monitoring, email and release instructions are in `OPERATIONS_RUNBOOK.md`.
The controlled customer test path is documented in `PILOT_TEST_HANDOFF.md`, with formal sign-off in `PILOT_ACCEPTANCE_CHECKLIST.md`.

## Docker deployment

Create `deployment/htpasswd` locally before starting the gateway. The Compose
project uses these fixed resource names:

- `kompliance_app_example`
- `kompliance_gateway_example`
- `kompliance_operations_example`
- `kompliance_data_example`

```powershell
docker compose up -d --build
```

The stack expects an existing external Docker network named `proxy`.

## Snapshot

The production snapshot is stored in `production-data/records.json`. The
application imports that snapshot into its runtime SQLite database on startup and
does not fall back to demo data when the snapshot is present.
