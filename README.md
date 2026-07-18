# Kompliance Recreation

Private, containerized recreation of the Kompliance health and safety application.

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
`READ_ONLY_POLICY.md`.

## Run locally

```powershell
python local-app/server.py
```

Then open `http://127.0.0.1:8090/`.

## Docker deployment

Create `deployment/htpasswd` locally before starting the gateway. The Compose
project uses these fixed resource names:

- `kompliance_app_example`
- `kompliance_gateway_example`
- `kompliance_data_example`

```powershell
docker compose up -d --build
```

The stack expects an existing external Docker network named `proxy`.

## Snapshot

The production snapshot is stored in `production-data/records.json`. The
application imports that snapshot into its runtime SQLite database on startup and
does not fall back to demo data when the snapshot is present.

