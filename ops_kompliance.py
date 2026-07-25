#!/usr/bin/env python3
"""Run non-destructive Kompliance readiness checks and verified backups."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("KOMPLIANCE_DATA_ROOT", "/app/local-app/data"))
BACKUP_ROOT = DATA_ROOT / "backups" / "automated"
STATUS_PATH = DATA_ROOT / "operations" / "status.json"
READY_URL = os.environ.get("KOMPLIANCE_READY_URL", "http://app:8090/api/health/ready")
CHECK_SECONDS = max(int(os.environ.get("KOMPLIANCE_MONITOR_INTERVAL_SECONDS", "60")), 15)
BACKUP_SECONDS = max(int(os.environ.get("KOMPLIANCE_BACKUP_INTERVAL_SECONDS", "86400")), 300)
BACKUPS_ENABLED = os.environ.get("KOMPLIANCE_AUTOMATED_BACKUPS", "1").strip() == "1"


def now_text() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_status(status: dict) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATUS_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    temporary.replace(STATUS_PATH)


def ready_check() -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(READY_URL, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))
            return response.status == 200 and body.get("ok") is True, ""
    except Exception as error:  # status is intentionally persisted for operators
        return False, str(error)[:500]


def verified_backup() -> dict:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = BACKUP_ROOT / f"kompliance-local-{stamp}.zip"
    backup = subprocess.run(
        [sys.executable, str(ROOT / "backup_kompliance.py"), "--data-root", str(DATA_ROOT), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
        timeout=600,
    )
    verification = subprocess.run(
        [sys.executable, str(ROOT / "verify_kompliance_backup.py"), str(output)],
        check=True,
        capture_output=True,
        text=True,
        timeout=600,
    )
    backup_result = json.loads(backup.stdout)
    verify_result = json.loads(verification.stdout)
    if verify_result.get("verified") is not True:
        raise RuntimeError("Backup verifier did not report success")
    return {
        "path": str(output.relative_to(DATA_ROOT)),
        "bytes": backup_result.get("bytes", output.stat().st_size),
        "sha256": backup_result.get("sha256", ""),
        "verified": True,
    }


def main() -> int:
    status = {
        "service": "kompliance-operations",
        "started_at": now_text(),
        "ready": False,
        "last_check_at": "",
        "last_check_error": "",
        "backups_enabled": BACKUPS_ENABLED,
        "backup_interval_seconds": BACKUP_SECONDS,
        "last_backup_at": "",
        "last_backup": None,
        "last_backup_error": "",
    }
    last_backup_monotonic = time.monotonic() - BACKUP_SECONDS
    while True:
        status["ready"], status["last_check_error"] = ready_check()
        status["last_check_at"] = now_text()
        if BACKUPS_ENABLED and time.monotonic() - last_backup_monotonic >= BACKUP_SECONDS:
            try:
                status["last_backup"] = verified_backup()
                status["last_backup_at"] = now_text()
                status["last_backup_error"] = ""
            except Exception as error:
                status["last_backup_error"] = str(error)[:1000]
            last_backup_monotonic = time.monotonic()
        write_status(status)
        print(json.dumps(status, separators=(",", ":")), flush=True)
        time.sleep(CHECK_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
