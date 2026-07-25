# Supervisor workflow and communications

## Delivered scope

The local application now provides one tenant-scoped workflow centre for company users and one worker inbox. It supports:

- department contacts for Safety, HR, Plant, Training and Administration;
- worker-originated and company-originated requests with type, priority, due date, automatic department routing and immutable status events;
- company/worker conversation threads linked to requests;
- induction submissions, approve/decline/request-information decisions, comments, reviewer identity and immutable decision history;
- in-app notifications with unread state;
- per-user and per-worker preferences for in-app, email, SMS, push and preferred language;
- strict company filters on every company read/write and worker-identity filters on every worker read/write.

Company users open **Workforce → Workflow & inbox**. Workers open **Inbox & requests** in the worker portal.

## Status models

- Requests: `open`, `in_progress`, `awaiting_information`, `resolved`, `closed`.
- Induction reviews: `pending`, `approved`, `declined`, `information_requested`.

All request transitions are appended to `workflow_request_events`. All induction transitions are appended to `induction_review_events`; the current state is also retained on the parent record for fast filtering.

## Delivery boundary

In-app notifications are active. Email is reported as available only when SMTP, HTTPS base URL and explicit delivery enablement are configured. SMS and push are intentionally unavailable until approved providers, contracts, privacy terms and credentials are supplied. Selecting an unavailable preference never attempts an external send.

## API surface

Company:

- `GET|POST /api/company/requests`
- `POST /api/company/requests/{id}/status`
- `GET /api/company/conversations`
- `POST /api/company/conversations/{id}/messages`
- `GET|POST /api/company/induction-reviews`
- `POST /api/company/induction-reviews/{id}/status`
- `GET|POST /api/company/notifications` (read uses `/{id}/read`)
- `GET|PUT /api/company/preferences`
- `GET|POST /api/company/departments`, `PUT /api/company/departments/{id}` (administrator)

Worker:

- `GET|POST /api/worker/requests`
- `GET /api/worker/conversations`, `POST /api/worker/conversations/{id}/messages`
- `GET /api/worker/induction-reviews`
- `GET /api/worker/notifications`, `POST /api/worker/notifications/{id}/read`
- `GET|PUT /api/worker/preferences`
