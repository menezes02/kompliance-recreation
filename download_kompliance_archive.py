#!/usr/bin/env python3
"""Read-only authenticated archive downloader for Kompliance.

Credentials must be supplied through KOMPLIANCE_EMAIL and
KOMPLIANCE_PASSWORD. The script performs GET requests after login and never
calls create, update, assignment, approval, or delete endpoints.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import http.cookiejar
import json
import mimetypes
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
from pathlib import Path, PurePosixPath
from typing import Any


BASE_URL = "https://kompliance.lgsafety.ie"
USER_AGENT = "KomplianceReadOnlyArchiver/1.0"

HSA_ENDPOINTS = {
    "ga2": "/ga2/form",
    "ga3": "/ga3/form",
    "ga3-scaffold": "/ga3scaffold/form",
    "af3": "/af3/form",
    "handover": "/handover/form",
    "ga2-manual": "/ga2_manual/form",
    "ga3-manual": "/ga3_manual/form",
}

OTHER_TABLES = {
    "ga1": "/ga1",
    "risk-assessment": "/risk_assessment",
    "shared-documents": "/document",
    "custom-forms": "/forms",
    "assets": "/appliances",
}

STATIC_FILES = {
    "logo": "/assets/images/logo.svg",
    "background": "/assets/images/background_image.svg",
    "sites-icon": "/assets/images/icons/sites_icon.svg",
    "workers-icon": "/assets/images/icons/workers_icon.svg",
    "subcontractors-icon": "/assets/images/icons/subcontractors_icon.svg",
    "forms-icon": "/assets/images/icons/forms_icon.svg",
    "completed-forms-icon": "/assets/images/icons/completed_forms_icon.svg",
    "icons-css": "/assets/css/icons.min.css",
    "bootstrap-css": "/assets/css/bootstrap.min.css",
    "app-css": "/assets/css/app.min.css",
    "custom-css": "/assets/css/custom.css",
    "toastr-css": "/assets/libs/toastr/toastr.min.css",
}

KNOWN_MIME_EXTENSIONS = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "text/csv": ".csv",
    "application/zip": ".zip",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.ms-excel": ".xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}

SAFE_EXISTING_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".csv",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".zip",
}


def extract_csrf(html: str) -> str:
    patterns = (
        r'name=["\']_token["\'][^>]*value=["\']([^"\']+)["\']',
        r'value=["\']([^"\']+)["\'][^>]*name=["\']_token["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1)
    raise RuntimeError("Login CSRF token was not found")


def extract_hrefs(fragment: Any) -> list[str]:
    if not isinstance(fragment, str):
        return []
    decoded = unescape(fragment)
    return re.findall(
        r'href\s*=\s*["\']([^"\']+)["\']',
        decoded,
        flags=re.IGNORECASE,
    )


def absolute_url(href: str) -> str:
    joined = urllib.parse.urljoin(BASE_URL + "/", href)
    parts = urllib.parse.urlsplit(joined)
    return urllib.parse.urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            urllib.parse.quote(parts.path, safe="/%:@"),
            urllib.parse.quote_plus(
                urllib.parse.unquote_plus(parts.query),
                safe="=&%:@/",
            ),
            parts.fragment,
        )
    )


def safe_identifier(value: Any) -> str:
    text = str(value or "unknown")
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-.")
    return cleaned or "unknown"


def id_from_url(url: str) -> str:
    numbers = re.findall(r"\d+", urllib.parse.urlparse(url).path)
    if not numbers:
        numbers = re.findall(r"\d+", urllib.parse.urlparse(url).query)
    return numbers[-1] if numbers else hashlib.sha256(url.encode()).hexdigest()[:12]


class KomplianceSession:
    def __init__(self, email: str, password: str) -> None:
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )
        self.email = email
        self.password = password
        self.cookie_header = ""

    def login(self) -> None:
        request = urllib.request.Request(
            BASE_URL + "/login",
            headers={"User-Agent": USER_AGENT},
        )
        with self.opener.open(request, timeout=30) as response:
            login_html = response.read().decode("utf-8", "replace")
        token = extract_csrf(login_html)
        body = urllib.parse.urlencode(
            {
                "_token": token,
                "email": self.email,
                "password": self.password,
            }
        ).encode()
        request = urllib.request.Request(
            BASE_URL + "/login",
            data=body,
            method="POST",
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        with self.opener.open(request, timeout=30) as response:
            response.read()
            final_url = response.geturl()
        if urllib.parse.urlparse(final_url).path == "/login":
            raise RuntimeError("Kompliance login did not succeed")
        self.cookie_header = "; ".join(
            f"{cookie.name}={cookie.value}" for cookie in self.cookie_jar
        )

    def get_text(self, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(1, 5):
            try:
                request = urllib.request.Request(
                    absolute_url(url),
                    headers={
                        "User-Agent": USER_AGENT,
                        "Cookie": self.cookie_header,
                    },
                )
                with urllib.request.urlopen(request, timeout=45) as response:
                    data = response.read()
                    final_url = response.geturl()
                    content_type = response.headers.get_content_type()
                break
            except Exception as error:  # noqa: BLE001 - retry transient network errors
                last_error = error
                if attempt == 4:
                    raise
                time.sleep(attempt * 1.5)
        else:  # pragma: no cover - loop always breaks or raises
            raise RuntimeError(f"Unable to read {url}: {last_error}")
        if urllib.parse.urlparse(final_url).path == "/login":
            raise RuntimeError("Session expired while reading a page")
        if content_type == "text/html":
            return data.decode("utf-8", "replace")
        return data.decode("utf-8", "replace")

    def get_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = absolute_url(path) + "?" + urllib.parse.urlencode(params)
        last_error: Exception | None = None
        for attempt in range(1, 5):
            try:
                request = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Cookie": self.cookie_header,
                        "X-Requested-With": "XMLHttpRequest",
                        "Accept": "application/json",
                    },
                )
                with urllib.request.urlopen(request, timeout=45) as response:
                    data = response.read()
                    final_url = response.geturl()
                break
            except Exception as error:  # noqa: BLE001 - retry transient network errors
                last_error = error
                if attempt == 4:
                    raise
                time.sleep(attempt * 1.5)
        else:  # pragma: no cover - loop always breaks or raises
            raise RuntimeError(f"Unable to read {url}: {last_error}")
        if urllib.parse.urlparse(final_url).path == "/login":
            raise RuntimeError("Session expired while reading a data table")
        return json.loads(data.decode("utf-8", "replace"))

    def post_json(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        body = urllib.parse.urlencode(params).encode()
        last_error: Exception | None = None
        for attempt in range(1, 5):
            try:
                request = urllib.request.Request(
                    absolute_url(path),
                    data=body,
                    method="POST",
                    headers={
                        "User-Agent": USER_AGENT,
                        "Cookie": self.cookie_header,
                        "X-Requested-With": "XMLHttpRequest",
                        "Accept": "application/json",
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                )
                with self.opener.open(request, timeout=45) as response:
                    data = response.read()
                    final_url = response.geturl()
                break
            except Exception as error:  # noqa: BLE001 - retry transient network errors
                last_error = error
                if attempt == 4:
                    raise
                time.sleep(attempt * 1.5)
        else:  # pragma: no cover - loop always breaks or raises
            raise RuntimeError(f"Unable to post to {path}: {last_error}")
        if urllib.parse.urlparse(final_url).path == "/login":
            raise RuntimeError("Session expired while reading a data table")
        return json.loads(data.decode("utf-8", "replace"))

    def fetch_table(self, path: str, page_size: int = 500) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        start = 0
        draw = 1
        total: int | None = None
        while total is None or start < total:
            payload = self.get_json(
                path,
                {
                    "draw": draw,
                    "start": start,
                    "length": page_size,
                },
            )
            page = payload.get("data") or []
            total = int(payload.get("recordsFiltered", payload.get("recordsTotal", 0)))
            rows.extend(page)
            if not page:
                break
            start += len(page)
            draw += 1
        return rows


def add_task(
    tasks: dict[str, dict[str, Any]],
    *,
    url: str,
    category: str,
    stem: str,
    extension: str | None = None,
    source_id: Any = None,
) -> None:
    url = absolute_url(url)
    if not url.startswith(BASE_URL + "/"):
        return
    tasks.setdefault(
        url,
        {
            "url": url,
            "category": safe_identifier(category),
            "stem": safe_identifier(stem),
            "extension": extension,
            "source_id": str(source_id) if source_id is not None else None,
        },
    )


def collect_archive_tasks(session: KomplianceSession) -> tuple[list[dict[str, Any]], dict[str, int]]:
    tasks: dict[str, dict[str, Any]] = {}
    counts: dict[str, int] = {}

    for category, endpoint in HSA_ENDPOINTS.items():
        rows = session.fetch_table(endpoint)
        counts[category] = len(rows)
        for row in rows:
            record_id = safe_identifier(row.get("id"))
            for href in extract_hrefs(row.get("action")):
                if "/pdf/download" in href:
                    add_task(
                        tasks,
                        url=href,
                        category=f"pdfs/{category}",
                        stem=f"{category}_{record_id}",
                        extension=".pdf",
                        source_id=record_id,
                    )
            for href in extract_hrefs(row.get("qr_code")):
                if "/upload/company_hsa_qr_code_url/" in href:
                    add_task(
                        tasks,
                        url=href,
                        category="qr/hsa",
                        stem=f"{category}-qr",
                        extension=".png",
                        source_id=category,
                    )

    shared_rows = session.fetch_table(OTHER_TABLES["shared-documents"])
    counts["shared-documents"] = len(shared_rows)
    for row in shared_rows:
        record_id = safe_identifier(row.get("id"))
        for href in extract_hrefs(row.get("action")):
            if "/upload/document/" in href:
                suffix = PurePosixPath(urllib.parse.urlparse(href).path).suffix.lower()
                add_task(
                    tasks,
                    url=href,
                    category="shared-documents",
                    stem=f"document_{record_id}",
                    extension=suffix if suffix in SAFE_EXISTING_EXTENSIONS else None,
                    source_id=record_id,
                )

    form_rows = session.fetch_table(OTHER_TABLES["custom-forms"])
    counts["custom-forms"] = len(form_rows)
    for row in form_rows:
        record_id = safe_identifier(row.get("id"))
        for href in extract_hrefs(row.get("qr_code")):
            if "/upload/qr-code/" in href:
                add_task(
                    tasks,
                    url=href,
                    category="qr/custom-forms",
                    stem=f"form_{record_id}",
                    extension=".png",
                    source_id=record_id,
                )

    asset_rows = session.fetch_table(OTHER_TABLES["assets"])
    counts["assets"] = len(asset_rows)
    for row in asset_rows:
        record_id = safe_identifier(row.get("id"))
        for href in extract_hrefs(row.get("qr_code")):
            if "/upload/appliance/" in href:
                qr_filename = re.search(
                    r"([0-9a-f]{8}-[0-9a-f-]{27}\.png)",
                    href,
                    re.IGNORECASE,
                )
                if qr_filename:
                    href = f"/upload/appliance/{qr_filename.group(1)}"
                add_task(
                    tasks,
                    url=href,
                    category="qr/assets",
                    stem=f"asset_{record_id}",
                    extension=".png",
                    source_id=record_id,
                )

    for category in ("ga1", "risk-assessment"):
        endpoint = OTHER_TABLES[category]
        rows = session.fetch_table(endpoint)
        counts[category] = len(rows)
        route_prefix = "/ga1/" if category == "ga1" else "/risk_assessment/"
        edit_suffix = "/edit"
        for row in rows:
            set_id = safe_identifier(row.get("id"))
            detail_url = None
            for href in extract_hrefs(row.get("action")):
                path = urllib.parse.urlparse(absolute_url(href)).path
                if path.startswith(route_prefix) and not path.endswith(edit_suffix):
                    detail_url = absolute_url(href)
                    break
            if not detail_url:
                continue
            detail_html = session.get_text(detail_url)
            if category == "ga1":
                token = extract_csrf(detail_html)
                start = 0
                draw = 1
                total: int | None = None
                while total is None or start < total:
                    payload = session.post_json(
                        "/ga1/documents",
                        {
                            "_token": token,
                            "draw": draw,
                            "start": start,
                            "length": 500,
                            "ga1_form_id": set_id,
                        },
                    )
                    documents = payload.get("data") or []
                    total = int(
                        payload.get("recordsFiltered", payload.get("recordsTotal", 0))
                    )
                    for document in documents:
                        document_id = safe_identifier(document.get("id"))
                        filename = str(document.get("document") or "")
                        suffix = PurePosixPath(filename).suffix.lower()
                        hrefs = [
                            href
                            for href in extract_hrefs(document.get("action"))
                            if "/ga1/download/" in href
                        ]
                        href = hrefs[0] if hrefs else f"/ga1/download/{document_id}"
                        add_task(
                            tasks,
                            url=href,
                            category=f"documents/{category}/{set_id}",
                            stem=f"document_{document_id}",
                            extension=(
                                suffix if suffix in SAFE_EXISTING_EXTENSIONS else None
                            ),
                            source_id=document_id,
                        )
                    if not documents:
                        break
                    start += len(documents)
                    draw += 1
                continue
            for href in extract_hrefs(detail_html):
                if (
                    (category == "ga1" and "/ga1/download/" in href)
                    or (
                        category == "risk-assessment"
                        and "/risk_assessment/download/" in href
                    )
                ):
                    document_id = id_from_url(href)
                    add_task(
                        tasks,
                        url=href,
                        category=f"documents/{category}/{set_id}",
                        stem=f"document_{document_id}",
                        extension=None,
                        source_id=document_id,
                    )

    counts["static-assets"] = len(STATIC_FILES)
    for name, href in STATIC_FILES.items():
        suffix = PurePosixPath(urllib.parse.urlparse(href).path).suffix.lower()
        add_task(
            tasks,
            url=href,
            category="static-assets",
            stem=name,
            extension=suffix or None,
            source_id=name,
        )

    return list(tasks.values()), counts


def extension_from_headers(
    url: str,
    headers: Any,
    explicit_extension: str | None,
) -> str:
    if explicit_extension:
        return explicit_extension

    url_suffix = PurePosixPath(urllib.parse.urlparse(url).path).suffix.lower()
    if url_suffix in SAFE_EXISTING_EXTENSIONS:
        return url_suffix

    disposition = headers.get("Content-Disposition", "")
    filename_match = re.search(
        r"filename\*?=(?:UTF-8''|[\"']?)([^\"';]+)",
        disposition,
        flags=re.IGNORECASE,
    )
    if filename_match:
        suffix = Path(urllib.parse.unquote(filename_match.group(1))).suffix.lower()
        if suffix in SAFE_EXISTING_EXTENSIONS:
            return suffix

    content_type = headers.get_content_type()
    if content_type in KNOWN_MIME_EXTENSIONS:
        return KNOWN_MIME_EXTENSIONS[content_type]
    guessed = mimetypes.guess_extension(content_type or "")
    return guessed or ".bin"


def download_one(
    task: dict[str, Any],
    *,
    output_root: Path,
    cookie_header: str,
    retries: int = 3,
) -> dict[str, Any]:
    category_dir = output_root / Path(task["category"])
    category_dir.mkdir(parents=True, exist_ok=True)

    explicit_extension = task.get("extension")
    if explicit_extension:
        expected_path = category_dir / (task["stem"] + explicit_extension)
        if expected_path.exists() and expected_path.stat().st_size > 0:
            return {
                **task,
                "status": "skipped",
                "path": str(expected_path.relative_to(output_root)),
                "size": expected_path.stat().st_size,
            }
    else:
        existing = list(category_dir.glob(task["stem"] + ".*"))
        existing = [path for path in existing if path.stat().st_size > 0]
        if existing:
            path = existing[0]
            return {
                **task,
                "status": "skipped",
                "path": str(path.relative_to(output_root)),
                "size": path.stat().st_size,
            }

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        temp_path: Path | None = None
        try:
            request = urllib.request.Request(
                task["url"],
                headers={
                    "User-Agent": USER_AGENT,
                    "Cookie": cookie_header,
                },
            )
            with urllib.request.urlopen(request, timeout=90) as response:
                final_url = response.geturl()
                if urllib.parse.urlparse(final_url).path == "/login":
                    raise RuntimeError("Session expired during download")
                extension = extension_from_headers(
                    task["url"],
                    response.headers,
                    explicit_extension,
                )
                output_path = category_dir / (task["stem"] + extension)
                temp_path = output_path.with_suffix(output_path.suffix + ".part")
                digest = hashlib.sha256()
                size = 0
                with temp_path.open("wb") as handle:
                    while True:
                        chunk = response.read(1024 * 256)
                        if not chunk:
                            break
                        handle.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                if size == 0:
                    raise RuntimeError("Downloaded file was empty")
                temp_path.replace(output_path)
                return {
                    **task,
                    "status": "downloaded",
                    "path": str(output_path.relative_to(output_root)),
                    "size": size,
                    "sha256": digest.hexdigest(),
                    "content_type": response.headers.get_content_type(),
                }
        except Exception as error:  # noqa: BLE001 - preserve failure in manifest
            last_error = error
            if temp_path and temp_path.exists():
                temp_path.unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(attempt * 1.5)
    return {
        **task,
        "status": "failed",
        "error": f"{type(last_error).__name__}: {last_error}",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent / "source-archive"),
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    email = os.environ.get("KOMPLIANCE_EMAIL")
    password = os.environ.get("KOMPLIANCE_PASSWORD")
    if not email or not password:
        print(
            "Set KOMPLIANCE_EMAIL and KOMPLIANCE_PASSWORD for this process.",
            file=sys.stderr,
        )
        return 2

    output_root = Path(args.output).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    session = KomplianceSession(email, password)
    session.login()
    print("Authenticated. Building read-only download inventory...", flush=True)
    tasks, source_counts = collect_archive_tasks(session)
    print(
        json.dumps(
            {
                "source_records": source_counts,
                "unique_downloads": len(tasks),
                "output": str(output_root),
            },
            indent=2,
        ),
        flush=True,
    )
    if args.dry_run:
        return 0

    manifest_path = output_root / "download-manifest.jsonl"
    manifest_lock = threading.Lock()
    completed = 0
    failures = 0
    started = time.time()

    def record(result: dict[str, Any]) -> None:
        nonlocal completed, failures
        with manifest_lock:
            with manifest_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(result, ensure_ascii=False) + "\n")
            completed += 1
            if result["status"] == "failed":
                failures += 1
            if completed == 1 or completed % 25 == 0 or completed == len(tasks):
                elapsed = max(time.time() - started, 0.001)
                print(
                    f"Progress {completed}/{len(tasks)} "
                    f"({completed / elapsed:.1f} files/s), failures={failures}",
                    flush=True,
                )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=max(1, min(args.workers, 8))
    ) as executor:
        futures = [
            executor.submit(
                download_one,
                task,
                output_root=output_root,
                cookie_header=session.cookie_header,
            )
            for task in tasks
        ]
        for future in concurrent.futures.as_completed(futures):
            record(future.result())

    summary = {
        "task_count": len(tasks),
        "completed": completed,
        "failures": failures,
        "elapsed_seconds": round(time.time() - started, 2),
        "manifest": str(manifest_path),
    }
    (output_root / "summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2), flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
