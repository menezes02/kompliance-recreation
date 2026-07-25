#!/usr/bin/env python3
"""Build, validate and transactionally import authorised Kompliance tenant packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import uuid
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE = ROOT / "local-app" / "data" / "kompliance.db"
DEFAULT_DATA_ROOT = ROOT / "local-app" / "data"
FORMAT = "kompliance-tenant-migration-v1"
APPLY_ACK = "I_HAVE_WRITTEN_CUSTOMER_AUTHORISATION"
MAX_RECORDS = 250_000
MAX_FILE_BYTES = 100 * 1024 * 1024
MAX_PACKAGE_BYTES = 2 * 1024 * 1024 * 1024
SAFE_KEY = re.compile(r"^[A-Za-z0-9_.:@/-]{1,180}$")


def now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def safe_archive_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts and "\\" not in name


def clean_resource(value: object) -> str:
    resource = "".join(character for character in str(value or "").lower().replace("-", "_") if character.isalnum() or character == "_")
    if not resource or len(resource) > 80:
        raise ValueError(f"Invalid resource name: {value!r}")
    return resource


def validate_record(record: object, index: int) -> dict:
    if not isinstance(record, dict):
        raise ValueError(f"Record {index} must be an object")
    source_key = str(record.get("source_key", "")).strip()
    if not SAFE_KEY.fullmatch(source_key):
        raise ValueError(f"Record {index} has an invalid source_key")
    resource = clean_resource(record.get("resource"))
    payload = record.get("payload")
    if not isinstance(payload, dict):
        raise ValueError(f"Record {source_key} payload must be an object")
    links = record.get("links", [])
    attachments = record.get("attachments", [])
    if not isinstance(links, list) or not isinstance(attachments, list):
        raise ValueError(f"Record {source_key} links and attachments must be arrays")
    normalized_links = []
    for link in links:
        if not isinstance(link, dict) or not SAFE_KEY.fullmatch(str(link.get("target_source_key", ""))):
            raise ValueError(f"Record {source_key} contains an invalid relationship")
        field = str(link.get("field", "")).strip()
        if not SAFE_KEY.fullmatch(field):
            raise ValueError(f"Record {source_key} relationship field is invalid")
        normalized_links.append({"field": field, "target_source_key": str(link["target_source_key"]), "many": bool(link.get("many", False))})
    normalized_attachments = []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            raise ValueError(f"Record {source_key} contains an invalid attachment")
        package_path = str(attachment.get("path", ""))
        field = str(attachment.get("field", "file_url")).strip()
        if not safe_archive_name(package_path) or not package_path.startswith("files/") or not SAFE_KEY.fullmatch(field):
            raise ValueError(f"Record {source_key} attachment path or field is invalid")
        normalized_attachments.append({"path": package_path, "field": field, "original_name": str(attachment.get("original_name") or PurePosixPath(package_path).name)[:240]})
    return {
        "source_key": source_key,
        "resource": resource,
        "payload": payload,
        "created_at": str(record.get("created_at") or now()),
        "updated_at": str(record.get("updated_at") or record.get("created_at") or now()),
        "links": normalized_links,
        "attachments": normalized_attachments,
    }


def package_command(args: argparse.Namespace) -> int:
    source_path = args.input.resolve(strict=True)
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source_tenant = str(source.get("source_tenant", "")).strip()
    if not source_tenant:
        raise SystemExit("Input must contain source_tenant")
    records_input = source.get("records")
    if not isinstance(records_input, list) or len(records_input) > MAX_RECORDS:
        raise SystemExit(f"Input records must be an array with at most {MAX_RECORDS} entries")
    records = [validate_record(record, index) for index, record in enumerate(records_input, 1)]
    keys = [record["source_key"] for record in records]
    duplicates = [key for key, count in Counter(keys).items() if count > 1]
    if duplicates:
        raise SystemExit(f"Duplicate source keys: {', '.join(duplicates[:10])}")
    known = set(keys)
    missing_targets = sorted({link["target_source_key"] for record in records for link in record["links"] if link["target_source_key"] not in known})
    if missing_targets:
        raise SystemExit(f"Missing relationship targets: {', '.join(missing_targets[:10])}")
    package_id = str(source.get("package_id") or uuid.uuid4())
    if not SAFE_KEY.fullmatch(package_id):
        raise SystemExit("package_id is invalid")
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing package: {output}")
    records_bytes = (json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    file_entries = {"records.json": {"sha256": sha256_bytes(records_bytes), "bytes": len(records_bytes)}}
    attachment_sources: dict[str, Path] = {}
    for record in records:
        for attachment in record["attachments"]:
            package_path = attachment["path"]
            local_path = (source_path.parent / PurePosixPath(package_path)).resolve(strict=True)
            if source_path.parent.resolve() not in local_path.parents or not local_path.is_file():
                raise SystemExit(f"Attachment escapes the input folder: {package_path}")
            if local_path.stat().st_size > MAX_FILE_BYTES:
                raise SystemExit(f"Attachment exceeds {MAX_FILE_BYTES} bytes: {package_path}")
            existing = attachment_sources.get(package_path)
            if existing and existing != local_path:
                raise SystemExit(f"Attachment package path is reused: {package_path}")
            attachment_sources[package_path] = local_path
            file_entries[package_path] = {"sha256": sha256_file(local_path), "bytes": local_path.stat().st_size}
    manifest = {
        "format": FORMAT,
        "package_id": package_id,
        "source_tenant": source_tenant,
        "created_at": now(),
        "authorised_by": args.authorised_by,
        "authorisation_reference": args.authorisation_reference,
        "record_count": len(records),
        "resource_counts": dict(sorted(Counter(record["resource"] for record in records).items())),
        "relationship_count": sum(len(record["links"]) for record in records),
        "attachment_count": sum(len(record["attachments"]) for record in records),
        "files": file_entries,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        archive.writestr("records.json", records_bytes)
        for package_path, local_path in sorted(attachment_sources.items()):
            archive.write(local_path, package_path)
    print(json.dumps({"created": str(output), "package_sha256": sha256_file(output), **manifest}, indent=2, ensure_ascii=False))
    return 0


def read_package(package: Path) -> tuple[dict, list[dict], dict[str, bytes]]:
    if package.stat().st_size > MAX_PACKAGE_BYTES:
        raise ValueError(f"Package exceeds {MAX_PACKAGE_BYTES} bytes")
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(not safe_archive_name(name) for name in names):
            raise ValueError("Package contains duplicate or unsafe paths")
        if "manifest.json" not in names or "records.json" not in names:
            raise ValueError("Package must contain manifest.json and records.json")
        if sum(entry.file_size for entry in archive.infolist()) > MAX_PACKAGE_BYTES or any(entry.file_size > MAX_FILE_BYTES for entry in archive.infolist() if entry.filename.startswith("files/")):
            raise ValueError("Package expanded size or attachment limit exceeded")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("format") != FORMAT:
            raise ValueError("Unsupported migration package format")
        declared = manifest.get("files")
        if not isinstance(declared, dict) or set(declared) != set(names) - {"manifest.json"}:
            raise ValueError("Manifest file inventory does not match the package")
        content = {}
        for name, expected in declared.items():
            value = archive.read(name)
            if len(value) != int(expected.get("bytes", -1)) or sha256_bytes(value) != expected.get("sha256"):
                raise ValueError(f"Checksum or size mismatch: {name}")
            content[name] = value
    raw_records = json.loads(content["records.json"])
    if not isinstance(raw_records, list) or len(raw_records) > MAX_RECORDS:
        raise ValueError("records.json is invalid or too large")
    records = [validate_record(record, index) for index, record in enumerate(raw_records, 1)]
    keys = [record["source_key"] for record in records]
    if len(keys) != len(set(keys)):
        raise ValueError("records.json contains duplicate source keys")
    known = set(keys)
    missing = sorted({link["target_source_key"] for record in records for link in record["links"] if link["target_source_key"] not in known})
    if missing:
        raise ValueError(f"Missing relationship targets: {', '.join(missing[:10])}")
    referenced_files = {attachment["path"] for record in records for attachment in record["attachments"]}
    if referenced_files != set(content) - {"records.json"}:
        raise ValueError("Attachment references do not match package files")
    if int(manifest.get("record_count", -1)) != len(records):
        raise ValueError("Manifest record count does not match records.json")
    return manifest, records, content


def ensure_migration_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS tenant_migration_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER NOT NULL, package_id TEXT NOT NULL,
            package_sha256 TEXT NOT NULL, source_tenant TEXT NOT NULL, authorised_by TEXT NOT NULL,
            authorisation_reference TEXT NOT NULL, status TEXT NOT NULL, input_records INTEGER NOT NULL DEFAULT 0,
            inserted_records INTEGER NOT NULL DEFAULT 0, skipped_records INTEGER NOT NULL DEFAULT 0,
            reconciliation_json TEXT NOT NULL, created_at TEXT NOT NULL, completed_at TEXT,
            UNIQUE(company_id, package_id));
        CREATE TABLE IF NOT EXISTS tenant_migration_record_map (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL, company_id INTEGER NOT NULL,
            source_key TEXT NOT NULL, resource TEXT NOT NULL, local_record_id INTEGER NOT NULL,
            created_at TEXT NOT NULL, UNIQUE(company_id, source_key));
        """
    )


