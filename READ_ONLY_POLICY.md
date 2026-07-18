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

