from __future__ import annotations

import pytest

from glpi_python_client.content.conversion import GlpiContentConverter


def test_content_converter_uses_markdown_in_python_and_html_for_glpi() -> None:
    markdown = GlpiContentConverter.from_transport(
        "<p>Hello <strong>world</strong></p>"
    )
    html = GlpiContentConverter.to_transport("Hello **world**")

    assert markdown == "Hello **world**"
    assert html == "<p>Hello <strong>world</strong></p>"


@pytest.mark.parametrize(
    "text",
    [
        "use the <Enter> key",
        "cmd </dev/null > out",
        "if x<y then z>0",
        "temp<max and p>min",
        "a </close> b",
        "<!-- a bare comment -->",
        "generic<T> in the signature",
    ],
)
def test_from_transport_preserves_text_whose_tags_are_not_html(text: str) -> None:
    """Angle brackets around a non-element name are text, not markup.

    ``<Enter>`` parses as an unknown tag, and an unknown tag's markup is
    dropped while its (empty) body is kept -- so the word disappears from the
    middle of a sentence with nothing to show it was ever there.
    """

    assert GlpiContentConverter.from_transport(text) == text


def test_from_transport_still_converts_real_html() -> None:
    """Tightening the probe must not stop genuine HTML being normalised."""

    html = "<p>The printer is <strong>offline</strong>.</p>"

    assert GlpiContentConverter.from_transport(html) == "The printer is **offline**."


def test_from_transport_leaves_caller_markdown_untouched() -> None:
    """Markdown authored by a caller survives the inbound normaliser.

    ``from_transport`` is wired as a Pydantic ``BeforeValidator``, so it also
    runs on outbound content. Anything that sends caller Markdown down the
    HTML path escapes it, and the ticket reaches GLPI showing literal
    asterisks.
    """

    markdown = "The printer is **offline** and 5 * 3 = 15."

    assert GlpiContentConverter.from_transport(markdown) == markdown


def test_fenced_code_block_survives_the_round_trip() -> None:
    """A fence stays a fence. Pasted logs are the common case for this."""

    markdown = "```\nblock\n```"

    assert (
        GlpiContentConverter.from_transport(GlpiContentConverter.to_transport(markdown))
        == markdown
    )


def test_fenced_code_block_renders_as_a_pre_block() -> None:
    """Outbound, a fence becomes ``<pre><code>`` rather than inline code.

    Inline ``<code>`` is what collapsed a multi-line log into one line in the
    GLPI web UI, and what a read-modify-write then wrote back as inline code.
    """

    assert GlpiContentConverter.to_transport("```\nblock\n```") == (
        "<pre><code>block\n</code></pre>"
    )


def test_table_survives_the_round_trip() -> None:
    """A Markdown table stays a table instead of degrading to text."""

    rendered = GlpiContentConverter.from_transport(
        GlpiContentConverter.to_transport("| a | b |\n| - | - |\n| 1 | 2 |")
    )

    assert rendered == "| a | b |\n| --- | --- |\n| 1 | 2 |"


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("<p>snake_case name</p>", "snake_case name"),
        ("<p>5 * 3 = 15</p>", "5 * 3 = 15"),
    ],
)
def test_incoming_text_is_not_backslash_escaped(html: str, expected: str) -> None:
    r"""Underscores and asterisks in prose stay readable.

    Escaping them turns ``snake_case`` into ``snake\_case`` on every read,
    and the backslash accumulates across read-modify-write cycles.
    """

    assert GlpiContentConverter.from_transport(html) == expected
