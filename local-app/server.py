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
import html
import json
import mimetypes
import os
import secrets
import sqlite3
import threading
import textwrap
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import qrcode


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
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCK_MINUTES = 15
RESET_TOKEN_MINUTES = 30


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
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                locked_until TEXT,
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
        user_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(users)").fetchall()
        }
        if "failed_attempts" not in user_columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN failed_attempts INTEGER NOT NULL DEFAULT 0"
            )
        if "locked_until" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN locked_until TEXT")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT NOT NULL,
                created_by INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_reset_tokens_user ON password_reset_tokens(user_id)"
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


def parse_record_date(value):
    text = str(value or "").strip()
    if not text or text in {"-", "—"}:
        return None
    formats = (
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    )
    normalized = text.replace("Z", "+00:00")
    for value_format in formats:
        try:
            return datetime.strptime(normalized, value_format).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(normalized).date()
    except ValueError:
        return None


def local_record(connection, resource: str, record_id: int):
    row = connection.execute(
        "SELECT * FROM records WHERE resource = ? AND id = ?", (resource, record_id)
    ).fetchone()
    if row is None:
        return None
    record = row_to_record(row)
    if record.get("_read_only") or not record.get("local_only"):
        return None
    return record


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


def pdf_escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def assemble_pdf(objects: list[str]) -> bytes:
    objects = [
        str(item) for item in objects
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


def build_text_pdf(title: str, subtitle: str, lines: list[str]) -> bytes:
    wrapped = []
    for line in lines:
        chunks = textwrap.wrap(str(line), width=88, replace_whitespace=True) or [""]
        wrapped.extend(chunks)
    page_chunks = [wrapped[index : index + 44] for index in range(0, len(wrapped), 44)] or [[]]
    page_count = len(page_chunks)
    normal_font = 3 + page_count * 2
    bold_font = normal_font + 1
    page_refs = " ".join(f"{3 + index * 2} 0 R" for index in range(page_count))
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{page_refs}] /Count {page_count} >>",
    ]
    for page_index, page_lines in enumerate(page_chunks):
        content_ref = 4 + page_index * 2
        commands = [
            "0.04 0.38 0.30 rg 0 790 595 52 re f",
            f"BT /F2 18 Tf 42 811 Td ({pdf_escape(title)}) Tj ET",
            "0 0 0 rg",
            f"BT /F1 9 Tf 42 774 Td ({pdf_escape(subtitle)}) Tj ET",
        ]
        y = 748
        for line in page_lines:
            commands.append(f"BT /F1 9 Tf 42 {y} Td ({pdf_escape(line)}) Tj ET")
            y -= 15
        commands.append(
            f"BT /F1 8 Tf 500 24 Td (Page {page_index + 1} of {page_count}) Tj ET"
        )
        stream = "\n".join(commands)
        objects.extend(
            [
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 {normal_font} 0 R /F2 {bold_font} 0 R >> >> /Contents {content_ref} 0 R >>",
                f"<< /Length {len(stream.encode('latin-1', 'replace'))} >>\nstream\n{stream}\nendstream",
            ]
        )
    objects.extend(
        [
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        ]
    )
    return assemble_pdf(objects)


