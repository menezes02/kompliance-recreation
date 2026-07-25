from __future__ import annotations

import base64
import json
import os
import sys
import unittest
from email import policy
from email.parser import BytesParser
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs


sys.path.insert(0, str(Path(__file__).resolve().parent))
import server  # noqa: E402


OAUTH_ENV = {
    "KOMPLIANCE_EMAIL_DELIVERY": "1",
    "KOMPLIANCE_EMAIL_PROVIDER": "gmail_oauth",
    "KOMPLIANCE_BASE_URL": "https://kompliance.example.test",
    "KOMPLIANCE_SMTP_FROM": "sender@example.test",
    "KOMPLIANCE_GMAIL_CLIENT_ID": "client-id.apps.googleusercontent.com",
    "KOMPLIANCE_GMAIL_CLIENT_SECRET": "CLIENT_SECRET_DO_NOT_EXPOSE",
    "KOMPLIANCE_GMAIL_REFRESH_TOKEN": "REFRESH_TOKEN_DO_NOT_EXPOSE",
}


class FakeResponse:
    def __init__(self, payload: dict, status: int = 200):
        self.payload = json.dumps(payload).encode()
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


class GmailOAuthTests(unittest.TestCase):
    def setUp(self):
        server.GMAIL_OAUTH_CACHE.update(access_token="", expires_at=0.0)

    def test_configuration_fails_closed_when_oauth_secret_is_missing(self):
        env = dict(OAUTH_ENV)
        env["KOMPLIANCE_GMAIL_REFRESH_TOKEN"] = ""
        with patch.dict(os.environ, env, clear=True):
            configuration = server.public_email_configuration()
        self.assertEqual(configuration["provider"], "gmail_oauth")
        self.assertFalse(configuration["oauth_configured"])
        self.assertFalse(configuration["configured"])

    def test_refresh_grant_and_message_send_use_gmail_api(self):
        requests = []

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            if request.full_url == server.GMAIL_TOKEN_ENDPOINT:
                return FakeResponse({"access_token": "SHORT_LIVED_ACCESS_TOKEN", "expires_in": 3600})
            return FakeResponse({"id": "gmail-message-id"})

        notification = {
            "recipient": "recipient@example.test",
            "subject": "Controlled OAuth test",
            "message": "This is a controlled test message.",
        }
        with patch.dict(os.environ, OAUTH_ENV, clear=True), patch.object(server, "urlopen", side_effect=fake_urlopen):
            server.send_notification_email(notification)

        self.assertEqual([request.full_url for request, _ in requests], [server.GMAIL_TOKEN_ENDPOINT, server.GMAIL_SEND_ENDPOINT])
        token_form = parse_qs(requests[0][0].data.decode())
        self.assertEqual(token_form["grant_type"], ["refresh_token"])
        self.assertEqual(token_form["refresh_token"], [OAUTH_ENV["KOMPLIANCE_GMAIL_REFRESH_TOKEN"]])
        self.assertEqual(requests[1][0].get_header("Authorization"), "Bearer SHORT_LIVED_ACCESS_TOKEN")
        raw = json.loads(requests[1][0].data)["raw"]
        decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        message = BytesParser(policy=policy.default).parsebytes(decoded)
        self.assertEqual(message["From"], OAUTH_ENV["KOMPLIANCE_SMTP_FROM"])
        self.assertEqual(message["To"], notification["recipient"])
        self.assertEqual(message["Subject"], notification["subject"])
        self.assertIn(notification["message"], message.get_content())

    def test_access_token_is_cached_until_close_to_expiry(self):
        calls = []

        def fake_urlopen(request, timeout):
            calls.append(request.full_url)
            return FakeResponse({"access_token": "cached-access-token", "expires_in": 3600})

        with patch.dict(os.environ, OAUTH_ENV, clear=True), patch.object(server, "urlopen", side_effect=fake_urlopen):
            self.assertEqual(server.gmail_oauth_access_token(), "cached-access-token")
            self.assertEqual(server.gmail_oauth_access_token(), "cached-access-token")
        self.assertEqual(calls, [server.GMAIL_TOKEN_ENDPOINT])

    def test_provider_errors_do_not_include_long_lived_secrets(self):
        failure = HTTPError(server.GMAIL_TOKEN_ENDPOINT, 400, "Bad Request", None, None)
        with patch.dict(os.environ, OAUTH_ENV, clear=True), patch.object(server, "urlopen", side_effect=failure):
            with self.assertRaises(RuntimeError) as caught:
                server.gmail_oauth_access_token()
        error = str(caught.exception)
        self.assertIn("HTTP 400", error)
        self.assertNotIn(OAUTH_ENV["KOMPLIANCE_GMAIL_CLIENT_SECRET"], error)
        self.assertNotIn(OAUTH_ENV["KOMPLIANCE_GMAIL_REFRESH_TOKEN"], error)


if __name__ == "__main__":
    unittest.main()
