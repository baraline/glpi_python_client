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
