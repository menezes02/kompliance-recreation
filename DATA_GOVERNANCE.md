# Kompliance Data Governance and Authorisation Register

This file defines who must approve operations involving the original Kompliance
service or customer data. It is a control register, not proof that approval has
already been granted.

## Default rule

- The original service is read-only for discovery.
- The local clone may not send create, update, delete, assignment, approval,
  rejection, upload, email, SMS, or notification requests to the original service.
- Existing local snapshot records are immutable. New synthetic/local records may
  be created separately for development.
- No new export, download, demo publication, or migration starts without a named
  approver and a written authorisation reference.
- A worker owns the Universal Worker profile and grants access per company and
  per field. Company access and integration output stop immediately on revocation.
- A company import creates or refreshes only its local tenant record. It does not
  transfer ownership of the worker source profile or alter protected customer data.
- Workflow requests, conversations, induction reviews and in-app notifications
  are partitioned by company and authenticated worker/user identity.
- Request and induction transition history is append-only through the application
  API. Email, SMS and push delivery remains disabled until separately approved.

## Required approvals

| Operation | Required approver | Evidence/reference | Current status |
|---|---|---|---|
| View production pages for discovery | Customer account owner or delegated product owner | Written scope/email/ticket | Confirm before each audit session |
| Export table metadata/records | Relevant customer data owner | Written export approval | Pending for any future refresh |
| Download customer documents | Relevant customer data owner | Written document-download approval | Pending for any future refresh |
| Publish data or files in the demo | Privacy owner plus product owner | PII scan report and manual sign-off | Pending |
| Migrate one customer | That customer's data owner plus project sponsor | Signed migration scope and mapping | Pending |
| Migrate multiple customers | Written approval from every affected data owner | Per-client approval register | Pending |
| Deploy a production application release | Product owner plus technical owner | Release approval and rollback reference | Pending |
| Enable email, SMS, push, or external API traffic | Product owner plus relevant service owner | Provider/configuration approval | Pending |

The migration CLI enforces the per-client authoriser/reference, an exact apply
acknowledgement, checksum inventory and a dry-run reconciliation report. It
refuses to target the protected source-snapshot tenant. The existence of the
tool does not itself authorise any customer export or migration.

## Technical enforcement

Production-reading scripts require all of the following process environment
values before they will connect:

```text
KOMPLIANCE_READ_ONLY_ACK=I_UNDERSTAND_READ_ONLY
KOMPLIANCE_EXPORT_AUTHORIZED=YES       # export only
KOMPLIANCE_DOWNLOAD_AUTHORIZED=YES     # download only
KOMPLIANCE_AUTHORIZED_BY=<name or role>
KOMPLIANCE_AUTHORIZATION_REFERENCE=<ticket/email/contract reference>
```

Credentials remain process-only and must never be placed in this register,
`.env.example`, Git, logs, screenshots, or documentation.

Company API secrets are displayed once, stored only as SHA-256 digests, scoped to
one tenant and individually revocable. API responses are derived from the active
worker consent grant; every successful read is added to that tenant's audit log.

## Authorisation log template

| Date | Operation | Customer/data owner | Approved by | Reference | Operator | Outcome |
|---|---|---|---|---|---|---|
| DD/MM/YYYY |  |  |  |  |  |  |
