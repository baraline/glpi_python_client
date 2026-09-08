from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from glpi_python_client import GlpiContentError, GlpiError
from glpi_python_client.content import conversion
from glpi_python_client.content.conversion import (
    MAX_HTML_DEPTH,
    GlpiContentConverter,
    _html_nesting_depth,
)


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


# ---------------------------------------------------------------------------
# Nesting depth
# ---------------------------------------------------------------------------
#
# ``markdownify`` walks the parsed tree recursively, so a deeply nested body
# used to exhaust the interpreter's stack -- and because the converter was
# wired as a Pydantic ``BeforeValidator``, the ``RecursionError`` surfaced
# from inside ``model_validate``, i.e. from inside ``get_ticket``. These
# tests pin the three things that fixed it: the depth is measured without
# recursing, the ceiling is enforced, and past it the body degrades to text
# rather than raising or being cut short.


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("", 0),
        ("no tags here", 0),
        ("<p>one</p>", 1),
        ("<p>The printer is <strong>offline</strong>.</p>", 2),
        ("<div>" * 7 + "x" + "</div>" * 7, 7),
        # An unclosed tag still nests: ``html.parser`` does not auto-close
        # ``<p>`` or ``<li>``, so this really is 40 levels to walk.
        ("<p>" * 40, 40),
        # Nothing nests below a void or self-closed element, but the element
        # itself is still a node one level below its parent.
        ("<p>" + "<br>" * 40 + "x</p>", 2),
        ("<br>" * 40, 1),
        ("<p>a</p>" + "<div/>" * 40, 1),
        # A close with nothing open, and a close for a void element, are
        # ignored rather than pushed below zero.
        ("</div>" * 40 + "<p>x</p>", 1),
        ("<div><b>x</b></br></div>", 2),
        # An unrecognised name is a node like any other to the parser.
        ("<foo>" * 12, 12),
        # Siblings are not depth.
        ("<p>a</p>" * 40, 1),
    ],
)
def test_the_depth_scan_measures_what_the_parser_will_build(
    html: str, expected: int
) -> None:
    """The flat scan agrees with the tree ``html.parser`` produces."""

    assert _html_nesting_depth(html) == expected


def test_the_depth_scan_does_not_itself_recurse() -> None:
    """Measuring 100k levels must not need 100k frames.

    The whole point of the scan is to decide whether a recursive parser is
    safe to run, so it cannot be recursive itself.
    """

    assert _html_nesting_depth("<div>" * 100_000) == 100_000


@pytest.mark.parametrize(
    "html",
    [
        pytest.param("<div>" * 500 + "text" + "</div>" * 500, id="balanced"),
        pytest.param("<p>" * 5000 + "text", id="unclosed"),
        pytest.param("<ul><li>" * 500 + "text" + "</li></ul>" * 500, id="lists"),
        pytest.param("<foo>" * 5000 + "<p>text</p>", id="unknown-elements"),
        pytest.param(
            "<table><tr><td>" * 400 + "text" + "</td></tr></table>" * 400,
            id="tables",
        ),
        pytest.param("<div>" * 100_000 + "text", id="absurd"),
    ],
)
def test_deep_html_degrades_instead_of_raising(html: str) -> None:
    """Past the ceiling the caller gets a usable body, not an exception.

    494 levels was enough to exhaust the default 1000-frame limit from a
    shallow stack. Every shape here is past ``MAX_HTML_DEPTH``, including
    the unclosed and unknown-element ones -- both of which the parser nests
    just as deeply as the balanced case.
    """

    assert GlpiContentConverter.from_transport(html) == "text"


def test_the_degraded_path_keeps_every_word() -> None:
    """It degrades; it does not truncate.

    A body too deep to convert is still the only copy of what someone
    wrote, so the fallback's contract is that all of the text comes back.
    """

    lines = [f"line {index}" for index in range(400)]
    html = "".join(f"<div><p>{line}</p>" for line in lines) + "</div>" * 400

    stripped = GlpiContentConverter.from_transport(html)

    assert all(line in stripped for line in lines)
    assert "<" not in stripped


