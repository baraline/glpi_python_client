"""Record whether GLPI 11 accepts a ticket *status* write, and on which route.

The package excludes ``status`` from ``PostTicket``/``PatchTicket`` on the
stated grounds that "GLPI manages the ticket lifecycle through dedicated
timeline routes". Nothing in the repository records a measurement behind
that claim, and the v2 API is fail-open: it answers 200 to fields it does
not recognise, so "the PATCH succeeded" proves nothing on its own. Every
case below therefore *reads the ticket back* and compares.

Cases, each on a distinct target status so one cannot be mistaken for
another's leftover:

* control    -- PATCH a field that certainly does not exist. If this is a
                200, then a 200 on ``status`` means nothing by itself.
* v2 object  -- ``{"status": {"id": 4}}``   (PENDING) -- the read shape.
* v2 int     -- ``{"status": 3}``           (PLANNED) -- the v1 shape.
* v2 id      -- ``{"status_id": 2}``        (ASSIGNED) -- GLPI's other idiom.
* v1 PUT     -- ``{"input": {"status": 6}}`` (CLOSED) -- the legacy route,
                the same escape hatch ``set_kb_article_categories`` uses.

Read-mostly: one ticket is created and force-deleted in a ``finally``.

Usage
-----
    python probe_ticket_status.py

Credentials load exactly as the integration suite loads them: from the
repository's ``secrets/`` files, falling back to ``GLPI_*`` env vars.
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


def _read_value(secret_name: str, env_name: str) -> str | None:
    """Return the secret file's contents, or the environment fallback."""

    path = _SECRETS_DIR / secret_name
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    env_value = os.environ.get(env_name)
    return env_value.strip() if env_value else None


def _load() -> dict[str, str | None]:
    """Resolve the live configuration or exit with what is missing."""

    required = {
        "api_url": ("glpi_api_url", "GLPI_API_URL"),
        "client_id": ("glpi_client_id_test", "GLPI_CLIENT_ID"),
        "client_secret": ("glpi_client_secret_test", "GLPI_CLIENT_SECRET"),
        "username": ("glpi_username", "GLPI_USERNAME"),
        "password": ("glpi_password", "GLPI_PASSWORD"),
    }
    optional = {
        "v1_url": ("glpi_api_v1_url", "GLPI_API_V1_URL"),
        "v1_user_token": ("glpi_api_v1_token_user", "GLPI_V1_USER_TOKEN"),
        "v1_app_token": ("glpi_api_v1_app_token", "GLPI_V1_APP_TOKEN"),
    }
    config: dict[str, str | None] = {}
    missing: list[str] = []
    for key, (secret, env) in required.items():
        value = _read_value(secret, env)
        if value is None:
            missing.append(secret)
        else:
            config[key] = value
    if missing:
        sys.exit("missing credentials: " + ", ".join(missing))
    for key, (secret, env) in optional.items():
        config[key] = _read_value(secret, env)
    return config


def _check_reachable(api_url: str) -> None:
    """Exit with a diagnosis when the API host does not resolve."""

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
            "Public DNS works, so this is internal name resolution: connect "
            "to the corporate VPN and run this again."
        )


