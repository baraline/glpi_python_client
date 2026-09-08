"""Record whether GLPI honours ``status`` at create, and how closed the set is.

Follow-up to :mod:`probe_ticket_status`, which established that the v2 PATCH
does write ``status`` (contradicting the package's own docstring). Two
questions remain before the field can be declared on the write models:

**Does POST honour it?** ``PatchTicket`` inherits ``PostTicket``, so
declaring the field once exposes it on both. The v2 API is fail-open --
it answered 200 to a field that does not exist -- so a create that returns
an id proves nothing. Only reading the new ticket back does.

**Is the id set fixed, or per instance?** The contract advertises a closed
enum ``[1, 10, 2, 3, 4, 5, 6]`` on ``Ticket.status.id``. If the server
rejects a value outside it, the set is validated server-side and an enum is
the right type. If it accepts one, the set is looser than the contract says
and an enum would reject values a real instance can hold -- the failure
mode ``GlpiPriority`` already documents, where a missing sixth level took
down whole searches.

Read-mostly: two tickets are created and force-deleted in a ``finally``.

Usage
-----
    python integration_tests/probe_ticket_status_scope.py
"""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SECRETS_DIR = _REPO_ROOT / "secrets"

_STATUS_NAMES = {
    1: "NEW",
    2: "ASSIGNED",
    3: "PLANNED",
    4: "PENDING",
    5: "SOLVED",
    6: "CLOSED",
    10: "VALIDATION",
}

#: Values probed for acceptance, and why each one is interesting.
#:
#: ``7``/``8``/``9`` sit in the gap the contract leaves between ``6`` and
#: ``10`` -- exactly where an instance-defined extra status would land if
#: statuses were a dropdown table. ``99`` is far outside any plausible set,
#: and ``0`` is below it. If the server rejects all of them the set is
#: closed and validated; if it stores one, the contract enum is too narrow.
_OUT_OF_CONTRACT = (7, 8, 9, 99, 0)


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
    """Exit with a diagnosis when the API host does not resolve."""

    host = urlparse(api_url).hostname
    if not host:
        sys.exit(f"glpi_api_url is not a URL: {api_url!r}")
    try:
        socket.getaddrinfo(host, None)
    except socket.gaierror:
        sys.exit(f"cannot resolve {host} -- connect to the corporate VPN.")


def _token(client: httpx.Client, config: dict[str, str]) -> str:
    """Obtain a v2 access token with the password grant."""

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


def _read_status(
    client: httpx.Client, base: str, headers: dict[str, str], ticket_id: int
) -> Any:
    """Return the ticket's ``status`` as GLPI v2 currently reports it."""

    response = client.get(
        f"{base}/Assistance/Ticket/{ticket_id}", headers=headers, timeout=30
    )
    if response.status_code >= 400:
        return f"<read failed HTTP {response.status_code}>"
    return response.json().get("status")


def _describe(status: Any) -> str:
    """Render a status value with its enum name when one can be read off."""

    ident = status.get("id") if isinstance(status, dict) else status
    if isinstance(ident, int) and ident in _STATUS_NAMES:
        return f"{status!r}  ({_STATUS_NAMES[ident]})"
    return f"{status!r}"


def _identifier(status: Any) -> Any:
    """Return the numeric id out of either status spelling."""

    return status.get("id") if isinstance(status, dict) else status


def _create(
    client: httpx.Client,
    base: str,
    write_headers: dict[str, str],
    body: dict[str, Any],
) -> tuple[int | None, httpx.Response]:
    """Create one probe ticket and return its id alongside the response."""

    payload = {
        "name": "py_glpi status-scope probe (safe to delete)",
        "content": "<p>Automated probe. Deleted immediately.</p>",
        **body,
    }
    response = client.post(
        f"{base}/Assistance/Ticket", headers=write_headers, json=payload, timeout=30
    )
    if response.status_code >= 400:
        return None, response
    try:
        return response.json().get("id"), response
    except ValueError:
        return None, response


