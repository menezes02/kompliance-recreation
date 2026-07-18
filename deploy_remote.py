#!/usr/bin/env python3
"""Upload and deploy the Kompliance Docker project over SSH.

Required environment variables:
  KOMPLIANCE_SSH_HOST
  KOMPLIANCE_SSH_USER
  KOMPLIANCE_SSH_PASS

The password is read only from the process environment and is never written to
the project or remote server.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko


LOCAL_ARCHIVE = Path(__file__).resolve().parent.parent / "kompliance-deploy.tar"
REMOTE_HOME = "/home/vulcano"
REMOTE_ARCHIVE_PART = f"{REMOTE_HOME}/kompliance-deploy.tar.part"
REMOTE_ARCHIVE = f"{REMOTE_HOME}/kompliance-deploy.tar"
REMOTE_APP = f"{REMOTE_HOME}/apps/kompliance"


def require_environment(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def run_remote(client: paramiko.SSHClient, command: str, timeout: int = 1800) -> None:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    del stdin
    while not stdout.channel.exit_status_ready():
        if stdout.channel.recv_ready():
            sys.stdout.write(stdout.channel.recv(65536).decode("utf-8", "replace"))
            sys.stdout.flush()
        if stdout.channel.recv_stderr_ready():
            sys.stderr.write(
                stdout.channel.recv_stderr(65536).decode("utf-8", "replace")
            )
            sys.stderr.flush()
        time.sleep(0.1)
    while stdout.channel.recv_ready():
        sys.stdout.write(stdout.channel.recv(65536).decode("utf-8", "replace"))
    while stdout.channel.recv_stderr_ready():
        sys.stderr.write(
            stdout.channel.recv_stderr(65536).decode("utf-8", "replace")
        )
    exit_status = stdout.channel.recv_exit_status()
    if exit_status:
        raise RuntimeError(f"Remote deployment command exited with {exit_status}")


def main() -> None:
    host = require_environment("KOMPLIANCE_SSH_HOST")
    user = require_environment("KOMPLIANCE_SSH_USER")
    password = require_environment("KOMPLIANCE_SSH_PASS")
    if not LOCAL_ARCHIVE.is_file():
        raise RuntimeError(f"Deployment archive not found: {LOCAL_ARCHIVE}")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host,
        username=user,
        password=password,
        timeout=20,
        banner_timeout=20,
        auth_timeout=20,
    )

    size = LOCAL_ARCHIVE.stat().st_size
    last_percent = -5

    def progress(transferred: int, total: int) -> None:
        nonlocal last_percent
        percent = int(transferred * 100 / max(total, 1))
        if percent >= last_percent + 5 or transferred == total:
            last_percent = percent
            print(
                f"UPLOAD {percent:3d}% "
                f"({transferred / 1024 / 1024:.1f}/{total / 1024 / 1024:.1f} MiB)",
                flush=True,
            )

    print(f"Uploading {size / 1024 / 1024:.1f} MiB...", flush=True)
    sftp = client.open_sftp()
    sftp.put(str(LOCAL_ARCHIVE), REMOTE_ARCHIVE_PART, callback=progress)
    try:
        sftp.remove(REMOTE_ARCHIVE)
    except FileNotFoundError:
        pass
    sftp.rename(REMOTE_ARCHIVE_PART, REMOTE_ARCHIVE)
    sftp.close()

    deploy_command = f"""
set -eu
mkdir -p '{REMOTE_APP}'
tar -xf '{REMOTE_ARCHIVE}' -C '{REMOTE_APP}'
rm -f '{REMOTE_ARCHIVE}'
cd '{REMOTE_APP}'
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker inspect kompliance_app_example --format '{{{{json .State.Health}}}}'
"""
    run_remote(client, deploy_command)
    client.close()
    print("DEPLOYMENT_COMPLETE", flush=True)


if __name__ == "__main__":
    main()
