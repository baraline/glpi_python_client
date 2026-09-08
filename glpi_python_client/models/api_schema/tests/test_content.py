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

import pytest
from pydantic_core import PydanticSerializationError

from glpi_python_client import GlpiContentError, GlpiError, GlpiValidationError
from glpi_python_client._sync._testing import TransportRecorder, make_client
from glpi_python_client._sync.clients.commons._payloads import model_to_payload
from glpi_python_client.models.api_schema._content import (
    _from_transport,
    _to_transport,
    markdown_view,
    restoring_content_faults,
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


def test_a_content_fault_on_the_write_path_stays_in_the_taxonomy() -> None:
    """pydantic-core destroys a serializer's exception; this puts it back.

    Outbound conversion runs in a ``PlainSerializer``, and everything it
    raises comes back out as ``PydanticSerializationError`` -- a
    ``ValueError``, not a :class:`GlpiError`, with ``__cause__`` and
    ``__context__`` both ``None``. Every ``create_*``/``update_*`` carrying
    a body was affected, so ``except GlpiError`` did not fire on the one
    path the package's error contract is most explicit about.
    """

    deep_markdown = "".join(" " * (4 * level) + "- x\n" for level in range(600))
    client = make_client()
    TransportRecorder().install(client)

    with pytest.raises(GlpiContentError) as caught:
        client.create_ticket(PostTicket(name="round trip", content=deep_markdown))

    assert isinstance(caught.value, GlpiError)
    assert not isinstance(caught.value, ValueError)
    # the original fault, which pydantic-core had discarded
    assert isinstance(caught.value.__cause__, RecursionError)
    # and the serializer wrapper, kept where a reader would look for it
    assert isinstance(caught.value.__context__, PydanticSerializationError)


def test_a_serialisation_fault_that_is_not_content_is_not_mislabelled() -> None:
    """Only a stashed content fault becomes a ``GlpiContentError``.

    An unserialisable field is a different problem, and reporting it as a
    content conversion failure would send a reader looking in the wrong
    place. It also proves the stash cannot go stale: this block records no
    fault of its own.
    """

    with pytest.raises(GlpiValidationError):
        with restoring_content_faults():
            raise PydanticSerializationError("unserialisable field")


def test_one_field_spelled_twice_keeps_the_spelling_pydantic_uses() -> None:
    """A duplicate spelling used to shadow the field in ``model_dump``.

    ``extra="allow"`` filed the alias Pydantic did not consume as a model
    extra, and ``model_dump`` emitted it *over* the real field: the
    attribute reported one body and the object's own dump reported the
    other. ``content_html`` is the first choice, so a dump that carries
    both -- which is what ``model_copy(update={"content": ...})`` produces
    -- round-trips back to the raw body rather than to the phantom.
    """

    both = GetTicket.model_validate(
        {
            "id": 1,
            "content": "<p>from content</p>",
            "content_html": "<p>from content_html</p>",
        }
    )

    assert both.content_html == "<p>from content_html</p>"
    assert both.model_extra == {}
    assert both.extra_payload == {}
    assert both.model_dump()["content_html"] == "<p>from content_html</p>"


def test_a_glpi_payload_still_populates_the_raw_field() -> None:
    """The alias order changed, so pin what GLPI actually sends.

    GLPI sends ``content``; only a round-tripped dump carries
    ``content_html``. Preferring the raw spelling must not stop the wire
    spelling working, or every read breaks.
    """

    ticket = GetTicket.model_validate({"id": 2, "content": "<p>offline</p>"})

    assert ticket.content_html == "<p>offline</p>"
    assert ticket.content == "offline"
    assert ticket.extra_payload == {}