def migration_report(connection: sqlite3.Connection, company_id: int, package: Path, manifest: dict, records: list[dict]) -> dict:
    company = connection.execute("SELECT id, name FROM companies WHERE id = ? AND active = 1", (company_id,)).fetchone()
    if company is None:
        raise ValueError("Target company does not exist or is inactive")
    if company_id == 1:
        raise ValueError("The protected source-snapshot tenant cannot be a migration target")
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
    existing_package = connection.execute("SELECT id, status FROM tenant_migration_runs WHERE company_id = ? AND package_id = ?", (company_id, manifest["package_id"])).fetchone() if "tenant_migration_runs" in tables else None
    existing_keys: set[str] = set()
    if records and "tenant_migration_record_map" in tables:
        keys = [record["source_key"] for record in records]
        for start in range(0, len(keys), 500):
            batch = keys[start:start + 500]
            existing_keys.update(
                row[0] for row in connection.execute(
                    f"SELECT source_key FROM tenant_migration_record_map WHERE company_id = ? AND source_key IN ({','.join('?' for _ in batch)})",
                    (company_id, *batch),
                ).fetchall()
            )
    input_counts = Counter(record["resource"] for record in records)
    insert_counts = Counter(record["resource"] for record in records if record["source_key"] not in existing_keys)
    report = {
        "mode": "dry-run",
        "target_company": {"id": company["id"], "name": company["name"]},
        "package": {"path": str(package), "id": manifest["package_id"], "sha256": sha256_file(package), "source_tenant": manifest["source_tenant"]},
        "input_records": len(records),
        "would_insert": len(records) - len(existing_keys),
        "would_skip_existing": len(existing_keys),
        "relationships": sum(len(record["links"]) for record in records),
        "attachments": sum(len(record["attachments"]) for record in records),
        "resource_reconciliation": {resource: {"input": count, "insert": insert_counts[resource], "skip": count - insert_counts[resource]} for resource, count in sorted(input_counts.items())},
        "existing_package_run": dict(existing_package) if existing_package else None,
        "validated": True,
        "applied": False,
    }
    return report


