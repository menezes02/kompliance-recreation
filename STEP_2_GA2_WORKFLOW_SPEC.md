# Step 2 - GA2 Workflow Specification

Status: Draft for Marcelo review
Scope: GA2 list, filters, PDF access and audit expectations
Safety boundary: Local clone only. Imported snapshot records remain read-only.

## 1. Outcome

An authorised company user can find a submitted GA2 record quickly, confirm its
site, worker and submission date, and view or download the archived PDF. The
workflow must work on desktop and mobile, must not expose another customer's
records, and must create the required audit evidence.

This is the first vertical workflow. GA1 and GA3 should reuse the same approved
interaction, permission, audit and document-delivery patterns after GA2 is
accepted.

## 2. Current local evidence

The local snapshot currently contains:

- 475 GA2 records;
- 7 sites and 12 distinct worker names;
- submitted dates from 07/05/2025 through 13/07/2026;
- one archived PDF for every GA2 record;
- no missing referenced GA2 PDF files; and
- 475 records marked as protected production-snapshot records.

The current interface was verified locally without creating, editing or
deleting data. It supports:

- global search;
- site and worker filters that combine correctly;
- one submitted-date calendar where one selected date means one day and a
  second selected date creates an inclusive range;
- newest-first and oldest-first creation order;
- page sizes of 10, 25, 50 and 100;
- pagination;
- a modal PDF preview;
- explicit Open in new tab and Download PDF fallbacks;
- a horizontally scrollable mobile table; and
- a mobile PDF preview with all actions visible.

Imported rows show `Read only` and expose no edit or delete controls.

## 3. Actors and provisional permissions

The final permission matrix requires Marcelo's confirmation.

| Actor | List GA2 | View PDF | Download PDF | Create | Correct | Delete |
|---|---:|---:|---:|---:|---:|---:|
| Platform administrator | Provisional yes | Provisional yes | Provisional yes | To confirm | To confirm | No hard delete by default |
| Company administrator | Provisional yes, own tenant | Provisional yes | To confirm | To confirm | To confirm | No hard delete by default |
| HSEQ / safety manager | Provisional yes, assigned sites | Provisional yes | To confirm | To confirm | To confirm | No |
| Site manager / supervisor | Provisional yes, assigned sites | Provisional yes | To confirm | To confirm | To confirm | No |
| Read-only auditor | To confirm | To confirm | To confirm | No | No | No |
| Worker | Own records only, if required | To confirm | To confirm | No | No | No |

Every query and document request must apply the tenant and site permission on
the server. Hiding a row or button in the browser is not an access control.

## 4. GA2 list data contract

Required record fields:

| Field | Purpose | Rule |
|---|---|---|
| `id` | Stable internal identifier | Never derived from the row number |
| `tenant_id` | Customer boundary | Mandatory in production |
| `site_id`, `site_name` | Site filter and display | Site ID is authoritative |
| `worker_id`, `worker_name` | Worker filter and display | Worker ID is authoritative |
| `worker_email` | Secondary identification | Display only when role permits |
| `subcontractor_id`, `subcontractor_name` | Employer context | Optional only when genuinely absent |
| `submitted_at` | Submission date/time | Store in UTC; display in Europe/Dublin |
| `created_at` | Creation order | Server-generated and immutable |
| `document_id` | Archived PDF relationship | Mandatory for submitted records |
| `document_name` | User-facing filename | Sanitised for display/download |
| `status` | Lifecycle state | Values require Marcelo's confirmation |
| `source` | Migration/provenance marker | Never editable by normal users |

Row numbers are presentation values calculated after filtering and paging.
They are not record identifiers.

## 5. Primary workflow

1. User signs in.
2. Server resolves the user's tenant, role and permitted sites.
3. User opens `GA2 Forms`.
4. The list enters `loading` and requests the first authorised page.
5. The server returns records, total count and allowed filter values.
6. User may combine global search, site, worker, submitted date and creation
   order.
7. Every filter change resets the list to page 1.
8. A single calendar date filters that day only.
9. Selecting a second date creates an inclusive range, regardless of which end
   was selected first.
10. User selects Preview on a record.
11. The server rechecks permission for that record and document.
12. The modal displays the PDF or provides Open in new tab and Download PDF.
13. The system writes the approved audit events.

