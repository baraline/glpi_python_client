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
11. ``<u>``, ``<mark>`` and ``<ins>`` stay raw HTML, except round a block,
    where they are dropped and the blocks kept;
12. an ordered list is numbered in linear time, and a ``start`` that is
    not a decimal number counts from 1;
13. the regex splitting a text's edges is greedy, so linear;
14. a number markdownify cannot read sends the body to the text fallback;
15. an unfinished tag at the very end is read as text (the CVE-2025-6069
    guard).

The cost side of 12, 13 and 15 is tested in :mod:`.test_cost`. Run against
0.6.0 on 2026-10-02 (CPython 3.12.3), 36 of the 54 tests first ported
failed. Of the 18 that passed there, 17 are controls, guards on a
correction to a fix, pins of output a fix leaves as it was, or behaviour a
cost fix had to keep, and each says which. The other is test 15's
``attribute`` case, which passed only because 3.12.3 predates CPython's own
fix; that test says why.

The 42 tests added to section 11 for a block inside ``<u>``, ``<mark>`` or
``<ins>`` pin the correction to fix 11, which wrapped blocks in the tag: run
against easyvista-python-client 0.4.0's converter, 40 failed, and the two
that passed are the one-line controls. They read such a body as 0.6.0 did,
so on 0.6.0 only the three that need a tag kept fail.

