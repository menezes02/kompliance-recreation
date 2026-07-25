#!/usr/bin/env python3
"""Verify operational localisation, review governance and Unicode PDF output."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parent


def load_server():
    path = ROOT / "local-app" / "server.py"
    spec = importlib.util.spec_from_file_location("kompliance_operational_i18n", path)
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
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            content = response.read()
            content_type = response.headers.get("Content-Type", "")
            body = json.loads(content.decode("utf-8")) if "json" in content_type else content
            return response.status, body, response.headers
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8")), error.headers


def main() -> int:
    failures = []
    server = load_server()
    server.AUTH_ENABLED = True
    previous_verification = os.environ.get("KOMPLIANCE_WORKER_EMAIL_VERIFICATION")
    os.environ["KOMPLIANCE_WORKER_EMAIL_VERIFICATION"] = "1"
    with tempfile.TemporaryDirectory(prefix="kompliance-operational-i18n-", ignore_cleanup_errors=True) as temp:
        server.DATA_ROOT = Path(temp)
        server.DATABASE_PATH = Path(temp) / "kompliance.db"
        server.initialize_database()
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.KomplianceHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_port}"
        try:
            setup_code, setup, setup_headers = request(
                base + "/api/auth/setup",
                "POST",
                {"name": "Language Admin", "email": "language@example.test", "password": "Language-Admin-2026!"},
            )
            cookie = setup_headers.get("Set-Cookie", "").split(";", 1)[0]
            csrf = setup.get("csrf_token", "")
            list_code, listing, _ = request(base + "/api/translations?locale=uk-UA&page_size=10", cookie=cookie)
            if setup_code != 201 or list_code != 200 or listing.get("stats", {}).get("total", 0) < 1200:
                failures.append("Administrator cannot load the controlled translation catalogue")
            first = listing.get("data", [{}])[0]
            approved_text = "Перевірений переклад"
            save_code, saved, _ = request(
                base + "/api/translations/review",
                "PUT",
                {
                    "locale": "uk-UA",
                    "source": first.get("source"),
                    "translation": approved_text,
                    "status": "approved",
                    "reviewer": "Native reviewer",
                    "note": "Terminology checked",
                },
                cookie,
                csrf,
            )
            override_code, overrides, _ = request(base + "/api/translations/overrides", cookie=cookie)
            approved = overrides.get("overrides", {}).get("uk-UA", {}).get(first.get("source"))
            if save_code != 200 or override_code != 200 or approved != approved_text:
                failures.append("Approved translations are not exposed as tenant-scoped runtime overrides")
            export_code, export_body, export_headers = request(
                base + "/api/translations/export?locale=uk-UA", cookie=cookie
            )
            if export_code != 200 or b"locale,source,translation,status,reviewer,note" not in export_body:
                failures.append("CSV export did not return the controlled review format")
            import_csv = (
                "locale,source,translation,status,reviewer,note\r\n"
                f'uk-UA,"{first.get("source")}","{approved_text}",approved,"Native reviewer","Imported check"\r\n'
            )
            import_code, imported, _ = request(
                base + "/api/translations/import",
                "POST",
                {"csv": import_csv},
                cookie,
                csrf,
            )
            if import_code != 201 or imported.get("imported") != 1:
                failures.append("Reviewed CSV import failed")
            worker_code, _, _ = request(
                base + "/api/worker/register",
                "POST",
                {
                    "name": "Іван Петренко",
                    "email": "ivan@example.test",
                    "password": "Worker-Password-2026!",
                    "preferred_language": "uk-UA",
                },
            )
            with server.connect_database() as connection:
                worker = connection.execute("SELECT id FROM worker_accounts WHERE email = ?", ("ivan@example.test",)).fetchone()
                profile = json.loads(connection.execute("SELECT payload FROM worker_profiles WHERE worker_id = ?", (worker["id"],)).fetchone()["payload"])
                notification = connection.execute("SELECT subject FROM worker_notifications WHERE worker_id = ?", (worker["id"],)).fetchone()
            if worker_code != 201 or profile.get("preferred_language") != "uk-UA" or notification["subject"] != server.server_message("verify_subject", "uk-UA"):
                failures.append("Worker onboarding did not persist and use the selected language")
            certificate = server.build_certificate_pdf(
                "Будівельна компанія",
                "Іван Петренко",
                "Вступний інструктаж",
                "Дублін",
                "2026-07-23",
                "2027-07-23",
                "KMP-TEST",
                "https://example.test/verify",
                locale="uk-UA",
            )
            extracted = PdfReader(io.BytesIO(certificate)).pages[0].extract_text()
            if not certificate.startswith(b"%PDF") or server.translate_ui("INDUCTION CERTIFICATE", "uk-UA") not in extracted:
                failures.append("Unicode operational PDF labels were not embedded correctly")
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=2)
    if previous_verification is None:
        os.environ.pop("KOMPLIANCE_WORKER_EMAIL_VERIFICATION", None)
    else:
        os.environ["KOMPLIANCE_WORKER_EMAIL_VERIFICATION"] = previous_verification
    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1
    print("[PASS] Translation review list, approval override and CSV exchange")
    print("[PASS] Worker onboarding and verification use the selected language")
    print("[PASS] Unicode certificate labels render in Ukrainian")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
