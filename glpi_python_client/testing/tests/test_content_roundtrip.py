"""Tests for transparent Markdown <-> HTML transport on content fields.

The package contract is that every ``content`` field accepts and returns
canonical Markdown while GLPI continues to receive HTML over the wire.
These tests cover both directions on every model that exposes a Markdown
content field, plus the inert behaviours (``None``, plain text round trip)
that keep ``exclude_none`` semantics and non-HTML payloads stable.
"""

from __future__ import annotations

from functools import cached_property

import pytest

from glpi_python_client._sync.clients.commons._payloads import model_to_payload
from glpi_python_client.content import conversion
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
from glpi_python_client.models.api_schema.knowledgebase import (
    GetKBArticle,
    GetKBArticleRevision,
)


def _count_conversions(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every call to the inbound converter, and return the log.

    A list rather than a counter so an assertion can show what was
    converted, not only how often.
    """

    seen: list[str] = []
    real = conversion.GlpiContentConverter.from_transport

    def _record(value: object) -> str:
        seen.append(str(value))
        return real(value)

    monkeypatch.setattr(
        conversion.GlpiContentConverter, "from_transport", staticmethod(_record)
    )
    return seen


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


# ---------------------------------------------------------------------------
# Round-trip corpus
# ---------------------------------------------------------------------------
#
# ``from_transport(to_transport(m)) == m`` is the property the content layer
# would like to hold. It does not hold universally, and cannot: the two
# libraries either side of the wire disagree about a handful of constructs,
# and no option on either fixes them.
#
# So the corpus is an inventory rather than a property test. Every case is
# listed, the lossy ones carry ``xfail(strict=True)``, and that strictness is
# the point -- fixing one of them turns its xfail into an XPASS and fails the
# suite, forcing the inventory to be updated rather than quietly drifting out
# of date. A regression in a passing case fails immediately.


def _lossy(reason: str) -> pytest.MarkDecorator:
    """Mark one corpus entry as a known, recorded round-trip loss."""

    return pytest.mark.xfail(strict=True, reason=reason)


ROUND_TRIP_CORPUS = [
    pytest.param("The printer is offline.", id="plain"),
    pytest.param("The printer is **offline**.", id="bold"),
    pytest.param("This is *emphasis*.", id="italic"),
    pytest.param("Run `systemctl restart` now.", id="inline-code"),
    pytest.param("# Title\n\nBody text.", id="heading"),
    pytest.param("## Section\n\nBody text.", id="subheading"),
    pytest.param("First para.\n\nSecond para.", id="paragraphs"),
    pytest.param("line one  \nline two", id="hard-break"),
    pytest.param("- alpha\n- beta\n- gamma", id="bullets"),
    pytest.param("1. one\n2. two", id="numbered"),
    pytest.param("> quoted text", id="blockquote"),
    pytest.param("See [the doc](https://example.test/doc).", id="link"),
    pytest.param("```\nx = 1\n```", id="fence"),
    pytest.param("| a | b |\n| --- | --- |\n| 1 | 2 |", id="table"),
    pytest.param("The snake_case name.", id="underscore"),
    pytest.param("5 * 3 = 15", id="asterisk"),
    pytest.param("# Title\n\n- alpha\n- beta\n\nClosing **note**.", id="mixed"),
    pytest.param(
        "line one\nline two",
        id="soft-newline",
        marks=_lossy(
            "nl2br renders a lone newline as <br>, which markdownify reads "
            "back as a hard break (two trailing spaces). Semantically "
            "equivalent and stable after one cycle; see issue #32."
        ),
    ),
    pytest.param(
        "- alpha\n    - inner\n- beta",
        id="nested-list",
        marks=_lossy(
            "markdownify indents nested items by 2 spaces; python-markdown "
            "needs 4 to keep the nesting, so a second cycle flattens it."
        ),
    ),
    pytest.param(
        "```python\nx = 1\n```",
        id="fence-with-language",
        marks=_lossy(
            "fenced_code emits class='language-python' and markdownify drops "
            "the class, so the language tag cannot survive."
        ),
    ),
    pytest.param(
        "use the <Enter> key",
        id="angle-bracket-text",
        marks=_lossy(
            "to_transport does not escape raw markup, so the text reaches "
            "GLPI as a live unknown tag -- which the web UI drops too. "
            "Escaping it is a separate change to the outbound direction."
        ),
    ),
]


@pytest.mark.parametrize("markdown", ROUND_TRIP_CORPUS)
def test_round_trip_corpus(markdown: str) -> None:
    """Markdown survives a full write-then-read cycle through GLPI's HTML."""

    outgoing = model_to_payload(PostTicket(name="Round trip", content=markdown))
    incoming = GetTicket.model_validate({"name": "Round trip", **outgoing})

    assert incoming.content == markdown


# ---------------------------------------------------------------------------
# Lazy conversion on the read models
# ---------------------------------------------------------------------------
#
# Conversion used to run inside the Pydantic validator, which meant a caller
# who wanted only ``id`` and ``date_mod`` paid HTML-to-Markdown on every
# record of every page, and one unconvertible body took its page-mates down
# with it -- ``_resource_list`` builds a page in a single comprehension. The
# tests here pin the three consequences of moving it to the attribute: the
# raw value is available, nothing converts until something is read, and a
# failure is confined to the record whose body was read.

#: Every read model with a content slot, and the fields on each.
#:
#: Named explicitly rather than discovered, so that adding a read model with
#: a content field and forgetting the property is a failure here rather than
#: a silently eager model.
READ_CONTENT_MODELS = [
    pytest.param(GetTicket, ["content"], id="GetTicket"),
    pytest.param(GetFollowup, ["content"], id="GetFollowup"),
    pytest.param(GetSolution, ["content"], id="GetSolution"),
    pytest.param(GetTicketTask, ["content"], id="GetTicketTask"),
    pytest.param(GetKBArticle, ["content", "description"], id="GetKBArticle"),
    pytest.param(GetKBArticleRevision, ["content"], id="GetKBArticleRevision"),
]


@pytest.mark.parametrize(("model_cls", "slots"), READ_CONTENT_MODELS)
def test_read_models_keep_the_raw_wire_value(model_cls: type, slots: list[str]) -> None:
    """``<slot>_html`` holds exactly what GLPI sent, unconverted."""

    html = "<p>The printer is <strong>offline</strong>.</p>"

    instance = model_cls.model_validate({slot: html for slot in slots})

    for slot in slots:
        assert getattr(instance, f"{slot}_html") == html
        assert getattr(instance, slot) == "The printer is **offline**."


@pytest.mark.parametrize(("model_cls", "slots"), READ_CONTENT_MODELS)
def test_no_read_model_still_declares_the_slot_as_a_field(
    model_cls: type, slots: list[str]
) -> None:
    """A leftover field declaration would shadow the property, silently.

    Pydantic keeps a field of that name if one is declared anywhere in the
    MRO, puts the validated value straight into ``__dict__``, and the
    non-data ``cached_property`` descriptor never runs -- no error, no
    warning, and ``.content`` hands back raw HTML. Deleting the old line is
    half the change, so it is asserted rather than assumed.
    """

    for slot in slots:
        assert slot not in model_cls.model_fields
        assert f"{slot}_html" in model_cls.model_fields
        assert isinstance(model_cls.__dict__.get(slot), cached_property)


def test_building_a_page_of_records_converts_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validation is free; the cost moves to whoever reads a body.

    This is the reason for the whole change. A search returning a hundred
    tickets used to run HTML-to-Markdown a hundred times whether or not the
    caller looked at a single body.
    """

    calls = _count_conversions(monkeypatch)
    payload = {"id": 1, "content": "<p>The printer is <strong>offline</strong>.</p>"}

    page = [GetTicket.model_validate(payload) for _ in range(100)]

    assert calls == []
    assert page[7].content == "The printer is **offline**."
    assert len(calls) == 1


def test_a_body_is_converted_once_however_often_it_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``cached_property``, so repeated reads are free.

    Worth pinning: without the cache, moving conversion to the attribute
    would make the common read-it-twice case slower than the eager version
    it replaced.
    """

    calls = _count_conversions(monkeypatch)
    ticket = GetTicket.model_validate({"content": "<p>a <em>b</em></p>"})

    first, second, third = ticket.content, ticket.content, ticket.content

    assert first == second == third == "a *b*"
    assert len(calls) == 1


def test_one_unconvertible_body_leaves_its_page_mates_readable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure is scoped to the record whose body was actually read.

    ``TransportMixin._resource_list`` validates a whole page in one
    comprehension, so a converter that raised on any single record used to
    abort the page and take every other body with it -- including the
    records the caller wanted. Now the two other tickets read fine and the
    bad one raises only when touched.
    """

    def _selective(value: object) -> str:
        if "poison" in str(value):
            raise RecursionError("maximum recursion depth exceeded")
        return "converted"

    monkeypatch.setattr(
        conversion.GlpiContentConverter, "from_transport", staticmethod(_selective)
    )

    page = [
        GetTicket.model_validate({"id": 1, "content": "<p>fine</p>"}),
        GetTicket.model_validate({"id": 2, "content": "<p>poison</p>"}),
        GetTicket.model_validate({"id": 3, "content": "<p>fine too</p>"}),
    ]

    assert [ticket.id for ticket in page] == [1, 2, 3]
    assert page[0].content == "converted"
    assert page[2].content == "converted"
    with pytest.raises(RecursionError):
        _ = page[1].content


def test_a_body_too_deep_to_convert_no_longer_breaks_get_ticket() -> None:
    """The end-to-end regression test for the bug behind all of this.

    Around 494 levels of nesting exhausted the interpreter's stack inside
    ``markdownify``. With the conversion in a ``BeforeValidator`` that
    ``RecursionError`` came out of ``model_validate`` -- so out of
    ``get_ticket``, from a library whose whole error surface is supposed to
    derive from ``GlpiError``. Two changes had to land for this to pass:
    the depth ceiling that degrades instead of recursing, and the move off
    the validator so nothing converts before it is asked for.
    """

    deep = "<div>" * 600 + "the printer is offline" + "</div>" * 600

    ticket = GetTicket.model_validate({"id": 42, "content": deep})

    assert ticket.id == 42
    assert ticket.content == "the printer is offline"


def test_reading_content_off_a_write_model_still_works() -> None:
    """Write models keep converting eagerly, and keep the field name.

    The asymmetry is deliberate -- a caller's own Markdown is worth
    checking where it was supplied, and there is no list path on a write
    model to make lazy -- but ``.content`` has to read back the same way on
    both, or the read-modify-write flow breaks.
    """

    ticket = PostTicket(content="The printer is **offline**.")

    assert ticket.content == "The printer is **offline**."
    assert "content" in PostTicket.model_fields
    assert not hasattr(ticket, "content_html")
