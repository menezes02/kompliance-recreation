#!/usr/bin/env python3
"""Verify a Kompliance backup and optionally rehearse restore into an empty folder."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path)
    parser.add_argument("--restore-to", type=Path, help="Extract only into a new or empty directory")
    return parser.parse_args()


def safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and not str(path).startswith(("source-archive/", "production-data/"))


def main() -> None:
    args = parse_args()
    backup = args.backup.resolve(strict=True)
    with zipfile.ZipFile(backup) as archive:
        names = archive.namelist()
        if any(not safe_member(name) for name in names):
            raise SystemExit("Backup contains an unsafe or protected path")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("format") != "kompliance-local-backup-v1":
            raise SystemExit("Unsupported backup format")
        for entry in manifest.get("files", []):
            content = archive.read(entry["path"])
            if len(content) != entry["bytes"] or digest(content) != entry["sha256"]:
                raise SystemExit(f"Backup verification failed: {entry['path']}")
        with tempfile.TemporaryDirectory(prefix="kompliance-verify-") as temporary:
            database = Path(temporary) / "kompliance.db"
            database.write_bytes(archive.read("data/kompliance.db"))
            connection = sqlite3.connect(database)
            try:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                records = connection.execute("SELECT COUNT(*) FROM records").fetchone()[0]
                users = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            finally:
                connection.close()
            if integrity != "ok":
                raise SystemExit(f"Database integrity failed: {integrity}")
        if args.restore_to:
            target = args.restore_to.resolve()
            target.mkdir(parents=True, exist_ok=True)
            if any(target.iterdir()):
                raise SystemExit(f"Restore rehearsal target must be empty: {target}")
            archive.extractall(target)
    print(json.dumps({"verified": True, "backup": str(backup), "files": len(manifest["files"]), "records": records, "users": users, "restore_target": str(args.restore_to.resolve()) if args.restore_to else None}, indent=2))


if __name__ == "__main__":
    main()
