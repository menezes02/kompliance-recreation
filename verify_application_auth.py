#!/usr/bin/env python3
"""Exercise application authentication, roles, CSRF and audit logging."""

from __future__ import annotations

import gc
import importlib.util
import json
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
    spec = importlib.util.spec_from_file_location("kompliance_auth_server", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load local server")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request_json(url, method="GET", payload=None, cookie="", csrf=""):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    if csrf:
        headers["X-CSRF-Token"] = csrf
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))
            return response.status, body, response.headers.get("Set-Cookie", "")
    except urllib.error.HTTPError as error:
        body = json.loads(error.read().decode("utf-8"))
        return error.code, body, error.headers.get("Set-Cookie", "")


def request_raw(url, content, headers, cookie="", csrf=""):
    request_headers = dict(headers)
    if cookie:
        request_headers["Cookie"] = cookie
    if csrf:
        request_headers["X-CSRF-Token"] = csrf
    request = urllib.request.Request(url, data=content, method="POST", headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def main() -> int:
    server_module = load_server()
    server_module.AUTH_ENABLED = True
    with tempfile.TemporaryDirectory(
        prefix="kompliance-auth-test-", ignore_cleanup_errors=True
    ) as temp:
        server_module.DATA_ROOT = Path(temp)
        server_module.DATABASE_PATH = Path(temp) / "kompliance.db"
        server_module.initialize_database()
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server_module.KomplianceHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_port}"
        try:
            status_code, status_body, _ = request_json(base + "/api/auth/status")
            anonymous_code, _, _ = request_json(base + "/api/resources/workers?limit=1")
            weak_code, _, _ = request_json(
                base + "/api/auth/setup",
                "POST",
                {"name": "Security Admin", "email": "admin@example.test", "password": "short"},
            )
            setup_code, setup_body, set_cookie = request_json(
                base + "/api/auth/setup",
                "POST",
                {
                    "name": "Security Admin",
                    "email": "admin@example.test",
                    "password": "Correct-Horse-2026!",
                },
            )
            cookie = set_cookie.split(";", 1)[0]
            csrf = setup_body.get("csrf_token", "")
            me_code, me_body, _ = request_json(base + "/api/auth/status", cookie=cookie)
            missing_csrf_code, _, _ = request_json(
                base + "/api/resources/sites", "POST", {"name": "Local auth test"}, cookie
            )
            create_code, created, _ = request_json(
                base + "/api/resources/sites",
                "POST",
                {"name": "Local auth test"},
                cookie,
                csrf,
            )
            worker_code, workers, _ = request_json(
                base + "/api/resources/workers?limit=1", cookie=cookie
            )
            protected = workers.get("data", [{}])[0]
            protected_code, _, _ = request_json(
                base + f"/api/resources/workers/{protected.get('id', 0)}",
                "PUT",
                {"name": "MUST NOT CHANGE"},
                cookie,
                csrf,
            )
            audit_code, audit, _ = request_json(base + "/api/audit?limit=50", cookie=cookie)
            audit_actions = {row.get("action") for row in audit.get("data", [])}
            user_create_code, _, _ = request_json(
                base + "/api/users",
                "POST",
                {"email": "viewer@example.test", "name": "Security Viewer", "role": "viewer", "password": "Viewer-Password-2026!"},
                cookie,
                csrf,
            )
            viewer_login_code, viewer_login, viewer_cookie_header = request_json(
                base + "/api/auth/login",
                "POST",
                {"email": "viewer@example.test", "password": "Viewer-Password-2026!"},
            )
            viewer_cookie = viewer_cookie_header.split(";", 1)[0]
            viewer_create_code, _, _ = request_json(
                base + "/api/resources/sites",
                "POST",
                {"name": "Viewer must not create"},
                viewer_cookie,
                viewer_login.get("csrf_token", ""),
            )
            upload_code, upload = request_raw(
                base + "/api/local/upload",
                b"%PDF-1.4\nlocal controlled test\n%%EOF\n",
                {"Content-Type": "application/pdf", "X-Upload-Title": "Safety%20Plan", "X-File-Name": "safety-plan.pdf"},
                cookie,
                csrf,
            )
            certificate_code, certificate, _ = request_json(
                base + "/api/local/certificate",
                "POST",
                {"worker": "Local Workflow Worker", "induction": "Citywest Site Induction", "site": "Citywest"},
                cookie,
                csrf,
            )
            upload_file = server_module.DATA_ROOT / "uploads" / upload.get("stored_name", "missing")
            certificate_file = server_module.DATA_ROOT / "certificates" / certificate.get("certificate_file", "missing")
            mfa_initial_code, mfa_initial, _ = request_json(base + "/api/auth/mfa", cookie=cookie)
            mfa_setup_code, mfa_setup, _ = request_json(
                base + "/api/auth/mfa/setup",
                "POST",
                {"password": "Correct-Horse-2026!"},
                cookie,
                csrf,
            )
            authenticator_code = server_module.mfa_code(mfa_setup.get("secret", "")) if mfa_setup.get("secret") else ""
            mfa_enable_code, mfa_enabled, _ = request_json(
                base + "/api/auth/mfa/enable",
                "POST",
                {"code": authenticator_code},
                cookie,
                csrf,
            )
            mfa_status_code, mfa_status, _ = request_json(base + "/api/auth/mfa", cookie=cookie)
            mfa_challenge_code, mfa_challenge, _ = request_json(
                base + "/api/auth/login",
                "POST",
                {"email": "admin@example.test", "password": "Correct-Horse-2026!"},
            )
            mfa_login_code, mfa_login, _ = request_json(
                base + "/api/auth/login",
                "POST",
                {"email": "admin@example.test", "password": "Correct-Horse-2026!", "mfa_code": server_module.mfa_code(mfa_setup.get("secret", ""))},
            )
            first_backup = (mfa_enabled.get("backup_codes") or [""])[0]
            backup_login_code, backup_login, _ = request_json(
                base + "/api/auth/login",
                "POST",
                {"email": "admin@example.test", "password": "Correct-Horse-2026!", "mfa_code": first_backup},
            )
            backup_reuse_code, _, _ = request_json(
                base + "/api/auth/login",
                "POST",
                {"email": "admin@example.test", "password": "Correct-Horse-2026!", "mfa_code": first_backup},
            )
            checks = {
                "setup_required_reported": status_code == 200 and status_body.get("setup_required") is True,
                "anonymous_api_blocked": anonymous_code == 401,
                "weak_password_rejected": weak_code == 400,
                "administrator_setup_succeeds": setup_code == 201 and bool(cookie) and bool(csrf),
                "authenticated_status_reports_admin": me_code == 200 and me_body.get("user", {}).get("role") == "admin",
                "csrf_is_required": missing_csrf_code == 403,
                "admin_local_create_allowed": create_code == 201 and created.get("_read_only") is False,
                "protected_snapshot_still_immutable": worker_code == 200 and protected_code == 403,
                "audit_log_records_security_and_changes": audit_code == 200 and {"setup", "create"}.issubset(audit_actions),
                "admin_can_create_role_account": user_create_code == 201,
                "viewer_login_succeeds": viewer_login_code == 200 and viewer_login.get("user", {}).get("role") == "viewer",
                "viewer_cannot_create": viewer_create_code == 403,
                "local_upload_isolated_and_preserved": (
                    upload_code == 201
                    and upload.get("local_only") is True
                    and upload_file.is_file()
                    and upload_file.read_bytes().startswith(b"%PDF-")
                ),
                "local_certificate_generated_as_pdf": (
                    certificate_code == 201
                    and certificate.get("local_only") is True
                    and certificate_file.is_file()
                    and certificate_file.read_bytes().startswith(b"%PDF-")
                ),
                "mfa_setup_requires_password_and_returns_qr": (
                    mfa_initial_code == 200
                    and mfa_initial.get("enabled") is False
                    and mfa_setup_code == 200
                    and mfa_setup.get("qr_data_url", "").startswith("data:image/svg+xml;base64,")
                ),
                "mfa_enable_returns_one_time_backup_codes": (
                    mfa_enable_code == 200
                    and mfa_enabled.get("enabled") is True
                    and len(mfa_enabled.get("backup_codes", [])) == server_module.MFA_BACKUP_CODE_COUNT
                    and mfa_status_code == 200
                    and mfa_status.get("enabled") is True
                ),
                "mfa_is_required_at_login": (
                    mfa_challenge_code == 202
                    and mfa_challenge.get("mfa_required") is True
                    and mfa_login_code == 200
                    and mfa_login.get("authenticated") is True
                ),
                "mfa_backup_code_is_single_use": (
                    backup_login_code == 200
                    and backup_login.get("authenticated") is True
                    and backup_reuse_code == 401
                ),
            }
            for name, passed in checks.items():
                print(f"[{'PASS' if passed else 'FAIL'}] {name}")
            return 0 if all(checks.values()) else 1
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)
            gc.collect()
            time.sleep(0.25)


if __name__ == "__main__":
    raise SystemExit(main())
