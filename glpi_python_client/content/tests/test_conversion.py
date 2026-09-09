from __future__ import annotations

import re
from html.parser import HTMLParser

import pytest
from bs4 import BeautifulSoup

from glpi_python_client import GlpiContentError, GlpiError
from glpi_python_client.content import conversion
from glpi_python_client.content.conversion import (
    GlpiContentConverter,
    _strip_tags,
)

#: Everything that is not a letter or a digit.
_NOT_PROSE = re.compile(r"[^0-9A-Za-z]+")

#: A Markdown link or image destination.
#:
#: The converting path renders a target that the fallback documents as
#: dropped -- "a link becomes its text without the target, an image
#: contributes nothing" -- so a URL inside ``]( )`` is not prose either,
#: and comparing it would assert a difference the module declares.
_DESTINATION = re.compile(r"\]\([^)]*\)")

#: A link, and the target only the *converting* path renders.
#:
#: There is no depth number to ask any more -- the converter attempts the
#: walk and answers the ``RecursionError`` -- so a test that needs to know
#: which path ran has to read the output. A link is the cheapest tell:
#: ``markdownify`` writes ``[probe](u)`` and :func:`_strip_tags` writes
#: ``probe``.
PROBE_LINK = '<a href="u">probe</a>'
PROBE_TARGET = "](u)"


def _prose(text: str) -> str:
    """Reduce a rendering to its letters and digits, in order.

    Whitespace falls differently at a markup boundary on the two paths --
    the converter joins ``a<b>c`` as ``a**c**`` where the degraded path
    joins it as ``ac``, and the degraded path breaks a line at a block
    edge the converter runs together -- and the converter adds
    punctuation of its own: table pipes, fence backticks, list bullets,
    link and image brackets. None of that is prose, and none of it is
    what the fallback promises to reproduce.
    """

    return _NOT_PROSE.sub("", _DESTINATION.sub("]", text))


def _is_subsequence(needle: str, haystack: str) -> bool:
    remaining = iter(haystack)
    return all(character in remaining for character in needle)


def _parser_rejects(html: str) -> bool:
    """Return whether ``html.parser`` gives up on this document.

    ``_markupbase`` raises ``AssertionError`` for an unknown
    marked-section keyword, and which keywords count has changed across
    CPython patch releases -- so whether a given document is rejected is
    a question to ask the running interpreter rather than to assume.
    """

    parser = HTMLParser(convert_charrefs=False)
    try:
        parser.feed(html)
        parser.close()
    except AssertionError:
        return True
    return False


