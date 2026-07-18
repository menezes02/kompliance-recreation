#!/usr/bin/env python3
"""Local Kompliance recreation server.

Uses only the Python standard library so the project runs on the current
machine without npm, Composer, or third-party Python packages.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sqlite3
import threading
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


APP_ROOT = Path(__file__).resolve().parent
STATIC_ROOT = APP_ROOT / "static"
DATA_ROOT = APP_ROOT / "data"
DATABASE_PATH = DATA_ROOT / "kompliance.db"
ARCHIVE_ROOT = APP_ROOT.parent / "source-archive"
EXAMPLES_ROOT = APP_ROOT.parent / "examples"
PRODUCTION_DATA_PATH = APP_ROOT.parent / "production-data" / "records.json"
MAX_BODY_BYTES = 10 * 1024 * 1024
DB_LOCK = threading.RLock()


SEED_RECORDS = {
    "sites": [
        {
            "name": "Demo Site",
            "address": "Local development address",
            "remarks": "Seed data — safe to edit or delete locally.",
        }
    ],
    "roles": [
        {"name": "Site Supervisor"},
        {"name": "General Operative"},
    ],
    "workers": [
        {
            "worker_id": "DEMO-001",
            "name": "Demo Worker",
            "email": "worker@example.test",
            "type": "Permanent",
            "status": "Pending",
            "phone": "+353 000 000 000",
            "sites": "Demo Site",
            "roles": "General Operative",
            "training_status": "Incomplete",
            "safe_pass_expiry": "",
            "induction_status": "Pending",
        }
    ],
    "subcontractors": [
        {
            "company_name": "Demo Subcontractor",
            "name": "Demo Contact",
            "email": "subcontractor@example.test",
            "phone": "+353 000 000 001",
            "expiry_date": "",
        }
    ],
    "training": [
        {"question": "Manual Handling?"},
        {"question": "First Aid training?"},
    ],
    "forms": [
        {
            "name": "Demo Safety Form",
            "assigned_sites": "Demo Site",
            "assigned_roles": "General Operative",
            "status": "Draft",
        }
    ],
    "distributions": [],
    "assets": [
        {
            "subcontractor": "Demo Subcontractor",
            "name": "Demo Asset",
            "asset_id": "ASSET-001",
        }
    ],
    "documents": [],
    "ga1": [],
    "ga2": [],
    "ga3": [],
    "ga3_scaffold": [],
    "af3": [],
    "handover": [],
    "ga2_manual": [],
    "ga3_manual": [],
    "risk_assessment": [],
    "inductions": [
        {
            "title": "Demo Site Induction",
            "site": "Demo Site",
            "submissions": 0,
            "status": "Active",
        }
    ],
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def connect_database() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    with DB_LOCK, connect_database() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_records_resource ON records(resource)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        if PRODUCTION_DATA_PATH.exists():
            production_data = json.loads(
                PRODUCTION_DATA_PATH.read_text(encoding="utf-8")
            )
            import_version = production_data.get("content_sha256", "")
            imported_row = connection.execute(
                "SELECT value FROM metadata WHERE key = 'production_import_version'"
            ).fetchone()
            imported_version = imported_row["value"] if imported_row else None
            if import_version and import_version != imported_version:
                connection.execute("DELETE FROM records")
                for resource, records in production_data.get("records", {}).items():
                    timestamps = production_data.get("timestamps", {}).get(
                        resource, []
                    )
                    rows = []
                    for index, record in enumerate(records):
                        source_time = (
                            timestamps[index] if index < len(timestamps) else {}
                        )
                        created_at = source_time.get("created_at") or utc_now()
                        updated_at = source_time.get("updated_at") or created_at
                        rows.append(
                            (
                                clean_resource(resource),
                                json.dumps(record, ensure_ascii=False),
                                created_at,
                                updated_at,
                            )
                        )
                    connection.executemany(
                        """
                        INSERT INTO records(resource, payload, created_at, updated_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        rows,
                    )
                connection.execute(
                    """
                    INSERT INTO metadata(key, value)
                    VALUES ('production_import_version', ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (import_version,),
                )
                connection.execute(
                    """
                    INSERT INTO metadata(key, value)
                    VALUES ('production_exported_at', ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (production_data.get("exported_at", ""),),
                )
            connection.commit()
            return

        for resource, records in SEED_RECORDS.items():
            existing = connection.execute(
                "SELECT COUNT(*) FROM records WHERE resource = ?",
                (resource,),
            ).fetchone()[0]
            if existing:
                continue
            now = utc_now()
            connection.executemany(
                """
                INSERT INTO records(resource, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (resource, json.dumps(record), now, now)
                    for record in records
                ],
            )

        custom_forms_path = EXAMPLES_ROOT / "custom-forms.json"
        if custom_forms_path.exists():
            mapped_forms = json.loads(custom_forms_path.read_text(encoding="utf-8"))
            existing_names = {
                json.loads(row["payload"]).get("name")
                for row in connection.execute(
                    "SELECT payload FROM records WHERE resource = 'forms'"
                )
            }
            now = utc_now()
            for mapped_form in mapped_forms:
                if mapped_form.get("name") in existing_names:
                    continue
                payload = {
                    "name": mapped_form.get("name", "Mapped form"),
                    "assigned_sites": "",
                    "assigned_roles": "",
                    "status": "Draft",
                    "definition": {"sections": mapped_form.get("sections", [])},
                    "source": "sanitized production example",
                }
                connection.execute(
                    """
                    INSERT INTO records(resource, payload, created_at, updated_at)
                    VALUES ('forms', ?, ?, ?)
                    """,
                    (json.dumps(payload), now, now),
                )

        inductions_path = EXAMPLES_ROOT / "inductions.json"
        if inductions_path.exists():
            mapped_catalog = json.loads(inductions_path.read_text(encoding="utf-8"))
            existing_titles = {
                json.loads(row["payload"]).get("title")
                for row in connection.execute(
                    "SELECT payload FROM records WHERE resource = 'inductions'"
                )
            }
            now = utc_now()
            for mapped_induction in mapped_catalog.get("inductions", []):
                if mapped_induction.get("title") in existing_titles:
                    continue
                page_map: dict[int, list[dict]] = {}
                for page in mapped_catalog.get("shared_content_pages", []):
                    blocks = page.get("blocks", [page])
                    page_map[page["index"]] = [
                        {
                            "type": "text",
                            "text": block.get("heading", ""),
                            "mapped_character_count": block.get("character_count", 0),
                            "embedded_image_count": block.get(
                                "embedded_image_count", 0
                            ),
                        }
                        for block in blocks
                    ]
                for page in mapped_induction.get("site_pages", []):
                    page_map[page["index"]] = [
                        {
                            "type": "text",
                            "text": page.get("heading", ""),
                            "mapped_character_count": page.get(
                                "character_count", 0
                            ),
                            "embedded_image_count": page.get(
                                "embedded_image_count", 0
                            ),
                        }
                    ]
                questions = mapped_catalog.get("shared_questions", [])
                if mapped_induction.get("question_layout", "").startswith("three"):
                    page_map[13] = [
                        {
                            **question,
                            "type": "question",
                            "question_type": question.get(
                                "type", "single_choice"
                            ),
                        }
                        for question in questions
                    ]
                else:
                    for question_index, question in enumerate(questions):
                        page_map[13 + question_index] = [
                            {
                                **question,
                                "type": "question",
                                "question_type": question.get(
                                    "type", "single_choice"
                                ),
                            }
                        ]
                pages = [
                    {"index": index, "blocks": blocks}
                    for index, blocks in sorted(page_map.items())
                ]
                payload = {
                    "title": mapped_induction.get("title", "Mapped induction"),
                    "site": mapped_induction.get("site", ""),
                    "submissions": 0,
                    "status": "Draft",
                    "pages": {"pages": pages},
                    "source": "sanitized production example",
                }
                connection.execute(
                    """
                    INSERT INTO records(resource, payload, created_at, updated_at)
                    VALUES ('inductions', ?, ?, ?)
                    """,
                    (json.dumps(payload), now, now),
                )

        archived_hsa_resources = {
            "ga2": "ga2",
            "ga3": "ga3",
            "ga3_scaffold": "ga3-scaffold",
            "af3": "af3",
            "handover": "handover",
            "ga2_manual": "ga2-manual",
            "ga3_manual": "ga3-manual",
        }
        for resource, folder in archived_hsa_resources.items():
            existing = connection.execute(
                "SELECT COUNT(*) FROM records WHERE resource = ?",
                (resource,),
            ).fetchone()[0]
            archive_folder = ARCHIVE_ROOT / f"pdfs-{folder}"
            if existing or not archive_folder.exists():
                continue
            now = utc_now()
            rows = []
            for pdf_path in sorted(archive_folder.glob("*.pdf")):
                payload = {
                    "subcontractor": "",
                    "site": "",
                    "worker": "",
                    "worker_email": "",
                    "submitted_date": "",
                    "archive_path": pdf_path.relative_to(
                        ARCHIVE_ROOT
                    ).as_posix(),
                    "source": "authorized production archive",
                }
                rows.append((resource, json.dumps(payload), now, now))
            connection.executemany(
                """
                INSERT INTO records(resource, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                rows,
            )

        existing_documents = connection.execute(
            "SELECT COUNT(*) FROM records WHERE resource = 'documents'"
        ).fetchone()[0]
        shared_documents_folder = ARCHIVE_ROOT / "shared-documents"
        if not existing_documents and shared_documents_folder.exists():
            now = utc_now()
            rows = []
            for document_path in sorted(shared_documents_folder.iterdir()):
                if not document_path.is_file():
                    continue
                payload = {
                    "title": document_path.stem,
                    "file_name": document_path.name,
                    "type": document_path.suffix.lstrip(".").upper(),
                    "subcontractor": "",
                    "archive_path": document_path.relative_to(
                        ARCHIVE_ROOT
                    ).as_posix(),
                    "source": "authorized production archive",
                }
                rows.append(("documents", json.dumps(payload), now, now))
            connection.executemany(
                """
                INSERT INTO records(resource, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                rows,
            )
        connection.commit()


def row_to_record(row: sqlite3.Row) -> dict:
    payload = json.loads(row["payload"])
    return {
        "id": row["id"],
        **payload,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def clean_resource(value: str) -> str:
    return "".join(
        character
        for character in value.lower().replace("-", "_")
        if character.isalnum() or character == "_"
    )


class KomplianceHandler(BaseHTTPRequestHandler):
    server_version = "KomplianceLocal/0.1"

    def log_message(self, format_string: str, *args) -> None:
        print(
            f"[{self.log_date_time_string()}] "
            f"{self.address_string()} {format_string % args}"
        )

    def send_json(self, payload, status=HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path: Path, cache=False) -> None:
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        allowed_roots = (
            STATIC_ROOT.resolve(),
            ARCHIVE_ROOT.resolve(),
            EXAMPLES_ROOT.resolve(),
        )
        if not any(resolved == root or root in resolved.parents for root in allowed_roots):
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        stat = resolved.stat()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(stat.st_size))
        self.send_header(
            "Cache-Control",
            "public, max-age=3600" if cache else "no-store",
        )
        self.end_headers()
        with resolved.open("rb") as handle:
            while chunk := handle.read(256 * 1024):
                self.wfile.write(chunk)

    def read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        if length > MAX_BODY_BYTES:
            raise ValueError("Request body exceeds 10 MB")
        raw = self.rfile.read(length)
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("JSON body must be an object")
        return value

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/api/health":
            self.send_json({"ok": True, "service": "kompliance-local"})
            return
        if path == "/api/dashboard":
            self.handle_dashboard()
            return
        if path == "/api/archive":
            self.handle_archive(parsed.query)
            return
        if path.startswith("/api/resources/"):
            self.handle_resource_get(path, parsed.query)
            return
        if path.startswith("/archive/"):
            relative = path.removeprefix("/archive/")
            self.send_file(ARCHIVE_ROOT / relative)
            return
        if path.startswith("/examples/"):
            relative = path.removeprefix("/examples/")
            self.send_file(EXAMPLES_ROOT / relative)
            return
        if path.startswith("/static/"):
            relative = path.removeprefix("/static/")
            self.send_file(STATIC_ROOT / relative, cache=True)
            return
        if path in {"/favicon.ico", "/favicon.svg"}:
            self.send_file(STATIC_ROOT / "favicon.svg", cache=True)
            return

        self.send_file(STATIC_ROOT / "index.html")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/resources/"):
            self.handle_resource_create(parsed.path)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_PUT(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/resources/"):
            self.handle_resource_update(parsed.path)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/resources/"):
            self.handle_resource_delete(parsed.path)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def handle_dashboard(self) -> None:
        resources = [
            "sites",
            "workers",
            "subcontractors",
            "forms",
            "ga2",
            "ga3",
            "ga3_scaffold",
            "af3",
            "handover",
            "ga2_manual",
            "ga3_manual",
            "ga1",
            "risk_assessment",
            "inductions",
        ]
        with DB_LOCK, connect_database() as connection:
            counts = {
                resource: connection.execute(
                    "SELECT COUNT(*) FROM records WHERE resource = ?",
                    (resource,),
                ).fetchone()[0]
                for resource in resources
            }
            pending_workers = connection.execute(
                """
                SELECT payload FROM records
                WHERE resource = 'workers'
                """
            ).fetchall()
        counts["unapproved_workers"] = sum(
            1
            for row in pending_workers
            if json.loads(row["payload"]).get("status") == "Pending"
        )
        archive_categories = {
            "ga2": "ga2",
            "ga3": "ga3",
            "ga3_scaffold": "ga3-scaffold",
            "af3": "af3",
            "handover": "handover",
            "ga2_manual": "ga2-manual",
            "ga3_manual": "ga3-manual",
        }
        for resource, folder in archive_categories.items():
            archive_folder = ARCHIVE_ROOT / f"pdfs-{folder}"
            if archive_folder.exists():
                counts[resource] = sum(
                    1 for item in archive_folder.glob("*.pdf") if item.is_file()
                )
        self.send_json(counts)

    def handle_resource_get(self, path: str, query: str) -> None:
        tail = path.removeprefix("/api/resources/").strip("/")
        parts = tail.split("/") if tail else []
        if not parts:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        resource = clean_resource(parts[0])
        record_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None

        with DB_LOCK, connect_database() as connection:
            if record_id is not None:
                row = connection.execute(
                    "SELECT * FROM records WHERE resource = ? AND id = ?",
                    (resource, record_id),
                ).fetchone()
                if row is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self.send_json(row_to_record(row))
                return

            params = parse_qs(query)
            search = params.get("q", [""])[0].strip().lower()
            limit = min(max(int(params.get("limit", ["100"])[0]), 1), 5000)
            offset = max(int(params.get("offset", ["0"])[0]), 0)
            rows = connection.execute(
                """
                SELECT * FROM records
                WHERE resource = ?
                ORDER BY id DESC
                """,
                (resource,),
            ).fetchall()
        records = [row_to_record(row) for row in rows]
        if search:
            records = [
                record
                for record in records
                if search in json.dumps(record, ensure_ascii=False).lower()
            ]
        total = len(records)
        self.send_json(
            {
                "resource": resource,
                "total": total,
                "data": records[offset : offset + limit],
            }
        )

    def handle_resource_create(self, path: str) -> None:
        resource = clean_resource(
            path.removeprefix("/api/resources/").strip("/").split("/")[0]
        )
        if not resource:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        payload.pop("id", None)
        payload.pop("created_at", None)
        payload.pop("updated_at", None)
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            cursor = connection.execute(
                """
                INSERT INTO records(resource, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (resource, json.dumps(payload), now, now),
            )
            connection.commit()
            record_id = cursor.lastrowid
        self.send_json(
            {
                "id": record_id,
                **payload,
                "created_at": now,
                "updated_at": now,
            },
            HTTPStatus.CREATED,
        )

    def handle_resource_update(self, path: str) -> None:
        tail = path.removeprefix("/api/resources/").strip("/")
        parts = tail.split("/")
        if len(parts) != 2 or not parts[1].isdigit():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        resource = clean_resource(parts[0])
        record_id = int(parts[1])
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        payload.pop("id", None)
        payload.pop("created_at", None)
        payload.pop("updated_at", None)
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            cursor = connection.execute(
                """
                UPDATE records
                SET payload = ?, updated_at = ?
                WHERE resource = ? AND id = ?
                """,
                (json.dumps(payload), now, resource, record_id),
            )
            connection.commit()
        if cursor.rowcount == 0:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_json({"id": record_id, **payload, "updated_at": now})

    def handle_resource_delete(self, path: str) -> None:
        tail = path.removeprefix("/api/resources/").strip("/")
        parts = tail.split("/")
        if len(parts) != 2 or not parts[1].isdigit():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        resource = clean_resource(parts[0])
        record_id = int(parts[1])
        with DB_LOCK, connect_database() as connection:
            cursor = connection.execute(
                "DELETE FROM records WHERE resource = ? AND id = ?",
                (resource, record_id),
            )
            connection.commit()
        if cursor.rowcount == 0:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_json({"deleted": True, "id": record_id})

    def handle_archive(self, query: str) -> None:
        params = parse_qs(query)
        category = params.get("category", [""])[0].strip().replace("\\", "/")
        search = params.get("q", [""])[0].strip().lower()
        limit = min(max(int(params.get("limit", ["200"])[0]), 1), 5000)
        if not ARCHIVE_ROOT.exists():
            self.send_json({"total": 0, "data": [], "ready": False})
            return
        root = (ARCHIVE_ROOT / category).resolve() if category else ARCHIVE_ROOT.resolve()
        if ARCHIVE_ROOT.resolve() not in (root, *root.parents):
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        files = []
        if root.exists():
            for file_path in root.rglob("*"):
                if not file_path.is_file() or file_path.suffix == ".part":
                    continue
                relative = file_path.relative_to(ARCHIVE_ROOT).as_posix()
                if search and search not in relative.lower():
                    continue
                files.append(
                    {
                        "name": file_path.name,
                        "path": relative,
                        "size": file_path.stat().st_size,
                        "type": file_path.suffix.lower().lstrip("."),
                    }
                )
        files.sort(key=lambda item: item["path"])
        self.send_json(
            {
                "ready": True,
                "total": len(files),
                "data": files[:limit],
            }
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    initialize_database()
    server = ThreadingHTTPServer((args.host, args.port), KomplianceHandler)
    print(f"Kompliance Local running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
