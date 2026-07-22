#!/usr/bin/env python3
"""One-time local OAuth consent helper for Kompliance Gmail delivery.

This script requests only gmail.send and never writes credentials unless an
explicit --output path is supplied. The resulting file must remain untracked.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import secrets
import threading
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path


AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    result: dict[str, str] = {}
    expected_state = ""

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        state = params.get("state", [""])[0]
        if state != self.expected_state:
            self.result = {"error": "OAuth state validation failed"}
            status = 400
            message = "Authorization could not be validated. Return to the terminal."
        elif params.get("error"):
            self.result = {"error": params["error"][0]}
            status = 400
            message = "Authorization was not granted. Return to the terminal."
        else:
            self.result = {"code": params.get("code", [""])[0]}
            status = 200
            message = "Authorization received. You can close this tab and return to the terminal."
        body = f"<!doctype html><meta charset='utf-8'><title>Kompliance Gmail OAuth</title><p>{message}</p>".encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


def load_client(path: Path) -> tuple[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    client = payload.get("installed") or payload.get("web") or {}
    client_id = str(client.get("client_id", "")).strip()
    client_secret = str(client.get("client_secret", "")).strip()
    if not client_id or not client_secret:
        raise ValueError("The JSON file does not contain an OAuth client ID and secret")
    return client_id, client_secret


def exchange_code(client_id: str, client_secret: str, code: str, verifier: str, redirect_uri: str) -> dict:
    body = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "code_verifier": verifier,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }
    ).encode()
    request = urllib.request.Request(
        TOKEN_ENDPOINT,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode())


def write_environment(output: Path | None, sender: str, client_id: str, client_secret: str, refresh_token: str) -> None:
    lines = [
        "KOMPLIANCE_EMAIL_PROVIDER=gmail_oauth",
        f"KOMPLIANCE_SMTP_FROM={sender}",
        f"KOMPLIANCE_GMAIL_CLIENT_ID={client_id}",
        f"KOMPLIANCE_GMAIL_CLIENT_SECRET={client_secret}",
        f"KOMPLIANCE_GMAIL_REFRESH_TOKEN={refresh_token}",
    ]
    block = "\n".join(lines) + "\n"
    if output:
        output.write_text(block, encoding="utf-8")
        output.chmod(0o600)
        print(f"OAuth environment block written to {output.resolve()}")
        print("Keep that file untracked and restrict access to your Windows account.")
    else:
        print("\nCopy these values directly into the untracked deployment .env, then clear this terminal:")
        print(block)


def main() -> int:
    parser = argparse.ArgumentParser(description="Authorize Kompliance to send Gmail messages")
    parser.add_argument("client_json", type=Path, help="Downloaded Google OAuth Desktop client JSON")
    parser.add_argument("--sender", default="", help="Gmail sender address for the generated environment block")
    parser.add_argument("--output", type=Path, help="Explicit untracked file to receive the environment block")
    parser.add_argument("--no-browser", action="store_true", help="Print the consent URL instead of opening it")
    parser.add_argument("--timeout", type=int, default=300, help="Seconds to wait for the local OAuth callback")
    parser.add_argument("--session-file", type=Path, help="Private resumable PKCE session file")
    parser.add_argument("--complete-url-file", type=Path, help="File containing a returned Google callback URL")
    args = parser.parse_args()

    client_id, client_secret = load_client(args.client_json)
    if args.complete_url_file:
        if not args.session_file or not args.session_file.is_file():
            raise ValueError("--complete-url-file requires an existing --session-file")
        session = json.loads(args.session_file.read_text(encoding="utf-8"))
        callback_url = args.complete_url_file.read_text(encoding="utf-8").strip()
        callback = urllib.parse.parse_qs(urllib.parse.urlparse(callback_url).query)
        if callback.get("state", [""])[0] != session.get("state"):
            raise ValueError("OAuth callback state validation failed")
        code = callback.get("code", [""])[0]
        if not code:
            raise ValueError("OAuth callback contains no authorization code")
        tokens = exchange_code(client_id, client_secret, code, session["verifier"], session["redirect_uri"])
        refresh_token = str(tokens.get("refresh_token", "")).strip()
        if not refresh_token:
            raise RuntimeError("Google returned no refresh token; revoke the prior grant and try again")
        write_environment(args.output, args.sender, client_id, client_secret, refresh_token)
        args.session_file.write_text(json.dumps({"completed": True}), encoding="utf-8")
        args.session_file.chmod(0o600)
        args.complete_url_file.write_text(json.dumps({"completed": True}), encoding="utf-8")
        args.complete_url_file.chmod(0o600)
        return 0

    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    OAuthCallbackHandler.expected_state = state
    OAuthCallbackHandler.result = {}
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), OAuthCallbackHandler)
    redirect_uri = f"http://127.0.0.1:{server.server_port}/"
    if args.session_file:
        args.session_file.write_text(
            json.dumps({"state": state, "verifier": verifier, "redirect_uri": redirect_uri}),
            encoding="utf-8",
        )
        args.session_file.chmod(0o600)
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": GMAIL_SEND_SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    authorization_url = f"{AUTH_ENDPOINT}?{query}"
    print("Requesting only the Gmail send permission.")
    if args.no_browser or not webbrowser.open(authorization_url):
        print(f"Open this URL in your browser:\n{authorization_url}")
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    thread.join(timeout=max(60, min(args.timeout, 1800)))
    server.server_close()
    result = OAuthCallbackHandler.result
    if not result:
        raise TimeoutError("No OAuth callback was received before the configured timeout")
    if result.get("error"):
        raise RuntimeError(f"Google authorization failed: {result['error']}")
    tokens = exchange_code(client_id, client_secret, result.get("code", ""), verifier, redirect_uri)
    refresh_token = str(tokens.get("refresh_token", "")).strip()
    if not refresh_token:
        raise RuntimeError("Google returned no refresh token; revoke the prior grant and try again")

    write_environment(args.output, args.sender, client_id, client_secret, refresh_token)
    if args.session_file:
        args.session_file.write_text(json.dumps({"completed": True}), encoding="utf-8")
        args.session_file.chmod(0o600)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
