#!/usr/bin/env python3
"""Verify unattended readiness monitoring and non-destructive backups."""

from __future__ import annotations

import gc
import importlib.util
import json
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def main() -> int:
    application = load_module("kompliance_operations_application", ROOT / "local-app" / "server.py")
    operations = load_module("kompliance_operations_runner", ROOT / "ops_kompliance.py")
    with tempfile.TemporaryDirectory(prefix="kompliance-operations-test-", ignore_cleanup_errors=True) as temporary:
        data_root = Path(temporary)
        application.DATA_ROOT = data_root
        application.DATABASE_PATH = data_root / "kompliance.db"
        application.initialize_database()
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), application.KomplianceHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            operations.DATA_ROOT = data_root
            operations.BACKUP_ROOT = data_root / "backups" / "automated"
            operations.STATUS_PATH = data_root / "operations" / "status.json"
            operations.READY_URL = f"http://127.0.0.1:{httpd.server_port}/api/health/ready"
            ready, ready_error = operations.ready_check()
            backup = operations.verified_backup()
            status = {
                "ready": ready,
                "last_check_error": ready_error,
                "last_backup_at": operations.now_text(),
                "last_backup": backup,
                "last_backup_error": "",
            }
            operations.write_status(status)
            saved = json.loads(operations.STATUS_PATH.read_text(encoding="utf-8"))
            archive = data_root / backup["path"]
            checks = {
                "readiness_probe_passes": ready is True and ready_error == "",
                "automated_backup_is_created": archive.is_file() and archive.stat().st_size > 0,
                "automated_backup_is_verified": backup.get("verified") is True and len(backup.get("sha256", "")) == 64,
                "operations_status_is_atomic_and_readable": saved.get("ready") is True and saved.get("last_backup", {}).get("verified") is True,
            }
            for name, passed in checks.items():
                print(f"[{'PASS' if passed else 'FAIL'}] {name}")
            return 0 if all(checks.values()) else 1
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)
            gc.collect()
            time.sleep(0.2)


if __name__ == "__main__":
    raise SystemExit(main())
