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
