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

**#22 follow-up -- does GLPI honour an offset on write?** The fix for #22
changed outbound serialisation to Pydantic's JSON mode, so an aware
``datetime`` now goes out as ``...+02:00`` or ``...Z``. Accepting it and
honouring it are different questions, and only the second is dangerous to
get wrong: a truncated offset moves the moment silently, with a 200.

This is a **read-mostly** probe. It creates exactly one ticket -- reused by
both write probes -- and deletes it again in a ``finally``. Nothing else is
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
import socket
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

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


def _check_reachable(api_url: str) -> None:
    """Exit with a diagnosis when the API host does not resolve.

    The GLPI instance lives on an internal ``.local`` name, so running this
    off the corporate VPN fails during DNS with a forty-line httpx traceback
    ending in ``getaddrinfo failed`` -- which looks like a bug in the probe
    rather than a missing network. Checking first turns that into one line.
    """

    host = urlparse(api_url).hostname
    if not host:
        sys.exit(f"glpi_api_url is not a URL: {api_url!r}")
    try:
        socket.getaddrinfo(host, None)
    except socket.gaierror:
        try:
            socket.getaddrinfo("github.com", None)
        except socket.gaierror:
            sys.exit(f"cannot resolve {host} -- and public DNS is down too.")
        sys.exit(
            f"cannot resolve {host}.\n"
            "Public DNS works, so this is name resolution for the internal "
            "domain: connect to the corporate VPN and run this again.\n"
            "(The integration suite cannot reach the instance either while "
            "this fails.)"
        )


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


#: The three ways this package can now render one moment onto the wire.
#:
#: These are not hypothetical spellings -- they are the literal bytes
#: ``model_to_payload`` produces for a ``PatchTicket(date=...)`` built with a
#: UTC ``tzinfo``, a ``Europe/Paris`` one, and none at all. Pydantic's JSON
#: mode writes UTC as ``Z`` and every other zone as a numeric offset.
#:
#: ``12:30Z`` is the discriminating case, because it is ``14:30`` in Paris:
#: a server that honours the offset stores a different wall clock than one
#: that ignores it, and one read-back separates them. The ``+02:00`` case
#: cannot discriminate -- it names the same wall clock either way -- but it
#: does answer whether an offset-bearing string is accepted at all.
_WRITE_CASES = (
    ("naive   (control)", "2026-08-01T12:30:00"),
    ("UTC     (Z form) ", "2026-08-01T12:30:00Z"),
    ("Paris   (+02:00) ", "2026-08-01T12:30:00+02:00"),
    ("Tokyo   (+09:00) ", "2026-08-01T12:30:00+09:00"),
    ("LA      (-08:00) ", "2026-08-01T12:30:00-08:00"),
    ("Kiritim (+14:00) ", "2026-08-01T12:30:00+14:00"),
    ("nonsense(+99:99) ", "2026-08-01T12:30:00+99:99"),
)


def _probe_write_offsets(
    client: httpx.Client,
    base: str,
    read_headers: dict[str, str],
    write_headers: dict[str, str],
    ticket_id: int,
) -> None:
    """Write each spelling of one moment and report what GLPI stored.

    Issue #22 changed outbound serialisation to Pydantic's JSON mode, so an
    aware ``datetime`` now leaves as ``...+02:00`` or ``...Z`` where it
    previously left as a live object that ``json.dumps`` refused. That fixed
    the crash but moved the question rather than answering it: nothing here
    had ever recorded whether GLPI *accepts* an offset, nor -- the part that
    matters more -- whether it *honours* one.

    A rejection is loud and harmless. Silent truncation is neither: writing
    ``12:30Z`` and having 12:30 stored as Paris local time moves the moment
    two hours with a 200 and no complaint.
    """

    for label, wire in _WRITE_CASES:
        patch = client.request(
            "PATCH",
            f"{base}/Assistance/Ticket/{ticket_id}",
            headers=write_headers,
            json={"date": wire},
        )
        if patch.status_code >= 400:
            print(f"  {label} {wire!r}")
            print(f"      PATCH -> HTTP {patch.status_code} REJECTED")
            print(f"      body  -> {patch.text[:200]!r}")
            continue
        read = client.get(f"{base}/Assistance/Ticket/{ticket_id}", headers=read_headers)
        stored = read.json().get("date") if read.status_code < 400 else None
        print(f"  {label} {wire!r}")
        print(f"      PATCH -> HTTP {patch.status_code}   read back -> {stored!r}")


def main() -> None:
    """Run every probe and print a report to paste into the issues."""

    config = _load()
    base = config["api_url"].rstrip("/")
    _check_reachable(base)

    with httpx.Client(verify=False, follow_redirects=True, timeout=30) as client:
        token = _token(client, config)
        # A GET must NOT advertise a JSON content type. GLPI sees the header,
        # tries to parse the (absent) body, and answers 400 "Contenu du JSON
        # invalide" -- an error about the request body on a request that has
        # none. The library avoids this with its `include_content_type` flag,
        # which is False for GET; the two header sets here mirror that.
        read_headers = {"Authorization": f"Bearer {token}"}
        write_headers = {
            "Authorization": f"Bearer {token}",
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
            response = client.get(f"{base}{path}", headers=read_headers)
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
                headers=write_headers,
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
            if created_id:
                print()
                print("=" * 72)
                print("PROBE 3 (#22 follow-up) -- does GLPI honour an offset on write?")
                print("=" * 72)
                _probe_write_offsets(
                    client, base, read_headers, write_headers, created_id
                )
        finally:
            if created_id:
                # `client.delete(...)` rejects `json=` -- httpx exposes a body
                # only on `request()`, because DELETE-with-a-body is unusual.
                # GLPI needs one for `force`, so this must not be "simplified"
                # back to the convenience method; the library's own
                # `_delete_request` goes through `session.request` for the
                # same reason.
                cleanup = client.request(
                    "DELETE",
                    f"{base}/Assistance/Ticket/{created_id}",
                    headers=write_headers,
                    json={"force": True},
                )
                print()
                print(f"  cleanup: deleted {created_id} -> {cleanup.status_code}")
            else:
                print()
                print("  cleanup: nothing to delete (no id parsed from the response)")


if __name__ == "__main__":
    main()
