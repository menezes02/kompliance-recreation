#!/usr/bin/env python3
"""Read-only export of production Kompliance table data.

The exporter authenticates, then performs GET-only DataTables requests. It
does not call create, update, assignment, approval, rejection, or delete
endpoints. Credentials are supplied only through environment variables.
"""

from __future__ import annotations

import hashlib
import html
import importlib.util
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = ROOT / "production-data"
OUTPUT_PATH = OUTPUT_ROOT / "records.json"
ARCHIVER_PATH = ROOT / "download_kompliance_archive.py"

TABLES = {
    "sites": "/sites",
    "roles": "/workers-roles",
    "workers": "/workers",
    "subcontractors": "/subcontractor",
    "training": "/training",
    "forms": "/forms",
    "distributions": "/form/distribution",
    "assets": "/appliances",
    "documents": "/document",
    "ga1": "/ga1",
    "risk_assessment": "/risk_assessment",
    "inductions": "/inductions",
}

HSA_TABLES = {
    "ga2": ("/ga2/form", "ga2"),
    "ga3": ("/ga3/form", "ga3"),
    "ga3_scaffold": ("/ga3scaffold/form", "ga3-scaffold"),
    "af3": ("/af3/form", "af3"),
    "handover": ("/handover/form", "handover"),
    "ga2_manual": ("/ga2_manual/form", "ga2-manual"),
    "ga3_manual": ("/ga3_manual/form", "ga3-manual"),
}


