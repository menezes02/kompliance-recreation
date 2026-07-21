#!/usr/bin/env python3
"""Exercise pilot form, certificate, reminder and account-security workflows."""

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
    spec = importlib.util.spec_from_file_location("kompliance_pilot_server", path)
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
        with urllib.request.urlopen(request, timeout=8) as response:
            return response.status, json.loads(response.read().decode("utf-8")), response.headers.get("Set-Cookie", "")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8")), error.headers.get("Set-Cookie", "")


def request_raw(url, content, headers, cookie="", csrf=""):
    request_headers = dict(headers)
    if cookie:
        request_headers["Cookie"] = cookie
    if csrf:
        request_headers["X-CSRF-Token"] = csrf
    request = urllib.request.Request(url, data=content, method="POST", headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def request_text(url):
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")


def main() -> int:
    server_module = load_server()
    server_module.AUTH_ENABLED = True
    with tempfile.TemporaryDirectory(prefix="kompliance-pilot-test-", ignore_cleanup_errors=True) as temp:
        server_module.DATA_ROOT = Path(temp)
        server_module.DATABASE_PATH = Path(temp) / "kompliance.db"
        server_module.initialize_database()
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server_module.KomplianceHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_port}"
        try:
            setup_code, setup, cookie_header = request_json(
                base + "/api/auth/setup",
                "POST",
                {"name": "Pilot Admin", "email": "pilot-admin@example.test", "password": "Pilot-Administrator-2026!"},
            )
            cookie = cookie_header.split(";", 1)[0]
            csrf = setup.get("csrf_token", "")
            assignment_code, assignment, _ = request_json(
                base + "/api/resources/distributions",
                "POST",
                {"worker": "Pilot Worker", "form": "FIRST AID / MINOR INJURY REPORT", "sites": "Pilot Site", "status": "Pending", "source": "local controlled workspace", "local_only": True},
                cookie,
                csrf,
            )
            evidence_code, evidence = request_raw(
                base + "/api/local/evidence",
                b"\x89PNG\r\n\x1a\nlocal evidence",
                {"Content-Type": "image/png", "X-File-Name": "injury-photo.png", "X-Distribution-Id": str(assignment.get("id", ""))},
                cookie,
                csrf,
            )
            forms_code, forms, _ = request_json(base + "/api/resources/forms?limit=5000", cookie=cookie)
            definition = next(row for row in forms.get("data", []) if row.get("name") == "FIRST AID / MINOR INJURY REPORT")
            complete_answers = []
            for section_index, section in enumerate(definition["definition"]["sections"]):
                for question_index, question in enumerate(section["questions"]):
                    value = "data:image/png;base64,iVBORw0KGgo=" if question.get("type") == "Sign" else "Pilot answer"
                    complete_answers.append({"key": f"s{section_index}q{question_index}", "value": value})
            draft_code, draft, _ = request_json(
                base + "/api/local/submission",
                "POST",
                {"distribution_id": assignment.get("id"), "status": "draft", "answers": complete_answers[:1], "attachment_ids": [evidence.get("id")]},
                cookie,
                csrf,
            )
            incomplete_code, incomplete, _ = request_json(
                base + "/api/local/submission",
                "POST",
                {"distribution_id": assignment.get("id"), "submission_id": draft.get("id"), "status": "submitted", "answers": complete_answers[:1], "attachment_ids": [evidence.get("id")]},
                cookie,
                csrf,
            )
            final_code, final, _ = request_json(
                base + "/api/local/submission",
                "POST",
                {"distribution_id": assignment.get("id"), "submission_id": draft.get("id"), "status": "submitted", "answers": complete_answers, "attachment_ids": [evidence.get("id")]},
                cookie,
                csrf,
            )
            report_file = server_module.DATA_ROOT / "reports" / final.get("report_file", "missing")
            certificate_code, certificate, _ = request_json(
                base + "/api/local/certificate",
                "POST",
                {"company": "Pilot Construction", "worker": "Pilot Worker", "induction": "Pilot Induction", "site": "Pilot Site", "validity_days": 365},
                cookie,
                csrf,
            )
            certificate_file = server_module.DATA_ROOT / "certificates" / certificate.get("certificate_file", "missing")
            verify_code, verify_html = request_text(certificate.get("verification_url", base + "/verify/missing"))
            replacement_code, replacement, _ = request_json(
                base + "/api/local/certificate",
                "POST",
                {"company": "Pilot Construction", "worker": "Pilot Worker", "induction": "Pilot Induction", "site": "Pilot Site", "validity_days": 365, "replaces_id": certificate.get("id")},
                cookie,
                csrf,
            )
            replaced_verify_code, replaced_html = request_text(certificate.get("verification_url", base + "/verify/missing"))
            revoke_code, revoked, _ = request_json(
                base + f"/api/local/certificate/{replacement.get('id', 0)}/revoke",
                "POST",
                {"reason": "Pilot revocation test"},
                cookie,
                csrf,
            )
            reminders_code, reminders, _ = request_json(base + "/api/compliance/reminders?days=30", cookie=cookie)
            prepared_code, prepared, _ = request_json(
                base + "/api/compliance/notifications/prepare", "POST", {"days": 30}, cookie, csrf
            )
            user_code, security_user, _ = request_json(
                base + "/api/users",
                "POST",
                {"name": "Security Pilot", "email": "security-pilot@example.test", "role": "editor", "password": "Security-Pilot-2026!"},
                cookie,
                csrf,
            )
            update_code, updated_user, _ = request_json(
                base + f"/api/users/{security_user.get('id', 0)}",
                "PUT",
                {"name": "Security Pilot", "role": "viewer", "active": True},
                cookie,
                csrf,
            )
            reset_link_code, reset_link, _ = request_json(
                base + f"/api/users/{security_user.get('id', 0)}/reset-link", "POST", {}, cookie, csrf
            )
            token = reset_link.get("reset_url", "").split("token=", 1)[-1]
            reset_code, _, _ = request_json(
                base + "/api/auth/recovery/reset", "POST", {"token": token, "password": "Reset-Security-2026!"}
            )
            login_code, _, _ = request_json(
                base + "/api/auth/login", "POST", {"email": "security-pilot@example.test", "password": "Reset-Security-2026!"}
            )
            lock_codes = []
            for _ in range(6):
                code, _, _ = request_json(
                    base + "/api/auth/login", "POST", {"email": "security-pilot@example.test", "password": "wrong-password"}
                )
                lock_codes.append(code)
            recovery_code, recovery, _ = request_json(
                base + "/api/auth/recovery/request", "POST", {"email": "unknown@example.test"}
            )
            checks = {
                "administrator_setup": setup_code == 201,
                "local_assignment_created": assignment_code == 201 and assignment.get("local_only") is True,
                "evidence_isolated": evidence_code == 201 and evidence.get("distribution_id") == assignment.get("id"),
                "real_form_definition_loaded": forms_code == 200 and len(complete_answers) == 17,
                "incomplete_draft_allowed": draft_code == 201 and draft.get("status") == "Draft",
                "incomplete_final_rejected": incomplete_code == 400 and bool(incomplete.get("missing")),
                "complete_final_and_report": final_code == 200 and final.get("status") == "Submitted" and report_file.is_file() and report_file.read_bytes().startswith(b"%PDF-"),
                "certificate_branded_and_numbered": certificate_code == 201 and certificate.get("certificate_number", "").startswith("KMP-") and certificate_file.is_file(),
                "public_certificate_verification": verify_code == 200 and "Pilot Worker" in verify_html and "Active" in verify_html,
                "certificate_replacement_history": replacement_code == 201 and replaced_verify_code == 200 and "Replaced" in replaced_html,
                "certificate_revocation": revoke_code == 200 and revoked.get("status") == "Revoked",
                "expiry_dashboard_data": reminders_code == 200 and set(reminders.get("counts", {})) == {"overdue", "due_soon", "current", "missing_date"},
                "notifications_prepared_not_sent": prepared_code == 201 and prepared.get("sent") == 0,
                "account_role_update": user_code == 201 and update_code == 200 and updated_user.get("role") == "viewer",
                "secure_reset_token": reset_link_code == 201 and reset_code == 200 and login_code == 200,
                "login_attempt_lockout": lock_codes[:5] == [401] * 5 and lock_codes[-1] == 429,
                "recovery_does_not_disclose_account": recovery_code == 202 and recovery.get("accepted") is True,
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
