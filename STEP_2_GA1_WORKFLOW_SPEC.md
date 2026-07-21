# Step 2 - GA1 Document-Set Workflow Specification

Status: Draft for Marcelo review
Scope: GA1 document-set list, expiry, attachment viewing and audit expectations
Safety boundary: Local clone only. Imported snapshot records remain read-only.

## 1. Outcome

An authorised user can find a GA1 document set, understand its company, site and
expiry position, open every attachment in that set, and download permitted
evidence. A multi-file GA1 set must remain one business record with individually
addressable, auditable documents.

GA1 must reuse the tenant, permission, audit and secure document-delivery
controls approved for GA2 while retaining its different document-set structure.

## 2. Current local evidence

The local snapshot currently contains:

- 166 protected GA1 document sets;
- 180 archived documents;
- 154 PDF, 18 JPG and 8 JPEG files;
- at least one file for every set and no missing referenced folders;
- four multi-file sets, with up to eight documents in one set;
- 7 distinct sites; and
- an expiry date on every current set.

Current snapshot expiry labels include `Active`, `Expired` and several dynamic
values such as `11 days remaining`. These labels are evidence from the source,
not an approved future status model.

The current local interface was verified without mutations. It supports global
search, page sizing, pagination and attachment links. Every PDF link can open the
modal viewer. JPG/JPEG files currently open in a new browser tab. The row action
opens only the first preferred attachment, while the Documents cell exposes all
attachments. Imported records show `Read only` and have no edit/delete controls.

## 3. GA1 differs from GA2 and GA3

| Area | GA1 | GA2 / GA3 |
|---|---|---|
| Business record | Document set | Submitted form record |
| Attachments | One to many | One archived PDF in current snapshot |
| File types | PDF, JPG, JPEG | PDF in current snapshot |
| Main date | Expiry date | Submitted date plus creation timestamp |
| Current filters | Global search only | Site, worker, submitted date and order |
| Recommended primary action | Open set detail | Preview submitted PDF |

The production GA1 list should not imply that the first attachment represents
the full set. The row action should be `View set` and open a detail surface that
lists every attachment, version and audit state.

## 4. Actors and provisional permissions

Marcelo must confirm the final matrix.

| Actor | List sets | View metadata | Preview files | Download | Upload/replace | Archive |
|---|---:|---:|---:|---:|---:|---:|
| Platform administrator | Provisional yes | Provisional yes | Provisional yes | To confirm | To confirm | To confirm |
| Company administrator | Own tenant | Own tenant | To confirm | To confirm | To confirm | To confirm |
| HSEQ / safety manager | Assigned scope | Assigned scope | Provisional yes | To confirm | To confirm | To confirm |
| Plant / equipment manager | Assigned scope | Assigned scope | Provisional yes | To confirm | Provisional yes | To confirm |
| Site manager | Assigned sites | Assigned sites | To confirm | To confirm | No by default | No by default |
| Read-only auditor | To confirm | To confirm | To confirm | To confirm | No | No |

Every list, detail and file request must enforce tenant and site scope on the
server. An attachment must inherit the set boundary and may also have a stricter
classification.

## 5. GA1 data contract

### Document set

| Field | Purpose | Rule |
|---|---|---|
| `id` | Stable GA1 set identifier | Immutable |
| `tenant_id` | Customer boundary | Mandatory in production |
| `company_id` | Owning company | Mandatory |
| `site_id` | Site context | Mandatory unless Marcelo approves company-wide sets |
| `subcontractor_id` | External owner/operator | Nullable only with documented meaning |
| `title` | Equipment or document-set label | Required and searchable |
| `equipment_id` | Equipment relationship | Requirement to confirm |
| `issue_date` | Source issue date | Requirement to confirm |
| `expiry_date` | Compliance expiry | Store as date, not formatted text |
| `expiry_state` | Stable calculated state | `valid`, `due_soon`, `expired`, `not_applicable` |
| `status` | Set lifecycle | Values require Marcelo's approval |
| `source` | Migration provenance | Protected from normal edits |
| `created_at`, `updated_at` | Audit ordering | Server-managed timestamps |

### Attachment