def test_the_degraded_path_resolves_entities_and_block_boundaries() -> None:
    """Blocks become line breaks, inline tags vanish, references resolve.

    Dropping every tag outright would run ``<p>a</p><p>b</p>`` together as
    ``ab``; separating at every tag would break ``<b>off</b>line`` into two
    words. Only the block boundary gets a separator.
    """

    html = "<div>" * 300 + "<b>off</b>line &amp; <p>next</p>" + "</div>" * 300

    assert GlpiContentConverter.from_transport(html) == "offline &\nnext"


@pytest.mark.parametrize(
    ("construct", "kept"),
    [
        pytest.param("<!-- SECRET -->", False, id="resolved-comment"),
        pytest.param("<!DOCTYPE SECRET>", False, id="doctype"),
        pytest.param("<!SECRET>", False, id="bogus-declaration"),
        pytest.param("<script>SECRET</script>", True, id="script-body"),
        pytest.param("<style>SECRET</style>", True, id="style-body"),
        pytest.param("<![CDATA[SECRET]]>", True, id="marked-section"),
        pytest.param("<![CDATA[SECRET>", True, id="unterminated-marked-section"),
        pytest.param("<?php SECRET ?>", True, id="processing-instruction"),
    ],
)
def test_the_degraded_path_keeps_exactly_what_the_converter_keeps(
    construct: str, kept: bool
) -> None:
    """Parity, construct by construct, and not one of these was a guess.

    Each expectation here was read off the converting path rather than
    reasoned about, and three came back the opposite way round from the
    obvious answer -- a ``<script>`` body is *kept*, because
    ``markdownify``'s ``strip=`` removes an element's markup and still
    walks its children; so is a ``CDATA`` body; and so is the inside of
    any construct the parser could not resolve. Each of those was a silent
    deletion in the degraded path until it was measured.

    The bar is that a body must not say less because of the path it took,
    so a divergence here is a bug even when the dropped text is
    JavaScript.
    """

    shallow = f"<p>a</p>{construct}<p>b</p>"
    deep = "<div>" * 300 + shallow + "</div>" * 300

    converted = GlpiContentConverter.from_transport(shallow)
    degraded = GlpiContentConverter.from_transport(deep)

    assert ("SECRET" in converted) is kept
    assert ("SECRET" in degraded) is kept


def test_an_unterminated_raw_text_element_swallows_the_rest_on_both_paths() -> None:
    """The one raw-text case where dropping the body IS parity.

    An unclosed ``<script>`` makes the parser read everything after it as
    script text, and the converting path prints none of it -- so keeping it
    here would be the divergence.
    """

    shallow = "<p>keep</p><script>SECRET"
    deep = "<div>" * 300 + shallow + "</div>" * 300

    assert GlpiContentConverter.from_transport(shallow) == "keep"
    assert GlpiContentConverter.from_transport(deep) == "keep"


def test_a_document_at_the_ceiling_is_still_converted() -> None:
    """The ceiling is inclusive, and below it nothing changes.

    Pinned because an off-by-one here silently downgrades ordinary content
    to stripped text -- a quality regression with no error to notice.
    """

    depth = MAX_HTML_DEPTH - 1  # the <strong> below is the last level
    html = "<div>" * depth + "<strong>offline</strong>" + "</div>" * depth

    assert GlpiContentConverter.from_transport(html) == "**offline**"


def test_void_elements_do_not_spend_the_depth_budget() -> None:
    """5000 ``<br>`` is one level, so this must take the converting path.

    The surviving ``**`` proves it: the degraded path strips markup, so
    emphasis would be gone if the void tags had been counted.
    """

    html = "<p>" + "<br>" * 5000 + "<strong>offline</strong></p>"

    assert "**offline**" in GlpiContentConverter.from_transport(html)


# ---------------------------------------------------------------------------
# Failure taxonomy
# ---------------------------------------------------------------------------


