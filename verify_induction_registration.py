#!/usr/bin/env python3
"""Verify site QR links and the public induction registration workflow."""

from __future__ import annotations

import base64
import importlib.util
import json
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_server():
    path = ROOT / "local-app" / "server.py"
    spec = importlib.util.spec_from_file_location("kompliance_induction_server", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load the Kompliance server")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request(base: str, path: str, method="GET", body=None, headers=None):
    request_headers = dict(headers or {})
    data = body
    if isinstance(body, dict):
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    call = urllib.request.Request(base + path, data=data, method=method, headers=request_headers)
    try:
        with urllib.request.urlopen(call, timeout=15) as response:
            raw = response.read()
            content_type = response.headers.get("Content-Type", "")
            payload = json.loads(raw) if "json" in content_type else raw
            return response.status, payload, response.headers
    except urllib.error.HTTPError as error:
        raw = error.read()
        content_type = error.headers.get("Content-Type", "")
        payload = json.loads(raw) if raw and "json" in content_type else raw
        return error.code, payload, error.headers


def valid_payload(schema: dict) -> dict:
    return {
        "name": "Verification Worker",
        "email": "verification.worker@example.test",
        "worker_id": "VERIFY-001",
        "country_code": "+353",
        "phone_number": "870000001",
        "emergency_country_code": "+353",
        "emergency_phone_number": "870000002",
        "emergency_contact_name": "Verification Contact",
        "emergency_contact_address": "Verification address",
        "roles": [schema["roles"][0]["id"]],
        "subcontractors": [schema["subcontractors"][0]["id"]],
        "medical_details": "",
        "training_records": [
            {"question_id": item["id"], "answer": "no", "expiry_date": ""}
            for item in schema["training_questions"]
        ],
        "safe_pass": {"answer": "no"},
        "safety_confirmation": True,
        "language": "en-IE",
    }


def main() -> int:
    module = load_server()
    module.AUTH_ENABLED = False
    checks = []
    with tempfile.TemporaryDirectory(prefix="kompliance-induction-", ignore_cleanup_errors=True) as temporary:
        module.DATA_ROOT = Path(temporary) / "data"
        module.DATABASE_PATH = module.DATA_ROOT / "kompliance.db"
        module.initialize_database()
        server = ThreadingHTTPServer(("127.0.0.1", 0), module.KomplianceHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            sites_status, sites, _ = request(base, "/api/company/induction-sites")
            checks.append(("seven_site_links", sites_status == 200 and len(sites.get("data", [])) == 7))
            site = sites["data"][0]
            token = site["public_token"]

            schema_status, schema, _ = request(base, f"/api/public/induction/{token}")
            checks.append(
                (
                    "complete_public_schema",
                    schema_status == 200
                    and len(schema.get("fields", [])) == 15
                    and len(schema.get("roles", [])) == 22
                    and len(schema.get("training_questions", [])) == 28
                    and len(schema.get("calling_codes", [])) == 245
                    and schema.get("selected_site", {}).get("name") == site["site_name"],
                )
            )
            page_status, page, _ = request(base, f"/induction/c/{token}/register")
            checks.append(("public_registration_page", page_status == 200 and b"registration-form" in page))
            qr_status, qr, qr_headers = request(base, site["qr_url"])
            checks.append(("site_qr_svg", qr_status == 200 and b"<svg" in qr and "svg" in qr_headers.get("Content-Type", "")))

            invalid_status, invalid, _ = request(
                base,
                f"/api/public/induction/{token}/registrations",
                "POST",
                {"email": "not-an-email"},
            )
            checks.append(("server_validation", invalid_status == 400 and bool(invalid.get("errors"))))

            payload = valid_payload(schema)
            payload["training_records"][0] = {
                "question_id": schema["training_questions"][0]["id"],
                "answer": "yes",
                "expiry_date": "2027-07-24",
            }
            create_status, created, _ = request(
                base,
                f"/api/public/induction/{token}/registrations",
                "POST",
                payload,
            )
            checks.append(
                (
                    "registration_created",
                    create_status == 201
                    and created.get("status") == "evidence_pending"
                    and created.get("required_evidence") == [f"training:{schema['training_questions'][0]['id']}:photo"],
                )
            )

            complete_path = f"/api/public/induction/{token}/registrations/{created['id']}/complete"
            completion_headers = {"X-Upload-Token": created["upload_token"]}
            incomplete_status, incomplete, _ = request(base, complete_path, "POST", {}, completion_headers)
            checks.append(("required_evidence_enforced", incomplete_status == 409 and bool(incomplete.get("missing_evidence"))))

            png = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
            )
            evidence_status, evidence, _ = request(
                base,
                f"/api/public/induction/{token}/registrations/{created['id']}/evidence",
                "POST",
                png,
                {
                    **completion_headers,
                    "Content-Type": "image/png",
                    "X-Field-Key": f"training:{schema['training_questions'][0]['id']}:photo",
                    "X-File-Name": "manual-handling.png",
                },
            )
            checks.append(("evidence_uploaded", evidence_status == 201 and evidence.get("size") == len(png)))

            submitted_status, submitted, _ = request(base, complete_path, "POST", {}, completion_headers)
            checks.append(("registration_submitted", submitted_status == 200 and submitted.get("status") == "submitted"))

            list_status, registrations, _ = request(base, "/api/company/induction-registrations")
            checks.append(
                (
                    "admin_registration_visibility",
                    list_status == 200
                    and registrations.get("data", [])[0]["reference"] == submitted["reference"]
                    and registrations["data"][0]["evidence_count"] == 1,
                )
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    failed = [name for name, passed in checks if not passed]
    for name, passed in checks:
        print(f"{'PASS' if passed else 'FAIL'} {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