| Field | Purpose | Rule |
|---|---|---|
| `id` | Stable attachment identifier | Never use storage path as the ID |
| `ga1_set_id` | Parent relationship | Mandatory |
| `display_name` | User-facing filename | Sanitised |
| `media_type` | PDF/JPEG/etc. | Server-detected and allowlisted |
| `size_bytes` | Validation/display | Mandatory |
| `sha256` | Integrity and duplicate detection | Mandatory |
| `version` | Attachment revision | Immutable sequence |
| `storage_key` | Private object reference | Never returned to ordinary clients |
| `uploaded_by`, `uploaded_at` | Provenance | Mandatory for new uploads |
| `malware_state` | Security control | File cannot open before clean result |
| `archived_at` | Lifecycle | Null while active |

## 6. Recommended list and detail workflow

1. User opens GA1.
2. Server returns only authorised document sets and authorised filter options.
3. User searches or filters by site, company, subcontractor, expiry state and
   expiry date.
4. The list displays title, company, subcontractor, site, expiry date, stable
   expiry state, attachment count and `View set`.
5. User opens a set detail page or accessible modal.
6. Server rechecks permission for the selected set.
7. Detail shows set metadata, lifecycle, expiry explanation and every attachment.
8. User previews a PDF or image, or downloads an authorised attachment.
9. The server rechecks permission for the attachment and records the audit event.
10. If uploads/replacements are approved, they create a new immutable version;
    they never overwrite the existing evidence silently.

## 7. Filter and status rules

Recommended filters:

- site;
- company;
- subcontractor;
- expiry state;
- expiry date or inclusive expiry-date range;
- equipment/asset, if GA1 is linked to the asset register;
- file type; and
- global search across an approved field list.

Expiry state must be calculated from `expiry_date` and an approved threshold.
Do not store values such as `11 days remaining` as the authoritative state.
Display the remaining days separately and recalculate it for the user's current
date and Europe/Dublin time zone.

The list API should filter, sort and paginate on the server:

```text
GET /api/v1/ga1?q=&site_id=&company_id=&subcontractor_id=&expiry_state=&expiry_from=&expiry_to=&sort=expiry_asc&page=1&page_size=25
GET /api/v1/ga1/{ga1_id}
```

## 8. Attachment viewing and download

- `View set` opens the set, not merely its first file.
- PDF and image attachments have in-app previews when the browser supports them.
- Every attachment retains explicit Open in new tab and permitted Download
  actions.
- Preview and download use an authorised endpoint rather than a public storage
  path.
- The endpoint sends the correct `Content-Type`, disposition filename, byte-range
  support and security headers.
- Unsupported formats show metadata and a controlled download/open fallback.
- A missing, quarantined or corrupt attachment does not hide the rest of the set.
- Bulk download of a set, if approved, produces an authorised ZIP with a
  manifest and its own audit event.

Proposed endpoints:

```text
GET /api/v1/ga1/{ga1_id}/attachments/{attachment_id}?disposition=inline
GET /api/v1/ga1/{ga1_id}/attachments/{attachment_id}?disposition=attachment
POST /api/v1/ga1/{ga1_id}/attachments             # only if upload is approved
POST /api/v1/ga1/{ga1_id}/attachments/{id}/versions # only if replacement is approved
```

## 9. Required audit evidence

| Event | When | Minimum fields |
|---|---|---|
| `ga1.list_viewed` | Authorised list loads | actor, tenant, scope, time, request ID |
| `ga1.filters_changed` | Filters apply | actor, tenant, filters, result count, time |
| `ga1.set_viewed` | Set detail opens | actor, tenant, set ID, site ID, time |
| `ga1.attachment_previewed` | Inline file authorised | actor, set ID, attachment ID, version, outcome |
| `ga1.attachment_downloaded` | Download authorised | actor, set ID, attachment ID, version, outcome |
| `ga1.attachment_uploaded` | New evidence stored | actor, set ID, attachment ID, hash, time |
| `ga1.attachment_replaced` | New version stored | actor, old/new attachment version, reason, time |
| `ga1.access_denied` | Set/file request rejected | actor, target ID, reason code, time |
| `ga1.expiry_state_changed` | Calculated state crosses threshold | set ID, old/new state, effective time |

## 10. Synthetic acceptance scenarios

### GA1-01 - Tenant and site isolation

An authorised Site Alpha user sees only Tenant A sets at permitted sites; direct
requests for Tenant B return 403 without metadata leakage.

