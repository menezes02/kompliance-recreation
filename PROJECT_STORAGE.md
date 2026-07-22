# Kompliance project storage

This directory is the canonical local home for the complete Kompliance project:

- Application source, Docker definitions, tests and operational scripts are stored in this repository.
- Project specifications and Markdown documentation are stored at the repository root.
- `source-archive/` contains the protected, read-only customer document archive.
- `production-data/` contains the protected record snapshot used by the local clone.
- `workstation-backups/server-backups/` contains verified copies pulled from the deployment server.
- `workstation-backups/legacy-desktop-backups/` contains the earlier workstation code and data archives.
- `workstation-backups/legacy-door-backups/` contains the earlier safety-baseline archives.
- `workstation-backups/customer-documentation/` contains the customer review, Marcelo questionnaire and original module requirements.
- `workstation-backups/original-site-reference/` contains captured original-site reference files.
- `workstation-backups/deployment-artifacts/` contains retained deployment packages.

`workstation-backups/` is deliberately excluded from Git. Its contents may include customer data, databases, credentials or large binary archives and must not be pushed to GitHub.

The internal directory structure must be preserved. Flattening the files into one physical directory would break imports, Docker paths, tests and document links. Everything is nevertheless contained beneath this single canonical project directory.
