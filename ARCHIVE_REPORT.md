# Authorized Source Archive Report

Completed: 2026-07-18

The archive was created with authenticated, read-only requests. No production
record was created, edited, assigned, approved, rejected, or deleted.

## Verified inventory

| Category | Files |
| --- | ---: |
| GA2 PDFs | 475 |
| GA3 PDFs | 13 |
| GA3 Scaffold Inspection PDFs | 1,110 |
| AF3 PDFs | 161 |
| Handover Certificate PDFs | 53 |
| GA2 Manual PDFs | 659 |
| GA3 Manual PDFs | 248 |
| Shared documents | 6 |
| Asset QR images | 148 |
| Custom-form QR images | 3 |
| HSA QR images | 7 |
| Production branding/CSS assets | 12 |
| **Total source files** | **2,895** |

## File types and integrity

| Type | Files |
| --- | ---: |
| PDF | 2,725 |
| PNG | 158 |
| SVG | 7 |
| CSS | 5 |

Final checks:

- 2,895 unique archive paths
- 0 missing files
- 0 empty files
- 0 invalid PDF signatures
- 723,472,253 bytes on disk, including manifests
- Final resumable download pass: 0 failures

## Local example schemas

- `examples/custom-forms.json`: three custom form definitions with sections,
  questions, and field types.
- `examples/inductions.json`: seven sanitized induction structures, their
  shared safety-page pattern, image counts, and scored-choice questions.
- Embedded production images, authentication credentials, session cookies,
  and CSRF tokens are not retained in the schema files.

## Re-run

Set `KOMPLIANCE_EMAIL` and `KOMPLIANCE_PASSWORD` in the current process, then:

```powershell
python .\download_kompliance_archive.py --output .\source-archive --workers 8
```

The downloader is resumable. Existing valid files are skipped and missing
files are retried.