def _probe_contract(client: httpx.Client, base: str, headers: dict[str, str]) -> None:
    """Print what this instance publishes for ``Ticket.status`` if reachable.

    The path the HL API serves its OpenAPI document on is not something the
    package records, so several plausible ones are tried and the first that
    answers with the ticket schema is reported. A miss is not a failure --
    the behavioural probes below are the authority either way.
    """

    parent = base.rsplit("/", 1)[0]
    for path in (
        f"{base}/doc.json",
        f"{base}/openapi.json",
        f"{base}/swagger.json",
        f"{base}/doc",
        f"{parent}/doc.json",
        f"{parent}/doc",
    ):
        try:
            response = client.get(path, headers=headers, timeout=20)
        except httpx.HTTPError as exc:
            print(f"  {path} -> transport error {exc!r}")
            continue
        if response.status_code >= 400:
            print(f"  {path} -> HTTP {response.status_code}")
            continue
        body = response.text
        print(f"  {path} -> HTTP {response.status_code}, {len(body)} bytes")
        try:
            document = response.json()
        except ValueError:
            print("      (not JSON -- probably the doc UI)")
            continue
        schemas = (
            document.get("components", {}).get("schemas", {})
            if isinstance(document, dict)
            else {}
        )
        for name, schema in schemas.items():
            if "ticket" not in name.lower():
                continue
            status = schema.get("properties", {}).get("status")
            if status:
                rendered = json.dumps(status, ensure_ascii=False)
                print(f"      {name}.status -> {rendered}")
        return


def main() -> None:
    """Run the create-time and value-range probes and print a report."""

    config = _load()
    base = config["api_url"].rstrip("/")
    _check_reachable(base)

    with httpx.Client(verify=False, follow_redirects=True, timeout=30) as client:
        token = _token(client, config)
        read_headers = {"Authorization": f"Bearer {token}"}
        write_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        print("=" * 72)
        print("PROBE 0 -- what does this instance publish for Ticket.status?")
        print("=" * 72)
        _probe_contract(client, base, read_headers)
        print()

        created: list[int] = []
        try:
            print("=" * 72)
            print("PROBE 1 -- does POST honour `status` at create time?")
            print("=" * 72)
            for label, body in (
                ("int shape    {'status': 4}", {"status": 4}),
                ("object shape {'status': {'id': 4}}", {"status": {"id": 4}}),
            ):
                new_id, response = _create(client, base, write_headers, body)
                print(f"  {label}")
                print(f"      POST        -> HTTP {response.status_code}")
                if new_id is None:
                    print(f"      body        -> {response.text[:300]!r}")
                    print("      VERDICT     -> create failed, nothing to read back")
                    print()
                    continue
                created.append(new_id)
                status = _read_status(client, base, read_headers, new_id)
                print(f"      created     -> #{new_id}")
                print(f"      status      -> {_describe(status)}")
                print(
                    "      VERDICT     -> "
                    + (
                        "HONOURED at create"
                        if _identifier(status) == 4
                        else "IGNORED at create (fell back to the default)"
                    )
                )
                print()

            print("=" * 72)
            print("PROBE 2 -- is the id set closed, or looser than the contract?")
            print("=" * 72)
            if not created:
                print("  no probe ticket available -- skipped")
            else:
                target = created[0]
                print(
                    f"  probing on #{target}; contract enum is [1, 2, 3, 4, 5, 6, 10]"
                )
                print()
                for value in _OUT_OF_CONTRACT:
                    before = _read_status(client, base, read_headers, target)
                    patch = client.request(
                        "PATCH",
                        f"{base}/Assistance/Ticket/{target}",
                        headers=write_headers,
                        json={"status": value},
                        timeout=30,
                    )
                    after = _read_status(client, base, read_headers, target)
                    stored = _identifier(after) == value
                    print(f"  status = {value}")
                    print(f"      PATCH       -> HTTP {patch.status_code}")
                    if patch.status_code >= 400:
                        print(f"      error body  -> {patch.text[:200]!r}")
                    print(
                        f"      read back   -> {_describe(after)} "
                        f"(was {_describe(before)})"
                    )
                    print(
                        "      VERDICT     -> "
                        + (
                            f"STORED {value} -- the set is NOT closed; an enum "
                            "would reject a value this instance can hold"
                            if stored
                            else "refused -- value not stored"
                        )
                    )
                    print()
        finally:
            for ticket_id in created:
                cleanup = client.request(
                    "DELETE",
                    f"{base}/Assistance/Ticket/{ticket_id}",
                    headers=write_headers,
                    json={"force": True},
                    timeout=30,
                )
                print(f"  cleanup: force-deleted #{ticket_id} -> {cleanup.status_code}")


if __name__ == "__main__":
    main()
