"""End-to-end tests for the tenant-isolated Universal Worker Foundation."""

from __future__ import annotations

import http.cookiejar
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "local-app" / "server.py"


class Client:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )

    def call(self, path, method="GET", body=None, csrf="", headers=None):
        request_headers = dict(headers or {})
        data = body
        if isinstance(body, dict):
            data = json.dumps(body).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        if csrf:
            request_headers["X-CSRF-Token"] = csrf
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers=request_headers,
            method=method,
        )
        try:
            with self.opener.open(request) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as error:
            result = (error.code, error.headers, error.read())
            error.close()
            return result

    def json(self, path, method="GET", body=None, csrf="", headers=None):
        status, response_headers, content = self.call(path, method, body, csrf, headers)
        payload = json.loads(content.decode("utf-8")) if content else {}
        return status, payload, response_headers


class UniversalWorkerEndToEndTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_directory = tempfile.TemporaryDirectory(prefix="kompliance-universal-")
        with socket.socket() as available:
            available.bind(("127.0.0.1", 0))
            cls.port = available.getsockname()[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        environment = os.environ.copy()
        environment.update(
            {
                "KOMPLIANCE_DATA_ROOT": cls.temp_directory.name,
                "KOMPLIANCE_APP_AUTH": "1",
                "KOMPLIANCE_WORKER_EMAIL_VERIFICATION": "0",
                "KOMPLIANCE_EMAIL_DELIVERY": "0",
            }
        )
        cls.process = subprocess.Popen(
            [sys.executable, str(SERVER), "--host", "127.0.0.1", "--port", str(cls.port)],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 20
        while time.time() < deadline:
            status, _, _ = Client(cls.base_url).call("/api/health")
            if status == 200:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("Test server did not start")

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.wait(timeout=10)
        cls.temp_directory.cleanup()

    def test_consent_import_documents_api_and_tenant_isolation(self):
        platform = Client(self.base_url)
        status, setup, _ = platform.json(
            "/api/auth/setup",
            "POST",
            {"name": "Platform Admin", "email": "platform@test.local", "password": "PlatformPass2026!"},
        )
        self.assertEqual(status, 201)
        status, tenant, _ = platform.json(
            "/api/companies",
            "POST",
            {"name": "Tenant Two", "admin_name": "Tenant Admin", "admin_email": "tenant@test.local", "admin_password": "TenantPass2026!"},
            setup["csrf_token"],
        )
        self.assertEqual(status, 201)

        worker = Client(self.base_url)
        status, registered, _ = worker.json(
            "/api/worker/register",
            "POST",
            {"name": "Aoife Worker", "email": "aoife@test.local", "password": "WorkerPass2026!", "trade": "Electrician"},
        )
        self.assertEqual((status, registered["authenticated"]), (201, True))
        worker_csrf = registered["csrf_token"]
        status, profile, _ = worker.json(
            "/api/worker/profile",
            "PUT",
            {"name": "Aoife Worker", "phone": "0870000000", "trade": "Electrician", "skills": ["LOTO"], "certifications": ["Electrical Level 6"], "training_records": ["Working at Height"], "inductions": ["Tenant Two Site"], "public_fields": ["name", "trade"]},
            worker_csrf,
        )
        self.assertEqual(profile["profile"]["public_fields"], ["name", "trade"])
        status, document, _ = worker.json(
            "/api/worker/documents",
            "POST",
            b"controlled worker document",
            worker_csrf,
            {"Content-Type": "application/pdf", "X-Document-Category": "Certification", "X-Document-Title": "Electrical Certificate", "X-File-Name": "certificate.pdf"},
        )
        self.assertEqual(status, 201)
        status, share, _ = worker.json(
            "/api/worker/shares",
            "POST",
            {"company_id": tenant["id"], "visible_fields": ["name", "email", "trade", "certifications", "training_records", "inductions", "documents"]},
            worker_csrf,
        )
        self.assertEqual(status, 201)

        tenant_client = Client(self.base_url)
        status, login, _ = tenant_client.json(
            "/api/auth/login", "POST", {"email": "tenant@test.local", "password": "TenantPass2026!"}
        )
        self.assertEqual(status, 200)
        tenant_csrf = login["csrf_token"]
        status, shared, _ = tenant_client.json("/api/company/shared-workers")
        self.assertEqual(len(shared["data"]), 1)
        self.assertEqual(shared["data"][0]["profile"]["email"], "aoife@test.local")
        self.assertNotIn("phone", shared["data"][0]["profile"])
        status, _, content = tenant_client.call(f"/api/company/worker-documents/{document['id']}/file")
        self.assertEqual((status, content), (200, b"controlled worker document"))
        status, review, _ = tenant_client.json(
            f"/api/company/worker-documents/{document['id']}/review", "POST", {"status": "approved"}, tenant_csrf
        )
        self.assertEqual(review["status"], "approved")
        access_id = shared["data"][0]["access_id"]
        status, imported, _ = tenant_client.json(
            f"/api/company/shared-workers/{access_id}/import", "POST", {}, tenant_csrf
        )
        self.assertEqual(status, 200)
        status, tenant_workers, _ = tenant_client.json("/api/resources/workers?limit=5000")
        self.assertEqual(tenant_workers["total"], 1)
        self.assertEqual(tenant_workers["data"][0]["universal_worker_id"], shared["data"][0]["worker_id"])
        self.assertEqual(tenant_client.call("/api/archive")[0], 403)

        status, token, _ = tenant_client.json(
            "/api/company/api-tokens", "POST", {"name": "E2E"}, tenant_csrf
        )
        self.assertEqual(status, 201)
        api = Client(self.base_url)
        auth_header = {"Authorization": "Bearer " + token["token"]}
        status, api_workers, _ = api.json("/api/v1/shared-workers", headers=auth_header)
        self.assertEqual((status, len(api_workers["data"])), (200, 1))
        worker_id = shared["data"][0]["worker_id"]
        self.assertEqual(api.json(f"/api/v1/workers/{worker_id}", headers=auth_header)[0], 200)
        self.assertEqual(api.json(f"/api/v1/workers/{worker_id}/certifications", headers=auth_header)[1]["data"], ["Electrical Level 6"])
        self.assertEqual(api.json(f"/api/v1/workers/{worker_id}/training-records", headers=auth_header)[1]["data"], ["Working at Height"])
        self.assertEqual(api.json(f"/api/v1/workers/{worker_id}/inductions", headers=auth_header)[1]["data"], ["Tenant Two Site"])
        self.assertEqual(api.call(f"/api/v1/workers/{worker_id}/documents/{document['id']}/file", headers=auth_header)[2], b"controlled worker document")
        self.assertEqual(
            tenant_client.json(f"/api/company/api-tokens/{token['id']}/revoke", "POST", {}, tenant_csrf)[0],
            200,
        )
        self.assertEqual(api.call("/api/v1/shared-workers", headers=auth_header)[0], 401)

        # Supervisor workflow remains tenant-scoped from worker request to final approval.
        status, users, _ = tenant_client.json("/api/users")
        self.assertEqual(status, 200)
        tenant_user_id = users["data"][0]["id"]
        status, contact, _ = tenant_client.json(
            "/api/company/departments", "POST",
            {"department": "Safety", "name": "Safety Lead", "email": "tenant@test.local", "user_id": tenant_user_id},
            tenant_csrf,
        )
        self.assertEqual(status, 201)
        status, request, _ = worker.json(
            "/api/worker/requests", "POST",
            {"company_id": tenant["id"], "department": "Safety", "request_type": "Additional Information", "subject": "Harness evidence", "message": "Please confirm which certificate is required."},
            worker_csrf,
        )
        self.assertEqual(status, 201)
        status, company_requests, _ = tenant_client.json("/api/company/requests")
        self.assertEqual(company_requests["data"][0]["assigned_contact_id"], contact["id"])
        self.assertEqual(company_requests["data"][0]["worker_name"], "Aoife Worker")
        request_id = request["id"]
        status, changed, _ = tenant_client.json(
            f"/api/company/requests/{request_id}/status", "POST",
            {"status": "awaiting_information", "note": "Upload the inspection record."}, tenant_csrf,
        )
        self.assertEqual(changed["status"], "awaiting_information")
        status, worker_requests, _ = worker.json("/api/worker/requests")
        self.assertEqual(worker_requests["data"][0]["events"][-1]["to_status"], "awaiting_information")

        status, company_conversations, _ = tenant_client.json("/api/company/conversations")
        conversation_id = company_conversations["data"][0]["id"]
        self.assertEqual(tenant_client.json(
            f"/api/company/conversations/{conversation_id}/messages", "POST",
            {"message": "The GA2 inspection certificate is required."}, tenant_csrf,
        )[0], 201)
        self.assertEqual(worker.json(
            f"/api/worker/conversations/{conversation_id}/messages", "POST",
            {"message": "Understood, I will provide it."}, worker_csrf,
        )[0], 201)
        status, conversation_after, _ = tenant_client.json("/api/company/conversations")
        self.assertEqual(conversation_after["data"][0]["messages"][-1]["sender_name"], "Aoife Worker")

        status, induction, _ = tenant_client.json(
            "/api/company/induction-reviews", "POST",
            {"worker_id": worker_id, "induction_name": "Oranmore Site Induction", "site": "Oranmore"}, tenant_csrf,
        )
        self.assertEqual(status, 201)
        status, decision, _ = tenant_client.json(
            f"/api/company/induction-reviews/{induction['id']}/status", "POST",
            {"status": "approved", "comments": "Identity and training verified."}, tenant_csrf,
        )
        self.assertEqual(decision["status"], "approved")
        status, worker_inductions, _ = worker.json("/api/worker/induction-reviews")
        self.assertEqual(worker_inductions["data"][0]["status"], "approved")
        self.assertEqual([event["to_status"] for event in worker_inductions["data"][0]["events"]], ["pending", "approved"])

        status, worker_notifications, _ = worker.json("/api/worker/notifications")
        self.assertGreater(worker_notifications["unread"], 0)
        self.assertEqual(worker.json(
            f"/api/worker/notifications/{worker_notifications['data'][0]['id']}/read", "POST", {}, worker_csrf,
        )[0], 200)
        status, company_notifications, _ = tenant_client.json("/api/company/notifications")
        self.assertGreater(company_notifications["unread"], 0)
        self.assertEqual(tenant_client.json(
            f"/api/company/notifications/{company_notifications['data'][0]['id']}/read", "POST", {}, tenant_csrf,
        )[0], 200)
        self.assertEqual(worker.json(
            "/api/worker/preferences", "PUT",
            {"in_app": True, "email": True, "sms": False, "push": False, "preferred_language": "pt"}, worker_csrf,
        )[1]["preferred_language"], "pt")
        status, worker_preferences, _ = worker.json("/api/worker/preferences")
        self.assertFalse(worker_preferences["channels"]["sms"]["available"])
        self.assertEqual(tenant_client.json(
            "/api/company/preferences", "PUT",
            {"in_app": True, "email": False, "sms": False, "push": False, "preferred_language": "en"}, tenant_csrf,
        )[0], 200)

        # A different tenant cannot read or mutate the workflow by guessing an ID.
        self.assertEqual(platform.json("/api/company/requests")[1]["data"], [])
        self.assertEqual(platform.call(
            f"/api/company/requests/{request_id}/status", "POST",
            json.dumps({"status": "closed"}).encode("utf-8"), setup["csrf_token"], {"Content-Type": "application/json"},
        )[0], 404)

        status, root_shared, _ = platform.json("/api/company/shared-workers")
        self.assertEqual(root_shared["data"], [])
        status, shares, _ = worker.json("/api/worker/shares")
        share_id = shares["data"][0]["id"]
        self.assertEqual(worker.json(f"/api/worker/shares/{share_id}/revoke", "POST", {}, worker_csrf)[0], 200)
        self.assertEqual(tenant_client.json("/api/company/shared-workers")[1]["data"], [])
        self.assertEqual(Client(self.base_url).call(share["share_url"].removeprefix(self.base_url))[0], 404)

        database = sqlite3.connect(Path(self.temp_directory.name) / "kompliance.db")
        try:
            protected = database.execute(
                "SELECT COUNT(*) FROM records WHERE payload LIKE '%production read-only export%'"
            ).fetchone()[0]
        finally:
            database.close()
        self.assertEqual(protected, 3597)


if __name__ == "__main__":
    unittest.main()
