# QR Worker Access Requests

This milestone implements a worker-controlled company access handshake without
changing the imported customer snapshot.

## Consent flow

1. A signed-in company editor or administrator opens **Shared worker passports**.
2. The company scans a worker's public Kompliance QR code or pastes the public
   profile link/token.
3. The company chooses the fields it wants and sends an optional explanation.
4. The request remains `pending`; no private field, document, secure share link
   or REST API access is created at this stage.
5. The worker reviews the request in **Inbox & requests**, may uncheck fields,
   and chooses **Approve selected** or **Decline**.
6. Approval creates or refreshes a tenant-specific active consent grant using
   only the approved subset. Decline creates no grant.
7. The worker can still revoke an active grant at any time. Revocation
   immediately blocks company screens, secure links and bearer API reads.

## Camera and fallback

Camera access is requested only after the user presses **Scan QR with camera**.
It is limited to the current origin by the `Permissions-Policy` response header.
Browsers without `BarcodeDetector` or camera support retain the manual paste
field, so scanning is never required.

## Tenant and audit boundary

- Company request lists are filtered by the authenticated `company_id`.
- Worker request lists are filtered by the authenticated worker ID.
- A company sees only the worker fields already marked public while a request is
  pending.
- Duplicate pending requests and requests against existing active consent return
  `409 Conflict`.
- Company request creation and worker decisions produce tenant audit events.
- Both sides receive in-app notifications.

## API routes

| Method | Route | Authentication |
|---|---|---|
| `GET` | `/api/company/worker-access-requests` | Company session |
| `POST` | `/api/company/worker-access-requests` | Editor/admin session + CSRF |
| `GET` | `/api/worker/access-requests` | Worker session |
| `POST` | `/api/worker/access-requests/:id/respond` | Worker session + CSRF |
| `GET` | `/api/openapi.json` | Public integration contract |

The machine-readable OpenAPI 3.1 contract also documents the read-only bearer
integration endpoints and their active-consent boundary.
