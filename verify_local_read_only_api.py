#!/usr/bin/env python3
"""Exercise immutable snapshot records against an isolated local API server."""

from __future__ import annotations

import importlib.util
import gc
import json
import tempfile
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import date, datetime
from http.server import ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def parse_snapshot_date(value: str) -> date:
    for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported snapshot date: {value!r}")


def load_server():
    path = ROOT / "local-app" / "server.py"
    spec = importlib.util.spec_from_file_location("kompliance_local_server", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load local server")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request_json(url: str, method: str = "GET", payload: dict | None = None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))
            return response.status, body
    except urllib.error.HTTPError as error:
        body = json.loads(error.read().decode("utf-8"))
        return error.code, body


def main() -> int:
    server_module = load_server()
    with tempfile.TemporaryDirectory(prefix="kompliance-read-only-test-") as temp:
        server_module.DATA_ROOT = Path(temp)
        server_module.DATABASE_PATH = Path(temp) / "kompliance.db"
        server_module.initialize_database()

        httpd = ThreadingHTTPServer(
            ("127.0.0.1", 0), server_module.KomplianceHandler
        )
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_port}"
        try:
            status, worker_list = request_json(
                base + "/api/resources/workers?limit=1"
            )
            if status != 200 or not worker_list.get("data"):
                raise RuntimeError("Unable to load an imported worker")
            protected = worker_list["data"][0]
            protected_url = (
                base + f"/api/resources/workers/{protected['id']}"
            )
            original_name = protected.get("name")

            put_status, _ = request_json(
                protected_url,
                "PUT",
                {"name": "MUST NOT CHANGE"},
            )
            delete_status, _ = request_json(protected_url, "DELETE")
            _, protected_after = request_json(protected_url)

            create_status, local_record = request_json(
                base + "/api/resources/workers",
                "POST",
                {"name": "Synthetic Safety Test Worker"},
            )
            local_url = base + f"/api/resources/workers/{local_record['id']}"
            local_put_status, local_after = request_json(
                local_url,
                "PUT",
                {"name": "Updated Synthetic Safety Test Worker"},
            )
            local_delete_status, _ = request_json(local_url, "DELETE")

            ga1_status, ga1_list = request_json(
                base + "/api/resources/ga1?limit=5000"
            )
            ga1_rows = ga1_list.get("data", [])
            ga1_protected = ga1_rows[0] if ga1_rows else {}
            ga1_url = base + f"/api/resources/ga1/{ga1_protected.get('id', 0)}"
            ga1_put_status, _ = request_json(
                ga1_url,
                "PUT",
                {"title": "MUST NOT CHANGE"},
            )
            ga1_delete_status, _ = request_json(ga1_url, "DELETE")
            archive_root = server_module.ARCHIVE_ROOT.resolve()
            ga1_paths = [
                path
                for row in ga1_rows
                for path in row.get("archive_paths", [])
            ]
            archive_paths_safe = all(
                archive_root in (candidate := (archive_root / path).resolve()).parents
                and candidate.is_file()
                for path in ga1_paths
            )
            worker_full_status, worker_full_list = request_json(
                base + "/api/resources/workers?limit=5000"
            )
            worker_rows = worker_full_list.get("data", [])
            safe_pass_counts = Counter(
                row.get("safe_pass_expiry", "") for row in worker_rows
            )
            document_status, document_list = request_json(
                base + "/api/resources/documents?limit=5000"
            )
            document_rows = document_list.get("data", [])
            document_record = document_rows[0] if document_rows else {}
            document_url = (
                base + f"/api/resources/documents/{document_record.get('id', 0)}"
            )
            document_put_status, _ = request_json(
                document_url,
                "PUT",
                {"title": "MUST NOT CHANGE"},
            )
            document_delete_status, _ = request_json(document_url, "DELETE")
            document_files = [
                (archive_root / row.get("archive_path", "")).resolve()
                for row in document_rows
            ]
            risk_status, risk_list = request_json(
                base + "/api/resources/risk_assessment?limit=5000"
            )
            risk_rows = risk_list.get("data", [])
            risk_record = risk_rows[0] if risk_rows else {}
            risk_url = (
                base
                + f"/api/resources/risk_assessment/{risk_record.get('id', 0)}"
            )
            risk_put_status, _ = request_json(
                risk_url,
                "PUT",
                {"title": "MUST NOT CHANGE"},
            )
            risk_delete_status, _ = request_json(risk_url, "DELETE")
            distribution_status, distribution_list = request_json(
                base + "/api/resources/distributions?limit=5000"
            )
            distribution_rows = distribution_list.get("data", [])
            distribution_record = distribution_rows[0] if distribution_rows else {}
            distribution_url = (
                base
                + f"/api/resources/distributions/{distribution_record.get('id', 0)}"
            )
            distribution_put_status, _ = request_json(
                distribution_url,
                "PUT",
                {"status": "MUST NOT CHANGE"},
            )
            distribution_delete_status, _ = request_json(
                distribution_url, "DELETE"
            )
            distribution_counts = Counter(
                row.get("status", "") for row in distribution_rows
            )
            induction_status, induction_list = request_json(
                base + "/api/resources/inductions?limit=5000"
            )
            induction_rows = induction_list.get("data", [])
            induction_record = induction_rows[0] if induction_rows else {}
            induction_url = (
                base + f"/api/resources/inductions/{induction_record.get('id', 0)}"
            )
            induction_put_status, _ = request_json(
                induction_url, "PUT", {"title": "MUST NOT CHANGE"}
            )
            induction_delete_status, _ = request_json(induction_url, "DELETE")
            induction_pages = [
                page
                for row in induction_rows
                for page in row.get("pages", {}).get("pages", [])
            ]
            induction_blocks = [
                block for page in induction_pages for block in page.get("blocks", [])
            ]

            asset_status, asset_list = request_json(
                base + "/api/resources/assets?limit=5000"
            )
            asset_rows = asset_list.get("data", [])
            asset_record = asset_rows[0] if asset_rows else {}
            asset_url = base + f"/api/resources/assets/{asset_record.get('id', 0)}"
            asset_put_status, _ = request_json(
                asset_url, "PUT", {"name": "MUST NOT CHANGE"}
            )
            asset_delete_status, _ = request_json(asset_url, "DELETE")
            asset_qr_files = [
                (archive_root / row.get("qr_archive_path", "")).resolve()
                for row in asset_rows
            ]

            training_status, training_list = request_json(
                base + "/api/resources/training?limit=5000"
            )
            training_rows = training_list.get("data", [])
            training_record = training_rows[0] if training_rows else {}
            training_url = (
                base + f"/api/resources/training/{training_record.get('id', 0)}"
            )
            training_put_status, _ = request_json(
                training_url, "PUT", {"question": "MUST NOT CHANGE"}
            )
            training_delete_status, _ = request_json(training_url, "DELETE")
            training_indicators = Counter(
                row.get("expiry_date", "") for row in training_rows
            )

            form_status, form_list = request_json(
                base + "/api/resources/forms?limit=5000"
            )
            form_rows = form_list.get("data", [])
            form_record = form_rows[0] if form_rows else {}
            form_url = base + f"/api/resources/forms/{form_record.get('id', 0)}"
            form_put_status, _ = request_json(
                form_url, "PUT", {"name": "MUST NOT CHANGE"}
            )
            form_delete_status, _ = request_json(form_url, "DELETE")
            form_sections = [
                section
                for row in form_rows
                for section in row.get("definition", {}).get("sections", [])
            ]
            form_qr_files = [
                (archive_root / row.get("qr_archive_path", "")).resolve()
                for row in form_rows
            ]

            checks = {
                "protected_record_flagged": protected.get("_read_only") is True,
                "protected_update_forbidden": put_status == 403,
                "protected_delete_forbidden": delete_status == 403,
                "protected_record_unchanged": protected_after.get("name") == original_name,
                "synthetic_create_allowed": create_status == 201,
                "synthetic_update_allowed": (
                    local_put_status == 200
                    and local_after.get("name")
                    == "Updated Synthetic Safety Test Worker"
                ),
                "synthetic_delete_allowed": local_delete_status == 200,
                "ga1_snapshot_loaded": ga1_status == 200 and len(ga1_rows) == 166,
                "ga1_records_protected": all(
                    row.get("_read_only") is True for row in ga1_rows
                ),
                "ga1_update_forbidden": ga1_put_status == 403,
                "ga1_delete_forbidden": ga1_delete_status == 403,
                "ga1_archive_documents_linked": len(ga1_paths) == 180,
                "ga1_multi_document_sets_preserved": any(
                    len(row.get("archive_paths", [])) > 1 for row in ga1_rows
                ),
                "ga1_pdf_and_image_formats_preserved": (
                    any(path.lower().endswith(".pdf") for path in ga1_paths)
                    and any(path.lower().endswith((".jpg", ".jpeg")) for path in ga1_paths)
                ),
                "ga1_archive_paths_safe_and_present": archive_paths_safe,
                "worker_snapshot_loaded": (
                    worker_full_status == 200 and len(worker_rows) == 286
                ),
                "worker_safe_pass_alert_source_preserved": (
                    safe_pass_counts["Expired"] == 32
                    and safe_pass_counts["Expiring Soon"] == 8
                ),
                "ga1_expiry_dates_are_parseable": all(
                    date.fromisoformat(row["expiry_date"])
                    for row in ga1_rows
                ),
                "shared_document_snapshot_loaded": (
                    document_status == 200 and len(document_rows) == 6
                ),
                "shared_document_records_protected": all(
                    row.get("_read_only") is True for row in document_rows
                ),
                "shared_document_update_forbidden": document_put_status == 403,
                "shared_document_delete_forbidden": document_delete_status == 403,
                "shared_document_files_safe_and_present": all(
                    archive_root in file_path.parents and file_path.is_file()
                    for file_path in document_files
                ),
                "shared_document_pdf_signatures_valid": all(
                    file_path.read_bytes()[:5] == b"%PDF-"
                    for file_path in document_files
                ),
                "risk_assessment_snapshot_loaded": (
                    risk_status == 200 and len(risk_rows) == 125
                ),
                "risk_assessment_records_protected": all(
                    row.get("_read_only") is True for row in risk_rows
                ),
                "risk_assessment_update_forbidden": risk_put_status == 403,
                "risk_assessment_delete_forbidden": risk_delete_status == 403,
                "risk_assessment_expiry_dates_parseable": all(
                    parse_snapshot_date(row["expiry_date"])
                    for row in risk_rows
                ),
                "risk_assessment_attachment_absence_is_explicit": all(
                    not row.get("archive_path") and not row.get("archive_paths")
                    for row in risk_rows
                ),
                "distribution_snapshot_loaded": (
                    distribution_status == 200 and len(distribution_rows) == 59
                ),
                "distribution_records_protected": all(
                    row.get("_read_only") is True for row in distribution_rows
                ),
                "distribution_update_forbidden": distribution_put_status == 403,
                "distribution_delete_forbidden": distribution_delete_status == 403,
                "distribution_status_counts_preserved": (
                    distribution_counts["Pending"] == 56
                    and distribution_counts["Submitted"] == 3
                ),
                "distribution_dates_parseable": all(
                    parse_snapshot_date(row["assigned_date"])
                    and (
                        row.get("submitted_date") == "-"
                        or parse_snapshot_date(row["submitted_date"])
                    )
                    for row in distribution_rows
                ),
                "distribution_answer_absence_is_explicit": all(
                    not row.get("answers")
                    and not row.get("signature")
                    and not row.get("attachments")
                    for row in distribution_rows
                ),
                "induction_snapshot_loaded": (
                    induction_status == 200 and len(induction_rows) == 7
                ),
                "induction_records_protected": all(
                    row.get("_read_only") is True for row in induction_rows
                ),
                "induction_update_forbidden": induction_put_status == 403,
                "induction_delete_forbidden": induction_delete_status == 403,
                "induction_structure_preserved": (
                    len(induction_pages) == 110
                    and sum(block.get("type") == "question" for block in induction_blocks) == 21
                    and sum(row.get("submissions", 0) for row in induction_rows) == 168
                ),
                "induction_missing_media_is_quantified": (
                    sum(int(block.get("embedded_image_count", 0)) for block in induction_blocks)
                    == 147
                ),
                "asset_snapshot_loaded": asset_status == 200 and len(asset_rows) == 148,
                "asset_records_protected": all(
                    row.get("_read_only") is True for row in asset_rows
                ),
                "asset_update_forbidden": asset_put_status == 403,
                "asset_delete_forbidden": asset_delete_status == 403,
                "asset_qr_files_safe_and_present": all(
                    archive_root in file_path.parents
                    and file_path.is_file()
                    and file_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
                    for file_path in asset_qr_files
                ),
                "training_snapshot_loaded": (
                    training_status == 200 and len(training_rows) == 28
                ),
                "training_records_protected": all(
                    row.get("_read_only") is True for row in training_rows
                ),
                "training_update_forbidden": training_put_status == 403,
                "training_delete_forbidden": training_delete_status == 403,
                "training_source_indicators_preserved": (
                    training_indicators["Expired"] == 26
                    and training_indicators["-"] == 2
                ),
                "form_snapshot_loaded": form_status == 200 and len(form_rows) == 3,
                "form_records_protected": all(
                    row.get("_read_only") is True for row in form_rows
                ),
                "form_update_forbidden": form_put_status == 403,
                "form_delete_forbidden": form_delete_status == 403,
                "form_definitions_preserved": (
                    len(form_sections) == 16
                    and sum(len(section.get("questions", [])) for section in form_sections)
                    == 78
                ),
                "form_qr_files_safe_and_present": all(
                    archive_root in file_path.parents
                    and file_path.is_file()
                    and file_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
                    for file_path in form_qr_files
                ),
                "form_distributions_link_to_real_definitions": (
                    {row.get("form") for row in distribution_rows}
                    == {row.get("name") for row in form_rows}
                ),
            }
            for name, passed in checks.items():
                print(f"[{'PASS' if passed else 'FAIL'}] {name}")
            if not all(checks.values()):
                return 1
            print("\nLocal API read-only integration test passed.")
            return 0
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)
            gc.collect()
            time.sleep(0.25)


if __name__ == "__main__":
    raise SystemExit(main())
