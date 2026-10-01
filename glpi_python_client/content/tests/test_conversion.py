"""The converter's contract: its two directions, its errors, and what it survives.

How faithfully realistic content round-trips is :mod:`.test_round_trip`'s
subject; this module pins the interface around it.
"""

from __future__ import annotations

import pytest

from glpi_python_client import GlpiContentError, GlpiError
from glpi_python_client.content import conversion
from glpi_python_client.content.conversion import GlpiContentConverter
from glpi_python_client.content.tests.display import displayed

read = GlpiContentConverter.from_transport
render = GlpiContentConverter.to_transport


def test_content_is_markdown_in_python_and_html_for_glpi() -> None:
    assert read("<p>The printer is <strong>offline</strong>.</p>") == (
        "The printer is **offline**."
    )
    assert render("The printer is **offline**.") == (
        "<p>The printer is <strong>offline</strong>.</p>"
    )


@pytest.mark.parametrize("value", [None, "", "   ", "\n\t"])
def test_an_empty_value_stays_empty(value: object) -> None:
    assert read(value) == ""
    assert render(value) == ""


@pytest.mark.parametrize(
    "text",
    [
        "use the <Enter> key",
        "cmd </dev/null > out",
        "if x<y then z>0",
        "generic<T> in the signature",
    ],
)
def test_angle_brackets_that_are_not_html_stay_text(text: str) -> None:
    """The element name decides what is markup: ``<Enter>`` is text."""

    shown = displayed(render(read(text)))

    assert shown == displayed("<p>" + text.replace("<", "&lt;") + "</p>")


def test_a_newline_renders_as_a_line_break() -> None:
    """GLPI's editor shows each line the caller typed, as nl2br did before."""

    assert render("ligne un\nligne deux") == "<p>ligne un<br />\nligne deux</p>"


def test_a_body_using_both_spellings_of_a_line_break_keeps_its_text() -> None:
    """beautifulsoup4 before 4.15 dropped the text after ``<br />`` in such a body."""

    markdown = read("<p>line1<br>line2</p><p>para2<br />line4</p>")

    assert "line4" in markdown


@pytest.mark.parametrize(
    "html",
    [
        pytest.param("<div>" * 3000 + "deep" + "</div>" * 3000, id="balanced"),
        pytest.param("<p>" * 5000 + "deep", id="unclosed"),
        pytest.param("<ul><li>" * 2000 + "deep" + "</li></ul>" * 2000, id="lists"),
        pytest.param(
            "<table><tr><td>" * 1500 + "deep" + "</td></tr></table>" * 1500,
            id="tables",
        ),
    ],
)
def test_a_body_too_deep_for_the_stack_degrades_to_its_text(html: str) -> None:
    """markdownify recurses per level; past the stack the words are still read."""

    assert "deep" in read(html)


@pytest.mark.parametrize(
    "html", ["<p>a</p><![FOO[x]]><p>b</p>", "<p>a</p><![ x<p>b</p>"]
)
def test_markup_the_parser_rejects_degrades_to_its_text(html: str) -> None:
    assert read(html) == "a b"


def test_an_inbound_fault_surfaces_as_a_glpi_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing(html: str) -> str:
        raise ValueError("converter fault")

    monkeypatch.setattr(conversion, "html_to_markdown", failing)

    with pytest.raises(GlpiContentError) as caught:
        read("<p>x</p>")

    assert isinstance(caught.value, GlpiError)
    assert isinstance(caught.value.__cause__, ValueError)


def test_an_outbound_fault_surfaces_as_a_glpi_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing(markdown: str) -> str:
        raise RuntimeError("renderer fault")

    monkeypatch.setattr(conversion, "markdown_to_html", failing)

    with pytest.raises(GlpiContentError) as caught:
        render("**x**")

    assert isinstance(caught.value.__cause__, RuntimeError)


def test_deeply_nested_markdown_renders() -> None:
    """cmark-gfm does not recurse in Python, so depth costs nothing outbound."""

    markdown = "".join(" " * (2 * level) + "- x\n" for level in range(600))

    assert render(markdown).count("<li>") == 600
