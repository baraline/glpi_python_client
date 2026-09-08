"""Leave one ticket parked on the out-of-range status 99, for UI inspection.

``probe_ticket_status_scope.py`` established that GLPI 11 stores any integer
written to ``status`` -- 0, 7, 8, 9 and 99 all returned 200 and read back as
``{"id": 99, "name": "99"}``, the name falling back to the number because no
label exists for it. What the API reports and what the *web interface* does
with such a row are different questions, and the second one decides whether
the write model should be strict: if the UI degrades gracefully, a
permissive ``int`` costs little; if the ticket becomes unopenable or
unfilterable, the library should refuse the value GLPI accepts.

**This probe deliberately leaves its ticket behind.** Every other probe in
this directory cleans up in a ``finally``; this one is meant to be looked at
in the browser and deleted by hand afterwards. It prints the id and the
front-end URL for that.

Usage
-----
    python integration_tests/probe_ticket_status_99.py
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SECRETS_DIR = _REPO_ROOT / "secrets"

#: The value to park the ticket on: far outside the contract enum
#: ``[1, 10, 2, 3, 4, 5, 6]`` and outside GLPI's own core constants.
_ROGUE_STATUS = 99


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


def _front_url(api_url: str) -> str:
    """Derive the web front-end origin from the API base URL."""

    parsed = urlparse(api_url)
    return f"{parsed.scheme}://{parsed.netloc}"


def main() -> None:
    """Create one ticket, park it on status 99, and leave it there."""

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

        created = client.post(
            f"{base}/Assistance/Ticket",
            headers=write_headers,
            json={
                "name": (
                    f"py_glpi PROBE statut {_ROGUE_STATUS} "
                    "-- a supprimer apres inspection"
                ),
                "content": (
                    "<p>Ticket de sonde. Son statut a ete force a "
                    f"{_ROGUE_STATUS}, une valeur hors de l'enum du contrat, "
                    "pour observer ce que l'interface en fait. "
                    "Supprimable sans risque.</p>"
                ),
            },
            timeout=30,
        )
        if created.status_code >= 400:
            sys.exit(f"create failed: HTTP {created.status_code} {created.text}")
        ticket_id = created.json().get("id")
        if not ticket_id:
            sys.exit(f"no id in create response: {created.text[:300]}")

        patch = client.request(
            "PATCH",
            f"{base}/Assistance/Ticket/{ticket_id}",
            headers=write_headers,
            json={"status": _ROGUE_STATUS},
            timeout=30,
        )
        read = client.get(
            f"{base}/Assistance/Ticket/{ticket_id}", headers=read_headers, timeout=30
        )
        status: Any = read.json().get("status") if read.status_code < 400 else None

        front = _front_url(base)
        print("=" * 72)
        print(f"  ticket        : #{ticket_id}")
        print(f"  PATCH status  : {_ROGUE_STATUS} -> HTTP {patch.status_code}")
        print(f"  read back     : {status!r}")
        print()
        print(f"  interface     : {front}/front/ticket.form.php?id={ticket_id}")
        print(f"  liste         : {front}/front/ticket.php")
        print()
        print("  NON SUPPRIME -- a supprimer a la main apres inspection.")
        print("=" * 72)


if __name__ == "__main__":
    main()
