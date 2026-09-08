"""Unit tests for :mod:`glpi_python_client.models.api_schema._content`.

The annotated types and the ``markdown_view`` helper had no unit tests of
their own -- their behaviour was covered incidentally by the model suites,
which left the ``None`` paths on both directions executed by nothing at
all. Those paths are what keeps ``exclude_none`` working, so they are the
ones worth pinning explicitly.

The wider read/write contract lives in
``glpi_python_client/testing/tests/test_content_roundtrip.py``; this module
is only the helpers.
"""

from __future__ import annotations

from glpi_python_client._sync.clients.commons._payloads import model_to_payload
from glpi_python_client.models.api_schema._content import (
    _from_transport,
    _to_transport,
    markdown_view,
)
from glpi_python_client.models.api_schema.assistance import GetTicket, PostTicket


def test_markdown_view_passes_none_through() -> None:
    """A slot GLPI never sent reads back as ``None``, not as ``""``.

    The distinction matters on the way back out: an empty string is a
    caller asking to clear the body, and ``None`` is a caller not
    mentioning it.
    """

    assert markdown_view(None) is None


def test_markdown_view_converts_a_raw_value() -> None:
    """The body of every read model's content property, in one line."""

    assert markdown_view("<p>The printer is <strong>offline</strong>.</p>") == (
        "The printer is **offline**."
    )


def test_the_inbound_validator_passes_none_through() -> None:
    """An explicit ``content=None`` on a write model stays ``None``.

    Reached only by naming the field, since an unset field never runs the
    validator -- which is why nothing exercised it before.
    """

    assert _from_transport(None) is None
    assert PostTicket(content=None).content is None


def test_the_outbound_serialiser_passes_none_through() -> None:
    """``None`` has to survive serialisation for ``exclude_none`` to work.

    ``model_to_payload`` dumps with ``exclude_none=True``, so a rendered
    empty string here would put an empty body in the request instead of
    leaving the field out.
    """

    assert _to_transport(None) is None
    assert "content" not in model_to_payload(PostTicket(content=None))


def test_a_read_model_reads_none_when_glpi_sent_no_body() -> None:
    """The read side of the same tri-state, through the real model."""

    ticket = GetTicket.model_validate({"id": 1})

    assert ticket.content_html is None
    assert ticket.content is None