def test_a_parser_fault_surfaces_as_a_glpi_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No parser fault escapes ``except GlpiError``.

    The depth guard means no ordinary input reaches this, so the fault is
    injected. It matters anyway: the frame budget is whatever the caller
    left behind, so a shallow-enough document can still run out of stack in
    a deep-enough application -- and a caller who wrote ``except GlpiError``
    around ``get_ticket`` would have watched a ``RecursionError`` sail
    straight through it.
    """

    def _boom(*args: object, **kwargs: object) -> str:
        raise RecursionError("maximum recursion depth exceeded")

    monkeypatch.setattr(conversion, "html_to_markdown", _boom)

    with pytest.raises(GlpiContentError) as caught:
        GlpiContentConverter.from_transport("<p>offline</p>")

    assert isinstance(caught.value, GlpiError)
    assert isinstance(caught.value.__cause__, RecursionError)


def test_an_outbound_render_fault_surfaces_as_a_glpi_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The outbound direction is wrapped too; ``markdown`` recurses as well."""

    def _boom(*args: object, **kwargs: object) -> str:
        raise RecursionError("maximum recursion depth exceeded")

    monkeypatch.setattr(conversion, "markdown_to_html", _boom)

    with pytest.raises(GlpiContentError) as caught:
        GlpiContentConverter.to_transport("offline")

    assert isinstance(caught.value, GlpiError)
    assert isinstance(caught.value.__cause__, RecursionError)


def test_deeply_nested_markdown_does_not_raise_a_bare_recursion_error() -> None:
    """The real outbound cliff, unmocked.

    ``markdown`` breaks between 495 and 500 levels of list indentation
    (measured). Unlike the inbound direction this is not degraded --
    outbound content is what the caller just wrote, so a failure is worth
    reporting -- but it has to be reported as a library error.
    """

    markdown = "\n".join("  " * level + "- x" for level in range(500))

    with pytest.raises(GlpiContentError):
        GlpiContentConverter.to_transport(markdown)


# ---------------------------------------------------------------------------
# The scan against the tree the parser really builds
# ---------------------------------------------------------------------------
#
# The three cases below are the ones a plain open/close counter gets wrong,
# and the first is not a corner case: a stray ``</p>`` or ``</span>`` is
# what a Word or Outlook paste leaves in a GLPI body. Each was measured
# under-counting -- the one direction that turns into a crash -- before the
# scan learned to pop by name.


def _parser_depth(html: str) -> int:
    """Return the deepest element ``html.parser`` actually builds.

    The ground truth the scan is checked against, walked iteratively so
    that measuring a pathological document does not hit the very limit
    under test.
    """

    soup = BeautifulSoup(html, "html.parser")
    deepest = 0
    pending = [(child, 1) for child in soup.children if getattr(child, "name", None)]
    while pending:
        node, depth = pending.pop()
        deepest = max(deepest, depth)
        pending.extend(
            (child, depth + 1)
            for child in node.children
            if getattr(child, "name", None)
        )
    return deepest


@pytest.mark.parametrize(
    "html",
    [
        pytest.param("<div></p>" * 600 + "kept", id="stray-close-p"),
        pytest.param("<div></span>" * 600 + "kept", id="stray-close-span"),
        pytest.param("<p></b>" * 600 + "kept", id="stray-close-b"),
        pytest.param("<b><i>x</b></i>", id="interleaved"),
        pytest.param("<div>" * 400 + "<br>" + "</div>" * 400, id="void-leaf"),
        pytest.param("<div>" * 400 + "<img/>" + "</div>" * 400, id="self-closed-leaf"),
        pytest.param("<br>" * 5000, id="void-only"),
        pytest.param("<div><b>x</b></br></div>", id="close-of-a-void"),
        pytest.param("<p>The printer is <strong>offline</strong>.</p>", id="realistic"),
        pytest.param("<div><!-- <div><div> --><p>x</p></div>", id="tags-in-a-comment"),
        pytest.param(
            "<div><script>var s='<div><div>'</script>x</div>", id="tags-in-js"
        ),
        pytest.param("<table><tr><td>" * 60 + "x", id="tables"),
        pytest.param("<blockquote>" * 300 + "x", id="blockquotes"),
        pytest.param("<p>a</p>" * 100, id="siblings"),
    ],
)
def test_the_depth_scan_agrees_with_the_parser(html: str) -> None:
    """The flat scan returns what a real parse would nest to.

    Equality, not an upper bound: over-counting is survivable but it
    degrades documents that did not need degrading, so it is worth pinning
    too. The cases where the scan is deliberately allowed to over-count are
    covered separately.
    """

    assert _html_nesting_depth(html) == _parser_depth(html)


