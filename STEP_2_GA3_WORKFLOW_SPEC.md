# Step 2 - GA3 Workflow Specification

Status: Draft for Marcelo review
Scope: GA3 list, filters, archived PDF and audit expectations
Safety boundary: Local clone only. Imported snapshot records remain read-only.

## 1. Outcome

An authorised user can find a submitted GA3 record by site, worker, date or
search, confirm its metadata and view or download its archived PDF. GA3 should
reuse the approved GA2 component and security pattern unless Marcelo confirms a
different legal workflow, data model or permission boundary.

## 2. Current local evidence

The local snapshot currently contains:

- 13 protected GA3 records;
- 5 sites and 7 distinct worker names;
- submitted dates from 28/05/2025 through 09/07/2026;
- one archived PDF for every record; and
- no missing referenced GA3 files.

The local UI was verified without mutations. Site and worker filters combine
correctly. Selecting one calendar date returns only that day. The expected PDF
opens in the modal with Open in new tab and Download PDF fallbacks. No edit or
delete control appears for imported records, and no browser warnings were
reported.

GA3 uses the same current list renderer as GA2, so search, inclusive date range,
creation order, page size, pagination and responsive behaviour inherit the GA2
implementation and its current limitations.

## 3. Shared GA2 pattern

The following requirements are inherited from
`STEP_2_GA2_WORKFLOW_SPEC.md`:

- tenant and site permission must be enforced by the server;
- filter values use stable IDs;
- date ranges are inclusive and normalised regardless of selection order;
- creation order uses immutable `created_at` with a deterministic tie-breaker;
- filtering, ordering and pagination occur on the server;
- preview and download re-authorise the record/document relationship;
- the modal provides inline, new-tab and download paths;
- document responses use safe disposition, filename, range and security headers;
- business audit events are immutable and structured; and
- migrated snapshot records remain immutable.

## 4. GA3-specific decisions and data

The current snapshot contains the same displayed fields as GA2:

- company and subcontractor context;
- site;
- worker and worker email;
- submitted date;
- archived PDF; and
- a `details` source payload that the current table does not display.

Marcelo must confirm whether GA3 requires distinct equipment, inspection,
examiner, signature, result, defect, action-required or approval fields. Source
`details` must not become an unstructured production catch-all without an
approved schema.

Recommended record fields:

| Field | Purpose | Rule |
|---|---|---|
| `id`, `tenant_id` | Identity and customer boundary | Mandatory, immutable |
| `site_id` | Site scope | Mandatory |
| `worker_id` | Worker relationship | Requirement to confirm |
| `subcontractor_id` | Employer context | Nullable only with defined meaning |
| `submitted_at` | Submission time | Store UTC; display Europe/Dublin |
| `created_at` | Creation order | Server-managed |
| `status` | GA3 lifecycle | Values require Marcelo's approval |
| `equipment_id` | Equipment relationship | Requirement to confirm |
| `inspection_result` | Outcome | Structured values to confirm |
| `action_required` | Defect/remediation state | Requirement to confirm |
| `document_id` | Archived evidence relationship | Mandatory when submitted |
| `source` | Migration provenance | Protected from ordinary edits |

## 5. Primary workflow

1. User signs in and opens GA3.
2. Server resolves tenant, role and permitted sites.
3. Server returns the first authorised page and authorised filter options.
4. User combines search, site, worker, submitted date and creation order.
5. Filter changes reset the page to 1.
6. User previews a record's PDF.
7. Server rechecks GA3 and document permission.
8. Modal displays the PDF with controlled fallbacks.
9. Approved list, filter, record, preview, download and denial events are
   recorded.

Proposed endpoints:

```text
GET /api/v1/ga3?q=&site_id=&worker_id=&submitted_from=&submitted_to=&status=&sort=created_desc&page=1&page_size=25
GET /api/v1/ga3/{ga3_id}
GET /api/v1/ga3/{ga3_id}/document?disposition=inline
GET /api/v1/ga3/{ga3_id}/document?disposition=attachment
```

## 6. Required audit events

