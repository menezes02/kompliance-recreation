import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import gmail_oauth_setup


class GmailOAuthSetupTests(unittest.TestCase):
    def test_resumable_completion_writes_environment_and_clears_one_time_values(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            client_file = directory / "client.json"
            session_file = directory / "session.json"
            callback_file = directory / "callback.url"
            output_file = directory / "gmail.env"
            client_file.write_text(
                json.dumps(
                    {
                        "installed": {
                            "client_id": "client-id",
                            "client_secret": "client-secret",
                        }
                    }
                ),
                encoding="utf-8",
            )
            session_file.write_text(
                json.dumps(
                    {
                        "state": "expected-state",
                        "verifier": "saved-verifier",
                        "redirect_uri": "http://127.0.0.1:45009/",
                    }
                ),
                encoding="utf-8",
            )
            callback_file.write_text(
                "http://127.0.0.1:45009/?state=expected-state&code=one-time-code",
                encoding="utf-8",
            )
            arguments = [
                "gmail_oauth_setup.py",
                str(client_file),
                "--sender",
                "kompliancesafety@gmail.com",
                "--output",
                str(output_file),
                "--session-file",
                str(session_file),
                "--complete-url-file",
                str(callback_file),
            ]

            with patch.object(sys, "argv", arguments), patch.object(
                gmail_oauth_setup,
                "exchange_code",
                return_value={"refresh_token": "refresh-token"},
            ) as exchange:
                self.assertEqual(gmail_oauth_setup.main(), 0)

            exchange.assert_called_once_with(
                "client-id",
                "client-secret",
                "one-time-code",
                "saved-verifier",
                "http://127.0.0.1:45009/",
            )
            environment = output_file.read_text(encoding="utf-8")
            self.assertIn("KOMPLIANCE_EMAIL_PROVIDER=gmail_oauth", environment)
            self.assertIn("KOMPLIANCE_GMAIL_REFRESH_TOKEN=refresh-token", environment)
            self.assertEqual(json.loads(session_file.read_text(encoding="utf-8")), {"completed": True})
            self.assertEqual(json.loads(callback_file.read_text(encoding="utf-8")), {"completed": True})


if __name__ == "__main__":
    unittest.main()