## 6. List states

| State | Required behaviour |
|---|---|
| Initial loading | Show a clear loading state and prevent duplicate requests |
| Ready | Show authorised rows, active filters, total and current page |
| Empty tenant | Explain that no GA2 records exist; do not show an error |
| No filter matches | Show `No records found` and retain filters for correction |
| Request failed | Show a retry action and a non-technical error message |
| Access denied | Return HTTP 403 and show no record metadata |
| Session expired | Return to sign-in without losing sensitive data in the URL |
| PDF loading | Show filename and progress/loading feedback |
| PDF unsupported | Offer Open in new tab and Download PDF |
| PDF missing | Show a controlled unavailable message and log the failure |

## 7. Filter and paging rules

- Site and worker filters use stable IDs, not display text.
- Available workers should optionally narrow to the selected site. Marcelo must
  confirm whether this is desired.
- Date filtering is inclusive at both ends and uses the submitted timestamp.
- The interface displays dates in Irish format.
- Creation order uses `created_at`, not row ID or displayed submission date.
- The server performs filtering, sorting and pagination before returning data.
- Supported page sizes are 10, 25, 50 and 100 unless Marcelo changes them.
- Global search must have a documented field list; it must not search hidden
  private data merely because it appears in stored JSON.
- Clear filters resets site, worker, date range and order, and returns to page 1.
- The URL should carry non-sensitive filter state if shareable filtered views are
  approved.

Proposed list request:

```text
GET /api/v1/ga2?q=&site_id=&worker_id=&submitted_from=&submitted_to=&sort=created_desc&page=1&page_size=25
```

The response should contain `items`, `page`, `page_size`, `total` and the
authorised filter options or references needed to load them.

## 8. PDF delivery rules

- A list result must never contain a direct storage path or public object URL.
- Preview and download use an authorised document endpoint with a short-lived
  server decision or signed URL.
- The endpoint validates tenant, role, site and record relationship again.
- Inline preview sends `Content-Type: application/pdf` and an inline
  `Content-Disposition` filename.
- Explicit download sends an attachment `Content-Disposition` filename.
- Byte-range requests should be supported for efficient browser PDF viewing.
- Missing, quarantined or corrupted files return a controlled error.
- Filenames are sanitised and response headers prevent MIME sniffing.
- Download permission is separate from preview permission if Marcelo requires
  that distinction.

Proposed endpoints:

```text
GET /api/v1/ga2/{ga2_id}
GET /api/v1/ga2/{ga2_id}/document?disposition=inline
GET /api/v1/ga2/{ga2_id}/document?disposition=attachment
```

## 9. Required audit evidence

The current clone writes HTTP logs but does not yet implement business audit
events. Production must use immutable, structured events.

| Event | When | Minimum fields |
|---|---|---|
| `ga2.list_viewed` | GA2 screen successfully loads | actor, tenant, permitted scope, time, request ID |
| `ga2.filters_changed` | Filters are applied | actor, tenant, filter names/values, result count, time |
| `ga2.record_viewed` | A record detail/preview is opened | actor, tenant, GA2 ID, site ID, time |
| `ga2.pdf_previewed` | Inline PDF request is authorised | actor, tenant, GA2 ID, document ID, time, outcome |
| `ga2.pdf_downloaded` | Attachment request is authorised | actor, tenant, GA2 ID, document ID, time, outcome |
| `ga2.access_denied` | Record or document request is rejected | actor, tenant, target ID, reason code, time |
| `ga2.document_failed` | File is missing/corrupt/unavailable | actor, target ID, technical correlation ID, time |

Audit records must not store document content, passwords, session tokens or
unnecessary personal data. Marcelo must confirm whether search/filter events are
required individually or may be aggregated.

## 10. Acceptance scenarios

All automated and customer acceptance tests use synthetic records.

### GA2-01 - Authorised first page

Given an HSEQ user assigned to Tenant A and Site Alpha, when the user opens GA2,
then only authorised Tenant A records are returned, the total is correct and no
Tenant B values appear in the response or filter options.

### GA2-02 - Combined site and worker filter

Given records at two sites for two workers, when Site Alpha and Worker W-001 are
selected, then every result matches both filters and the page resets to 1.

### GA2-03 - Single submitted date

