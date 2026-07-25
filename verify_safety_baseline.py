#!/usr/bin/env python3
"""Offline verification for the Kompliance read-only safety baseline."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expect_blocked(action, description: str, failures: list[str]) -> None:
    try:
        action()
    except RuntimeError:
        print(f"[PASS] {description}")
        return
    failures.append(description)
    print(f"[FAIL] {description}")


def check(condition: bool, description: str, failures: list[str]) -> None:
    if condition:
        print(f"[PASS] {description}")
    else:
        failures.append(description)
        print(f"[FAIL] {description}")


def main() -> int:
    failures: list[str] = []
    archiver = load_module("kompliance_archiver", ROOT / "download_kompliance_archive.py")
    server = load_module("kompliance_local_server", ROOT / "local-app" / "server.py")

    origin = archiver.BASE_URL
    check(
        archiver.validate_remote_request(origin + "/workers", "GET").endswith(
            "/workers"
        ),
        "same-origin GET requests are allowed",
        failures,
    )
    check(
        archiver.validate_remote_request(origin + "/login", "POST").endswith(
            "/login"
        ),
        "only the login POST is allowed for authentication",
        failures,
    )
    check(
        archiver.validate_remote_request(
            origin + "/ga1/documents", "POST"
        ).endswith("/ga1/documents"),
        "the documented read-only GA1 table POST is allowed",
        failures,
    )
    expect_blocked(
        lambda: archiver.validate_remote_request(origin + "/workers/1", "PUT"),
        "production PUT requests are blocked",
        failures,
    )
    expect_blocked(
        lambda: archiver.validate_remote_request(origin + "/workers", "POST"),
        "unapproved production POST requests are blocked",
        failures,
    )
    expect_blocked(
        lambda: archiver.validate_remote_request("https://example.com/file", "GET"),
        "cross-origin requests and redirects are blocked",
        failures,
    )

    protected_env = {
        "KOMPLIANCE_READ_ONLY_ACK",
        "KOMPLIANCE_EXPORT_AUTHORIZED",
        "KOMPLIANCE_DOWNLOAD_AUTHORIZED",
        "KOMPLIANCE_AUTHORIZED_BY",
        "KOMPLIANCE_AUTHORIZATION_REFERENCE",
    }
    saved_env = {key: os.environ.get(key) for key in protected_env}
    try:
        for key in protected_env:
            os.environ.pop(key, None)
        expect_blocked(
            lambda: archiver.require_operation_authorization("export"),
            "exports fail closed without an approval acknowledgement",
            failures,
        )
        expect_blocked(
            lambda: archiver.require_operation_authorization("download"),
            "downloads fail closed without an approval acknowledgement",
            failures,
        )
    finally:
        for key, value in saved_env.items():
            if value is not None:
                os.environ[key] = value

    check(
        server.is_protected_payload({"source": "production read-only export"}),
        "imported snapshot payloads are classified as protected",
        failures,
    )
    check(
        not server.is_protected_payload({"source": "local synthetic record"}),
        "local synthetic payloads remain editable",
        failures,
    )

    snapshot = json.loads(
        (ROOT / "production-data" / "records.json").read_text(encoding="utf-8")
    )
    snapshot_records = [
        record
        for records in snapshot.get("records", {}).values()
        for record in records
    ]
    check(
        bool(snapshot_records)
        and all(server.is_protected_payload(record) for record in snapshot_records),
        "every current snapshot record carries the immutable source marker",
        failures,
    )

    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    check(
        compose.count("read_only: true") >= 2,
        "application and gateway container filesystems are read-only",
        failures,
    )
    check(
        "./source-archive:/app/source-archive:ro" in compose,
        "the source archive is mounted read-only",
        failures,
    )
    check(
        compose.count("no-new-privileges:true") >= 2,
        "containers prevent privilege escalation",
        failures,
    )
    check(
        "USER 10001:10001" in dockerfile,
        "the application runs as a non-root user",
        failures,
    )

    tracked = subprocess.check_output(
        ["git", "ls-files"], cwd=ROOT, text=True, encoding="utf-8"
    ).splitlines()
    forbidden_names = {
        ".env",
        "deployment/htpasswd",
        "cookies.txt",
    }
    forbidden_suffixes = (".db", ".sqlite", ".sqlite3", ".log")
    unsafe_tracked = [
        path
        for path in tracked
        if path in forbidden_names or path.lower().endswith(forbidden_suffixes)
    ]
    check(
        not unsafe_tracked,
        "credentials, runtime databases, cookies, and logs are not tracked",
        failures,
    )

    if failures:
        print(f"\nSafety baseline failed: {len(failures)} check(s).")
        return 1
    print(f"\nSafety baseline passed. Snapshot records: {len(snapshot_records)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