| Event | When |
|---|---|
| `ga3.list_viewed` | Authorised list loads |
| `ga3.filters_changed` | Approved filter audit is required |
| `ga3.record_viewed` | Record/detail opens |
| `ga3.pdf_previewed` | Inline PDF is authorised |
| `ga3.pdf_downloaded` | Attachment is authorised |
| `ga3.access_denied` | Record or document is rejected |
| `ga3.document_failed` | File is missing, corrupt or unavailable |
| `ga3.status_changed` | Approved lifecycle transition occurs |

Events require actor, tenant, target ID, authorised scope, timestamp, outcome and
request/correlation ID as applicable. They must not store the document content,
session token or unnecessary personal data.

## 7. Synthetic acceptance scenarios

### GA3-01 - Tenant and site isolation

An assigned-site user receives only authorised GA3 rows and filter options;
direct Tenant B access returns 403 without metadata leakage.

### GA3-02 - Combined site and worker filter

Selecting Site Alpha and Worker W-001 returns only rows matching both values and
resets the page to 1.

### GA3-03 - Single date and inclusive range

One calendar selection filters one submitted day. A second selection creates a
normalised inclusive range containing both boundary dates.

### GA3-04 - Creation ordering

Oldest/newest ordering uses immutable `created_at` and a deterministic ID
tie-breaker, not row number or formatted submission date.

### GA3-05 - Search and pagination

Search uses only approved fields, combines with active filters and preserves
correct totals and row numbering across pages.

### GA3-06 - PDF preview and fallback

An authorised PDF opens in the responsive modal; new-tab and download actions
reference the same authorised document.

### GA3-07 - Denied download

A role without download permission may perform only the separately approved
preview action; direct attachment mode returns 403 and writes an audit event.

### GA3-08 - Missing document

A missing synthetic PDF produces a controlled unavailable state and correlation
ID without exposing a storage path.

### GA3-09 - Protected migrated record

Update/delete attempts against a migrated GA3 record return 403 and leave the
record unchanged.

## 8. Current gaps before production acceptance

1. Authentication, tenant/site authorisation and business audit events are not
   implemented in the local server.
2. Filtering, sorting and pagination are browser-side after fetching up to 5,000
   records.
3. Global search matches serialised JSON instead of an approved field list.
4. The source `details` field has no approved production schema or detail view.
5. The GA3 lifecycle, inspection result, defect and action-required states are
   unresolved.
6. PDF delivery lacks the final disposition, byte-range and security-header
   behaviour.
7. `Add Local Example` must be relabelled, permission-controlled or excluded
   from production.
8. Empty, denied, missing-file and server-error states require automated tests.
9. Retention, correction, revision and legal-evidence rules are unresolved.

## 9. Decisions Marcelo must provide

1. What exact inspection/business process does GA3 represent in this platform?
2. Which roles may list, preview, download, create, correct, approve or archive
   GA3?
3. Is access restricted by company, site, worker, equipment or a combination?
4. Is a worker relationship mandatory, or is GA3 primarily equipment/site based?
5. Which structured fields from the current `details` payload are required?
6. What lifecycle, inspection-result and action-required states exist?
7. Are submitted GA3 records immutable, or may corrections create revisions?
8. Which signatures, examiner information and legal evidence must be retained?
9. Are GA3 filters identical to GA2, or are equipment, result and status filters
   also required?
10. Which fields participate in global search?
11. May preview and download permissions differ?
12. Which events must be audited and how long are records retained?
13. How should GA3 outcomes contribute to worker, site, equipment and company
    compliance dashboards?

## 10. Build sequence after approval

1. Confirm GA3 meaning, schema, lifecycle and permission differences from GA2.
2. Extend the shared tenant-aware compliance-record API and database model.
3. Reuse the server-filtered list, calendar, paging and secure document service.
4. Add GA3 detail/outcome fields and approved transitions.
5. Emit immutable GA3 audit events.
6. Pass the nine synthetic acceptance scenarios on desktop and mobile.
7. Obtain Marcelo's recorded acceptance.

## 11. Definition of done

- Marcelo has answered the 13 GA3 decisions.
- GA3-specific fields and lifecycle are approved.
- The shared GA2 component is reused without weakening GA3 permissions.
- All nine synthetic scenarios pass.
- Direct API and document requests enforce tenant/site scope.
- Required audit evidence can be demonstrated.
- Migrated data remains immutable and demo/test data is synthetic.
