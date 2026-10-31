"""Unit tests for the ``Administration/User`` endpoint mixin.

The tests cover search, fetch, create, update, delete, and page-by-page
iteration for GLPI users, using the shared transport recorders to stub
the four transport helpers without any HTTP plumbing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from glpi_python_client import (
    GlpiProtocolError,
    GlpiValidationError,
    PatchUser,
    PostUser,
)
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


class _FakeV1:
    """Stand-in for the v1 session that records ``request_json`` calls."""

    def __init__(self, *responses: object) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, object] | None = None,
        json_body: dict[str, object] | None = None,
        success_statuses: tuple[int, ...] = (200, 201, 204, 206),
        failure_message: str | None = None,
    ) -> object:
        self.calls.append(
            {
                "method": method,
                "path": path,
                "params": params,
                "json_body": json_body,
                "failure_message": failure_message,
            }
        )
        return self.responses.pop(0)

    async def close(self) -> None:
        """No-op; the real session is closed with the client."""


_ROW = {
    "id": 5,
    "users_id": 2568,
    "profiles_id": 1,
    "entities_id": 0,
    "is_recursive": 0,
    "is_dynamic": 0,
    "is_default_profile": 1,
}


async def test_list_user_authorizations_parses_v1_rows(client: Any) -> None:
    """Rows of ``GET User/<id>/Profile_User`` become ``UserAuthorization``."""

    fake = _FakeV1([_ROW, {**_ROW, "id": 6, "entities_id": 493, "is_recursive": 1}])
    client._v1 = fake
    rows = await client.list_user_authorizations(2568)
    assert fake.calls[0]["method"] == "GET"
    assert fake.calls[0]["path"] == "User/2568/Profile_User"
    assert fake.calls[0]["params"] == {"range": "0-999"}
    assert [(r.id, r.user_id, r.profile_id, r.entity_id) for r in rows] == [
        (5, 2568, 1, 0),
        (6, 2568, 1, 493),
    ]
    assert [r.is_recursive for r in rows] == [False, True]
    assert rows[0].is_default_profile is True
    assert rows[0].is_dynamic is False


async def test_list_user_authorizations_ignores_a_non_list_answer(
    client: Any,
) -> None:
    """An empty body yields an empty list."""

    client._v1 = _FakeV1({})
    assert await client.list_user_authorizations(1) == []


async def test_add_user_authorization_posts_the_row(client: Any) -> None:
    """``add_user_authorization`` posts a Profile_User row and returns its id."""

    fake = _FakeV1({"id": 31, "message": ""})
    client._v1 = fake
    new_id = await client.add_user_authorization(
        2568, profile_id=1, entity_id=492, recursive=True
    )
    assert new_id == 31
    call = fake.calls[0]
    assert call["method"] == "POST"
    assert call["path"] == "Profile_User"
    assert call["json_body"] == {
        "input": {
            "users_id": 2568,
            "profiles_id": 1,
            "entities_id": 492,
            "is_recursive": 1,
        }
    }


async def test_add_user_authorization_defaults_to_non_recursive(client: Any) -> None:
    """``recursive`` defaults to ``False``."""

    fake = _FakeV1({"id": "32"})
    client._v1 = fake
    assert await client.add_user_authorization(1, profile_id=2, entity_id=3) == 32
    assert fake.calls[0]["json_body"]["input"]["is_recursive"] == 0


@pytest.mark.parametrize(
    "answer", [{"message": "x"}, [], {"id": True}, {"id": "abc"}, None]
)
async def test_add_user_authorization_requires_an_id(
    client: Any, answer: object
) -> None:
    """A success answer without a usable id raises a protocol error."""

    client._v1 = _FakeV1(answer)
    with pytest.raises(GlpiProtocolError):
        await client.add_user_authorization(1, profile_id=2, entity_id=3)


async def test_update_user_authorization_sends_only_given_fields(
    client: Any,
) -> None:
    """Only the supplied fields travel in the PUT body."""

    fake = _FakeV1([{"5": True, "message": ""}], [{"5": True, "message": ""}])
    client._v1 = fake
    await client.update_user_authorization(5, entity_id=493)
    await client.update_user_authorization("5", recursive=False)
    assert fake.calls[0]["method"] == "PUT"
    assert fake.calls[0]["path"] == "Profile_User/5"
    assert fake.calls[0]["json_body"] == {"input": {"id": 5, "entities_id": 493}}
    assert fake.calls[1]["json_body"] == {"input": {"id": 5, "is_recursive": 0}}


async def test_update_user_authorization_needs_a_change(client: Any) -> None:
    """With neither argument the call fails before any request."""

    fake = _FakeV1()
    client._v1 = fake
    with pytest.raises(GlpiValidationError):
        await client.update_user_authorization(5)
    assert fake.calls == []


async def test_update_user_authorization_raises_on_a_refused_answer(
    client: Any,
) -> None:
    """A ``false`` answer raises with the server message."""

    client._v1 = _FakeV1([{"5": False, "message": "Not allowed"}])
    with pytest.raises(GlpiProtocolError, match="Not allowed"):
        await client.update_user_authorization(5, recursive=True)


async def test_delete_user_authorization_sends_delete(client: Any) -> None:
    """``delete_user_authorization`` deletes the Profile_User row."""

    fake = _FakeV1([{"5": True, "message": ""}])
    client._v1 = fake
    await client.delete_user_authorization(5)
    assert fake.calls[0]["method"] == "DELETE"
    assert fake.calls[0]["path"] == "Profile_User/5"


async def test_delete_user_authorization_raises_on_a_refused_answer(
    client: Any,
) -> None:
    """A ``false`` answer raises on delete too."""

    client._v1 = _FakeV1([{"5": False, "message": ""}])
    with pytest.raises(GlpiProtocolError, match="refused"):
        await client.delete_user_authorization(5)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.list_user_authorizations(1),
        lambda c: c.add_user_authorization(1, profile_id=2, entity_id=3),
        lambda c: c.update_user_authorization(1, recursive=True),
        lambda c: c.delete_user_authorization(1),
    ],
)
async def test_authorization_methods_require_the_v1_session(
    client: Any, call: Callable[[Any], Any]
) -> None:
    """Without a v1 session each method raises the configuration error."""

    with pytest.raises(RuntimeError, match="user authorizations"):
        await call(client)