Every word is invented and every URL is under ``example.org``.
"""

from __future__ import annotations

import sys

import pytest
from bs4 import BeautifulSoup

from glpi_python_client.content import conversion
from glpi_python_client.content.conversion import GlpiContentConverter
from glpi_python_client.content.tests.display import (
    displayed,
    one_line,
    text_words,
)
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


_TABLE = (
    "<table><tr><th>Nom</th><th>Valeur</th></tr>"
    "<tr><td>serveur</td><td>srv01</td></tr></table>"
)


@pytest.mark.parametrize("tag", ["u", "mark", "ins"])
@pytest.mark.parametrize(
    "body",
    [
        pytest.param(f"<p>Voir :</p><X>{_TABLE}</X><p>fin</p>", id="table"),
        pytest.param("<X><ul><li>un</li><li>deux</li></ul></X>", id="list"),
        pytest.param("<X><ol><li>un</li><li>deux</li></ol></X>", id="ordered-list"),
        pytest.param("<X><h2>Titre</h2><p>texte</p></X>", id="heading"),
        pytest.param("<X><blockquote>cite</blockquote></X>", id="quote"),
        pytest.param("<X><pre>un\ndeux</pre></X>", id="pre"),
        pytest.param("<p>a</p><X><hr></X><p>b</p>", id="rule"),
        pytest.param("<X><p>un</p><p>deux</p></X>", id="paragraphs"),
        pytest.param("<X><div>un</div><div>deux</div></X>", id="divs"),
        pytest.param("<X>avant<p>milieu</p>apres</X>", id="text-around-a-block"),
        pytest.param("<ul><li><X><p>un</p><p>deux</p></X></li></ul>", id="in-an-item"),
        pytest.param(
            "<blockquote><X><p>un</p><p>deux</p></X></blockquote>", id="in-a-quote"
        ),
    ],
)
def test_11_around_a_block_the_tag_is_dropped_and_the_blocks_kept(
    body: str, tag: str
) -> None:
    """Markdown has no inline tag around blocks: fix 11 wrapped them anyway,
    so a table read as pipe text, a list, heading, quote or rule as its
    Markdown source, and paragraphs were not a fixed point. The tag is
    dropped there and the blocks read as they would without it, as 0.6.0
    read them; the underline is lost, which the display oracle cannot see."""

    html = body.replace("<X>", f"<{tag}>").replace("</X>", f"</{tag}>")
    bare = body.replace("<X>", "").replace("</X>", "")

    markdown = assert_survives(html)

    assert markdown == read(bare)
    assert f"<{tag}>" not in markdown


def test_11_a_pre_inside_underline_leaves_no_stray_fence() -> None:
    """The worst of the shapes above: the closing fence took the ``</u>`` as
    its info string, so it opened a new fence and everything after it,
    ``apres`` included, displayed as code."""

    markdown = assert_survives("<u><pre>code</pre></u><p>apres</p>")

    assert markdown == "```\ncode\n```\n\napres"


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        pytest.param(
            "<u><mark><ul><li>a</li></ul></mark></u>", "- a", id="both-around-a-list"
        ),
        pytest.param(
            "<u><mark>x</mark><p>y</p></u>", "<mark>x</mark>\n\ny", id="inline-sibling"
        ),
        pytest.param(
            "<u><p>a</p><mark><p>b</p></mark>c</u>", "a\n\nb\n\nc", id="inner-after"
        ),
    ],
)
def test_11_each_tag_around_a_block_is_dropped_and_no_other(
    html: str, expected: str
) -> None:
    """Nested tags: each one holding a block is dropped, however deep the
    block, and one that closed before the block keeps its raw tag."""

    assert assert_survives(html) == expected


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        pytest.param(
            "<table><tr><th><u><p>a</p></u></th></tr>"
            "<tr><td><u><p>b</p><p>c</p></u></td></tr></table>",
            "| <u>a</u> |\n| -- |\n| <u>b c</u> |",
            id="cell",
        ),
        pytest.param("<h2><u><p>titre</p></u></h2>", "## <u>titre</u>", id="heading"),
    ],
)
def test_11_around_a_block_on_one_line_the_tag_stays(html: str, expected: str) -> None:
    """The control: a cell or a heading writes its blocks on its one line,
    so the tag wraps inline text there and is kept."""

    assert assert_survives(html) == expected


# ---------------------------------------------------------------------------
# 12. Ordered-list numbering
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        pytest.param(
            '<ol start="3"><li>a</li><li>b</li><li>c<ol><li>d</li></ol></li></ol>',
            "3. a\n4. b\n5. c\n   1. d",
            id="start-and-a-nested-list",
        ),
        pytest.param(
            '<ol start="0"><li>a</li><li>b</li></ol>', "0. a\n1. b", id="start-zero"
        ),
        pytest.param('<ol start="½"><li>a</li><li>b</li></ol>', "1. a\n2. b", id="½"),
        pytest.param('<ol start="²"><li>a</li><li>b</li></ol>', "1. a\n2. b", id="²"),
    ],
)
def test_12_an_ordered_item_is_numbered_one_past_the_item_before(
    html: str, expected: str
) -> None:
    """Each item keeps its number for the next, where markdownify counted
    every item before each one. ``isdecimal``, where markdownify's
    ``isnumeric`` let ``int("½")`` raise -- a browser counts such a list
    from 1, and so does the converter now.

    With a decimal ``start``, 0.6.0 numbered the same: what the fix
    changed there is the cost (:mod:`.test_cost`), and the first two cases
    pin that the rewrite numbers as markdownify did.
    """

    assert assert_survives(html) == expected


def test_12_an_empty_ordered_item_still_counts_for_the_next() -> None:
    """An empty item takes a number and writes nothing.

    Markdown has no empty ordered item, so the item cannot survive: the
    browser shows ``3. a`` and ``5. c``, and the Markdown, renumbered by
    mdformat, shows ``3. a`` and ``4. c``. The words and the fixed point
    are kept. 0.6.0 wrote the same; this pins that the rewrite still
    does, and no other test reaches its branch for an empty ordered item.
    """

    html = '<ol start="3"><li>a</li><li></li><li>c</li></ol>'

    markdown = read(html)

    assert markdown == "3. a\n4. c"
    assert text_words(render(markdown)) == text_words(html)
    assert read(render(markdown)) == markdown


# ---------------------------------------------------------------------------
# 13. The edge regex is greedy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "groups"),
    [
        pytest.param("  a b  ", ("  ", "a b", "  "), id="spaces"),
        pytest.param("\\\n a\\\n", ("\\\n ", "a", "\\\n"), id="hard-breaks"),
        pytest.param("a\\b", ("", "a\\b", ""), id="inner-backslash"),
        pytest.param("x\\", ("", "x\\", ""), id="trailing-backslash"),
        pytest.param(" \n ", (" \n ", "", ""), id="nothing-inside"),
        pytest.param("", ("", "", ""), id="empty"),
    ],
)
def test_13_the_edge_regex_splits_leading_content_and_trailing(
    text: str, groups: tuple[str, str, str]
) -> None:
    """Leading breaks and spaces, the content, trailing ones. The greedy
    pattern finds the content's last character from the end, where the
    lazy one rescanned the run after it at every step. The lazy one split
    the same way, only slower: these pin that the rewrite still does, and
    :mod:`.test_cost` pins the cost."""

    edges = conversion._EDGES.fullmatch(text)

    assert edges is not None
    assert edges.groups() == groups


# ---------------------------------------------------------------------------
# 14. A number markdownify cannot read
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "html",
    [
        pytest.param(
            '<table><tr><td colspan="²">trelm</td><td>vosk</td></tr></table>',
            id="colspan-²",
        ),
        pytest.param(
            '<ol start="' + "7" * 5000 + '"><li>trelm</li><li>vosk</li></ol>',
            id="start-of-5000-digits",
        ),
    ],
)
def test_14_a_number_markdownify_cannot_read_falls_back_to_text(html: str) -> None:
    """markdownify's ``int()`` raised ``ValueError`` -- on ``"²"``, or on more
    digits than CPython converts -- and the whole body failed. Now the body
    is read as its text: every word, one line per row or item.

    The digit limit is pinned to CPython's default of 4,300: the
    interpreter takes another from ``PYTHONINTMAXSTRDIGITS``, and ``0``
    lifts it, under which 5,000 digits are a number and the case tests
    nothing.
    """

    limit = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(4300)
    try:
        markdown = read(html)
    finally:
        sys.set_int_max_str_digits(limit)

    assert text_words(render(markdown)) == ["trelm", "vosk"]
    assert read(render(markdown)) == markdown


# ---------------------------------------------------------------------------
# 15. An unfinished tag at the very end
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        pytest.param("<p>r</p>x <a b", "r\n\nx \\<a b", id="attribute"),
        pytest.param("<p>r</p>x <<a", "r\n\nx \\<\\<a", id="doubled"),
        pytest.param(  # the control: a bare '<' was text on every release
            "<p>r</p>fin <", "r\n\nfin \\<", id="bare"
        ),
    ],
)
def test_15_an_unfinished_tag_at_the_end_reads_as_text(
    html: str, expected: str
) -> None:
    """No ``<`` after the last ``>`` can finish a tag, so each is text.

    CPython's ``html.parser`` before 3.11.14, 3.12.12 and 3.13.6 rescanned
    to the end for each such ``<`` -- quadratic, CVE-2025-6069 -- and the
    releases that fixed it drop the unfinished tag instead: on 3.13.14,
    0.6.0 read ``x <a b`` as ``x``, where 3.12.3 kept it (measured
    2026-10-02). With the guard every release reads it the same way, as
    text.

    So what these cases detect depends on the interpreter. ``attribute``
    fails without the guard only on a patched release; on an unpatched one,
    3.12.3 included, the parser keeps the text by itself, and only the
    cost test in :mod:`.test_cost` notices the guard is gone. ``doubled``
    also depends on fix 5, and fails on every release without that one.
    """

    assert read(html) == expected