### GA1-02 - Server-side filters

Combining site, subcontractor and `due_soon` returns only matching sets, resets
the page to 1 and reports the correct total.

### GA1-03 - Stable expiry calculation

Synthetic dates on both sides of the approved threshold produce the correct
`valid`, `due_soon` and `expired` states without stored `N days remaining` text.

### GA1-04 - Multi-file set detail

A synthetic set with eight attachments opens one detail surface listing all
eight in a deterministic order; no attachment is hidden behind the row action.

### GA1-05 - PDF preview

Selecting a PDF opens the expected version in the modal with authorised new-tab
and download fallbacks.

### GA1-06 - Image preview

Selecting a JPG/JPEG opens an accessible in-app image preview with filename,
close, new-tab and permitted download actions.

### GA1-07 - Missing attachment

One missing attachment shows an unavailable state and correlation ID while the
remaining attachments in the set stay usable.

### GA1-08 - Replacement creates a version

If replacement is approved, uploading a corrected synthetic file creates a new
version, preserves the old hash and file, records the reason and never mutates
the original evidence.

### GA1-09 - Download denied independently

If a role may preview but not download, inline preview succeeds and attachment
download returns 403 with an audit event.

### GA1-10 - Protected migrated set

Update/delete attempts against a migrated snapshot set return 403 and leave the
set and all attachments unchanged.

## 11. Current gaps before production acceptance

1. The current GA1 list has no structured site, company, subcontractor or expiry
   filters.
2. The row action represents only the first attachment, which is insufficient
   for multi-file sets.
3. JPG/JPEG files do not have an in-app preview.
4. Expiry labels mix stable states with stored `N days remaining` values.
5. Filtering, search, sorting and pagination are not production server-side.
6. Authentication, tenant/site permission and business audit events are absent.
7. Document responses are not yet hardened with the final disposition, byte
   range and security-header rules.
8. Attachment versions, hashes, malware state and replacement reasons are not
   represented.
9. Missing-file, quarantine, denied-access and partial-set failure states need
   automated coverage.
10. Retention, archival, correction, legal hold and permanent-deletion rules are
    unresolved.

## 12. Decisions Marcelo must provide

1. What business object does one GA1 set represent: equipment, inspection,
   certificate, upload batch or another concept?
2. Which roles may list, preview, download, upload, replace and archive GA1?
3. Is access restricted by company, site, equipment, department or a
   combination?
4. Is every GA1 set required to link to a registered plant/equipment item?
5. Which fields are mandatory: title, issue date, expiry date, examiner,
   certificate number, equipment ID and site?
6. Which stable lifecycle states are required?
7. What expiry-warning threshold applies, and can it vary by document type?
8. Which list filters and default sort are required?
9. Should the set detail display all prior attachment versions?
10. May an attachment be replaced, and who approves the replacement?
11. Must a replacement retain the original file permanently?
12. Should JPG/JPEG evidence have an in-app preview?
13. May preview and download permissions differ?
14. Is whole-set ZIP download required?
15. Which actions must be audited and how long are events retained?
16. What retention, archive, legal-hold and deletion rules apply?
17. Should GA1 expiry contribute to worker, site, equipment or company
    compliance dashboards?

## 13. Build sequence after approval

1. Confirm the GA1 business object, mandatory metadata, permissions and expiry
   model.
2. Define tenant-aware set, attachment and version schemas.
3. Implement server-filtered list and authorised set-detail endpoints.
4. Implement secure PDF and image preview plus attachment download.
5. Implement stable expiry calculation and threshold-change jobs/events.
6. Implement immutable audit events.
7. Add approved upload/version actions with malware scanning if in first scope.
8. Pass the ten synthetic acceptance scenarios.
9. Obtain Marcelo's recorded workflow acceptance.

## 14. Definition of done

- Marcelo has answered the 17 GA1 decisions.
- Permission, expiry, versioning and retention rules are approved.
- Every attachment in a multi-file set is visible and independently authorised.
- All ten synthetic scenarios pass on desktop and mobile.
- Direct storage paths are never exposed to ordinary clients.
- Required audit evidence can be demonstrated.
- Migrated records remain immutable unless an approved migration correction
  process creates a new version.
- No real customer information is used in demo or automated tests.
