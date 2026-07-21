#!/usr/bin/env python3
"""Local Kompliance recreation server.

Uses only the Python standard library so the project runs on the current
machine without npm, Composer, or third-party Python packages.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


APP_ROOT = Path(__file__).resolve().parent
STATIC_ROOT = APP_ROOT / "static"
DATA_ROOT = Path(os.environ.get("KOMPLIANCE_DATA_ROOT", APP_ROOT / "data"))
DATABASE_PATH = DATA_ROOT / "kompliance.db"
ARCHIVE_ROOT = APP_ROOT.parent / "source-archive"
EXAMPLES_ROOT = APP_ROOT.parent / "examples"
PRODUCTION_DATA_PATH = APP_ROOT.parent / "production-data" / "records.json"
MAX_BODY_BYTES = 10 * 1024 * 1024
DB_LOCK = threading.RLock()
PROTECTED_RECORD_SOURCE = "production read-only export"
AUTH_ENABLED = os.environ.get("KOMPLIANCE_APP_AUTH", "0").strip() == "1"
SESSION_COOKIE = "kompliance_session"
SESSION_HOURS = 12
PASSWORD_ITERATIONS = 310_000


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


def is_protected_payload(payload: dict) -> bool:
    """Identify records imported from the immutable production snapshot."""
    return str(payload.get("source", "")).strip().casefold() == (
        PROTECTED_RECORD_SOURCE.casefold()
    )


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
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('viewer', 'editor', 'admin')),
                password_hash TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                csrf_token TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                resource TEXT NOT NULL,
                record_id INTEGER,
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL
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
        "_read_only": is_protected_payload(payload),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }

def attach_archive_documents(resource: str, record: dict) -> dict:
    if resource != "ga1":
        return record
    source_id = record.get("source_id")
    if not source_id:
        return record
    archive_folder = ARCHIVE_ROOT / f"documents-ga1-{source_id}"
    if not archive_folder.exists():
        return record
    files = sorted(
        (item for item in archive_folder.iterdir() if item.is_file()),
        key=lambda item: (item.suffix.lower() != ".pdf", item.name.lower()),
    )
    archive_paths = [
        item.relative_to(ARCHIVE_ROOT).as_posix()
        for item in files
    ]
    if archive_paths:
        record["archive_paths"] = archive_paths
        record["archive_path"] = archive_paths[0]
        record["document_count"] = len(archive_paths)
    return record


def clean_resource(value: str) -> str:
    return "".join(
        character
        for character in value.lower().replace("-", "_")
        if character.isalnum() or character == "_"
    )


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return "$".join(
        (
            "pbkdf2-sha256",
            str(PASSWORD_ITERATIONS),
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(digest).decode("ascii"),
        )
    )


def password_matches(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "pbkdf2-sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_text.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_text.encode("ascii"))
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def build_certificate_pdf(title: str, worker: str, induction: str, completed_at: str) -> bytes:
    def pdf_text(value: str) -> str:
        return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    lines = [
        (18, 760, title),
        (12, 718, "This certifies that"),
        (16, 686, worker),
        (12, 646, "completed the following site induction:"),
        (14, 614, induction),
        (11, 570, f"Completion recorded: {completed_at}"),
        (9, 520, "Generated by the local Kompliance controlled workflow."),
    ]
    stream = "\n".join(
        f"BT /F1 {size} Tf 72 {y} Td ({pdf_text(text)}) Tj ET"
        for size, y, text in lines
    )
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(stream.encode('latin-1', 'replace'))} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, item in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n{item}\nendobj\n".encode("latin-1", "replace"))
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)


class KomplianceHandler(BaseHTTPRequestHandler):
    server_version = "KomplianceLocal/0.1"

    def log_message(self, format_string: str, *args) -> None:
        print(
            f"[{self.log_date_time_string()}] "
            f"{self.address_string()} {format_string % args}"
        )

    def send_json(self, payload, status=HTTPStatus.OK, headers=None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
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

    def send_local_file(self, folder: str, filename: str) -> None:
        root = (DATA_ROOT / folder).resolve()
        try:
            resolved = (root / Path(filename).name).resolve(strict=True)
        except FileNotFoundError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if root not in resolved.parents:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        stat = resolved.stat()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(stat.st_size))
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("Content-Disposition", f'inline; filename="{resolved.name}"')
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

    def read_raw_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            raise ValueError("File content is required")
        if length > MAX_BODY_BYTES:
            raise ValueError("File exceeds the 10 MB limit")
        return self.rfile.read(length)

    def session_token(self) -> str:
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get("Cookie", ""))
        except Exception:
            return ""
        morsel = cookies.get(SESSION_COOKIE)
        return morsel.value if morsel else ""

    def current_user(self):
        if not AUTH_ENABLED:
            return {
                "id": 0,
                "email": "local@kompliance.test",
                "name": "Local Administrator",
                "role": "admin",
                "csrf_token": "",
            }
        token = self.session_token()
        if not token:
            return None
        token_digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                """
                SELECT users.id, users.email, users.name, users.role,
                       sessions.csrf_token, sessions.expires_at
                FROM sessions JOIN users ON users.id = sessions.user_id
                WHERE sessions.token_hash = ? AND sessions.expires_at > ?
                  AND users.active = 1
                """,
                (token_digest, now),
            ).fetchone()
        return dict(row) if row else None

    def require_user(self, roles=None):
        user = self.current_user()
        if user is None:
            self.send_json({"error": "Authentication required."}, HTTPStatus.UNAUTHORIZED)
            return None
        if roles and user.get("role") not in roles:
            self.send_json({"error": "Your role does not permit this action."}, HTTPStatus.FORBIDDEN)
            return None
        return user

    def require_csrf(self, user) -> bool:
        if not AUTH_ENABLED:
            return True
        supplied = self.headers.get("X-CSRF-Token", "")
        if supplied and hmac.compare_digest(supplied, user.get("csrf_token", "")):
            return True
        self.send_json({"error": "Invalid or missing CSRF token."}, HTTPStatus.FORBIDDEN)
        return False

    def write_audit(self, user, action, resource, record_id=None, summary="") -> None:
        actor = user.get("email", "system") if user else "anonymous"
        user_id = user.get("id") if user and user.get("id") else None
        with DB_LOCK, connect_database() as connection:
            connection.execute(
                """
                INSERT INTO audit_log(user_id, actor, action, resource, record_id, summary, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, actor, action, resource, record_id, summary[:500], utc_now()),
            )
            connection.commit()

    def create_session(self, user_id: int):
        raw_token = secrets.token_urlsafe(32)
        token_digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        csrf_token = secrets.token_urlsafe(24)
        created_at = utc_now()
        expires_at = (datetime.now(UTC) + timedelta(hours=SESSION_HOURS)).replace(
            microsecond=0
        ).isoformat()
        with DB_LOCK, connect_database() as connection:
            connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (created_at,))
            connection.execute(
                """
                INSERT INTO sessions(token_hash, user_id, csrf_token, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (token_digest, user_id, csrf_token, expires_at, created_at),
            )
            connection.commit()
        cookie = (
            f"{SESSION_COOKIE}={raw_token}; Path=/; HttpOnly; SameSite=Lax; "
            f"Max-Age={SESSION_HOURS * 3600}"
        )
        if self.headers.get("X-Forwarded-Proto", "").lower() == "https":
            cookie += "; Secure"
        return csrf_token, cookie

    def handle_auth_status(self) -> None:
        if not AUTH_ENABLED:
            self.send_json(
                {
                    "enabled": False,
                    "setup_required": False,
                    "authenticated": True,
                    "user": {
                        "name": "Local Administrator",
                        "email": "local@kompliance.test",
                        "role": "admin",
                    },
                    "csrf_token": "",
                }
            )
            return
        with DB_LOCK, connect_database() as connection:
            setup_required = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        user = self.current_user()
        self.send_json(
            {
                "enabled": True,
                "setup_required": setup_required,
                "authenticated": user is not None,
                "user": ({key: user[key] for key in ("name", "email", "role")} if user else None),
                "csrf_token": user.get("csrf_token", "") if user else "",
            }
        )

    def handle_auth_setup(self) -> None:
        if not AUTH_ENABLED:
            self.send_json({"error": "Application authentication is disabled."}, HTTPStatus.CONFLICT)
            return
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        email = str(payload.get("email", "")).strip().lower()
        name = str(payload.get("name", "")).strip()
        password = str(payload.get("password", ""))
        if "@" not in email or not name or len(password) < 12:
            self.send_json(
                {"error": "Name, valid email, and a password of at least 12 characters are required."},
                HTTPStatus.BAD_REQUEST,
            )
            return
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            if connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
                self.send_json({"error": "Initial administrator already exists."}, HTTPStatus.CONFLICT)
                return
            cursor = connection.execute(
                """
                INSERT INTO users(email, name, role, password_hash, active, created_at, updated_at)
                VALUES (?, ?, 'admin', ?, 1, ?, ?)
                """,
                (email, name, password_hash(password), now, now),
            )
            connection.commit()
            user_id = cursor.lastrowid
        csrf_token, cookie = self.create_session(user_id)
        user = {"id": user_id, "email": email, "name": name, "role": "admin"}
        self.write_audit(user, "setup", "auth", summary="Initial administrator created")
        self.send_json(
            {"authenticated": True, "user": {key: user[key] for key in ("name", "email", "role")}, "csrf_token": csrf_token},
            HTTPStatus.CREATED,
            {"Set-Cookie": cookie},
        )

    def handle_auth_login(self) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE email = ? AND active = 1", (email,)
            ).fetchone()
        if row is None or not password_matches(password, row["password_hash"]):
            self.write_audit(None, "login_failed", "auth", summary=f"Failed login for {email[:180]}")
            self.send_json({"error": "Invalid email or password."}, HTTPStatus.UNAUTHORIZED)
            return
        csrf_token, cookie = self.create_session(row["id"])
        user = dict(row)
        self.write_audit(user, "login", "auth", summary="Successful login")
        self.send_json(
            {"authenticated": True, "user": {key: user[key] for key in ("name", "email", "role")}, "csrf_token": csrf_token},
            headers={"Set-Cookie": cookie},
        )

    def handle_auth_logout(self) -> None:
        user = self.require_user()
        if user is None or not self.require_csrf(user):
            return
        token = self.session_token()
        if token:
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
            with DB_LOCK, connect_database() as connection:
                connection.execute("DELETE FROM sessions WHERE token_hash = ?", (digest,))
                connection.commit()
        self.write_audit(user, "logout", "auth", summary="Session ended")
        self.send_json(
            {"logged_out": True},
            headers={"Set-Cookie": f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"},
        )

    def handle_auth_password(self) -> None:
        user = self.require_user()
        if user is None or not self.require_csrf(user):
            return
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        current = str(payload.get("current", ""))
        new_password = str(payload.get("new", ""))
        if len(new_password) < 12:
            self.send_json({"error": "New password must be at least 12 characters."}, HTTPStatus.BAD_REQUEST)
            return
        with DB_LOCK, connect_database() as connection:
            row = connection.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
            if row is None or not password_matches(current, row["password_hash"]):
                self.send_json({"error": "Current password is incorrect."}, HTTPStatus.FORBIDDEN)
                return
            connection.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (password_hash(new_password), utc_now(), user["id"]),
            )
            connection.commit()
        self.write_audit(user, "password_changed", "auth", summary="Password changed")
        self.send_json({"updated": True})

    def handle_audit(self, query: str) -> None:
        user = self.require_user({"admin"})
        if user is None:
            return
        params = parse_qs(query)
        limit = min(max(int(params.get("limit", ["100"])[0]), 1), 500)
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        self.send_json({"data": [dict(row) for row in rows], "total": len(rows)})

    def handle_users_get(self) -> None:
        if self.require_user({"admin"}) is None:
            return
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute(
                "SELECT id, email, name, role, active, created_at, updated_at FROM users ORDER BY name"
            ).fetchall()
        self.send_json({"data": [dict(row) for row in rows]})

    def handle_users_create(self, user) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        email = str(payload.get("email", "")).strip().lower()
        name = str(payload.get("name", "")).strip()
        role = str(payload.get("role", "viewer")).strip().lower()
        password = str(payload.get("password", ""))
        if "@" not in email or not name or role not in {"viewer", "editor", "admin"} or len(password) < 12:
            self.send_json({"error": "Valid name, email, role and 12-character password are required."}, HTTPStatus.BAD_REQUEST)
            return
        now = utc_now()
        try:
            with DB_LOCK, connect_database() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO users(email, name, role, password_hash, active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?)
                    """,
                    (email, name, role, password_hash(password), now, now),
                )
                connection.commit()
                record_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            self.send_json({"error": "An account with this email already exists."}, HTTPStatus.CONFLICT)
            return
        self.write_audit(user, "user_created", "users", record_id, f"Created {role} account for {email}")
        self.send_json({"id": record_id, "email": email, "name": name, "role": role, "active": 1}, HTTPStatus.CREATED)

    def handle_local_upload(self, user) -> None:
        title = unquote(self.headers.get("X-Upload-Title", "")).strip()
        original_name = Path(unquote(self.headers.get("X-File-Name", "upload.bin"))).name
        extension = Path(original_name).suffix.lower()
        allowed = {".pdf", ".csv", ".xlsx", ".xls", ".docx", ".doc", ".png", ".jpg", ".jpeg"}
        if not title or extension not in allowed:
            self.send_json({"error": "A title and an allowed PDF, office, CSV or image file are required."}, HTTPStatus.BAD_REQUEST)
            return
        try:
            content = self.read_raw_body()
        except ValueError as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        upload_root = DATA_ROOT / "uploads"
        upload_root.mkdir(parents=True, exist_ok=True)
        stored_name = f"{secrets.token_hex(12)}{extension}"
        (upload_root / stored_name).write_bytes(content)
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            existing_rows = connection.execute(
                "SELECT payload FROM records WHERE resource = 'local_uploads'"
            ).fetchall()
            version = 1 + sum(
                1
                for row in existing_rows
                if json.loads(row["payload"]).get("title", "").casefold() == title.casefold()
            )
            payload = {
                "title": title,
                "original_name": original_name,
                "stored_name": stored_name,
                "content_type": self.headers.get("Content-Type", "application/octet-stream"),
                "size": len(content),
                "version": version,
                "source": "local controlled workspace",
                "local_only": True,
            }
            cursor = connection.execute(
                "INSERT INTO records(resource, payload, created_at, updated_at) VALUES ('local_uploads', ?, ?, ?)",
                (json.dumps(payload), now, now),
            )
            connection.commit()
            record_id = cursor.lastrowid
        self.write_audit(user, "upload", "local_uploads", record_id, f"Uploaded {original_name} as version {version}")
        self.send_json(
            {"id": record_id, **payload, "url": f"/local-files/uploads/{stored_name}", "created_at": now},
            HTTPStatus.CREATED,
        )

    def handle_local_certificate(self, user) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        worker = str(payload.get("worker", "")).strip()
        induction = str(payload.get("induction", "")).strip()
        site = str(payload.get("site", "")).strip()
        if not worker or not induction:
            self.send_json({"error": "Worker and induction are required."}, HTTPStatus.BAD_REQUEST)
            return
        completed_at = utc_now()
        certificate_root = DATA_ROOT / "certificates"
        certificate_root.mkdir(parents=True, exist_ok=True)
        stored_name = f"induction-{secrets.token_hex(12)}.pdf"
        pdf = build_certificate_pdf("Induction Completion Certificate", worker, induction, completed_at)
        (certificate_root / stored_name).write_bytes(pdf)
        record_payload = {
            "worker": worker,
            "induction": induction,
            "site": site,
            "completed_at": completed_at,
            "certificate_file": stored_name,
            "source": "local controlled workspace",
            "local_only": True,
        }
        with DB_LOCK, connect_database() as connection:
            cursor = connection.execute(
                "INSERT INTO records(resource, payload, created_at, updated_at) VALUES ('local_induction_completions', ?, ?, ?)",
                (json.dumps(record_payload), completed_at, completed_at),
            )
            connection.commit()
            record_id = cursor.lastrowid
        self.write_audit(user, "certificate_generated", "local_induction_completions", record_id, f"Certificate generated for {worker}")
        self.send_json(
            {"id": record_id, **record_payload, "url": f"/local-files/certificates/{stored_name}"},
            HTTPStatus.CREATED,
        )

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/api/health":
            self.send_json({"ok": True, "service": "kompliance-local"})
            return
        if path == "/api/auth/status":
            self.handle_auth_status()
            return
        if path.startswith("/static/"):
            relative = path.removeprefix("/static/")
            self.send_file(STATIC_ROOT / relative, cache=True)
            return
        if path in {"/favicon.ico", "/favicon.svg"}:
            self.send_file(STATIC_ROOT / "favicon.svg", cache=True)
            return
        if path.startswith("/api/") or path.startswith("/archive/") or path.startswith("/examples/") or path.startswith("/local-files/"):
            if self.require_user() is None:
                return
        if path == "/api/audit":
            self.handle_audit(parsed.query)
            return
        if path == "/api/users":
            self.handle_users_get()
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
        if path.startswith("/local-files/"):
            parts = path.removeprefix("/local-files/").split("/", 1)
            if len(parts) != 2 or parts[0] not in {"uploads", "certificates"}:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self.send_local_file(parts[0], parts[1])
            return
        self.send_file(STATIC_ROOT / "index.html")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/auth/setup":
            self.handle_auth_setup()
            return
        if parsed.path == "/api/auth/login":
            self.handle_auth_login()
            return
        if parsed.path == "/api/auth/logout":
            self.handle_auth_logout()
            return
        if parsed.path == "/api/auth/password":
            self.handle_auth_password()
            return
        user = self.require_user({"editor", "admin"})
        if user is None or not self.require_csrf(user):
            return
        self.request_user = user
        if parsed.path == "/api/users":
            if user.get("role") != "admin":
                self.send_json({"error": "Administrator role required."}, HTTPStatus.FORBIDDEN)
                return
            self.handle_users_create(user)
            return
        if parsed.path == "/api/local/upload":
            self.handle_local_upload(user)
            return
        if parsed.path == "/api/local/certificate":
            self.handle_local_certificate(user)
            return
        if parsed.path.startswith("/api/resources/"):
            self.handle_resource_create(parsed.path)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_PUT(self) -> None:
        parsed = urlparse(self.path)
        user = self.require_user({"editor", "admin"})
        if user is None or not self.require_csrf(user):
            return
        self.request_user = user
        if parsed.path.startswith("/api/resources/"):
            self.handle_resource_update(parsed.path)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        user = self.require_user({"admin"})
        if user is None or not self.require_csrf(user):
            return
        self.request_user = user
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
                self.send_json(attach_archive_documents(resource, row_to_record(row)))
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
        records = [
            attach_archive_documents(resource, row_to_record(row))
            for row in rows
        ]
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
        payload.pop("_read_only", None)
        payload.pop("created_at", None)
        payload.pop("updated_at", None)
        if is_protected_payload(payload):
            self.send_json(
                {"error": "The protected production source marker cannot be assigned."},
                HTTPStatus.BAD_REQUEST,
            )
            return
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
                "_read_only": False,
                "created_at": now,
                "updated_at": now,
            },
            HTTPStatus.CREATED,
        )
        self.write_audit(
            getattr(self, "request_user", None),
            "create",
            resource,
            record_id,
            "Local record created",
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
        payload.pop("_read_only", None)
        payload.pop("created_at", None)
        payload.pop("updated_at", None)
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            existing = connection.execute(
                "SELECT payload FROM records WHERE resource = ? AND id = ?",
                (resource, record_id),
            ).fetchone()
            if existing is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if is_protected_payload(json.loads(existing["payload"])):
                self.send_json(
                    {
                        "error": (
                            "This record came from the protected production snapshot "
                            "and cannot be edited."
                        )
                    },
                    HTTPStatus.FORBIDDEN,
                )
                return
            cursor = connection.execute(
                """
                UPDATE records
                SET payload = ?, updated_at = ?
                WHERE resource = ? AND id = ?
                """,
                (json.dumps(payload), now, resource, record_id),
            )
            connection.commit()
        self.send_json(
            {"id": record_id, **payload, "_read_only": False, "updated_at": now}
        )
        self.write_audit(
            getattr(self, "request_user", None),
            "update",
            resource,
            record_id,
            "Local record updated",
        )

    def handle_resource_delete(self, path: str) -> None:
        tail = path.removeprefix("/api/resources/").strip("/")
        parts = tail.split("/")
        if len(parts) != 2 or not parts[1].isdigit():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        resource = clean_resource(parts[0])
        record_id = int(parts[1])
        with DB_LOCK, connect_database() as connection:
            existing = connection.execute(
                "SELECT payload FROM records WHERE resource = ? AND id = ?",
                (resource, record_id),
            ).fetchone()
            if existing is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if is_protected_payload(json.loads(existing["payload"])):
                self.send_json(
                    {
                        "error": (
                            "This record came from the protected production snapshot "
                            "and cannot be deleted."
                        )
                    },
                    HTTPStatus.FORBIDDEN,
                )
                return
            cursor = connection.execute(
                "DELETE FROM records WHERE resource = ? AND id = ?",
                (resource, record_id),
            )
            connection.commit()
        self.send_json({"deleted": True, "id": record_id})
        self.write_audit(
            getattr(self, "request_user", None),
            "delete",
            resource,
            record_id,
            "Local record deleted",
        )

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
