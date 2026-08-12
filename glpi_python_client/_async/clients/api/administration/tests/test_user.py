"""Unit tests for the ``Administration/User`` endpoint mixin.

The tests cover search, fetch, create, update, delete, and page-by-page
iteration for GLPI users, using the shared transport recorders to stub
the four transport helpers without any HTTP plumbing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from glpi_python_client import PatchUser, PostUser
from glpi_python_client._async._testing import (
    FailingTransportRecorder,
    TransportRecorder,
)

# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


async def test_search_users_forwards_skip_entity(client: Any) -> None:
    """``search_users`` forwards the ``skip_entity`` flag."""

    rec = TransportRecorder(get_payload=[{"id": 1, "username": "alice"}])
    rec.install(client)
    users = await client.search_users("username==alice", skip_entity=True)
    assert len(users) == 1
    assert rec.calls[0]["skip_entity"] is True
    assert rec.calls[0]["params"]["filter"] == "username==alice"


async def test_get_user_targets_user_endpoint(client: Any) -> None:
    """``get_user`` hits the per-id endpoint."""

    rec = TransportRecorder(get_payload={"id": 5, "username": "alice"})
    rec.install(client)
    user = await client.get_user(5)
    assert user.id == 5
    assert rec.calls[0]["endpoint"] == "Administration/User/5"


async def test_update_user_sends_patch(client: Any) -> None:
    """``update_user`` issues PATCH against the user endpoint."""

    rec = TransportRecorder()
    rec.install(client)
    await client.update_user(5, PatchUser(firstname="Alice"))
    assert rec.calls[0]["method"] == "PATCH"
    assert rec.calls[0]["endpoint"] == "Administration/User/5"


async def test_create_user_serialises_post_body(client: Any) -> None:
    """``create_user`` serialises the ``PostUser`` model into the POST body."""

    rec = TransportRecorder()
    rec.install(client)
    user_id = await client.create_user(PostUser(username="alice"))
    assert user_id == 999
    assert rec.calls == [
        {
            "method": "POST",
            "endpoint": "Administration/User",
            "json": {"username": "alice"},
            "skip_entity": False,
        }
    ]


async def test_delete_user_supports_force_flag(client: Any) -> None:
    """``delete_user`` forwards the ``force`` flag inside the JSON body."""

    rec = TransportRecorder()
    rec.install(client)
    await client.delete_user(5, force=True)
    call = rec.calls[0]
    assert call["method"] == "DELETE"
    assert call["endpoint"] == "Administration/User/5"
    assert call["json"] == {"force": True}


# ---------------------------------------------------------------------------
# Generic error handling (this mixin's share of the shared failure suites)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_user(1),
    ],
)
async def test_get_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every read helper raises on a non-success status."""

    FailingTransportRecorder(404).install(client)
    with pytest.raises(ValueError):
        await call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.update_user(1, PatchUser(firstname="x")),
    ],
)
async def test_update_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every update helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        await call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.delete_user(1, force=True),
    ],
)
async def test_delete_helpers_raise_on_failure_status(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Every delete helper raises on a non-success status."""

    FailingTransportRecorder(500).install(client)
    with pytest.raises(ValueError):
        await call(client)


# ---------------------------------------------------------------------------
# iter_search_users
# ---------------------------------------------------------------------------


async def test_iter_search_users_single_page(client: Any) -> None:
    """A response shorter than batch_size yields one batch then stops."""

    call_count = 0

    async def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        skip_entity: bool = False,
    ) -> list[Any]:
        nonlocal call_count
        call_count += 1
        return [{"id": 1, "username": "alice"}]

    client.search_users = fake_search  # type: ignore[method-assign]
    batches = [
        b async for b in client.iter_search_users("username==alice", batch_size=50)
    ]
    assert call_count == 1
    assert len(batches) == 1


async def test_iter_search_users_multi_page_stops_on_short_batch(
    client: Any,
) -> None:
    """Iteration stops after the first short user batch."""

    responses = [
        [{"id": 1, "username": "alice"}, {"id": 2, "username": "bob"}],
        [{"id": 3, "username": "carol"}],
    ]
    call_count = 0

    async def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        skip_entity: bool = False,
    ) -> list[Any]:
        nonlocal call_count
        result = responses[min(call_count, len(responses) - 1)]
        call_count += 1
        return result

    client.search_users = fake_search  # type: ignore[method-assign]
    batches = [batch async for batch in client.iter_search_users("", batch_size=2)]
    assert call_count == 2
    assert sum(len(b) for b in batches) == 3


async def test_find_user_by_email_matches_a_nested_email_entry(client: Any) -> None:
    """The address is matched inside the ``emails`` array, not on a top field."""

    from glpi_python_client.models.api_schema.administration._user import GetUser

    async def fake_search(
        rsql_filter: str = "", *, limit: int = 50, start: int = 0, **kwargs: Any
    ) -> list[GetUser]:
        if start:
            return []
        return [
            GetUser.model_validate(
                {"id": 1, "username": "alice", "emails": [{"email": "alice@x.test"}]}
            ),
            GetUser.model_validate(
                {"id": 2, "username": "bob", "emails": [{"email": "bob@x.test"}]}
            ),
        ]

    client.search_users = fake_search  # type: ignore[method-assign]

    found = await client.find_user_by_email("bob@x.test")

    assert found is not None
    assert found.id == 2


async def test_find_user_by_email_is_case_insensitive(client: Any) -> None:
    """Addresses are compared case-insensitively, as mail systems treat them."""

    from glpi_python_client.models.api_schema.administration._user import GetUser

    async def fake_search(
        rsql_filter: str = "", *, limit: int = 50, start: int = 0, **kwargs: Any
    ) -> list[GetUser]:
        if start:
            return []
        return [
            GetUser.model_validate(
                {"id": 1, "username": "alice", "emails": [{"email": "Alice@X.test"}]}
            )
        ]

    client.search_users = fake_search  # type: ignore[method-assign]

    found = await client.find_user_by_email("  ALICE@x.TEST ")

    assert found is not None
    assert found.id == 1


async def test_find_user_by_email_returns_none_when_absent(client: Any) -> None:
    """No match is ``None`` rather than an arbitrary first user."""

    from glpi_python_client.models.api_schema.administration._user import GetUser

    async def fake_search(
        rsql_filter: str = "", *, limit: int = 50, start: int = 0, **kwargs: Any
    ) -> list[GetUser]:
        if start:
            return []
        return [
            GetUser.model_validate(
                {"id": 1, "username": "alice", "emails": [{"email": "alice@x.test"}]}
            )
        ]

    client.search_users = fake_search  # type: ignore[method-assign]

    assert await client.find_user_by_email("nobody@x.test") is None


async def test_find_user_by_email_scans_past_the_first_page(client: Any) -> None:
    """The match may live on any page, so the scan pages until it finds one."""

    from glpi_python_client.models.api_schema.administration._user import GetUser

    pages = [
        [GetUser.model_validate({"id": i, "username": f"u{i}"}) for i in range(1, 3)],
        [
            GetUser.model_validate(
                {"id": 9, "username": "zoe", "emails": [{"email": "zoe@x.test"}]}
            ),
        ],
    ]

    async def fake_search(
        rsql_filter: str = "", *, limit: int = 50, start: int = 0, **kwargs: Any
    ) -> list[GetUser]:
        index = start // limit
        return pages[index] if index < len(pages) else []

    client.search_users = fake_search  # type: ignore[method-assign]

    found = await client.find_user_by_email("zoe@x.test", batch_size=2)

    assert found is not None
    assert found.id == 9


async def test_find_user_by_email_stops_at_the_matching_page(client: Any) -> None:
    """The scan stops as soon as it matches instead of walking the directory."""

    from glpi_python_client.models.api_schema.administration._user import GetUser

    starts: list[int] = []

    async def fake_search(
        rsql_filter: str = "", *, limit: int = 50, start: int = 0, **kwargs: Any
    ) -> list[GetUser]:
        starts.append(start)
        return [
            GetUser.model_validate(
                {"id": 1, "username": "alice", "emails": [{"email": "alice@x.test"}]}
            )
        ] * limit

    client.search_users = fake_search  # type: ignore[method-assign]

    await client.find_user_by_email("alice@x.test", batch_size=2)

    assert starts == [0]


async def test_find_user_by_email_scans_every_entity_by_default(client: Any) -> None:
    """The scan spans entities, or a match outside the header scope is missed."""

    from glpi_python_client.models.api_schema.administration._user import GetUser

    seen: dict[str, Any] = {}

    async def fake_search(
        rsql_filter: str = "", *, limit: int = 50, start: int = 0, **kwargs: Any
    ) -> list[GetUser]:
        seen.update(kwargs)
        seen["filter"] = rsql_filter
        return []

    client.search_users = fake_search  # type: ignore[method-assign]

    await client.find_user_by_email("alice@x.test", rsql_filter="is_active==true")

    assert seen["skip_entity"] is True
    assert seen["filter"] == "is_active==true"


async def test_find_user_by_email_rejects_a_blank_address(client: Any) -> None:
    """A blank address would scan the whole directory and match nothing."""

    from glpi_python_client import GlpiValidationError

    with pytest.raises(GlpiValidationError):
        await client.find_user_by_email("   ")
