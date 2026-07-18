# Kompliance Local Recreation

A dependency-free Python/SQLite recreation of the mapped Kompliance customer
portal. It is intentionally separate from the production service.

## Run

```powershell
python .\server.py
```

Open `http://127.0.0.1:8090/`.

## Docker

From the `kompliance-recreation` directory:

```powershell
docker compose up -d --build
```

The Compose deployment creates:

- Application container: `kompliance_app_example`
- Authenticated gateway container: `kompliance_gateway_example`
- Data volume: `kompliance_data_example`
- Internal application port: `8090`
- Internal gateway port: `80`
- External network: `proxy`

The source archive is mounted at `/app/source-archive` read-only. The
container has a read-only root filesystem and does not publish a host port;
the existing reverse proxy is the only public entry point. The proxy must
forward to `kompliance_gateway_example:80`, not directly to the application
container.

HTTP Basic Authentication is enforced by the gateway. The username is
`kompliance_admin`; only its Apache-compatible password hash is stored in
`deployment/htpasswd`.

Current server deployment:

`https://kompliance.felipeitprojects.com/`

## Production data snapshot

The deployed database is initialized from:

`../production-data/records.json`

The snapshot contains 3,597 records exported through authenticated, read-only
table requests. When its content hash changes, the container replaces the
previous local snapshot on startup. This operation changes only the cloned
SQLite database; it never writes to the production Kompliance service.

To refresh the snapshot, supply credentials through the current process
environment and run:

```powershell
python .\export_kompliance_data.py
docker compose up -d --build app
docker compose restart gateway
```

Credentials, session cookies, CSRF values, induction access tokens, and
presentation/action HTML are not stored in the snapshot.

## Current capabilities

- High-fidelity navigation shell and dashboard
- Responsive desktop/tablet/mobile layout
- Local SQLite records
- Local create, edit, search, pagination, and delete behavior
- Sites, roles, workers, subcontractors, training questions
- Custom forms and distributions
- Visual section/question form builder with three mapped example templates
- Assets and shared-document metadata
- HSA form repositories populated from 2,719 archived PDFs
- GA1 and Risk Assessment document-set metadata
- Visual multi-page induction builder with seven mapped structural examples
- Company profile, local password form, and contact form
- Searchable/category-filtered browser for the authorized source archive

All actions performed in this application affect only
`data/kompliance.db`. They do not call the production Kompliance service.

## Source archive

The archive downloader stores authorized production examples in:

`../source-archive/`

The local `/archive` page indexes those files without exposing them outside the
local server.

The completed archive contains 2,895 source files (2,725 PDFs, 158 PNG files,
7 SVG files, and 5 CSS files). The final verification pass completed with zero
missing files, zero empty files, and zero invalid PDF signatures.

## Reset local sample data

Stop the server and remove `data/kompliance.db`, then start the server again.
The seed records will be recreated.

## Next implementation areas

- Dedicated worker training and Safe Pass editors
- Form assignment and submission workflow
- Worker induction completion and certificate flow
- File upload storage and document expiry processing
- QR generation
- PDF template generation
- Authentication and role permissions
