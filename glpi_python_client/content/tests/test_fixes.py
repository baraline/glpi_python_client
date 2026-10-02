"""One regression test per reader fix ported from easyvista-python-client 0.4.0.

That package's converter is this package's 0.6.0 converter (commit
``917f030``) plus fifteen fixes, each verified there on 2026-10-02 against
synthetic generators and against its own earlier test corpus. 0.6.1 ports
them, so that the two readers give the same Markdown. Each section below
pins one, numbered as in both packages' changelogs:

1. an image's alt keeps its escapes and entities;
2. ``~~~`` opening a line stays text, not a code fence;
3. a ``!`` ending a text right before a link does not make it an image;
4. an alt opening with ``^`` stays an image;
5. a second ``<`` after an escaped one does not open an autolink;
6. a line break in inline code (``code``, ``kbd``, ``samp``) is kept in a
   paragraph and a cell, and is a space in a heading, which is one line;
   and a ``|`` in one of them in a cell stays in the cell;
7. a table inside a heading or a link is written as its cells' text, as
   one inside a cell already was;
8. a block in such a table stays on its holder's line;
9. bold at a flattened cell's edge still closes;
10. ``<center>`` is a block, except inside ``<pre>``;
11. ``<u>``, ``<mark>`` and ``<ins>`` stay raw HTML.

Every word is invented and every URL is under ``example.org``.
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from glpi_python_client.content.conversion import GlpiContentConverter
from glpi_python_client.content.tests.display import displayed, one_line
from glpi_python_client.content.tests.test_round_trip import assert_survives

read = GlpiContentConverter.from_transport
render = GlpiContentConverter.to_transport


def _alts(html: str) -> list[str]:
    """The alt of every image, as the HTML parser reads it."""

    soup = BeautifulSoup(html, "html.parser")
    return [str(image.get("alt")) for image in soup.find_all("img")]


# ---------------------------------------------------------------------------
# 1. An image's alt keeps its escapes and entities
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "alt",
    [
        pytest.param("a_b C:\\Temp *x* [y] &amp; `z`", id="syntax"),
        pytest.param("R&amp;amp;D &amp;copy;", id="literal-entities"),
        pytest.param("\\_ et \\*", id="backslashes"),
        pytest.param("x &lt; y", id="less-than"),
    ],
)
def test_1_an_image_alt_keeps_its_escapes_and_entities(alt: str) -> None:
    """markdown-it-py 3 leaves an escape or an entity in alt text as a
    ``text_special`` token, which mdformat rendered as nothing."""

    html = f'<p><img src="https://example.org/i.png" alt="{alt}"></p>'

    markdown = assert_survives(html)

    assert _alts(render(markdown)) == _alts(html)


# ---------------------------------------------------------------------------
# 2. '~~~' opening a line stays text
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "html",
    [
        pytest.param("<p>~~~</p>", id="paragraph"),
        pytest.param("<p>intro<br>~~~<br>suite</p>", id="after-a-break"),
        pytest.param("<ul><li>a<br>~~~~ b</li></ul>", id="in-a-list-item"),
        pytest.param("<blockquote><p>a<br>~~~ x</p></blockquote>", id="quoted"),
    ],
)
def test_2_a_tilde_run_opening_a_line_stays_text(html: str) -> None:
    """CommonMark reads ``~~~`` at a line start as a fence, which swallowed
    the rest of the body; mdformat has no guard for it."""

    markdown = assert_survives(html)

    assert "\\~~~" in markdown


def test_2_a_tilde_run_inside_a_line_is_not_escaped() -> None:
    """The control: only a run that opens a line is a fence, so only it is escaped."""

    assert assert_survives("<p>a ~~~ b</p>") == "a ~~~ b"


# ---------------------------------------------------------------------------
# 3. A trailing '!' before a link
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "html",
    [
        pytest.param(
            '<p>Attention!<a href="https://example.org/u">voir</a></p>', id="link"
        ),
        pytest.param(
            '<p>a!<a href="https://example.org/u">'
            '<img src="https://example.org/i.png" alt="x"></a></p>',
            id="linked-image",
        ),
        pytest.param(  # the control: "!<url>" was never an image
            '<p>a!<a href="https://example.org/u">https://example.org/u</a></p>',
            id="autolink",
        ),
    ],
)
def test_3_a_bang_before_a_link_does_not_make_an_image(html: str) -> None:
    """``!`` then ``[text](url)`` is an image in Markdown."""

    assert_survives(html)


def test_3_only_a_trailing_bang_is_escaped() -> None:
    """A ``!`` meets a ``[`` only at a text's end, so no other is escaped.

    A pin on the output, not a guard on the fix's narrow form. mdformat
    re-renders from the syntax tree and drops an escape that changes
    nothing, so escaping every ``!`` gives this same Markdown: a review on
    2026-10-02 found no body, among 3,414 from this suite's generators, on
    which the two forms differ. The narrow form was kept as the smaller
    change.
    """

    assert assert_survives("<p>Hi! there! ok</p>") == "Hi! there! ok"


# ---------------------------------------------------------------------------
# 4. An alt opening with '^'
# ---------------------------------------------------------------------------


def test_4_an_alt_opening_with_a_caret_stays_an_image() -> None:
    """cmark-gfm never opens an image on ``![^``, the footnote syntax."""

    html = '<p><img src="https://example.org/i.png" alt="^x"> fin</p>'

    markdown = assert_survives(html)

    assert markdown.startswith("![\\^x]")


def test_4_in_code_the_caret_is_not_escaped() -> None:
    """Inside code nothing is syntax, so a backslash there would show.

    This guards the fix's correction, not the fix.
    """

    markdown = read(
        '<p><code>x<img src="https://example.org/i.png" alt="^x"></code></p>'
    )

    assert "\\^" not in markdown


# ---------------------------------------------------------------------------
# 5. A second '<' does not open an autolink
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "html",
    [
        pytest.param("<p>&lt;&lt;a@b.c&gt; et &lt;&lt;b&gt; c</p>", id="address"),
        pytest.param("<p>&lt;&lt;https://example.org&gt;</p>", id="url"),
    ],
)
def test_5_a_second_less_than_stays_text(html: str) -> None:
    """mdformat's escape pattern ate the character after an escaped ``<``,
    so ``<<a@b.c>`` became ``\\<<a@b.c>``: an autolink."""

    markdown = assert_survives(html)

    assert "\\<\\<" in markdown


# ---------------------------------------------------------------------------
# 6. A line break in inline code
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        pytest.param(
            "<p>Sortie : <code>ligne un<br>ligne deux</code> fin</p>",
            "Sortie : `ligne un`\\\n`ligne deux` fin",
            id="paragraph",
        ),
        pytest.param(
            "<p>x <code>ligne un<br> ligne deux</code> y</p>",
            "x `ligne un`\\\n`ligne deux` y",
            id="space-after-the-break",
        ),
        pytest.param(
            "<table><tr><th>H</th></tr><tr><td>a <code>un<br>deux</code> b</td></tr>"
            "</table>",
            "| H |\n| -- |\n| a `un`<br>`deux` b |",
            id="cell",
        ),
    ],
)
def test_6_a_line_break_in_inline_code_splits_the_span(
    html: str, expected: str
) -> None:
    """A code span cannot hold a line break, so the span ends and resumes."""

    assert assert_survives(html) == expected


def test_6_a_line_break_in_inline_code_in_a_heading_is_a_space() -> None:
    """A heading is one line in Markdown: the break becomes a space."""

    markdown = read("<h2>a <code>un<br>deux</code> b</h2>")

    assert markdown == "## a `un` `deux` b"
    assert displayed(render(markdown)) == displayed(
        "<h2>a <code>un</code> <code>deux</code> b</h2>"
    )


@pytest.mark.parametrize("tag", ["code", "kbd", "samp"])
def test_6_a_pipe_in_inline_code_in_a_cell_stays_in_the_cell(tag: str) -> None:
    """GFM splits a row on ``|`` before it reads code. ``code`` is the control:
    0.6.0 escaped it there already, but not in ``kbd`` or ``samp``."""

    html = f"<table><tr><th>H</th></tr><tr><td><{tag}>a|b</{tag}> fin</td></tr></table>"

    markdown = assert_survives(html)

    assert "`a\\|b` fin" in markdown


# ---------------------------------------------------------------------------
# 7. A table inside a heading or a link
# ---------------------------------------------------------------------------


def test_7_a_table_inside_a_heading_is_its_cells_text() -> None:
    markdown = assert_survives(
        "<h2>Titre <table><tr><td>a</td><td>b</td></tr></table></h2>"
    )

    assert markdown == "## Titre a b"


def test_7_a_table_inside_a_link_is_the_links_text() -> None:
    """A browser draws the table inside the link; Markdown cannot, so every
    word is kept, in order, still linked."""

    html = (
        '<p>avant <a href="https://example.org/u"><table><tr><td>un</td><td>deux</td>'
        "</tr></table></a> apres</p>"
    )

    markdown = read(html)

    assert markdown == "avant [un deux](https://example.org/u) apres"
    assert displayed(render(markdown)) == one_line(html)
    assert read(render(markdown)) == markdown


def test_7_a_table_inside_a_cell_is_its_cells_text() -> None:
    """The control: 0.6.0 already flattened a table nested in a cell."""

    markdown = assert_survives(
        "<table><tr><th>A</th></tr><tr><td><table><tr><td>un</td><td>deux</td></tr>"
        "</table></td></tr></table>"
    )

    assert markdown == "| A |\n| -- |\n| un deux |"


# ---------------------------------------------------------------------------
# 8. A block in a flattened table stays on its holder's line
# ---------------------------------------------------------------------------


def test_8_blocks_in_a_table_inside_a_link_stay_on_the_links_line() -> None:
    html = (
        '<p>avant <a href="https://example.org/u"><table><tr><td><p>un</p><p>deux</p>'
        "</td><td>z</td></tr></table></a> apres</p>"
    )

    markdown = read(html)

    assert markdown == "avant [un deux z](https://example.org/u) apres"
    assert displayed(render(markdown)) == one_line(html)


# ---------------------------------------------------------------------------
# 9. Bold at a flattened cell's edge still closes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cells",
    [
        pytest.param("<td>x</td><td><b>gras.</b></td><td>y</td>", id="ends-on-a-dot"),
        pytest.param("<td><b>(gras)</b></td><td>y</td>", id="parenthesised"),
    ],
)
def test_9_bold_at_a_flattened_cells_edge_is_markdown_bold(cells: str) -> None:
    """The converter spaces a flattened cell, so its edge counts as a space.
    0.6.0 counted the next cell's text and wrote raw ``<strong>``,
    which read back as ``**`` and was not a fixed point."""

    markdown = assert_survives(
        f"<table><tr><th>A</th></tr><tr><td><table><tr>{cells}</tr></table></td></tr>"
        "</table>"
    )

    assert "<strong>" not in markdown


# ---------------------------------------------------------------------------
# 10. <center> is a block, except inside <pre>
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        pytest.param("<center>Titre</center> suite", "Titre\n\nsuite", id="alone"),
        pytest.param("<p>a<center>b</center>c</p>", "a\n\nb\n\nc", id="in-a-line"),
    ],
)
def test_10_center_is_a_block(html: str, expected: str) -> None:
    assert assert_survives(html) == expected


def test_10_center_inside_pre_is_left_alone() -> None:
    """The correction to the fix, not the fix: as a block there it split the code."""

    markdown = assert_survives("<pre>un\n<center>deux</center>\ntrois</pre>")

    assert markdown == "```\nun\ndeux\ntrois\n```"


# ---------------------------------------------------------------------------
# 11. <u>, <mark> and <ins> stay raw HTML
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tag", ["u", "mark", "ins"])
def test_11_underline_and_highlight_stay_raw_html(tag: str) -> None:
    """CommonMark has neither; 0.6.0 dropped the formatting."""

    markdown = assert_survives(f"<p>a <{tag}>trilo</{tag}> fin</p>")

    assert markdown == f"a <{tag}>trilo</{tag}> fin"
    assert f"<{tag}>trilo</{tag}>" in render(markdown)


def test_11_the_edges_move_outside_the_tag() -> None:
    assert read("<p>a<u> trilo </u>b</p>") == "a <u>trilo</u> b"


def test_11_underline_inside_a_link() -> None:
    markdown = assert_survives('<p><a href="https://example.org/u"><u>lien</u></a></p>')

    assert markdown == "[<u>lien</u>](https://example.org/u)"