def assert_the_degraded_path_says_no_less(shallow: str) -> None:
    """Assert the module's one promise about the fallback, on this parser.

    ``html.parser``'s reading of a *malformed* construct is not stable
    across CPython patch releases. Measured on the same three documents,
    3.12.3, 3.12.11 and 3.12.14 disagree about an unterminated
    ``<script>``, about a comment with no ``-->``, and about an end tag
    carrying a quoted ``>``: each build emits a different set of events.
    Writing down the literal output of one of them made this suite assert
    that interpreter's quirks rather than the module's contract, and it
    duly went red on a patch bump while the module itself was fine.

    So the expectation is computed from the converting path rather than
    written down. Both paths read the same parser, so they move together,
    and the promise was never equality anyway -- it is inclusion: **a
    body must not say less because of the path it took.**
    """

    # The padding is closed *before* the construct rather than wrapped
    # around it. Wrapping changes what the construct means: an
    # unterminated ``<!weird`` runs to the next ``>``, which inside a
    # wrapper is the ``>`` of a ``</div>``, so the same text is a bogus
    # comment there and character data at end of input. The point of the
    # padding is only to be deeper than the converter can walk.
    #
    # The probe link is how the test knows which path ran, now that there
    # is no depth number to consult: only the converting path renders a
    # target, so its absence is the degradation.
    # Both renderings are taken from the *same* document, and the
    # fallback is called directly rather than provoked with a body deep
    # enough to exhaust the stack. Provoking it costs a 600-level tree
    # and a walk that runs until it raises, which under coverage
    # instrumentation took this suite from 69 seconds to 333; and it
    # tests the routing, which one test can do once, rather than the
    # property, which is what every shape here is for.
    #
    # The probe link carries the document onto the HTML path. Without it
    # a fragment whose only tag name is not an element -- ``<scripty>`` --
    # is plain text rather than markup, and the two sides would not be
    # renderings of the same thing.
    document = PROBE_LINK + shallow
    converted = GlpiContentConverter.from_transport(document)
    degraded = _strip_tags(document)

    assert PROBE_TARGET in converted, "the body must reach the converting path"

    assert _is_subsequence(_prose(converted), _prose(degraded)), (
        f"the degraded path said less than the converting one\n"
        f"  converted: {converted!r}\n  degraded:  {degraded!r}"
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
    shallow stack. Every shape here is past it, including the unclosed and
    unknown-element ones -- both of which the parser nests just as deeply
    as the balanced case.
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

    html = "<div>" * 600 + "<b>off</b>line &amp; <p>next</p>" + "</div>" * 600

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
    deep = "<div>" * 600 + shallow + "</div>" * 600

    converted = GlpiContentConverter.from_transport(shallow)
    degraded = GlpiContentConverter.from_transport(deep)

    # ``kept`` records what was measured, and is asserted only where the
    # running parser still agrees with the measurement -- the reading of a
    # malformed construct moves between CPython patch releases, and it is
    # the parity below, not the snapshot, that this module promises.
    if ("SECRET" in converted) is kept:
        assert ("SECRET" in degraded) is kept
    assert not ("SECRET" in converted and "SECRET" not in degraded)


def test_an_unterminated_raw_text_element_reads_the_same_on_both_paths() -> None:
    """Whether an unclosed ``<script>`` body survives is the parser's call.

    It made this test its own snapshot: 3.12.3 discards the body on
    ``close()`` and 3.12.14 flushes it as character data, so the literal
    that was correct on one was wrong on the other. What has to hold on
    either is that the two paths agree.
    """

    assert_the_degraded_path_says_no_less("<p>keep</p><script>SECRET")
    assert "keep" in GlpiContentConverter.from_transport("<p>keep</p><script>SECRET")


@pytest.mark.parametrize("depth", [1, 100, 200, 250, 300])
def test_a_document_the_stack_can_hold_is_converted_in_full(depth: int) -> None:
    """Everything that fits must convert, and structure has to survive.

    This is what attempting the conversion bought. The previous design
    predicted the depth and degraded past a fixed 200, which flattened
    every body between 200 and the real cliff of about 494 -- ordinary
    quoted mail threads among them -- to text, with no error to notice
    and no way for a caller to ask for better. The 300 and 400 cases here
    are the ones that used to come back as prose.
    """

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

    Nothing ordinary reaches this, so the fault is injected. It matters
    anyway: a caller who wrote ``except GlpiError`` around ``get_ticket``
    would otherwise watch a bare parser exception sail straight through
    it.

    A ``RecursionError`` is deliberately *not* the fault used here. It is
    no longer a failure at all -- it is how the converter learns that the
    document does not fit, and it is answered with the body's text; see
    the test below.
    """

    def _boom(*args: object, **kwargs: object) -> str:
        raise ValueError("the parser fell over")

    monkeypatch.setattr(conversion, "html_to_markdown", _boom)

    with pytest.raises(GlpiContentError) as caught:
        GlpiContentConverter.from_transport("<p>offline</p>")

    assert isinstance(caught.value, GlpiError)
    assert isinstance(caught.value.__cause__, ValueError)


def test_a_recursion_error_degrades_rather_than_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Running out of stack is answered, not reported.

    Injected rather than provoked, because the depth needed to provoke it
    depends on the stack the test runner has already spent -- which is the
    very reason the depth is no longer predicted. What is pinned is the
    contract: the caller gets their words, not an exception.
    """

    def _boom(*args: object, **kwargs: object) -> str:
        raise RecursionError("maximum recursion depth exceeded")

    monkeypatch.setattr(conversion, "html_to_markdown", _boom)

    assert (
        GlpiContentConverter.from_transport("<p>Le serveur ne repond plus.</p>")
        == "Le serveur ne repond plus."
    )


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

    html = "<div>" * 600 + "<p>a<![CDATA[secret words]]>b</p>" + "</div>" * 600

    assert GlpiContentConverter.from_transport(html) == "asecret wordsb"


def test_the_degraded_path_keeps_the_text_of_a_broken_comment() -> None:
    """Parity with the normal path, even where the parser gave up.

    ``html.parser`` cannot resolve a comment with no ``-->``, so it hands
    the region back as character data -- meaning ``markdownify`` would have
    kept it. The degraded path is only trustworthy if which path a body
    took never changes what it says, so it keeps it too.
    """

    assert_the_degraded_path_says_no_less("<p>keep</p><!--oops but keep this")


def test_the_degraded_path_drops_a_comment_the_parser_understood() -> None:
    """A resolved comment is text on neither path, so it goes.

    The mirror of the test above, and the reason the two cannot share one
    rule: telling them apart is the whole job of the ``-->``.
    """

    html = "<div>" * 600 + "<p>keep</p><!-- drop this -->" + "</div>" * 600

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
        if _parser_depth(f"<{name}>" * 300 + "x") > 1
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

    Reading a quoted ``</div>`` as a real close tag lost the text after
    it, and used to under-count the nesting without bound as well, back
    when the nesting was predicted. What has to hold either way is that
    the shape costs the body nothing: it converts, and if it is too deep
    to convert it still says the same thing.
    """

    assert_the_degraded_path_says_no_less(html)


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

    html = "<div>" * 600 + f"<p>{raw}</p>" + "</div>" * 600

    assert GlpiContentConverter.from_transport(html) == expected


@pytest.mark.parametrize(
    "prefix",
    [
        pytest.param("<style=>", id="malformed-style-name"),
        pytest.param("<script=>", id="malformed-script-name"),
        pytest.param("<script/>", id="self-closed-script"),
        pytest.param("<style />", id="self-closed-style"),
        pytest.param("<p title=don't>", id="apostrophe-in-bare-value"),
        pytest.param("<p alt=P<0.05>", id="lt-in-bare-value"),
    ],
)
def test_a_malformed_tag_does_not_swallow_the_body_after_it(prefix: str) -> None:
    """One malformed tag must not take the rest of the document with it.

    Read as raw text, ``"<style=>"`` and ``"<script/>"`` swallowed
    everything after them. That showed up first as an unbounded depth
    under-count -- ``"<style=>" + "<div>" * 600`` measured **1** level
    against a real 601 and reached ``markdownify`` -- but the deletion was
    always the real damage, and it is what this pins now that the depth is
    no longer predicted.
    """

    html = prefix + "<div>" * 600 + "the printer is offline"

    assert GlpiContentConverter.from_transport(html) == "the printer is offline"


def test_the_degraded_path_does_not_emit_a_tag_it_could_not_read() -> None:
    """A tag the scan mis-read used to be printed at the reader.

    Measured: the body below degraded to ``"<p title=don't>Le serveur ne
    repond plus."`` -- the opening tag verbatim in text a person reads,
    from a path whose whole promise is text. An apostrophe is ordinary in
    French, so this needs no malice to reach a ticket.
    """

    html = "<div>" * 600 + "<p title=don't>Le serveur ne repond plus.</p>"

    degraded = GlpiContentConverter.from_transport(html)

    assert degraded == "Le serveur ne repond plus."
    assert "<" not in degraded


def test_an_unterminated_declaration_at_end_of_input_is_kept() -> None:
    """``close()`` flushes an incomplete declaration as text, so this does.

    A declaration is text on neither path only when it is *closed*: a
    ``"<!weird"`` that never completes is flushed as character data when
    the parser closes, and the converting path prints it. Dropping it lost
    the tail of the body.
    """

    assert_the_degraded_path_says_no_less("<p>keep this</p><!weird")
    assert "keep this" in GlpiContentConverter.from_transport("<p>keep this</p><!weird")


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        pytest.param(
            "<p>one<br>two<br />three</p>",
            "one  \ntwo  \nthree",
            id="br-both-spellings",
        ),
        pytest.param(
            "<p>Bonjour,<br>Le serveur ne repond plus.<br />Merci de regarder.</p>",
            "Bonjour,  \nLe serveur ne repond plus.  \nMerci de regarder.",
            id="realistic-body",
        ),
        pytest.param(
            "<p>line1<br>line2</p><p>para2<br />line4</p>",
            "line1  \nline2\n\npara2  \nline4",
            id="across-paragraphs",
        ),
        pytest.param(
            "<p>a<br>b<br />c<br>d<br />e</p>",
            "a  \nb  \nc  \nd  \ne",
            id="alternating",
        ),
        pytest.param(
            "<p>one<img>two<img />three</p>",
            "one![]()two![]()three",
            id="img",
        ),
        pytest.param(
            "<p>one<hr>two<hr />three</p>",
            "one\n\n---\n\ntwo\n\n---\n\nthree",
            id="hr",
        ),
    ],
)
def test_a_body_using_both_spellings_of_a_void_tag_keeps_its_text(
    html: str, expected: str
) -> None:
    """Text after the second spelling of ``<br>`` used to be dropped.

    A ``beautifulsoup4`` defect, silent when it fires and reachable from
    ordinary editor output: a bare ``<br>`` leaves its name in
    ``already_closed_empty_element`` for a ``</br>`` that never comes, and
    the next ``<br />`` closes itself against that stale entry and stays
    open. Every later sibling becomes its child, and ``convert_br``
    discards an element's children.

    Note the paragraph case: the two spellings need not be near each
    other, because a name once recorded poisons the rest of the document.
    ``<img>`` and ``<hr>`` are the other two converters that drop
    children, so they lose text the same way.
    """

    assert GlpiContentConverter.from_transport(html) == expected


@pytest.mark.parametrize(
    "html",
    [
        pytest.param("<div/>x", id="self-closed-non-void"),
        pytest.param("<custom />x", id="self-closed-unknown"),
        pytest.param("<p>a<br>b</p>", id="already-bare"),
        pytest.param("<p>2 /> 3</p>", id="slash-gt-in-text"),
        pytest.param('<div title="<br />">x</div>', id="in-an-attribute"),
        pytest.param("<script>var s = '<br />';</script>x", id="in-a-script-body"),
        pytest.param("<!-- <br /> -->x", id="in-a-comment"),
        pytest.param("<p>a<br  /  >b</p>", id="slash-not-abutting-gt"),
    ],
)
def test_the_void_rewrite_leaves_everything_else_alone(html: str) -> None:
    """The rewrite is confined to void tags in real tag position.

    ``<div/>`` is left as it is -- rewriting it would change what the
    document means, and it cannot be affected anyway, since only a void
    name is ever recorded as already closed. The last case is the one
    worth pinning: ``<br  /  >`` reaches the parser as an ordinary start
    tag, because its ``/`` does not abut the ``>``, so it never takes the
    path that loses text and needs no rewriting.
    """

    assert conversion._canonicalise_void_elements(html) == html


def test_the_void_rewrite_changes_nothing_for_one_spelling_alone() -> None:
    """A body that picks a spelling and keeps it converts exactly as before.

    The rewrite exists to remove an asymmetry between two spellings of the
    same node, so it must be invisible to every body that does not mix
    them. Measured over 4000 fuzzed documents of each spelling: not one
    output moved.
    """

    bare = "<p>a<br>b<img><hr>c</p>"
    slashed = "<p>a<br />b<img /><hr />c</p>"

    assert GlpiContentConverter.from_transport(bare) == "a  \nb![]()\n\n---\n\nc"
    assert GlpiContentConverter.from_transport(slashed) == "a  \nb![]()\n\n---\n\nc"


def test_both_paths_agree_on_a_body_using_both_spellings() -> None:
    """The degraded path already kept this text; now the converting one does.

    This body was the one place where the fallback said *more* than the
    conversion it stands in for, which is the wrong way round for a
    fallback and was how the defect was noticed at all.
    """

    shallow = "<p>one<br>two<br />three</p>"
    deep = "<div>" * 600 + shallow + "</div>" * 600

    converted = GlpiContentConverter.from_transport(shallow)
    degraded = GlpiContentConverter.from_transport(deep)

    for word in ("one", "two", "three"):
        assert word in converted
        assert word in degraded


@pytest.mark.parametrize(
    "fragment",
    [
        pytest.param('</x a="><div>">', id="end-tag-with-a-quoted-attribute"),
        pytest.param('<div ="<p>', id="name-less-equals-quote"),
        pytest.param('<p title="><span>">', id="quoted-gt-then-tag"),
    ],
)
def test_a_misread_tag_end_does_not_swallow_the_body_after_it(fragment: str) -> None:
    """Scaled past the cliff: degrades quietly, and keeps its words.

    Reading an end tag with start-tag rules consumed everything up to the
    next quote, which deleted prose at any depth and under-counted the
    nesting 1:1 with the repetition back when the nesting was predicted.
    """

    html = fragment * 600 + "the printer is offline"

    assert "the printer is offline" in GlpiContentConverter.from_transport(html)


def test_a_misread_tag_end_does_not_delete_prose() -> None:
    """The other half of the same defect, and it needs no depth at all.

    Reading an end tag with attribute rules consumed everything between
    the opening quote and its partner, so a degraded body said less than
    the converting one -- the divergence the parity test forbids.
    """

    body = '<p>Bonjour</p title="> Le serveur ne repond plus. SECRET ">fin'

    assert_the_degraded_path_says_no_less(body)
    assert "Bonjour" in GlpiContentConverter.from_transport(body)


def test_a_document_with_no_closing_bracket_is_answered_without_scanning() -> None:
    """No ``>`` means no element, and saying so keeps a bad shape cheap.

    ``html.parser`` cannot finish a tag that never closes, so ``close()``
    flushes it one character at a time and rescans the tail at each step:
    measured, 32 KB of ``'<div a="'`` costs it 13 seconds. Both readers
    answer that shape directly instead. The text still survives, because
    the parser flushes an unfinished tag as data when it closes.
    """

    html = '<div a="' * 4000

    assert GlpiContentConverter.from_transport(html).startswith('<div a="')
    assert "the printer" in GlpiContentConverter.from_transport(html + "the printer")
    assert _strip_tags(html).startswith('<div a="')


def test_a_document_the_parser_rejects_degrades_instead_of_raising() -> None:
    """An unknown marked-section keyword stops the parser, not the body.

    ``_markupbase.parse_marked_section`` raises ``AssertionError`` for a
    keyword it does not know, and ``bs4`` catches that same
    ``AssertionError`` and re-raises it as ``ParserRejectedMarkup``. So a
    document carrying ``<![FOO[`` is one the converting path cannot
    convert either, and the old behaviour was to let it try and fail:
    the caller got a :class:`GlpiContentError` and none of their text.

    Reporting a depth past the ceiling instead sends it down the degraded
    path, where it yields its words. Degrading beats raising when the
    alternative is a body nobody can read.
    """

    html = "<p>Le serveur ne repond plus. SECRET</p><![FOO[x]]>"

    assert "SECRET" in GlpiContentConverter.from_transport(html)
    if _parser_rejects(html):
        # The converting path cannot run at all, so the answer is the text.
        assert GlpiContentConverter.from_transport(html) == _strip_tags(html)


def test_the_text_after_a_construct_the_parser_rejects_is_still_kept() -> None:
    """The give-up point is not the end of the body.

    The scan stops where the parser stopped, so everything past that
    construct would go missing unless it is handed back explicitly --
    and a body is far more likely to carry the marked section in the
    middle than at the end.
    """

    html = "<p>avant</p><![FOO[x]]><p>apres SECRET</p>"

    assert "avant" in _strip_tags(html)
    assert "SECRET" in _strip_tags(html)
    assert "SECRET" in GlpiContentConverter.from_transport(html)
    assert "avant" in GlpiContentConverter.from_transport(html)


def test_stripping_a_document_with_no_closing_bracket_keeps_all_of_it() -> None:
    """The degraded path needs the same guard the depth scan needs.

    ``html.parser`` cannot complete a tag that never closes, so
    ``close()`` flushes it one character at a time and rescans the tail
    at each step: measured, 32 KB of ``'<div a="'`` costs it 13 seconds.
    The whole document is that unfinished tag's text, which is the answer
    the guard returns directly.
    """

    html = '<div a="' * 4000 + "le serveur ne repond plus"

    assert _strip_tags(html).endswith("le serveur ne repond plus")
    assert _strip_tags(html).startswith('<div a="')


@pytest.mark.parametrize(
    "html",
    [
        # The repetition counts here are deliberately modest. They were
        # large when this corpus guarded a depth *prediction*, where the
        # error grew with the repetition; the shapes are what matter now,
        # and each document has to be one the converting path can still
        # walk on every supported interpreter for the comparison to mean
        # anything.
        pytest.param("<div></p>" * 60 + "kept", id="stray-close-p"),
        pytest.param("<div></span>" * 60 + "kept", id="stray-close-span"),
        pytest.param("<p></b>" * 60 + "kept", id="stray-close-b"),
        pytest.param("<b><i>x</b></i>", id="interleaved"),
        pytest.param("<div>" * 100 + "<br>" + "</div>" * 100, id="void-leaf"),
        pytest.param("<div>" * 100 + "<img/>" + "</div>" * 100, id="self-closed-leaf"),
        pytest.param("<br>" * 5000, id="void-only"),
        pytest.param("<div><b>x</b></br></div>", id="close-of-a-void"),
        pytest.param("<p>The printer is <strong>offline</strong>.</p>", id="realistic"),
        pytest.param("<div><!-- <div><div> --><p>x</p></div>", id="tags-in-a-comment"),
        pytest.param(
            "<div><script>var s='<div><div>'</script>x</div>", id="tags-in-js"
        ),
        pytest.param("<table><tr><td>" * 30 + "x", id="tables"),
        pytest.param("<blockquote>" * 100 + "x", id="blockquotes"),
        pytest.param("<p>a</p>" * 100, id="siblings"),
    ],
)
def test_both_paths_agree_about_what_is_markup(html: str) -> None:
    """The two renderings of one body must not disagree about its markup.

    This corpus was built against a flat scan that predicted the nesting
    depth, and it caught the scan reading markup differently from the
    parser -- a stray close popping an element the parser keeps, a void
    element counted as a parent, a tag inside a comment or a script body
    counted at all. The prediction is gone; the corpus is not, because
    the same disagreements would now show up as the fallback deleting or
    inventing text relative to the converting path.
    """

    assert_the_degraded_path_says_no_less(html)


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
def test_every_markup_construct_is_read_the_way_the_parser_reads_it(html: str) -> None:
    """Construct by construct, and the order they are tried in matters.

    The parser reads left to right and these constructs overlap: in
    ``<?php x<!-- <div><div> -->`` the processing instruction ends at the
    first ``>``, which lands inside what looks like a comment, so the
    ``<div>`` after it is a real element. Handling any of them out of
    order gets that document wrong in both directions at once.
    """

    assert_the_degraded_path_says_no_less(html)


@pytest.mark.parametrize(
    "html",
    [
        pytest.param("<p title=don't>x</p>", id="apostrophe-in-bare-value"),
        pytest.param('<p title=say"hi>x</p>', id="quote-in-bare-value"),
        pytest.param("<p alt=P<0.05>x</p>", id="lt-in-bare-value"),
        pytest.param("<p title=Etape 1>x</p>", id="space-in-bare-value"),
        pytest.param("<style=>x", id="malformed-style-name"),
        pytest.param("<script=>x", id="malformed-script-name"),
        pytest.param("<div=x>y", id="malformed-name"),
        pytest.param('<div"a">y', id="quote-in-name"),
        pytest.param("<scripty>x</scripty>", id="raw-name-is-a-prefix"),
        pytest.param("<script/>x", id="self-closed-script"),
        pytest.param("<style />x", id="self-closed-style"),
        pytest.param('<li y=">mot<script data-x="</div>">tail', id="lt-after-value"),
        pytest.param("<div a=1 <p>text", id="tag-inside-a-tag"),
        pytest.param("<div class=a<b>text", id="lt-in-unquoted-value"),
    ],
)
def test_a_malformed_tag_is_read_the_way_the_parser_reads_it(html: str) -> None:
    """Malformed markup is where every rule taken from the spec was wrong.

    Each shape here was read one way by the HTML5 grammar and another by
    ``tagfind_tolerant`` and ``locatestarttagend_tolerant``, which are
    what ``markdownify`` actually builds its tree with. The module reads
    the parser's events now, so the corpus is a guard against a future
    change reintroducing a rule from the wrong place.
    """

    assert_the_degraded_path_says_no_less(html)


@pytest.mark.parametrize(
    ("html", "reason"),
    [
        pytest.param(
            '</x a="><div>">',
            "an end tag skips nothing, so the <div> after it is real",
            id="end-tag-with-a-quoted-attribute",
        ),
        pytest.param(
            '<div ="<p><p>">',
            "a name-less = starts an attribute NAME, not a quoted value",
            id="name-less-equals-quote",
        ),
        pytest.param(
            '<div a ="x>y">',
            "whitespace before = still leaves a quoted value",
            id="space-before-equals",
        ),
        pytest.param(
            "</ p>x",
            "the strict end-tag pattern allows space after </",
            id="space-in-end-tag",
        ),
        pytest.param("</p/>x", "a trailing slash on an end tag", id="slash-in-end-tag"),
        pytest.param(
            '<li y=">mot<script data-x="</div>">tail',
            "< inside a tag",
            id="lt-after-a-value",
        ),
    ],
)
def test_a_tag_end_is_read_the_way_the_parser_reads_it(html: str, reason: str) -> None:
    """``parse_endtag`` falls back to ``rawdata.find(">")`` and skips nothing.

    CPython's own comment concedes the consequence -- "this is not 100%
    correct, since we might have things like ``</tag attr=">">``" -- so
    an end tag read with attribute rules consumes prose the parser keeps.
    """

    assert_the_degraded_path_says_no_less(html)


def test_the_fallback_does_not_itself_recurse() -> None:
    """Stripping 100k levels must not need 100k frames.

    The fallback exists because the converting path ran out of stack, so
    it cannot want a stack of its own. ``html.parser`` is an iterative
    scanner and this walks its events into a list, which is what makes it
    an answer for input of any depth rather than a second thing to guard.
    """

    assert _strip_tags("<div>" * 100_000 + "le serveur") == "le serveur"