def build_certificate_pdf(
    company: str,
    worker: str,
    induction: str,
    site: str,
    completed_at: str,
    expires_at: str,
    certificate_number: str,
    verification_url: str,
) -> bytes:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=1)
    qr.add_data(verification_url)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    module_size = min(3.2, 122 / max(len(matrix), 1))
    qr_x = 414
    qr_y = 530
    qr_commands = ["0 0 0 rg"]
    for row_index, row in enumerate(matrix):
        for column_index, active in enumerate(row):
            if active:
                x = qr_x + column_index * module_size
                y = qr_y + (len(matrix) - row_index - 1) * module_size
                qr_commands.append(f"{x:.2f} {y:.2f} {module_size:.2f} {module_size:.2f} re f")
    lines = [
        ("F2", 24, 64, 742, "INDUCTION CERTIFICATE"),
        ("F1", 11, 64, 710, company),
        ("F1", 11, 64, 663, "This certifies that"),
        ("F2", 21, 64, 628, worker),
        ("F1", 11, 64, 591, "has completed the following site induction:"),
        ("F2", 15, 64, 562, induction),
        ("F1", 10, 64, 530, f"Site: {site or 'Not specified'}"),
        ("F1", 10, 64, 510, f"Completed: {completed_at}"),
        ("F1", 10, 64, 490, f"Valid until: {expires_at}"),
        ("F2", 10, 64, 438, f"Certificate: {certificate_number}"),
        ("F1", 8, 64, 410, "Verify this certificate using the QR code or address below:"),
        ("F1", 7, 64, 392, verification_url),
        ("F1", 8, 64, 62, "Generated by the controlled Kompliance workflow. Status must be checked online."),
    ]
    commands = [
        "0.04 0.38 0.30 rg 0 780 595 62 re f",
        "1 1 1 rg",
        "BT /F2 13 Tf 64 804 Td (KOMPLIANCE) Tj ET",
        "0 0 0 rg",
    ]
    commands.extend(
        f"BT /{font} {size} Tf {x} {y} Td ({pdf_escape(text)}) Tj ET"
        for font, size, x, y, text in lines
    )
    commands.extend(qr_commands)
    stream = "\n".join(commands)
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(stream.encode('latin-1', 'replace'))} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
    ]
    return assemble_pdf(objects)


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

    def send_html(self, markup: str, status=HTTPStatus.OK) -> None:
        body = markup.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
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

    def application_base_url(self) -> str:
        forwarded_host = self.headers.get("X-Forwarded-Host", "").split(",")[0].strip()
        host = forwarded_host or self.headers.get("Host", "127.0.0.1:8090")
        forwarded_proto = self.headers.get("X-Forwarded-Proto", "").split(",")[0].strip()
        scheme = forwarded_proto or "http"
        return f"{scheme}://{host}"

    def issue_password_reset(self, user_row, created_by=None):
        raw_token = secrets.token_urlsafe(32)
        token_digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        created_at = utc_now()
        expires_at = (
            datetime.now(UTC) + timedelta(minutes=RESET_TOKEN_MINUTES)
        ).replace(microsecond=0).isoformat()
        reset_url = f"{self.application_base_url()}/reset-password?token={raw_token}"
        notification_payload = {
            "kind": "password_reset",
            "recipient": user_row["email"],
            "subject": "Kompliance password reset",
            "reset_url": reset_url,
            "status": "Prepared - not sent",
            "expires_at": expires_at,
            "source": "local controlled workspace",
            "local_only": True,
        }
        with DB_LOCK, connect_database() as connection:
            connection.execute(
                "DELETE FROM password_reset_tokens WHERE user_id = ? AND used_at IS NULL",
                (user_row["id"],),
            )
            connection.execute(
                """
                INSERT INTO password_reset_tokens(token_hash, user_id, expires_at, used_at, created_at, created_by)
                VALUES (?, ?, ?, NULL, ?, ?)
                """,
                (token_digest, user_row["id"], expires_at, created_at, created_by),
            )
            cursor = connection.execute(
                "INSERT INTO records(resource, payload, created_at, updated_at) VALUES ('local_notifications', ?, ?, ?)",
                (json.dumps(notification_payload), created_at, created_at),
            )
            connection.commit()
        return reset_url, expires_at, cursor.lastrowid

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
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            row = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            locked = bool(row and row["locked_until"] and row["locked_until"] > now)
            valid = bool(
                row
                and row["active"]
                and not locked
                and password_matches(password, row["password_hash"])
            )
            if row and not valid and row["active"] and not locked:
                failures = int(row["failed_attempts"] or 0) + 1
                locked_until = None
                if failures >= LOGIN_MAX_ATTEMPTS:
                    locked_until = (
                        datetime.now(UTC) + timedelta(minutes=LOGIN_LOCK_MINUTES)
                    ).replace(microsecond=0).isoformat()
                connection.execute(
                    "UPDATE users SET failed_attempts = ?, locked_until = ?, updated_at = ? WHERE id = ?",
                    (failures, locked_until, now, row["id"]),
                )
                connection.commit()
            elif valid:
                connection.execute(
                    "UPDATE users SET failed_attempts = 0, locked_until = NULL, updated_at = ? WHERE id = ?",
                    (now, row["id"]),
                )
                connection.commit()
        if locked:
            self.write_audit(None, "login_locked", "auth", summary=f"Locked account login for {email[:180]}")
            self.send_json(
                {"error": "Account temporarily locked after repeated failed sign-in attempts."},
                HTTPStatus.TOO_MANY_REQUESTS,
            )
            return
        if not valid:
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
            connection.execute("DELETE FROM sessions WHERE user_id = ?", (user["id"],))
            connection.commit()
        csrf_token, cookie = self.create_session(user["id"])
        self.write_audit(user, "password_changed", "auth", summary="Password changed")
        self.send_json({"updated": True, "csrf_token": csrf_token}, headers={"Set-Cookie": cookie})

    def handle_auth_recovery_request(self) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        email = str(payload.get("email", "")).strip().lower()
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                "SELECT id, email, name FROM users WHERE email = ? AND active = 1", (email,)
            ).fetchone()
        if row:
            self.issue_password_reset(row)
            self.write_audit(None, "password_reset_requested", "auth", summary=f"Reset prepared for {email[:180]}")
        else:
            self.write_audit(None, "password_reset_requested", "auth", summary="Reset requested for unknown account")
        self.send_json(
            {"accepted": True, "message": "If the account exists, a reset message has been prepared for secure delivery."},
            HTTPStatus.ACCEPTED,
        )

    def handle_auth_recovery_reset(self) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        token = str(payload.get("token", "")).strip()
        new_password = str(payload.get("password", ""))
        if not token or len(new_password) < 12:
            self.send_json({"error": "A valid token and 12-character password are required."}, HTTPStatus.BAD_REQUEST)
            return
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                """
                SELECT password_reset_tokens.user_id, users.email, users.active
                FROM password_reset_tokens JOIN users ON users.id = password_reset_tokens.user_id
                WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?
                """,
                (digest, now),
            ).fetchone()
            if row is None or not row["active"]:
                self.send_json({"error": "This reset link is invalid or has expired."}, HTTPStatus.BAD_REQUEST)
                return
            connection.execute(
                "UPDATE users SET password_hash = ?, failed_attempts = 0, locked_until = NULL, updated_at = ? WHERE id = ?",
                (password_hash(new_password), now, row["user_id"]),
            )
            connection.execute(
                "UPDATE password_reset_tokens SET used_at = ? WHERE token_hash = ?", (now, digest)
            )
            connection.execute("DELETE FROM sessions WHERE user_id = ?", (row["user_id"],))
            connection.commit()
        self.write_audit(
            {"id": row["user_id"], "email": row["email"]},
            "password_reset_completed",
            "auth",
            summary="Password reset completed; sessions revoked",
        )
        self.send_json({"reset": True})

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
                """
                SELECT users.id, users.email, users.name, users.role, users.active,
                       users.failed_attempts, users.locked_until, users.created_at, users.updated_at,
                       COUNT(sessions.token_hash) AS session_count
                FROM users LEFT JOIN sessions ON sessions.user_id = users.id
                GROUP BY users.id ORDER BY users.name
                """
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

    def handle_user_update(self, user, user_id: int) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        name = str(payload.get("name", "")).strip()
        role = str(payload.get("role", "")).strip().lower()
        active = 1 if payload.get("active") in {True, 1, "1", "true", "on"} else 0
        if not name or role not in {"viewer", "editor", "admin"}:
            self.send_json({"error": "A valid name and role are required."}, HTTPStatus.BAD_REQUEST)
            return
        if user_id == user["id"] and (not active or role != "admin"):
            self.send_json({"error": "You cannot disable or demote your own administrator account."}, HTTPStatus.BAD_REQUEST)
            return
        with DB_LOCK, connect_database() as connection:
            existing = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if existing is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            active_admins = connection.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin' AND active = 1"
            ).fetchone()[0]
            if existing["role"] == "admin" and existing["active"] and (role != "admin" or not active) and active_admins <= 1:
                self.send_json({"error": "The final active administrator cannot be disabled or demoted."}, HTTPStatus.BAD_REQUEST)
                return
            now = utc_now()
            connection.execute(
                "UPDATE users SET name = ?, role = ?, active = ?, updated_at = ? WHERE id = ?",
                (name, role, active, now, user_id),
            )
            if not active or role != existing["role"]:
                connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            connection.commit()
        self.write_audit(user, "user_updated", "users", user_id, f"Account set to {role}; active={active}")
        self.send_json({"id": user_id, "name": name, "role": role, "active": active})

    def handle_user_revoke_sessions(self, user, user_id: int) -> None:
        with DB_LOCK, connect_database() as connection:
            target = connection.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
            if target is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            cursor = connection.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            connection.commit()
        self.write_audit(user, "sessions_revoked", "users", user_id, f"Revoked {cursor.rowcount} session(s) for {target['email']}")
        self.send_json({"revoked": cursor.rowcount})

    def handle_user_reset_link(self, user, user_id: int) -> None:
        with DB_LOCK, connect_database() as connection:
            target = connection.execute(
                "SELECT id, email, name FROM users WHERE id = ? AND active = 1", (user_id,)
            ).fetchone()
        if target is None:
            self.send_json({"error": "Active account not found."}, HTTPStatus.NOT_FOUND)
            return
        reset_url, expires_at, notification_id = self.issue_password_reset(target, user["id"])
        self.write_audit(user, "password_reset_issued", "users", user_id, f"Reset link prepared for {target['email']}")
        self.send_json(
            {"reset_url": reset_url, "expires_at": expires_at, "notification_id": notification_id},
            HTTPStatus.CREATED,
        )

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

    def handle_local_evidence(self, user) -> None:
        original_name = Path(unquote(self.headers.get("X-File-Name", "evidence.bin"))).name
        distribution_id = str(self.headers.get("X-Distribution-Id", "")).strip()
        extension = Path(original_name).suffix.lower()
        allowed = {".pdf", ".csv", ".xlsx", ".xls", ".docx", ".doc", ".png", ".jpg", ".jpeg"}
        if not distribution_id.isdigit() or extension not in allowed:
            self.send_json({"error": "A local assignment and allowed evidence file are required."}, HTTPStatus.BAD_REQUEST)
            return
        try:
            content = self.read_raw_body()
        except ValueError as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        with DB_LOCK, connect_database() as connection:
            distribution = local_record(connection, "distributions", int(distribution_id))
        if distribution is None:
            self.send_json({"error": "Local assignment not found."}, HTTPStatus.NOT_FOUND)
            return
        evidence_root = DATA_ROOT / "evidence"
        evidence_root.mkdir(parents=True, exist_ok=True)
        stored_name = f"evidence-{secrets.token_hex(12)}{extension}"
        (evidence_root / stored_name).write_bytes(content)
        now = utc_now()
        payload = {
            "distribution_id": int(distribution_id),
            "worker": distribution.get("worker", ""),
            "form": distribution.get("form", ""),
            "original_name": original_name,
            "stored_name": stored_name,
            "content_type": self.headers.get("Content-Type", "application/octet-stream"),
            "size": len(content),
            "source": "local controlled workspace",
            "local_only": True,
        }
        with DB_LOCK, connect_database() as connection:
            cursor = connection.execute(
                "INSERT INTO records(resource, payload, created_at, updated_at) VALUES ('local_evidence', ?, ?, ?)",
                (json.dumps(payload), now, now),
            )
            connection.commit()
        self.write_audit(user, "evidence_uploaded", "local_evidence", cursor.lastrowid, f"Evidence attached to assignment {distribution_id}")
        self.send_json(
            {"id": cursor.lastrowid, **payload, "url": f"/local-files/evidence/{stored_name}"},
            HTTPStatus.CREATED,
        )

    def form_definition_for_assignment(self, connection, distribution):
        rows = connection.execute("SELECT * FROM records WHERE resource = 'forms'").fetchall()
        wanted = str(distribution.get("form", "")).strip().casefold()
        for row in rows:
            record = row_to_record(row)
            if str(record.get("name", "")).strip().casefold() == wanted:
                return record
        return None

    def handle_local_submission(self, user) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        distribution_id = payload.get("distribution_id")
        status = str(payload.get("status", "draft")).strip().lower()
        answers = payload.get("answers", [])
        attachment_ids = payload.get("attachment_ids", [])
        submission_id = payload.get("submission_id")
        if not str(distribution_id).isdigit() or status not in {"draft", "submitted"} or not isinstance(answers, list):
            self.send_json({"error": "A local assignment, valid status, and answer list are required."}, HTTPStatus.BAD_REQUEST)
            return
        with DB_LOCK, connect_database() as connection:
            distribution = local_record(connection, "distributions", int(distribution_id))
            if distribution is None:
                self.send_json({"error": "Local assignment not found."}, HTTPStatus.NOT_FOUND)
                return
            form_record = self.form_definition_for_assignment(connection, distribution)
            if form_record is None:
                self.send_json({"error": "The assignment form definition is unavailable."}, HTTPStatus.CONFLICT)
                return
            expected = {}
            for section_index, section in enumerate(form_record.get("definition", {}).get("sections", [])):
                for question_index, question in enumerate(section.get("questions", [])):
                    key = f"s{section_index}q{question_index}"
                    expected[key] = {
                        "key": key,
                        "section": section.get("name", ""),
                        "question": question.get("text", ""),
                        "type": question.get("type", "Textbox"),
                    }
            supplied = {str(answer.get("key", "")): answer for answer in answers if isinstance(answer, dict)}
            normalized_answers = []
            missing = []
            for key, definition in expected.items():
                value = supplied.get(key, {}).get("value", "")
                if isinstance(value, str):
                    value = value.strip()
                if definition["type"] == "Sign" and value and not str(value).startswith("data:image/png;base64,"):
                    self.send_json({"error": f"Signature for '{definition['question']}' is invalid."}, HTTPStatus.BAD_REQUEST)
                    return
                if status == "submitted" and (value is None or value == "" or value == []):
                    missing.append(definition["question"])
                normalized_answers.append({**definition, "value": value})
            if missing:
                self.send_json(
                    {"error": "Complete every required field before submitting.", "missing": missing[:20]},
                    HTTPStatus.BAD_REQUEST,
                )
                return
            safe_attachment_ids = [int(item) for item in attachment_ids if str(item).isdigit()]
            evidence = []
            if safe_attachment_ids:
                placeholders = ",".join("?" for _ in safe_attachment_ids)
                rows = connection.execute(
                    f"SELECT * FROM records WHERE resource = 'local_evidence' AND id IN ({placeholders})",
                    safe_attachment_ids,
                ).fetchall()
                evidence = [
                    row_to_record(row)
                    for row in rows
                    if row_to_record(row).get("distribution_id") == int(distribution_id)
                ]
            now = utc_now()
            record_payload = {
                "distribution_id": int(distribution_id),
                "worker": distribution.get("worker", ""),
                "form": distribution.get("form", ""),
                "site": distribution.get("sites", ""),
                "status": "Submitted" if status == "submitted" else "Draft",
                "answers": normalized_answers,
                "attachments": [
                    {"id": item["id"], "original_name": item.get("original_name", ""), "stored_name": item.get("stored_name", "")}
                    for item in evidence
                ],
                "updated_by": user["email"],
                "source": "local controlled workspace",
                "local_only": True,
            }
            if status == "submitted":
                record_payload["submitted_at"] = now
                report_root = DATA_ROOT / "reports"
                report_root.mkdir(parents=True, exist_ok=True)
                report_name = f"submission-{secrets.token_hex(12)}.pdf"
                report_lines = [
                    f"Worker: {record_payload['worker']}",
                    f"Site: {record_payload['site']}",
                    f"Status: Submitted at {now}",
                    "",
                ]
                for answer in normalized_answers:
                    value = "[Captured signature]" if answer["type"] == "Sign" and answer["value"] else answer["value"]
                    report_lines.extend([f"{answer['section']} / {answer['question']}", f"Answer: {value}", ""])
                if evidence:
                    report_lines.append("Attachments: " + ", ".join(item.get("original_name", "") for item in evidence))
                (report_root / report_name).write_bytes(
                    build_text_pdf(record_payload["form"], "Controlled local form submission", report_lines)
                )
                record_payload["report_file"] = report_name
            existing = None
            if str(submission_id).isdigit():
                existing = local_record(connection, "local_submissions", int(submission_id))
                if existing and existing.get("distribution_id") != int(distribution_id):
                    existing = None
            if existing:
                record_id = int(submission_id)
                connection.execute(
                    "UPDATE records SET payload = ?, updated_at = ? WHERE resource = 'local_submissions' AND id = ?",
                    (json.dumps(record_payload), now, record_id),
                )
            else:
                cursor = connection.execute(
                    "INSERT INTO records(resource, payload, created_at, updated_at) VALUES ('local_submissions', ?, ?, ?)",
                    (json.dumps(record_payload), now, now),
                )
                record_id = cursor.lastrowid
            if status == "submitted":
                distribution_payload = {key: value for key, value in distribution.items() if key not in {"id", "_read_only", "created_at", "updated_at"}}
                distribution_payload.update({"status": "Submitted", "submitted_date": now[:10], "submission_id": record_id})
                connection.execute(
                    "UPDATE records SET payload = ?, updated_at = ? WHERE resource = 'distributions' AND id = ?",
                    (json.dumps(distribution_payload), now, int(distribution_id)),
                )
            connection.commit()
        action = "submission_finalized" if status == "submitted" else "submission_draft_saved"
        self.write_audit(user, action, "local_submissions", record_id, f"{record_payload['form']} for {record_payload['worker']}")
        self.send_json(
            {
                "id": record_id,
                **record_payload,
                "report_url": f"/local-files/reports/{record_payload['report_file']}" if record_payload.get("report_file") else None,
            },
            HTTPStatus.CREATED if not existing else HTTPStatus.OK,
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
        company = str(payload.get("company", "Kompliance Client Company")).strip()[:120]
        validity_days = min(max(int(payload.get("validity_days", 365)), 1), 3650)
        replaces_id = payload.get("replaces_id")
        if not worker or not induction:
            self.send_json({"error": "Worker and induction are required."}, HTTPStatus.BAD_REQUEST)
            return
        completed_at = utc_now()
        expires_at = (datetime.now(UTC) + timedelta(days=validity_days)).date().isoformat()
        certificate_number = f"KMP-{datetime.now(UTC):%Y%m%d}-{secrets.token_hex(4).upper()}"
        verification_token = secrets.token_urlsafe(18)
        verification_url = f"{self.application_base_url()}/verify/{verification_token}"
        certificate_root = DATA_ROOT / "certificates"
        certificate_root.mkdir(parents=True, exist_ok=True)
        stored_name = f"induction-{secrets.token_hex(12)}.pdf"
        pdf = build_certificate_pdf(
            company,
            worker,
            induction,
            site,
            completed_at,
            expires_at,
            certificate_number,
            verification_url,
        )
        (certificate_root / stored_name).write_bytes(pdf)
        record_payload = {
            "worker": worker,
            "induction": induction,
            "site": site,
            "completed_at": completed_at,
            "expires_at": expires_at,
            "company": company,
            "certificate_number": certificate_number,
            "verification_token": verification_token,
            "verification_url": verification_url,
            "status": "Active",
            "replaces_id": int(replaces_id) if str(replaces_id).isdigit() else None,
            "certificate_file": stored_name,
            "source": "local controlled workspace",
            "local_only": True,
        }
        with DB_LOCK, connect_database() as connection:
            cursor = connection.execute(
                "INSERT INTO records(resource, payload, created_at, updated_at) VALUES ('local_induction_completions', ?, ?, ?)",
                (json.dumps(record_payload), completed_at, completed_at),
            )
            record_id = cursor.lastrowid
            if str(replaces_id).isdigit():
                previous = local_record(connection, "local_induction_completions", int(replaces_id))
                if previous:
                    previous_payload = {key: value for key, value in previous.items() if key not in {"id", "_read_only", "created_at", "updated_at"}}
                    previous_payload.update({"status": "Replaced", "replaced_by": record_id, "replaced_at": completed_at})
                    connection.execute(
                        "UPDATE records SET payload = ?, updated_at = ? WHERE resource = 'local_induction_completions' AND id = ?",
                        (json.dumps(previous_payload), completed_at, int(replaces_id)),
                    )
            connection.commit()
        self.write_audit(user, "certificate_generated", "local_induction_completions", record_id, f"Certificate generated for {worker}")
        self.send_json(
            {"id": record_id, **record_payload, "url": f"/local-files/certificates/{stored_name}"},
            HTTPStatus.CREATED,
        )

    def handle_local_certificate_revoke(self, user, record_id: int) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        reason = str(payload.get("reason", "")).strip()
        if not reason:
            self.send_json({"error": "A revocation reason is required."}, HTTPStatus.BAD_REQUEST)
            return
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            record = local_record(connection, "local_induction_completions", record_id)
            if record is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if record.get("status") != "Active":
                self.send_json({"error": "Only an active certificate can be revoked."}, HTTPStatus.CONFLICT)
                return
            updated = {key: value for key, value in record.items() if key not in {"id", "_read_only", "created_at", "updated_at"}}
            updated.update({"status": "Revoked", "revoked_at": now, "revocation_reason": reason})
            connection.execute(
                "UPDATE records SET payload = ?, updated_at = ? WHERE resource = 'local_induction_completions' AND id = ?",
                (json.dumps(updated), now, record_id),
            )
            connection.commit()
        self.write_audit(user, "certificate_revoked", "local_induction_completions", record_id, reason)
        self.send_json({"id": record_id, **updated})

    def compliance_reminder_data(self, days: int):
        today = datetime.now(UTC).date()
        cutoff = today + timedelta(days=days)
        definitions = (
            ("workers", "safe_pass_expiry", "Safe Pass", "name"),
            ("ga1", "expiry_date", "GA1 document set", "worker"),
            ("risk_assessment", "expiry_date", "Risk assessment", "title"),
            ("local_induction_completions", "expires_at", "Induction certificate", "worker"),
        )
        items = []
        missing_dates = 0
        with DB_LOCK, connect_database() as connection:
            for resource, date_field, category, subject_field in definitions:
                rows = connection.execute(
                    "SELECT * FROM records WHERE resource = ? ORDER BY id DESC", (resource,)
                ).fetchall()
                for row in rows:
                    record = row_to_record(row)
                    if resource == "local_induction_completions" and record.get("status") in {"Revoked", "Replaced"}:
                        continue
                    due = parse_record_date(record.get(date_field))
                    if due is None:
                        missing_dates += 1
                        continue
                    if due < today:
                        state = "Overdue"
                    elif due <= cutoff:
                        state = "Due soon"
                    else:
                        state = "Current"
                    items.append(
                        {
                            "resource": resource,
                            "record_id": record["id"],
                            "category": category,
                            "subject": record.get(subject_field) or record.get("name") or record.get("title") or f"Record {record['id']}",
                            "site": record.get("site") or record.get("sites") or "",
                            "due_date": due.isoformat(),
                            "days_remaining": (due - today).days,
                            "state": state,
                        }
                    )
        order = {"Overdue": 0, "Due soon": 1, "Current": 2}
        items.sort(key=lambda item: (order[item["state"]], item["due_date"], str(item["subject"]).casefold()))
        return {
            "days": days,
            "generated_at": utc_now(),
            "counts": {
                "overdue": sum(item["state"] == "Overdue" for item in items),
                "due_soon": sum(item["state"] == "Due soon" for item in items),
                "current": sum(item["state"] == "Current" for item in items),
                "missing_date": missing_dates,
            },
            "data": items,
        }

    def handle_compliance_reminders(self, query: str) -> None:
        params = parse_qs(query)
        try:
            days = min(max(int(params.get("days", ["30"])[0]), 1), 365)
        except ValueError:
            days = 30
        self.send_json(self.compliance_reminder_data(days))

    def handle_compliance_prepare(self, user) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        days = min(max(int(payload.get("days", 30)), 1), 365)
        reminder_data = self.compliance_reminder_data(days)
        due_items = [item for item in reminder_data["data"] if item["state"] in {"Overdue", "Due soon"}]
        now = utc_now()
        created = []
        with DB_LOCK, connect_database() as connection:
            for item in due_items:
                notification = {
                    "kind": "compliance_reminder",
                    "channel": "Email",
                    "recipient": "To be assigned",
                    "subject": f"{item['category']} {item['state'].lower()}: {item['subject']}",
                    "message": f"{item['category']} for {item['subject']} is {item['state'].lower()} with due date {item['due_date']}.",
                    "related_resource": item["resource"],
                    "related_record_id": item["record_id"],
                    "status": "Prepared - not sent",
                    "source": "local controlled workspace",
                    "local_only": True,
                }
                cursor = connection.execute(
                    "INSERT INTO records(resource, payload, created_at, updated_at) VALUES ('local_notifications', ?, ?, ?)",
                    (json.dumps(notification), now, now),
                )
                created.append(cursor.lastrowid)
            connection.commit()
        self.write_audit(user, "notifications_prepared", "local_notifications", summary=f"Prepared {len(created)} compliance reminder(s); none sent")
        self.send_json({"created": len(created), "ids": created, "sent": 0}, HTTPStatus.CREATED)

    def handle_public_certificate(self, token: str) -> None:
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute(
                "SELECT * FROM records WHERE resource = 'local_induction_completions' ORDER BY id DESC"
            ).fetchall()
        certificate = next(
            (row_to_record(row) for row in rows if row_to_record(row).get("verification_token") == token),
            None,
        )
        if certificate is None:
            self.send_html(
                "<!doctype html><html><head><title>Certificate not found</title></head><body style='font-family:system-ui;padding:3rem'><h1>Certificate not found</h1><p>This verification address is invalid.</p></body></html>",
                HTTPStatus.NOT_FOUND,
            )
            return
        status = certificate.get("status", "Active")
        expiry = parse_record_date(certificate.get("expires_at"))
        if status == "Active" and expiry and expiry < datetime.now(UTC).date():
            status = "Expired"
        safe = {key: html.escape(str(certificate.get(key, ""))) for key in ("certificate_number", "company", "worker", "induction", "site", "completed_at", "expires_at")}
        colour = "#0f8b6d" if status == "Active" else "#c2414b"
        markup = f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Certificate verification</title></head>
        <body style='margin:0;background:#f3f7f6;font-family:system-ui;color:#17324a'><main style='max-width:680px;margin:8vh auto;background:white;border-radius:18px;padding:2rem;box-shadow:0 20px 60px #17324a20'>
        <div style='color:#0f6f5b;font-weight:800;letter-spacing:.08em'>KOMPLIANCE</div><h1>Certificate verification</h1>
        <p style='display:inline-block;background:{colour};color:white;border-radius:999px;padding:.45rem .85rem;font-weight:700'>{html.escape(status)}</p>
        <dl style='display:grid;grid-template-columns:10rem 1fr;gap:.8rem;border-top:1px solid #dce7e4;padding-top:1.5rem'>
        <dt>Certificate</dt><dd>{safe['certificate_number']}</dd><dt>Company</dt><dd>{safe['company']}</dd><dt>Worker</dt><dd>{safe['worker']}</dd><dt>Induction</dt><dd>{safe['induction']}</dd><dt>Site</dt><dd>{safe['site']}</dd><dt>Completed</dt><dd>{safe['completed_at']}</dd><dt>Valid until</dt><dd>{safe['expires_at']}</dd></dl>
        <p style='color:#61758a'>Always rely on the status shown on this page, not a downloaded copy.</p></main></body></html>"""
        self.send_html(markup)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/api/health":
            self.send_json({"ok": True, "service": "kompliance-local"})
            return
        if path == "/api/auth/status":
            self.handle_auth_status()
            return
        if path.startswith("/verify/"):
            token = path.removeprefix("/verify/").strip("/")
            self.handle_public_certificate(token)
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
        if path == "/api/compliance/reminders":
            self.handle_compliance_reminders(parsed.query)
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
            if len(parts) != 2 or parts[0] not in {"uploads", "certificates", "evidence", "reports"}:
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
        if parsed.path == "/api/auth/recovery/request":
            self.handle_auth_recovery_request()
            return
        if parsed.path == "/api/auth/recovery/reset":
            self.handle_auth_recovery_reset()
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
        user_match = parsed.path.strip("/").split("/")
        if len(user_match) == 4 and user_match[:2] == ["api", "users"] and user_match[2].isdigit():
            if user.get("role") != "admin":
                self.send_json({"error": "Administrator role required."}, HTTPStatus.FORBIDDEN)
                return
            if user_match[3] == "revoke-sessions":
                self.handle_user_revoke_sessions(user, int(user_match[2]))
                return
            if user_match[3] == "reset-link":
                self.handle_user_reset_link(user, int(user_match[2]))
                return
        if parsed.path == "/api/local/upload":
            self.handle_local_upload(user)
            return
        if parsed.path == "/api/local/evidence":
            self.handle_local_evidence(user)
            return
        if parsed.path == "/api/local/submission":
            self.handle_local_submission(user)
            return
        if parsed.path == "/api/local/certificate":
            self.handle_local_certificate(user)
            return
        certificate_match = parsed.path.strip("/").split("/")
        if (
            len(certificate_match) == 5
            and certificate_match[:3] == ["api", "local", "certificate"]
            and certificate_match[3].isdigit()
            and certificate_match[4] == "revoke"
        ):
            if user.get("role") != "admin":
                self.send_json({"error": "Administrator role required."}, HTTPStatus.FORBIDDEN)
                return
            self.handle_local_certificate_revoke(user, int(certificate_match[3]))
            return
        if parsed.path == "/api/compliance/notifications/prepare":
            self.handle_compliance_prepare(user)
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
        user_match = parsed.path.strip("/").split("/")
        if len(user_match) == 3 and user_match[:2] == ["api", "users"] and user_match[2].isdigit():
            if user.get("role") != "admin":
                self.send_json({"error": "Administrator role required."}, HTTPStatus.FORBIDDEN)
                return
            self.handle_user_update(user, int(user_match[2]))
            return
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
