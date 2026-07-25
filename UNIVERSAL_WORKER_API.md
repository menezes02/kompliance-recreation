# Universal Worker API

The version 1 REST API exposes only worker data that has an active consent grant
for the calling company. Revocation takes effect immediately. Every successful
API read updates the token's last-used timestamp and creates a tenant audit event.

## Authentication

A company administrator creates a token in **Shared worker passports → Company
API tokens**. The raw token is displayed once and must be held outside the
repository and passed as a bearer token:

```http
Authorization: Bearer kmp_example-secret
```

Tokens are tenant-scoped, read-only and individually revocable. A revoked or
unknown token returns `401`. A resource that the worker has not shared returns
`403`; a worker outside the tenant's active consent set returns `404`.

## Endpoints

The machine-readable OpenAPI 3.1 contract is available from
`GET /api/openapi.json` and is also stored at `local-app/static/openapi.json`.

| Method | Endpoint | Result |
|---|---|---|
| GET | `/api/v1/shared-workers` | All active consented profiles for the token's company |
| GET | `/api/v1/workers/{worker_id}` | One consent-filtered worker profile |
| GET | `/api/v1/workers/{worker_id}/certifications` | Shared certification records |
| GET | `/api/v1/workers/{worker_id}/training-records` | Shared training records |
| GET | `/api/v1/workers/{worker_id}/inductions` | Shared induction records |
| GET | `/api/v1/workers/{worker_id}/documents` | Shared document metadata and company review status |
| GET | `/api/v1/workers/{worker_id}/documents/{document_id}/file` | Shared file, inline with its original filename |

The API never returns passwords, verification/reset tokens, worker sessions,
private medical information, another tenant's review history, storage paths or
unshared fields.

## Consent lifecycle

1. The worker creates and verifies a worker account.
2. A company scans/pastes the public worker QR and requests specific fields, or
   the worker initiates a grant from the worker portal.
3. For company-initiated requests, no private access exists until the worker
   approves a subset of the requested fields. A decline shares nothing.
4. The company sees the approved worker in **Shared worker passports** and may import a
   local tenant worker record.
5. The worker may change the allowed fields or revoke the grant at any time.
6. Revocation removes the worker from company screens, secure links and API
   responses without deleting the worker-owned source profile.

Company import creates or refreshes a local-only `workers` record identified by
`universal_worker_id`. It never updates imported protected customer records.

## Local integration check

```powershell
$headers = @{ Authorization = "Bearer $env:KOMPLIANCE_API_TOKEN" }
Invoke-RestMethod "http://127.0.0.1:8090/api/v1/shared-workers" -Headers $headers
```

Run the isolated end-to-end suite with:

```powershell
python -m unittest local-app/test_universal_workers.py -v
```