@pytest.mark.parametrize(
    "html",
    [
        pytest.param("<div></p>" * 600 + "kept", id="stray-close-p"),
        pytest.param("<div></span>" * 800 + "kept", id="stray-close-span"),
        pytest.param("<li></tr>" * 700 + "kept", id="stray-close-tr"),
    ],
)
def test_a_stray_closing_tag_does_not_hide_real_nesting(html: str) -> None:
    """The regression test for the under-count that reached ``markdownify``.

    A closing tag with no matching open element pops nothing in ``bs4``, so
    these documents nest as deeply as their opening tags say. Counting the
    close as a level down measured them at 1, they went to the recursive
    converter, and it raised.
    """

    assert GlpiContentConverter.from_transport(html) == "kept"


def test_the_degraded_path_keeps_a_cdata_body() -> None:
    """A ``CDATA`` section's body is text, and text is what survives.

    The declaration pattern that strips ``<!DOCTYPE ...>`` reaches the
    first ``>``, and a ``CDATA`` section has none until its end, so it used
    to take the body with it -- a silent deletion in the one path whose
    whole promise is that nothing is deleted.
    """

    html = "<div>" * 300 + "<p>a<![CDATA[secret words]]>b</p>" + "</div>" * 300

    assert GlpiContentConverter.from_transport(html) == "asecret wordsb"


@pytest.mark.parametrize(
    "html",
    [
        # A comment with no ``-->`` is a *bogus comment*: the parser gives up
        # at the first ``>``, so the ``</custom>`` inside it is text and the
        # ``<br>`` lands inside ``<custom>``. Read that ``</custom>`` as a
        # real close and the count comes back one level short -- which is
        # how a document that needed degrading reached the converter.
        pytest.param("<custom><!--oops</custom><br>", id="bogus-comment-eats-a-close"),
        # ... and recovery ends at that ``>``. It does not swallow the rest
        # of the document, so these really are two levels.
        pytest.param("<!--oops><div><div>", id="bogus-comment-ends-at-its-close"),
        # A processing instruction ends at the first ``>`` too, and here
        # that lands inside what looks like a comment -- so the second
        # ``<div>`` is a real element. Stripping comments globally before
        # scanning gets this wrong in both directions at once.
        pytest.param("<?php x<!-- <div><div> -->", id="pi-overlapping-a-comment"),
        pytest.param("<div><!-- <div><div> --></div>", id="terminated-comment"),
        pytest.param("<!DOCTYPE html><div><p>x</p></div>", id="doctype"),
        pytest.param("<div><![CDATA[a<div>b]]><p>x</p></div>", id="marked-section"),
        pytest.param("<div><script>a<div><div></script><p>x</p></div>", id="raw-text"),
        pytest.param("<div><script>a<div>", id="unclosed-raw-text"),
    ],
)
def test_the_depth_scan_dispatches_like_the_parser(html: str) -> None:
    """Comments, declarations and raw text change where the tags are.

    Each of these was measured against a real parse. They are in the suite
    because they are the cases where reading the constructs in the wrong
    order, or independently of one another, changes the answer -- and one
    direction of wrong is a ``RecursionError``.
    """

    assert _html_nesting_depth(html) == _parser_depth(html)


def test_the_degraded_path_keeps_the_text_of_a_broken_comment() -> None:
    """Parity with the normal path, even where the parser gave up.

    ``html.parser`` cannot resolve a comment with no ``-->``, so it hands
    the region back as character data -- meaning ``markdownify`` would have
    kept it. The degraded path is only trustworthy if which path a body
    took never changes what it says, so it keeps it too.
    """

    html = "<div>" * 300 + "<p>keep</p>" + "</div>" * 300 + "<!--oops but keep this"

    stripped = GlpiContentConverter.from_transport(html)

    assert stripped == "keep\n\n<!--oops but keep this"


