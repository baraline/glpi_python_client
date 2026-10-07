"""The converter's contract: its two directions, its errors, and what it survives.

How faithfully realistic content round-trips is :mod:`.test_round_trip`'s
subject; this module pins the interface around it.
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup, ParserRejectedMarkup

from glpi_python_client import GlpiContentError, GlpiError
from glpi_python_client.content import conversion
from glpi_python_client.content.conversion import GlpiContentConverter
from glpi_python_client.content.tests.display import displayed

read = GlpiContentConverter.from_transport
render = GlpiContentConverter.to_transport

#: What every rendered link carries: GLPI's editor writes it on a link it makes.
NEW_WINDOW = ' target="_blank" rel="noopener noreferrer"'


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


_MALFORMED_DECLARATIONS = ["<p>a</p><![FOO[x]]><p>b</p>", "<p>a</p><![ x<p>b</p>"]


@pytest.mark.parametrize("html", _MALFORMED_DECLARATIONS)
def test_a_malformed_declaration_still_reads_both_sides(html: str) -> None:
    """Older CPython patch releases reject these; newer ones parse them.

    3.12.11 raises from ``html.parser``, 3.12.14 and 3.13.14 read a
    comment, so only what both outcomes share is pinned here.
    """

    markdown = read(html)
    assert markdown.index("a") < markdown.rindex("b")


@pytest.mark.parametrize("html", _MALFORMED_DECLARATIONS)
def test_markup_the_parser_rejects_degrades_to_its_text(
    monkeypatch: pytest.MonkeyPatch, html: str
) -> None:
    """Rejection is forced, so the fallback runs whatever ``html.parser`` does."""

    parse = conversion._soup

    def rejecting(markup: str) -> BeautifulSoup:
        if "<![" in markup:
            raise ParserRejectedMarkup(AssertionError("marked section"))
        return parse(markup)

    monkeypatch.setattr(conversion, "_soup", rejecting)

    assert read(html) == "a b"


def test_an_inbound_fault_surfaces_as_a_glpi_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fault is a ``RuntimeError``: since fix 14 a ``ValueError`` goes to
    the text fallback first (:func:`test_a_value_error_is_retried_as_text_first`),
    and a ``RuntimeError`` reaches the error path directly."""

    def failing(html: str) -> str:
        raise RuntimeError("converter fault")

    monkeypatch.setattr(conversion, "html_to_markdown", failing)

    with pytest.raises(GlpiContentError) as caught:
        read("<p>x</p>")

    assert isinstance(caught.value, GlpiError)
    assert isinstance(caught.value.__cause__, RuntimeError)
    assert "Could not convert GLPI HTML content to Markdown" in str(caught.value)