def import_command(args: argparse.Namespace) -> int:
    package = args.package.resolve(strict=True)
    manifest, records, content = read_package(package)
    database = args.database.resolve(strict=True)
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    copied_files: list[Path] = []
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        report = migration_report(connection, args.company_id, package, manifest, records)
        if not args.apply:
            if args.report:
                args.report.resolve().write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0
        if args.acknowledge != APPLY_ACK or not args.authorised_by or not args.authorisation_reference:
            raise ValueError(f"Apply requires --acknowledge {APPLY_ACK}, --authorised-by and --authorisation-reference")
        ensure_migration_schema(connection)
        connection.commit()
        report = migration_report(connection, args.company_id, package, manifest, records)
        if report["existing_package_run"]:
            raise ValueError("This package ID already has a migration run for the target company")
        timestamp = now()
        connection.execute("BEGIN IMMEDIATE")
        run_cursor = connection.execute(
            """INSERT INTO tenant_migration_runs(company_id, package_id, package_sha256, source_tenant, authorised_by,
               authorisation_reference, status, input_records, reconciliation_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?, ?)""",
            (args.company_id, manifest["package_id"], sha256_file(package), manifest["source_tenant"], args.authorised_by, args.authorisation_reference, len(records), json.dumps(report), timestamp),
        )
        run_id = run_cursor.lastrowid
        local_ids: dict[str, int] = {}
        payloads: dict[str, dict] = {}
        skipped = 0
        for record in records:
            existing = connection.execute("SELECT local_record_id FROM tenant_migration_record_map WHERE company_id = ? AND source_key = ?", (args.company_id, record["source_key"])).fetchone()
            if existing:
                local_ids[record["source_key"]] = int(existing["local_record_id"])
                skipped += 1
                continue
            payload = dict(record["payload"])
            payload.update({"source": "authorised tenant migration", "local_only": True, "migration_source": manifest["source_tenant"], "migration_source_id": record["source_key"], "migration_package_id": manifest["package_id"]})
            cursor = connection.execute("INSERT INTO records(resource, payload, created_at, updated_at, company_id) VALUES (?, ?, ?, ?, ?)", (record["resource"], json.dumps(payload, ensure_ascii=False), record["created_at"], record["updated_at"], args.company_id))
            local_ids[record["source_key"]] = cursor.lastrowid
            payloads[record["source_key"]] = payload
            connection.execute("INSERT INTO tenant_migration_record_map(run_id, company_id, source_key, resource, local_record_id, created_at) VALUES (?, ?, ?, ?, ?, ?)", (run_id, args.company_id, record["source_key"], record["resource"], cursor.lastrowid, timestamp))
        uploads = args.data_root.resolve() / "uploads"
        uploads.mkdir(parents=True, exist_ok=True)
        for record in records:
            if record["source_key"] not in payloads:
                continue
            payload = payloads[record["source_key"]]
            for link in record["links"]:
                target_id = local_ids[link["target_source_key"]]
                if link["many"]:
                    values = payload.get(link["field"], [])
                    if not isinstance(values, list):
                        values = []
                    if target_id not in values:
                        values.append(target_id)
                    payload[link["field"]] = values
                else:
                    payload[link["field"]] = target_id
            for attachment in record["attachments"]:
                suffix = Path(PurePosixPath(attachment["path"]).name).suffix[:16]
                stored_name = f"migration-{args.company_id}-{run_id}-{uuid.uuid4().hex}{suffix}"
                target = (uploads / stored_name).resolve()
                if uploads not in target.parents:
                    raise ValueError("Unsafe attachment destination")
                target.write_bytes(content[attachment["path"]])
                copied_files.append(target)
                payload[attachment["field"]] = f"/local-files/uploads/{stored_name}"
                attachment_payload = {
                    "title": attachment["original_name"], "original_name": attachment["original_name"], "stored_name": stored_name,
                    "size": len(content[attachment["path"]]), "source": "authorised tenant migration", "local_only": True,
                    "migration_parent_source_key": record["source_key"], "migration_package_id": manifest["package_id"],
                }
                connection.execute("INSERT INTO records(resource, payload, created_at, updated_at, company_id) VALUES ('local_uploads', ?, ?, ?, ?)", (json.dumps(attachment_payload, ensure_ascii=False), timestamp, timestamp, args.company_id))
            connection.execute("UPDATE records SET payload = ? WHERE id = ? AND company_id = ?", (json.dumps(payload, ensure_ascii=False), local_ids[record["source_key"]], args.company_id))
        inserted = len(records) - skipped
        applied_report = {**report, "mode": "apply", "would_insert": 0, "would_skip_existing": 0, "inserted": inserted, "skipped_existing": skipped, "applied": True, "run_id": run_id, "completed_at": now()}
        connection.execute("UPDATE tenant_migration_runs SET status = 'completed', inserted_records = ?, skipped_records = ?, reconciliation_json = ?, completed_at = ? WHERE id = ?", (inserted, skipped, json.dumps(applied_report, ensure_ascii=False), applied_report["completed_at"], run_id))
        connection.commit()
        if args.report:
            args.report.resolve().write_text(json.dumps(applied_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(applied_report, indent=2, ensure_ascii=False))
        return 0
    except Exception:
        connection.rollback()
        for path in copied_files:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    finally:
        connection.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    package = commands.add_parser("package", help="Build a signed-inventory package from an authorised JSON extract")
    package.add_argument("--input", type=Path, required=True)
    package.add_argument("--output", type=Path, required=True)
    package.add_argument("--authorised-by", required=True)
    package.add_argument("--authorisation-reference", required=True)
    package.set_defaults(handler=package_command)
    migrate = commands.add_parser("migrate", help="Validate or apply a package to an isolated tenant")
    migrate.add_argument("--package", type=Path, required=True)
    migrate.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    migrate.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    migrate.add_argument("--company-id", type=int, required=True)
    migrate.add_argument("--report", type=Path)
    migrate.add_argument("--apply", action="store_true")
    migrate.add_argument("--authorised-by")
    migrate.add_argument("--authorisation-reference")
    migrate.add_argument("--acknowledge")
    migrate.set_defaults(handler=import_command)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return args.handler(args)
    except (ValueError, json.JSONDecodeError, zipfile.BadZipFile, sqlite3.Error, OSError) as error:
        print(json.dumps({"error": str(error), "applied": False}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
