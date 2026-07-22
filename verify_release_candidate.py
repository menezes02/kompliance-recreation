#!/usr/bin/env python3
"""Exercise release-candidate settings, delivery, retention, refresh and backups."""

from __future__ import annotations

import gc
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_server():
    path = ROOT / "local-app" / "server.py"
    spec = importlib.util.spec_from_file_location("kompliance_release_server", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load local server")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request(url, method="GET", payload=None, cookie="", csrf=""):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    if csrf:
        headers["X-CSRF-Token"] = csrf
    call = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(call, timeout=12) as response:
            raw = response.read()
            content_type = response.headers.get("Content-Type", "")
            body = json.loads(raw) if "json" in content_type else raw.decode("utf-8")
            return response.status, body, response.headers
    except urllib.error.HTTPError as error:
        raw = error.read()
        content_type = error.headers.get("Content-Type", "")
        body = json.loads(raw) if "json" in content_type else raw.decode("utf-8")
        return error.code, body, error.headers


def main() -> int:
    module = load_server()
    module.AUTH_ENABLED = True
    checks = []
    with tempfile.TemporaryDirectory(prefix="kompliance-release-test-", ignore_cleanup_errors=True) as temporary:
        data_root = Path(temporary) / "data"
        module.DATA_ROOT = data_root
        module.DATABASE_PATH = data_root / "kompliance.db"
        module.initialize_database()
        server = ThreadingHTTPServer(("127.0.0.1", 0), module.KomplianceHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            health_code, health, health_headers = request(base + "/api/health/ready")
            checks.append(("readiness_and_security_headers", health_code == 200 and health.get("ok") and health_headers.get("X-Content-Type-Options") == "nosniff" and health_headers.get("X-Frame-Options") == "DENY"))
            setup_code, setup, setup_headers = request(base + "/api/auth/setup", "POST", {"name": "Release Admin", "email": "release@example.test", "password": "Release-Candidate-2026!"})
            cookie = setup_headers.get("Set-Cookie", "").split(";", 1)[0]
            csrf = setup.get("csrf_token", "")
            checks.append(("release_admin_setup", setup_code == 201 and bool(cookie) and bool(csrf)))

            settings_code, settings, _ = request(base + "/api/settings", cookie=cookie)
            update_code, updated, _ = request(base + "/api/settings", "PUT", {"brand_name": "Safety Hub", "brand_company": "Pilot Contractor", "brand_tagline": "Controlled Operations", "privacy_contact": "privacy@example.test", "compliance_recipient": "safety@example.test", "reminder_days": "30", "retention_days": "30"}, cookie, csrf)
            checks.append(("settings_round_trip", settings_code == 200 and update_code == 200 and updated["settings"]["brand_name"] == "Safety Hub"))

            privacy_code, privacy, _ = request(base + "/privacy")
            checks.append(("public_privacy_notice", privacy_code == 200 and "privacy@example.test" in privacy and "Protected imported records are never removed" in privacy))

            status_code, status, _ = request(base + "/api/system/status", cookie=cookie)
            checks.append(("system_readiness_status", status_code == 200 and status.get("ok") and status["records"]["protected"] > 0 and status["database"]["integrity"] == "ok"))

            first_code, first, _ = request(base + "/api/compliance/notifications/prepare", "POST", {"days": 30}, cookie, csrf)
            second_code, second, _ = request(base + "/api/compliance/notifications/prepare", "POST", {"days": 30}, cookie, csrf)
            checks.append(("reminder_deduplication", first_code == 201 and first["created"] > 0 and second_code == 201 and second["created"] == 0 and second["duplicates"] > 0))

            disabled_code, disabled, _ = request(base + "/api/compliance/notifications/send", "POST", {"limit": 5}, cookie, csrf)
            checks.append(("email_fail_closed", disabled_code == 200 and disabled["sent"] == 0 and not disabled["enabled"]))

            delivered = []
            old_environment = {name: os.environ.get(name) for name in ("KOMPLIANCE_EMAIL_DELIVERY", "KOMPLIANCE_BASE_URL", "KOMPLIANCE_SMTP_HOST", "KOMPLIANCE_SMTP_FROM")}
            os.environ.update({"KOMPLIANCE_EMAIL_DELIVERY": "1", "KOMPLIANCE_BASE_URL": "https://kompliance.example.test", "KOMPLIANCE_SMTP_HOST": "smtp.example.test", "KOMPLIANCE_SMTP_FROM": "noreply@example.test"})
            original_sender = module.send_notification_email
            module.send_notification_email = lambda notification: delivered.append(notification["id"])
            try:
                delivery_code, delivery, _ = request(base + "/api/compliance/notifications/send", "POST", {"limit": 5}, cookie, csrf)
            finally:
                module.send_notification_email = original_sender
                for name, value in old_environment.items():
                    if value is None:
                        os.environ.pop(name, None)
                    else:
                        os.environ[name] = value
            checks.append(("email_delivery_history", delivery_code == 200 and delivery["sent"] == 5 and len(delivered) == 5))

            with module.DB_LOCK, module.connect_database() as connection:
                local_cursor = connection.execute("INSERT INTO records(resource, payload, created_at, updated_at) VALUES ('sites', ?, ?, ?)", (json.dumps({"name": "Preserved local site", "source": "local controlled workspace", "local_only": True}), "2020-01-01T00:00:00+00:00", "2020-01-01T00:00:00+00:00"))
                local_id = local_cursor.lastrowid
                connection.execute("INSERT INTO records(resource, payload, created_at, updated_at) VALUES ('local_notifications', ?, ?, ?)", (json.dumps({"kind": "test", "status": "Prepared", "source": "local controlled workspace", "local_only": True}), "2020-01-01T00:00:00+00:00", "2020-01-01T00:00:00+00:00"))
                connection.execute("UPDATE metadata SET value = 'force-refresh-test' WHERE key = 'production_import_version'")
                connection.commit()
            module.initialize_database()
            with module.DB_LOCK, module.connect_database() as connection:
                preserved = connection.execute("SELECT COUNT(*) FROM records WHERE id = ? AND resource = 'sites'", (local_id,)).fetchone()[0]
                protected_before = sum(module.is_protected_payload(json.loads(row["payload"])) for row in connection.execute("SELECT payload FROM records").fetchall())
            checks.append(("snapshot_refresh_preserves_local", preserved == 1 and protected_before > 0))

            wrong_code, _, _ = request(base + "/api/system/retention-cleanup", "POST", {"confirmation": "wrong"}, cookie, csrf)
            cleanup_code, cleanup, _ = request(base + "/api/system/retention-cleanup", "POST", {"confirmation": "PURGE_LOCAL_EXPIRED_DATA"}, cookie, csrf)
            with module.DB_LOCK, module.connect_database() as connection:
                protected_after = sum(module.is_protected_payload(json.loads(row["payload"])) for row in connection.execute("SELECT payload FROM records").fetchall())
            checks.append(("retention_local_only", wrong_code == 400 and cleanup_code == 200 and cleanup["local_notifications"] >= 1 and cleanup["protected_records"] == 0 and protected_after == protected_before))

            for _ in range(5):
                recovery_code, recovery, _ = request(base + "/api/auth/recovery/request", "POST", {"email": "release@example.test"})
            with module.DB_LOCK, module.connect_database() as connection:
                rate_events = connection.execute("SELECT COUNT(*) FROM audit_log WHERE action = 'password_reset_rate_limited'").fetchone()[0]
            checks.append(("recovery_throttled_without_disclosure", recovery_code == 202 and recovery.get("accepted") and rate_events >= 1))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        backup = Path(temporary) / "release-backup.zip"
        restore = Path(temporary) / "restore-rehearsal"
        backup_run = subprocess.run([sys.executable, str(ROOT / "backup_kompliance.py"), "--data-root", str(data_root), "--output", str(backup)], capture_output=True, text=True, timeout=60)
        verify_run = subprocess.run([sys.executable, str(ROOT / "verify_kompliance_backup.py"), str(backup), "--restore-to", str(restore)], capture_output=True, text=True, timeout=60) if backup_run.returncode == 0 else None
        checks.append(("backup_and_restore_rehearsal", backup_run.returncode == 0 and verify_run is not None and verify_run.returncode == 0 and (restore / "data" / "kompliance.db").is_file()))

    gc.collect()
    time.sleep(0.1)
    for name, passed in checks:
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    return 0 if all(passed for _, passed in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
