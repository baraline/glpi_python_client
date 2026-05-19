"""Integration tests targeting a live GLPI instance.

The suite exercises the synchronous :class:`GlpiClient` end-to-end
against the GLPI API. It is skipped automatically when the local
secrets used to authenticate against the live instance are missing.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest

from glpi_python_client import (
    GlpiClient,
    GlpiTicketContext,
    PostFollowup,
    PostLocation,
    PostSolution,
    PostTeamMember,
    PostTicket,
    PostTicketTask,
    PostUser,
)

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SECRETS_DIR = _REPO_ROOT / "secrets"


@dataclass(frozen=True)
class _LiveGlpiConfig:
    """Resolved live-GLPI configuration values used by the integration tests."""

    api_url: str
    client_id: str
    client_secret: str
    username: str
    password: str
    verify_ssl: bool
    entity: int | None
    profile: int | None
    entity_recursive: bool
    v1_base_url: str | None
    v1_user_token: str | None
    v1_app_token: str | None
    team_member_role: str


def _read_value(secret_name: str, *env_names: str) -> str | None:
    """Return the first non-empty value among the secret file or env names."""

    path = _SECRETS_DIR / secret_name
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value:
            return value
    for env_name in env_names:
        env_value = os.environ.get(env_name)
        if env_value:
            return env_value.strip()
    return None


def _parse_bool(value: str | None, *, default: bool) -> bool:
    """Parse a boolean string falling back to a default when unset or invalid."""

    if value is None:
        return default
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_int(value: str | None) -> int | None:
    """Parse an optional integer string returning ``None`` for empty values."""

    if value is None or not value.strip():
        return None
    return int(value)


def _load_config() -> _LiveGlpiConfig:
    """Load the live GLPI configuration, skipping the suite when incomplete."""

    api_url = _read_value("glpi_api_url", "GLPI_API_URL")
    client_id = _read_value("glpi_client_id_test", "GLPI_CLIENT_ID")
    client_secret = _read_value("glpi_client_secret_test", "GLPI_CLIENT_SECRET")
    username = _read_value("glpi_username", "GLPI_USERNAME")
    password = _read_value("glpi_password", "GLPI_PASSWORD")

    missing = [
        name
        for name, value in (
            ("glpi_api_url", api_url),
            ("glpi_client_id_test", client_id),
            ("glpi_client_secret_test", client_secret),
            ("glpi_username", username),
            ("glpi_password", password),
        )
        if value is None
    ]
    if missing:
        pytest.skip("live GLPI integration secrets missing: " + ", ".join(missing))

    assert api_url is not None
    assert client_id is not None
    assert client_secret is not None
    assert username is not None
    assert password is not None

    return _LiveGlpiConfig(
        api_url=api_url.rstrip("/"),
        client_id=client_id,
        client_secret=client_secret,
        username=username,
        password=password,
        verify_ssl=_parse_bool(
            _read_value("glpi_verify_ssl", "GLPI_VERIFY_SSL"),
            default=False,
        ),
        entity=_parse_int(_read_value("glpi_entity", "GLPI_ENTITY")),
        profile=_parse_int(_read_value("glpi_profile", "GLPI_PROFILE")),
        entity_recursive=_parse_bool(
            _read_value("glpi_entity_recursive", "GLPI_ENTITY_RECURSIVE"),
            default=False,
        ),
        v1_base_url=_read_value("glpi_api_v1_url", "GLPI_API_V1_URL"),
        v1_user_token=_read_value("glpi_api_v1_token_user", "GLPI_V1_USER_TOKEN"),
        v1_app_token=_read_value("glpi_api_v1_app_token", "GLPI_V1_APP_TOKEN"),
        team_member_role=_read_value("glpi_team_member_role", "GLPI_TEAM_MEMBER_ROLE")
        or "assigned",
    )


@pytest.fixture(scope="session")
def live_config() -> _LiveGlpiConfig:
    """Session-scoped fixture exposing the live GLPI configuration."""

    return _load_config()


@pytest.fixture
def client(
    live_config: _LiveGlpiConfig,
) -> Iterator[GlpiClient]:
    """Yield one configured sync GLPI client and close it on teardown.

    Each test gets its own client so HTTP sessions and OAuth tokens
    never leak across tests.
    """

    glpi_client = GlpiClient(
        glpi_api_url=live_config.api_url,
        client_id=live_config.client_id,
        client_secret=live_config.client_secret,
        username=live_config.username,
        password=live_config.password,
        glpi_entity=live_config.entity,
        glpi_profile=live_config.profile,
        entity_recursive=live_config.entity_recursive,
        verify_ssl=live_config.verify_ssl,
        v1_base_url=live_config.v1_base_url,
        v1_user_token=live_config.v1_user_token,
        v1_app_token=live_config.v1_app_token,
    )
    try:
        yield glpi_client
    finally:
        glpi_client.close()


def _suffix() -> str:
    """Return one short random suffix used to make test record names unique."""

    return uuid4().hex[:12]


def test_user_lifecycle(client: GlpiClient) -> None:
    """Create, fetch, list, and delete a user round-trip."""

    suffix = _suffix()
    user_id = client.create_user(
        PostUser(
            username=f"itest-user-{suffix}",
            password=f"pwd-{suffix}",
            password2=f"pwd-{suffix}",
            realname="Integration",
            firstname="Test",
        )
    )
    try:
        fetched = client.get_user(user_id)
        assert fetched.id == user_id
        listing = client.search_users(f"username=={fetched.username}")
        assert any(u.id == user_id for u in listing)
    finally:
        client.delete_user(user_id, force=True)


def test_location_lifecycle(client: GlpiClient) -> None:
    """Create, fetch, and delete one dropdown location."""

    suffix = _suffix()
    location_id = client.create_location(PostLocation(name=f"itest-loc-{suffix}"))
    try:
        fetched = client.get_location(location_id)
        assert fetched.id == location_id
    finally:
        client.delete_location(location_id, force=True)


def test_ticket_full_workflow(client: GlpiClient, live_config: _LiveGlpiConfig) -> None:
    """Create a ticket, exercise its timeline, and aggregate one context view."""

    suffix = _suffix()
    ticket_id = client.create_ticket(
        PostTicket(
            name=f"itest-ticket-{suffix}",
            content=f"<p>integration body {suffix}</p>",
        )
    )
    try:
        followup_id = client.create_ticket_followup(
            ticket_id,
            PostFollowup(content=f"<p>integration followup {suffix}</p>"),
        )
        task_id = client.create_ticket_task(
            ticket_id,
            PostTicketTask(
                content=f"<p>integration task {suffix}</p>",
                duration=900,
            ),
        )
        solution_id = client.create_ticket_solution(
            ticket_id,
            PostSolution(content=f"<p>integration solution {suffix}</p>"),
        )

        context: GlpiTicketContext = client.get_ticket_context(ticket_id)
        assert context.ticket.id == ticket_id
        assert any(f.id == followup_id for f in context.followups)
        assert any(t.id == task_id for t in context.tasks)
        assert any(s.id == solution_id for s in context.solutions)

        if live_config.username:
            users = client.search_users(f"username=={live_config.username}")
            if users:
                client.add_ticket_team_member(
                    ticket_id,
                    PostTeamMember(
                        type="User",
                        id=users[0].id,
                        role=live_config.team_member_role,
                    ),
                )
                members = client.list_ticket_team_members(ticket_id)
                assert any(m.name == users[0].username for m in members)
    finally:
        client.delete_ticket(ticket_id, force=True)


def test_from_env(
    monkeypatch: pytest.MonkeyPatch, live_config: _LiveGlpiConfig
) -> None:
    """The :meth:`GlpiClient.from_env` helper builds a working client."""

    monkeypatch.setenv("GLPI_API_URL", live_config.api_url)
    monkeypatch.setenv("GLPI_CLIENT_ID", live_config.client_id)
    monkeypatch.setenv("GLPI_CLIENT_SECRET", live_config.client_secret)
    monkeypatch.setenv("GLPI_USERNAME", live_config.username)
    monkeypatch.setenv("GLPI_PASSWORD", live_config.password)
    monkeypatch.setenv("GLPI_VERIFY_SSL", str(live_config.verify_ssl).lower())

    glpi_client = GlpiClient.from_env()
    try:
        users = glpi_client.search_users(limit=1)
        assert isinstance(users, list)
    finally:
        glpi_client.close()


def test_example_create_and_read_ticket(client: GlpiClient) -> None:
    """Example 1: create a ticket and render its context as Markdown."""

    suffix = _suffix()
    ticket_id = client.create_ticket(
        PostTicket(
            name=f"itest-example1-{suffix}",
            content=f"example one body {suffix}",
        )
    )
    try:
        context = client.get_ticket_context(ticket_id)
        rendered = context.to_markdown()
        assert f"# Ticket #{ticket_id}" in rendered
        assert f"itest-example1-{suffix}" in rendered
        assert f"example one body {suffix}" in rendered
    finally:
        client.delete_ticket(ticket_id, force=True)


def test_example_add_followup_response(client: GlpiClient) -> None:
    """Example 2: post a followup and confirm it shows up in the transcript."""

    suffix = _suffix()
    ticket_id = client.create_ticket(
        PostTicket(
            name=f"itest-example2-{suffix}",
            content=f"example two body {suffix}",
        )
    )
    try:
        followup_id = client.create_ticket_followup(
            ticket_id,
            PostFollowup(content=f"reply note {suffix}"),
        )
        context = client.get_ticket_context(ticket_id)
        rendered = context.to_markdown()
        assert "## Timeline" in rendered
        assert f"### Followup #{followup_id}" in rendered
        assert f"reply note {suffix}" in rendered
    finally:
        client.delete_ticket(ticket_id, force=True)


def test_example_add_task_with_duration(client: GlpiClient) -> None:
    """Example 3: post a task with a duration and verify the rendered output."""

    suffix = _suffix()
    ticket_id = client.create_ticket(
        PostTicket(
            name=f"itest-example3-{suffix}",
            content=f"example three body {suffix}",
        )
    )
    try:
        task_id = client.create_ticket_task(
            ticket_id,
            PostTicketTask(
                content=f"task note {suffix}",
                duration=1800,
            ),
        )
        context = client.get_ticket_context(ticket_id)
        rendered = context.to_markdown()
        assert f"### Task #{task_id}" in rendered
        assert "Duration: 1800s" in rendered
        assert f"task note {suffix}" in rendered
    finally:
        client.delete_ticket(ticket_id, force=True)


def test_example_close_ticket_with_solution(client: GlpiClient) -> None:
    """Example 4: post a solution and confirm it appears in the transcript."""

    suffix = _suffix()
    ticket_id = client.create_ticket(
        PostTicket(
            name=f"itest-example4-{suffix}",
            content=f"example four body {suffix}",
        )
    )
    try:
        solution_id = client.create_ticket_solution(
            ticket_id,
            PostSolution(content=f"resolution note {suffix}"),
        )
        context = client.get_ticket_context(ticket_id)
        rendered = context.to_markdown()
        assert f"### Solution #{solution_id}" in rendered
        assert f"resolution note {suffix}" in rendered
    finally:
        client.delete_ticket(ticket_id, force=True)


def test_example_upload_document(
    client: GlpiClient, live_config: _LiveGlpiConfig
) -> None:
    """Example 5: upload a document attached to one ticket and render it."""

    if not live_config.v1_base_url or not live_config.v1_user_token:
        pytest.skip("v1 session not configured; document upload requires v1")

    suffix = _suffix()
    ticket_id = client.create_ticket(
        PostTicket(
            name=f"itest-example5-{suffix}",
            content=f"example five body {suffix}",
        )
    )
    try:
        client.upload_document(
            filename=f"diag-{suffix}.txt",
            content=f"diagnostic payload {suffix}\n".encode(),
            mime_type="text/plain",
            ticket_id=ticket_id,
        )
        context = client.get_ticket_context(ticket_id)
        rendered = context.to_markdown()
        assert "## Documents" in rendered
        assert len(context.documents) >= 1
    finally:
        client.delete_ticket(ticket_id, force=True)


# ---------------------------------------------------------------------------
# iter_search_* generators (Change 1)
# ---------------------------------------------------------------------------


def test_iter_search_tickets_yields_batches(client: GlpiClient) -> None:
    """iter_search_tickets yields at least one list of GetTicket objects."""

    from glpi_python_client.models.api_schema.assistance._ticket import GetTicket

    items: list[GetTicket] = []
    for batch in client.iter_search_tickets("status==1", batch_size=50):
        assert isinstance(batch, list)
        for ticket in batch:
            assert ticket.id is not None
        items.extend(batch)
        break  # one batch is sufficient to validate the contract

    # An empty instance is valid; we only assert on the batch shape above.
    assert isinstance(items, list)


def test_iter_search_users_yields_batches(client: GlpiClient) -> None:
    """iter_search_users yields at least one list of GetUser objects."""

    from glpi_python_client.models.api_schema.administration._user import GetUser

    items: list[GetUser] = []
    for batch in client.iter_search_users("", batch_size=50):
        assert isinstance(batch, list)
        for user in batch:
            assert user.id is not None
        items.extend(batch)
        break

    assert isinstance(items, list)


def test_iter_search_entities_yields_batches(client: GlpiClient) -> None:
    """iter_search_entities yields at least one list of GetEntity objects."""

    from glpi_python_client.models.api_schema.administration._entity import GetEntity

    items: list[GetEntity] = []
    for batch in client.iter_search_entities("", batch_size=50):
        assert isinstance(batch, list)
        for entity in batch:
            assert entity.id is not None
        items.extend(batch)
        break

    assert isinstance(items, list)


def test_iter_search_tickets_multi_page(client: GlpiClient) -> None:
    """iter_search_tickets paginates correctly when batch_size forces multiple pages.

    Uses a small batch size (3) so that any instance with more than
    three tickets exercises the multi-page code path.
    """

    from glpi_python_client.models.api_schema.assistance._ticket import GetTicket

    collected: list[GetTicket] = []
    for batch in client.iter_search_tickets("status==1", batch_size=3):
        assert isinstance(batch, list)
        assert len(batch) <= 3
        collected.extend(batch)

    assert isinstance(collected, list)


# ---------------------------------------------------------------------------
# get_ticket_statistics with new parameters (Change 2)
# ---------------------------------------------------------------------------


def test_get_ticket_statistics_returns_expected_shape(client: GlpiClient) -> None:
    """get_ticket_statistics returns a dict with the right top-level structure."""

    result = client.get_ticket_statistics(default_days=1)
    assert "entities" in result
    for entity_data in result["entities"].values():  # type: ignore[union-attr]
        assert "total" in entity_data
        assert "by_status" in entity_data
        assert "by_priority" in entity_data
        assert "by_type" in entity_data


def test_get_ticket_statistics_entity_id_filter(
    client: GlpiClient, live_config: _LiveGlpiConfig
) -> None:
    """Filtering by entity_id limits the result to that entity."""

    if live_config.entity is None:
        pytest.skip("no entity configured in live secrets")

    result = client.get_ticket_statistics(
        default_days=90,
        entity_id=live_config.entity,
    )
    assert "entities" in result
    # All buckets must be for the requested entity.
    entity_key = str(live_config.entity)
    for key in result["entities"]:  # type: ignore[union-attr]
        assert key == entity_key, f"unexpected entity key {key!r}"


def test_get_ticket_statistics_extra_filter_live(client: GlpiClient) -> None:
    """extra_filter RSQL fragment is accepted without raising."""

    result = client.get_ticket_statistics(
        default_days=30,
        extra_filter="status==1",
    )
    assert "entities" in result


# ---------------------------------------------------------------------------
# get_task_durations (Change 3)
# ---------------------------------------------------------------------------


def test_get_task_durations_returns_expected_shape(client: GlpiClient) -> None:
    """get_task_durations always returns a mapping with the documented keys."""

    result = client.get_task_durations(default_days=1)
    for key in (
        "start_date",
        "end_date",
        "total_duration",
        "task_count",
        "duration_by_user",
        "duration_by_entity",
        "tasks",
    ):
        assert key in result, f"missing key {key!r}"
    assert result["tasks"] is None  # return_task_details defaults to False


def test_get_task_durations_captures_created_task(client: GlpiClient) -> None:
    """A task created today appears in get_task_durations with the correct duration."""

    suffix = _suffix()
    ticket_id = client.create_ticket(
        PostTicket(
            name=f"itest-taskdur-{suffix}",
            content=f"task duration integration test {suffix}",
        )
    )
    try:
        client.create_ticket_task(
            ticket_id,
            PostTicketTask(content=f"task {suffix}", duration=600),
        )
        result = client.get_task_durations(default_days=1)
        assert isinstance(result["total_duration"], int)
        assert isinstance(result["task_count"], int)
        assert int(result["total_duration"]) >= 600
        assert int(result["task_count"]) >= 1
    finally:
        client.delete_ticket(ticket_id, force=True)


def test_get_task_durations_with_details(client: GlpiClient) -> None:
    """When return_task_details=True the tasks key holds a list."""

    suffix = _suffix()
    ticket_id = client.create_ticket(
        PostTicket(
            name=f"itest-taskdet-{suffix}",
            content=f"task details integration test {suffix}",
        )
    )
    try:
        client.create_ticket_task(
            ticket_id,
            PostTicketTask(content=f"detail task {suffix}", duration=300),
        )
        result = client.get_task_durations(
            default_days=1,
            return_task_details=True,
        )
        assert isinstance(result["tasks"], list)
        if result["tasks"]:
            task = result["tasks"][0]
            assert "task_id" in task
            assert "ticket_id" in task
            assert "duration" in task
    finally:
        client.delete_ticket(ticket_id, force=True)


# ---------------------------------------------------------------------------
# get_user_activity (Change 4)
# ---------------------------------------------------------------------------


def test_get_user_activity_shape(
    client: GlpiClient, live_config: _LiveGlpiConfig
) -> None:
    """get_user_activity returns the documented structure for the live user."""

    try:
        result = client.get_user_activity(
            username=live_config.username,
            default_days=90,
        )
    except ValueError:
        pytest.skip("live username not found in GLPI user directory")
        return

    assert "users" in result
    for _key, data in result["users"].items():  # type: ignore[union-attr]
        assert "user_ids" in data
        assert "tickets_as_technician" in data
        assert "tickets_as_recipient" in data
        assert "task_durations" in data
        assert isinstance(data["user_ids"], list)
        assert isinstance(data["tickets_as_technician"], int)
        assert isinstance(data["tickets_as_recipient"], int)
        td = data["task_durations"]
        assert "total_duration" in td
        assert "task_count" in td


def test_get_user_activity_raises_without_identifier(client: GlpiClient) -> None:
    """Calling get_user_activity without any identifier raises ValueError."""

    import pytest as _pytest

    with _pytest.raises(ValueError, match="user_id"):
        client.get_user_activity()
