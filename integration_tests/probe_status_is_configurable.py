"""Determine whether ticket statuses are instance data or hardcoded values.

``PatchTicket.status`` is typed as a closed enum. That is only defensible
if the id set cannot be extended or renamed by a GLPI administrator: a
per-instance vocabulary would make the enum reject values a real server
legitimately holds -- the failure mode ``GlpiPriority`` already carries,
where the contract's missing ``Major`` level took down whole searches.

Three independent read-only checks, because no single one is conclusive:

1. **Is there a dropdown itemtype behind it?** GLPI's configurable
   vocabularies are ordinary itemtypes -- ``ITILCategory``,
   ``RequestType``, ``SolutionType`` -- each with a CRUD route on the v1
   API and a management screen behind it. If ``status`` were one, a
   comparable itemtype would answer. Several plausible names are tried
   against v1, with two known-configurable ones as positive controls: a
   probe where *everything* 404s proves nothing.

2. **How does GLPI describe the field to itself?** ``listSearchOptions``
   reports each field's storage. A foreign key into a dropdown table
   shows that table; a hardcoded column shows ``glpi_tickets`` with a
   ``specific``-style datatype and no linked table.

3. **What does the v2 contract publish?** A configurable vocabulary
   cannot be published as a fixed ``enum`` with fixed labels, because the
   document is generated per instance. Whether the labels are localised
   or stored is visible in the same place.

Nothing is created, modified or deleted.

Usage
-----
    python integration_tests/probe_status_is_configurable.py
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

#: Itemtypes probed on the v1 API, and what each answer would mean.
#:
#: The first two are *positive controls*: both are configurable GLPI
#: vocabularies with an admin screen, so both must answer. If they do not,
#: the account lacks the rights and the whole probe is uninformative rather
#: than negative. The rest are the names a ticket-status dropdown would
#: plausibly carry if one existed.
_ITEMTYPES = (
    ("ITILCategory", "control -- known configurable"),
    ("RequestType", "control -- known configurable"),
    ("TicketStatus", "would be the dropdown if statuses were data"),
    ("ITILStatus", "ditto, alternative naming"),
    ("Status", "ditto, generic naming"),
)


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
        sys.exit(f"cannot resolve {host} -- connect to the corporate VPN.")


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


def _v1_session(
    client: httpx.Client, config: dict[str, str | None]
) -> dict[str, str] | None:
    """Open a legacy v1 session and return its headers, or ``None``."""

    v1_url = config.get("v1_url")
    user_token = config.get("v1_user_token")
    if not v1_url or not user_token:
        return None
    headers = {"Authorization": f"user_token {user_token}"}
    app_token = config.get("v1_app_token")
    if app_token:
        headers["App-Token"] = str(app_token)
    init = client.get(
        f"{str(v1_url).rstrip('/')}/initSession", headers=headers, timeout=30
    )
    if init.status_code >= 400:
        print(f"  v1 initSession -> HTTP {init.status_code} {init.text[:200]!r}")
        return None
    session_headers = {"Session-Token": str(init.json().get("session_token"))}
    if app_token:
        session_headers["App-Token"] = str(app_token)
    return session_headers


def _probe_itemtypes(client: httpx.Client, v1: str, headers: dict[str, str]) -> None:
    """Ask v1 for each candidate dropdown itemtype and report the answer."""

    for itemtype, note in _ITEMTYPES:
        response = client.get(
            f"{v1}/{itemtype}", headers=headers, params={"range": "0-2"}, timeout=30
        )
        exists = response.status_code < 400
        rows = ""
        if exists:
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if isinstance(payload, list):
                names = [r.get("name") for r in payload if isinstance(r, dict)][:3]
                rows = f"  first rows: {names}"
        verdict = "EXISTS" if exists else "absent"
        print(f"  {itemtype:<16} HTTP {response.status_code}  {verdict:<7} ({note})")
        if rows:
            print(f"      {rows.strip()}")


def _probe_search_options(
    client: httpx.Client, v1: str, headers: dict[str, str]
) -> None:
    """Print how GLPI describes the ticket ``status`` field's storage."""

    response = client.get(f"{v1}/listSearchOptions/Ticket", headers=headers, timeout=30)
    if response.status_code >= 400:
        print(f"  listSearchOptions/Ticket -> HTTP {response.status_code}")
        return
    try:
        options = response.json()
    except ValueError:
        print("  listSearchOptions/Ticket -> not JSON")
        return
    if not isinstance(options, dict):
        print(f"  listSearchOptions/Ticket -> unexpected shape {type(options)}")
        return
    for key, option in options.items():
        if not isinstance(option, dict):
            continue
        if option.get("field") != "status":
            continue
        print(f"  option {key}: {json.dumps(option, ensure_ascii=False)}")


def _probe_contract(client: httpx.Client, base: str, headers: dict[str, str]) -> None:
    """Print each ITIL type's published ``status`` enum.

    ``Problem`` and ``Change`` are included because the earlier value-range
    probe found that ``7``, ``8`` and ``9`` are *stored* on a ticket even
    though the ticket enum stops at ``6`` (plus ``10``). If those ids turn
    up as legitimate statuses of the sibling ITIL types, then they are
    core constants of the shared parent class rather than room left for
    instance-defined values -- which is the difference between "the set is
    extensible" and "the column is unvalidated".
    """

    response = client.get(f"{base}/doc.json", headers=headers, timeout=60)
    if response.status_code >= 400:
        print(f"  {base}/doc.json -> HTTP {response.status_code}")
        return
    try:
        document: Any = response.json()
    except ValueError:
        print("  doc.json -> not JSON")
        return
    schemas = document.get("components", {}).get("schemas", {})
    for name in ("Ticket", "Problem", "Change"):
        status = schemas.get(name, {}).get("properties", {}).get("status")
        if status is None:
            print(f"  {name}.status -> <no such schema>")
            continue
        ident = status.get("properties", {}).get("id", status)
        print(f"  {name}.status ids -> {ident.get('enum')}")
        description = (ident.get("description") or "").strip()
        for line in description.splitlines():
            print(f"      {line}")


def main() -> None:
    """Run the three checks and print a report."""

    config = _load()
    base = str(config["api_url"]).rstrip("/")
    _check_reachable(base)

    with httpx.Client(verify=False, follow_redirects=True, timeout=60) as client:
        token = _token(client, config)
        read_headers = {"Authorization": f"Bearer {token}"}

        print("=" * 72)
        print("CHECK 1 -- is there a dropdown itemtype behind ticket status?")
        print("=" * 72)
        v1_headers = _v1_session(client, config)
        if v1_headers is None:
            print("  v1 session unavailable -- skipped")
        else:
            v1 = str(config["v1_url"]).rstrip("/")
            try:
                _probe_itemtypes(client, v1, v1_headers)
                print()
                print("=" * 72)
                print("CHECK 2 -- how does GLPI describe the field's storage?")
                print("=" * 72)
                _probe_search_options(client, v1, v1_headers)
            finally:
                client.get(f"{v1}/killSession", headers=v1_headers, timeout=30)
        print()

        print("=" * 72)
        print("CHECK 3 -- what does the v2 contract publish?")
        print("=" * 72)
        _probe_contract(client, base, read_headers)


if __name__ == "__main__":
    main()
