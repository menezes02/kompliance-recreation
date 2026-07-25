#!/usr/bin/env python3
"""Local Kompliance recreation server with isolated writable workflows."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import hmac
import html
import io
import json
import mimetypes
import os
import re
import secrets
import shutil
import smtplib
import sqlite3
import threading
import textwrap
import time
import zipfile
from base64 import urlsafe_b64encode
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from functools import lru_cache
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from io import BytesIO
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import qrcode


APP_ROOT = Path(__file__).resolve().parent
STATIC_ROOT = APP_ROOT / "static"
DATA_ROOT = Path(os.environ.get("KOMPLIANCE_DATA_ROOT", APP_ROOT / "data"))
DATABASE_PATH = DATA_ROOT / "kompliance.db"
ARCHIVE_ROOT = APP_ROOT.parent / "source-archive"
EXAMPLES_ROOT = APP_ROOT.parent / "examples"
PRODUCTION_DATA_PATH = APP_ROOT.parent / "production-data" / "records.json"
INDUCTION_REGISTRATION_SCHEMA_PATH = EXAMPLES_ROOT / "induction-registration.json"
MAX_BODY_BYTES = 10 * 1024 * 1024
DB_LOCK = threading.RLock()
PROTECTED_RECORD_SOURCE = "production read-only export"
AUTH_ENABLED = os.environ.get("KOMPLIANCE_APP_AUTH", "0").strip() == "1"
SESSION_COOKIE = "kompliance_session"
WORKER_SESSION_COOKIE = "kompliance_worker_session"
SESSION_HOURS = 12
WORKER_SESSION_HOURS = 24 * 7
PASSWORD_ITERATIONS = 310_000
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCK_MINUTES = 15
LOGIN_LOCKOUT_ENABLED = (
    os.environ.get("KOMPLIANCE_LOGIN_LOCKOUT_ENABLED", "1").strip() == "1"
)
RESET_TOKEN_MINUTES = 30
RECOVERY_MAX_ATTEMPTS = 3
RECOVERY_WINDOW_MINUTES = 15
MFA_PERIOD_SECONDS = 30
MFA_DIGITS = 6
MFA_BACKUP_CODE_COUNT = 10
API_RATE_LIMIT_PER_MINUTE = max(int(os.environ.get("KOMPLIANCE_API_RATE_LIMIT_PER_MINUTE", "120")), 10)
PUBLIC_INDUCTION_MAX_ATTEMPTS = 20
PUBLIC_INDUCTION_WINDOW_MINUTES = 10
STARTED_AT = utc_now() if "utc_now" in globals() else datetime.now(UTC).replace(microsecond=0).isoformat()
SCHEDULER_STOP = threading.Event()
GMAIL_OAUTH_LOCK = threading.Lock()
GMAIL_OAUTH_CACHE = {"access_token": "", "expires_at": 0.0}
GMAIL_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GMAIL_SEND_ENDPOINT = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
SCHEDULER_STATE = {
    "enabled": os.environ.get("KOMPLIANCE_SCHEDULER", "0").strip() == "1",
    "running": False,
    "last_run_at": "",
    "last_error": "",
}

DEFAULT_SETTINGS = {
    "brand_name": "Kompliance",
    "brand_company": "Kingscroft Developments",
    "brand_tagline": "Health & Safety Operations",
    "company_email": "",
    "company_phone": "",
    "company_address": "",
    "privacy_contact": "",
    "compliance_recipient": "",
    "reminder_days": "30",
    "retention_days": "365",
}

PILOT_REVIEW_CHECKLIST = (
    ("ga_search_filters", "GA1, GA2 and GA3 search, filters and date range"),
    ("archived_pdf_view", "Archived PDF browser view and download"),
    ("role_boundaries", "Viewer, Editor and Administrator role boundaries"),
    ("local_form_workflow", "Local form draft, signature, submission and PDF report"),
    ("worker_consent", "Worker QR access request, approval and revocation"),
    ("responsive_layout", "Desktop and mobile review paths"),
    ("email_delivery", "Controlled application email delivery"),
    ("backup_restore", "Backup verification and restore rehearsal"),
)

WORKER_DOCUMENT_CATEGORIES = {
    "GA1", "GA2", "GA3", "AF3", "RAMS", "Induction", "Certification",
    "Licence", "Medical Certificate", "Training", "Other",
}
WORKER_SHARE_FIELDS = {
    "name", "email", "phone", "trade", "skills", "qualifications", "certifications",
    "training_records", "inductions", "employment_history", "documents",
}
WORKFLOW_DEPARTMENTS = {"Safety", "HR", "Plant", "Training", "Administration"}
WORKFLOW_REQUEST_TYPES = {
    "New Inspection", "Certificate Renewal", "Approval", "Missing Documents",
    "Additional Information", "Equipment Inspection", "Plant Inspection", "Other",
}
WORKFLOW_STATUSES = {"open", "in_progress", "awaiting_information", "resolved", "closed"}
INDUCTION_REVIEW_STATUSES = {"pending", "approved", "declined", "information_requested"}
SUPPORTED_LANGUAGES = {"en-IE", "pl-PL", "ro-RO", "pt-BR", "uk-UA", "ru-RU", "es-ES"}
LANGUAGE_ALIASES = {
    "en": "en-IE", "pt": "pt-BR", "es": "es-ES", "pl": "pl-PL",
    "ro": "ro-RO", "uk": "uk-UA", "ru": "ru-RU",
}


@lru_cache(maxsize=1)
def induction_registration_schema() -> dict:
    if not INDUCTION_REGISTRATION_SCHEMA_PATH.exists():
        return {}
    return json.loads(INDUCTION_REGISTRATION_SCHEMA_PATH.read_text(encoding="utf-8"))


def ensure_induction_site_links(connection, company_id: int) -> None:
    schema = induction_registration_schema()
    site_ids = {
        str(site.get("name", "")).strip().casefold(): str(site.get("id", ""))
        for site in schema.get("sites", [])
    }
    rows = connection.execute(
        "SELECT id, payload FROM records WHERE resource = 'inductions' AND company_id = ?",
        (company_id,),
    ).fetchall()
    now = utc_now()
    for row in rows:
        payload = json.loads(row["payload"])
        site_name = str(payload.get("site", "")).strip()
        if not site_name:
            continue
        site_source_id = site_ids.get(site_name.casefold(), "")
        connection.execute(
            """
            INSERT INTO induction_site_links(
                company_id, induction_record_id, site_source_id, site_name,
                public_token, active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(company_id, site_name) DO UPDATE SET
                induction_record_id = excluded.induction_record_id,
                site_source_id = excluded.site_source_id,
                updated_at = excluded.updated_at
            """,
            (
                company_id,
                int(row["id"]),
                site_source_id,
                site_name,
                secrets.token_urlsafe(32),
                now,
                now,
            ),
        )


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


def normalize_language(value: object) -> str:
    candidate = str(value or "").strip()
    if candidate in SUPPORTED_LANGUAGES:
        return candidate
    return LANGUAGE_ALIASES.get(candidate, "en-IE")


LANGUAGE_NAMES = {
    "en-IE": "English",
    "pl-PL": "Polski",
    "ro-RO": "Română",
    "pt-BR": "Português (Brasil)",
    "uk-UA": "Українська",
    "ru-RU": "Русский",
    "es-ES": "Español",
}

SERVER_MESSAGES = {
    "en-IE": {
        "verify_subject": "Verify your Kompliance worker account",
        "verify_body": "Verify your worker account within 24 hours: {url}",
        "worker_reset_subject": "Reset your Kompliance worker password",
        "worker_reset_body": "Reset your worker password within {minutes} minutes: {url}",
        "user_reset_subject": "Kompliance password reset",
        "user_reset_body": "Use this secure link within {minutes} minutes to reset your Kompliance password: {url}",
        "compliance_subject": "{category} {state}: {subject}",
        "compliance_body": "{category} for {subject} is {state} with due date {due_date}.",
        "status_changed": "Status changed to {status}. {note}",
        "induction_submitted": "Induction submitted for supervisor review at {site}.",
        "induction_status": "Induction {status}. {comments}",
    },
    "pl-PL": {
        "verify_subject": "Zweryfikuj konto pracownika Kompliance",
        "verify_body": "Zweryfikuj konto pracownika w ciągu 24 godzin: {url}",
        "worker_reset_subject": "Zresetuj hasło pracownika Kompliance",
        "worker_reset_body": "Zresetuj hasło pracownika w ciągu {minutes} minut: {url}",
        "user_reset_subject": "Resetowanie hasła Kompliance",
        "user_reset_body": "Użyj tego bezpiecznego łącza w ciągu {minutes} minut, aby zresetować hasło Kompliance: {url}",
        "compliance_subject": "{category} — {state}: {subject}",
        "compliance_body": "{category} dla {subject}: stan {state}, termin {due_date}.",
        "status_changed": "Status zmieniono na {status}. {note}",
        "induction_submitted": "Instruktaż przesłano do weryfikacji przez przełożonego w lokalizacji {site}.",
        "induction_status": "Instruktaż: {status}. {comments}",
    },
    "ro-RO": {
        "verify_subject": "Verifică-ți contul de lucrător Kompliance",
        "verify_body": "Verifică-ți contul de lucrător în termen de 24 de ore: {url}",
        "worker_reset_subject": "Resetează parola contului de lucrător Kompliance",
        "worker_reset_body": "Resetează parola contului de lucrător în termen de {minutes} minute: {url}",
        "user_reset_subject": "Resetarea parolei Kompliance",
        "user_reset_body": "Folosește acest link securizat în termen de {minutes} minute pentru a reseta parola Kompliance: {url}",
        "compliance_subject": "{category} — {state}: {subject}",
        "compliance_body": "{category} pentru {subject} are starea {state}, cu termenul {due_date}.",
        "status_changed": "Starea a fost schimbată în {status}. {note}",
        "induction_submitted": "Instructajul a fost trimis spre verificare supervizorului la {site}.",
        "induction_status": "Instructaj: {status}. {comments}",
    },
    "pt-BR": {
        "verify_subject": "Verifique sua conta de trabalhador no Kompliance",
        "verify_body": "Verifique sua conta de trabalhador em até 24 horas: {url}",
        "worker_reset_subject": "Redefina a senha da sua conta de trabalhador no Kompliance",
        "worker_reset_body": "Redefina a senha da sua conta de trabalhador em até {minutes} minutos: {url}",
        "user_reset_subject": "Redefinição de senha do Kompliance",
        "user_reset_body": "Use este link seguro em até {minutes} minutos para redefinir sua senha do Kompliance: {url}",
        "compliance_subject": "{category} — {state}: {subject}",
        "compliance_body": "{category} de {subject} está com status {state} e vencimento em {due_date}.",
        "status_changed": "O status foi alterado para {status}. {note}",
        "induction_submitted": "A integração foi enviada para análise do supervisor em {site}.",
        "induction_status": "Integração: {status}. {comments}",
    },
    "uk-UA": {
        "verify_subject": "Підтвердьте обліковий запис працівника Kompliance",
        "verify_body": "Підтвердьте обліковий запис працівника протягом 24 годин: {url}",
        "worker_reset_subject": "Скиньте пароль працівника Kompliance",
        "worker_reset_body": "Скиньте пароль працівника протягом {minutes} хвилин: {url}",
        "user_reset_subject": "Скидання пароля Kompliance",
        "user_reset_body": "Скористайтеся цим захищеним посиланням протягом {minutes} хвилин, щоб скинути пароль Kompliance: {url}",
        "compliance_subject": "{category} — {state}: {subject}",
        "compliance_body": "{category} для {subject}: стан {state}, кінцева дата {due_date}.",
        "status_changed": "Стан змінено на {status}. {note}",
        "induction_submitted": "Інструктаж надіслано керівнику на перевірку на об’єкті {site}.",
        "induction_status": "Інструктаж: {status}. {comments}",
    },
    "ru-RU": {
        "verify_subject": "Подтвердите учётную запись работника Kompliance",
        "verify_body": "Подтвердите учётную запись работника в течение 24 часов: {url}",
        "worker_reset_subject": "Сбросьте пароль работника Kompliance",
        "worker_reset_body": "Сбросьте пароль работника в течение {minutes} минут: {url}",
        "user_reset_subject": "Сброс пароля Kompliance",
        "user_reset_body": "Используйте эту защищённую ссылку в течение {minutes} минут, чтобы сбросить пароль Kompliance: {url}",
        "compliance_subject": "{category} — {state}: {subject}",
        "compliance_body": "{category} для {subject}: состояние {state}, срок {due_date}.",
        "status_changed": "Состояние изменено на {status}. {note}",
        "induction_submitted": "Инструктаж отправлен руководителю на проверку на объекте {site}.",
        "induction_status": "Инструктаж: {status}. {comments}",
    },
    "es-ES": {
        "verify_subject": "Verifica tu cuenta de trabajador de Kompliance",
        "verify_body": "Verifica tu cuenta de trabajador en un plazo de 24 horas: {url}",
        "worker_reset_subject": "Restablece la contraseña de trabajador de Kompliance",
        "worker_reset_body": "Restablece la contraseña de trabajador en un plazo de {minutes} minutos: {url}",
        "user_reset_subject": "Restablecimiento de contraseña de Kompliance",
        "user_reset_body": "Utiliza este enlace seguro en un plazo de {minutes} minutos para restablecer tu contraseña de Kompliance: {url}",
        "compliance_subject": "{category} — {state}: {subject}",
        "compliance_body": "{category} de {subject} está en estado {state}, con fecha límite {due_date}.",
        "status_changed": "El estado cambió a {status}. {note}",
        "induction_submitted": "La inducción se envió al supervisor para su revisión en {site}.",
        "induction_status": "Inducción: {status}. {comments}",
    },
}

SERVER_MESSAGE_SOURCES = {
    key: value for key, value in SERVER_MESSAGES["en-IE"].items()
}

SAFETY_GLOSSARY = (
    ("Kompliance", "Product name; never translate"),
    ("Safe Pass", "Irish construction safety-awareness registration; keep the official name"),
    ("RAMS", "Risk Assessments and Method Statements; keep the acronym"),
    ("GA1", "Irish lifting equipment inspection form; keep the form code"),
    ("GA2", "Irish lifting equipment examination form; keep the form code"),
    ("GA3", "Irish scaffold inspection form; keep the form code"),
    ("AF3", "Irish construction safety form; keep the form code"),
    ("induction", "Site-specific safety onboarding"),
    ("competent person", "A person with the required training, knowledge and experience"),
    ("lifting equipment", "Work equipment used for lifting or lowering loads"),
    ("working at height", "Work where a person could fall and be injured"),
    ("personal protective equipment", "Equipment worn to reduce exposure to hazards"),
    ("near miss", "An event that did not cause harm but had the potential to do so"),
    ("hazard", "A source or situation with potential to cause harm"),
    ("risk assessment", "A structured evaluation of hazards, likelihood and controls"),
)


def server_message(key: str, locale: object = "en-IE", **values) -> str:
    language = normalize_language(locale)
    template = SERVER_MESSAGES.get(language, {}).get(key) or SERVER_MESSAGES["en-IE"][key]
    return template.format(**values).strip()


def reviewed_server_message(
    connection: sqlite3.Connection,
    company_id: int,
    key: str,
    locale: object = "en-IE",
    **values,
) -> str:
    language = normalize_language(locale)
    source = SERVER_MESSAGE_SOURCES[key]
    row = connection.execute(
        """
        SELECT translation FROM translation_reviews
        WHERE company_id = ? AND locale = ? AND source_key = ? AND status = 'approved'
        """,
        (company_id, language, source),
    ).fetchone()
    template = row["translation"] if row else SERVER_MESSAGES.get(language, {}).get(key)
    return str(template or source).format(**values).strip()


@lru_cache(maxsize=1)
def static_translation_catalog() -> dict:
    path = STATIC_ROOT / "i18n-catalog.js"
    try:
        content = path.read_text("utf-8")
        prefix = "window.KomplianceTranslationCatalog = Object.freeze("
        payload = content.split(prefix, 1)[1].rsplit(");", 1)[0]
        catalog = json.loads(payload)
        return catalog if isinstance(catalog, dict) else {}
    except (OSError, ValueError, IndexError, json.JSONDecodeError):
        return {}


def translate_ui(source: object, locale: object = "en-IE") -> str:
    text = str(source)
    language = normalize_language(locale)
    if language == "en-IE":
        return text
    return str(static_translation_catalog().get(language, {}).get(text) or text)


def approved_translation_overrides(
    connection: sqlite3.Connection, company_id: int, locale: object
) -> dict[str, str]:
    language = normalize_language(locale)
    rows = connection.execute(
        """
        SELECT source_key, translation
        FROM translation_reviews
        WHERE company_id = ? AND locale = ? AND status = 'approved'
        """,
        (company_id, language),
    ).fetchall()
    return {row["source_key"]: row["translation"] for row in rows}


def preferred_language_for_owner(
    connection: sqlite3.Connection, owner_type: str, owner_id: int
) -> str:
    row = connection.execute(
        "SELECT preferred_language FROM notification_preferences WHERE owner_type = ? AND owner_id = ?",
        (owner_type, owner_id),
    ).fetchone()
    if row:
        return normalize_language(row["preferred_language"])
    if owner_type == "worker":
        profile_row = connection.execute(
            "SELECT payload FROM worker_profiles WHERE worker_id = ?", (owner_id,)
        ).fetchone()
        if profile_row:
            try:
                return normalize_language(json.loads(profile_row["payload"]).get("preferred_language"))
            except (TypeError, json.JSONDecodeError):
                pass
    return "en-IE"


def preferred_language_for_email(connection: sqlite3.Connection, email: object) -> str:
    address = str(email or "").strip().lower()
    if not address:
        return "en-IE"
    worker = connection.execute(
        "SELECT id FROM worker_accounts WHERE lower(email) = ?", (address,)
    ).fetchone()
    if worker:
        return preferred_language_for_owner(connection, "worker", int(worker["id"]))
    user = connection.execute(
        "SELECT id FROM users WHERE lower(email) = ?", (address,)
    ).fetchone()
    if user:
        return preferred_language_for_owner(connection, "user", int(user["id"]))
    return "en-IE"


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
            """
            CREATE TABLE IF NOT EXISTS rate_limits (
                limit_key TEXT PRIMARY KEY,
                window_started TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0
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
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        now = utc_now()
        connection.execute(
            "INSERT OR IGNORE INTO companies(id, name, slug, active, created_at, updated_at) VALUES (1, ?, 'default-company', 1, ?, ?)",
            (DEFAULT_SETTINGS["brand_company"], now, now),
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS company_settings (
                company_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY(company_id, key),
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
            )"""
        )
        record_columns = {row["name"] for row in connection.execute("PRAGMA table_info(records)").fetchall()}
        if "company_id" not in record_columns:
            connection.execute("ALTER TABLE records ADD COLUMN company_id INTEGER NOT NULL DEFAULT 1")
        if "company_id" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN company_id INTEGER NOT NULL DEFAULT 1")
        if "platform_admin" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN platform_admin INTEGER NOT NULL DEFAULT 0")
        if "mfa_enabled" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN mfa_enabled INTEGER NOT NULL DEFAULT 0")
        if "mfa_secret" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN mfa_secret TEXT")
        if "mfa_pending_secret" not in user_columns:
            connection.execute("ALTER TABLE users ADD COLUMN mfa_pending_secret TEXT")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_mfa_backup_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code_hash TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_mfa_backup_user ON user_mfa_backup_codes(user_id, used_at)"
        )
        audit_columns = {row["name"] for row in connection.execute("PRAGMA table_info(audit_log)").fetchall()}
        if "company_id" not in audit_columns:
            connection.execute("ALTER TABLE audit_log ADD COLUMN company_id INTEGER NOT NULL DEFAULT 1")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_records_company_resource ON records(company_id, resource)")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS worker_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                verified INTEGER NOT NULL DEFAULT 0,
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
            CREATE TABLE IF NOT EXISTS worker_sessions (
                token_hash TEXT PRIMARY KEY,
                worker_id INTEGER NOT NULL,
                csrf_token TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(worker_id) REFERENCES worker_accounts(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS worker_profiles (
                worker_id INTEGER PRIMARY KEY,
                public_token TEXT NOT NULL UNIQUE,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(worker_id) REFERENCES worker_accounts(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS worker_verification_tokens (
                token_hash TEXT PRIMARY KEY,
                worker_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(worker_id) REFERENCES worker_accounts(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS worker_reset_tokens (
                token_hash TEXT PRIMARY KEY,
                worker_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(worker_id) REFERENCES worker_accounts(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS worker_company_access (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id INTEGER NOT NULL,
                company_id INTEGER NOT NULL,
                share_token TEXT NOT NULL UNIQUE,
                visible_fields TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                granted_at TEXT NOT NULL,
                revoked_at TEXT,
                imported_at TEXT,
                UNIQUE(worker_id, company_id),
                FOREIGN KEY(worker_id) REFERENCES worker_accounts(id) ON DELETE CASCADE,
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS worker_access_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                worker_id INTEGER NOT NULL,
                requested_by_user_id INTEGER,
                requested_fields TEXT NOT NULL,
                message TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                response_fields TEXT,
                responded_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE,
                FOREIGN KEY(worker_id) REFERENCES worker_accounts(id) ON DELETE CASCADE,
                FOREIGN KEY(requested_by_user_id) REFERENCES users(id) ON DELETE SET NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS worker_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL UNIQUE,
                mime_type TEXT NOT NULL,
                size INTEGER NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                expiry_date TEXT,
                review_status TEXT NOT NULL DEFAULT 'unread',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(worker_id) REFERENCES worker_accounts(id) ON DELETE CASCADE
            )
            """
        )
        worker_document_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(worker_documents)").fetchall()
        }
        if "expiry_source" not in worker_document_columns:
            connection.execute("ALTER TABLE worker_documents ADD COLUMN expiry_source TEXT")
        if "expiry_confidence" not in worker_document_columns:
            connection.execute("ALTER TABLE worker_documents ADD COLUMN expiry_confidence TEXT")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS worker_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                recipient TEXT NOT NULL,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'prepared',
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(worker_id) REFERENCES worker_accounts(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS worker_document_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                company_id INTEGER NOT NULL,
                reviewer_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(document_id) REFERENCES worker_documents(id) ON DELETE CASCADE,
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE,
                FOREIGN KEY(reviewer_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS company_api_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 1,
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                last_used_at TEXT,
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS department_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                department TEXT NOT NULL,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                user_id INTEGER,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                worker_id INTEGER,
                created_by_user_id INTEGER,
                created_by_worker_id INTEGER,
                department TEXT NOT NULL,
                request_type TEXT NOT NULL,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                related_resource TEXT,
                related_id INTEGER,
                status TEXT NOT NULL DEFAULT 'open',
                priority TEXT NOT NULL DEFAULT 'normal',
                assigned_contact_id INTEGER,
                due_date TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE,
                FOREIGN KEY(worker_id) REFERENCES worker_accounts(id) ON DELETE SET NULL,
                FOREIGN KEY(created_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY(created_by_worker_id) REFERENCES worker_accounts(id) ON DELETE SET NULL,
                FOREIGN KEY(assigned_contact_id) REFERENCES department_contacts(id) ON DELETE SET NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_request_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER NOT NULL,
                actor_type TEXT NOT NULL,
                actor_id INTEGER,
                event_type TEXT NOT NULL,
                from_status TEXT,
                to_status TEXT,
                note TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(request_id) REFERENCES workflow_requests(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                worker_id INTEGER NOT NULL,
                request_id INTEGER,
                subject TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE,
                FOREIGN KEY(worker_id) REFERENCES worker_accounts(id) ON DELETE CASCADE,
                FOREIGN KEY(request_id) REFERENCES workflow_requests(id) ON DELETE SET NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                sender_type TEXT NOT NULL,
                sender_user_id INTEGER,
                sender_worker_id INTEGER,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(conversation_id) REFERENCES workflow_conversations(id) ON DELETE CASCADE,
                FOREIGN KEY(sender_user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY(sender_worker_id) REFERENCES worker_accounts(id) ON DELETE SET NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS induction_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                worker_id INTEGER NOT NULL,
                induction_name TEXT NOT NULL,
                site TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                comments TEXT,
                reviewer_id INTEGER,
                reviewed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE,
                FOREIGN KEY(worker_id) REFERENCES worker_accounts(id) ON DELETE CASCADE,
                FOREIGN KEY(reviewer_id) REFERENCES users(id) ON DELETE SET NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS induction_review_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_id INTEGER NOT NULL,
                actor_type TEXT NOT NULL,
                actor_id INTEGER,
                from_status TEXT,
                to_status TEXT NOT NULL,
                comments TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(review_id) REFERENCES induction_reviews(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS induction_site_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                induction_record_id INTEGER,
                site_source_id TEXT,
                site_name TEXT NOT NULL,
                public_token TEXT NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(company_id, site_name),
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE,
                FOREIGN KEY(induction_record_id) REFERENCES records(id) ON DELETE SET NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_induction_site_links_company ON induction_site_links(company_id, active)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS induction_registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                site_link_id INTEGER NOT NULL,
                reference TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'evidence_pending',
                payload TEXT NOT NULL,
                upload_token_hash TEXT,
                upload_expires_at TEXT,
                submitted_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE,
                FOREIGN KEY(site_link_id) REFERENCES induction_site_links(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_induction_registrations_company ON induction_registrations(company_id, created_at)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS induction_registration_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                registration_id INTEGER NOT NULL,
                field_key TEXT NOT NULL,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL UNIQUE,
                content_type TEXT NOT NULL,
                size INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(registration_id) REFERENCES induction_registrations(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_induction_registration_evidence_registration ON induction_registration_evidence(registration_id)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS in_app_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                recipient_type TEXT NOT NULL,
                recipient_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                link TEXT,
                read_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS notification_preferences (
                owner_type TEXT NOT NULL,
                owner_id INTEGER NOT NULL,
                in_app INTEGER NOT NULL DEFAULT 1,
                email INTEGER NOT NULL DEFAULT 0,
                sms INTEGER NOT NULL DEFAULT 0,
                push INTEGER NOT NULL DEFAULT 0,
                preferred_language TEXT NOT NULL DEFAULT 'en',
                updated_at TEXT NOT NULL,
                PRIMARY KEY(owner_type, owner_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tenant_migration_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                package_id TEXT NOT NULL,
                package_sha256 TEXT NOT NULL,
                source_tenant TEXT NOT NULL,
                authorised_by TEXT NOT NULL,
                authorisation_reference TEXT NOT NULL,
                status TEXT NOT NULL,
                input_records INTEGER NOT NULL DEFAULT 0,
                inserted_records INTEGER NOT NULL DEFAULT 0,
                skipped_records INTEGER NOT NULL DEFAULT 0,
                reconciliation_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                UNIQUE(company_id, package_id),
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tenant_migration_record_map (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                company_id INTEGER NOT NULL,
                source_key TEXT NOT NULL,
                resource TEXT NOT NULL,
                local_record_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(company_id, source_key),
                FOREIGN KEY(run_id) REFERENCES tenant_migration_runs(id) ON DELETE CASCADE,
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE,
                FOREIGN KEY(local_record_id) REFERENCES records(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS pilot_acceptance (
                company_id INTEGER PRIMARY KEY,
                reviewer_name TEXT NOT NULL DEFAULT '',
                product_owner TEXT NOT NULL DEFAULT '',
                technical_owner TEXT NOT NULL DEFAULT '',
                decision TEXT NOT NULL DEFAULT 'pending',
                conditions TEXT NOT NULL DEFAULT '',
                checklist_json TEXT NOT NULL DEFAULT '{}',
                updated_by INTEGER,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE,
                FOREIGN KEY(updated_by) REFERENCES users(id) ON DELETE SET NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS translation_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                locale TEXT NOT NULL,
                source_key TEXT NOT NULL,
                translation TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'machine',
                reviewer TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                updated_by INTEGER,
                updated_at TEXT NOT NULL,
                UNIQUE(company_id, locale, source_key),
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE,
                FOREIGN KEY(updated_by) REFERENCES users(id) ON DELETE SET NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS email_diagnostic_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER NOT NULL,
                requested_by INTEGER,
                recipient TEXT NOT NULL,
                provider TEXT NOT NULL,
                status TEXT NOT NULL,
                safe_error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE,
                FOREIGN KEY(requested_by) REFERENCES users(id) ON DELETE SET NULL
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_workflow_requests_company_status ON workflow_requests(company_id, status)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_workflow_conversations_company_worker ON workflow_conversations(company_id, worker_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_notifications_recipient ON in_app_notifications(recipient_type, recipient_id, read_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_migration_runs_company ON tenant_migration_runs(company_id, created_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_email_diagnostics_company ON email_diagnostic_runs(company_id, created_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_translation_reviews_company_locale ON translation_reviews(company_id, locale, status)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_worker_access_requests_worker_status ON worker_access_requests(worker_id, status, created_at)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_worker_access_requests_company_status ON worker_access_requests(company_id, status, created_at)")
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_worker_access_requests_one_pending ON worker_access_requests(company_id, worker_id) WHERE status = 'pending'")
        for key, value in DEFAULT_SETTINGS.items():
            connection.execute(
                "INSERT OR IGNORE INTO metadata(key, value) VALUES (?, ?)",
                (f"setting_{key}", value),
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
            # The customer snapshot is append-once and immutable. A changed export must be
            # reviewed and imported into a fresh data volume; startup never replaces rows.
            if import_version and imported_version is None:
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
            # Production-backed installations return before the local seed path
            # below. Generate any missing per-site public induction links here so
            # fresh deployments and restored data volumes are immediately ready.
            ensure_induction_site_links(connection, 1)
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
        ensure_induction_site_links(connection, 1)
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


def extract_document_expiry(content: bytes, original_name: str, title: str = "") -> tuple[str, str, str]:
    """Best-effort, auditable expiry extraction; callers must still allow review."""
    extension = Path(original_name).suffix.lower()
    text_parts = [Path(original_name).stem, title]
    try:
        if extension in {".docx", ".xlsx"}:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                names = [
                    name for name in archive.namelist()
                    if name.endswith(".xml") and (name.startswith("word/") or name.startswith("xl/sharedStrings"))
                ]
                for name in names[:20]:
                    xml = archive.read(name).decode("utf-8", "ignore")
                    text_parts.append(html.unescape(re.sub(r"<[^>]+>", " ", xml)))
        else:
            text_parts.append(content.decode("latin-1", "ignore"))
    except (OSError, zipfile.BadZipFile, KeyError):
        pass
    text = re.sub(r"\s+", " ", " ".join(text_parts))[:2_000_000]
    date_expression = r"(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})"
    keyword = r"(?:expiry|expires?|expiration|valid\s+(?:until|to)|renewal\s+(?:date|due)|due\s+date)"
    contextual = re.compile(rf"{keyword}[^0-9]{{0,48}}{date_expression}", re.IGNORECASE)
    reverse = re.compile(rf"{date_expression}[^A-Za-z]{{0,24}}{keyword}", re.IGNORECASE)
    matches = [(match.group(1), "document_text", "high") for match in contextual.finditer(text)]
    matches.extend((match.group(1), "document_text", "high") for match in reverse.finditer(text))
    if not matches and re.search(keyword, " ".join(text_parts[:2]), re.IGNORECASE):
        matches = [(match.group(1), "file_name_or_title", "medium") for match in re.finditer(date_expression, " ".join(text_parts[:2]))]
    for candidate, source, confidence in matches:
        parsed = parse_record_date(candidate.replace("-", "/") if re.match(r"\d{1,2}-", candidate) else candidate)
        if parsed:
            return parsed.isoformat(), source, confidence
    return "", "not_detected", "none"


def local_record(connection, resource: str, record_id: int, company_id: int = 1):
    row = connection.execute(
        "SELECT * FROM records WHERE resource = ? AND id = ? AND company_id = ?", (resource, record_id, company_id)
    ).fetchone()
    if row is None:
        return None
    record = row_to_record(row)
    if record.get("_read_only") or not record.get("local_only"):
        return None
    return record


def application_settings(company_id: int = 1) -> dict:
    settings = dict(DEFAULT_SETTINGS)
    with DB_LOCK, connect_database() as connection:
        if company_id == 1:
            rows = connection.execute("SELECT key, value FROM metadata WHERE key LIKE 'setting_%'").fetchall()
            for row in rows:
                settings[row["key"].removeprefix("setting_")] = row["value"]
        tenant_rows = connection.execute("SELECT key, value FROM company_settings WHERE company_id = ?", (company_id,)).fetchall()
        for row in tenant_rows:
            settings[row["key"]] = row["value"]
        company = connection.execute("SELECT name FROM companies WHERE id = ?", (company_id,)).fetchone()
        if company and not tenant_rows:
            settings["brand_company"] = company["name"]
    environment_overrides = {
        "brand_name": "KOMPLIANCE_BRAND_NAME",
        "brand_company": "KOMPLIANCE_BRAND_COMPANY",
        "brand_tagline": "KOMPLIANCE_BRAND_TAGLINE",
        "privacy_contact": "KOMPLIANCE_PRIVACY_CONTACT",
        "compliance_recipient": "KOMPLIANCE_COMPLIANCE_RECIPIENT",
    }
    for key, environment_name in environment_overrides.items():
        value = os.environ.get(environment_name, "").strip()
        if value:
            settings[key] = value
    return settings


def public_email_configuration() -> dict:
    provider = os.environ.get("KOMPLIANCE_EMAIL_PROVIDER", "smtp").strip().lower()
    if provider not in {"smtp", "gmail_oauth"}:
        provider = "unsupported"
    host = os.environ.get("KOMPLIANCE_SMTP_HOST", "").strip()
    sender = os.environ.get("KOMPLIANCE_SMTP_FROM", "").strip()
    base_url = os.environ.get("KOMPLIANCE_BASE_URL", "").strip()
    enabled = os.environ.get("KOMPLIANCE_EMAIL_DELIVERY", "0").strip() == "1"
    oauth_configured = all(
        os.environ.get(name, "").strip()
        for name in (
            "KOMPLIANCE_GMAIL_CLIENT_ID",
            "KOMPLIANCE_GMAIL_CLIENT_SECRET",
            "KOMPLIANCE_GMAIL_REFRESH_TOKEN",
        )
    )
    provider_configured = bool(host) if provider == "smtp" else oauth_configured if provider == "gmail_oauth" else False
    return {
        "enabled": enabled,
        "configured": bool(provider_configured and sender and base_url.startswith("https://")),
        "provider": provider,
        "host_configured": bool(host),
        "oauth_configured": oauth_configured,
        "base_url_configured": base_url.startswith("https://"),
        "sender": sender,
        "mode": (
            "OAuth 2.0 / Gmail API"
            if provider == "gmail_oauth"
            else os.environ.get("KOMPLIANCE_SMTP_SECURITY", "starttls").strip().lower()
        ),
    }


def mask_email(value: str) -> str:
    """Return a useful diagnostic label without exposing a full recipient."""
    text = str(value or "").strip()
    if "@" not in text:
        return "invalid recipient"
    local, domain = text.rsplit("@", 1)
    visible = local[:1] if local else ""
    return f"{visible}{'*' * max(min(len(local) - 1, 6), 2)}@{domain}"


def safe_delivery_error(error: Exception) -> str:
    """Remove configured long-lived credentials from a provider error."""
    message = str(error) or error.__class__.__name__
    for name in (
        "KOMPLIANCE_GMAIL_CLIENT_SECRET",
        "KOMPLIANCE_GMAIL_REFRESH_TOKEN",
        "KOMPLIANCE_SMTP_PASSWORD",
    ):
        secret = os.environ.get(name, "")
        if secret:
            message = message.replace(secret, "[redacted]")
    return re.sub(r"\s+", " ", message).strip()[:300]


def pilot_acceptance_state(company_id: int = 1) -> dict:
    checklist = {key: False for key, _ in PILOT_REVIEW_CHECKLIST}
    with DB_LOCK, connect_database() as connection:
        row = connection.execute(
            "SELECT * FROM pilot_acceptance WHERE company_id = ?", (company_id,)
        ).fetchone()
    if row is None:
        return {
            "reviewer_name": "",
            "product_owner": "",
            "technical_owner": "",
            "decision": "pending",
            "conditions": "",
            "checklist": checklist,
            "updated_at": "",
        }
    try:
        saved = json.loads(row["checklist_json"])
    except (TypeError, json.JSONDecodeError):
        saved = {}
    checklist.update({key: bool(saved.get(key)) for key in checklist})
    return {
        "reviewer_name": row["reviewer_name"],
        "product_owner": row["product_owner"],
        "technical_owner": row["technical_owner"],
        "decision": row["decision"],
        "conditions": row["conditions"],
        "checklist": checklist,
        "updated_at": row["updated_at"],
    }


def review_operations_status() -> dict:
    status = {
        "available": False,
        "ready": False,
        "backups_enabled": False,
        "last_backup_at": "",
        "last_backup_error": "",
    }
    try:
        saved = json.loads(
            (DATA_ROOT / "operations" / "status.json").read_text(encoding="utf-8")
        )
        if isinstance(saved, dict):
            status.update(saved)
            status["available"] = True
    except (OSError, json.JSONDecodeError):
        pass
    return status


def build_review_readiness(company_id: int = 1) -> dict:
    settings = application_settings(company_id)
    email = public_email_configuration()
    acceptance = pilot_acceptance_state(company_id)
    operations = review_operations_status()
    with DB_LOCK, connect_database() as connection:
        integrity = connection.execute("PRAGMA quick_check").fetchone()[0]
        role_rows = connection.execute(
            "SELECT role, COUNT(*) AS total FROM users WHERE company_id = ? AND active = 1 GROUP BY role",
            (company_id,),
        ).fetchall()
        roles = {row["role"]: row["total"] for row in role_rows}
        mfa_enabled = connection.execute(
            "SELECT COUNT(*) FROM users WHERE company_id = ? AND active = 1 AND mfa_enabled = 1",
            (company_id,),
        ).fetchone()[0]
        setting_rows = connection.execute(
            "SELECT key FROM company_settings WHERE company_id = ?", (company_id,)
        ).fetchall()
        explicit_settings = {row["key"] for row in setting_rows}
        record_rows = connection.execute(
            "SELECT payload FROM records WHERE company_id = ?", (company_id,)
        ).fetchall()
        email_runs = connection.execute(
            "SELECT id, recipient, provider, status, safe_error, created_at "
            "FROM email_diagnostic_runs WHERE company_id = ? ORDER BY id DESC LIMIT 20",
            (company_id,),
        ).fetchall()
    protected_records = 0
    local_records = 0
    for row in record_rows:
        try:
            payload = json.loads(row["payload"])
        except (TypeError, json.JSONDecodeError):
            continue
        if is_protected_payload(payload):
            protected_records += 1
        elif payload.get("local_only"):
            local_records += 1
    diagnostic_history = [
        {
            "id": row["id"],
            "recipient": mask_email(row["recipient"]),
            "provider": row["provider"],
            "status": row["status"],
            "safe_error": row["safe_error"],
            "created_at": row["created_at"],
        }
        for row in email_runs
    ]
    last_email_run = diagnostic_history[0] if diagnostic_history else None
    last_email_success = (
        last_email_run if last_email_run and last_email_run["status"] == "sent" else None
    )
    checklist_completed = sum(bool(value) for value in acceptance["checklist"].values())
    checklist_total = len(PILOT_REVIEW_CHECKLIST)

    def check(key, label, status, detail, action=""):
        return {
            "key": key,
            "label": label,
            "status": status,
            "detail": detail,
            "action": action,
        }

    all_roles_present = all(roles.get(role, 0) > 0 for role in ("viewer", "editor", "admin"))
    settings_approved = {
        "privacy_contact": bool(settings.get("privacy_contact", "").strip()),
        "compliance_recipient": bool(settings.get("compliance_recipient", "").strip()),
        "retention_days": "retention_days" in explicit_settings,
        "reminder_days": "reminder_days" in explicit_settings,
    }
    checks = [
        check(
            "database",
            "Database integrity",
            "pass" if integrity == "ok" else "block",
            f"SQLite quick check: {integrity}",
        ),
        check(
            "protected_boundary",
            "Imported snapshot boundary",
            "pass" if company_id != 1 or protected_records > 0 else "block",
            f"{protected_records:,} protected records; {local_records:,} isolated local records",
        ),
        check(
            "roles",
            "Pilot role coverage",
            "pass" if all_roles_present else "block",
            f"Admin {roles.get('admin', 0)} · Editor {roles.get('editor', 0)} · Viewer {roles.get('viewer', 0)}",
            "Create any missing pilot account.",
        ),
        check(
            "mfa",
            "Administrator MFA",
            "pass" if mfa_enabled else "attention",
            f"{mfa_enabled} active account{'s' if mfa_enabled != 1 else ''} enrolled",
            "Enrol at least one administrator under Security settings.",
        ),
        check(
            "email_configuration",
            "Email provider",
            "pass" if email["enabled"] and email["configured"] else "attention",
            f"{'Enabled' if email['enabled'] else 'Disabled'} · {email['provider']} · {'configured' if email['configured'] else 'incomplete'}",
            "Complete the approved sender configuration.",
        ),
        check(
            "email_test",
            "Controlled email test",
            "pass" if last_email_success else "attention",
            (
                f"Last successful test {last_email_success['created_at']}"
                if last_email_success
                else "No successful application-path diagnostic recorded"
            ),
            "Send one controlled diagnostic from this review centre.",
        ),
        check(
            "privacy_contact",
            "Privacy contact",
            "pass" if settings_approved["privacy_contact"] else "attention",
            "Configured" if settings_approved["privacy_contact"] else "Awaiting an approved contact",
            "Record Marcelo’s approved privacy contact.",
        ),
        check(
            "compliance_recipient",
            "Compliance recipient",
            "pass" if settings_approved["compliance_recipient"] else "attention",
            "Configured" if settings_approved["compliance_recipient"] else "Awaiting an approved recipient",
            "Record the recipient before reminder delivery.",
        ),
        check(
            "retention",
            "Retention approval",
            "pass" if settings_approved["retention_days"] else "attention",
            (
                f"{settings.get('retention_days', '365')} days recorded"
                if settings_approved["retention_days"]
                else f"Default {settings.get('retention_days', '365')} days; approval not recorded"
            ),
            "Record the approved local-data retention period.",
        ),
        check(
            "reminders",
            "Reminder interval approval",
            "pass" if settings_approved["reminder_days"] else "attention",
            (
                f"{settings.get('reminder_days', '30')} days recorded"
                if settings_approved["reminder_days"]
                else f"Default {settings.get('reminder_days', '30')} days; approval not recorded"
            ),
            "Record the approved reminder window.",
        ),
        check(
            "scheduler",
            "Automatic scheduler",
            "hold" if not SCHEDULER_STATE["enabled"] else "pass",
            "Disabled for controlled pilot" if not SCHEDULER_STATE["enabled"] else "Enabled",
            "Keep disabled until recipients and intervals are approved.",
        ),
        check(
            "backups",
            "Automated backup service",
            "pass"
            if operations.get("ready")
            and operations.get("backups_enabled")
            and not operations.get("last_backup_error")
            else "attention",
            (
                f"Healthy · last backup {operations.get('last_backup_at') or 'recorded'}"
                if operations.get("ready") and not operations.get("last_backup_error")
                else "No healthy operations backup status is available"
            ),
            "Verify a backup and empty-directory restore rehearsal.",
        ),
        check(
            "acceptance_checklist",
            "Pilot acceptance checklist",
            "pass" if checklist_completed == checklist_total else "attention",
            f"{checklist_completed} of {checklist_total} review paths recorded",
            "Complete the remaining review paths with Marcelo.",
        ),
        check(
            "release_decision",
            "Customer release decision",
            "pass"
            if acceptance["decision"] in {"accepted", "accepted_with_conditions"}
            else "attention",
            acceptance["decision"].replace("_", " ").title(),
            "Record the named customer decision.",
        ),
    ]
    counts = {
        status: sum(item["status"] == status for item in checks)
        for status in ("pass", "attention", "hold", "block")
    }
    return {
        "generated_at": utc_now(),
        "pilot_ready": counts["block"] == 0,
        "commercial_release_ready": counts["block"] == 0
        and counts["attention"] == 0
        and acceptance["decision"] in {"accepted", "accepted_with_conditions"},
        "counts": counts,
        "checks": checks,
        "acceptance": acceptance,
        "checklist_items": [
            {"key": key, "label": label} for key, label in PILOT_REVIEW_CHECKLIST
        ],
        "email": email,
        "email_diagnostics": diagnostic_history,
        "scheduler": dict(SCHEDULER_STATE),
        "operations": operations,
    }


def gmail_oauth_access_token() -> str:
    """Return a short-lived Gmail access token without exposing long-lived credentials."""
    now = time.monotonic()
    with GMAIL_OAUTH_LOCK:
        cached_token = str(GMAIL_OAUTH_CACHE.get("access_token", ""))
        if cached_token and float(GMAIL_OAUTH_CACHE.get("expires_at", 0.0)) > now + 60:
            return cached_token

        form = urlencode(
            {
                "client_id": os.environ.get("KOMPLIANCE_GMAIL_CLIENT_ID", ""),
                "client_secret": os.environ.get("KOMPLIANCE_GMAIL_CLIENT_SECRET", ""),
                "refresh_token": os.environ.get("KOMPLIANCE_GMAIL_REFRESH_TOKEN", ""),
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")
        request = Request(
            GMAIL_TOKEN_ENDPOINT,
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            status = getattr(error, "code", "unavailable")
            raise RuntimeError(f"Gmail OAuth token refresh failed (HTTP {status})") from None
        access_token = str(payload.get("access_token", ""))
        if not access_token:
            raise RuntimeError("Gmail OAuth token refresh returned no access token")
        try:
            expires_in = max(int(payload.get("expires_in", 3600)), 120)
        except (TypeError, ValueError):
            expires_in = 3600
        GMAIL_OAUTH_CACHE["access_token"] = access_token
        GMAIL_OAUTH_CACHE["expires_at"] = now + expires_in
        return access_token


def send_gmail_api_message(message: EmailMessage) -> None:
    raw_message = urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")
    request = Request(
        GMAIL_SEND_ENDPOINT,
        data=json.dumps({"raw": raw_message}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {gmail_oauth_access_token()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            if not 200 <= int(getattr(response, "status", 200)) < 300:
                raise RuntimeError("Gmail API rejected the message")
            response.read()
    except (HTTPError, URLError, TimeoutError) as error:
        status = getattr(error, "code", "unavailable")
        raise RuntimeError(f"Gmail API delivery failed (HTTP {status})") from None


def recovery_rate_limit_allowed(limit_key: str) -> bool:
    now = datetime.now(UTC)
    window_start = now - timedelta(minutes=RECOVERY_WINDOW_MINUTES)
    with DB_LOCK, connect_database() as connection:
        row = connection.execute(
            "SELECT window_started, attempts FROM rate_limits WHERE limit_key = ?",
            (limit_key,),
        ).fetchone()
        if row is None or datetime.fromisoformat(row["window_started"]) < window_start:
            connection.execute(
                "INSERT INTO rate_limits(limit_key, window_started, attempts) VALUES (?, ?, 1) "
                "ON CONFLICT(limit_key) DO UPDATE SET window_started = excluded.window_started, attempts = 1",
                (limit_key, now.replace(microsecond=0).isoformat()),
            )
            connection.commit()
            return True
        attempts = int(row["attempts"] or 0) + 1
        connection.execute(
            "UPDATE rate_limits SET attempts = ? WHERE limit_key = ?", (attempts, limit_key)
        )
        connection.commit()
        return attempts <= RECOVERY_MAX_ATTEMPTS


def company_api_rate_limit(token_id: int) -> tuple[bool, int, int]:
    now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=1)
    key = f"company-api:{token_id}"
    with DB_LOCK, connect_database() as connection:
        row = connection.execute(
            "SELECT window_started, attempts FROM rate_limits WHERE limit_key = ?", (key,)
        ).fetchone()
        if row is None or row["window_started"] <= cutoff.replace(microsecond=0).isoformat():
            started = now.replace(microsecond=0).isoformat()
            attempts = 1
            connection.execute(
                "INSERT INTO rate_limits(limit_key, window_started, attempts) VALUES (?, ?, ?) "
                "ON CONFLICT(limit_key) DO UPDATE SET window_started = excluded.window_started, attempts = excluded.attempts",
                (key, started, attempts),
            )
            retry_after = 60
        else:
            started_at = datetime.fromisoformat(row["window_started"])
            attempts = int(row["attempts"] or 0) + 1
            connection.execute("UPDATE rate_limits SET attempts = ? WHERE limit_key = ?", (attempts, key))
            retry_after = max(1, int(60 - (now - started_at).total_seconds()))
        connection.commit()
    remaining = max(API_RATE_LIMIT_PER_MINUTE - attempts, 0)
    return attempts <= API_RATE_LIMIT_PER_MINUTE, remaining, retry_after


def public_induction_rate_limit_allowed(limit_key: str) -> bool:
    now = datetime.now(UTC)
    window_start = now - timedelta(minutes=PUBLIC_INDUCTION_WINDOW_MINUTES)
    key = f"public-induction:{limit_key}"
    with DB_LOCK, connect_database() as connection:
        row = connection.execute(
            "SELECT window_started, attempts FROM rate_limits WHERE limit_key = ?",
            (key,),
        ).fetchone()
        if row is None or datetime.fromisoformat(row["window_started"]) < window_start:
            connection.execute(
                "INSERT INTO rate_limits(limit_key, window_started, attempts) VALUES (?, ?, 1) "
                "ON CONFLICT(limit_key) DO UPDATE SET window_started = excluded.window_started, attempts = 1",
                (key, now.replace(microsecond=0).isoformat()),
            )
            connection.commit()
            return True
        attempts = int(row["attempts"] or 0) + 1
        connection.execute(
            "UPDATE rate_limits SET attempts = ? WHERE limit_key = ?",
            (attempts, key),
        )
        connection.commit()
    return attempts <= PUBLIC_INDUCTION_MAX_ATTEMPTS


def write_system_audit(action: str, resource: str, summary: str = "") -> None:
    with DB_LOCK, connect_database() as connection:
        connection.execute(
            "INSERT INTO audit_log(user_id, actor, action, resource, record_id, summary, created_at) "
            "VALUES (NULL, 'Kompliance scheduler', ?, ?, NULL, ?, ?)",
            (action, resource, summary[:500], utc_now()),
        )
        connection.commit()


def build_compliance_reminder_data(days: int, company_id: int = 1) -> dict:
    today = datetime.now(UTC).date()
    cutoff = today + timedelta(days=days)
    definitions = (
        ("workers", "safe_pass_expiry", "Safe Pass", "name"),
        ("ga1", "expiry_date", "GA1 document set", "worker"),
        ("risk_assessment", "expiry_date", "Risk assessment", "title"),
        ("local_induction_completions", "expires_at", "Induction certificate", "worker"),
    )
    settings = application_settings(company_id)
    items = []
    missing_dates = 0
    with DB_LOCK, connect_database() as connection:
        worker_rows = connection.execute(
            "SELECT payload FROM records WHERE resource = 'workers' AND company_id = ?", (company_id,)
        ).fetchall()
        worker_emails = {}
        for worker_row in worker_rows:
            worker = json.loads(worker_row["payload"])
            if worker.get("name") and worker.get("email"):
                worker_emails[str(worker["name"]).strip().casefold()] = str(worker["email"]).strip()
        for resource, date_field, category, subject_field in definitions:
            rows = connection.execute(
                "SELECT * FROM records WHERE resource = ? AND company_id = ? ORDER BY id DESC", (resource, company_id)
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
                subject = record.get(subject_field) or record.get("name") or record.get("title") or f"Record {record['id']}"
                recipient = str(record.get("email") or "").strip()
                if not recipient:
                    recipient = worker_emails.get(str(subject).strip().casefold(), "")
                if not recipient:
                    recipient = settings.get("compliance_recipient", "")
                items.append(
                    {
                        "resource": resource,
                        "record_id": record["id"],
                        "category": category,
                        "subject": subject,
                        "site": record.get("site") or record.get("sites") or "",
                        "recipient": recipient,
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


def prepare_compliance_notifications(days: int, company_id: int = 1) -> dict:
    reminder_data = build_compliance_reminder_data(days, company_id)
    due_items = [item for item in reminder_data["data"] if item["state"] in {"Overdue", "Due soon"}]
    now = utc_now()
    created = []
    duplicates = 0
    with DB_LOCK, connect_database() as connection:
        existing_rows = connection.execute(
            "SELECT payload FROM records WHERE resource = 'local_notifications' AND company_id = ?", (company_id,)
        ).fetchall()
        fingerprints = {
            json.loads(row["payload"]).get("fingerprint")
            for row in existing_rows
            if json.loads(row["payload"]).get("kind") == "compliance_reminder"
        }
        for item in due_items:
            fingerprint = hashlib.sha256(
                f"{item['resource']}:{item['record_id']}:{item['due_date']}".encode("utf-8")
            ).hexdigest()
            if fingerprint in fingerprints:
                duplicates += 1
                continue
            locale = preferred_language_for_email(connection, item["recipient"])
            localized_category = translate_ui(item["category"], locale)
            localized_state = translate_ui(item["state"], locale).lower()
            notification = {
                "kind": "compliance_reminder",
                "channel": "Email",
                "recipient": item["recipient"],
                "subject": reviewed_server_message(
                    connection,
                    company_id,
                    "compliance_subject",
                    locale,
                    category=localized_category,
                    state=localized_state,
                    subject=item["subject"],
                ),
                "message": reviewed_server_message(
                    connection,
                    company_id,
                    "compliance_body",
                    locale,
                    category=localized_category,
                    state=localized_state,
                    subject=item["subject"],
                    due_date=item["due_date"],
                ),
                "language": locale,
                "related_resource": item["resource"],
                "related_record_id": item["record_id"],
                "due_date": item["due_date"],
                "fingerprint": fingerprint,
                "delivery_status": "prepared",
                "status": "Prepared - not sent",
                "attempts": 0,
                "source": "local controlled workspace",
                "local_only": True,
            }
            cursor = connection.execute(
                "INSERT INTO records(resource, payload, created_at, updated_at, company_id) VALUES ('local_notifications', ?, ?, ?, ?)",
                (json.dumps(notification), now, now, company_id),
            )
            created.append(cursor.lastrowid)
            fingerprints.add(fingerprint)
        connection.commit()
    return {"created": len(created), "ids": created, "duplicates": duplicates, "sent": 0}


def send_notification_email(notification: dict) -> None:
    configuration = public_email_configuration()
    if not configuration["enabled"]:
        raise RuntimeError("Email delivery is disabled")
    if not configuration["configured"]:
        raise RuntimeError(f"{configuration['provider']} email delivery is not fully configured")
    recipient = str(notification.get("recipient", "")).strip()
    if "@" not in recipient:
        raise ValueError("A valid notification recipient is required")
    message = EmailMessage()
    message["From"] = configuration["sender"]
    message["To"] = recipient
    message["Subject"] = str(notification.get("subject", "Kompliance notification"))[:240]
    message.set_content(str(notification.get("message", "")))
    if configuration["provider"] == "gmail_oauth":
        send_gmail_api_message(message)
        return
    host = os.environ["KOMPLIANCE_SMTP_HOST"].strip()
    port = int(os.environ.get("KOMPLIANCE_SMTP_PORT", "465" if configuration["mode"] == "ssl" else "587"))
    timeout = min(max(int(os.environ.get("KOMPLIANCE_SMTP_TIMEOUT", "15")), 3), 60)
    smtp_class = smtplib.SMTP_SSL if configuration["mode"] == "ssl" else smtplib.SMTP
    with smtp_class(host, port, timeout=timeout) as client:
        if configuration["mode"] == "starttls":
            client.starttls()
        username = os.environ.get("KOMPLIANCE_SMTP_USERNAME", "").strip()
        password = os.environ.get("KOMPLIANCE_SMTP_PASSWORD", "")
        if username:
            client.login(username, password)
        client.send_message(message)


def dispatch_notification_queue(limit: int = 100, record_ids: set[int] | None = None, company_id: int = 1) -> dict:
    configuration = public_email_configuration()
    if not configuration["enabled"] or not configuration["configured"]:
        return {"sent": 0, "failed": 0, "skipped": 0, "enabled": configuration["enabled"], "configured": configuration["configured"]}
    with DB_LOCK, connect_database() as connection:
        rows = connection.execute(
            "SELECT * FROM records WHERE resource = 'local_notifications' AND company_id = ? ORDER BY id ASC", (company_id,)
        ).fetchall()
    sent = failed = skipped = 0
    for row in rows:
        if sent + failed >= limit:
            break
        notification = row_to_record(row)
        if record_ids is not None and notification["id"] not in record_ids:
            continue
        if notification.get("delivery_status", "prepared") not in {"prepared", "failed"}:
            continue
        if int(notification.get("attempts") or 0) >= 3 and record_ids is None:
            skipped += 1
            continue
        if "@" not in str(notification.get("recipient", "")):
            skipped += 1
            continue
        updated = {key: value for key, value in notification.items() if key not in {"id", "_read_only", "created_at", "updated_at"}}
        updated["attempts"] = int(updated.get("attempts") or 0) + 1
        try:
            send_notification_email(notification)
            updated.update({"delivery_status": "sent", "status": "Sent", "sent_at": utc_now(), "last_error": ""})
            sent += 1
        except Exception as error:
            updated.update({"delivery_status": "failed", "status": "Delivery failed", "last_error": str(error)[:300], "last_attempt_at": utc_now()})
            failed += 1
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            connection.execute(
                "UPDATE records SET payload = ?, updated_at = ? WHERE resource = 'local_notifications' AND id = ? AND company_id = ?",
                (json.dumps(updated), now, notification["id"], company_id),
            )
            connection.commit()
    return {"sent": sent, "failed": failed, "skipped": skipped, "enabled": True, "configured": True}


def retention_cleanup(dry_run: bool = True, company_id: int = 1) -> dict:
    settings = application_settings(company_id)
    retention_days = min(max(int(settings.get("retention_days", "365")), 30), 3650)
    now = datetime.now(UTC)
    cutoff = (now - timedelta(days=retention_days)).replace(microsecond=0).isoformat()
    now_text = now.replace(microsecond=0).isoformat()
    with DB_LOCK, connect_database() as connection:
        notification_ids = [
            row["id"] for row in connection.execute(
                "SELECT id FROM records WHERE resource = 'local_notifications' AND created_at < ? AND company_id = ?", (cutoff, company_id)
            ).fetchall()
        ]
        expired_sessions = connection.execute(
            "SELECT COUNT(*) FROM sessions JOIN users ON users.id = sessions.user_id WHERE sessions.expires_at <= ? AND users.company_id = ?", (now_text, company_id)
        ).fetchone()[0]
        expired_tokens = connection.execute(
            "SELECT COUNT(*) FROM password_reset_tokens JOIN users ON users.id = password_reset_tokens.user_id WHERE (password_reset_tokens.expires_at <= ? OR password_reset_tokens.used_at IS NOT NULL) AND users.company_id = ?", (now_text, company_id)
        ).fetchone()[0]
        if not dry_run:
            connection.executemany("DELETE FROM records WHERE resource = 'local_notifications' AND id = ? AND company_id = ?", [(item, company_id) for item in notification_ids])
            connection.execute("DELETE FROM sessions WHERE expires_at <= ? AND user_id IN (SELECT id FROM users WHERE company_id = ?)", (now_text, company_id))
            connection.execute("DELETE FROM password_reset_tokens WHERE (expires_at <= ? OR used_at IS NOT NULL) AND user_id IN (SELECT id FROM users WHERE company_id = ?)", (now_text, company_id))
            connection.commit()
    return {
        "dry_run": dry_run,
        "retention_days": retention_days,
        "local_notifications": len(notification_ids),
        "expired_sessions": expired_sessions,
        "expired_reset_tokens": expired_tokens,
        "protected_records": 0,
    }


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


def generate_mfa_secret() -> str:
    """Generate a 160-bit RFC 6238-compatible Base32 secret."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def mfa_code(secret: str, timestamp: float | None = None) -> str:
    normalized = str(secret or "").strip().replace(" ", "").upper()
    padding = "=" * ((8 - len(normalized) % 8) % 8)
    key = base64.b32decode(normalized + padding, casefold=True)
    counter = int((timestamp if timestamp is not None else time.time()) // MFA_PERIOD_SECONDS)
    digest = hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    return str(number % (10**MFA_DIGITS)).zfill(MFA_DIGITS)


def mfa_code_matches(secret: str, supplied: str, timestamp: float | None = None) -> bool:
    candidate = "".join(character for character in str(supplied or "") if character.isdigit())
    if len(candidate) != MFA_DIGITS:
        return False
    moment = timestamp if timestamp is not None else time.time()
    try:
        return any(
            hmac.compare_digest(candidate, mfa_code(secret, moment + offset * MFA_PERIOD_SECONDS))
            for offset in (-1, 0, 1)
        )
    except (ValueError, TypeError):
        return False


def mfa_backup_hash(code: str) -> str:
    normalized = str(code or "").strip().replace("-", "").replace(" ", "").upper()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_mfa_backup_codes() -> list[str]:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return [
        "".join(secrets.choice(alphabet) for _ in range(5))
        + "-"
        + "".join(secrets.choice(alphabet) for _ in range(5))
        for _ in range(MFA_BACKUP_CODE_COUNT)
    ]


def verify_user_mfa(connection, user_row, supplied: str, consume_backup: bool = True) -> bool:
    if mfa_code_matches(user_row["mfa_secret"], supplied):
        return True
    digest = mfa_backup_hash(supplied)
    row = connection.execute(
        "SELECT id FROM user_mfa_backup_codes WHERE user_id = ? AND code_hash = ? AND used_at IS NULL",
        (user_row["id"], digest),
    ).fetchone()
    if row is None:
        return False
    if consume_backup:
        connection.execute(
            "UPDATE user_mfa_backup_codes SET used_at = ? WHERE id = ? AND used_at IS NULL",
            (utc_now(), row["id"]),
        )
    return True


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


@lru_cache(maxsize=1)
def register_pdf_fonts() -> tuple[str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    roots = (
        Path("C:/Windows/Fonts"),
        Path("/usr/share/fonts/truetype/noto"),
        Path("/usr/share/fonts/opentype/noto"),
        Path("/usr/share/fonts/truetype/dejavu"),
    )
    for regular_name, bold_name in (
        ("NotoSans-Regular.ttf", "NotoSans-Bold.ttf"),
        ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
    ):
        for root in roots:
            regular = root / regular_name
            bold = root / bold_name
            if regular.is_file() and bold.is_file():
                pdfmetrics.registerFont(TTFont("KomplianceSans", str(regular)))
                pdfmetrics.registerFont(TTFont("KomplianceSansBold", str(bold)))
                return "KomplianceSans", "KomplianceSansBold"
    return "Helvetica", "Helvetica-Bold"


def build_text_pdf(
    title: str,
    subtitle: str,
    lines: list[str],
    locale: str = "en-IE",
    overrides: dict[str, str] | None = None,
) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen.canvas import Canvas

    regular_font, bold_font = register_pdf_fonts()
    wrapped = []
    for line in lines:
        wrapped.extend(
            textwrap.wrap(str(line), width=88, replace_whitespace=True, break_long_words=True)
            or [""]
        )
    page_chunks = [wrapped[index : index + 44] for index in range(0, len(wrapped), 44)] or [[]]
    output = io.BytesIO()
    canvas = Canvas(output, pagesize=A4, pageCompression=1)
    width, height = A4
    for page_index, page_lines in enumerate(page_chunks, 1):
        canvas.setFillColorRGB(0.04, 0.38, 0.30)
        canvas.rect(0, height - 52, width, 52, fill=1, stroke=0)
        canvas.setFillColorRGB(1, 1, 1)
        canvas.setFont(bold_font, 18)
        canvas.drawString(42, height - 31, str(title)[:90])
        canvas.setFillColorRGB(0.08, 0.18, 0.28)
        canvas.setFont(regular_font, 9)
        canvas.drawString(42, height - 68, str(subtitle)[:110])
        y = height - 94
        for line in page_lines:
            canvas.drawString(42, y, str(line))
            y -= 15
        canvas.setFont(regular_font, 8)
        translations = overrides or {}
        canvas.drawRightString(
            width - 42,
            24,
            f"{translations.get('Page') or translate_ui('Page', locale)} {page_index} {translations.get('of') or translate_ui('of', locale)} {len(page_chunks)}",
        )
        canvas.showPage()
    canvas.save()
    return output.getvalue()


def build_certificate_pdf_legacy(
    company: str,
    worker: str,
    induction: str,
    site: str,
    completed_at: str,
    expires_at: str,
    certificate_number: str,
    verification_url: str,
    brand_name: str = "Kompliance",
    brand_tagline: str = "Health & Safety Operations",
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
        ("F1", 8, 64, 62, f"Generated by {brand_name} · {brand_tagline}. Status must be checked online."),
    ]
    commands = [
        "0.04 0.38 0.30 rg 0 780 595 62 re f",
        "1 1 1 rg",
        "34 796 20 20 re f",
        "0.04 0.38 0.30 rg",
        "BT /F2 13 Tf 39 801 Td (K) Tj ET",
        "1 1 1 rg",
        f"BT /F2 13 Tf 64 804 Td ({pdf_escape(brand_name.upper())}) Tj ET",
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


def build_certificate_pdf(
    company: str,
    worker: str,
    induction: str,
    site: str,
    completed_at: str,
    expires_at: str,
    certificate_number: str,
    verification_url: str,
    brand_name: str = "Kompliance",
    brand_tagline: str = "Health & Safety Operations",
    locale: str = "en-IE",
    overrides: dict[str, str] | None = None,
) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen.canvas import Canvas

    regular_font, bold_font = register_pdf_fonts()
    output = io.BytesIO()
    canvas = Canvas(output, pagesize=A4, pageCompression=1)
    _, height = A4
    canvas.setFillColorRGB(0.04, 0.38, 0.30)
    canvas.rect(0, height - 62, 595, 62, fill=1, stroke=0)
    canvas.setFillColorRGB(1, 1, 1)
    canvas.setFont(bold_font, 13)
    canvas.drawString(64, height - 39, brand_name.upper())
    canvas.setFillColorRGB(0.08, 0.18, 0.28)

    def label(source: str) -> str:
        return (overrides or {}).get(source) or translate_ui(source, locale)

    lines = [
        (bold_font, 24, 64, 742, label("INDUCTION CERTIFICATE")),
        (regular_font, 11, 64, 710, company),
        (regular_font, 11, 64, 663, label("This certifies that")),
        (bold_font, 21, 64, 628, worker),
        (regular_font, 11, 64, 591, label("has completed the following site induction:")),
        (bold_font, 15, 64, 562, induction),
        (regular_font, 10, 64, 530, f"{label('Site')}: {site or label('Not specified')}"),
        (regular_font, 10, 64, 510, f"{label('Completed')}: {completed_at}"),
        (regular_font, 10, 64, 490, f"{label('Valid until')}: {expires_at}"),
        (bold_font, 10, 64, 438, f"{label('Certificate')}: {certificate_number}"),
        (regular_font, 8, 64, 410, label("Verify this certificate using the QR code or address below:")),
        (regular_font, 7, 64, 392, verification_url),
        (regular_font, 8, 64, 62, f"{label('Generated by')} {brand_name} · {brand_tagline}. {label('Status must be checked online.')}"),
    ]
    for font, size, x, y, value in lines:
        canvas.setFont(font, size)
        canvas.drawString(x, y, str(value))
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=1)
    qr.add_data(verification_url)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    module_size = min(3.2, 122 / max(len(matrix), 1))
    canvas.setFillColorRGB(0, 0, 0)
    for row_index, row in enumerate(matrix):
        for column_index, active in enumerate(row):
            if active:
                canvas.rect(
                    414 + column_index * module_size,
                    530 + (len(matrix) - row_index - 1) * module_size,
                    module_size,
                    module_size,
                    fill=1,
                    stroke=0,
                )
    canvas.showPage()
    canvas.save()
    return output.getvalue()


def build_qr_svg(value: str, title: str = "QR code") -> bytes:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=2)
    qr.add_data(value)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    size = len(matrix)
    cells = []
    for row_index, row in enumerate(matrix):
        for column_index, active in enumerate(row):
            if active:
                cells.append(f'<rect x="{column_index}" y="{row_index}" width="1" height="1"/>')
    safe_title = html.escape(title)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" role="img" aria-label="{safe_title}" shape-rendering="crispEdges">'
        f'<title>{safe_title}</title><rect width="100%" height="100%" fill="white"/><g fill="#082f49">{"".join(cells)}</g></svg>'
    ).encode("utf-8")


def normalized_worker_profile(payload: dict, existing: dict | None = None) -> dict:
    profile = dict(existing or {})
    scalar_fields = (
        "name", "phone", "trade", "medical_information", "preferred_language",
        "emergency_contact_name", "emergency_contact_phone", "emergency_contact_address",
    )
    list_fields = (
        "skills", "qualifications", "certifications", "training_records", "inductions", "employment_history",
    )
    for field in scalar_fields:
        if field in payload:
            profile[field] = str(payload.get(field, "")).strip()[:2000]
    for field in list_fields:
        if field in payload:
            value = payload.get(field)
            if not isinstance(value, list):
                raise ValueError(f"{field} must be a list")
            profile[field] = value[:100]
    profile["preferred_language"] = normalize_language(profile.get("preferred_language"))
    profile.setdefault("skills", [])
    profile.setdefault("qualifications", [])
    profile.setdefault("certifications", [])
    profile.setdefault("training_records", [])
    profile.setdefault("inductions", [])
    profile.setdefault("employment_history", [])
    if "public_fields" in payload:
        requested = payload.get("public_fields")
        if not isinstance(requested, list):
            raise ValueError("public_fields must be a list")
        profile["public_fields"] = sorted(
            set(requested) & (WORKER_SHARE_FIELDS - {"email", "documents", "medical_information"})
        )
    profile.setdefault("public_fields", ["name", "trade"])
    return profile


def shared_worker_projection(connection, access_row) -> dict:
    access = dict(access_row)
    visible = set(json.loads(access["visible_fields"])) & WORKER_SHARE_FIELDS
    profile = json.loads(access["profile_payload"])
    projected = {field: profile.get(field) for field in visible if field not in {"email", "documents"}}
    if "email" in visible:
        projected["email"] = access["email"]
    if "documents" in visible:
        document_rows = connection.execute(
            """SELECT worker_documents.*,
                      COALESCE((SELECT status FROM worker_document_reviews
                                WHERE worker_document_reviews.document_id = worker_documents.id
                                  AND worker_document_reviews.company_id = ?
                                ORDER BY worker_document_reviews.id DESC LIMIT 1), 'unread') AS company_review_status
               FROM worker_documents WHERE worker_id = ? ORDER BY id DESC""",
            (access["company_id"], access["worker_id"]),
        ).fetchall()
        projected["documents"] = []
        for row in document_rows:
            document = {
                key: row[key]
                for key in ("id", "category", "title", "original_name", "mime_type", "size", "version", "expiry_date", "expiry_source", "expiry_confidence", "created_at", "updated_at")
            }
            document["review_status"] = row["company_review_status"]
            projected["documents"].append(document)
    return {
        "access_id": access["id"],
        "worker_id": access["worker_id"],
        "company_id": access["company_id"],
        "status": access["status"],
        "granted_at": access["granted_at"],
        "visible_fields": sorted(visible),
        "profile": projected,
    }


def create_in_app_notification(connection, company_id: int, recipient_type: str, recipient_id: int, kind: str, title: str, message: str, link: str = "") -> int:
    cursor = connection.execute(
        """INSERT INTO in_app_notifications(company_id, recipient_type, recipient_id, kind, title, message, link, read_at, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)""",
        (company_id, recipient_type, recipient_id, kind, title[:180], message[:1000], link[:500], utc_now()),
    )
    return int(cursor.lastrowid)


def notify_company_workflow_users(connection, company_id: int, kind: str, title: str, message: str, link: str = "", contact_user_id=None) -> list[int]:
    if contact_user_id:
        recipients = connection.execute("SELECT id FROM users WHERE id = ? AND company_id = ? AND active = 1", (contact_user_id, company_id)).fetchall()
    else:
        recipients = connection.execute("SELECT id FROM users WHERE company_id = ? AND active = 1 AND role IN ('admin', 'editor')", (company_id,)).fetchall()
    return [create_in_app_notification(connection, company_id, "user", int(row["id"]), kind, title, message, link) for row in recipients]


class KomplianceHandler(BaseHTTPRequestHandler):
    server_version = "KomplianceLocal/0.1"

    def log_message(self, format_string: str, *args) -> None:
        print(
            f"[{self.log_date_time_string()}] "
            f"{self.address_string()} {format_string % args}"
        )

    def send_security_headers(self, html_document: bool = False) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Permissions-Policy", "camera=(self), microphone=(), geolocation=(self)")
        if html_document:
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                "script-src 'self'; connect-src 'self'; object-src 'self'; base-uri 'self'; "
                "form-action 'self'; frame-ancestors 'none'",
            )

    def send_json(self, payload, status=HTTPStatus.OK, headers=None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_security_headers()
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
        self.send_security_headers(html_document=True)
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
        self.send_security_headers(html_document=content_type.startswith("text/html"))
        self.end_headers()
        with resolved.open("rb") as handle:
            while chunk := handle.read(256 * 1024):
                self.wfile.write(chunk)

    def send_local_file(self, folder: str, filename: str, company_id: int) -> None:
        resource_and_key = {
            "uploads": ("local_uploads", "stored_name"),
            "evidence": ("local_evidence", "stored_name"),
            "reports": ("local_submissions", "report_file"),
            "certificates": ("local_induction_completions", "certificate_file"),
        }
        resource, key = resource_and_key[folder]
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute("SELECT payload FROM records WHERE resource = ? AND company_id = ?", (resource, company_id)).fetchall()
        if not any(Path(str(json.loads(row["payload"]).get(key, ""))).name == Path(filename).name for row in rows):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
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
        self.send_security_headers()
        self.end_headers()
        with resolved.open("rb") as handle:
            while chunk := handle.read(256 * 1024):
                self.wfile.write(chunk)

    def send_worker_file(self, worker_id: int, stored_name: str, original_name: str, mime_type: str) -> None:
        root = (DATA_ROOT / "worker-documents" / str(worker_id)).resolve()
        try:
            resolved = (root / Path(stored_name).name).resolve(strict=True)
        except FileNotFoundError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if root not in resolved.parents:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        stat = resolved.stat()
        safe_name = Path(original_name).name.replace('"', "")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Content-Length", str(stat.st_size))
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("Content-Disposition", f'inline; filename="{safe_name}"')
        self.send_security_headers()
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
                "company_id": 1,
                "company_name": DEFAULT_SETTINGS["brand_company"],
                "platform_admin": 1,
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
                SELECT users.id, users.email, users.name, users.role, users.company_id,
                       users.platform_admin, users.mfa_enabled, companies.name AS company_name,
                       sessions.csrf_token, sessions.expires_at
                FROM sessions JOIN users ON users.id = sessions.user_id
                JOIN companies ON companies.id = users.company_id
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
                INSERT INTO audit_log(user_id, actor, action, resource, record_id, summary, created_at, company_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, actor, action, resource, record_id, summary[:500], utc_now(), int(user.get("company_id", 1)) if user else 1),
            )
            connection.commit()

    def write_worker_audit(self, worker, company_id: int, action: str, resource: str, record_id=None, summary="") -> None:
        with DB_LOCK, connect_database() as connection:
            connection.execute(
                """
                INSERT INTO audit_log(user_id, actor, action, resource, record_id, summary, created_at, company_id)
                VALUES (NULL, ?, ?, ?, ?, ?, ?, ?)
                """,
                (worker.get("email", "worker"), action, resource, record_id, summary[:500], utc_now(), company_id),
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

    def worker_session_token(self) -> str:
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get("Cookie", ""))
        except Exception:
            return ""
        morsel = cookies.get(WORKER_SESSION_COOKIE)
        return morsel.value if morsel else ""

    def current_worker(self):
        token = self.worker_session_token()
        if not token:
            return None
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                """
                SELECT worker_accounts.id, worker_accounts.email, worker_accounts.verified,
                       worker_profiles.payload, worker_profiles.public_token,
                       worker_sessions.csrf_token, worker_sessions.expires_at
                FROM worker_sessions
                JOIN worker_accounts ON worker_accounts.id = worker_sessions.worker_id
                JOIN worker_profiles ON worker_profiles.worker_id = worker_accounts.id
                WHERE worker_sessions.token_hash = ? AND worker_sessions.expires_at > ?
                  AND worker_accounts.active = 1 AND worker_accounts.verified = 1
                """,
                (digest, utc_now()),
            ).fetchone()
        if row is None:
            return None
        worker = dict(row)
        worker["profile"] = json.loads(worker.pop("payload"))
        return worker

    def require_worker(self):
        worker = self.current_worker()
        if worker is None:
            self.send_json({"error": "Worker authentication required."}, HTTPStatus.UNAUTHORIZED)
            return None
        return worker

    def require_worker_csrf(self, worker) -> bool:
        supplied = self.headers.get("X-CSRF-Token", "")
        if supplied and hmac.compare_digest(supplied, worker.get("csrf_token", "")):
            return True
        self.send_json({"error": "Invalid or missing worker CSRF token."}, HTTPStatus.FORBIDDEN)
        return False

    def create_worker_session(self, worker_id: int):
        raw_token = secrets.token_urlsafe(32)
        token_digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        csrf_token = secrets.token_urlsafe(24)
        now = utc_now()
        expires_at = (datetime.now(UTC) + timedelta(hours=WORKER_SESSION_HOURS)).replace(microsecond=0).isoformat()
        with DB_LOCK, connect_database() as connection:
            connection.execute("DELETE FROM worker_sessions WHERE expires_at <= ?", (now,))
            connection.execute(
                "INSERT INTO worker_sessions(token_hash, worker_id, csrf_token, expires_at, created_at) VALUES (?, ?, ?, ?, ?)",
                (token_digest, worker_id, csrf_token, expires_at, now),
            )
            connection.commit()
        cookie = f"{WORKER_SESSION_COOKIE}={raw_token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={WORKER_SESSION_HOURS * 3600}"
        if self.headers.get("X-Forwarded-Proto", "").lower() == "https":
            cookie += "; Secure"
        return csrf_token, cookie

    def application_base_url(self) -> str:
        configured = os.environ.get("KOMPLIANCE_BASE_URL", "").strip().rstrip("/")
        if configured:
            return configured
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
        with DB_LOCK, connect_database() as language_connection:
            locale = preferred_language_for_owner(
                language_connection, "user", int(user_row["id"])
            )
            company_id = int(user_row["company_id"]) if "company_id" in user_row.keys() else 1
            reset_subject = reviewed_server_message(
                language_connection, company_id, "user_reset_subject", locale
            )
            reset_body = reviewed_server_message(
                language_connection,
                company_id,
                "user_reset_body",
                locale,
                minutes=RESET_TOKEN_MINUTES,
                url=reset_url,
            )
        notification_payload = {
            "kind": "password_reset",
            "channel": "Email",
            "recipient": user_row["email"],
            "subject": reset_subject,
            "message": reset_body,
            "language": locale,
            "reset_url": reset_url,
            "delivery_status": "prepared",
            "status": "Prepared - not sent",
            "attempts": 0,
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
                "INSERT INTO records(resource, payload, created_at, updated_at, company_id) VALUES ('local_notifications', ?, ?, ?, ?)",
                (json.dumps(notification_payload), created_at, created_at, int(user_row["company_id"]) if "company_id" in user_row.keys() else 1),
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
                        "company_id": 1,
                        "company_name": DEFAULT_SETTINGS["brand_company"],
                        "platform_admin": 1,
                        "mfa_enabled": 0,
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
                "user": ({key: user.get(key) for key in ("name", "email", "role", "company_id", "company_name", "platform_admin", "mfa_enabled")} if user else None),
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
                INSERT INTO users(email, name, role, password_hash, active, created_at, updated_at, company_id, platform_admin)
                VALUES (?, ?, 'admin', ?, 1, ?, ?, 1, 1)
                """,
                (email, name, password_hash(password), now, now),
            )
            connection.commit()
            user_id = cursor.lastrowid
        csrf_token, cookie = self.create_session(user_id)
        user = {"id": user_id, "email": email, "name": name, "role": "admin", "company_id": 1, "company_name": DEFAULT_SETTINGS["brand_company"], "platform_admin": 1, "mfa_enabled": 0}
        self.write_audit(user, "setup", "auth", summary="Initial administrator created")
        self.send_json(
            {"authenticated": True, "user": {key: user.get(key) for key in ("name", "email", "role", "company_id", "company_name", "platform_admin", "mfa_enabled")}, "csrf_token": csrf_token},
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
        supplied_mfa = str(payload.get("mfa_code", "")).strip()
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                "SELECT users.*, companies.name AS company_name FROM users JOIN companies ON companies.id = users.company_id WHERE users.email = ?",
                (email,),
            ).fetchone()
            locked = bool(
                LOGIN_LOCKOUT_ENABLED
                and row
                and row["locked_until"]
                and row["locked_until"] > now
            )
            password_valid = bool(
                row
                and row["active"]
                and not locked
                and password_matches(password, row["password_hash"])
            )
            mfa_required = bool(password_valid and row["mfa_enabled"])
            mfa_missing = bool(mfa_required and not supplied_mfa)
            mfa_valid = bool(
                not mfa_required
                or (supplied_mfa and verify_user_mfa(connection, row, supplied_mfa))
            )
            valid = bool(password_valid and mfa_valid)
            if row and not valid and row["active"] and not locked:
                if not mfa_missing:
                    failures = int(row["failed_attempts"] or 0) + 1
                    locked_until = None
                    if LOGIN_LOCKOUT_ENABLED and failures >= LOGIN_MAX_ATTEMPTS:
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
        if mfa_missing:
            self.write_audit(dict(row), "login_mfa_challenge", "auth", summary="Password accepted; authenticator code required")
            self.send_json(
                {"authenticated": False, "mfa_required": True, "message": "Enter the code from your authenticator app or a backup code."},
                HTTPStatus.ACCEPTED,
            )
            return
        if not valid:
            action = "login_mfa_failed" if password_valid and mfa_required else "login_failed"
            self.write_audit(dict(row) if row else None, action, "auth", summary=f"Failed login for {email[:180]}")
            self.send_json({"error": "Invalid email, password, or authentication code."}, HTTPStatus.UNAUTHORIZED)
            return
        csrf_token, cookie = self.create_session(row["id"])
        user = dict(row)
        self.write_audit(user, "login", "auth", summary="Successful login with MFA" if mfa_required else "Successful login")
        self.send_json(
            {"authenticated": True, "user": {key: user.get(key) for key in ("name", "email", "role", "company_id", "company_name", "platform_admin", "mfa_enabled")}, "csrf_token": csrf_token},
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

    def handle_auth_mfa_status(self) -> None:
        user = self.require_user()
        if user is None:
            return
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                "SELECT mfa_enabled FROM users WHERE id = ?", (user["id"],)
            ).fetchone()
            remaining = connection.execute(
                "SELECT COUNT(*) FROM user_mfa_backup_codes WHERE user_id = ? AND used_at IS NULL",
                (user["id"],),
            ).fetchone()[0]
        self.send_json({"enabled": bool(row and row["mfa_enabled"]), "backup_codes_remaining": remaining})

    def handle_auth_mfa_setup(self) -> None:
        user = self.require_user()
        if user is None or not self.require_csrf(user):
            return
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        current_password = str(payload.get("password", ""))
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                "SELECT password_hash, mfa_enabled FROM users WHERE id = ?", (user["id"],)
            ).fetchone()
            if row is None or not password_matches(current_password, row["password_hash"]):
                self.send_json({"error": "Current password is incorrect."}, HTTPStatus.FORBIDDEN)
                return
            if row["mfa_enabled"]:
                self.send_json({"error": "Multi-factor authentication is already enabled."}, HTTPStatus.CONFLICT)
                return
            secret = generate_mfa_secret()
            connection.execute(
                "UPDATE users SET mfa_pending_secret = ?, updated_at = ? WHERE id = ?",
                (secret, utc_now(), user["id"]),
            )
            connection.commit()
        issuer = application_settings(int(user.get("company_id", 1))).get("brand_name", "Kompliance")
        label = f"{issuer}:{user['email']}"
        query = urlencode({"secret": secret, "issuer": issuer, "algorithm": "SHA1", "digits": MFA_DIGITS, "period": MFA_PERIOD_SECONDS})
        provisioning_uri = f"otpauth://totp/{quote(label)}?{query}"
        qr_svg = build_qr_svg(provisioning_uri, "Authenticator setup QR code")
        self.write_audit(user, "mfa_setup_started", "auth", summary="Authenticator enrolment started")
        self.send_json({
            "secret": secret,
            "provisioning_uri": provisioning_uri,
            "qr_data_url": "data:image/svg+xml;base64," + base64.b64encode(qr_svg).decode("ascii"),
        })

    def handle_auth_mfa_enable(self) -> None:
        user = self.require_user()
        if user is None or not self.require_csrf(user):
            return
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        code = str(payload.get("code", ""))
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                "SELECT mfa_pending_secret, mfa_enabled FROM users WHERE id = ?", (user["id"],)
            ).fetchone()
            if row is None or row["mfa_enabled"]:
                self.send_json({"error": "Multi-factor authentication is already enabled."}, HTTPStatus.CONFLICT)
                return
            secret = row["mfa_pending_secret"] or ""
            if not secret or not mfa_code_matches(secret, code):
                self.send_json({"error": "The authenticator code is invalid or expired."}, HTTPStatus.BAD_REQUEST)
                return
            backup_codes = generate_mfa_backup_codes()
            now = utc_now()
            connection.execute(
                "UPDATE users SET mfa_enabled = 1, mfa_secret = ?, mfa_pending_secret = NULL, updated_at = ? WHERE id = ?",
                (secret, now, user["id"]),
            )
            connection.execute("DELETE FROM user_mfa_backup_codes WHERE user_id = ?", (user["id"],))
            connection.executemany(
                "INSERT INTO user_mfa_backup_codes(user_id, code_hash, used_at, created_at) VALUES (?, ?, NULL, ?)",
                [(user["id"], mfa_backup_hash(item), now) for item in backup_codes],
            )
            current_digest = hashlib.sha256(self.session_token().encode("utf-8")).hexdigest()
            connection.execute(
                "DELETE FROM sessions WHERE user_id = ? AND token_hash <> ?", (user["id"], current_digest)
            )
            connection.commit()
        self.write_audit(user, "mfa_enabled", "auth", summary="Authenticator MFA enabled; other sessions revoked")
        self.send_json({"enabled": True, "backup_codes": backup_codes, "backup_codes_remaining": len(backup_codes)})

    def handle_auth_mfa_disable(self) -> None:
        user = self.require_user()
        if user is None or not self.require_csrf(user):
            return
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        password = str(payload.get("password", ""))
        code = str(payload.get("code", ""))
        with DB_LOCK, connect_database() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
            if row is None or not row["mfa_enabled"]:
                self.send_json({"error": "Multi-factor authentication is not enabled."}, HTTPStatus.CONFLICT)
                return
            if not password_matches(password, row["password_hash"]):
                self.send_json({"error": "Current password is incorrect."}, HTTPStatus.FORBIDDEN)
                return
            if not verify_user_mfa(connection, row, code):
                self.send_json({"error": "The authentication code is invalid or expired."}, HTTPStatus.BAD_REQUEST)
                return
            connection.execute(
                "UPDATE users SET mfa_enabled = 0, mfa_secret = NULL, mfa_pending_secret = NULL, updated_at = ? WHERE id = ?",
                (utc_now(), user["id"]),
            )
            connection.execute("DELETE FROM user_mfa_backup_codes WHERE user_id = ?", (user["id"],))
            current_digest = hashlib.sha256(self.session_token().encode("utf-8")).hexdigest()
            connection.execute(
                "DELETE FROM sessions WHERE user_id = ? AND token_hash <> ?", (user["id"], current_digest)
            )
            connection.commit()
        self.write_audit(user, "mfa_disabled", "auth", summary="Authenticator MFA disabled; other sessions revoked")
        self.send_json({"enabled": False, "backup_codes_remaining": 0})

    def handle_auth_recovery_request(self) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        email = str(payload.get("email", "")).strip().lower()
        remote_address = str(self.client_address[0] if self.client_address else "unknown")
        rate_key = hashlib.sha256(
            f"recovery:{remote_address}:{email}".encode("utf-8")
        ).hexdigest()
        address_key = hashlib.sha256(f"recovery-address:{remote_address}".encode("utf-8")).hexdigest()
        email_allowed = recovery_rate_limit_allowed(rate_key)
        address_allowed = recovery_rate_limit_allowed(address_key)
        allowed = email_allowed and address_allowed
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                "SELECT id, email, name, company_id FROM users WHERE email = ? AND active = 1", (email,)
            ).fetchone()
        if row and allowed:
            _, _, notification_id = self.issue_password_reset(row)
            delivery = dispatch_notification_queue(limit=1, record_ids={notification_id}, company_id=int(row["company_id"]))
            self.write_audit(None, "password_reset_requested", "auth", summary=f"Reset prepared for {email[:180]}")
            if delivery.get("sent"):
                self.write_audit(None, "password_reset_sent", "auth", summary="Password reset email delivered")
        elif row:
            self.write_audit(None, "password_reset_rate_limited", "auth", summary="Recovery rate limit applied")
        else:
            self.write_audit(None, "password_reset_requested", "auth", summary="Reset requested for unknown account")
        time.sleep(0.15)
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

    def handle_worker_register(self) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        name = str(payload.get("name", "")).strip()
        if "@" not in email or len(password) < 12 or not name:
            self.send_json({"error": "Name, valid email and a 12-character password are required."}, HTTPStatus.BAD_REQUEST)
            return
        verification_required = os.environ.get("KOMPLIANCE_WORKER_EMAIL_VERIFICATION", "1").strip() == "1"
        now = utc_now()
        profile = normalized_worker_profile(payload)
        profile["name"] = name
        locale = normalize_language(profile.get("preferred_language"))
        profile["preferred_language"] = locale
        verification_subject = server_message("verify_subject", locale)
        raw_verification = secrets.token_urlsafe(32)
        verification_digest = hashlib.sha256(raw_verification.encode("utf-8")).hexdigest()
        verification_url = f"{self.application_base_url()}/worker/?verify={raw_verification}"
        expires_at = (datetime.now(UTC) + timedelta(hours=24)).replace(microsecond=0).isoformat()
        notification_id = None
        try:
            with DB_LOCK, connect_database() as connection:
                cursor = connection.execute(
                    "INSERT INTO worker_accounts(email, password_hash, verified, active, created_at, updated_at) VALUES (?, ?, ?, 1, ?, ?)",
                    (email, password_hash(password), 0 if verification_required else 1, now, now),
                )
                worker_id = cursor.lastrowid
                connection.execute(
                    "INSERT INTO worker_profiles(worker_id, public_token, payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (worker_id, secrets.token_urlsafe(24), json.dumps(profile), now, now),
                )
                connection.execute(
                    """
                    INSERT INTO notification_preferences(owner_type, owner_id, preferred_language, updated_at)
                    VALUES ('worker', ?, ?, ?)
                    ON CONFLICT(owner_type, owner_id) DO UPDATE SET
                        preferred_language = excluded.preferred_language,
                        updated_at = excluded.updated_at
                    """,
                    (worker_id, locale, now),
                )
                if verification_required:
                    connection.execute(
                        "INSERT INTO worker_verification_tokens(token_hash, worker_id, expires_at, used_at, created_at) VALUES (?, ?, ?, NULL, ?)",
                        (verification_digest, worker_id, expires_at, now),
                    )
                    notification_cursor = connection.execute(
                        "INSERT INTO worker_notifications(worker_id, kind, recipient, subject, message, status, attempts, created_at, updated_at) VALUES (?, 'email_verification', ?, ?, ?, 'prepared', 0, ?, ?)",
                        (
                            worker_id,
                            email,
                            verification_subject,
                            server_message("verify_body", locale, url=verification_url),
                            now,
                            now,
                        ),
                    )
                    notification_id = notification_cursor.lastrowid
                connection.commit()
        except sqlite3.IntegrityError:
            self.send_json({"error": "A worker account with this email already exists."}, HTTPStatus.CONFLICT)
            return
        response = {"registered": True, "verification_required": verification_required}
        email_configuration = public_email_configuration()
        if verification_required and email_configuration["enabled"] and email_configuration["configured"]:
            try:
                send_notification_email({
                    "recipient": email,
                    "subject": verification_subject,
                    "message": server_message("verify_body", locale, url=verification_url),
                    "language": locale,
                })
                with DB_LOCK, connect_database() as connection:
                    connection.execute("UPDATE worker_notifications SET status = 'sent', attempts = 1, updated_at = ? WHERE id = ?", (utc_now(), notification_id))
                    connection.commit()
                response["delivery_status"] = "sent"
            except Exception as error:
                with DB_LOCK, connect_database() as connection:
                    connection.execute("UPDATE worker_notifications SET status = 'failed', attempts = 1, last_error = ?, updated_at = ? WHERE id = ?", (str(error)[:500], utc_now(), notification_id))
                    connection.commit()
                response["delivery_status"] = "failed"
        if verification_required and (not email_configuration["enabled"] or not email_configuration["configured"]):
            response["verification_url"] = verification_url
        if not verification_required:
            csrf_token, cookie = self.create_worker_session(worker_id)
            response.update({"authenticated": True, "csrf_token": csrf_token})
            self.send_json(response, HTTPStatus.CREATED, {"Set-Cookie": cookie})
            return
        self.send_json(response, HTTPStatus.CREATED)

    def handle_worker_verify(self, query: str) -> None:
        token = parse_qs(query).get("token", [""])[0].strip()
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest() if token else ""
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                "SELECT worker_id FROM worker_verification_tokens WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
                (digest, now),
            ).fetchone()
            if row is None:
                self.send_json({"error": "Verification link is invalid or expired."}, HTTPStatus.BAD_REQUEST)
                return
            connection.execute("UPDATE worker_accounts SET verified = 1, updated_at = ? WHERE id = ?", (now, row["worker_id"]))
            connection.execute("UPDATE worker_verification_tokens SET used_at = ? WHERE token_hash = ?", (now, digest))
            connection.commit()
        csrf_token, cookie = self.create_worker_session(row["worker_id"])
        self.send_json({"verified": True, "authenticated": True, "csrf_token": csrf_token}, headers={"Set-Cookie": cookie})

    def handle_worker_login(self) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            row = connection.execute("SELECT * FROM worker_accounts WHERE email = ?", (email,)).fetchone()
            locked = bool(
                LOGIN_LOCKOUT_ENABLED
                and row
                and row["locked_until"]
                and row["locked_until"] > now
            )
            valid = bool(row and row["active"] and row["verified"] and not locked and password_matches(password, row["password_hash"]))
            if row and not valid and row["active"] and row["verified"] and not locked:
                failures = int(row["failed_attempts"] or 0) + 1
                locked_until = (
                    (datetime.now(UTC) + timedelta(minutes=LOGIN_LOCK_MINUTES))
                    .replace(microsecond=0)
                    .isoformat()
                    if LOGIN_LOCKOUT_ENABLED and failures >= LOGIN_MAX_ATTEMPTS
                    else None
                )
                connection.execute("UPDATE worker_accounts SET failed_attempts = ?, locked_until = ?, updated_at = ? WHERE id = ?", (failures, locked_until, now, row["id"]))
                connection.commit()
            elif valid:
                connection.execute("UPDATE worker_accounts SET failed_attempts = 0, locked_until = NULL, updated_at = ? WHERE id = ?", (now, row["id"]))
                connection.commit()
        if locked:
            self.send_json({"error": "Worker account temporarily locked."}, HTTPStatus.TOO_MANY_REQUESTS)
            return
        if not valid:
            message = "Verify your email before signing in." if row and not row["verified"] else "Invalid email or password."
            self.send_json({"error": message}, HTTPStatus.UNAUTHORIZED)
            return
        csrf_token, cookie = self.create_worker_session(row["id"])
        self.send_json({"authenticated": True, "csrf_token": csrf_token}, headers={"Set-Cookie": cookie})

    def handle_worker_status(self) -> None:
        worker = self.current_worker()
        self.send_json({
            "authenticated": worker is not None,
            "worker": ({"id": worker["id"], "email": worker["email"], "profile": worker["profile"], "public_token": worker["public_token"]} if worker else None),
            "csrf_token": worker.get("csrf_token", "") if worker else "",
        })

    def handle_worker_logout(self, worker) -> None:
        token = self.worker_session_token()
        if token:
            with DB_LOCK, connect_database() as connection:
                connection.execute("DELETE FROM worker_sessions WHERE token_hash = ?", (hashlib.sha256(token.encode("utf-8")).hexdigest(),))
                connection.commit()
        self.send_json({"logged_out": True}, headers={"Set-Cookie": f"{WORKER_SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"})

    def handle_worker_profile_update(self, worker) -> None:
        try:
            payload = self.read_json_body()
            profile = normalized_worker_profile(payload, worker["profile"])
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        if not profile.get("name"):
            self.send_json({"error": "Worker name is required."}, HTTPStatus.BAD_REQUEST)
            return
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            connection.execute("UPDATE worker_profiles SET payload = ?, updated_at = ? WHERE worker_id = ?", (json.dumps(profile), now, worker["id"]))
            connection.commit()
        self.send_json({"profile": profile, "updated_at": now})

    def handle_worker_documents_get(self, worker) -> None:
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute("SELECT * FROM worker_documents WHERE worker_id = ? ORDER BY id DESC", (worker["id"],)).fetchall()
        self.send_json({"data": [dict(row) for row in rows], "categories": sorted(WORKER_DOCUMENT_CATEGORIES)})

    def handle_worker_document_upload(self, worker) -> None:
        category = unquote(self.headers.get("X-Document-Category", "Other")).strip()
        title = unquote(self.headers.get("X-Document-Title", "")).strip()
        original_name = Path(unquote(self.headers.get("X-File-Name", "document.bin"))).name
        expiry_date = unquote(self.headers.get("X-Expiry-Date", "")).strip()
        extension = Path(original_name).suffix.lower()
        allowed_extensions = {".pdf", ".csv", ".xlsx", ".xls", ".docx", ".doc", ".png", ".jpg", ".jpeg", ".webp"}
        if category not in WORKER_DOCUMENT_CATEGORIES or not title or extension not in allowed_extensions:
            self.send_json({"error": "A valid category, title and supported document are required."}, HTTPStatus.BAD_REQUEST)
            return
        if expiry_date and parse_record_date(expiry_date) is None:
            self.send_json({"error": "Expiry date is invalid."}, HTTPStatus.BAD_REQUEST)
            return
        try:
            content = self.read_raw_body()
        except ValueError as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        if expiry_date:
            expiry_source = "manual"
            expiry_confidence = "confirmed"
        else:
            expiry_date, expiry_source, expiry_confidence = extract_document_expiry(content, original_name, title)
        folder = DATA_ROOT / "worker-documents" / str(worker["id"])
        folder.mkdir(parents=True, exist_ok=True)
        stored_name = f"{worker['id']}-{secrets.token_hex(12)}{extension}"
        (folder / stored_name).write_bytes(content)
        now = utc_now()
        mime_type = mimetypes.guess_type(original_name)[0] or "application/octet-stream"
        with DB_LOCK, connect_database() as connection:
            version = 1 + connection.execute("SELECT COUNT(*) FROM worker_documents WHERE worker_id = ? AND category = ? AND title = ? COLLATE NOCASE", (worker["id"], category, title)).fetchone()[0]
            cursor = connection.execute(
                "INSERT INTO worker_documents(worker_id, category, title, original_name, stored_name, mime_type, size, version, expiry_date, expiry_source, expiry_confidence, review_status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'unread', ?, ?)",
                (worker["id"], category, title, original_name, stored_name, mime_type, len(content), version, expiry_date or None, expiry_source, expiry_confidence, now, now),
            )
            connection.commit()
        self.send_json({"id": cursor.lastrowid, "category": category, "title": title, "original_name": original_name, "stored_name": stored_name, "size": len(content), "version": version, "expiry_date": expiry_date or None, "expiry_source": expiry_source, "expiry_confidence": expiry_confidence, "review_status": "unread"}, HTTPStatus.CREATED)

    def handle_worker_document_delete(self, worker, document_id: int) -> None:
        with DB_LOCK, connect_database() as connection:
            row = connection.execute("SELECT stored_name FROM worker_documents WHERE id = ? AND worker_id = ?", (document_id, worker["id"])).fetchone()
            if row is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            connection.execute("DELETE FROM worker_documents WHERE id = ? AND worker_id = ?", (document_id, worker["id"]))
            connection.commit()
        path = DATA_ROOT / "worker-documents" / str(worker["id"]) / row["stored_name"]
        if path.is_file():
            path.unlink()
        self.send_json({"deleted": True, "id": document_id})

    def handle_worker_shares_get(self, worker) -> None:
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute("SELECT worker_company_access.*, companies.name AS company_name FROM worker_company_access JOIN companies ON companies.id = worker_company_access.company_id WHERE worker_id = ? ORDER BY companies.name", (worker["id"],)).fetchall()
        data = []
        for row in rows:
            item = dict(row)
            item["visible_fields"] = json.loads(item["visible_fields"])
            item["share_url"] = f"{self.application_base_url()}/worker/share/{item['share_token']}"
            data.append(item)
        self.send_json({"data": data, "available_fields": sorted(WORKER_SHARE_FIELDS)})

    def handle_worker_share_create(self, worker) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        company_id = int(payload.get("company_id", 0)) if str(payload.get("company_id", "")).isdigit() else 0
        visible_fields = sorted(set(payload.get("visible_fields") or []) & WORKER_SHARE_FIELDS)
        if not company_id or not visible_fields:
            self.send_json({"error": "Company and at least one shared field are required."}, HTTPStatus.BAD_REQUEST)
            return
        with DB_LOCK, connect_database() as connection:
            company = connection.execute("SELECT id FROM companies WHERE id = ? AND active = 1", (company_id,)).fetchone()
            if company is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            now = utc_now()
            token = secrets.token_urlsafe(24)
            connection.execute(
                "INSERT INTO worker_company_access(worker_id, company_id, share_token, visible_fields, status, granted_at, revoked_at) VALUES (?, ?, ?, ?, 'active', ?, NULL) ON CONFLICT(worker_id, company_id) DO UPDATE SET share_token = excluded.share_token, visible_fields = excluded.visible_fields, status = 'active', granted_at = excluded.granted_at, revoked_at = NULL",
                (worker["id"], company_id, token, json.dumps(visible_fields), now),
            )
            connection.commit()
        self.send_json({"shared": True, "company_id": company_id, "visible_fields": visible_fields, "share_url": f"{self.application_base_url()}/worker/share/{token}"}, HTTPStatus.CREATED)

    def handle_worker_share_revoke(self, worker, access_id: int) -> None:
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            cursor = connection.execute("UPDATE worker_company_access SET status = 'revoked', revoked_at = ? WHERE id = ? AND worker_id = ?", (now, access_id, worker["id"]))
            connection.commit()
        if not cursor.rowcount:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_json({"revoked": True, "id": access_id, "revoked_at": now})

    def handle_company_access_requests_get(self, user) -> None:
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute(
                """SELECT worker_access_requests.*, worker_profiles.payload AS profile_payload,
                          users.name AS requested_by_name
                   FROM worker_access_requests
                   JOIN worker_profiles ON worker_profiles.worker_id = worker_access_requests.worker_id
                   LEFT JOIN users ON users.id = worker_access_requests.requested_by_user_id
                   WHERE worker_access_requests.company_id = ?
                   ORDER BY CASE worker_access_requests.status WHEN 'pending' THEN 0 ELSE 1 END,
                            worker_access_requests.created_at DESC""",
                (user["company_id"],),
            ).fetchall()
        data = []
        for row in rows:
            item = dict(row)
            profile = json.loads(item.pop("profile_payload"))
            public_fields = set(profile.get("public_fields", ["name", "trade"])) & (WORKER_SHARE_FIELDS - {"email", "documents"})
            item["worker"] = {
                field: profile.get(field)
                for field in sorted(public_fields)
            }
            item["requested_fields"] = json.loads(item["requested_fields"])
            item["response_fields"] = json.loads(item["response_fields"] or "[]")
            data.append(item)
        self.send_json({"data": data, "available_fields": sorted(WORKER_SHARE_FIELDS)})

    def handle_company_access_request_create(self, user) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        qr_value = str(payload.get("qr_value", "")).strip()
        requested_fields = sorted(set(payload.get("requested_fields") or []) & WORKER_SHARE_FIELDS)
        message = str(payload.get("message", "")).strip()[:1000]
        parsed_qr = urlparse(qr_value)
        if parsed_qr.scheme or parsed_qr.netloc:
            parts = parsed_qr.path.strip("/").split("/")
            public_token = parts[2] if len(parts) == 3 and parts[:2] == ["worker", "public"] else ""
        else:
            public_token = qr_value
        if not public_token or len(public_token) > 200 or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in public_token):
            self.send_json({"error": "Paste or scan a valid Kompliance worker QR link."}, HTTPStatus.BAD_REQUEST)
            return
        if not requested_fields:
            self.send_json({"error": "Choose at least one field to request."}, HTTPStatus.BAD_REQUEST)
            return
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            worker = connection.execute(
                """SELECT worker_accounts.id, worker_profiles.payload
                   FROM worker_accounts JOIN worker_profiles ON worker_profiles.worker_id = worker_accounts.id
                   WHERE worker_profiles.public_token = ? AND worker_accounts.active = 1 AND worker_accounts.verified = 1""",
                (public_token,),
            ).fetchone()
            if worker is None:
                self.send_json({"error": "That worker QR is invalid or inactive."}, HTTPStatus.NOT_FOUND)
                return
            active = connection.execute(
                "SELECT id FROM worker_company_access WHERE company_id = ? AND worker_id = ? AND status = 'active'",
                (user["company_id"], worker["id"]),
            ).fetchone()
            if active:
                self.send_json({"error": "This worker has already granted active access to your company.", "access_id": active["id"]}, HTTPStatus.CONFLICT)
                return
            pending = connection.execute(
                "SELECT id FROM worker_access_requests WHERE company_id = ? AND worker_id = ? AND status = 'pending'",
                (user["company_id"], worker["id"]),
            ).fetchone()
            if pending:
                self.send_json({"error": "An access request is already waiting for this worker.", "request_id": pending["id"]}, HTTPStatus.CONFLICT)
                return
            cursor = connection.execute(
                """INSERT INTO worker_access_requests(
                       company_id, worker_id, requested_by_user_id, requested_fields, message,
                       status, response_fields, responded_at, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, 'pending', NULL, NULL, ?, ?)""",
                (user["company_id"], worker["id"], user["id"], json.dumps(requested_fields), message, now, now),
            )
            company = connection.execute("SELECT name FROM companies WHERE id = ?", (user["company_id"],)).fetchone()
            create_in_app_notification(
                connection, user["company_id"], "worker", int(worker["id"]), "access_request",
                "Company access request",
                f"{company['name']} requested access to {len(requested_fields)} worker passport field{'s' if len(requested_fields) != 1 else ''}.",
                "/worker/#inbox",
            )
            connection.commit()
            request_id = int(cursor.lastrowid)
        self.write_audit(user, "worker_access_requested", "worker_access_requests", request_id, f"Requested worker passport fields: {', '.join(requested_fields)}")
        self.send_json({"id": request_id, "status": "pending", "requested_fields": requested_fields, "created_at": now}, HTTPStatus.CREATED)

    def handle_worker_access_requests_get(self, worker) -> None:
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute(
                """SELECT worker_access_requests.*, companies.name AS company_name, companies.slug AS company_slug,
                          users.name AS requested_by_name
                   FROM worker_access_requests
                   JOIN companies ON companies.id = worker_access_requests.company_id
                   LEFT JOIN users ON users.id = worker_access_requests.requested_by_user_id
                   WHERE worker_access_requests.worker_id = ?
                   ORDER BY CASE worker_access_requests.status WHEN 'pending' THEN 0 ELSE 1 END,
                            worker_access_requests.created_at DESC""",
                (worker["id"],),
            ).fetchall()
        data = []
        for row in rows:
            item = dict(row)
            item["requested_fields"] = json.loads(item["requested_fields"])
            item["response_fields"] = json.loads(item["response_fields"] or "[]")
            data.append(item)
        self.send_json({"data": data, "available_fields": sorted(WORKER_SHARE_FIELDS)})

    def handle_worker_access_request_respond(self, worker, request_id: int) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        decision = str(payload.get("decision", "")).strip().lower()
        if decision not in {"approved", "declined"}:
            self.send_json({"error": "Decision must be approved or declined."}, HTTPStatus.BAD_REQUEST)
            return
        now = utc_now()
        share_token = ""
        visible_fields = []
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                """SELECT worker_access_requests.*, companies.name AS company_name
                   FROM worker_access_requests JOIN companies ON companies.id = worker_access_requests.company_id
                   WHERE worker_access_requests.id = ? AND worker_access_requests.worker_id = ?""",
                (request_id, worker["id"]),
            ).fetchone()
            if row is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if row["status"] != "pending":
                self.send_json({"error": "This access request has already been answered."}, HTTPStatus.CONFLICT)
                return
            requested = set(json.loads(row["requested_fields"])) & WORKER_SHARE_FIELDS
            if decision == "approved":
                supplied = payload.get("visible_fields")
                if not isinstance(supplied, list):
                    self.send_json({"error": "Choose the fields you approve."}, HTTPStatus.BAD_REQUEST)
                    return
                visible_fields = sorted(set(supplied) & requested & WORKER_SHARE_FIELDS)
                if not visible_fields:
                    self.send_json({"error": "Approve at least one requested field or decline the request."}, HTTPStatus.BAD_REQUEST)
                    return
                share_token = secrets.token_urlsafe(24)
                connection.execute(
                    """INSERT INTO worker_company_access(worker_id, company_id, share_token, visible_fields, status, granted_at, revoked_at)
                       VALUES (?, ?, ?, ?, 'active', ?, NULL)
                       ON CONFLICT(worker_id, company_id) DO UPDATE SET share_token = excluded.share_token,
                           visible_fields = excluded.visible_fields, status = 'active', granted_at = excluded.granted_at,
                           revoked_at = NULL""",
                    (worker["id"], row["company_id"], share_token, json.dumps(visible_fields), now),
                )
            connection.execute(
                """UPDATE worker_access_requests SET status = ?, response_fields = ?, responded_at = ?, updated_at = ?
                   WHERE id = ? AND worker_id = ? AND status = 'pending'""",
                (decision, json.dumps(visible_fields), now, now, request_id, worker["id"]),
            )
            notify_company_workflow_users(
                connection, int(row["company_id"]), "access_request_response", "Worker access request answered",
                f"{worker['profile'].get('name') or 'A worker'} {decision} the passport access request.",
                "/shared-workers",
            )
            connection.commit()
            company_id = int(row["company_id"])
        self.write_worker_audit(worker, company_id, f"worker_access_{decision}", "worker_access_requests", request_id, f"Worker {decision} fields: {', '.join(visible_fields)}")
        response = {"id": request_id, "status": decision, "visible_fields": visible_fields, "responded_at": now}
        if share_token:
            response["share_url"] = f"{self.application_base_url()}/worker/share/{share_token}"
        self.send_json(response)

    def handle_public_companies(self) -> None:
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute("SELECT id, name, slug FROM companies WHERE active = 1 ORDER BY name").fetchall()
        self.send_json({"data": [dict(row) for row in rows]})

    def handle_worker_recovery_request(self) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        email = str(payload.get("email", "")).strip().lower()
        raw_token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        now = utc_now()
        expires_at = (datetime.now(UTC) + timedelta(minutes=RESET_TOKEN_MINUTES)).replace(microsecond=0).isoformat()
        reset_url = f"{self.application_base_url()}/worker/?reset={raw_token}"
        worker_id = None
        notification_id = None
        locale = "en-IE"
        with DB_LOCK, connect_database() as connection:
            row = connection.execute("SELECT id FROM worker_accounts WHERE email = ? AND active = 1", (email,)).fetchone()
            if row:
                worker_id = int(row["id"])
                locale = preferred_language_for_owner(connection, "worker", worker_id)
                connection.execute(
                    "INSERT INTO worker_reset_tokens(token_hash, worker_id, expires_at, used_at, created_at) VALUES (?, ?, ?, NULL, ?)",
                    (digest, worker_id, expires_at, now),
                )
                notification_cursor = connection.execute(
                    "INSERT INTO worker_notifications(worker_id, kind, recipient, subject, message, status, attempts, created_at, updated_at) VALUES (?, 'password_reset', ?, ?, ?, 'prepared', 0, ?, ?)",
                    (
                        worker_id,
                        email,
                        server_message("worker_reset_subject", locale),
                        server_message("worker_reset_body", locale, minutes=RESET_TOKEN_MINUTES, url=reset_url),
                        now,
                        now,
                    ),
                )
                notification_id = notification_cursor.lastrowid
                connection.commit()
        response = {"accepted": True, "message": "If the worker account exists, a reset message has been prepared."}
        configuration = public_email_configuration()
        if worker_id and (not configuration["enabled"] or not configuration["configured"]):
            response["reset_url"] = reset_url
        elif worker_id:
            try:
                send_notification_email({
                    "recipient": email,
                    "subject": server_message("worker_reset_subject", locale),
                    "message": server_message("worker_reset_body", locale, minutes=RESET_TOKEN_MINUTES, url=reset_url),
                    "language": locale,
                })
                with DB_LOCK, connect_database() as connection:
                    connection.execute("UPDATE worker_notifications SET status = 'sent', attempts = 1, updated_at = ? WHERE id = ?", (utc_now(), notification_id))
                    connection.commit()
            except Exception as error:
                with DB_LOCK, connect_database() as connection:
                    connection.execute("UPDATE worker_notifications SET status = 'failed', attempts = 1, last_error = ?, updated_at = ? WHERE id = ?", (str(error)[:500], utc_now(), notification_id))
                    connection.commit()
        time.sleep(0.15)
        self.send_json(response, HTTPStatus.ACCEPTED)

    def handle_worker_recovery_reset(self) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        token = str(payload.get("token", "")).strip()
        password = str(payload.get("password", ""))
        if not token or len(password) < 12:
            self.send_json({"error": "A valid token and 12-character password are required."}, HTTPStatus.BAD_REQUEST)
            return
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                "SELECT worker_id FROM worker_reset_tokens WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
                (digest, now),
            ).fetchone()
            if row is None:
                self.send_json({"error": "This reset link is invalid or expired."}, HTTPStatus.BAD_REQUEST)
                return
            connection.execute(
                "UPDATE worker_accounts SET password_hash = ?, failed_attempts = 0, locked_until = NULL, updated_at = ? WHERE id = ?",
                (password_hash(password), now, row["worker_id"]),
            )
            connection.execute("UPDATE worker_reset_tokens SET used_at = ? WHERE token_hash = ?", (now, digest))
            connection.execute("DELETE FROM worker_sessions WHERE worker_id = ?", (row["worker_id"],))
            connection.commit()
        self.send_json({"reset": True})

    def handle_worker_qr(self, worker) -> None:
        url = f"{self.application_base_url()}/worker/public/{worker['public_token']}"
        body = build_qr_svg(url, "Worker profile QR code")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/svg+xml")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "private, no-store")
        self.send_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def handle_worker_document_file(self, worker, document_id: int) -> None:
        with DB_LOCK, connect_database() as connection:
            row = connection.execute("SELECT * FROM worker_documents WHERE id = ? AND worker_id = ?", (document_id, worker["id"])).fetchone()
        if row is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_worker_file(row["worker_id"], row["stored_name"], row["original_name"], row["mime_type"])

    def handle_public_worker_profile(self, token: str) -> None:
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                "SELECT worker_profiles.payload FROM worker_profiles JOIN worker_accounts ON worker_accounts.id = worker_profiles.worker_id WHERE public_token = ? AND worker_accounts.active = 1 AND worker_accounts.verified = 1",
                (token,),
            ).fetchone()
        if row is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        profile = json.loads(row["payload"])
        fields = set(profile.get("public_fields", ["name", "trade"])) & (WORKER_SHARE_FIELDS - {"email", "documents"})
        labels = {field: field.replace("_", " ").title() for field in fields}
        items = "".join(
            f"<dt>{html.escape(labels[field])}</dt><dd>{html.escape(', '.join(map(str, profile.get(field, []))) if isinstance(profile.get(field), list) else str(profile.get(field, '') or '—'))}</dd>"
            for field in sorted(fields)
        )
        self.send_html(f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Worker profile</title></head><body style='margin:0;background:#edf5f3;font-family:system-ui;color:#15324b'><main style='max-width:680px;margin:8vh auto;background:#fff;border-radius:20px;padding:2rem;box-shadow:0 20px 70px #15324b20'><div style='color:#087863;font-weight:800;letter-spacing:.08em'>KOMPLIANCE WORKER</div><h1>Verified worker profile</h1><p>This worker controls which fields are public. Company-specific documents and details require explicit consent.</p><dl style='display:grid;grid-template-columns:11rem 1fr;gap:.8rem;border-top:1px solid #d9e7e3;padding-top:1.5rem'>{items}</dl></main></body></html>""")

    def handle_public_worker_share(self, token: str) -> None:
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                """SELECT worker_company_access.*, worker_accounts.email, worker_profiles.payload AS profile_payload,
                          companies.name AS company_name
                   FROM worker_company_access
                   JOIN worker_accounts ON worker_accounts.id = worker_company_access.worker_id
                   JOIN worker_profiles ON worker_profiles.worker_id = worker_company_access.worker_id
                   JOIN companies ON companies.id = worker_company_access.company_id
                   WHERE worker_company_access.share_token = ? AND worker_company_access.status = 'active'
                     AND worker_accounts.active = 1""",
                (token,),
            ).fetchone()
            projection = shared_worker_projection(connection, row) if row else None
        if projection is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        profile = projection["profile"]
        items = []
        for field, value in profile.items():
            if field == "documents":
                links = "".join(
                    f"<li><a href='/worker/share/{html.escape(token)}/documents/{doc['id']}'>{html.escape(doc['title'])}</a> · {html.escape(doc['category'])} · v{doc['version']}</li>"
                    for doc in value
                )
                items.append(f"<dt>Documents</dt><dd><ul>{links or '<li>None shared</li>'}</ul></dd>")
            else:
                rendered = ", ".join(map(str, value)) if isinstance(value, list) else str(value or "—")
                items.append(f"<dt>{html.escape(field.replace('_', ' ').title())}</dt><dd>{html.escape(rendered)}</dd>")
        self.send_html(f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Consented worker profile</title></head><body style='margin:0;background:#edf5f3;font-family:system-ui;color:#15324b'><main style='max-width:760px;margin:6vh auto;background:#fff;border-radius:20px;padding:2rem;box-shadow:0 20px 70px #15324b20'><div style='color:#087863;font-weight:800'>CONSENTED SHARE</div><h1>Worker profile for {html.escape(str(row['company_name']))}</h1><p>The worker can revoke this access at any time.</p><dl style='display:grid;grid-template-columns:11rem 1fr;gap:.9rem;border-top:1px solid #d9e7e3;padding-top:1.5rem'>{''.join(items)}</dl></main></body></html>""")

    def handle_public_shared_document(self, token: str, document_id: int) -> None:
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                """SELECT worker_documents.* FROM worker_company_access
                   JOIN worker_documents ON worker_documents.worker_id = worker_company_access.worker_id
                   WHERE worker_company_access.share_token = ? AND worker_company_access.status = 'active'
                     AND worker_documents.id = ? AND worker_company_access.visible_fields LIKE '%documents%'""",
                (token, document_id),
            ).fetchone()
        if row is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_worker_file(row["worker_id"], row["stored_name"], row["original_name"], row["mime_type"])

    def handle_companies_get(self, user) -> None:
        with DB_LOCK, connect_database() as connection:
            if user.get("platform_admin"):
                rows = connection.execute("SELECT id, name, slug, active, created_at FROM companies ORDER BY name").fetchall()
            else:
                rows = connection.execute("SELECT id, name, slug, active, created_at FROM companies WHERE id = ?", (user["company_id"],)).fetchall()
        self.send_json({"data": [dict(row) for row in rows]})

    def handle_company_create(self, user) -> None:
        if not user.get("platform_admin"):
            self.send_json({"error": "Platform administrator role required."}, HTTPStatus.FORBIDDEN)
            return
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        name = str(payload.get("name", "")).strip()
        admin_name = str(payload.get("admin_name", "")).strip()
        admin_email = str(payload.get("admin_email", "")).strip().lower()
        admin_password = str(payload.get("admin_password", ""))
        slug = "-".join("".join(character.lower() if character.isalnum() else " " for character in name).split())[:60]
        if not name or not slug or not admin_name or "@" not in admin_email or len(admin_password) < 12:
            self.send_json({"error": "Company name and an administrator with a valid email and 12-character password are required."}, HTTPStatus.BAD_REQUEST)
            return
        now = utc_now()
        try:
            with DB_LOCK, connect_database() as connection:
                cursor = connection.execute("INSERT INTO companies(name, slug, active, created_at, updated_at) VALUES (?, ?, 1, ?, ?)", (name, slug, now, now))
                company_id = cursor.lastrowid
                admin_cursor = connection.execute(
                    "INSERT INTO users(email, name, role, password_hash, active, created_at, updated_at, company_id, platform_admin) VALUES (?, ?, 'admin', ?, 1, ?, ?, ?, 0)",
                    (admin_email, admin_name, password_hash(admin_password), now, now, company_id),
                )
                connection.commit()
        except sqlite3.IntegrityError:
            self.send_json({"error": "That company slug or administrator email already exists."}, HTTPStatus.CONFLICT)
            return
        self.write_audit(user, "company_created", "companies", company_id, f"Created tenant {name}")
        self.send_json({"id": company_id, "name": name, "slug": slug, "admin_user_id": admin_cursor.lastrowid}, HTTPStatus.CREATED)

    def handle_company_shared_workers(self, user) -> None:
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute(
                """SELECT worker_company_access.*, worker_accounts.email, worker_profiles.payload AS profile_payload
                   FROM worker_company_access
                   JOIN worker_accounts ON worker_accounts.id = worker_company_access.worker_id
                   JOIN worker_profiles ON worker_profiles.worker_id = worker_company_access.worker_id
                   WHERE worker_company_access.company_id = ? AND worker_company_access.status = 'active'
                   ORDER BY worker_company_access.granted_at DESC""",
                (user["company_id"],),
            ).fetchall()
            data = [shared_worker_projection(connection, row) | {"imported_at": row["imported_at"]} for row in rows]
        self.send_json({"data": data})

    def handle_company_import_worker(self, user, access_id: int) -> None:
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                """SELECT worker_company_access.*, worker_accounts.email, worker_profiles.payload AS profile_payload
                   FROM worker_company_access
                   JOIN worker_accounts ON worker_accounts.id = worker_company_access.worker_id
                   JOIN worker_profiles ON worker_profiles.worker_id = worker_company_access.worker_id
                   WHERE worker_company_access.id = ? AND worker_company_access.company_id = ? AND worker_company_access.status = 'active'""",
                (access_id, user["company_id"]),
            ).fetchone()
            if row is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            shared = shared_worker_projection(connection, row)
            profile = shared["profile"]
            worker_payload = {
                "universal_worker_id": row["worker_id"], "name": profile.get("name", "Shared worker"),
                "email": profile.get("email", ""), "phone": profile.get("phone", ""), "trade": profile.get("trade", ""),
                "skills": profile.get("skills", []), "qualifications": profile.get("qualifications", []),
                "status": "Active", "source": "local universal worker consent", "local_only": True,
            }
            existing = connection.execute("SELECT id, payload FROM records WHERE resource = 'workers' AND company_id = ?", (user["company_id"],)).fetchall()
            match = next((record for record in existing if json.loads(record["payload"]).get("universal_worker_id") == row["worker_id"]), None)
            if match:
                connection.execute("UPDATE records SET payload = ?, updated_at = ? WHERE id = ? AND company_id = ?", (json.dumps(worker_payload), now, match["id"], user["company_id"]))
                record_id = match["id"]
            else:
                cursor = connection.execute("INSERT INTO records(resource, payload, created_at, updated_at, company_id) VALUES ('workers', ?, ?, ?, ?)", (json.dumps(worker_payload), now, now, user["company_id"]))
                record_id = cursor.lastrowid
            connection.execute("UPDATE worker_company_access SET imported_at = ? WHERE id = ?", (now, access_id))
            connection.commit()
        self.write_audit(user, "universal_worker_imported", "workers", record_id, "Imported consented worker profile")
        self.send_json({"imported": True, "record_id": record_id, "access_id": access_id})

    def handle_company_document_file(self, user, document_id: int) -> None:
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                """SELECT worker_documents.* FROM worker_documents
                   JOIN worker_company_access ON worker_company_access.worker_id = worker_documents.worker_id
                   WHERE worker_documents.id = ? AND worker_company_access.company_id = ?
                     AND worker_company_access.status = 'active' AND worker_company_access.visible_fields LIKE '%documents%'""",
                (document_id, user["company_id"]),
            ).fetchone()
        if row is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_worker_file(row["worker_id"], row["stored_name"], row["original_name"], row["mime_type"])

    def handle_company_document_review(self, user, document_id: int) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        status = str(payload.get("status", "viewed")).lower()
        note = str(payload.get("note", "")).strip()[:1000]
        if status not in {"viewed", "approved", "declined"}:
            self.send_json({"error": "Review status must be viewed, approved or declined."}, HTTPStatus.BAD_REQUEST)
            return
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            allowed = connection.execute(
                """SELECT worker_documents.id FROM worker_documents
                   JOIN worker_company_access ON worker_company_access.worker_id = worker_documents.worker_id
                   WHERE worker_documents.id = ? AND worker_company_access.company_id = ?
                     AND worker_company_access.status = 'active' AND worker_company_access.visible_fields LIKE '%documents%'""",
                (document_id, user["company_id"]),
            ).fetchone()
            if allowed is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            connection.execute("INSERT INTO worker_document_reviews(document_id, company_id, reviewer_id, status, note, created_at) VALUES (?, ?, ?, ?, ?, ?)", (document_id, user["company_id"], user["id"], status, note, now))
            connection.commit()
        self.write_audit(user, "worker_document_reviewed", "worker_documents", document_id, f"Marked {status}")
        self.send_json({"reviewed": True, "document_id": document_id, "status": status, "reviewed_at": now})

    def handle_company_api_tokens_get(self, user) -> None:
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute("SELECT id, name, active, created_at, last_used_at FROM company_api_tokens WHERE company_id = ? ORDER BY id DESC", (user["company_id"],)).fetchall()
        self.send_json({"data": [dict(row) for row in rows]})

    def handle_company_api_token_create(self, user) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        name = str(payload.get("name", "Integration token")).strip()[:100]
        raw = f"kmp_{secrets.token_urlsafe(32)}"
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            cursor = connection.execute("INSERT INTO company_api_tokens(company_id, name, token_hash, active, created_by, created_at) VALUES (?, ?, ?, 1, ?, ?)", (user["company_id"], name, hashlib.sha256(raw.encode()).hexdigest(), user["id"], now))
            connection.commit()
        self.write_audit(user, "api_token_created", "company_api_tokens", cursor.lastrowid, name)
        self.send_json({"id": cursor.lastrowid, "name": name, "token": raw, "created_at": now}, HTTPStatus.CREATED)

    def handle_company_api_token_revoke(self, user, token_id: int) -> None:
        with DB_LOCK, connect_database() as connection:
            cursor = connection.execute("UPDATE company_api_tokens SET active = 0 WHERE id = ? AND company_id = ?", (token_id, user["company_id"]))
            connection.commit()
        if not cursor.rowcount:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.write_audit(user, "api_token_revoked", "company_api_tokens", token_id, "Integration token revoked")
        self.send_json({"revoked": True, "id": token_id})

    def authenticate_company_api(self):
        authorization = self.headers.get("Authorization", "")
        raw = authorization.removeprefix("Bearer ").strip() if authorization.startswith("Bearer ") else ""
        digest = hashlib.sha256(raw.encode()).hexdigest() if raw else ""
        with DB_LOCK, connect_database() as connection:
            token = connection.execute("SELECT * FROM company_api_tokens WHERE token_hash = ? AND active = 1", (digest,)).fetchone()
        if token is None:
            self.send_json({"error": "Valid bearer token required."}, HTTPStatus.UNAUTHORIZED)
            return None
        allowed, remaining, retry_after = company_api_rate_limit(int(token["id"]))
        self.api_rate_headers = {
            "X-RateLimit-Limit": str(API_RATE_LIMIT_PER_MINUTE),
            "X-RateLimit-Remaining": str(remaining),
        }
        if not allowed:
            self.send_json(
                {"error": "API rate limit exceeded. Retry after the indicated delay."},
                HTTPStatus.TOO_MANY_REQUESTS,
                {**self.api_rate_headers, "Retry-After": str(retry_after)},
            )
            return None
        return dict(token)

    def send_company_api_json(self, payload, status=HTTPStatus.OK) -> None:
        self.send_json(payload, status, getattr(self, "api_rate_headers", {}))

    def record_company_api_use(self, token, resource: str, record_id=None) -> None:
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            connection.execute("UPDATE company_api_tokens SET last_used_at = ? WHERE id = ?", (now, token["id"]))
            connection.execute(
                "INSERT INTO audit_log(user_id, actor, action, resource, record_id, summary, created_at, company_id) VALUES (NULL, ?, 'api_read', ?, ?, ?, ?, ?)",
                (f"api:{token['name']}", resource, record_id, "Consented worker API read", now, token["company_id"]),
            )
            connection.commit()

    def handle_api_shared_workers(self, query: str = "") -> None:
        token = self.authenticate_company_api()
        if token is None:
            return
        parameters = parse_qs(query)
        try:
            page = max(int(parameters.get("page", ["1"])[0]), 1)
            page_size = min(max(int(parameters.get("page_size", ["50"])[0]), 1), 100)
        except ValueError:
            self.send_company_api_json({"error": "page and page_size must be integers."}, HTTPStatus.BAD_REQUEST)
            return
        offset = (page - 1) * page_size
        with DB_LOCK, connect_database() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM worker_company_access WHERE company_id = ? AND status = 'active'",
                (token["company_id"],),
            ).fetchone()[0]
            rows = connection.execute(
                """SELECT worker_company_access.*, worker_accounts.email, worker_profiles.payload AS profile_payload
                   FROM worker_company_access JOIN worker_accounts ON worker_accounts.id = worker_company_access.worker_id
                   JOIN worker_profiles ON worker_profiles.worker_id = worker_company_access.worker_id
                   WHERE worker_company_access.company_id = ? AND worker_company_access.status = 'active'
                   ORDER BY worker_company_access.id ASC LIMIT ? OFFSET ?""",
                (token["company_id"], page_size, offset),
            ).fetchall()
            data = [shared_worker_projection(connection, row) for row in rows]
        self.record_company_api_use(token, "shared_workers")
        self.send_company_api_json({
            "data": data,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size,
            },
        })

    def handle_api_worker_resource(self, path: str) -> None:
        token = self.authenticate_company_api()
        if token is None:
            return
        parts = path.strip("/").split("/")
        if len(parts) < 4 or parts[:3] != ["api", "v1", "workers"] or not parts[3].isdigit():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        worker_id = int(parts[3])
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                """SELECT worker_company_access.*, worker_accounts.email, worker_profiles.payload AS profile_payload
                   FROM worker_company_access JOIN worker_accounts ON worker_accounts.id = worker_company_access.worker_id
                   JOIN worker_profiles ON worker_profiles.worker_id = worker_company_access.worker_id
                   WHERE worker_company_access.company_id = ? AND worker_company_access.worker_id = ?
                     AND worker_company_access.status = 'active'""",
                (token["company_id"], worker_id),
            ).fetchone()
            if row is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            projection = shared_worker_projection(connection, row)
            profile = projection["profile"]
            if len(parts) == 4:
                payload = projection
                resource = "worker_profile"
            elif len(parts) == 5 and parts[4] == "certifications":
                if "certifications" not in projection["visible_fields"]:
                    self.send_json({"error": "The worker has not shared certifications with this company."}, HTTPStatus.FORBIDDEN)
                    return
                payload = {"worker_id": worker_id, "data": profile.get("certifications", [])}
                resource = "worker_certifications"
            elif len(parts) == 5 and parts[4] == "training-records":
                if "training_records" not in projection["visible_fields"]:
                    self.send_json({"error": "The worker has not shared training records with this company."}, HTTPStatus.FORBIDDEN)
                    return
                payload = {"worker_id": worker_id, "data": profile.get("training_records", [])}
                resource = "worker_training_records"
            elif len(parts) == 5 and parts[4] == "inductions":
                if "inductions" not in projection["visible_fields"]:
                    self.send_json({"error": "The worker has not shared inductions with this company."}, HTTPStatus.FORBIDDEN)
                    return
                payload = {"worker_id": worker_id, "data": profile.get("inductions", [])}
                resource = "worker_inductions"
            elif len(parts) == 5 and parts[4] == "documents":
                if "documents" not in projection["visible_fields"]:
                    self.send_json({"error": "The worker has not shared documents with this company."}, HTTPStatus.FORBIDDEN)
                    return
                payload = {"worker_id": worker_id, "data": profile.get("documents", [])}
                resource = "worker_documents"
            elif len(parts) == 7 and parts[4] == "documents" and parts[5].isdigit() and parts[6] == "file":
                if "documents" not in projection["visible_fields"]:
                    self.send_json({"error": "The worker has not shared documents with this company."}, HTTPStatus.FORBIDDEN)
                    return
                document_id = int(parts[5])
                document = connection.execute("SELECT * FROM worker_documents WHERE id = ? AND worker_id = ?", (document_id, worker_id)).fetchone()
                if document is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                document = dict(document)
                payload = None
                resource = "worker_document_file"
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
        self.record_company_api_use(token, resource, worker_id)
        if payload is None:
            self.send_worker_file(document["worker_id"], document["stored_name"], document["original_name"], document["mime_type"])
        else:
            self.send_company_api_json(payload)

    def workflow_request_payload(self, connection, row) -> dict:
        item = dict(row)
        events = connection.execute("SELECT * FROM workflow_request_events WHERE request_id = ? ORDER BY id", (row["id"],)).fetchall()
        item["events"] = [dict(event) for event in events]
        return item

    def conversation_payload(self, connection, row) -> dict:
        item = dict(row)
        messages = connection.execute(
            """SELECT workflow_messages.*, users.name AS sender_user_name,
                      worker_profiles.payload AS sender_worker_profile
               FROM workflow_messages
               LEFT JOIN users ON users.id = workflow_messages.sender_user_id
               LEFT JOIN worker_profiles ON worker_profiles.worker_id = workflow_messages.sender_worker_id
               WHERE workflow_messages.conversation_id = ? ORDER BY workflow_messages.id""",
            (row["id"],),
        ).fetchall()
        item["messages"] = []
        for message in messages:
            value = dict(message)
            worker_profile = value.pop("sender_worker_profile", None)
            user_name = value.pop("sender_user_name", None)
            if worker_profile:
                value["sender_name"] = json.loads(message["sender_worker_profile"]).get("name", "Worker")
            else:
                value["sender_name"] = user_name or "Company team"
            item["messages"].append(value)
        return item

    def handle_departments_get(self, user) -> None:
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute("SELECT * FROM department_contacts WHERE company_id = ? ORDER BY department, name", (user["company_id"],)).fetchall()
        self.send_json({"data": [dict(row) for row in rows], "departments": sorted(WORKFLOW_DEPARTMENTS)})

    def handle_department_create(self, user) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        department = str(payload.get("department", "")).strip()
        name = str(payload.get("name", "")).strip()
        email = str(payload.get("email", "")).strip().lower()
        phone = str(payload.get("phone", "")).strip()
        user_id = int(payload["user_id"]) if str(payload.get("user_id", "")).isdigit() else None
        if department not in WORKFLOW_DEPARTMENTS or not name or (email and "@" not in email):
            self.send_json({"error": "A valid department, contact name and optional email are required."}, HTTPStatus.BAD_REQUEST)
            return
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            if user_id and connection.execute("SELECT id FROM users WHERE id = ? AND company_id = ? AND active = 1", (user_id, user["company_id"])).fetchone() is None:
                self.send_json({"error": "The linked user is not active in this company."}, HTTPStatus.BAD_REQUEST)
                return
            cursor = connection.execute(
                "INSERT INTO department_contacts(company_id, department, name, email, phone, user_id, active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)",
                (user["company_id"], department, name, email or None, phone or None, user_id, now, now),
            )
            connection.commit()
        self.write_audit(user, "department_contact_created", "department_contacts", cursor.lastrowid, f"{department}: {name}")
        self.send_json({"id": cursor.lastrowid, "department": department, "name": name, "email": email, "phone": phone, "user_id": user_id, "active": 1}, HTTPStatus.CREATED)

    def handle_department_update(self, user, contact_id: int) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        active = 1 if bool(payload.get("active", True)) else 0
        with DB_LOCK, connect_database() as connection:
            cursor = connection.execute("UPDATE department_contacts SET active = ?, updated_at = ? WHERE id = ? AND company_id = ?", (active, utc_now(), contact_id, user["company_id"]))
            connection.commit()
        if not cursor.rowcount:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.write_audit(user, "department_contact_updated", "department_contacts", contact_id, "Activated" if active else "Deactivated")
        self.send_json({"id": contact_id, "active": active})

    def handle_company_requests_get(self, user) -> None:
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute(
                """SELECT workflow_requests.*, department_contacts.name AS assigned_contact_name,
                          worker_profiles.payload AS worker_profile
                   FROM workflow_requests
                   LEFT JOIN department_contacts ON department_contacts.id = workflow_requests.assigned_contact_id
                   LEFT JOIN worker_profiles ON worker_profiles.worker_id = workflow_requests.worker_id
                   WHERE workflow_requests.company_id = ? ORDER BY workflow_requests.id DESC""",
                (user["company_id"],),
            ).fetchall()
            data = []
            for row in rows:
                item = self.workflow_request_payload(connection, row)
                worker_profile = item.pop("worker_profile", None)
                item["worker_name"] = json.loads(worker_profile).get("name", "") if worker_profile else ""
                data.append(item)
        self.send_json({"data": data, "departments": sorted(WORKFLOW_DEPARTMENTS), "request_types": sorted(WORKFLOW_REQUEST_TYPES), "statuses": sorted(WORKFLOW_STATUSES)})

    def handle_company_request_create(self, user) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        company_id = int(user["company_id"])
        worker_id = int(payload["worker_id"]) if str(payload.get("worker_id", "")).isdigit() else None
        department = str(payload.get("department", "")).strip()
        request_type = str(payload.get("request_type", "")).strip()
        subject = str(payload.get("subject", "")).strip()[:180]
        message = str(payload.get("message", "")).strip()[:4000]
        priority = str(payload.get("priority", "normal")).strip().lower()
        due_date = str(payload.get("due_date", "")).strip() or None
        if department not in WORKFLOW_DEPARTMENTS or request_type not in WORKFLOW_REQUEST_TYPES or not subject or not message or priority not in {"low", "normal", "high", "urgent"}:
            self.send_json({"error": "Department, request type, subject, message and valid priority are required."}, HTTPStatus.BAD_REQUEST)
            return
        if due_date and parse_record_date(due_date) is None:
            self.send_json({"error": "Due date is invalid."}, HTTPStatus.BAD_REQUEST)
            return
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            if worker_id and connection.execute("SELECT id FROM worker_company_access WHERE company_id = ? AND worker_id = ? AND status = 'active'", (company_id, worker_id)).fetchone() is None:
                self.send_json({"error": "The worker has not granted this company access."}, HTTPStatus.FORBIDDEN)
                return
            contact = connection.execute("SELECT * FROM department_contacts WHERE company_id = ? AND department = ? AND active = 1 ORDER BY id LIMIT 1", (company_id, department)).fetchone()
            cursor = connection.execute(
                """INSERT INTO workflow_requests(company_id, worker_id, created_by_user_id, department, request_type, subject, message, related_resource, related_id, status, priority, assigned_contact_id, due_date, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)""",
                (company_id, worker_id, user["id"] or None, department, request_type, subject, message, str(payload.get("related_resource", ""))[:80] or None, int(payload["related_id"]) if str(payload.get("related_id", "")).isdigit() else None, priority, contact["id"] if contact else None, due_date, now, now),
            )
            request_id = cursor.lastrowid
            connection.execute("INSERT INTO workflow_request_events(request_id, actor_type, actor_id, event_type, to_status, note, created_at) VALUES (?, 'user', ?, 'created', 'open', ?, ?)", (request_id, user["id"] or None, message, now))
            if worker_id:
                conversation = connection.execute("INSERT INTO workflow_conversations(company_id, worker_id, request_id, subject, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'open', ?, ?)", (company_id, worker_id, request_id, subject, now, now))
                connection.execute("INSERT INTO workflow_messages(conversation_id, sender_type, sender_user_id, message, created_at) VALUES (?, 'user', ?, ?, ?)", (conversation.lastrowid, user["id"] or None, message, now))
                create_in_app_notification(connection, company_id, "worker", worker_id, "workflow_request", subject, message, "/worker/#inbox")
            notify_company_workflow_users(connection, company_id, "workflow_request", subject, message, "/workflow-centre", contact["user_id"] if contact else None)
            connection.commit()
        self.write_audit(user, "workflow_request_created", "workflow_requests", request_id, subject)
        self.send_json({"id": request_id, "status": "open", "assigned_contact_id": contact["id"] if contact else None}, HTTPStatus.CREATED)

    def handle_worker_requests_get(self, worker) -> None:
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute(
                """SELECT workflow_requests.*, companies.name AS company_name, department_contacts.name AS assigned_contact_name
                   FROM workflow_requests JOIN companies ON companies.id = workflow_requests.company_id
                   LEFT JOIN department_contacts ON department_contacts.id = workflow_requests.assigned_contact_id
                   WHERE workflow_requests.worker_id = ? ORDER BY workflow_requests.id DESC""",
                (worker["id"],),
            ).fetchall()
            data = [self.workflow_request_payload(connection, row) for row in rows]
        self.send_json({"data": data, "departments": sorted(WORKFLOW_DEPARTMENTS), "request_types": sorted(WORKFLOW_REQUEST_TYPES)})

    def handle_worker_request_create(self, worker) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        company_id = int(payload["company_id"]) if str(payload.get("company_id", "")).isdigit() else 0
        department = str(payload.get("department", "")).strip()
        request_type = str(payload.get("request_type", "")).strip()
        subject = str(payload.get("subject", "")).strip()[:180]
        message = str(payload.get("message", "")).strip()[:4000]
        if not company_id or department not in WORKFLOW_DEPARTMENTS or request_type not in WORKFLOW_REQUEST_TYPES or not subject or not message:
            self.send_json({"error": "Company, department, request type, subject and message are required."}, HTTPStatus.BAD_REQUEST)
            return
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            access = connection.execute("SELECT id FROM worker_company_access WHERE company_id = ? AND worker_id = ? AND status = 'active'", (company_id, worker["id"])).fetchone()
            if access is None:
                self.send_json({"error": "Share your profile with this company before creating a request."}, HTTPStatus.FORBIDDEN)
                return
            contact = connection.execute("SELECT * FROM department_contacts WHERE company_id = ? AND department = ? AND active = 1 ORDER BY id LIMIT 1", (company_id, department)).fetchone()
            cursor = connection.execute(
                """INSERT INTO workflow_requests(company_id, worker_id, created_by_worker_id, department, request_type, subject, message, status, priority, assigned_contact_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'open', 'normal', ?, ?, ?)""",
                (company_id, worker["id"], worker["id"], department, request_type, subject, message, contact["id"] if contact else None, now, now),
            )
            request_id = cursor.lastrowid
            connection.execute("INSERT INTO workflow_request_events(request_id, actor_type, actor_id, event_type, to_status, note, created_at) VALUES (?, 'worker', ?, 'created', 'open', ?, ?)", (request_id, worker["id"], message, now))
            conversation = connection.execute("INSERT INTO workflow_conversations(company_id, worker_id, request_id, subject, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'open', ?, ?)", (company_id, worker["id"], request_id, subject, now, now))
            connection.execute("INSERT INTO workflow_messages(conversation_id, sender_type, sender_worker_id, message, created_at) VALUES (?, 'worker', ?, ?, ?)", (conversation.lastrowid, worker["id"], message, now))
            notify_company_workflow_users(connection, company_id, "worker_request", subject, message, "/workflow-centre", contact["user_id"] if contact else None)
            connection.commit()
        self.send_json({"id": request_id, "status": "open"}, HTTPStatus.CREATED)

    def handle_company_request_status(self, user, request_id: int) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        status = str(payload.get("status", "")).strip().lower()
        note = str(payload.get("note", "")).strip()[:2000]
        if status not in WORKFLOW_STATUSES:
            self.send_json({"error": "Invalid workflow status."}, HTTPStatus.BAD_REQUEST)
            return
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            row = connection.execute("SELECT * FROM workflow_requests WHERE id = ? AND company_id = ?", (request_id, user["company_id"])).fetchone()
            if row is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            connection.execute("UPDATE workflow_requests SET status = ?, updated_at = ? WHERE id = ?", (status, now, request_id))
            connection.execute("INSERT INTO workflow_request_events(request_id, actor_type, actor_id, event_type, from_status, to_status, note, created_at) VALUES (?, 'user', ?, 'status_changed', ?, ?, ?, ?)", (request_id, user["id"] or None, row["status"], status, note, now))
            if row["worker_id"]:
                locale = preferred_language_for_owner(connection, "worker", int(row["worker_id"]))
                create_in_app_notification(
                    connection,
                    user["company_id"],
                    "worker",
                    row["worker_id"],
                    "request_status",
                    row["subject"],
                    reviewed_server_message(
                        connection,
                        int(user["company_id"]),
                        "status_changed",
                        locale,
                        status=translate_ui(status.replace("_", " "), locale),
                        note=note,
                    ),
                    "/worker/#inbox",
                )
            connection.commit()
        self.write_audit(user, "workflow_request_status", "workflow_requests", request_id, f"{row['status']} → {status}")
        self.send_json({"id": request_id, "status": status, "updated_at": now})

    def handle_company_conversations_get(self, user) -> None:
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute(
                """SELECT workflow_conversations.*, worker_profiles.payload AS worker_profile
                   FROM workflow_conversations JOIN worker_profiles ON worker_profiles.worker_id = workflow_conversations.worker_id
                   WHERE workflow_conversations.company_id = ? ORDER BY workflow_conversations.updated_at DESC""",
                (user["company_id"],),
            ).fetchall()
            data = []
            for row in rows:
                item = self.conversation_payload(connection, row)
                item["worker_name"] = json.loads(item.pop("worker_profile")).get("name", "Worker")
                data.append(item)
        self.send_json({"data": data})

    def handle_worker_conversations_get(self, worker) -> None:
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute("SELECT workflow_conversations.*, companies.name AS company_name FROM workflow_conversations JOIN companies ON companies.id = workflow_conversations.company_id WHERE worker_id = ? ORDER BY workflow_conversations.updated_at DESC", (worker["id"],)).fetchall()
            data = [self.conversation_payload(connection, row) for row in rows]
        self.send_json({"data": data})

    def handle_conversation_message(self, actor, conversation_id: int, actor_type: str) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        message = str(payload.get("message", "")).strip()[:4000]
        if not message:
            self.send_json({"error": "Message is required."}, HTTPStatus.BAD_REQUEST)
            return
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            if actor_type == "user":
                row = connection.execute("SELECT * FROM workflow_conversations WHERE id = ? AND company_id = ?", (conversation_id, actor["company_id"])).fetchone()
            else:
                row = connection.execute("SELECT * FROM workflow_conversations WHERE id = ? AND worker_id = ?", (conversation_id, actor["id"])).fetchone()
            if row is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            cursor = connection.execute(
                "INSERT INTO workflow_messages(conversation_id, sender_type, sender_user_id, sender_worker_id, message, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (conversation_id, actor_type, actor["id"] if actor_type == "user" and actor["id"] else None, actor["id"] if actor_type == "worker" else None, message, now),
            )
            connection.execute("UPDATE workflow_conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
            if actor_type == "user":
                create_in_app_notification(connection, row["company_id"], "worker", row["worker_id"], "message", row["subject"], message, "/worker/#inbox")
            else:
                notify_company_workflow_users(connection, row["company_id"], "message", row["subject"], message, "/workflow-centre")
            connection.commit()
        if actor_type == "user":
            self.write_audit(actor, "workflow_message_sent", "workflow_conversations", conversation_id, row["subject"])
        self.send_json({"id": cursor.lastrowid, "conversation_id": conversation_id, "message": message, "created_at": now}, HTTPStatus.CREATED)

    def public_induction_site(self, token: str):
        if (
            not token
            or len(token) > 200
            or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in token)
        ):
            return None
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                """
                SELECT induction_site_links.*, companies.name AS company_name,
                       records.payload AS induction_payload
                FROM induction_site_links
                JOIN companies ON companies.id = induction_site_links.company_id
                JOIN records ON records.id = induction_site_links.induction_record_id
                WHERE induction_site_links.public_token = ?
                  AND induction_site_links.active = 1
                  AND companies.active = 1
                  AND records.resource = 'inductions'
                """,
                (token,),
            ).fetchone()
        return dict(row) if row else None

    def handle_public_induction_schema(self, token: str) -> None:
        site = self.public_induction_site(token)
        if site is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        schema = induction_registration_schema()
        if not schema:
            self.send_json({"error": "The induction registration schema is unavailable."}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        selected_site = next(
            (
                item
                for item in schema.get("sites", [])
                if str(item.get("id", "")) == str(site.get("site_source_id", ""))
                or str(item.get("name", "")).casefold() == str(site.get("site_name", "")).casefold()
            ),
            {"id": str(site.get("site_source_id", "")), "name": site.get("site_name", "")},
        )
        public_schema = {
            key: value
            for key, value in schema.items()
            if key not in {"capture_policy", "source_path", "subcontractors_by_site"}
        }
        public_schema["company"] = site["company_name"]
        public_schema["sites"] = [selected_site]
        public_schema["selected_site"] = selected_site
        public_schema["subcontractors"] = [
            {"id": str(item[0]), "name": str(item[1])}
            for item in schema.get("subcontractors_by_site", {}).get(str(selected_site.get("id", "")), [])
        ]
        induction = json.loads(site["induction_payload"])
        public_schema["induction"] = {
            "title": induction.get("title", f"{site['site_name']} Site Induction"),
            "site": site["site_name"],
            "status": induction.get("status", "Active"),
        }
        self.send_json(public_schema)

    def normalize_public_induction_registration(self, payload: dict, site: dict) -> tuple[dict, list[str]]:
        schema = induction_registration_schema()
        errors: list[str] = []

        def text_value(name: str, label: str, required=True, maximum=500) -> str:
            value = str(payload.get(name, "")).strip()
            if required and not value:
                errors.append(f"{label} is required.")
            if len(value) > maximum:
                errors.append(f"{label} is too long.")
            return value[:maximum]

        name = text_value("name", "Worker name", maximum=180)
        email = text_value("email", "Worker email", maximum=254).lower()
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            errors.append("Worker email is invalid.")
        worker_id = text_value("worker_id", "Worker ID", required=False, maximum=120)
        country_code = text_value("country_code", "Country code", maximum=12)
        emergency_country_code = text_value("emergency_country_code", "Emergency country code", maximum=12)
        allowed_calling_codes = set(schema.get("calling_codes", []))
        if country_code not in allowed_calling_codes:
            errors.append("Country code is invalid.")
        if emergency_country_code not in allowed_calling_codes:
            errors.append("Emergency country code is invalid.")
        phone_number = text_value("phone_number", "Contact number", maximum=40)
        emergency_phone_number = text_value("emergency_phone_number", "Emergency contact number", maximum=40)
        emergency_contact_name = text_value("emergency_contact_name", "Emergency contact name", maximum=180)
        emergency_contact_address = text_value("emergency_contact_address", "Emergency contact address", maximum=500)
        medical_details = text_value("medical_details", "Medical details", required=False, maximum=4000)

        role_ids = [
            str(value)
            for value in payload.get("roles", [])
            if isinstance(value, (str, int))
        ] if isinstance(payload.get("roles"), list) else []
        allowed_roles = {str(item.get("id", "")): item for item in schema.get("roles", [])}
        role_ids = list(dict.fromkeys(role_ids))
        if not role_ids or any(role_id not in allowed_roles for role_id in role_ids):
            errors.append("Select at least one valid role.")

        site_id = str(site.get("site_source_id", ""))
        available_subcontractors = {
            str(item[0]): str(item[1])
            for item in schema.get("subcontractors_by_site", {}).get(site_id, [])
        }
        subcontractor_ids = [
            str(value)
            for value in payload.get("subcontractors", [])
            if isinstance(value, (str, int))
        ] if isinstance(payload.get("subcontractors"), list) else []
        subcontractor_ids = list(dict.fromkeys(subcontractor_ids))
        if not subcontractor_ids:
            errors.append("Select a subcontractor or No Subcontractor.")
        elif any(value not in available_subcontractors for value in subcontractor_ids):
            errors.append("A selected subcontractor is not available for this site.")

        raw_training = payload.get("training_records", [])
        training_by_id = {
            str(item.get("question_id", "")): item
            for item in raw_training
            if isinstance(item, dict)
        } if isinstance(raw_training, list) else {}
        normalized_training = []
        required_evidence = []
        for question in schema.get("training_questions", []):
            question_id = str(question.get("id", ""))
            supplied = training_by_id.get(question_id, {})
            answer = str(supplied.get("answer", "")).strip().lower()
            if answer not in {"", "yes", "no"}:
                errors.append(f"Training answer {question_id} is invalid.")
                answer = ""
            expiry_date = str(supplied.get("expiry_date", "")).strip()[:10]
            if answer == "yes":
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", expiry_date):
                    errors.append(f"Expiry date is required for {question.get('question', 'training')}.")
                required_evidence.append(f"training:{question_id}:photo")
            normalized_training.append(
                {
                    "question_id": question_id,
                    "question": question.get("question", ""),
                    "answer": answer,
                    "expiry_date": expiry_date if answer == "yes" else "",
                }
            )

        supplied_safe_pass = payload.get("safe_pass", {})
        supplied_safe_pass = supplied_safe_pass if isinstance(supplied_safe_pass, dict) else {}
        safe_pass_answer = str(supplied_safe_pass.get("answer", "")).strip().lower()
        if safe_pass_answer not in {"yes", "no"}:
            errors.append("Choose Yes or No for Safe Pass.")
        safe_pass = {"answer": safe_pass_answer}
        if safe_pass_answer == "yes":
            for field_name, label in (
                ("name", "Safe Pass name"),
                ("title", "Safe Pass registration number"),
                ("valid_from", "Safe Pass valid-from date"),
                ("expiry_date", "Safe Pass expiry date"),
            ):
                value = str(supplied_safe_pass.get(field_name, "")).strip()
                if not value:
                    errors.append(f"{label} is required.")
                if field_name in {"valid_from", "expiry_date"} and value and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                    errors.append(f"{label} is invalid.")
                safe_pass[field_name] = value[:180]
            required_evidence.append("safe_pass:photo")

        safety_confirmation = payload.get("safety_confirmation") is True
        if not safety_confirmation:
            errors.append("Confirm that the Safety Statement and RAMS have been read.")

        normalized = {
            "name": name,
            "email": email,
            "worker_id": worker_id,
            "country_code": country_code,
            "phone_number": phone_number,
            "emergency_country_code": emergency_country_code,
            "emergency_phone_number": emergency_phone_number,
            "emergency_contact_name": emergency_contact_name,
            "emergency_contact_address": emergency_contact_address,
            "site": {"id": site_id, "name": site.get("site_name", "")},
            "roles": [
                {"id": role_id, "name": allowed_roles[role_id].get("name", "")}
                for role_id in role_ids
                if role_id in allowed_roles
            ],
            "subcontractors": [
                {"id": value, "name": available_subcontractors[value]}
                for value in subcontractor_ids
                if value in available_subcontractors
            ],
            "medical_details": medical_details,
            "training_records": normalized_training,
            "safe_pass": safe_pass,
            "safety_confirmation": safety_confirmation,
            "required_evidence": sorted(set(required_evidence)),
            "language": normalize_language(payload.get("language")),
            "source": "local controlled workspace",
            "local_only": True,
        }
        return normalized, errors

    def public_induction_upload_context(self, token: str, registration_id: int):
        supplied_token = self.headers.get("X-Upload-Token", "").strip()
        if not supplied_token:
            return None
        digest = hashlib.sha256(supplied_token.encode("utf-8")).hexdigest()
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                """
                SELECT induction_registrations.*, induction_site_links.public_token,
                       induction_site_links.site_name
                FROM induction_registrations
                JOIN induction_site_links ON induction_site_links.id = induction_registrations.site_link_id
                WHERE induction_registrations.id = ?
                  AND induction_site_links.public_token = ?
                  AND induction_registrations.upload_token_hash = ?
                  AND induction_registrations.upload_expires_at > ?
                """,
                (registration_id, token, digest, now),
            ).fetchone()
        return dict(row) if row else None

    def handle_public_induction_registration_create(self, token: str) -> None:
        site = self.public_induction_site(token)
        if site is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        address = self.client_address[0] if self.client_address else "unknown"
        rate_key = hashlib.sha256(f"{token}:{address}".encode("utf-8")).hexdigest()
        if not public_induction_rate_limit_allowed(rate_key):
            self.send_json(
                {"error": "Too many registration attempts. Please try again in 10 minutes."},
                HTTPStatus.TOO_MANY_REQUESTS,
                {"Retry-After": str(PUBLIC_INDUCTION_WINDOW_MINUTES * 60)},
            )
            return
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        normalized, errors = self.normalize_public_induction_registration(payload, site)
        if errors:
            self.send_json({"error": errors[0], "errors": errors}, HTTPStatus.BAD_REQUEST)
            return
        now = utc_now()
        raw_upload_token = secrets.token_urlsafe(32)
        upload_digest = hashlib.sha256(raw_upload_token.encode("utf-8")).hexdigest()
        upload_expires_at = (datetime.now(UTC) + timedelta(hours=2)).replace(microsecond=0).isoformat()
        reference = f"IND-{datetime.now(UTC).strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"
        status = "evidence_pending" if normalized["required_evidence"] else "ready"
        with DB_LOCK, connect_database() as connection:
            cursor = connection.execute(
                """
                INSERT INTO induction_registrations(
                    company_id, site_link_id, reference, status, payload,
                    upload_token_hash, upload_expires_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    site["company_id"],
                    site["id"],
                    reference,
                    status,
                    json.dumps(normalized, ensure_ascii=False),
                    upload_digest,
                    upload_expires_at,
                    now,
                    now,
                ),
            )
            connection.commit()
        self.send_json(
            {
                "id": cursor.lastrowid,
                "reference": reference,
                "status": status,
                "required_evidence": normalized["required_evidence"],
                "upload_token": raw_upload_token,
                "upload_expires_at": upload_expires_at,
            },
            HTTPStatus.CREATED,
        )

    def handle_public_induction_evidence(self, token: str, registration_id: int) -> None:
        registration = self.public_induction_upload_context(token, registration_id)
        if registration is None:
            self.send_json({"error": "The evidence upload link is invalid or expired."}, HTTPStatus.FORBIDDEN)
            return
        if registration["status"] == "submitted":
            self.send_json({"error": "This registration has already been submitted."}, HTTPStatus.CONFLICT)
            return
        field_key = unquote(self.headers.get("X-Field-Key", "")).strip()[:120]
        original_name = Path(unquote(self.headers.get("X-File-Name", ""))).name
        extension = Path(original_name).suffix.lower()
        payload = json.loads(registration["payload"])
        allowed_field_keys = set(payload.get("required_evidence", [])) | {"worker_photo"}
        if field_key not in allowed_field_keys or extension not in {".png", ".jpg", ".jpeg"}:
            self.send_json({"error": "A valid induction image field and PNG or JPEG file are required."}, HTTPStatus.BAD_REQUEST)
            return
        try:
            content = self.read_raw_body()
        except ValueError as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        is_png = extension == ".png" and content.startswith(b"\x89PNG\r\n\x1a\n")
        is_jpeg = extension in {".jpg", ".jpeg"} and content.startswith(b"\xff\xd8\xff")
        if not (is_png or is_jpeg):
            self.send_json({"error": "The uploaded file content is not a valid PNG or JPEG image."}, HTTPStatus.BAD_REQUEST)
            return
        evidence_root = DATA_ROOT / "induction-evidence" / str(registration["company_id"]) / str(registration_id)
        evidence_root.mkdir(parents=True, exist_ok=True)
        stored_name = f"{secrets.token_hex(12)}{extension}"
        (evidence_root / stored_name).write_bytes(content)
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            cursor = connection.execute(
                """
                INSERT INTO induction_registration_evidence(
                    registration_id, field_key, original_name, stored_name,
                    content_type, size, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    registration_id,
                    field_key,
                    original_name,
                    stored_name,
                    "image/png" if is_png else "image/jpeg",
                    len(content),
                    now,
                ),
            )
            connection.commit()
        self.send_json(
            {"id": cursor.lastrowid, "field_key": field_key, "original_name": original_name, "size": len(content)},
            HTTPStatus.CREATED,
        )

    def handle_public_induction_complete(self, token: str, registration_id: int) -> None:
        registration = self.public_induction_upload_context(token, registration_id)
        if registration is None:
            self.send_json({"error": "The registration completion link is invalid or expired."}, HTTPStatus.FORBIDDEN)
            return
        payload = json.loads(registration["payload"])
        required = set(payload.get("required_evidence", []))
        with DB_LOCK, connect_database() as connection:
            uploaded = {
                row["field_key"]
                for row in connection.execute(
                    "SELECT field_key FROM induction_registration_evidence WHERE registration_id = ?",
                    (registration_id,),
                ).fetchall()
            }
            missing = sorted(required - uploaded)
            if missing:
                self.send_json(
                    {"error": "Required evidence is still missing.", "missing_evidence": missing},
                    HTTPStatus.CONFLICT,
                )
                return
            now = utc_now()
            connection.execute(
                """
                UPDATE induction_registrations
                SET status = 'submitted', submitted_at = ?, updated_at = ?,
                    upload_token_hash = NULL, upload_expires_at = NULL
                WHERE id = ?
                """,
                (now, now, registration_id),
            )
            notify_company_workflow_users(
                connection,
                int(registration["company_id"]),
                "induction_registration",
                "New site induction registration",
                f"{payload.get('name', 'A worker')} registered for {registration['site_name']}.",
                "/inductions",
            )
            connection.execute(
                """
                INSERT INTO audit_log(user_id, actor, action, resource, record_id, summary, created_at, company_id)
                VALUES (NULL, 'Public induction registration', 'submit', 'induction_registrations', ?, ?, ?, ?)
                """,
                (
                    registration_id,
                    f"{registration['reference']} submitted for {registration['site_name']}",
                    now,
                    registration["company_id"],
                ),
            )
            connection.commit()
        self.send_json(
            {
                "id": registration_id,
                "reference": registration["reference"],
                "status": "submitted",
                "submitted_at": now,
            }
        )

    def handle_company_induction_sites_get(self, user) -> None:
        with DB_LOCK, connect_database() as connection:
            ensure_induction_site_links(connection, int(user["company_id"]))
            connection.commit()
            rows = connection.execute(
                """
                SELECT induction_site_links.*, records.payload AS induction_payload
                FROM induction_site_links
                JOIN records ON records.id = induction_site_links.induction_record_id
                WHERE induction_site_links.company_id = ?
                ORDER BY induction_site_links.site_name
                """,
                (user["company_id"],),
            ).fetchall()
        base = self.application_base_url()
        data = []
        for row in rows:
            item = dict(row)
            induction = json.loads(item.pop("induction_payload"))
            item["induction_title"] = induction.get("title", item["site_name"])
            item["registration_url"] = f"{base}/induction/c/{item['public_token']}/register"
            item["qr_url"] = f"/api/company/induction-sites/{item['id']}/qr"
            data.append(item)
        self.send_json({"data": data})

    def handle_company_induction_site_qr(self, user, link_id: int) -> None:
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                "SELECT * FROM induction_site_links WHERE id = ? AND company_id = ? AND active = 1",
                (link_id, user["company_id"]),
            ).fetchone()
        if row is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        url = f"{self.application_base_url()}/induction/c/{row['public_token']}/register"
        body = build_qr_svg(url, f"{row['site_name']} induction registration QR code")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/svg+xml")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "private, no-store")
        self.send_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def handle_company_induction_registrations_get(self, user) -> None:
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute(
                """
                SELECT induction_registrations.*, induction_site_links.site_name,
                       COUNT(induction_registration_evidence.id) AS evidence_count
                FROM induction_registrations
                JOIN induction_site_links ON induction_site_links.id = induction_registrations.site_link_id
                LEFT JOIN induction_registration_evidence
                    ON induction_registration_evidence.registration_id = induction_registrations.id
                WHERE induction_registrations.company_id = ?
                GROUP BY induction_registrations.id
                ORDER BY induction_registrations.id DESC
                LIMIT 500
                """,
                (user["company_id"],),
            ).fetchall()
        data = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item["payload"])
            item.pop("upload_token_hash", None)
            item.pop("upload_expires_at", None)
            data.append(item)
        self.send_json({"data": data})

    def handle_company_induction_evidence_file(self, user, registration_id: int, evidence_id: int) -> None:
        with DB_LOCK, connect_database() as connection:
            row = connection.execute(
                """
                SELECT induction_registration_evidence.*, induction_registrations.company_id
                FROM induction_registration_evidence
                JOIN induction_registrations
                    ON induction_registrations.id = induction_registration_evidence.registration_id
                WHERE induction_registration_evidence.id = ?
                  AND induction_registration_evidence.registration_id = ?
                  AND induction_registrations.company_id = ?
                """,
                (evidence_id, registration_id, user["company_id"]),
            ).fetchone()
        if row is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        root = (DATA_ROOT / "induction-evidence" / str(row["company_id"]) / str(registration_id)).resolve()
        try:
            resolved = (root / Path(row["stored_name"]).name).resolve(strict=True)
        except FileNotFoundError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if root not in resolved.parents:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        stat = resolved.stat()
        safe_name = Path(row["original_name"]).name.replace('"', "")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", row["content_type"])
        self.send_header("Content-Length", str(stat.st_size))
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("Content-Disposition", f'inline; filename="{safe_name}"')
        self.send_security_headers()
        self.end_headers()
        with resolved.open("rb") as handle:
            while chunk := handle.read(256 * 1024):
                self.wfile.write(chunk)

    def handle_company_inductions_get(self, user) -> None:
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute(
                """SELECT induction_reviews.*, worker_profiles.payload AS worker_profile, users.name AS reviewer_name
                   FROM induction_reviews JOIN worker_profiles ON worker_profiles.worker_id = induction_reviews.worker_id
                   LEFT JOIN users ON users.id = induction_reviews.reviewer_id
                   WHERE induction_reviews.company_id = ? ORDER BY induction_reviews.id DESC""",
                (user["company_id"],),
            ).fetchall()
            data = []
            for row in rows:
                item = dict(row)
                item["worker_name"] = json.loads(item.pop("worker_profile")).get("name", "Worker")
                events = connection.execute("SELECT * FROM induction_review_events WHERE review_id = ? ORDER BY id", (row["id"],)).fetchall()
                item["events"] = [dict(event) for event in events]
                data.append(item)
        self.send_json({"data": data, "statuses": sorted(INDUCTION_REVIEW_STATUSES)})

    def handle_worker_inductions_get(self, worker) -> None:
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute("SELECT induction_reviews.*, companies.name AS company_name, users.name AS reviewer_name FROM induction_reviews JOIN companies ON companies.id = induction_reviews.company_id LEFT JOIN users ON users.id = induction_reviews.reviewer_id WHERE worker_id = ? ORDER BY induction_reviews.id DESC", (worker["id"],)).fetchall()
            data = []
            for row in rows:
                item = dict(row)
                events = connection.execute("SELECT * FROM induction_review_events WHERE review_id = ? ORDER BY id", (row["id"],)).fetchall()
                item["events"] = [dict(event) for event in events]
                data.append(item)
        self.send_json({"data": data})

    def handle_company_induction_create(self, user) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        worker_id = int(payload["worker_id"]) if str(payload.get("worker_id", "")).isdigit() else 0
        induction = str(payload.get("induction_name", "")).strip()[:180]
        site = str(payload.get("site", "")).strip()[:180]
        if not worker_id or not induction:
            self.send_json({"error": "Worker and induction name are required."}, HTTPStatus.BAD_REQUEST)
            return
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            if connection.execute("SELECT id FROM worker_company_access WHERE company_id = ? AND worker_id = ? AND status = 'active'", (user["company_id"], worker_id)).fetchone() is None:
                self.send_json({"error": "The worker has not granted this company access."}, HTTPStatus.FORBIDDEN)
                return
            cursor = connection.execute("INSERT INTO induction_reviews(company_id, worker_id, induction_name, site, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'pending', ?, ?)", (user["company_id"], worker_id, induction, site or None, now, now))
            connection.execute("INSERT INTO induction_review_events(review_id, actor_type, actor_id, to_status, comments, created_at) VALUES (?, 'user', ?, 'pending', ?, ?)", (cursor.lastrowid, user["id"] or None, "Submitted for supervisor review", now))
            locale = preferred_language_for_owner(connection, "worker", worker_id)
            create_in_app_notification(
                connection,
                user["company_id"],
                "worker",
                worker_id,
                "induction_review",
                induction,
                reviewed_server_message(
                    connection,
                    int(user["company_id"]),
                    "induction_submitted",
                    locale,
                    site=site or translate_ui("the assigned site", locale),
                ),
                "/worker/#inbox",
            )
            connection.commit()
        self.write_audit(user, "induction_review_created", "induction_reviews", cursor.lastrowid, induction)
        self.send_json({"id": cursor.lastrowid, "status": "pending"}, HTTPStatus.CREATED)

    def handle_company_induction_status(self, user, review_id: int) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        status = str(payload.get("status", "")).strip().lower()
        comments = str(payload.get("comments", "")).strip()[:2000]
        if status not in INDUCTION_REVIEW_STATUSES - {"pending"}:
            self.send_json({"error": "Status must be approved, declined or information_requested."}, HTTPStatus.BAD_REQUEST)
            return
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            row = connection.execute("SELECT * FROM induction_reviews WHERE id = ? AND company_id = ?", (review_id, user["company_id"])).fetchone()
            if row is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            connection.execute("UPDATE induction_reviews SET status = ?, comments = ?, reviewer_id = ?, reviewed_at = ?, updated_at = ? WHERE id = ?", (status, comments or None, user["id"] or None, now, now, review_id))
            connection.execute("INSERT INTO induction_review_events(review_id, actor_type, actor_id, from_status, to_status, comments, created_at) VALUES (?, 'user', ?, ?, ?, ?, ?)", (review_id, user["id"] or None, row["status"], status, comments or None, now))
            locale = preferred_language_for_owner(connection, "worker", int(row["worker_id"]))
            create_in_app_notification(
                connection,
                user["company_id"],
                "worker",
                row["worker_id"],
                "induction_status",
                row["induction_name"],
                reviewed_server_message(
                    connection,
                    int(user["company_id"]),
                    "induction_status",
                    locale,
                    status=translate_ui(status.replace("_", " "), locale),
                    comments=comments,
                ),
                "/worker/#inbox",
            )
            connection.commit()
        self.write_audit(user, "induction_review_status", "induction_reviews", review_id, status)
        self.send_json({"id": review_id, "status": status, "comments": comments, "reviewed_at": now})

    def handle_notifications_get(self, actor, recipient_type: str) -> None:
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute("SELECT * FROM in_app_notifications WHERE recipient_type = ? AND recipient_id = ? ORDER BY id DESC LIMIT 250", (recipient_type, actor["id"])).fetchall()
        self.send_json({"data": [dict(row) for row in rows], "unread": sum(1 for row in rows if not row["read_at"])})

    def handle_notification_read(self, actor, recipient_type: str, notification_id: int) -> None:
        with DB_LOCK, connect_database() as connection:
            cursor = connection.execute("UPDATE in_app_notifications SET read_at = COALESCE(read_at, ?) WHERE id = ? AND recipient_type = ? AND recipient_id = ?", (utc_now(), notification_id, recipient_type, actor["id"]))
            connection.commit()
        if not cursor.rowcount:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.send_json({"id": notification_id, "read": True})

    def handle_preferences_get(self, actor, owner_type: str) -> None:
        with DB_LOCK, connect_database() as connection:
            row = connection.execute("SELECT * FROM notification_preferences WHERE owner_type = ? AND owner_id = ?", (owner_type, actor["id"])).fetchone()
        preferences = dict(row) if row else {"owner_type": owner_type, "owner_id": actor["id"], "in_app": 1, "email": 0, "sms": 0, "push": 0, "preferred_language": "en-IE"}
        preferences["preferred_language"] = normalize_language(preferences.get("preferred_language"))
        email = public_email_configuration()
        self.send_json({"preferences": preferences, "channels": {"in_app": {"available": True}, "email": {"available": bool(email["enabled"] and email["configured"])}, "sms": {"available": False, "reason": "Provider approval and configuration required"}, "push": {"available": False, "reason": "Provider approval and configuration required"}}})

    def handle_preferences_update(self, actor, owner_type: str) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        raw_language = str(payload.get("preferred_language", "en-IE")).strip()
        if raw_language not in SUPPORTED_LANGUAGES and raw_language not in LANGUAGE_ALIASES:
            self.send_json({"error": "Preferred language is not supported."}, HTTPStatus.BAD_REQUEST)
            return
        language = normalize_language(raw_language)
        values = [1 if bool(payload.get(channel, channel == "in_app")) else 0 for channel in ("in_app", "email", "sms", "push")]
        with DB_LOCK, connect_database() as connection:
            connection.execute("""INSERT INTO notification_preferences(owner_type, owner_id, in_app, email, sms, push, preferred_language, updated_at)
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                  ON CONFLICT(owner_type, owner_id) DO UPDATE SET in_app=excluded.in_app, email=excluded.email, sms=excluded.sms, push=excluded.push, preferred_language=excluded.preferred_language, updated_at=excluded.updated_at""", (owner_type, actor["id"], *values, language, utc_now()))
            connection.commit()
        self.send_json({"updated": True, "in_app": values[0], "email": values[1], "sms": values[2], "push": values[3], "preferred_language": language})

    def translation_rows(self, user, locale: str) -> list[dict]:
        language = normalize_language(locale)
        catalog = static_translation_catalog().get(language, {})
        if not isinstance(catalog, dict):
            catalog = {}
        catalog = dict(catalog)
        for key, source in SERVER_MESSAGE_SOURCES.items():
            catalog[source] = SERVER_MESSAGES.get(language, {}).get(key) or source
        with DB_LOCK, connect_database() as connection:
            review_rows = connection.execute(
                "SELECT source_key, translation, status, reviewer, note, updated_at FROM translation_reviews WHERE company_id = ? AND locale = ?",
                (int(user["company_id"]), language),
            ).fetchall()
        reviews = {row["source_key"]: dict(row) for row in review_rows}
        rows = []
        for source in sorted(catalog, key=str.casefold):
            review = reviews.get(source)
            translation = str(review["translation"] if review else catalog[source])
            rows.append({
                "source": source,
                "translation": translation,
                "status": review["status"] if review else "machine",
                "reviewer": review["reviewer"] if review else "",
                "note": review["note"] if review else "",
                "updated_at": review["updated_at"] if review else "",
                "fallback": not translation.strip() or translation.strip() == source.strip(),
            })
        return rows

    def handle_translation_overrides(self, user) -> None:
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute(
                "SELECT locale, source_key, translation FROM translation_reviews WHERE company_id = ? AND status = 'approved' ORDER BY locale, source_key",
                (int(user["company_id"]),),
            ).fetchall()
        overrides = {}
        for row in rows:
            overrides.setdefault(row["locale"], {})[row["source_key"]] = row["translation"]
        self.send_json({"overrides": overrides})

    def handle_translations_get(self, user, query: str) -> None:
        parameters = parse_qs(query)
        locale = normalize_language(parameters.get("locale", ["pl-PL"])[0])
        if locale == "en-IE":
            locale = "pl-PL"
        search = parameters.get("search", [""])[0].strip().casefold()
        status_filter = parameters.get("status", [""])[0].strip().lower()
        page = max(int(parameters.get("page", ["1"])[0] or 1), 1)
        page_size = min(max(int(parameters.get("page_size", ["25"])[0] or 25), 10), 100)
        all_rows = self.translation_rows(user, locale)
        stats = {name: sum(row["status"] == name for row in all_rows) for name in ("machine", "in_review", "approved", "needs_changes")}
        stats.update({"fallback": sum(bool(row["fallback"]) for row in all_rows), "total": len(all_rows)})
        filtered = [
            row for row in all_rows
            if (not search or search in row["source"].casefold() or search in row["translation"].casefold())
            and (not status_filter or row["status"] == status_filter)
        ]
        start = (page - 1) * page_size
        self.send_json({
            "locale": locale,
            "language": LANGUAGE_NAMES.get(locale, locale),
            "supported_languages": [{"locale": key, "name": value} for key, value in LANGUAGE_NAMES.items() if key != "en-IE"],
            "stats": stats,
            "data": filtered[start:start + page_size],
            "page": page,
            "page_size": page_size,
            "filtered_total": len(filtered),
            "glossary": [{"term": term, "guidance": guidance} for term, guidance in SAFETY_GLOSSARY],
        })

    def handle_translations_export(self, user, query: str) -> None:
        parameters = parse_qs(query)
        locale = normalize_language(parameters.get("locale", ["pl-PL"])[0])
        if locale == "en-IE":
            locale = "pl-PL"
        output = io.StringIO(newline="")
        fieldnames = ("locale", "source", "translation", "status", "reviewer", "note")
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in self.translation_rows(user, locale):
            writer.writerow({"locale": locale, **{key: row[key] for key in fieldnames if key != "locale"}})
        body = ("\ufeff" + output.getvalue()).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="kompliance-translations-{locale}.csv"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_security_headers()
        self.end_headers()
        self.wfile.write(body)

    def save_translation_review(self, user, payload: dict) -> dict:
        locale = normalize_language(payload.get("locale"))
        source = str(payload.get("source", "")).strip()
        translation = str(payload.get("translation", "")).strip()
        status = str(payload.get("status", "in_review")).strip().lower()
        reviewer = str(payload.get("reviewer", "")).strip()[:120]
        note = str(payload.get("note", "")).strip()[:1000]
        if locale == "en-IE" or not source or not translation or status not in {"machine", "in_review", "approved", "needs_changes"}:
            raise ValueError("Locale, source, translation and a valid review status are required.")
        if source not in static_translation_catalog().get(locale, {}) and source not in SERVER_MESSAGE_SOURCES.values():
            raise ValueError("The source string is not part of the controlled catalogue.")
        if sorted(re.findall(r"\{[a-z_]+\}", source)) != sorted(re.findall(r"\{[a-z_]+\}", translation)):
            raise ValueError("Template placeholders must be preserved exactly in the reviewed translation.")
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            connection.execute(
                """
                INSERT INTO translation_reviews(company_id, locale, source_key, translation, status, reviewer, note, updated_by, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(company_id, locale, source_key) DO UPDATE SET
                    translation=excluded.translation, status=excluded.status, reviewer=excluded.reviewer,
                    note=excluded.note, updated_by=excluded.updated_by, updated_at=excluded.updated_at
                """,
                (int(user["company_id"]), locale, source, translation, status, reviewer, note, int(user.get("id") or 0) or None, now),
            )
            connection.commit()
        return {"locale": locale, "source": source, "translation": translation, "status": status, "reviewer": reviewer, "note": note, "updated_at": now}

    def handle_translation_review_update(self, user) -> None:
        try:
            result = self.save_translation_review(user, self.read_json_body())
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        self.write_audit(user, "translation_review_updated", "translation_reviews", summary=f"{result['locale']}: {result['source'][:120]}")
        self.send_json(result)

    def handle_translations_import(self, user) -> None:
        try:
            payload = self.read_json_body()
            csv_text = str(payload.get("csv", ""))
            if not csv_text.strip():
                raise ValueError("CSV content is required.")
            rows = list(csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff"))))
            if len(rows) > 5000:
                raise ValueError("CSV import is limited to 5,000 rows.")
            saved = [self.save_translation_review(user, row) for row in rows]
        except (ValueError, json.JSONDecodeError, csv.Error) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        self.write_audit(user, "translation_reviews_imported", "translation_reviews", summary=f"Imported {len(saved)} translation review rows")
        self.send_json({"imported": len(saved)}, HTTPStatus.CREATED)

    def handle_audit(self, query: str) -> None:
        user = self.require_user({"admin"})
        if user is None:
            return
        params = parse_qs(query)
        limit = min(max(int(params.get("limit", ["100"])[0]), 1), 500)
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_log WHERE company_id = ? ORDER BY id DESC LIMIT ?", (user["company_id"], limit)
            ).fetchall()
        self.send_json({"data": [dict(row) for row in rows], "total": len(rows)})

    def handle_users_get(self) -> None:
        user = self.require_user({"admin"})
        if user is None:
            return
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute(
                """
                SELECT users.id, users.email, users.name, users.role, users.active,
                       users.failed_attempts, users.locked_until, users.mfa_enabled, users.created_at, users.updated_at,
                       COUNT(sessions.token_hash) AS session_count
                FROM users LEFT JOIN sessions ON sessions.user_id = users.id
                WHERE users.company_id = ?
                GROUP BY users.id ORDER BY users.name
                """
                , (user["company_id"],)
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
                    INSERT INTO users(email, name, role, password_hash, active, created_at, updated_at, company_id)
                    VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (email, name, role, password_hash(password), now, now, user["company_id"]),
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
            existing = connection.execute("SELECT * FROM users WHERE id = ? AND company_id = ?", (user_id, user["company_id"])).fetchone()
            if existing is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            active_admins = connection.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin' AND active = 1 AND company_id = ?", (user["company_id"],)
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
            target = connection.execute("SELECT email FROM users WHERE id = ? AND company_id = ?", (user_id, user["company_id"])).fetchone()
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
                "SELECT id, email, name, company_id FROM users WHERE id = ? AND active = 1 AND company_id = ?", (user_id, user["company_id"])
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

    def handle_settings_get(self, user) -> None:
        self.send_json(
            {
                "settings": application_settings(int(user["company_id"])),
                "email": public_email_configuration(),
                "scheduler": dict(SCHEDULER_STATE),
            }
        )

    def handle_settings_update(self, user) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        updates = {}
        for key in DEFAULT_SETTINGS:
            if key not in payload:
                continue
            value = str(payload.get(key, "")).strip()
            if len(value) > 240:
                self.send_json({"error": f"{key} is too long."}, HTTPStatus.BAD_REQUEST)
                return
            updates[key] = value
        for numeric_key, minimum, maximum in (("reminder_days", 1, 365), ("retention_days", 30, 3650)):
            if numeric_key in updates:
                try:
                    updates[numeric_key] = str(min(max(int(updates[numeric_key]), minimum), maximum))
                except ValueError:
                    self.send_json({"error": f"{numeric_key} must be a number."}, HTTPStatus.BAD_REQUEST)
                    return
        for email_key in ("privacy_contact", "compliance_recipient", "company_email"):
            if updates.get(email_key) and "@" not in updates[email_key]:
                self.send_json({"error": f"{email_key} must be a valid email address."}, HTTPStatus.BAD_REQUEST)
                return
        with DB_LOCK, connect_database() as connection:
            for key, value in updates.items():
                connection.execute(
                    "INSERT INTO company_settings(company_id, key, value) VALUES (?, ?, ?) "
                    "ON CONFLICT(company_id, key) DO UPDATE SET value = excluded.value",
                    (user["company_id"], key, value),
                )
            if updates.get("brand_company"):
                connection.execute(
                    "UPDATE companies SET name = ?, updated_at = ? WHERE id = ?",
                    (updates["brand_company"], utc_now(), user["company_id"]),
                )
            connection.commit()
        self.write_audit(user, "settings_updated", "settings", summary=f"Updated: {', '.join(sorted(updates))}")
        self.handle_settings_get(user)

    def handle_system_status(self, user) -> None:
        company_id = int(user.get("company_id", 1))
        with DB_LOCK, connect_database() as connection:
            integrity = connection.execute("PRAGMA quick_check").fetchone()[0]
            rows = connection.execute("SELECT payload FROM records WHERE company_id = ?", (company_id,)).fetchall()
            active_sessions = connection.execute(
                "SELECT COUNT(*) FROM sessions JOIN users ON users.id = sessions.user_id WHERE sessions.expires_at > ? AND users.company_id = ?", (utc_now(), company_id)
            ).fetchone()[0]
            audit_events = connection.execute("SELECT COUNT(*) FROM audit_log WHERE company_id = ?", (company_id,)).fetchone()[0]
            migration_rows = connection.execute(
                "SELECT id, package_id, source_tenant, status, input_records, inserted_records, skipped_records, authorised_by, authorisation_reference, created_at, completed_at FROM tenant_migration_runs WHERE company_id = ? ORDER BY id DESC LIMIT 50",
                (company_id,),
            ).fetchall()
        protected = local = 0
        for row in rows:
            try:
                record = json.loads(row["payload"])
            except (TypeError, json.JSONDecodeError):
                continue
            if is_protected_payload(record):
                protected += 1
            elif record.get("local_only"):
                local += 1
        disk = shutil.disk_usage(DATA_ROOT)
        operations = {
            "available": False,
            "ready": False,
            "backups_enabled": False,
            "last_check_at": "",
            "last_check_error": "",
            "last_backup_at": "",
            "last_backup": None,
            "last_backup_error": "",
        }
        try:
            saved_operations = json.loads(
                (DATA_ROOT / "operations" / "status.json").read_text(encoding="utf-8")
            )
            if isinstance(saved_operations, dict):
                operations.update(saved_operations)
                operations["available"] = True
        except (OSError, json.JSONDecodeError):
            pass
        self.send_json(
            {
                "ok": integrity == "ok",
                "started_at": STARTED_AT,
                "database": {"integrity": integrity, "path": DATABASE_PATH.name},
                "records": {"protected": protected, "local": local, "total": len(rows)},
                "active_sessions": active_sessions,
                "audit_events": audit_events,
                "migrations": [dict(row) for row in migration_rows],
                "disk": {"free_bytes": disk.free, "total_bytes": disk.total},
                "email": public_email_configuration(),
                "scheduler": dict(SCHEDULER_STATE),
                "operations": operations,
                "retention_preview": retention_cleanup(dry_run=True, company_id=company_id),
            }
        )

    def handle_review_readiness(self, user) -> None:
        self.send_json(build_review_readiness(int(user.get("company_id", 1))))

    def handle_review_acceptance_update(self, user) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        decision = str(payload.get("decision", "pending")).strip().lower()
        allowed_decisions = {
            "pending",
            "accepted",
            "accepted_with_conditions",
            "rejected",
        }
        if decision not in allowed_decisions:
            self.send_json({"error": "Select a valid review decision."}, HTTPStatus.BAD_REQUEST)
            return
        text_values = {}
        for key, maximum in (
            ("reviewer_name", 160),
            ("product_owner", 160),
            ("technical_owner", 160),
            ("conditions", 4000),
        ):
            value = str(payload.get(key, "")).strip()
            if len(value) > maximum:
                self.send_json({"error": f"{key} is too long."}, HTTPStatus.BAD_REQUEST)
                return
            text_values[key] = value
        supplied_checklist = payload.get("checklist", {})
        if not isinstance(supplied_checklist, dict):
            self.send_json({"error": "Checklist must be an object."}, HTTPStatus.BAD_REQUEST)
            return
        checklist = {
            key: bool(supplied_checklist.get(key)) for key, _ in PILOT_REVIEW_CHECKLIST
        }
        company_id = int(user.get("company_id", 1))
        now = utc_now()
        with DB_LOCK, connect_database() as connection:
            connection.execute(
                """
                INSERT INTO pilot_acceptance(
                    company_id, reviewer_name, product_owner, technical_owner,
                    decision, conditions, checklist_json, updated_by, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(company_id) DO UPDATE SET
                    reviewer_name = excluded.reviewer_name,
                    product_owner = excluded.product_owner,
                    technical_owner = excluded.technical_owner,
                    decision = excluded.decision,
                    conditions = excluded.conditions,
                    checklist_json = excluded.checklist_json,
                    updated_by = excluded.updated_by,
                    updated_at = excluded.updated_at
                """,
                (
                    company_id,
                    text_values["reviewer_name"],
                    text_values["product_owner"],
                    text_values["technical_owner"],
                    decision,
                    text_values["conditions"],
                    json.dumps(checklist),
                    user.get("id") or None,
                    now,
                ),
            )
            connection.commit()
        completed = sum(checklist.values())
        self.write_audit(
            user,
            "pilot_acceptance_updated",
            "pilot_acceptance",
            summary=f"Decision {decision}; checklist {completed}/{len(checklist)}",
        )
        self.send_json(build_review_readiness(company_id))

    def handle_review_email_test(self, user) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        if payload.get("confirmation") != "SEND_CONTROLLED_TEST":
            self.send_json(
                {"error": "Exact controlled-test confirmation is required."},
                HTTPStatus.BAD_REQUEST,
            )
            return
        recipient = str(payload.get("recipient", "")).strip().lower()
        if (
            len(recipient) > 254
            or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", recipient)
        ):
            self.send_json(
                {"error": "Enter one valid controlled-test recipient."},
                HTTPStatus.BAD_REQUEST,
            )
            return
        configuration = public_email_configuration()
        company_id = int(user.get("company_id", 1))
        created_at = utc_now()
        status = "failed"
        safe_error = ""
        try:
            send_notification_email(
                {
                    "recipient": recipient,
                    "subject": "Kompliance controlled delivery test",
                    "message": (
                        "This controlled message confirms that the Kompliance application "
                        f"can deliver email through its configured provider.\n\nTest time: {created_at}\n"
                        "No customer document or personal record is attached."
                    ),
                }
            )
            status = "sent"
        except Exception as error:
            safe_error = safe_delivery_error(error)
        with DB_LOCK, connect_database() as connection:
            cursor = connection.execute(
                """
                INSERT INTO email_diagnostic_runs(
                    company_id, requested_by, recipient, provider, status, safe_error, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    company_id,
                    user.get("id") or None,
                    recipient,
                    configuration["provider"],
                    status,
                    safe_error,
                    created_at,
                ),
            )
            connection.commit()
            diagnostic_id = cursor.lastrowid
        self.write_audit(
            user,
            "controlled_email_test",
            "email_diagnostic_runs",
            diagnostic_id,
            f"{configuration['provider']} diagnostic {status} for {mask_email(recipient)}",
        )
        response = {
            "id": diagnostic_id,
            "status": status,
            "recipient": mask_email(recipient),
            "provider": configuration["provider"],
            "created_at": created_at,
            "safe_error": safe_error,
        }
        if status != "sent":
            response["error"] = safe_error or "Controlled email test failed."
        self.send_json(
            response,
            HTTPStatus.CREATED if status == "sent" else HTTPStatus.BAD_GATEWAY,
        )

    def handle_notifications_send(self, user) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        identifiers = payload.get("ids")
        record_ids = None
        if isinstance(identifiers, list):
            record_ids = {int(value) for value in identifiers if str(value).isdigit()}
        result = dispatch_notification_queue(
            limit=min(max(int(payload.get("limit", 100)), 1), 500), record_ids=record_ids, company_id=int(user.get("company_id", 1))
        )
        self.write_audit(
            user,
            "notification_delivery_run",
            "local_notifications",
            summary=f"Sent {result['sent']}; failed {result['failed']}; skipped {result['skipped']}",
        )
        self.send_json(result)

    def handle_retention_cleanup(self, user) -> None:
        try:
            payload = self.read_json_body()
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        if payload.get("confirmation") != "PURGE_LOCAL_EXPIRED_DATA":
            self.send_json(
                {"error": "Exact confirmation PURGE_LOCAL_EXPIRED_DATA is required."},
                HTTPStatus.BAD_REQUEST,
            )
            return
        result = retention_cleanup(dry_run=False, company_id=int(user.get("company_id", 1)))
        self.write_audit(
            user,
            "retention_cleanup",
            "local_notifications",
            summary=f"Removed {result['local_notifications']} expired local notification(s); protected records removed: 0",
        )
        self.send_json(result)

    def handle_privacy_page(self) -> None:
        privacy_user = self.current_user()
        settings = application_settings(int(privacy_user["company_id"]) if privacy_user else 1)
        brand = html.escape(settings.get("brand_name", "Kompliance"))
        contact = html.escape(settings.get("privacy_contact") or "Contact your organisation administrator")
        retention = html.escape(settings.get("retention_days", "365"))
        markup = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Privacy · {brand}</title></head><body style='font:16px/1.6 system-ui;background:#f4f8f7;color:#17324d;margin:0'><main style='max-width:760px;margin:3rem auto;background:white;padding:2.5rem;border-radius:20px'><p style='color:#08745d;font-weight:700'>{brand}</p><h1>Privacy and data handling</h1><p>This controlled workspace stores health and safety administration records for authorised organisational users. Access is role-based and security-sensitive changes are audited.</p><h2>Data boundaries</h2><p>Imported customer snapshot records are immutable. New assignments, submissions, evidence, certificates, notifications and account records are stored separately in the local application data area.</p><h2>Retention</h2><p>Prepared notification history is retained for up to {retention} days unless the organisation changes that setting. Expired sessions and reset tokens can be removed by an administrator. Protected imported records are never removed by the retention tool.</p><h2>Your rights and contact</h2><p>For access, correction, retention or deletion requests, contact: <strong>{contact}</strong>.</p><p><a href='/'>Return to Kompliance</a></p></main></body></html>"""
        self.send_html(markup)

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
                "SELECT payload FROM records WHERE resource = 'local_uploads' AND company_id = ?", (user["company_id"],)
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
                "INSERT INTO records(resource, payload, created_at, updated_at, company_id) VALUES ('local_uploads', ?, ?, ?, ?)",
                (json.dumps(payload), now, now, user["company_id"]),
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
            distribution = local_record(connection, "distributions", int(distribution_id), user["company_id"])
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
                "INSERT INTO records(resource, payload, created_at, updated_at, company_id) VALUES ('local_evidence', ?, ?, ?, ?)",
                (json.dumps(payload), now, now, user["company_id"]),
            )
            connection.commit()
        self.write_audit(user, "evidence_uploaded", "local_evidence", cursor.lastrowid, f"Evidence attached to assignment {distribution_id}")
        self.send_json(
            {"id": cursor.lastrowid, **payload, "url": f"/local-files/evidence/{stored_name}"},
            HTTPStatus.CREATED,
        )

    def form_definition_for_assignment(self, connection, distribution, company_id: int):
        rows = connection.execute("SELECT * FROM records WHERE resource = 'forms' AND company_id = ?", (company_id,)).fetchall()
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
            locale = normalize_language(
                payload.get("language")
                or preferred_language_for_owner(connection, "user", int(user["id"]))
            )
            translation_overrides = approved_translation_overrides(
                connection, int(user["company_id"]), locale
            )
            translated = lambda source: translation_overrides.get(source) or translate_ui(source, locale)
            distribution = local_record(connection, "distributions", int(distribution_id), user["company_id"])
            if distribution is None:
                self.send_json({"error": "Local assignment not found."}, HTTPStatus.NOT_FOUND)
                return
            form_record = self.form_definition_for_assignment(connection, distribution, user["company_id"])
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
                    f"SELECT * FROM records WHERE resource = 'local_evidence' AND company_id = ? AND id IN ({placeholders})",
                    [user["company_id"], *safe_attachment_ids],
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
                "language": locale,
                "source": "local controlled workspace",
                "local_only": True,
            }
            if status == "submitted":
                record_payload["submitted_at"] = now
                report_root = DATA_ROOT / "reports"
                report_root.mkdir(parents=True, exist_ok=True)
                report_name = f"submission-{secrets.token_hex(12)}.pdf"
                report_lines = [
                    f"{translated('Worker')}: {record_payload['worker']}",
                    f"{translated('Site')}: {record_payload['site']}",
                    f"{translated('Status')}: {translated('Submitted at')} {now}",
                    "",
                ]
                for answer in normalized_answers:
                    value = f"[{translated('Captured signature')}]" if answer["type"] == "Sign" and answer["value"] else answer["value"]
                    report_lines.extend([f"{answer['section']} / {answer['question']}", f"{translated('Answer')}: {value}", ""])
                if evidence:
                    report_lines.append(translated("Attachments") + ": " + ", ".join(item.get("original_name", "") for item in evidence))
                (report_root / report_name).write_bytes(
                    build_text_pdf(
                        record_payload["form"],
                        translated("Controlled local form submission"),
                        report_lines,
                        locale,
                        translation_overrides,
                    )
                )
                record_payload["report_file"] = report_name
            existing = None
            if str(submission_id).isdigit():
                existing = local_record(connection, "local_submissions", int(submission_id), user["company_id"])
                if existing and existing.get("distribution_id") != int(distribution_id):
                    existing = None
            if existing:
                record_id = int(submission_id)
                connection.execute(
                    "UPDATE records SET payload = ?, updated_at = ? WHERE resource = 'local_submissions' AND id = ? AND company_id = ?",
                    (json.dumps(record_payload), now, record_id, user["company_id"]),
                )
            else:
                cursor = connection.execute(
                    "INSERT INTO records(resource, payload, created_at, updated_at, company_id) VALUES ('local_submissions', ?, ?, ?, ?)",
                    (json.dumps(record_payload), now, now, user["company_id"]),
                )
                record_id = cursor.lastrowid
            if status == "submitted":
                distribution_payload = {key: value for key, value in distribution.items() if key not in {"id", "_read_only", "created_at", "updated_at"}}
                distribution_payload.update({"status": "Submitted", "submitted_date": now[:10], "submission_id": record_id})
                connection.execute(
                    "UPDATE records SET payload = ?, updated_at = ? WHERE resource = 'distributions' AND id = ? AND company_id = ?",
                    (json.dumps(distribution_payload), now, int(distribution_id), user["company_id"]),
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
        settings = application_settings(int(user["company_id"]))
        with DB_LOCK, connect_database() as language_connection:
            locale = normalize_language(
                payload.get("language")
                or preferred_language_for_owner(language_connection, "user", int(user["id"]))
            )
            translation_overrides = approved_translation_overrides(
                language_connection, int(user["company_id"]), locale
            )
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
            settings.get("brand_name", "Kompliance"),
            settings.get("brand_tagline", "Health & Safety Operations"),
            locale,
            translation_overrides,
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
            "language": locale,
            "source": "local controlled workspace",
            "local_only": True,
        }
        with DB_LOCK, connect_database() as connection:
            cursor = connection.execute(
                "INSERT INTO records(resource, payload, created_at, updated_at, company_id) VALUES ('local_induction_completions', ?, ?, ?, ?)",
                (json.dumps(record_payload), completed_at, completed_at, user["company_id"]),
            )
            record_id = cursor.lastrowid
            if str(replaces_id).isdigit():
                previous = local_record(connection, "local_induction_completions", int(replaces_id), user["company_id"])
                if previous:
                    previous_payload = {key: value for key, value in previous.items() if key not in {"id", "_read_only", "created_at", "updated_at"}}
                    previous_payload.update({"status": "Replaced", "replaced_by": record_id, "replaced_at": completed_at})
                    connection.execute(
                        "UPDATE records SET payload = ?, updated_at = ? WHERE resource = 'local_induction_completions' AND id = ? AND company_id = ?",
                        (json.dumps(previous_payload), completed_at, int(replaces_id), user["company_id"]),
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
            record = local_record(connection, "local_induction_completions", record_id, user["company_id"])
            if record is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if record.get("status") != "Active":
                self.send_json({"error": "Only an active certificate can be revoked."}, HTTPStatus.CONFLICT)
                return
            updated = {key: value for key, value in record.items() if key not in {"id", "_read_only", "created_at", "updated_at"}}
            updated.update({"status": "Revoked", "revoked_at": now, "revocation_reason": reason})
            connection.execute(
                "UPDATE records SET payload = ?, updated_at = ? WHERE resource = 'local_induction_completions' AND id = ? AND company_id = ?",
                (json.dumps(updated), now, record_id, user["company_id"]),
            )
            connection.commit()
        self.write_audit(user, "certificate_revoked", "local_induction_completions", record_id, reason)
        self.send_json({"id": record_id, **updated})

    def compliance_reminder_data(self, days: int):
        company_id = int(getattr(self, "request_user", {}).get("company_id", 1))
        return build_compliance_reminder_data(days, company_id)

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
        result = prepare_compliance_notifications(days, int(user.get("company_id", 1)))
        self.write_audit(
            user,
            "notifications_prepared",
            "local_notifications",
            summary=f"Prepared {result['created']} compliance reminder(s); {result['duplicates']} duplicate(s) skipped",
        )
        self.send_json(result, HTTPStatus.CREATED)

    def handle_public_certificate(self, token: str) -> None:
        with DB_LOCK, connect_database() as connection:
            rows = connection.execute(
                "SELECT * FROM records WHERE resource = 'local_induction_completions' ORDER BY id DESC"
            ).fetchall()
        certificates = [row_to_record(row) for row in rows]
        certificate = next(
            (record for record in certificates if record.get("verification_token") == token), None
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
        brand = html.escape(application_settings().get("brand_name", "Kompliance").upper())
        colour = "#0f8b6d" if status == "Active" else "#c2414b"
        markup = f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Certificate verification</title></head>
        <body style='margin:0;background:#f3f7f6;font-family:system-ui;color:#17324a'><main style='max-width:680px;margin:8vh auto;background:white;border-radius:18px;padding:2rem;box-shadow:0 20px 60px #17324a20'>
        <div style='color:#0f6f5b;font-weight:800;letter-spacing:.08em'>{brand}</div><h1>Certificate verification</h1>
        <p style='display:inline-block;background:{colour};color:white;border-radius:999px;padding:.45rem .85rem;font-weight:700'>{html.escape(status)}</p>
        <dl style='display:grid;grid-template-columns:10rem 1fr;gap:.8rem;border-top:1px solid #dce7e4;padding-top:1.5rem'>
        <dt>Certificate</dt><dd>{safe['certificate_number']}</dd><dt>Company</dt><dd>{safe['company']}</dd><dt>Worker</dt><dd>{safe['worker']}</dd><dt>Induction</dt><dd>{safe['induction']}</dd><dt>Site</dt><dd>{safe['site']}</dd><dt>Completed</dt><dd>{safe['completed_at']}</dd><dt>Valid until</dt><dd>{safe['expires_at']}</dd></dl>
        <p style='color:#61758a'>Always rely on the status shown on this page, not a downloaded copy.</p></main></body></html>"""
        self.send_html(markup)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/api/health":
            self.send_json({"ok": True, "service": "kompliance-local", "started_at": STARTED_AT})
            return
        if path == "/api/health/ready":
            try:
                with DB_LOCK, connect_database() as connection:
                    database_ok = connection.execute("SELECT 1").fetchone()[0] == 1
                ready = bool(database_ok and DATA_ROOT.exists() and ARCHIVE_ROOT.exists())
            except sqlite3.Error:
                ready = False
            self.send_json({"ok": ready, "service": "kompliance-local"}, HTTPStatus.OK if ready else HTTPStatus.SERVICE_UNAVAILABLE)
            return
        if path == "/api/auth/status":
            self.handle_auth_status()
            return
        if path == "/api/auth/mfa":
            self.handle_auth_mfa_status()
            return
        if path == "/api/public/companies":
            self.handle_public_companies()
            return
        if path.startswith("/api/public/induction/"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[:3] == ["api", "public", "induction"]:
                self.handle_public_induction_schema(parts[3])
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
            return
        if path == "/api/openapi.json":
            self.send_file(STATIC_ROOT / "openapi.json", cache=True)
            return
        if path == "/api/worker/status":
            self.handle_worker_status()
            return
        if path == "/api/worker/verify":
            self.handle_worker_verify(parsed.query)
            return
        if path == "/api/v1/shared-workers":
            self.handle_api_shared_workers(parsed.query)
            return
        if path.startswith("/api/v1/workers/"):
            self.handle_api_worker_resource(path)
            return
        if path in {"/worker", "/worker/"}:
            self.send_file(STATIC_ROOT / "worker.html")
            return
        if path.startswith("/worker-static/"):
            self.send_file(STATIC_ROOT / path.removeprefix("/worker-static/"), cache=True)
            return
        if path.startswith("/induction-static/"):
            self.send_file(STATIC_ROOT / path.removeprefix("/induction-static/"), cache=True)
            return
        if path.startswith("/induction/c/"):
            parts = path.strip("/").split("/")
            if len(parts) in {3, 4} and parts[:2] == ["induction", "c"] and (len(parts) == 3 or parts[3] == "register"):
                if self.public_induction_site(parts[2]) is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                else:
                    self.send_file(STATIC_ROOT / "induction-register.html")
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
            return
        if path.startswith("/worker/public/"):
            self.handle_public_worker_profile(path.removeprefix("/worker/public/").strip("/"))
            return
        if path.startswith("/worker/share/"):
            parts = path.strip("/").split("/")
            if len(parts) == 5 and parts[:2] == ["worker", "share"] and parts[2] and parts[3] == "documents" and parts[4].isdigit():
                self.handle_public_shared_document(parts[2], int(parts[4]))
            elif len(parts) == 3:
                self.handle_public_worker_share(parts[2])
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
            return
        if path.startswith("/api/worker/"):
            worker = self.require_worker()
            if worker is None:
                return
            if path == "/api/worker/documents":
                self.handle_worker_documents_get(worker)
                return
            if path == "/api/worker/shares":
                self.handle_worker_shares_get(worker)
                return
            if path == "/api/worker/access-requests":
                self.handle_worker_access_requests_get(worker)
                return
            if path == "/api/worker/requests":
                self.handle_worker_requests_get(worker)
                return
            if path == "/api/worker/conversations":
                self.handle_worker_conversations_get(worker)
                return
            if path == "/api/worker/induction-reviews":
                self.handle_worker_inductions_get(worker)
                return
            if path == "/api/worker/notifications":
                self.handle_notifications_get(worker, "worker")
                return
            if path == "/api/worker/preferences":
                self.handle_preferences_get(worker, "worker")
                return
            if path == "/api/worker/qr":
                self.handle_worker_qr(worker)
                return
            worker_document = path.strip("/").split("/")
            if len(worker_document) == 5 and worker_document[:3] == ["api", "worker", "documents"] and worker_document[3].isdigit() and worker_document[4] == "file":
                self.handle_worker_document_file(worker, int(worker_document[3]))
                return
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if path.startswith("/verify/"):
            token = path.removeprefix("/verify/").strip("/")
            self.handle_public_certificate(token)
            return
        if path == "/privacy":
            self.handle_privacy_page()
            return
        if path.startswith("/static/"):
            relative = path.removeprefix("/static/")
            self.send_file(STATIC_ROOT / relative, cache=True)
            return
        if path in {"/favicon.ico", "/favicon.svg"}:
            self.send_file(STATIC_ROOT / "favicon.svg", cache=True)
            return
        if path == "/archive/static-assets/logo.svg":
            self.send_file(ARCHIVE_ROOT / "static-assets" / "logo.svg", cache=True)
            return
        if path.startswith("/api/") or path.startswith("/archive/") or path.startswith("/examples/") or path.startswith("/local-files/"):
            request_user = self.require_user()
            if request_user is None:
                return
            self.request_user = request_user
            if request_user.get("company_id") != 1 and (path == "/api/archive" or path.startswith("/archive/") or path.startswith("/examples/")):
                self.send_json({"error": "This tenant has no imported source archive."}, HTTPStatus.FORBIDDEN)
                return
        if path == "/api/audit":
            self.handle_audit(parsed.query)
            return
        if path == "/api/translations/overrides":
            self.handle_translation_overrides(self.request_user)
            return
        if path in {"/api/translations", "/api/translations/export"}:
            if self.request_user.get("role") != "admin":
                self.send_json({"error": "Administrator role required."}, HTTPStatus.FORBIDDEN)
                return
            if path.endswith("/export"):
                self.handle_translations_export(self.request_user, parsed.query)
            else:
                self.handle_translations_get(self.request_user, parsed.query)
            return
        if path == "/api/users":
            self.handle_users_get()
            return
        if path == "/api/companies":
            self.handle_companies_get(self.request_user)
            return
        if path == "/api/company/shared-workers":
            self.handle_company_shared_workers(self.request_user)
            return
        if path == "/api/company/worker-access-requests":
            self.handle_company_access_requests_get(self.request_user)
            return
        if path == "/api/company/api-tokens":
            self.handle_company_api_tokens_get(self.request_user)
            return
        if path == "/api/company/departments":
            self.handle_departments_get(self.request_user)
            return
        if path == "/api/company/requests":
            self.handle_company_requests_get(self.request_user)
            return
        if path == "/api/company/conversations":
            self.handle_company_conversations_get(self.request_user)
            return
        if path == "/api/company/induction-reviews":
            self.handle_company_inductions_get(self.request_user)
            return
        if path == "/api/company/induction-sites":
            self.handle_company_induction_sites_get(self.request_user)
            return
        if path == "/api/company/induction-registrations":
            self.handle_company_induction_registrations_get(self.request_user)
            return
        induction_site_parts = path.strip("/").split("/")
        if (
            len(induction_site_parts) == 5
            and induction_site_parts[:3] == ["api", "company", "induction-sites"]
            and induction_site_parts[3].isdigit()
            and induction_site_parts[4] == "qr"
        ):
            self.handle_company_induction_site_qr(self.request_user, int(induction_site_parts[3]))
            return
        if (
            len(induction_site_parts) == 7
            and induction_site_parts[:3] == ["api", "company", "induction-registrations"]
            and induction_site_parts[3].isdigit()
            and induction_site_parts[4] == "evidence"
            and induction_site_parts[5].isdigit()
            and induction_site_parts[6] == "file"
        ):
            self.handle_company_induction_evidence_file(
                self.request_user,
                int(induction_site_parts[3]),
                int(induction_site_parts[5]),
            )
            return
        if path == "/api/company/notifications":
            self.handle_notifications_get(self.request_user, "user")
            return
        if path == "/api/company/preferences":
            self.handle_preferences_get(self.request_user, "user")
            return
        company_document = path.strip("/").split("/")
        if len(company_document) == 5 and company_document[:3] == ["api", "company", "worker-documents"] and company_document[3].isdigit() and company_document[4] == "file":
            self.handle_company_document_file(self.request_user, int(company_document[3]))
            return
        if path == "/api/settings":
            settings_user = self.require_user()
            if settings_user is not None:
                self.handle_settings_get(settings_user)
            return
        if path == "/api/system/status":
            status_user = self.require_user({"admin"})
            if status_user is not None:
                self.handle_system_status(status_user)
            return
        if path == "/api/review/readiness":
            review_user = self.require_user({"admin"})
            if review_user is not None:
                self.handle_review_readiness(review_user)
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
            self.send_local_file(parts[0], parts[1], int(self.request_user["company_id"]))
            return
        self.send_file(STATIC_ROOT / "index.html")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/public/induction/"):
            parts = unquote(parsed.path).strip("/").split("/")
            if (
                len(parts) == 5
                and parts[:3] == ["api", "public", "induction"]
                and parts[4] == "registrations"
            ):
                self.handle_public_induction_registration_create(parts[3])
            elif (
                len(parts) == 7
                and parts[:3] == ["api", "public", "induction"]
                and parts[4] == "registrations"
                and parts[5].isdigit()
                and parts[6] == "evidence"
            ):
                self.handle_public_induction_evidence(parts[3], int(parts[5]))
            elif (
                len(parts) == 7
                and parts[:3] == ["api", "public", "induction"]
                and parts[4] == "registrations"
                and parts[5].isdigit()
                and parts[6] == "complete"
            ):
                self.handle_public_induction_complete(parts[3], int(parts[5]))
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
            return
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
        if parsed.path == "/api/auth/mfa/setup":
            self.handle_auth_mfa_setup()
            return
        if parsed.path == "/api/auth/mfa/enable":
            self.handle_auth_mfa_enable()
            return
        if parsed.path == "/api/auth/mfa/disable":
            self.handle_auth_mfa_disable()
            return
        if parsed.path == "/api/auth/recovery/request":
            self.handle_auth_recovery_request()
            return
        if parsed.path == "/api/auth/recovery/reset":
            self.handle_auth_recovery_reset()
            return
        if parsed.path == "/api/worker/register":
            self.handle_worker_register()
            return
        if parsed.path == "/api/worker/login":
            self.handle_worker_login()
            return
        if parsed.path == "/api/worker/recovery/request":
            self.handle_worker_recovery_request()
            return
        if parsed.path == "/api/worker/recovery/reset":
            self.handle_worker_recovery_reset()
            return
        if parsed.path.startswith("/api/worker/"):
            worker = self.require_worker()
            if worker is None or not self.require_worker_csrf(worker):
                return
            if parsed.path == "/api/worker/logout":
                self.handle_worker_logout(worker)
                return
            if parsed.path == "/api/worker/documents":
                self.handle_worker_document_upload(worker)
                return
            if parsed.path == "/api/worker/shares":
                self.handle_worker_share_create(worker)
                return
            if parsed.path == "/api/worker/access-requests":
                self.send_json({"error": "Access requests are created by companies and answered by workers."}, HTTPStatus.METHOD_NOT_ALLOWED)
                return
            if parsed.path == "/api/worker/requests":
                self.handle_worker_request_create(worker)
                return
            worker_workflow = parsed.path.strip("/").split("/")
            if len(worker_workflow) == 5 and worker_workflow[:3] == ["api", "worker", "conversations"] and worker_workflow[3].isdigit() and worker_workflow[4] == "messages":
                self.handle_conversation_message(worker, int(worker_workflow[3]), "worker")
                return
            if len(worker_workflow) == 5 and worker_workflow[:3] == ["api", "worker", "notifications"] and worker_workflow[3].isdigit() and worker_workflow[4] == "read":
                self.handle_notification_read(worker, "worker", int(worker_workflow[3]))
                return
            share_parts = parsed.path.strip("/").split("/")
            if len(share_parts) == 5 and share_parts[:3] == ["api", "worker", "access-requests"] and share_parts[3].isdigit() and share_parts[4] == "respond":
                self.handle_worker_access_request_respond(worker, int(share_parts[3]))
                return
            if len(share_parts) == 5 and share_parts[:3] == ["api", "worker", "shares"] and share_parts[3].isdigit() and share_parts[4] == "revoke":
                self.handle_worker_share_revoke(worker, int(share_parts[3]))
                return
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if parsed.path.startswith("/api/company/notifications/"):
            notification_user = self.require_user()
            if notification_user is None or not self.require_csrf(notification_user):
                return
            notification_parts = parsed.path.strip("/").split("/")
            if len(notification_parts) == 5 and notification_parts[:3] == ["api", "company", "notifications"] and notification_parts[3].isdigit() and notification_parts[4] == "read":
                self.handle_notification_read(notification_user, "user", int(notification_parts[3]))
                return
            self.send_error(HTTPStatus.NOT_FOUND)
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
        if parsed.path == "/api/translations/import":
            if user.get("role") != "admin":
                self.send_json({"error": "Administrator role required."}, HTTPStatus.FORBIDDEN)
                return
            self.handle_translations_import(user)
            return
        if parsed.path == "/api/companies":
            if user.get("role") != "admin":
                self.send_json({"error": "Administrator role required."}, HTTPStatus.FORBIDDEN)
                return
            self.handle_company_create(user)
            return
        if parsed.path == "/api/company/api-tokens":
            if user.get("role") != "admin":
                self.send_json({"error": "Administrator role required."}, HTTPStatus.FORBIDDEN)
                return
            self.handle_company_api_token_create(user)
            return
        if parsed.path == "/api/company/departments":
            if user.get("role") != "admin":
                self.send_json({"error": "Administrator role required."}, HTTPStatus.FORBIDDEN)
                return
            self.handle_department_create(user)
            return
        if parsed.path == "/api/company/requests":
            self.handle_company_request_create(user)
            return
        if parsed.path == "/api/company/worker-access-requests":
            self.handle_company_access_request_create(user)
            return
        if parsed.path == "/api/company/induction-reviews":
            self.handle_company_induction_create(user)
            return
        company_parts = parsed.path.strip("/").split("/")
        if len(company_parts) == 5 and company_parts[:3] == ["api", "company", "requests"] and company_parts[3].isdigit() and company_parts[4] == "status":
            self.handle_company_request_status(user, int(company_parts[3]))
            return
        if len(company_parts) == 5 and company_parts[:3] == ["api", "company", "conversations"] and company_parts[3].isdigit() and company_parts[4] == "messages":
            self.handle_conversation_message(user, int(company_parts[3]), "user")
            return
        if len(company_parts) == 5 and company_parts[:3] == ["api", "company", "induction-reviews"] and company_parts[3].isdigit() and company_parts[4] == "status":
            self.handle_company_induction_status(user, int(company_parts[3]))
            return
        if len(company_parts) == 5 and company_parts[:3] == ["api", "company", "shared-workers"] and company_parts[3].isdigit() and company_parts[4] == "import":
            self.handle_company_import_worker(user, int(company_parts[3]))
            return
        if len(company_parts) == 5 and company_parts[:3] == ["api", "company", "worker-documents"] and company_parts[3].isdigit() and company_parts[4] == "review":
            self.handle_company_document_review(user, int(company_parts[3]))
            return
        if len(company_parts) == 5 and company_parts[:3] == ["api", "company", "api-tokens"] and company_parts[3].isdigit() and company_parts[4] == "revoke":
            if user.get("role") != "admin":
                self.send_json({"error": "Administrator role required."}, HTTPStatus.FORBIDDEN)
                return
            self.handle_company_api_token_revoke(user, int(company_parts[3]))
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
        if parsed.path == "/api/compliance/notifications/send":
            if user.get("role") != "admin":
                self.send_json({"error": "Administrator role required."}, HTTPStatus.FORBIDDEN)
                return
            self.handle_notifications_send(user)
            return
        if parsed.path == "/api/system/retention-cleanup":
            if user.get("role") != "admin":
                self.send_json({"error": "Administrator role required."}, HTTPStatus.FORBIDDEN)
                return
            self.handle_retention_cleanup(user)
            return
        if parsed.path == "/api/review/email-test":
            if user.get("role") != "admin":
                self.send_json({"error": "Administrator role required."}, HTTPStatus.FORBIDDEN)
                return
            self.handle_review_email_test(user)
            return
        if parsed.path.startswith("/api/resources/"):
            self.handle_resource_create(parsed.path)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_PUT(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/worker/profile":
            worker = self.require_worker()
            if worker is not None and self.require_worker_csrf(worker):
                self.handle_worker_profile_update(worker)
            return
        if parsed.path == "/api/worker/preferences":
            worker = self.require_worker()
            if worker is not None and self.require_worker_csrf(worker):
                self.handle_preferences_update(worker, "worker")
            return
        if parsed.path == "/api/company/preferences":
            preference_user = self.require_user()
            if preference_user is not None and self.require_csrf(preference_user):
                self.handle_preferences_update(preference_user, "user")
            return
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
        if parsed.path == "/api/settings":
            if user.get("role") != "admin":
                self.send_json({"error": "Administrator role required."}, HTTPStatus.FORBIDDEN)
                return
            self.handle_settings_update(user)
            return
        if parsed.path == "/api/translations/review":
            if user.get("role") != "admin":
                self.send_json({"error": "Administrator role required."}, HTTPStatus.FORBIDDEN)
                return
            self.handle_translation_review_update(user)
            return
        if parsed.path == "/api/review/acceptance":
            if user.get("role") != "admin":
                self.send_json({"error": "Administrator role required."}, HTTPStatus.FORBIDDEN)
                return
            self.handle_review_acceptance_update(user)
            return
        department_parts = parsed.path.strip("/").split("/")
        if len(department_parts) == 4 and department_parts[:3] == ["api", "company", "departments"] and department_parts[3].isdigit():
            if user.get("role") != "admin":
                self.send_json({"error": "Administrator role required."}, HTTPStatus.FORBIDDEN)
                return
            self.handle_department_update(user, int(department_parts[3]))
            return
        if parsed.path.startswith("/api/resources/"):
            self.handle_resource_update(parsed.path)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        worker_parts = parsed.path.strip("/").split("/")
        if len(worker_parts) == 4 and worker_parts[:3] == ["api", "worker", "documents"] and worker_parts[3].isdigit():
            worker = self.require_worker()
            if worker is not None and self.require_worker_csrf(worker):
                self.handle_worker_document_delete(worker, int(worker_parts[3]))
            return
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
        company_id = int(getattr(self, "request_user", {}).get("company_id", 1))
        with DB_LOCK, connect_database() as connection:
            counts = {
                resource: connection.execute(
                    "SELECT COUNT(*) FROM records WHERE resource = ? AND company_id = ?",
                    (resource, company_id),
                ).fetchone()[0]
                for resource in resources
            }
            pending_workers = connection.execute(
                """
                SELECT payload FROM records
                WHERE resource = 'workers' AND company_id = ?
                """
                , (company_id,)
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
        if company_id == 1:
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
        company_id = int(getattr(self, "request_user", {}).get("company_id", 1))

        with DB_LOCK, connect_database() as connection:
            if record_id is not None:
                row = connection.execute(
                    "SELECT * FROM records WHERE resource = ? AND id = ? AND company_id = ?",
                    (resource, record_id, company_id),
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
                WHERE resource = ? AND company_id = ?
                ORDER BY id DESC
                """,
                (resource, company_id),
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
        company_id = int(getattr(self, "request_user", {}).get("company_id", 1))
        with DB_LOCK, connect_database() as connection:
            cursor = connection.execute(
                """
                INSERT INTO records(resource, payload, created_at, updated_at, company_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (resource, json.dumps(payload), now, now, company_id),
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
        company_id = int(getattr(self, "request_user", {}).get("company_id", 1))
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
                "SELECT payload FROM records WHERE resource = ? AND id = ? AND company_id = ?",
                (resource, record_id, company_id),
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
                WHERE resource = ? AND id = ? AND company_id = ?
                """,
                (json.dumps(payload), now, resource, record_id, company_id),
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
        company_id = int(getattr(self, "request_user", {}).get("company_id", 1))
        with DB_LOCK, connect_database() as connection:
            existing = connection.execute(
                "SELECT payload FROM records WHERE resource = ? AND id = ? AND company_id = ?",
                (resource, record_id, company_id),
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
                "DELETE FROM records WHERE resource = ? AND id = ? AND company_id = ?",
                (resource, record_id, company_id),
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


def run_scheduled_maintenance() -> dict:
    settings = application_settings()
    days = min(max(int(settings.get("reminder_days", "30")), 1), 365)
    prepared = prepare_compliance_notifications(days)
    delivered = dispatch_notification_queue(limit=500)
    retained = retention_cleanup(dry_run=False)
    result = {"prepared": prepared, "delivered": delivered, "retention": retained}
    write_system_audit(
        "scheduled_maintenance",
        "system",
        f"Prepared {prepared['created']}; sent {delivered['sent']}; expired local notifications removed {retained['local_notifications']}",
    )
    return result


def scheduler_worker() -> None:
    interval = min(max(int(os.environ.get("KOMPLIANCE_SCHEDULER_INTERVAL_SECONDS", "3600")), 60), 86400)
    SCHEDULER_STATE["running"] = True
    try:
        while not SCHEDULER_STOP.wait(interval):
            try:
                run_scheduled_maintenance()
                SCHEDULER_STATE["last_run_at"] = utc_now()
                SCHEDULER_STATE["last_error"] = ""
            except Exception as error:
                SCHEDULER_STATE["last_error"] = str(error)[:300]
                write_system_audit("scheduled_maintenance_failed", "system", str(error)[:300])
    finally:
        SCHEDULER_STATE["running"] = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    initialize_database()
    scheduler_thread = None
    if SCHEDULER_STATE["enabled"]:
        SCHEDULER_STOP.clear()
        scheduler_thread = threading.Thread(target=scheduler_worker, name="kompliance-scheduler", daemon=True)
        scheduler_thread.start()
    server = ThreadingHTTPServer((args.host, args.port), KomplianceHandler)
    print(f"Kompliance Local running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        SCHEDULER_STOP.set()
        if scheduler_thread is not None:
            scheduler_thread.join(timeout=2)
        server.server_close()


if __name__ == "__main__":
    main()
