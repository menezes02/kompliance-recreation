#!/usr/bin/env python3
"""Exercise the administrator review centre without sending external email."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_server():
    path = ROOT / "local-app" / "server.py"
    spec = importlib.util.spec_from_file_location("kompliance_review_server", path)
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
        with urllib.request.urlopen(call, timeout=10) as response:
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
    controlled_deliveries = []
    with tempfile.TemporaryDirectory(
        prefix="kompliance-review-test-", ignore_cleanup_errors=True
    ) as temporary:
        root = Path(temporary)
        module.DATA_ROOT = root / "data"
        module.DATABASE_PATH = module.DATA_ROOT / "kompliance.db"
        module.PRODUCTION_DATA_PATH = root / "no-production-snapshot.json"
        module.initialize_database()
        now = module.utc_now()
        with module.DB_LOCK, module.connect_database() as connection:
            connection.execute(
                "INSERT INTO records(resource, payload, created_at, updated_at, company_id) VALUES ('workers', ?, ?, ?, 1)",
                (
                    json.dumps(
                        {
                            "name": "Protected review evidence",
                            "source": module.PROTECTED_RECORD_SOURCE,
                        }
                    ),
                    now,
                    now,
                ),
            )
            connection.commit()

        environment = {
            "KOMPLIANCE_EMAIL_DELIVERY": "1",
            "KOMPLIANCE_EMAIL_PROVIDER": "gmail_oauth",
            "KOMPLIANCE_BASE_URL": "https://kompliance.example.test",
            "KOMPLIANCE_SMTP_FROM": "sender@example.test",
            "KOMPLIANCE_GMAIL_CLIENT_ID": "client.apps.googleusercontent.com",
            "KOMPLIANCE_GMAIL_CLIENT_SECRET": "LONG_LIVED_CLIENT_SECRET",
            "KOMPLIANCE_GMAIL_REFRESH_TOKEN": "LONG_LIVED_REFRESH_TOKEN",
            "KOMPLIANCE_SCHEDULER": "0",
        }
        previous_environment = {key: os.environ.get(key) for key in environment}
        os.environ.update(environment)
        original_sender = module.send_notification_email
        module.send_notification_email = lambda notification: controlled_deliveries.append(
            {
                "recipient": notification["recipient"],
                "subject": notification["subject"],
            }
        )
        server = ThreadingHTTPServer(("127.0.0.1", 0), module.KomplianceHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            setup_code, setup, setup_headers = request(
                base + "/api/auth/setup",
                "POST",
                {
                    "name": "Review Admin",
                    "email": "admin@example.test",
                    "password": "Review-Centre-2026!",
                },
            )
            cookie = setup_headers.get("Set-Cookie", "").split(";", 1)[0]
            csrf = setup.get("csrf_token", "")
            checks.append(
                (
                    "administrator_setup",
                    setup_code == 201 and bool(cookie) and bool(csrf),
                )
            )
            for role in ("editor", "viewer"):
                code, _, _ = request(
                    base + "/api/users",
                    "POST",
                    {
                        "name": f"Review {role.title()}",
                        "email": f"{role}@example.test",
                        "password": f"Review-{role.title()}-2026!",
                        "role": role,
                    },
                    cookie,
                    csrf,
                )
                checks.append((f"{role}_account_created", code == 201))

            readiness_code, readiness, _ = request(
                base + "/api/review/readiness", cookie=cookie
            )
            statuses = {item["key"]: item["status"] for item in readiness.get("checks", [])}
            checks.append(
                (
                    "initial_readiness_aggregates_existing_controls",
                    readiness_code == 200
                    and readiness.get("pilot_ready")
                    and statuses.get("database") == "pass"
                    and statuses.get("protected_boundary") == "pass"
                    and statuses.get("roles") == "pass"
                    and statuses.get("scheduler") == "hold"
                    and statuses.get("email_test") == "attention",
                )
            )

            viewer_login_code, viewer_login, viewer_headers = request(
                base + "/api/auth/login",
                "POST",
                {
                    "email": "viewer@example.test",
                    "password": "Review-Viewer-2026!",
                },
            )
            viewer_cookie = viewer_headers.get("Set-Cookie", "").split(";", 1)[0]
            viewer_readiness_code, _, _ = request(
                base + "/api/review/readiness", cookie=viewer_cookie
            )
            checks.append(
                (
                    "review_centre_is_administrator_only",
                    viewer_login_code == 200 and viewer_readiness_code == 403,
                )
            )

            checklist = {key: True for key, _ in module.PILOT_REVIEW_CHECKLIST}
            acceptance_code, acceptance_result, _ = request(
                base + "/api/review/acceptance",
                "PUT",
                {
                    "reviewer_name": "Marcelo Reviewer",
                    "product_owner": "Named Product Owner",
                    "technical_owner": "Named Technical Owner",
                    "decision": "accepted_with_conditions",
                    "conditions": "One non-blocking follow-up.",
                    "checklist": checklist,
                },
                cookie,
                csrf,
            )
            saved = acceptance_result.get("acceptance", {})
            checks.append(
                (
                    "acceptance_progress_is_persisted",
                    acceptance_code == 200
                    and saved.get("decision") == "accepted_with_conditions"
                    and all(saved.get("checklist", {}).values()),
                )
            )

            bad_confirmation_code, _, _ = request(
                base + "/api/review/email-test",
                "POST",
                {"recipient": "reviewer@example.test", "confirmation": "wrong"},
                cookie,
                csrf,
            )
            email_code, email_result, _ = request(
                base + "/api/review/email-test",
                "POST",
                {
                    "recipient": "reviewer@example.test",
                    "confirmation": "SEND_CONTROLLED_TEST",
                },
                cookie,
                csrf,
            )
            checks.append(
                (
                    "controlled_email_requires_confirmation_and_records_success",
                    bad_confirmation_code == 400
                    and email_code == 201
                    and email_result.get("status") == "sent"
                    and email_result.get("recipient") != "reviewer@example.test"
                    and len(controlled_deliveries) == 1,
                )
            )

            readiness_code, readiness, _ = request(
                base + "/api/review/readiness", cookie=cookie
            )
            statuses = {item["key"]: item["status"] for item in readiness.get("checks", [])}
            serialized = json.dumps(readiness)
            checks.append(
                (
                    "readiness_records_email_without_exposing_secrets",
                    readiness_code == 200
                    and statuses.get("email_test") == "pass"
                    and environment["KOMPLIANCE_GMAIL_CLIENT_SECRET"] not in serialized
                    and environment["KOMPLIANCE_GMAIL_REFRESH_TOKEN"] not in serialized
                    and "reviewer@example.test" not in serialized,
                )
            )

            module.send_notification_email = lambda notification: (_ for _ in ()).throw(
                RuntimeError(
                    f"Provider rejected {environment['KOMPLIANCE_GMAIL_REFRESH_TOKEN']}"
                )
            )
            failure_code, failure, _ = request(
                base + "/api/review/email-test",
                "POST",
                {
                    "recipient": "failure@example.test",
                    "confirmation": "SEND_CONTROLLED_TEST",
                },
                cookie,
                csrf,
            )
            checks.append(
                (
                    "provider_failures_are_redacted",
                    failure_code == 502
                    and "[redacted]" in failure.get("safe_error", "")
                    and environment["KOMPLIANCE_GMAIL_REFRESH_TOKEN"]
                    not in json.dumps(failure),
                )
            )
            _, failed_readiness, _ = request(
                base + "/api/review/readiness", cookie=cookie
            )
            failed_statuses = {
                item["key"]: item["status"]
                for item in failed_readiness.get("checks", [])
            }
            checks.append(
                (
                    "latest_email_failure_reopens_readiness_action",
                    failed_statuses.get("email_test") == "attention",
                )
            )

            page_code, page, _ = request(base + "/review")
            checks.append(
                (
                    "review_route_serves_application_shell",
                    page_code == 200 and "Review &amp; acceptance" in page,
                )
            )
            with module.DB_LOCK, module.connect_database() as connection:
                protected_payloads = [
                    json.loads(row["payload"])
                    for row in connection.execute(
                        "SELECT payload FROM records WHERE resource = 'workers'"
                    ).fetchall()
                    if module.is_protected_payload(json.loads(row["payload"]))
                ]
                audit_actions = {
                    row["action"]
                    for row in connection.execute(
                        "SELECT action FROM audit_log WHERE company_id = 1"
                    ).fetchall()
                }
            checks.append(
                (
                    "review_actions_are_audited_and_snapshot_unchanged",
                    len(protected_payloads) == 1
                    and protected_payloads[0]["name"] == "Protected review evidence"
                    and {"pilot_acceptance_updated", "controlled_email_test"}
                    <= audit_actions,
                )
            )
        finally:
            module.send_notification_email = original_sender
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            for key, value in previous_environment.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    for name, passed in checks:
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    return 0 if checks and all(passed for _, passed in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
