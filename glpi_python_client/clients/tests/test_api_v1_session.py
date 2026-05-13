from __future__ import annotations

from datetime import datetime, timezone

import pytest

from glpi_python_client import GLPIV1Session

_V1_BASE_URLS = (
    pytest.param("https://glpi.example.test/api.php/v1", id="api.php-v1"),
    pytest.param("https://glpi.example.test/apirest.php", id="apirest.php"),
)


@pytest.mark.parametrize("base_url", _V1_BASE_URLS)
def test_v1_session_rejects_non_positive_refresh_interval(base_url: str) -> None:
    with pytest.raises(ValueError, match="session_refresh_interval_seconds"):
        GLPIV1Session(
            base_url=base_url,
            user_token="user-token",
            app_token="app-token",
            session_refresh_interval_seconds=0,
        )


@pytest.mark.parametrize("base_url", _V1_BASE_URLS)
def test_v1_session_close_releases_http_session_before_init(
    base_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = GLPIV1Session(
        base_url=base_url,
        user_token="user-token",
        app_token="app-token",
    )
    events: list[str] = []

    def get(*args: object, **kwargs: object) -> None:
        events.append("get")

    def close() -> None:
        events.append("close")

    monkeypatch.setattr(session._http, "get", get)
    monkeypatch.setattr(session._http, "close", close)

    session.close()

    assert events == ["close"]


@pytest.mark.parametrize("base_url", _V1_BASE_URLS)
def test_v1_session_close_kills_active_session_and_releases_http_session(
    base_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = GLPIV1Session(
        base_url=base_url,
        user_token="user-token",
        app_token="app-token",
    )
    session._session_token = "session-token"
    session._session_started_at = datetime.now(tz=timezone.utc)
    events: list[str] = []

    def get(url: str, **kwargs: object) -> None:
        events.append(f"get:{url}")

    def close() -> None:
        events.append("close")

    monkeypatch.setattr(session._http, "get", get)
    monkeypatch.setattr(session._http, "close", close)

    session.close()
    session.close()

    assert events == [
        f"get:{base_url}/killSession",
        "close",
        "close",
    ]
    session_state = vars(session)
    assert session_state["_session_token"] is None
    assert session_state["_session_started_at"] is None
