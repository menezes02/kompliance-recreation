# Authorised tenant migration

`tenant_migration.py` builds checksum-inventoried packages and imports them into an existing isolated company. It never connects to the original Kompliance service and refuses to target company `1`, which is reserved for the protected customer snapshot.

## Safety sequence

1. Obtain written authorisation from the source customer/data owner.
2. Produce a JSON extract in a controlled folder. Do not place credentials in it.
3. Build the immutable ZIP inventory with the authoriser and ticket/contract reference.
4. Run `migrate` without `--apply`. Review the reconciliation report.
5. Back up the target writable data.
6. Apply only with the exact acknowledgement and the same recorded authority.
7. Review the run in **System & privacy → Authorised migration history**.

Package creation:

```powershell
python tenant_migration.py package `
  --input C:\authorised\client-export.json `
  --output C:\authorised\client-package.zip `
  --authorised-by "Customer data owner" `
  --authorisation-reference "TICKET-1234"
```

Dry run and reconciliation:

```powershell
python tenant_migration.py migrate `
  --package C:\authorised\client-package.zip `
  --company-id 2 `
  --report C:\authorised\dry-run-report.json
```

Authorised apply:

```powershell
python tenant_migration.py migrate `
  --package C:\authorised\client-package.zip `
  --company-id 2 `
  --apply `
  --authorised-by "Customer data owner" `
  --authorisation-reference "TICKET-1234" `
  --acknowledge I_HAVE_WRITTEN_CUSTOMER_AUTHORISATION `
  --report C:\authorised\applied-report.json
```

## Input contract

```json
{
  "package_id": "stable-customer-batch-id",
  "source_tenant": "Authorised customer name",
  "records": [
    {
      "source_key": "sites:source-id",
      "resource": "sites",
      "payload": {"name": "Site name"}
    },
    {
      "source_key": "workers:source-id",
      "resource": "workers",
      "payload": {"name": "Worker name"},
      "links": [
        {"field": "site_id", "target_source_key": "sites:source-id"}
      ],
      "attachments": [
        {"path": "files/document.pdf", "field": "document_url", "original_name": "Document.pdf"}
      ]
    }
  ]
}
```

`source_key` must be stable within that customer. Links are resolved after local IDs are allocated, preserving relationships without reusing foreign tenant IDs. Attachments are verified against the package manifest, copied under unique local names and registered as tenant-owned `local_uploads` records.

## Guarantees

- ZIP paths, file sizes and SHA-256 checksums are validated before database work.
- Duplicate keys, missing relationship targets and undeclared attachments fail validation.
- Dry-run mode performs no database or filesystem mutations.
- Apply uses one immediate SQLite transaction and removes only newly copied files if the transaction fails.
- Package replay is blocked per target company.
- Imported payloads are marked `authorised tenant migration`, `local_only` and include package/source provenance.
- Input/insert/skip counts, resource reconciliation and authorisation evidence are stored with the migration run.
