# Kompliance Pilot Acceptance Checklist

Use this checklist with the company pilot user before approving production release. Record evidence, defects and the name/date of the person accepting each area.

## Pilot record

- Pilot company:
- Pilot site(s):
- Business owner:
- Pilot user(s):
- Build commit:
- Test start/end dates:
- Acceptance decision: Pending / Accepted / Rejected

## Access and security

- [ ] Initial administrator setup is completed once.
- [ ] Viewer can inspect records but cannot create or change local data.
- [ ] Editor can create local assignments, drafts, submissions, evidence and certificates.
- [ ] Administrator can change roles, suspend accounts and revoke sessions.
- [ ] Five failed logins lock the account temporarily.
- [ ] Forgotten-password requests do not reveal whether an email exists.
- [ ] Administrator-generated reset links expire and can be used only once.
- [ ] Password reset signs out existing sessions.
- [ ] Audit log records all tested security and local-data mutations.

## Imported information

- [ ] Dashboard totals match the authorised snapshot.
- [ ] GA1, GA2 and GA3 lists, filters and date ranges behave correctly.
- [ ] Archived PDFs/images open, download and preserve list state.
- [ ] Workers, sites, roles and subcontractors can be searched.
- [ ] Induction definitions, assets/QR images, training questions and custom forms display correctly.
- [ ] No imported record offers an edit or delete action.
- [ ] Direct API attempts to update/delete an imported record are rejected.

## Form assignment and submission

- [ ] A local assignment can be created for a real imported form definition.
- [ ] Text, date, time, date-time, location, yes/no/N/A and signature controls render correctly.
- [ ] Incomplete work can be saved and resumed as a draft.
- [ ] Final submission is blocked when any required field is blank.
- [ ] Supporting PDF, office, CSV and image evidence can be attached.
- [ ] Evidence is linked only to its local assignment.
- [ ] Final submission changes the assignment status to Submitted.
- [ ] Generated submission PDF contains all answers and the attachment list.

## Certificates

- [ ] Certificate shows company, worker, induction, site, completion and expiry dates.
- [ ] Certificate number is unique.
- [ ] QR code opens the public verification page.
- [ ] Verification page shows Active for a valid certificate.
- [ ] Replacement marks the prior certificate Replaced.
- [ ] Revocation requires a reason and changes public status to Revoked.
- [ ] Expired certificates display Expired even if the original PDF still exists.

## Expiry and reminders

- [ ] Expiry centre shows overdue, due-soon, current and missing-date counts.
- [ ] Reminder window works for 7, 14, 30, 60 and 90 days.
- [ ] Safe Pass, GA1, risk assessment and local certificate dates are included.
- [ ] Preparing reminders creates local notification records.
- [ ] Interface clearly states that no external message was sent.
- [ ] Business owner confirms future email recipients, sender and reminder intervals.

## Responsive and operational checks

- [ ] Primary workflows are usable on desktop, tablet and mobile.
- [ ] Signature pad works with mouse and touch input.
- [ ] Browser console has no errors during the pilot path.
- [ ] Docker container names do not collide with other applications.
- [ ] Backup and rollback references are recorded in `RELEASE_CHECKLIST.md`.
- [ ] Restore procedure is tested before production approval.

## Defects and decisions

| ID | Area | Observation | Severity | Owner | Decision/status |
|---|---|---|---|---|---|
| | | | | | |

## Sign-off

- Business owner name/date:
- Technical owner name/date:
- Pilot user name/date:
- Conditions or deferred work:
