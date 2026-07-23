#!/usr/bin/env python3
"""Verify the seven-language catalogue, preference API and source-data boundary."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EXPECTED = ("en-IE", "pl-PL", "ro-RO", "pt-BR", "uk-UA", "ru-RU", "es-ES")


def load_server():
    path = ROOT / "local-app" / "server.py"
    spec = importlib.util.spec_from_file_location("kompliance_localisation_server", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load local server")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request_json(url: str, method: str = "GET", payload: dict | None = None):
    content = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url, data=content, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def protected_count(server_module) -> int:
    with server_module.connect_database() as connection:
        rows = connection.execute("SELECT payload FROM records").fetchall()
    return sum(
        1 for row in rows if server_module.is_protected_payload(json.loads(row["payload"]))
    )


def check_static_catalog() -> list[str]:
    failures = []
    catalog_source = (ROOT / "local-app" / "static" / "i18n-catalog.js").read_text("utf-8")
    prefix = "window.KomplianceTranslationCatalog = Object.freeze("
    if not catalog_source.startswith("/*") or prefix not in catalog_source:
        return ["Static catalogue wrapper is missing"]
    catalog_json = catalog_source.split(prefix, 1)[1].rsplit(");", 1)[0]
    catalog = json.loads(catalog_json)
    if tuple(catalog) != EXPECTED[1:]:
        failures.append(f"Unexpected translated locales: {tuple(catalog)}")
    sizes = {locale: len(dictionary) for locale, dictionary in catalog.items()}
    if len(set(sizes.values())) != 1 or min(sizes.values(), default=0) < 1000:
        failures.append(f"Catalogue coverage is incomplete: {sizes}")
    required = {
        "Operations overview", "Review & acceptance", "Worker passport",
        "Notification preferences", "Submit for review", "Download PDF",
    }
    for locale, dictionary in catalog.items():
        missing = sorted(key for key in required if not dictionary.get(key))
        unchanged = sorted(key for key in required if dictionary.get(key) == key)
        if missing or unchanged:
            failures.append(f"{locale}: missing={missing}; unchanged={unchanged}")

    html = "\n".join(
        (ROOT / "local-app" / "static" / name).read_text("utf-8")
        for name in ("index.html", "worker.html")
    )
    for locale in EXPECTED:
        if f'value="{locale}"' not in html:
            failures.append(f"Selector is missing {locale}")
    if any("\U0001f1e6" <= character <= "\U0001f1ff" for character in html):
        failures.append("Language selectors must not contain flags")
    return failures


def main() -> int:
    failures = check_static_catalog()
    server_module = load_server()
    server_module.AUTH_ENABLED = False
    if tuple(sorted(server_module.SUPPORTED_LANGUAGES)) != tuple(sorted(EXPECTED)):
        failures.append("Backend supported-language set does not match the UI")

    with tempfile.TemporaryDirectory(prefix="kompliance-i18n-test-", ignore_cleanup_errors=True) as temp:
        server_module.DATA_ROOT = Path(temp)
        server_module.DATABASE_PATH = Path(temp) / "kompliance.db"
        server_module.initialize_database()
        before = protected_count(server_module)
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), server_module.KomplianceHandler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{httpd.server_port}"
        try:
            initial_code, initial = request_json(base + "/api/company/preferences")
            if initial_code != 200 or initial["preferences"]["preferred_language"] != "en-IE":
                failures.append(f"Unexpected default preference: {initial_code} {initial}")
            for locale in EXPECTED:
                code, body = request_json(
                    base + "/api/company/preferences",
                    "PUT",
                    {
                        "in_app": True, "email": False, "sms": False, "push": False,
                        "preferred_language": locale,
                    },
                )
                if code != 200 or body.get("preferred_language") != locale:
                    failures.append(f"Preference round trip failed for {locale}: {code} {body}")
            alias_code, alias = request_json(
                base + "/api/company/preferences", "PUT", {"preferred_language": "pt"}
            )
            if alias_code != 200 or alias.get("preferred_language") != "pt-BR":
                failures.append(f"Legacy Portuguese alias was not upgraded: {alias_code} {alias}")
            invalid_code, _ = request_json(
                base + "/api/company/preferences", "PUT", {"preferred_language": "xx"}
            )
            if invalid_code != 400:
                failures.append(f"Unsupported locale should return 400, received {invalid_code}")
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=2)
        after = protected_count(server_module)
        if before != after:
            failures.append(f"Protected snapshot changed during preference tests: {before} -> {after}")

    if failures:
        for failure in failures:
            print(f"[FAIL] {failure}")
        return 1
    print("[PASS] Seven locale codes are accepted and persisted")
    print("[PASS] Static catalogue coverage is complete and selectors contain no flags")
    print(f"[PASS] Protected snapshot remained unchanged ({before:,} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
