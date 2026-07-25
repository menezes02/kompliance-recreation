# Remote Kompliance Discovery Policy

This policy applies to every audit session against `https://kompliance.lgsafety.ie/`.

## Allowed

- Sign in with credentials supplied for the session.
- Open authenticated and public pages.
- Expand navigation menus.
- Read headings, labels, table schemas, statuses, and visible records.
- Open create, view, and edit screens solely to inspect their structure.
- Read static frontend asset metadata and computed styles.
- Record route patterns, field schemas, validation hints, and UI behavior.
- Take screenshots for local design reference.

## Never perform

- Submit any create, edit, assignment, registration, approval, or contact form.
- Change a field value in an existing record.
- Approve or reject a worker.
- Delete a record or activate a delete confirmation.
- Select records for bulk deletion.
- Upload a document, image, certificate, or other file.
- Download customer documents, certificates, QR codes, or HSA PDFs without separate permission.
- Send an invitation, email, support request, or notification.
- Change a password, profile, company setting, role, permission, or assignment.
- Log out unless explicitly requested, because doing so can interrupt the audit session.
- Enter public induction registration data or continue an induction.
- Trigger a workflow merely to discover its success/error response.

## Safe stopping rule

If learning the next step requires a submit, upload, download, approval, deletion, external message, or persistent field change, stop at the current screen and record the gap in `APP_MAP.md`.

## Enforced production request boundary

Production-reading scripts fail closed unless the request is:

- a same-origin `GET` or `HEAD` request;
- the authentication `POST /login`; or
- the read-only DataTables request `POST /ga1/documents`.

Every other non-GET production request is rejected before it reaches the
network. Cross-origin redirects are also rejected.

Future exports and downloads additionally require an explicit read-only
acknowledgement, a named approver, an authorisation reference, and the relevant
operation flag. See `DATA_GOVERNANCE.md` and `.env.example`.

## Local snapshot protection

Records carrying the source marker `production read-only export` are immutable
inside the recreated application. The API rejects update and delete requests for
those records, and the interface displays a **Read only** badge instead of edit
and delete controls. Synthetic records created locally remain editable.
