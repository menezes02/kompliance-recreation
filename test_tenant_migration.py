"""Transaction, relationship and safety tests for tenant_migration.py."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "tenant_migration.py"
ACK = "I_HAVE_WRITTEN_CUSTOMER_AUTHORISATION"


class TenantMigrationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="kompliance-migration-")
        self.root = Path(self.temporary.name)
        self.database = self.root / "kompliance.db"
        self.data_root = self.root / "data"
        self.data_root.mkdir()
        connection = sqlite3.connect(self.database)
        connection.executescript(
            """
            CREATE TABLE companies(id INTEGER PRIMARY KEY, name TEXT NOT NULL, active INTEGER NOT NULL);
            INSERT INTO companies VALUES (1, 'Protected Snapshot', 1), (2, 'Authorised Tenant', 1);
            CREATE TABLE records(
                id INTEGER PRIMARY KEY AUTOINCREMENT, resource TEXT NOT NULL, payload TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, company_id INTEGER NOT NULL DEFAULT 1);
            """
        )
        connection.commit()
        connection.close()
        self.input = self.root / "authorised-input.json"
        self.input.write_text(
            json.dumps(
                {
                    "package_id": "migration-test-001",
                    "source_tenant": "Authorised Source Ltd",
                    "records": [
                        {"source_key": "sites:10", "resource": "sites", "payload": {"name": "North Site"}},
                        {
                            "source_key": "workers:20", "resource": "workers", "payload": {"name": "Imported Worker"},
                            "links": [{"field": "site_id", "target_source_key": "sites:10"}],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        self.package = self.root / "tenant-package.zip"

    def tearDown(self):
        self.temporary.cleanup()

    def run_cli(self, *arguments):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, arguments)], cwd=ROOT,
            text=True, capture_output=True, timeout=30,
        )

    def build_package(self):
        result = self.run_cli(
            "package", "--input", self.input, "--output", self.package,
            "--authorised-by", "Customer Data Owner", "--authorisation-reference", "TICKET-001",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_dry_run_apply_relationship_reconciliation_and_replay_block(self):
        created = self.build_package()
        self.assertEqual(created["record_count"], 2)
        dry_run = self.run_cli(
            "migrate", "--package", self.package, "--database", self.database,
            "--data-root", self.data_root, "--company-id", 2,
        )
        self.assertEqual(dry_run.returncode, 0, dry_run.stderr)
        preview = json.loads(dry_run.stdout)
        self.assertEqual((preview["would_insert"], preview["relationships"], preview["applied"]), (2, 1, False))
        connection = sqlite3.connect(self.database)
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM records").fetchone()[0], 0)
        tables_after_dry_run = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
        self.assertNotIn("tenant_migration_runs", tables_after_dry_run)
        connection.close()

        missing_gate = self.run_cli(
            "migrate", "--package", self.package, "--database", self.database,
            "--data-root", self.data_root, "--company-id", 2, "--apply",
        )
        self.assertNotEqual(missing_gate.returncode, 0)

        applied = self.run_cli(
            "migrate", "--package", self.package, "--database", self.database,
            "--data-root", self.data_root, "--company-id", 2, "--apply",
            "--authorised-by", "Customer Data Owner", "--authorisation-reference", "TICKET-001",
            "--acknowledge", ACK,
        )
        self.assertEqual(applied.returncode, 0, applied.stderr)
        result = json.loads(applied.stdout)
        self.assertEqual((result["inserted"], result["skipped_existing"], result["applied"]), (2, 0, True))
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM records WHERE company_id = 2 ORDER BY id").fetchall()
        self.assertEqual(len(rows), 2)
        site_id = rows[0]["id"]
        worker = json.loads(rows[1]["payload"])
        self.assertEqual(worker["site_id"], site_id)
        self.assertEqual(worker["source"], "authorised tenant migration")
        self.assertTrue(worker["local_only"])
        run = connection.execute("SELECT * FROM tenant_migration_runs").fetchone()
        self.assertEqual((run["status"], run["inserted_records"]), ("completed", 2))
        self.assertEqual(connection.execute("SELECT COUNT(*) FROM tenant_migration_record_map").fetchone()[0], 2)
        connection.close()

        replay = self.run_cli(
            "migrate", "--package", self.package, "--database", self.database,
            "--data-root", self.data_root, "--company-id", 2, "--apply",
            "--authorised-by", "Customer Data Owner", "--authorisation-reference", "TICKET-001",
            "--acknowledge", ACK,
        )
        self.assertNotEqual(replay.returncode, 0)

    def test_protected_snapshot_tenant_is_never_a_target(self):
        self.build_package()
        result = self.run_cli(
            "migrate", "--package", self.package, "--database", self.database,
            "--data-root", self.data_root, "--company-id", 1,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("protected source-snapshot tenant", result.stderr)

    def test_attachment_inventory_and_checksum_tampering(self):
        files = self.root / "files"
        files.mkdir()
        attachment = files / "inspection.pdf"
        attachment.write_bytes(b"%PDF-1.4\nauthorised inspection\n%%EOF")
        source = json.loads(self.input.read_text(encoding="utf-8"))
        source["package_id"] = "migration-files-001"
        source["records"][0]["attachments"] = [
            {"path": "files/inspection.pdf", "field": "document_url", "original_name": "Inspection.pdf"}
        ]
        self.input.write_text(json.dumps(source), encoding="utf-8")
        created = self.build_package()
        self.assertEqual(created["attachment_count"], 1)
        applied = self.run_cli(
            "migrate", "--package", self.package, "--database", self.database,
            "--data-root", self.data_root, "--company-id", 2, "--apply",
            "--authorised-by", "Customer Data Owner", "--authorisation-reference", "TICKET-002",
            "--acknowledge", ACK,
        )
        self.assertEqual(applied.returncode, 0, applied.stderr)
        connection = sqlite3.connect(self.database)
        rows = connection.execute("SELECT resource, payload FROM records WHERE company_id = 2 ORDER BY id").fetchall()
        connection.close()
        site_payload = json.loads(rows[0][1])
        upload_payload = json.loads(next(payload for resource, payload in rows if resource == "local_uploads"))
        stored = self.data_root / "uploads" / upload_payload["stored_name"]
        self.assertEqual(stored.read_bytes(), attachment.read_bytes())
        self.assertTrue(site_payload["document_url"].endswith(upload_payload["stored_name"]))

        tampered = self.root / "tampered.zip"
        with zipfile.ZipFile(self.package) as source_zip, zipfile.ZipFile(tampered, "w") as target_zip:
            for name in source_zip.namelist():
                value = source_zip.read(name)
                target_zip.writestr(name, value + b"tampered" if name == "records.json" else value)
        validation = self.run_cli(
            "migrate", "--package", tampered, "--database", self.database,
            "--data-root", self.data_root, "--company-id", 2,
        )
        self.assertNotEqual(validation.returncode, 0)
        self.assertIn("Checksum or size mismatch", validation.stderr)


if __name__ == "__main__":
    unittest.main()