When the user selects 13 July 2026 once, then only records submitted on that
calendar day are shown and the trigger displays one date.

### GA2-04 - Inclusive date range

When the user selects 13 July and then 7 July, then the interface normalises the
range to 7-13 July and includes records on both boundary dates.

### GA2-05 - Creation order

When `Oldest first` is selected, then results are ordered by immutable
`created_at` ascending with a deterministic ID tie-breaker. `Newest first`
reverses that order.

### GA2-06 - Search and pagination

Given more records than the selected page size, when the user searches an
approved searchable field and opens page 2, then the total, row numbers and
records are correct and filters remain active.

### GA2-07 - PDF preview and fallback

When an authorised user selects Preview, then the expected PDF opens in the
modal and Open in new tab and Download PDF reference the same authorised
document. The layout works at a 390-pixel mobile viewport.

### GA2-08 - Denied document access

Given a user without access to the record's tenant or site, when the user calls
the record or document URL directly, then the server returns 403, reveals no
metadata and records `ga2.access_denied`.

### GA2-09 - Missing document

Given a synthetic record whose test document is unavailable, when Preview is
selected, then the user sees a controlled unavailable message, can return to the
list and the failure receives a correlation ID.

### GA2-10 - Immutable migrated record

Given a migrated snapshot record, when any client attempts update or delete,
then the API returns 403 and the stored record remains unchanged.

## 11. Current gaps before production acceptance

1. Authentication and tenant/site authorisation are not implemented in the
   current local server.
2. Filtering, sorting and pagination are currently browser-side after fetching
   as many as 5,000 records.
3. The global search currently matches serialised record JSON rather than an
   approved searchable-field list.
4. Business audit events are not implemented.
5. The document server does not currently send `Content-Disposition`,
   `Accept-Ranges` or security headers required for a hardened viewer/download.
6. There is no formal GA2 status lifecycle or record-detail page.
7. The `Add Local Example` action is useful for synthetic development but must
   be permission-controlled and relabelled or removed from production.
8. Empty, access-denied, missing-file and server-error states need dedicated
   automated tests.
9. The final retention, correction, archival and deletion rules are unresolved.
10. Filter persistence/shareability and export requirements are unresolved.

## 12. Decisions Marcelo must provide

1. Which roles may list GA2 records?
2. Is access limited by company, project, site, subcontractor or a combination?
3. May workers view their own GA2 records?
4. Which roles may preview PDFs, and which may download them?
5. Is GA2 download always permitted when preview is permitted?
6. Are submitted GA2 records permanently immutable, or can an authorised user
   issue a corrected revision?
7. What statuses exist for GA2 records?
8. Is `created_at` the intended creation-order field?
9. Should selecting a site narrow the worker list?
10. Which fields participate in global search?
11. Should filters remain after leaving the page, and may filtered URLs be
    shared?
12. Are bulk download, CSV/Excel export or print actions required?
13. Which view, filter and download actions must be audited?
14. How long must GA2 records, PDFs and audit events be retained?
15. What should happen when a PDF is replaced, corrected or found invalid?
16. Must PDFs carry a legal version, signature state or verification code?

## 13. Build sequence after approval

1. Confirm the permission, lifecycle, retention and audit decisions above.
2. Define the tenant-aware GA2 database schema and indexes.
3. Implement authenticated, server-filtered list and filter-option endpoints.
4. Implement authorised inline and attachment document delivery with byte-range
   support.
5. Implement immutable audit events and correlation IDs.
6. Connect the existing responsive interface to the new endpoints.
7. Add automated unit, API, permission and browser acceptance tests using
   synthetic data.
8. Run Marcelo's workflow review and record acceptance or defects.
9. Reuse the accepted pattern for GA1 and GA3.

## 14. Definition of done

- Marcelo has answered the 16 workflow decisions.
- The permission matrix and lifecycle are approved.
- All ten synthetic acceptance scenarios pass.
- Direct API calls cannot bypass tenant or site restrictions.
- Desktop and mobile layouts pass empty, loading, error and large-data tests.
- PDF preview, new-tab fallback and download work on supported browsers.
- Required audit events can be demonstrated and exported for review.
- Backup, restore, deployment and rollback procedures are tested.
- No real customer data is used in demo or automated test environments.
- Marcelo records acceptance of the deployed workflow.
