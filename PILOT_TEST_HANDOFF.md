# Kompliance pilot test handoff

## Test release

- Environment: `https://kompliance.felipeitprojects.com/`
- Application release: `fc5ac80c778032e7d4b56c53cf0a7b6d0c4808b0`
- Pilot company: Kingscroft Developments
- Status: ready for controlled customer acceptance
- Expected session: 45–60 minutes for the primary path

Gateway and application credentials are supplied separately. Do not place passwords, authentication codes or backup codes in this document or in Git.

Prepared company test accounts:

- `pilot.viewer@kompliance.test` — read-only Viewer
- `pilot.editor@kompliance.test` — local-workflow Editor

Their passwords are supplied separately to the pilot owner.

## Safety boundary

The 3,597 imported customer records and the 3,077-file source archive are protected and read-only. Pilot actions may create separate local records but cannot edit or delete the imported snapshot. Do not upload any document unless its use in this private pilot is authorised.

## Primary company test

1. Sign in and confirm that the dashboard identifies Kingscroft Developments.
2. Open GA1, GA2 and GA3.
3. Search by site and worker, change creation order and select one submitted date.
4. Select two dates in the same calendar and confirm the date range is applied.
5. Open a PDF in the browser viewer, download it and return to the same filtered list.
6. Inspect Workers, Inductions, Training, Assets, Documents and Source archive.
7. Confirm that imported records have no edit or delete controls.
8. Open Expiry centre and inspect overdue, due-soon, current and missing-date groups.
9. Open System & privacy and confirm database status `ok` and automated operations `Healthy`.

## Local workflow test

1. Open Local workflows.
2. Create a local assignment against an existing form definition.
3. Save an incomplete form as a draft, leave the page and resume it.
4. Complete required controls and add a signature.
5. Submit the form and open the generated PDF report.
6. Generate a certificate, open its public QR verification page, then test replacement or revocation only if the pilot owner approves that local action.
7. Confirm the Audit log records each mutation.

All records created by this sequence are local pilot records; they do not change the imported customer snapshot.

## Worker and consent test

1. Open `https://kompliance.felipeitprojects.com/worker/`.
2. Register a new pilot worker with a unique email and a password of at least 12 characters.
3. While SMTP is deliberately disabled, use the one-time verification link displayed by the private pilot.
4. Complete the worker profile and choose only the fields intended to be public.
5. Open the generated QR/public link in a private browser window and confirm that unselected fields remain hidden.
6. From the company portal, scan or paste the QR link and request access.
7. From the worker portal, approve only selected fields, then confirm the company sees only those fields.
8. Revoke access and confirm that the company view and API access stop immediately.

## Roles and responsive checks

1. An administrator may create temporary Viewer and Editor accounts under Access management.
2. Confirm Viewer is read-only and Editor can manage local workflows but cannot manage users or system settings.
3. Repeat the GA2 viewer, worker QR and form-draft paths on a phone or a browser width near 390 pixels.
4. Report any clipped controls, horizontal scrolling, unclear labels or touch problems.

## Deliberate pilot holds

- External email delivery and the scheduler remain disabled until an SMTP provider and recipients are approved.
- SMS and push delivery remain unavailable until providers and privacy terms are approved.
- Administrator MFA is available but must be enrolled by the account owner using their current password and authenticator app.
- No public demo tenant exists because the current instruction is to use the authorised private customer data and not create demo documents.

These holds do not block the controlled private pilot.

## Feedback to record

For every issue provide:

- page and action;
- expected result;
- actual result;
- desktop or mobile device/browser;
- screenshot with personal data removed where possible;
- severity: blocking, high, normal or cosmetic.

Use `PILOT_ACCEPTANCE_CHECKLIST.md` for the formal decision and sign-off.
