#!/usr/bin/env python3
"""Create a verifiable backup of Kompliance local writable data.

The immutable source archive and production snapshot are deliberately excluded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_ROOT = ROOT / "local-app" / "data"
BACKUP_FOLDERS = ("uploads", "evidence", "certificates", "reports")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_root = args.data_root.resolve()
    database = data_root / "kompliance.db"
    if not database.is_file():
        raise SystemExit(f"Database not found: {database}")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = (args.output or (ROOT / "backups" / f"kompliance-local-{stamp}.zip")).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise SystemExit(f"Refusing to overwrite an existing backup: {output}")

    with tempfile.TemporaryDirectory(prefix="kompliance-backup-") as temporary:
        snapshot = Path(temporary) / "kompliance.db"
        source_connection = sqlite3.connect(database)
        destination_connection = sqlite3.connect(snapshot)
        try:
            source_connection.backup(destination_connection)
        finally:
            destination_connection.close()
            source_connection.close()
        verification_connection = sqlite3.connect(snapshot)
        try:
            integrity = verification_connection.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            verification_connection.close()
        if integrity != "ok":
            raise SystemExit(f"Database snapshot integrity check failed: {integrity}")

        files: list[tuple[Path, str]] = [(snapshot, "data/kompliance.db")]
        for folder_name in BACKUP_FOLDERS:
            folder = data_root / folder_name
            if not folder.is_dir():
                continue
            for path in sorted(item for item in folder.rglob("*") if item.is_file()):
                files.append((path, f"data/{path.relative_to(data_root).as_posix()}"))
        manifest = {
            "format": "kompliance-local-backup-v1",
            "created_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "source_archive_included": False,
            "production_snapshot_included": False,
            "database_integrity": integrity,
            "files": [
                {"path": archive_path, "bytes": path.stat().st_size, "sha256": sha256(path)}
                for path, archive_path in files
            ],
        }
        with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for path, archive_path in files:
                archive.write(path, archive_path)
            archive.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"backup": str(output), "bytes": output.stat().st_size, "sha256": sha256(output), "files": len(manifest["files"])}, indent=2))


if __name__ == "__main__":
    main()