def _token(client: httpx.Client, config: dict[str, str | None]) -> str:
    """Obtain a v2 access token with the password grant."""

    response = client.post(
        f"{str(config['api_url']).rstrip('/')}/token",
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


def _probe_v2_case(
    client: httpx.Client,
    base: str,
    read_headers: dict[str, str],
    write_headers: dict[str, str],
    ticket_id: int,
    label: str,
    body: dict[str, Any],
    expected: int | None,
) -> None:
    """PATCH one body shape on the v2 route, then read the ticket back."""

    before = _read_status(client, base, read_headers, ticket_id)
    patch = client.request(
        "PATCH",
        f"{base}/Assistance/Ticket/{ticket_id}",
        headers=write_headers,
        json=body,
        timeout=30,
    )
    after = _read_status(client, base, read_headers, ticket_id)
    print(f"  {label}")
    print(f"      body        -> {json.dumps(body, ensure_ascii=False)}")
    print(f"      PATCH       -> HTTP {patch.status_code}")
    if patch.status_code >= 400:
        print(f"      error body  -> {patch.text[:300]!r}")
    print(f"      status before -> {_describe(before)}")
    print(f"      status after  -> {_describe(after)}")
    if expected is None:
        print(
            "      VERDICT     -> "
            + (
                "v2 REJECTS an unknown field (a 200 on status would be meaningful)"
                if patch.status_code >= 400
                else "v2 ACCEPTS an unknown field with a 200 -- a 200 alone "
                "proves NOTHING; only the read-back counts"
            )
        )
    else:
        ident = after.get("id") if isinstance(after, dict) else after
        applied = ident == expected
        print(
            "      VERDICT     -> "
            + (
                f"APPLIED (status is now {expected})"
                if applied
                else f"NOT APPLIED (wanted {expected}, still {ident!r})"
            )
        )
    print()


def _probe_v1(
    client: httpx.Client,
    base: str,
    read_headers: dict[str, str],
    config: dict[str, str | None],
    ticket_id: int,
    target: int,
) -> None:
    """Init a legacy v1 session, PUT the status, read back through v2."""

    v1_url = config.get("v1_url")
    user_token = config.get("v1_user_token")
    if not v1_url or not user_token:
        print("  v1 PUT: SKIPPED -- glpi_api_v1_url / glpi_api_v1_token_user absent")
        return
    v1 = str(v1_url).rstrip("/")
    init_headers = {"Authorization": f"user_token {user_token}"}
    app_token = config.get("v1_app_token")
    if app_token:
        init_headers["App-Token"] = app_token

    init = client.get(f"{v1}/initSession", headers=init_headers, timeout=30)
    if init.status_code >= 400:
        print(f"  v1 PUT: initSession -> HTTP {init.status_code} {init.text[:200]!r}")
        return
    session_token = init.json().get("session_token")
    print(f"  v1 initSession -> HTTP {init.status_code}, token acquired")

    v1_headers = {
        "Session-Token": str(session_token),
        "Content-Type": "application/json",
    }
    if app_token:
        v1_headers["App-Token"] = str(app_token)

    try:
        before = _read_status(client, base, read_headers, ticket_id)
        put = client.put(
            f"{v1}/Ticket/{ticket_id}",
            headers=v1_headers,
            json={"input": {"id": ticket_id, "status": target}},
            timeout=30,
        )
        after = _read_status(client, base, read_headers, ticket_id)
        print(f"      PUT {v1}/Ticket/{ticket_id}")
        print(f"      body        -> {{'input': {{'status': {target}}}}}")
        print(f"      PUT         -> HTTP {put.status_code} {put.text[:200]!r}")
        print(f"      status before -> {_describe(before)}")
        print(f"      status after  -> {_describe(after)}")
        ident = after.get("id") if isinstance(after, dict) else after
        print(
            "      VERDICT     -> "
            + (
                f"APPLIED (status is now {target})"
                if ident == target
                else f"NOT APPLIED (wanted {target}, still {ident!r})"
            )
        )
    finally:
        client.get(f"{v1}/killSession", headers=v1_headers, timeout=30)


def main() -> None:
    """Run the status-write probes and print a report."""

    config = _load()
    base = str(config["api_url"]).rstrip("/")
    _check_reachable(base)

    with httpx.Client(verify=False, follow_redirects=True, timeout=30) as client:
        token = _token(client, config)
        read_headers = {"Authorization": f"Bearer {token}"}
        write_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        created_id: int | None = None
        try:
            created = client.post(
                f"{base}/Assistance/Ticket",
                headers=write_headers,
                json={
                    "name": "py_glpi status-write probe (safe to delete)",
                    "content": "<p>Automated probe. Deleted immediately.</p>",
                },
                timeout=30,
            )
            if created.status_code >= 400:
                sys.exit(f"create failed: HTTP {created.status_code} {created.text}")
            created_id = created.json().get("id")
            if not created_id:
                sys.exit(f"no id in create response: {created.text[:300]}")
            print("=" * 72)
            print(f"probe ticket #{created_id} created")
            baseline = _read_status(client, base, read_headers, created_id)
            print(f"  baseline status -> {_describe(baseline)}")
            print("=" * 72)
            print()

            print("=" * 72)
            print("CONTROL -- is a 200 on the v2 PATCH worth anything?")
            print("=" * 72)
            _probe_v2_case(
                client,
                base,
                read_headers,
                write_headers,
                created_id,
                "unknown field",
                {"__probe_field_that_does_not_exist__": "x"},
                None,
            )

            print("=" * 72)
            print("v2 PATCH /Assistance/Ticket/{id} -- three body shapes")
            print("=" * 72)
            for label, body, expected in (
                ("object shape {'status': {'id': 4}}", {"status": {"id": 4}}, 4),
                ("int shape    {'status': 3}", {"status": 3}, 3),
                ("id shape     {'status_id': 2}", {"status_id": 2}, 2),
            ):
                _probe_v2_case(
                    client,
                    base,
                    read_headers,
                    write_headers,
                    created_id,
                    label,
                    body,
                    expected,
                )

            print("=" * 72)
            print("v1 PUT /Ticket/{id} -- the legacy escape hatch")
            print("=" * 72)
            _probe_v1(client, base, read_headers, config, created_id, 6)
        finally:
            if created_id:
                cleanup = client.request(
                    "DELETE",
                    f"{base}/Assistance/Ticket/{created_id}",
                    headers=write_headers,
                    json={"force": True},
                    timeout=30,
                )
                print()
                print()
                print(
                    f"  cleanup: force-deleted #{created_id} -> {cleanup.status_code}"
                )


if __name__ == "__main__":
    main()
