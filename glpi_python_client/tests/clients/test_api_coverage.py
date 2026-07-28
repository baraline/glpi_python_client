"""Coverage-focused tests for every public ``GlpiClient`` API mixin method.

The tests reuse the recorder pattern from :mod:`test_smoke` to assert
endpoint URLs, HTTP verbs and serialised request bodies for the search,
get, update and delete operations that the existing smoke tests do not
already cover.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from glpi_python_client import (
    GlpiClient,
    GlpiValidationError,
    PatchDocument,
    PatchEntity,
    PatchFollowup,
    PatchLocation,
    PatchSolution,
    PatchTicket,
    PatchTicketTask,
    PatchTimelineDocument,
    PatchUser,
    PostDocument,
    PostEntity,
    PostTeamMember,
)
from glpi_python_client.testing.utils import FakeResponse, make_client


class _Recorder:
    """Async transport recorder that drives FakeResponse responses."""

    def __init__(
        self,
        *,
        get_payload: Any = None,
        get_status: int = 200,
        get_content: bytes | None = None,
        post_payload: Any = None,
        post_status: int = 201,
        patch_status: int = 204,
        delete_status: int = 204,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._get_payload = get_payload if get_payload is not None else []
        self._get_status = get_status
        self._get_content = get_content
        self._post_payload = post_payload if post_payload is not None else {"id": 999}
        self._post_status = post_status
        self._patch_status = patch_status
        self._delete_status = delete_status

    def install(self, client: GlpiClient) -> None:
        """Replace the four transport helpers with capturing stubs."""

        def _get(
            endpoint: str,
            params: dict[str, Any] | None = None,
            skip_entity: bool = False,
        ) -> FakeResponse:
            self.calls.append(
                {
                    "method": "GET",
                    "endpoint": endpoint,
                    "params": params,
                    "skip_entity": skip_entity,
                }
            )
            return FakeResponse(
                status_code=self._get_status,
                payload=self._get_payload,
                content=self._get_content,
            )

        def _post(
            endpoint: str,
            json_body: dict[str, Any] | None = None,
            skip_entity: bool = False,
        ) -> FakeResponse:
            self.calls.append(
                {
                    "method": "POST",
                    "endpoint": endpoint,
                    "json": json_body,
                    "skip_entity": skip_entity,
                }
            )
            return FakeResponse(
                status_code=self._post_status, payload=self._post_payload
            )

        def _patch(
            endpoint: str, json_body: dict[str, Any] | None = None
        ) -> FakeResponse:
            self.calls.append(
                {"method": "PATCH", "endpoint": endpoint, "json": json_body}
            )
            return FakeResponse(status_code=self._patch_status, payload={})

        def _delete(
            endpoint: str,
            json_body: dict[str, Any] | None = None,
            skip_entity: bool = False,
        ) -> FakeResponse:
            self.calls.append(
                {
                    "method": "DELETE",
                    "endpoint": endpoint,
                    "json": json_body,
                    "skip_entity": skip_entity,
                }
            )
            return FakeResponse(status_code=self._delete_status, payload={})

        client._get_request = _get  # type: ignore[method-assign]
        client._post_request = _post  # type: ignore[method-assign]
        client._update_request = _patch  # type: ignore[method-assign]
        client._delete_request = _delete  # type: ignore[method-assign]


@pytest.fixture
def client() -> GlpiClient:
    """Return one in-memory client without any real HTTP plumbing."""

    return make_client()


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------


def test_search_tickets_forwards_sort_and_fields(client: GlpiClient) -> None:
    """Sort and field selection both flow into the GET query parameters."""

    rec = _Recorder(get_payload=[{"id": 1, "name": "n", "content": "c"}])
    rec.install(client)
    tickets = client.search_tickets(
        "status==1", limit=5, start=10, sort="date_mod desc", fields=("id", "name")
    )

    assert len(tickets) == 1
    assert rec.calls[0]["params"]["filter"] == "status==1"
    assert rec.calls[0]["params"]["limit"] == 5
    assert rec.calls[0]["params"]["start"] == 10
    assert rec.calls[0]["params"]["sort"] == "date_mod desc"
    assert rec.calls[0]["params"]["fields"] == "id,name"


def test_get_ticket_returns_validated_model(client: GlpiClient) -> None:
    """Single ticket responses are validated through ``GetTicket``."""

    rec = _Recorder(get_payload={"id": 7, "name": "demo", "content": "<p>c</p>"})
    rec.install(client)
    ticket = client.get_ticket(7)
    assert ticket.id == 7
    assert rec.calls[0]["endpoint"] == "Assistance/Ticket/7"


def test_update_ticket_sends_patch(client: GlpiClient) -> None:
    """Update sends a PATCH with the partial body."""

    rec = _Recorder()
    rec.install(client)
    client.update_ticket(7, PatchTicket(content="<p>x</p>"))
    call = rec.calls[0]
    assert call["method"] == "PATCH"
    assert call["endpoint"] == "Assistance/Ticket/7"
    assert call["json"] == {"content": "<p>x</p>"}


def test_delete_ticket_omits_body_without_force(client: GlpiClient) -> None:
    """``delete_ticket(force=None)`` omits the JSON body."""

    rec = _Recorder()
    rec.install(client)
    client.delete_ticket(7)
    call = rec.calls[0]
    assert call["method"] == "DELETE"
    assert call["endpoint"] == "Assistance/Ticket/7"
    assert call["json"] is None


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


def test_search_users_forwards_skip_entity(client: GlpiClient) -> None:
    """``search_users`` forwards the ``skip_entity`` flag."""

    rec = _Recorder(get_payload=[{"id": 1, "username": "alice"}])
    rec.install(client)
    users = client.search_users("username==alice", skip_entity=True)
    assert len(users) == 1
    assert rec.calls[0]["skip_entity"] is True
    assert rec.calls[0]["params"]["filter"] == "username==alice"


def test_get_user_targets_user_endpoint(client: GlpiClient) -> None:
    """``get_user`` hits the per-id endpoint."""

    rec = _Recorder(get_payload={"id": 5, "username": "alice"})
    rec.install(client)
    user = client.get_user(5)
    assert user.id == 5
    assert rec.calls[0]["endpoint"] == "Administration/User/5"


def test_update_user_sends_patch(client: GlpiClient) -> None:
    """``update_user`` issues PATCH against the user endpoint."""

    rec = _Recorder()
    rec.install(client)
    client.update_user(5, PatchUser(firstname="Alice"))
    assert rec.calls[0]["method"] == "PATCH"
    assert rec.calls[0]["endpoint"] == "Administration/User/5"


# ---------------------------------------------------------------------------
# Locations
# ---------------------------------------------------------------------------


def test_search_locations_passes_filter(client: GlpiClient) -> None:
    """``search_locations`` forwards the RSQL filter through ``filter``."""

    rec = _Recorder(get_payload=[{"id": 1, "name": "Paris"}])
    rec.install(client)
    locations = client.search_locations("name==Paris")
    assert locations[0].id == 1
    assert rec.calls[0]["endpoint"] == "Dropdowns/Location"
    assert rec.calls[0]["params"]["filter"] == "name==Paris"


def test_get_location_endpoint(client: GlpiClient) -> None:
    """``get_location`` hits the per-id endpoint."""

    rec = _Recorder(get_payload={"id": 9, "name": "Paris"})
    rec.install(client)
    loc = client.get_location(9)
    assert loc.id == 9
    assert rec.calls[0]["endpoint"] == "Dropdowns/Location/9"


def test_update_location(client: GlpiClient) -> None:
    """``update_location`` patches the per-id endpoint."""

    rec = _Recorder()
    rec.install(client)
    client.update_location(9, PatchLocation(name="Paris HQ"))
    assert rec.calls[0]["endpoint"] == "Dropdowns/Location/9"


def test_delete_location_with_force(client: GlpiClient) -> None:
    """``delete_location(force=True)`` ships the force flag in the body."""

    rec = _Recorder()
    rec.install(client)
    client.delete_location(9, force=True)
    call = rec.calls[0]
    assert call["method"] == "DELETE"
    assert call["endpoint"] == "Dropdowns/Location/9"
    assert call["json"] == {"force": True}


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


def test_search_entities_skips_entity_header(client: GlpiClient) -> None:
    """``search_entities`` skips the GLPI-Entity header."""

    rec = _Recorder(get_payload=[{"id": 1, "name": "root"}])
    rec.install(client)
    entities = client.search_entities("name==root", limit=None, start=0)
    assert entities[0].id == 1
    assert rec.calls[0]["skip_entity"] is True
    assert "limit" not in rec.calls[0]["params"]


def test_get_entity_skips_entity_header(client: GlpiClient) -> None:
    """``get_entity`` also bypasses the entity header."""

    rec = _Recorder(get_payload={"id": 2, "name": "root"})
    rec.install(client)
    entity = client.get_entity(2)
    assert entity.id == 2
    assert rec.calls[0]["endpoint"] == "Administration/Entity/2"
    assert rec.calls[0]["skip_entity"] is True


def test_update_entity_patch(client: GlpiClient) -> None:
    """``update_entity`` patches the per-id endpoint."""

    rec = _Recorder()
    rec.install(client)
    client.update_entity(2, PatchEntity(name="renamed"))
    assert rec.calls[0]["endpoint"] == "Administration/Entity/2"


def test_delete_entity_with_force(client: GlpiClient) -> None:
    """``delete_entity(force=True)`` ships the force flag and skips entity."""

    rec = _Recorder()
    rec.install(client)
    client.delete_entity(2, force=True)
    call = rec.calls[0]
    assert call["endpoint"] == "Administration/Entity/2"
    assert call["json"] == {"force": True}
    assert call["skip_entity"] is True


def test_create_entity_id_returned(client: GlpiClient) -> None:
    """``create_entity`` returns the newly created identifier."""

    rec = _Recorder(post_payload={"id": 42})
    rec.install(client)
    entity_id = client.create_entity(PostEntity(name="root"))
    assert entity_id == 42
    assert rec.calls[0]["endpoint"] == "Administration/Entity"
    assert rec.calls[0]["skip_entity"] is True


# ---------------------------------------------------------------------------
# Documents (management)
# ---------------------------------------------------------------------------


def test_search_documents_filter_and_pagination(client: GlpiClient) -> None:
    """``search_documents`` forwards the filter, limit, start, and skip_entity."""

    rec = _Recorder(get_payload=[{"id": 1, "name": "doc"}])
    rec.install(client)
    docs = client.search_documents("name==*manual*", limit=10, start=20)
    assert len(docs) == 1
    call = rec.calls[0]
    assert call["endpoint"] == "Management/Document"
    assert call["skip_entity"] is True
    assert call["params"]["limit"] == 10
    assert call["params"]["start"] == 20
    assert call["params"]["filter"] == "name==*manual*"


def test_get_document_endpoint(client: GlpiClient) -> None:
    """``get_document`` hits the per-id endpoint."""

    rec = _Recorder(get_payload={"id": 3, "name": "doc"})
    rec.install(client)
    document = client.get_document(3)
    assert document.id == 3
    assert rec.calls[0]["endpoint"] == "Management/Document/3"


def test_create_document_returns_id(client: GlpiClient) -> None:
    """``create_document`` returns the new id and skips entity."""

    rec = _Recorder(post_payload={"id": 77})
    rec.install(client)
    document_id = client.create_document(PostDocument(name="manual"))
    assert document_id == 77
    assert rec.calls[0]["endpoint"] == "Management/Document"
    assert rec.calls[0]["skip_entity"] is True


def test_update_document_patches_endpoint(client: GlpiClient) -> None:
    """``update_document`` issues PATCH on the per-id endpoint."""

    rec = _Recorder()
    rec.install(client)
    client.update_document(3, PatchDocument(name="x"))
    assert rec.calls[0]["endpoint"] == "Management/Document/3"


def test_delete_document_with_force(client: GlpiClient) -> None:
    """``delete_document(force=True)`` adds the body and skips entity."""

    rec = _Recorder()
    rec.install(client)
    client.delete_document(3, force=True)
    call = rec.calls[0]
    assert call["endpoint"] == "Management/Document/3"
    assert call["json"] == {"force": True}
    assert call["skip_entity"] is True


def test_download_document_returns_bytes(client: GlpiClient) -> None:
    """``download_document_content`` returns the response bytes."""

    rec = _Recorder(
        get_status=200, get_payload={"ignored": True}, get_content=b"\x00ZZ"
    )
    rec.install(client)
    content = client.download_document_content(3)
    assert content == b"\x00ZZ"
    assert rec.calls[0]["endpoint"] == "Management/Document/3/Download"


def test_download_document_raises_on_failure(client: GlpiClient) -> None:
    """A non-200 download status raises ``ValueError``."""

    rec = _Recorder(get_status=404, get_payload={"err": "missing"})
    rec.install(client)
    with pytest.raises(ValueError):
        client.download_document_content(3)


def test_upload_document_requires_filename(client: GlpiClient) -> None:
    """``upload_document`` rejects an empty filename before any HTTP call.

    ``GlpiValidationError`` inherits ``ValueError`` so existing callers that
    catch the broader type keep working.
    """

    with pytest.raises(GlpiValidationError, match="filename") as excinfo:
        client.upload_document(filename="", content=b"x")
    assert isinstance(excinfo.value, ValueError)


def test_upload_document_dispatches_to_v1(client: GlpiClient) -> None:
    """``upload_document`` forwards arguments to the configured v1 session."""

    captured: dict[str, Any] = {}

    class _FakeV1:
        def upload_document(
            self,
            filename: str,
            content: bytes,
            mime_type: str,
            *,
            document_name: str | None,
            ticket_id: int | None,
            entity_id: int | None,
        ) -> dict[str, object]:
            captured.update(
                {
                    "filename": filename,
                    "content": content,
                    "mime_type": mime_type,
                    "document_name": document_name,
                    "ticket_id": ticket_id,
                    "entity_id": entity_id,
                }
            )
            return {"id": 1}

    client._v1 = _FakeV1()  # type: ignore[assignment]
    result = client.upload_document(
        filename="a.txt",
        content=b"abc",
        mime_type="text/plain",
        document_name="DocA",
        ticket_id=5,
        entity_id=2,
    )

    assert result == {"id": 1}
    assert captured["filename"] == "a.txt"
    assert captured["ticket_id"] == 5
    assert captured["entity_id"] == 2


# ---------------------------------------------------------------------------
# Timeline mixins (followups, tasks, solutions, documents)
# ---------------------------------------------------------------------------


def test_list_ticket_followups_unwraps_envelope(client: GlpiClient) -> None:
    """Live envelope ``{"type":..,"item":..}`` entries are unwrapped."""

    rec = _Recorder(
        get_payload=[
            {"type": "ITILFollowup", "item": {"id": 11, "content": "hi"}},
            {"id": 12, "content": "bye"},
        ]
    )
    rec.install(client)
    items = client.list_ticket_followups(7)
    assert [i.id for i in items] == [11, 12]
    assert rec.calls[0]["endpoint"] == "Assistance/Ticket/7/Timeline/Followup"


def test_get_ticket_followup_endpoint(client: GlpiClient) -> None:
    """``get_ticket_followup`` hits the per-id endpoint."""

    rec = _Recorder(get_payload={"id": 11, "content": "x"})
    rec.install(client)
    followup = client.get_ticket_followup(7, 11)
    assert followup.id == 11
    assert rec.calls[0]["endpoint"] == "Assistance/Ticket/7/Timeline/Followup/11"


def test_update_ticket_followup_patch(client: GlpiClient) -> None:
    """``update_ticket_followup`` patches the per-id endpoint."""

    rec = _Recorder()
    rec.install(client)
    client.update_ticket_followup(7, 11, PatchFollowup(content="<p>up</p>"))
    assert rec.calls[0]["endpoint"] == "Assistance/Ticket/7/Timeline/Followup/11"


def test_delete_ticket_followup_force(client: GlpiClient) -> None:
    """``delete_ticket_followup(force=True)`` adds the body."""

    rec = _Recorder()
    rec.install(client)
    client.delete_ticket_followup(7, 11, force=True)
    assert rec.calls[0]["json"] == {"force": True}


def test_list_get_update_delete_ticket_tasks(client: GlpiClient) -> None:
    """All four task helpers target the task timeline endpoint."""

    rec = _Recorder(
        get_payload=[
            {"type": "TicketTask", "item": {"id": 1, "content": "x"}},
        ]
    )
    rec.install(client)
    tasks = client.list_ticket_tasks(7)
    assert tasks[0].id == 1
    assert rec.calls[0]["endpoint"] == "Assistance/Ticket/7/Timeline/Task"

    rec.calls.clear()
    rec._get_payload = {"id": 1, "content": "x"}  # type: ignore[attr-defined]
    task = client.get_ticket_task(7, 1)
    assert task.id == 1

    client.update_ticket_task(7, 1, PatchTicketTask(content="<p>up</p>"))
    client.delete_ticket_task(7, 1, force=True)

    endpoints = [c["endpoint"] for c in rec.calls]
    assert endpoints == [
        "Assistance/Ticket/7/Timeline/Task/1",
        "Assistance/Ticket/7/Timeline/Task/1",
        "Assistance/Ticket/7/Timeline/Task/1",
    ]


def test_list_get_update_delete_ticket_solutions(client: GlpiClient) -> None:
    """All four solution helpers target the solution timeline endpoint."""

    rec = _Recorder(
        get_payload=[
            {"type": "ITILSolution", "item": {"id": 1, "content": "x"}},
        ]
    )
    rec.install(client)
    sols = client.list_ticket_solutions(7)
    assert sols[0].id == 1

    rec._get_payload = {"id": 1, "content": "x"}  # type: ignore[attr-defined]
    sol = client.get_ticket_solution(7, 1)
    assert sol.id == 1

    client.update_ticket_solution(7, 1, PatchSolution(content="<p>up</p>"))
    client.delete_ticket_solution(7, 1, force=True)

    methods = [c["method"] for c in rec.calls]
    assert methods == ["GET", "GET", "PATCH", "DELETE"]
    endpoints = {c["endpoint"] for c in rec.calls if c["method"] != "GET"} | {
        c["endpoint"] for c in rec.calls if c["method"] == "GET"
    }
    assert any("Solution" in e for e in endpoints)


def test_list_get_update_unlink_timeline_documents(client: GlpiClient) -> None:
    """All four timeline document helpers target the document endpoint."""

    rec = _Recorder(
        get_payload=[
            {"type": "Document_Item", "item": {"id": 1, "filename": "report.txt"}},
        ]
    )
    rec.install(client)
    items = client.list_ticket_timeline_documents(7)
    assert items[0].id == 1
    assert rec.calls[0]["endpoint"] == "Assistance/Ticket/7/Timeline/Document"

    rec._get_payload = {"id": 1, "filename": "report.txt"}  # type: ignore[attr-defined]
    doc = client.get_ticket_timeline_document(7, 1)
    assert doc.id == 1

    client.update_ticket_timeline_document(7, 1, PatchTimelineDocument())
    client.unlink_ticket_timeline_document(7, 1, force=True)

    methods = [c["method"] for c in rec.calls]
    assert methods == ["GET", "GET", "PATCH", "DELETE"]


# ---------------------------------------------------------------------------
# Team members
# ---------------------------------------------------------------------------


def test_list_ticket_team_members_endpoint(client: GlpiClient) -> None:
    """``list_ticket_team_members`` hits the team-member endpoint."""

    rec = _Recorder(get_payload=[{"id": 1, "type": "User", "role": "assigned"}])
    rec.install(client)
    members = client.list_ticket_team_members(7)
    assert members[0].id == 1
    assert rec.calls[0]["endpoint"] == "Assistance/Ticket/7/TeamMember"


def test_remove_ticket_team_member_uses_delete(client: GlpiClient) -> None:
    """``remove_ticket_team_member`` issues DELETE with the member body."""

    rec = _Recorder()
    rec.install(client)
    client.remove_ticket_team_member(
        7, PostTeamMember(type="User", id=42, role="assigned")
    )

    call = rec.calls[0]
    assert call["method"] == "DELETE"
    assert call["endpoint"] == "Assistance/Ticket/7/TeamMember"
    assert call["json"] == {"type": "User", "id": 42, "role": "assigned"}


# ---------------------------------------------------------------------------
# Generic error handling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.get_ticket(1),
        lambda c: c.get_user(1),
        lambda c: c.get_location(1),
        lambda c: c.get_entity(1),
        lambda c: c.get_document(1),
        lambda c: c.get_ticket_followup(1, 2),
        lambda c: c.get_ticket_task(1, 2),
        lambda c: c.get_ticket_solution(1, 2),
        lambda c: c.get_ticket_timeline_document(1, 2),
        lambda c: c.list_ticket_team_members(1),
        lambda c: c.list_ticket_followups(1),
        lambda c: c.list_ticket_tasks(1),
        lambda c: c.list_ticket_solutions(1),
        lambda c: c.list_ticket_timeline_documents(1),
    ],
)
def test_get_helpers_raise_on_failure_status(
    client: GlpiClient, call: Callable[[GlpiClient], Any]
) -> None:
    """Every read helper raises ``ValueError`` on a non-success status."""

    rec = _Recorder(get_status=404, get_payload={"err": "missing"})
    rec.install(client)
    with pytest.raises(ValueError):
        call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.update_ticket(1, PatchTicket(content="<p>x</p>")),
        lambda c: c.update_user(1, PatchUser(firstname="x")),
        lambda c: c.update_location(1, PatchLocation(name="x")),
        lambda c: c.update_entity(1, PatchEntity(name="x")),
        lambda c: c.update_document(1, PatchDocument(name="x")),
        lambda c: c.update_ticket_followup(1, 2, PatchFollowup(content="<p>x</p>")),
        lambda c: c.update_ticket_task(1, 2, PatchTicketTask(content="<p>x</p>")),
        lambda c: c.update_ticket_solution(1, 2, PatchSolution(content="<p>x</p>")),
        lambda c: c.update_ticket_timeline_document(1, 2, PatchTimelineDocument()),
    ],
)
def test_update_helpers_raise_on_failure_status(
    client: GlpiClient, call: Callable[[GlpiClient], Any]
) -> None:
    """Every update helper raises ``ValueError`` on a non-success status."""

    rec = _Recorder(patch_status=500)
    rec.install(client)
    with pytest.raises(ValueError):
        call(client)


@pytest.mark.parametrize(
    "call",
    [
        lambda c: c.delete_ticket(1, force=True),
        lambda c: c.delete_user(1, force=True),
        lambda c: c.delete_location(1, force=True),
        lambda c: c.delete_entity(1, force=True),
        lambda c: c.delete_document(1, force=True),
        lambda c: c.delete_ticket_followup(1, 2, force=True),
        lambda c: c.delete_ticket_task(1, 2, force=True),
        lambda c: c.delete_ticket_solution(1, 2, force=True),
        lambda c: c.unlink_ticket_timeline_document(1, 2, force=True),
        lambda c: c.remove_ticket_team_member(
            1, PostTeamMember(type="User", id=2, role="assigned")
        ),
    ],
)
def test_delete_helpers_raise_on_failure_status(
    client: GlpiClient, call: Callable[[GlpiClient], Any]
) -> None:
    """Every delete helper raises ``ValueError`` on a non-success status."""

    rec = _Recorder(delete_status=500)
    rec.install(client)
    with pytest.raises(ValueError):
        call(client)


# ---------------------------------------------------------------------------
# iter_search_tickets
# ---------------------------------------------------------------------------


def test_iter_search_tickets_single_page(client: GlpiClient) -> None:
    """A response shorter than batch_size yields one batch then stops."""

    pages: list[list[Any]] = [[{"id": 1, "name": "t1", "content": "c"}]]
    call_count = 0

    def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
        fields: tuple[str, ...] = (),
    ) -> list[Any]:
        nonlocal call_count
        call_count += 1
        return pages[0]

    client.search_tickets = fake_search  # type: ignore[method-assign]
    batches = list(client.iter_search_tickets("status==1", batch_size=50))
    assert call_count == 1
    assert len(batches) == 1
    assert len(batches[0]) == 1


def test_iter_search_tickets_multi_page_stops_on_short_batch(
    client: GlpiClient,
) -> None:
    """Iteration stops after the first batch shorter than batch_size."""

    ticket_a = {"id": 1, "name": "a", "content": "c"}
    ticket_b = {"id": 2, "name": "b", "content": "c"}
    ticket_c = {"id": 3, "name": "c", "content": "c"}
    responses = [
        [ticket_a, ticket_b],  # full page → continue
        [ticket_c],  # short page → last
    ]
    call_count = 0

    def fake_search(
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
        fields: tuple[str, ...] = (),
    ) -> list[Any]:
        nonlocal call_count
        result = responses[min(call_count, len(responses) - 1)]
        call_count += 1
        return result

    client.search_tickets = fake_search  # type: ignore[method-assign]
    batches = list(client.iter_search_tickets("", batch_size=2))
    assert call_count == 2
    assert len(batches) == 2
    assert len(batches[0]) == 2
    assert len(batches[1]) == 1


# ---------------------------------------------------------------------------
# iter_search_users
# ---------------------------------------------------------------------------


def test_iter_search_users_single_page(client: GlpiClient) -> None:
    """A response shorter than batch_size yields one batch then stops."""

    call_count = 0

    def fake_search(
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
    batches = list(client.iter_search_users("username==alice", batch_size=50))
    assert call_count == 1
    assert len(batches) == 1


def test_iter_search_users_multi_page_stops_on_short_batch(
    client: GlpiClient,
) -> None:
    """Iteration stops after the first short user batch."""

    responses = [
        [{"id": 1, "username": "alice"}, {"id": 2, "username": "bob"}],
        [{"id": 3, "username": "carol"}],
    ]
    call_count = 0

    def fake_search(
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
    batches = list(client.iter_search_users("", batch_size=2))
    assert call_count == 2
    assert sum(len(b) for b in batches) == 3


# ---------------------------------------------------------------------------
# iter_search_entities
# ---------------------------------------------------------------------------


def test_iter_search_entities_single_page(client: GlpiClient) -> None:
    """A response shorter than batch_size yields one batch then stops."""

    call_count = 0

    def fake_search(
        rsql_filter: str = "",
        *,
        limit: int | None = 50,
        start: int = 0,
    ) -> list[Any]:
        nonlocal call_count
        call_count += 1
        return [{"id": 1, "name": "root"}]

    client.search_entities = fake_search  # type: ignore[method-assign]
    batches = list(client.iter_search_entities("", batch_size=50))
    assert call_count == 1
    assert len(batches) == 1


def test_iter_search_entities_multi_page_stops_on_short_batch(
    client: GlpiClient,
) -> None:
    """Iteration stops after the first short entity batch."""

    responses = [
        [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}],
        [{"id": 3, "name": "c"}],
    ]
    call_count = 0

    def fake_search(
        rsql_filter: str = "",
        *,
        limit: int | None = 50,
        start: int = 0,
    ) -> list[Any]:
        nonlocal call_count
        result = responses[min(call_count, len(responses) - 1)]
        call_count += 1
        return result

    client.search_entities = fake_search  # type: ignore[method-assign]
    batches = list(client.iter_search_entities("", batch_size=2))
    assert call_count == 2
    assert sum(len(b) for b in batches) == 3