def load_archiver_module():
    spec = importlib.util.spec_from_file_location("kompliance_archiver", ARCHIVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load read-only Kompliance session")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return ", ".join(filter(None, (clean_text(item) for item in value)))
    if isinstance(value, dict):
        for key in (
            "name",
            "site_name",
            "company_name",
            "form_name",
            "title",
            "email",
        ):
            if value.get(key):
                return clean_text(value[key])
        return ", ".join(
            filter(None, (clean_text(item) for item in value.values()))
        )
    text = html.unescape(str(value))
    text = re.sub(r"<br\s*/?>", ", ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,")
    return text


def source_times(row: dict[str, Any]) -> tuple[str, str]:
    created = clean_text(row.get("created_at")) or datetime.now(UTC).isoformat()
    updated = clean_text(row.get("updated_at")) or created
    return created, updated


def load_examples() -> tuple[dict[str, dict], dict[str, dict], dict]:
    forms = json.loads((ROOT / "examples" / "custom-forms.json").read_text("utf-8"))
    induction_catalog = json.loads(
        (ROOT / "examples" / "inductions.json").read_text("utf-8")
    )
    forms_by_name = {item["name"].casefold(): item for item in forms}
    inductions_by_title = {
        item["title"].casefold(): item
        for item in induction_catalog.get("inductions", [])
    }
    return forms_by_name, inductions_by_title, induction_catalog


def induction_pages(example: dict, catalog: dict) -> dict:
    page_map: dict[int, list[dict[str, Any]]] = {}
    for page in catalog.get("shared_content_pages", []):
        blocks = page.get("blocks", [page])
        page_map[page["index"]] = [
            {
                "type": "text",
                "text": block.get("heading", ""),
                "mapped_character_count": block.get("character_count", 0),
                "embedded_image_count": block.get("embedded_image_count", 0),
            }
            for block in blocks
        ]
    for page in example.get("site_pages", []):
        page_map[page["index"]] = [
            {
                "type": "text",
                "text": page.get("heading", ""),
                "mapped_character_count": page.get("character_count", 0),
                "embedded_image_count": page.get("embedded_image_count", 0),
            }
        ]
    questions = catalog.get("shared_questions", [])
    if example.get("question_layout", "").startswith("three"):
        page_map[13] = [
            {
                **question,
                "type": "question",
                "question_type": question.get("type", "single_choice"),
            }
            for question in questions
        ]
    else:
        for index, question in enumerate(questions):
            page_map[13 + index] = [
                {
                    **question,
                    "type": "question",
                    "question_type": question.get("type", "single_choice"),
                }
            ]
    return {
        "pages": [
            {"index": index, "blocks": blocks}
            for index, blocks in sorted(page_map.items())
        ]
    }


def mapped_record(
    resource: str,
    row: dict[str, Any],
    *,
    forms_by_name: dict[str, dict],
    inductions_by_title: dict[str, dict],
    induction_catalog: dict,
) -> dict[str, Any]:
    source_id = row.get("id")
    common = {"source_id": source_id, "source": "production read-only export"}

    if resource == "sites":
        return {
            **common,
            "name": clean_text(row.get("site_name")),
            "address": clean_text(row.get("address")),
            "remarks": clean_text(row.get("additional_remarks")),
        }
    if resource == "roles":
        return {**common, "name": clean_text(row.get("name"))}
    if resource == "workers":
        return {
            **common,
            "worker_id": clean_text(row.get("worker_id")),
            "name": clean_text(row.get("name")),
            "email": clean_text(row.get("email")),
            "type": clean_text(row.get("type")),
            "status": clean_text(row.get("status")),
            "phone": clean_text(row.get("phone_number")),
            "sites": clean_text(row.get("assigned_site")),
            "roles": clean_text(row.get("assigned_role")),
            "subcontractor": clean_text(row.get("subcontractor_name")),
            "temporary_valid_from": clean_text(row.get("valid_from")),
            "temporary_expiry": clean_text(row.get("expiry_date")),
            "safe_pass_expiry": clean_text(row.get("safe_expiry_date")),
            "induction_status": clean_text(row.get("induction_status")),
            "training_status": "",
        }
    if resource == "subcontractors":
        return {
            **common,
            "company_name": clean_text(row.get("company_name")),
            "name": clean_text(row.get("name")),
            "email": clean_text(row.get("email")),
            "phone": clean_text(row.get("phone_number")),
            "expiry_date": clean_text(row.get("expiry_date")),
        }
    if resource == "training":
        return {
            **common,
            "question": clean_text(row.get("question")),
            "expiry_date": clean_text(row.get("expiry_date")),
        }
    if resource == "forms":
        name = clean_text(row.get("form_name"))
        example = forms_by_name.get(name.casefold(), {})
        return {
            **common,
            "name": name,
            "assigned_sites": clean_text(row.get("assigned_site")),
            "assigned_roles": clean_text(row.get("assigned_role")),
            "status": "Active",
            "definition": {"sections": example.get("sections", [])},
            "qr_archive_path": f"qr-custom-forms/form_{source_id}.png",
        }
    if resource == "distributions":
        return {
            **common,
            "worker": clean_text(row.get("worker_name") or row.get("user")),
            "sites": clean_text(row.get("assigned_site")),
            "form": clean_text(row.get("assigned_form")),
            "assigned_date": clean_text(row.get("assigned_date")),
            "submitted_date": clean_text(row.get("submitted_date")),
            "score": clean_text(row.get("score")),
            "status": clean_text(row.get("status")),
        }
    if resource == "assets":
        return {
            **common,
            "asset_id": clean_text(row.get("appliance_id")),
            "name": clean_text(row.get("name")),
            "subcontractor": clean_text(row.get("subcontractor_name")),
            "company": clean_text(row.get("company_name")),
            "qr_archive_path": f"qr-assets/asset_{source_id}.png",
        }
    if resource == "documents":
        return {
            **common,
            "title": clean_text(row.get("title")),
            "file_name": clean_text(row.get("name")),
            "type": clean_text(row.get("type")),
            "subcontractor": clean_text(row.get("subcontractor_name")),
            "company": clean_text(row.get("company_name")),
            "archive_path": f"shared-documents/document_{source_id}.pdf",
        }
    if resource in {"ga1", "risk_assessment"}:
        return {
            **common,
            "title": clean_text(row.get("title")),
            "company": clean_text(row.get("company_name") or row.get("company")),
            "subcontractor": clean_text(row.get("company_subcontractor")),
            "site": clean_text(row.get("company_site")),
            "expiry_date": clean_text(row.get("expiry_date")),
            "expiry_status": clean_text(row.get("expiry_status")),
        }
    if resource == "inductions":
        title = clean_text(row.get("title"))
        example = inductions_by_title.get(title.casefold(), {})
        return {
            **common,
            "title": title,
            "site": clean_text(row.get("site_name") or row.get("site")),
            "submissions": row.get("submissions_count", 0),
            "status": clean_text(row.get("status_label") or row.get("status")),
            "pages": induction_pages(example, induction_catalog),
        }
    raise KeyError(resource)


def mapped_hsa_record(
    resource: str, archive_folder: str, row: dict[str, Any]
) -> dict[str, Any]:
    source_id = row.get("id")
    details = {}
    for key in (
        "location_description_scaffold",
        "observations",
        "location",
        "reference",
        "copies_to",
        "erected_by",
        "owner_name",
    ):
        value = clean_text(row.get(key))
        if value:
            details[key] = value
    return {
        "source_id": source_id,
        "source": "production read-only export",
        "subcontractor": clean_text(row.get("subcontractor_name")),
        "site": clean_text(row.get("site_name")),
        "worker": clean_text(row.get("worker_name")),
        "worker_email": clean_text(row.get("worker_email")),
        "submitted_date": clean_text(row.get("submitted_date")),
        "company": clean_text(row.get("company_name")),
        "archive_path": (
            f"pdfs-{archive_folder}/{archive_folder}_{source_id}.pdf"
        ),
        "details": details,
    }


def main() -> None:
    email = os.environ.get("KOMPLIANCE_EMAIL")
    password = os.environ.get("KOMPLIANCE_PASSWORD")
    if not email or not password:
        raise RuntimeError(
            "KOMPLIANCE_EMAIL and KOMPLIANCE_PASSWORD are required"
        )

    module = load_archiver_module()
    authorization = module.require_operation_authorization("export")
    session = module.KomplianceSession(email, password)
    session.login()
    print(
        "Authenticated for an approved read-only export "
        f"({authorization['authorization_reference']})."
    )

    forms_by_name, inductions_by_title, induction_catalog = load_examples()
    records: dict[str, list[dict[str, Any]]] = {}
    source_timestamps: dict[str, list[dict[str, str]]] = {}

    for resource, endpoint in TABLES.items():
        rows = session.fetch_table(endpoint)
        records[resource] = [
            mapped_record(
                resource,
                row,
                forms_by_name=forms_by_name,
                inductions_by_title=inductions_by_title,
                induction_catalog=induction_catalog,
            )
            for row in rows
        ]
        source_timestamps[resource] = [
            {"created_at": source_times(row)[0], "updated_at": source_times(row)[1]}
            for row in rows
        ]
        print(f"{resource}: {len(rows)}")

    for resource, (endpoint, archive_folder) in HSA_TABLES.items():
        rows = session.fetch_table(endpoint)
        records[resource] = [
            mapped_hsa_record(resource, archive_folder, row) for row in rows
        ]
        source_timestamps[resource] = [
            {"created_at": source_times(row)[0], "updated_at": source_times(row)[1]}
            for row in rows
        ]
        print(f"{resource}: {len(rows)}")

    exported_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    content = {
        "source": "https://kompliance.lgsafety.ie",
        "mode": "authenticated read-only export",
        "exported_at": exported_at,
        "counts": {resource: len(items) for resource, items in records.items()},
        "records": records,
        "timestamps": source_timestamps,
    }
    canonical = json.dumps(content, ensure_ascii=False, sort_keys=True).encode("utf-8")
    content["content_sha256"] = hashlib.sha256(canonical).hexdigest()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(content, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