def test_a_value_error_is_retried_as_text_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fix 14: a ``ValueError`` is answered like a ``RecursionError``, by the text.

    markdownify calls ``int()`` on a ``colspan`` or a ``start``, which raises
    on ``"²"`` or on more digits than CPython converts. The body is read again
    as its text; only if that fails too is the error reported.
    """

    calls: list[str] = []
    convert = conversion.html_to_markdown

    def failing_once(html: str) -> str:
        calls.append(html)
        if len(calls) == 1:
            raise ValueError("invalid literal for int()")
        return convert(html)

    monkeypatch.setattr(conversion, "html_to_markdown", failing_once)

    assert read("<p>un <b>deux</b></p>") == "un deux"
    assert len(calls) == 2


def test_a_value_error_on_the_text_path_too_is_a_glpi_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing(html: str) -> str:
        raise ValueError("converter fault")

    monkeypatch.setattr(conversion, "html_to_markdown", failing)

    with pytest.raises(GlpiContentError) as caught:
        read("<p>x</p>")

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
    assert "Could not render Markdown content as GLPI HTML" in str(caught.value)


def test_deeply_nested_markdown_renders() -> None:
    """cmark-gfm does not recurse in Python, so depth costs nothing outbound."""

    markdown = "".join(" " * (2 * level) + "- x\n" for level in range(600))

    assert render(markdown).count("<li>") == 600


# ---------------------------------------------------------------------------
# It is not a sanitiser
# ---------------------------------------------------------------------------
#
# What the user guide ("Rich-text content", docs/user_guide.rst) says,
# pinned exactly: a cmark-gfm option or release that changed any of it would
# make the documentation wrong in one direction or the other. The writing
# direction neutralises nothing; the reading direction keeps a body's link
# targets, and keeps text a body displays as text. easyvista-python-client
# 0.4.0 pins the same.


@pytest.mark.parametrize(
    ("markdown", "html"),
    [
        pytest.param(
            "<script>alert(1)</script>", "<script>alert(1)</script>", id="raw-html"
        ),
        pytest.param(
            "[x](javascript:alert(1))",
            f'<p><a href="javascript:alert(1)"{NEW_WINDOW}>x</a></p>',
            id="link-target",
        ),
        pytest.param(  # python-markdown, before 0.6.0, left this as raw markup
            "<javascript:alert(1)>",
            f'<p><a href="javascript:alert(1)"{NEW_WINDOW}>javascript:alert(1)</a></p>',
            id="autolink",
        ),
    ],
)
def test_the_write_path_renders_what_it_is_given_live(markdown: str, html: str) -> None:
    assert render(markdown) == html


def test_the_read_path_keeps_a_bodys_javascript_link() -> None:
    assert read('<p><a href="javascript:alert(1)">x</a></p>') == (
        "[x](<javascript:alert(1)>)"
    )


def test_markup_a_body_displays_as_text_stays_text_both_ways() -> None:
    markdown = read("<p>&lt;script&gt;</p>")

    assert markdown == "\\<script>"
    assert render(markdown) == "<p>&lt;script&gt;</p>"


# A link opens in a new window, as a link written in GLPI's editor does
# (``target="_blank"``), rather than in place of the page showing it. The same
# attributes as ``easyvista-python-client`` 0.4.2 writes, so the twins agree.


@pytest.mark.parametrize(
    ("markdown", "html"),
    [
        pytest.param(
            "[voir](https://example.org/p)",
            f'<p><a href="https://example.org/p"{NEW_WINDOW}>voir</a></p>',
            id="link",
        ),
        pytest.param(
            '[voir](https://example.org/p "le titre")',
            f'<p><a href="https://example.org/p" title="le titre"{NEW_WINDOW}>'
            "voir</a></p>",
            id="titled",
        ),
        pytest.param(
            "<https://example.org/p>",
            f'<p><a href="https://example.org/p"{NEW_WINDOW}>https://example.org/p</a></p>',
            id="autolink",
        ),
        pytest.param(
            "[![a](https://example.org/i.png)](https://example.org/p)",
            f'<p><a href="https://example.org/p"{NEW_WINDOW}>'
            '<img src="https://example.org/i.png" alt="a" /></a></p>',
            id="image-link",
        ),
    ],
)
def test_every_link_written_opens_in_a_new_window(markdown: str, html: str) -> None:
    assert render(markdown) == html


def test_a_link_shown_as_code_is_text_and_gains_nothing() -> None:
    assert render('`<a href="https://example.org">x</a>`') == (
        "<p><code>&lt;a href=&quot;https://example.org&quot;&gt;x&lt;/a&gt;</code></p>"
    )


@pytest.mark.parametrize(
    "markdown",
    [
        "[voir](https://example.org/p)",
        '[voir](https://example.org/p "le titre")',
        "<https://example.org/p>",
        "[![a](https://example.org/i.png)](https://example.org/p)",
    ],
    ids=["link", "titled", "autolink", "image-link"],
)
def test_a_link_written_to_open_in_a_new_window_reads_back_as_written(
    markdown: str,
) -> None:
    # Reading ignores ``target`` and ``rel``, so a round trip stays exact.
    assert read(render(markdown)) == markdown