def test_the_degraded_path_drops_a_comment_the_parser_understood() -> None:
    """A resolved comment is text on neither path, so it goes.

    The mirror of the test above, and the reason the two cannot share one
    rule: telling them apart is the whole job of the ``-->``.
    """

    html = "<div>" * 300 + "<p>keep</p><!-- drop this -->" + "</div>" * 300

    assert GlpiContentConverter.from_transport(html) == "keep"


def test_no_name_in_the_void_set_actually_nests() -> None:
    """The one direction of the void set that would be a crash.

    A name listed as void that the parser really nests hides real depth,
    and the document then reaches the recursive converter. The set is a
    hand-copy of a private ``bs4`` table, so the invariant is asserted
    against a real parse rather than against that table: for every name
    claimed void, 300 of them must build one level, not 300.
    """

    understated = [
        name
        for name in sorted(conversion._VOID_ELEMENTS)
        if _html_nesting_depth(f"<{name}>" * 300 + "x")
        < _parser_depth(f"<{name}>" * 300 + "x")
    ]

    assert understated == []


@pytest.mark.parametrize(
    "html",
    [
        pytest.param('<div title="</div>">x</div>', id="close-tag-in-attribute"),
        pytest.param('<div title="<div>">x</div>', id="open-tag-in-attribute"),
        pytest.param('<div title="a>b">x</div>', id="gt-in-attribute"),
        pytest.param("<div data-x='a>b'><p>x</p></div>", id="single-quoted"),
        pytest.param('<p title=">">one</p><p>two</p>', id="attribute-is-just-gt"),
        pytest.param('<div title="</div>">' * 5 + "x", id="nested-and-quoted"),
    ],
)
def test_a_tag_inside_a_quoted_attribute_is_not_read_as_markup(html: str) -> None:
    """An attribute value may legally contain ``<`` and ``>``.

    Reading a quoted ``</div>`` as a real close tag under-counted without
    bound: ``'<div title="</div>">' * 600`` measured **0** levels when the
    parser builds 600, so the document sailed past the ceiling into
    ``markdownify`` and raised. This is the regression test for that, and
    it is the one class of error the ceiling exists to prevent.
    """

    assert _html_nesting_depth(html) == _parser_depth(html)


def test_a_quoted_close_tag_at_depth_still_degrades() -> None:
    """The same shape scaled past the ceiling: degrades, does not raise."""

    html = '<div title="</div>">' * 600 + "keep"

    assert GlpiContentConverter.from_transport(html) == "keep"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # A URL in a ticket body is exactly where a semicolon-less
        # reference that is a prefix of a longer word shows up.
        ("http://x/?a=1&copyright=2", "http://x/?a=1&copyright=2"),
        ("http://x/?a=1&notanentity=2", "http://x/?a=1&notanentity=2"),
        # Terminated references still resolve, named and numeric.
        ("a &amp; b &lt; c", "a & b < c"),
        ("&#65;&#x42;", "AB"),
        # ... and so does a semicolon-less reference whose whole name is
        # known, because that is what the parser does.
        ("&copy 2026", "\u00a9 2026"),
        ("a&b", "a&b"),
    ],
)
def test_the_degraded_path_resolves_references_like_the_parser(
    raw: str, expected: str
) -> None:
    """``html.unescape`` alone corrupts URLs; the parser's rule does not.

    ``unescape`` implements HTML5's longest-known-*prefix* rule, so
    ``&copyright=2`` comes back as ``(c)right=2`` -- a query parameter
    silently rewritten. The parser behind the converting path resolves a
    semicolon-less reference only when the entire name is known, so it
    leaves that URL alone, and the degraded path has to agree or a body
    changes meaning according to how deeply it nests.
    """

    html = "<div>" * 300 + f"<p>{raw}</p>" + "</div>" * 300

    assert GlpiContentConverter.from_transport(html) == expected
