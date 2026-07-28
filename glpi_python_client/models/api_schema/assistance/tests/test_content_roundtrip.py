"""Tests for transparent Markdown <-> HTML transport on content fields.

The package contract is that every ``content`` field accepts and returns
canonical Markdown while GLPI continues to receive HTML over the wire.
These tests cover both directions on every model that exposes a Markdown
content field, plus the inert behaviours (``None``, plain text round trip)
that keep ``exclude_none`` semantics and non-HTML payloads stable.
"""

from __future__ import annotations

import pytest

from glpi_python_client._sync.clients.commons._payloads import model_to_payload
from glpi_python_client.models.api_schema.assistance import (
    GetTicket,
    PatchTicket,
    PostTicket,
)
from glpi_python_client.models.api_schema.assistance.timeline import (
    GetFollowup,
    GetSolution,
    GetTicketTask,
    PostFollowup,
    PostSolution,
    PostTicketTask,
)


@pytest.mark.parametrize(
    "model_cls",
    [PostTicket, PatchTicket, PostFollowup, PostSolution, PostTicketTask],
)
def test_outgoing_markdown_is_rendered_to_html(model_cls: type) -> None:
    """Markdown supplied by callers becomes HTML in the request payload."""

    instance = model_cls(content="The printer is **offline**.")

    payload = model_to_payload(instance)

    assert payload["content"] == "<p>The printer is <strong>offline</strong>.</p>"


@pytest.mark.parametrize(
    "model_cls",
    [PostTicket, PatchTicket, PostFollowup, PostSolution, PostTicketTask],
)
def test_outgoing_none_content_is_dropped_from_payload(
    model_cls: type,
) -> None:
    """``None`` content stays ``None`` so ``exclude_none`` removes it."""

    instance = model_cls()

    payload = model_to_payload(instance)

    assert "content" not in payload


@pytest.mark.parametrize(
    "model_cls",
    [GetTicket, GetFollowup, GetSolution, GetTicketTask],
)
def test_incoming_html_is_normalised_to_markdown(model_cls: type) -> None:
    """HTML returned by GLPI is normalised to Markdown on attribute access."""

    instance = model_cls.model_validate(
        {"content": "<p>The printer is <strong>offline</strong>.</p>"}
    )

    assert instance.content == "The printer is **offline**."


@pytest.mark.parametrize(
    "model_cls",
    [GetTicket, GetFollowup, GetSolution, GetTicketTask],
)
def test_incoming_plain_text_passes_through(model_cls: type) -> None:
    """Plain-text content (no HTML tags) is preserved verbatim."""

    instance = model_cls.model_validate({"content": "Plain text body"})

    assert instance.content == "Plain text body"


def test_round_trip_preserves_markdown_intent() -> None:
    """Markdown in -> HTML on the wire -> Markdown back on read."""

    outgoing = PostTicket(name="Round trip", content="A **bold** statement.")
    payload = model_to_payload(outgoing)

    incoming = GetTicket.model_validate({"name": "Round trip", **payload})

    assert incoming.content == "A **bold** statement."


def test_outgoing_empty_string_renders_empty() -> None:
    """Empty Markdown serialises to an empty string, not to ``<p></p>``."""

    payload = model_to_payload(PostTicket(content=""))

    assert payload["content"] == ""
