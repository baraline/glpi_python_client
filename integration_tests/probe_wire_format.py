"""Record what GLPI 11 actually puts on the wire, for two open decisions.

Run this against preprod and paste the output into issues #31 and #35. It
answers two questions the repository cannot answer from inside, and both
decide whether a proposed change is worth building at all:

**#31 -- do datetimes arrive naive?** The proposal to attach a server
timezone assumes GLPI omits the UTC offset. Nothing here records a real v2
response, and the project's own fixtures disagree: the knowledge base tests
use ``+00:00`` (which already parses aware) while the timeline, management
and administration tests use a bare ``2024-01-02T03:04:05``. If the live
server sends an offset, #31 can be closed unbuilt.

**#35 -- what does a POST return?** ``_resource_create`` parses the whole
body and keeps one integer. If the body already carries the full record,
the fix is to stop discarding it, not to add a second request behind a
``create_*_and_fetch`` helper.

This is a **read-mostly** probe. It creates exactly one ticket, to see a
create response, and deletes it again in a ``finally``. Nothing else is
written.

Usage
-----
    python integration_tests/probe_wire_format.py

Credentials load the same way the integration suite loads them: from
``secrets/`` files, falling back to ``GLPI_*`` environment variables.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SECRETS_DIR = _REPO_ROOT / "secrets"

#: Wire values that look like a timestamp, offset-bearing or not.
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}")


def _read_value(secret_name: str, env_name: str) -> str | None:
    """Return the secret file's contents, or the environment fallback."""

    path = _SECRETS_DIR / secret_name
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    env_value = os.environ.get(env_name)
    return env_value.strip() if env_value else None


def _load() -> dict[str, str]:
    """Resolve the live configuration or exit with what is missing."""

    wanted = {
        "api_url": ("glpi_api_url", "GLPI_API_URL"),
        "client_id": ("glpi_client_id_test", "GLPI_CLIENT_ID"),
        "client_secret": ("glpi_client_secret_test", "GLPI_CLIENT_SECRET"),
        "username": ("glpi_username", "GLPI_USERNAME"),
        "password": ("glpi_password", "GLPI_PASSWORD"),
    }
    config: dict[str, str] = {}
    missing: list[str] = []
    for key, (secret, env) in wanted.items():
        value = _read_value(secret, env)
        if value is None:
            missing.append(secret)
        else:
            config[key] = value
    if missing:
        sys.exit("missing credentials: " + ", ".join(missing))
    return config


def _token(client: httpx.Client, config: dict[str, str]) -> str:
    """Obtain an access token with the password grant."""

    response = client.post(
        f"{config['api_url'].rstrip('/')}/token",
        data={
            "grant_type": "password",
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "username": config["username"],
            "password": config["password"],
            "scope": "api",
        },
        timeout=30,
    )
    response.raise_for_status()
    return str(response.json()["access_token"])


def _walk_timestamps(payload: Any, prefix: str = "") -> list[tuple[str, str]]:
    """Return every ``(path, value)`` in ``payload`` that looks like a timestamp."""

    found: list[tuple[str, str]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            found.extend(_walk_timestamps(value, f"{prefix}.{key}" if prefix else key))
    elif isinstance(payload, list):
        for index, value in enumerate(payload[:2]):
            found.extend(_walk_timestamps(value, f"{prefix}[{index}]"))
    elif isinstance(payload, str) and _TIMESTAMP.match(payload):
        found.append((prefix, payload))
    return found


def _report_timestamps(label: str, payload: Any) -> None:
    """Print every timestamp in one payload and whether it carries an offset."""

    stamps = _walk_timestamps(payload)
    if not stamps:
        print(f"  {label}: no timestamp-shaped values found")
        return
    for path, value in stamps:
        aware = bool(re.search(r"(Z|[+-]\d{2}:?\d{2})$", value))
        verdict = "AWARE (carries an offset)" if aware else "NAIVE (no offset)"
        print(f"  {label}.{path} = {value!r}  -> {verdict}")


def main() -> None:
    """Run both probes and print a report to paste into the issues."""

    config = _load()
    base = config["api_url"].rstrip("/")

    with httpx.Client(verify=False, follow_redirects=True, timeout=30) as client:
        headers = {
            "Authorization": f"Bearer {_token(client, config)}",
            "Content-Type": "application/json",
        }

        print("=" * 72)
        print("PROBE 1 (issue #31) -- datetime wire format")
        print("=" * 72)
        for label, path in (
            ("Ticket", "/Assistance/Ticket?limit=1"),
            ("User", "/Administration/User?limit=1"),
            ("KBArticle", "/Knowledgebase/Article?limit=1"),
        ):
            response = client.get(f"{base}{path}", headers=headers)
            if response.status_code >= 400:
                print(f"  {label}: HTTP {response.status_code} -- skipped")
                continue
            _report_timestamps(label, response.json())

        print()
        print("=" * 72)
        print("PROBE 2 (issue #35) -- what a create returns")
        print("=" * 72)
        created_id: int | None = None
        try:
            response = client.post(
                f"{base}/Assistance/Ticket",
                headers=headers,
                json={
                    "name": "py_glpi wire-format probe (safe to delete)",
                    "content": "<p>Automated probe. Deleted immediately.</p>",
                },
            )
            print(f"  status      : {response.status_code}")
            print(f"  Location    : {response.headers.get('Location', '<absent>')}")
            print(f"  body bytes  : {len(response.content)}")
            try:
                body = response.json()
            except ValueError:
                print(f"  body        : <not JSON> {response.text[:200]!r}")
            else:
                keys = sorted(body) if isinstance(body, dict) else "<not an object>"
                print(f"  body keys   : {keys}")
                print("  body        :")
                print(json.dumps(body, indent=4, ensure_ascii=False)[:2000])
                if isinstance(body, dict):
                    created_id = body.get("id")
                    print()
                    print(
                        "  VERDICT: "
                        + (
                            "id only -- a fetch is genuinely needed (#35)"
                            if set(body) <= {"id", "href"}
                            else f"{len(body)} fields returned -- the client is "
                            "DISCARDING a fuller record; fix that instead of "
                            "adding create_*_and_fetch (#35)"
                        )
                    )
        finally:
            if created_id:
                cleanup = client.delete(
                    f"{base}/Assistance/Ticket/{created_id}",
                    headers=headers,
                    json={"force": True},
                )
                print()
                print(f"  cleanup: deleted {created_id} -> {cleanup.status_code}")
            else:
                print()
                print("  cleanup: nothing to delete (no id parsed from the response)")


if __name__ == "__main__":
    main()
