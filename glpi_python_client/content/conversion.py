"""Content conversion helpers for GLPI payloads.

This module translates between GLPI's HTML transport format and the
package's canonical Markdown representation used by the rich content
models.

Literal text
------------

**Text in the HTML is literal, and the Markdown spells it so.** A user who
types ``__init__`` into GLPI means eight characters; Markdown reads the
same eight as bold ``init``. So :meth:`GlpiContentConverter.from_transport`
escapes a character exactly where python-markdown -- with this module's
extensions, which is what :meth:`GlpiContentConverter.to_transport` and any
peer rendering the Markdown uses -- would otherwise read it as syntax, and
nowhere else. It has to happen here: once the Markdown is written, nothing
can tell a literal ``__`` from a bold one any more. The rule set is
documented on :class:`_LiteralSafeConverter`; the property it is held to is
that ``to_transport(from_transport(html))`` displays what ``html``
displays, and that the Markdown is a fixed point of the round trip.

Ordinary prose carries no escape at all -- ``fichier_de_test_v2.xlsx``,
``C:\\Temp\\logs``, a ``#`` or a ``-`` mid-sentence, ``R&D`` -- because
python-markdown already renders those literally. What is escaped is what it
would not: ``\\\\serveur`` (it would lose a backslash), ``__init__``, a
``#4521`` or a ``> merci`` at the start of a line, a ``|`` in a table cell,
``<Enter>``, ``&amp;``. None of this is visible to anyone reading the ticket
in either ITSM: the escapes exist only in the Markdown between them.

Neither *parse* recurses -- ``html.parser`` is an iterative scanner --
but ``markdownify`` walks the finished tree recursively, at about two
CPython frames per nesting level, so inbound conversion has a nesting
ceiling. Measured from a shallow stack against the default 1000-frame
limit, the deepest document that converts is 494 levels: the same 494
for ``<div>``, ``<p>``, ``<blockquote>`` and ``<table><tr><td>``, and
495 for ``<ul><li>``, which is what identifies the cost as per-level.

**The ceiling is discovered rather than predicted.** Inbound conversion
is attempted, and a ``RecursionError`` is caught and answered by
stripping the document to its text instead -- see
:meth:`GlpiContentConverter.from_transport`. Estimating the depth up
front and degrading past a fixed bound was the previous design, and it
was wrong in both directions: it degraded bodies that would have
converted, because the bound had to assume the worst about the caller's
remaining stack, and three rounds of review found seven ways for the
estimate to come in *under* the real tree, each of which put a document
through ``markdownify`` and into the ``RecursionError`` the bound
existed to prevent. Trying the conversion cannot be wrong about whether
the conversion fits.

Anything else that goes wrong in either direction surfaces as
:class:`~glpi_python_client.GlpiContentError`, so no parser fault
escapes the package's exception taxonomy.

**``sys.setrecursionlimit`` is deliberately not called, here or anywhere
in the package.** It is process-global state that belongs to the
application, not to a library an application imported; and raising the
limit past what the C stack can hold turns a catchable
``RecursionError`` into a hard interpreter crash -- on Windows, an
access violation with no traceback. It moves the cliff and makes falling
off it worse. Degrading the one body that does not fit is the answer
that does not. Running the walk in a thread with a larger stack was
considered and rejected for the same reason: the recursion limit is a
counter rather than a measurement of the stack, so a deeper thread still
needs the global limit raised to use it.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from html import unescape
from html.entities import html5 as _HTML5_REFERENCES
from html.parser import HTMLParser
from itertools import chain
from typing import Any, NamedTuple

from bs4 import Comment, Doctype, ParserRejectedMarkup, Tag
from bs4.element import PageElement
from markdown import Markdown
from markdown import markdown as markdown_to_html
from markdown.blockprocessors import HRProcessor, ReferenceProcessor
from markdown.inlinepatterns import (
    AUTOLINK_RE,
    AUTOMAIL_RE,
    BACKTICK_RE,
    NOT_STRONG_RE,
)
from markdownify import MarkdownConverter

from glpi_python_client._errors import GlpiContentError

#: Element names that make a ``<...>`` sequence markup rather than text.
#:
#: The HTML5 element set, which is what the parser behind ``markdownify``
#: will actually recognise. Anything outside it -- ``<Enter>``, ``<T>``,
#: ``</dev/null>`` -- parses as an *unknown* tag, whose markup is dropped
#: while its (usually empty) body is kept, so the token silently vanishes
#: from the middle of a sentence.
#:
#: The second group is the HTML standard's *obsolete* elements -- its list
#: of features that "must not be used by authors", which old editors and
#: e-mail clients write all the same. Without them a body marked up only with
#: ``<font color="red">URGENT</font>`` or ``<center>`` failed the probe, took
#: the plain-text path and kept its tags as text.
_HTML_ELEMENTS = frozenset(
    """
    a abbr address area article aside audio b base bdi bdo blockquote body br
    button canvas caption cite code col colgroup data datalist dd del details
    dfn dialog div dl dt em embed fieldset figcaption figure footer form h1 h2
    h3 h4 h5 h6 head header hgroup hr html i iframe img input ins kbd label
    legend li link main map mark menu meta meter nav noscript object ol optgroup
    option output p param picture pre progress q rp rt ruby s samp script search
    section select slot small source span strong style sub summary sup table
    tbody td template textarea tfoot th thead time title tr track u ul var video
    wbr

    acronym applet basefont bgsound big blink center dir font frame frameset
    isindex keygen listing marquee menuitem multicol nextid nobr noembed
    noframes plaintext rb rtc spacer strike tt xmp
    """.split()
)

#: python-markdown extensions applied when rendering outbound content.
#:
#: ``fenced_code`` and ``tables`` are here because without them the two
#: constructs do not survive at all. A fence rendered without
#: ``fenced_code`` becomes inline ``<code>``, which the GLPI web UI shows
#: as one run-on line and which a later read writes back as inline code --
#: so a pasted log degrades a little more on every edit. A table without
#: ``tables`` renders as literal pipe characters.
#:
#: A language tag is still lost: ``markdownify`` drops the
#: ``class="language-python"`` that ``fenced_code`` emits, so ```` ```python ````
#: comes back as a bare fence. That is a limitation of the pair of
#: libraries, not something an extension list can fix.
_MARKDOWN_EXTENSIONS = ["nl2br", "sane_lists", "fenced_code", "tables"]

#: One candidate tag: ``<`` or ``</`` immediately followed by a name.
#:
#: The ``<`` must abut the name, matching what an HTML parser accepts. That
#: is what keeps ``2 < 3 > 1`` and ``x <= y`` text: a space after ``<``
#: means no tag, so arithmetic never reaches the HTML path in the first
#: place.
_CANDIDATE_TAG = re.compile(r"</?([a-zA-Z][a-zA-Z0-9]*)\b[^<>]*>")

#: Elements that cannot contain anything, so nothing nests below them.
#:
#: ``html.parser`` -- the parser ``markdownify`` builds its tree with --
#: closes these itself, so ``<br>`` a thousand times over is a thousand
#: siblings, not a thousand levels. Measured: ``"<br>" * 5000`` parses one
#: level deep and converts fine, while ``"<div>" * 5000`` parses 5000 deep
#: and raises.
#:
#: The HTML5 void set, plus the ten legacy names ``bs4``'s HTML-parser tree
#: builder also treats as empty. **The invariant is that this stays a
#: subset of what the parser treats as empty**, and the direction matters:
#: a name missing from here is counted as nesting when it does not, which
#: costs an unnecessary degradation, while a name wrongly *in* here hides
#: real nesting, which is a ``RecursionError``. Listing the legacy names
#: only makes the count exact on old markup. Copied rather than imported --
#: it lives in ``bs4.builder`` as
#: ``HTMLTreeBuilder.DEFAULT_EMPTY_ELEMENT_TAGS``, which ``bs4``'s own
#: documentation marks ``:meta private:`` -- and the subset invariant is
#: asserted against a real parse in the unit tests, so a future ``bs4``
#: cannot quietly break it. The two sets currently hold the same 24 names.
_VOID_ELEMENTS = frozenset(
    """
    area base basefont bgsound br col command embed frame hr image img
    input isindex keygen link menuitem meta nextid param source spacer
    track wbr
    """.split()
)

#: Elements whose boundary becomes a line break when tags are stripped.
#:
#: Used only by :func:`_strip_tags`. Removing a block element outright runs
#: its neighbours together -- ``<p>a</p><p>b</p>`` becomes ``ab`` -- while
#: putting a separator at *every* tag breaks words apart, turning
#: ``<b>off</b>line`` into ``off line``. Splitting on the block/inline line
#: keeps both readable. An unrecognised name counts as inline, matching how
#: the normal path treats it: markup dropped, body kept in place.
_BLOCK_ELEMENTS = frozenset(
    """
    address article aside blockquote br center col dd details dialog dir div
    dl dt fieldset figcaption figure footer form h1 h2 h3 h4 h5 h6 header
    hgroup hr li main menu nav ol p pre search section summary table tbody td
    tfoot th thead tr ul
    """.split()
)


#: One character reference, with or without its terminating semicolon.
#:
#: Resolved by :func:`_resolve_references` rather than by ``html.unescape``
#: over the whole string. ``unescape`` implements the HTML5 rule of
#: consuming the longest *known* name it can find, so a semicolon-less
#: reference that is a prefix of a longer unknown word gets split --
#: measured, ``http://x/?a=1&copyright=2`` becomes
#: ``http://x/?a=1©right=2``, and a URL pasted into a ticket is exactly
#: where ``&copyright=`` and ``&notanentity=`` occur. The parser behind the
#: converting path leaves those whole, so this does too.
_CHARACTER_REFERENCE = re.compile(
    r"&(?:\#[0-9]+;?|\#[xX][0-9a-fA-F]+;?|[A-Za-z][A-Za-z0-9]*;?)"
)


#: The ``/`` of a self-closing tag, with any space around it.
_VOID_SELF_CLOSE = re.compile(r"\s*/\s*>$")


def _resolve_references(text: str) -> str:
    """Resolve character references the way the real parser would.

    A numeric reference always resolves. A named one resolves only when
    the whole name is known, which is the difference from
    ``html.unescape``: that consumes the longest known *prefix*, so
    ``&copyright=2`` loses its ``&copy`` and leaves ``right=2`` behind.
    See :data:`_CHARACTER_REFERENCE`.

    Where the two rules differ this one keeps the reference literal, which
    is the safe direction for :func:`_strip_tags`, whose promise is that no
    text goes missing.
    """

    def resolve(match: re.Match[str]) -> str:
        token = match.group(0)
        if token[1] == "#":
            return unescape(token)
        return unescape(token) if token[1:] in _HTML5_REFERENCES else token

    return _CHARACTER_REFERENCE.sub(resolve, text)


def _looks_like_html(content: str) -> bool:
    """Return whether ``content`` carries at least one real HTML element.

    Deciding on the element *name* rather than on the presence of angle
    brackets is what separates markup from prose that merely contains
    ``<`` and ``>``. It cannot separate them perfectly: ``a<b>c`` is
    genuinely ambiguous, because ``b`` is both a real element and a
    plausible variable, and no probe reading the text alone can resolve
    that. It resolves every case where the name is not an element at all,
    which is where the silent deletions came from.
    """

    return any(
        match.group(1).lower() in _HTML_ELEMENTS
        for match in _CANDIDATE_TAG.finditer(content)
    )


class _ParserScan(HTMLParser):
    """Walk a document with the parser that will convert it, not one like it.

    Both remaining questions this module asks about raw HTML -- which
    self-closing void tags to rewrite, and what the text is when the tree
    will not fit the stack -- are questions about ``html.parser``'s
    dispatch. This subclass asks ``html.parser`` instead of describing
    it.

    It replaces a regular expression that reproduced that dispatch by
    imitation, and the imitation kept being wrong in ways that showed up
    only after they shipped. A comment closes on ``--\\s*>``
    and not only on ``-->``, ``</ script>`` ends raw text, ``<![IGNORE[``
    opens a marked section, ``</ div foo>`` is a bogus comment rather than
    an end tag, and ``<a href=/>`` leaves an element *open* because the
    unquoted value swallows the ``/``. Two more were cost rather than
    correctness: a run of whitespace inside a failing tag made the
    attribute pattern backtrack as ``(a+)*``, and a 39-byte body took
    20.8 seconds.

    Those seven were found as depth under-counts, back when this module
    predicted the nesting depth instead of attempting the conversion.
    Predicting it is gone, but the pattern's other two readers were wrong
    the same way and are still here: a derailed scan meant
    :func:`_canonicalise_void_elements` never saw the ``<br />`` it
    exists to rewrite, so
    ``"<p>one<br>two</p><script>x</ script><p>three<br />TAIL</p>"`` lost
    ``TAIL`` outright, and :func:`_strip_tags` inherited both the
    misreadings and the backtracking.

    Reading the parser's own event stream cannot be wrong about the
    parser, so none of those remain judgement calls. It is also not a new
    dependency nor a new risk: ``markdownify`` builds its tree with
    ``bs4``, and ``bs4`` builds it with this same ``html.parser``, so
    every pathology the parser has was already in the pipeline. Measured
    on the shapes that made the pattern backtrack, the ``markdownify``
    call costs what this scan costs, to within a few per cent.

    ``convert_charrefs`` is ``False`` because that is what ``bs4`` passes
    (in ``bs4.builder._htmlparser``), and the difference shows: with it
    on, ``html.unescape`` consumes the longest *known* name, so
    ``&copyright=2`` in a pasted URL loses its ``&copy``. Off, each
    reference arrives as its own event and :func:`_resolve_references`
    applies the whole-name rule the converting path applies.

    ``collect_text`` separates the two callers: the void rewrite needs
    only the spans, and accumulating the pieces of a 150 KB body for it
    would be waste.

    Parameters
    ----------
    content : str
        The document to walk. Kept so spans can be sliced back out of it:
        the parser reports what it found and where, and the source is the
        only place the exact original spelling still exists.
    collect_text : bool, optional
        Whether to accumulate :attr:`pieces` for :func:`_strip_tags`.
    """

    def __init__(self, content: str, *, collect_text: bool = False) -> None:
        super().__init__(convert_charrefs=False)
        self._content = content
        self._collect_text = collect_text
        offsets = [0]
        for line in content.splitlines(keepends=True):
            offsets.append(offsets[-1] + len(line))
        self._line_offsets = offsets
        #: Source spans of ``<void ... />`` tags, for
        #: :func:`_canonicalise_void_elements`.
        self.void_spans: list[tuple[int, int]] = []
        #: The document's text, in order, when ``collect_text`` is set.
        self.pieces: list[str] = []
        #: Set when ``html.parser`` gave up on the document.
        self.rejected = False

    def _at(self) -> int:
        """Return the absolute offset of the construct being handled.

        ``goahead`` calls ``updatepos`` up to the start of each construct
        before dispatching it, so ``getpos`` addresses the construct
        itself. It reports a line and a column, and every span sliced
        here needs an index, which is what the line table built in
        ``__init__`` converts between.
        """

        lineno, offset = self.getpos()
        return self._line_offsets[lineno - 1] + offset

    def _text(self, piece: str) -> None:
        if self._collect_text:
            self.pieces.append(piece)

    def _boundary(self, tag: str) -> None:
        """Record a block element's edge as a line break.

        See :data:`_BLOCK_ELEMENTS` for why the block/inline line is the
        one that matters here.
        """

        if self._collect_text and tag in _BLOCK_ELEMENTS:
            self.pieces.append("\n")

    def handle_starttag(self, tag: str, attrs: object) -> None:
        self._boundary(tag)

    def handle_startendtag(self, tag: str, attrs: object) -> None:
        """Count a ``<foo/>`` as a leaf, and note a void one to rewrite.

        This is the event :func:`_canonicalise_void_elements` needs, and
        the one a pattern cannot identify reliably. ``html.parser``
        reaches it only when the stripped remainder of the tag is exactly
        ``/>``, so ``<br />`` arrives here while ``<br  /  >`` is an
        ordinary start tag. Deciding it on the event means the workaround
        fires on exactly the tags that trigger the ``bs4`` defect, and on
        no others.
        """

        if tag in _VOID_ELEMENTS:
            token = self.get_starttag_text()
            start = self._at()
            if token is not None and self._content.startswith(token, start):
                self.void_spans.append((start, start + len(token)))
        self._boundary(tag)

    def handle_endtag(self, tag: str) -> None:
        self._boundary(tag)

    def handle_data(self, data: str) -> None:
        """Keep character data, a raw-text element's body included.

        A ``<script>`` or ``<style>`` body arrives here because the parser
        is in CDATA mode. The converting path drops such a body -- a
        browser displays none of it -- and this keeps it anyway, which is
        the safe direction for a fallback whose promise is that it says no
        less than the conversion: see :func:`_strip_tags`.
        """

        self._text(data)

    def handle_entityref(self, name: str) -> None:
        self._text(self._reference_at())

    def handle_charref(self, name: str) -> None:
        self._text(self._reference_at())

    def _reference_at(self) -> str:
        """Return a character reference exactly as it was written.

        The event carries the name but not whether a semicolon closed it,
        and that is what decides whether the reference resolves -- so the
        source is re-read rather than the token rebuilt from the name.
        See :data:`_CHARACTER_REFERENCE`.
        """

        match = _CHARACTER_REFERENCE.match(self._content, self._at())
        return match.group(0) if match is not None else ""

    def handle_pi(self, data: str) -> None:
        """Keep a processing instruction's body, which the converter prints.

        Measured, not assumed, and the delimiters are the detail that
        matters: ``bs4`` files the instruction as a string node, so
        ``<p>a</p><?php SECRET ?><p>b</p>`` converts to
        ``"a\\n\\nphp SECRET ?\\n\\nb"`` -- the body, without its ``<?``
        and ``>``. Keeping the body alone therefore matches the
        converting path exactly, where keeping the whole construct used
        to leave punctuation in an output that promises none.
        """

        self._text(data)

    def keep_remainder(self) -> None:
        """Hand back the text of the region the parser stopped on.

        Called only when it raised, so that the degraded path still
        carries every word after the construct it could not read.
        """

        self._text(self._content[self._at() :])

    def unknown_decl(self, data: str) -> None:
        """Keep the body of a ``CDATA`` section or a marked section.

        Counter-intuitive, and measured rather than assumed: ``bs4`` files
        both as a string node, and ``markdownify`` prints a string node
        that is neither a comment nor a doctype. So ``<![IGNORE[x]]>``
        contributes ``IGNORE[x`` to the converted output, and dropping it
        here would make the same document say less on the degraded path
        than on the converting one.
        """

        self._text(data[6:] if data.startswith("CDATA[") else data)


def _scan(content: str, *, collect_text: bool = False) -> _ParserScan:
    """Run one :class:`_ParserScan` over ``content`` and hand it back.

    The parser gives up on two constructs -- an unknown marked-section
    keyword such as ``<![FOO[``, and a ``[`` where a declaration cannot
    hold one -- by raising ``AssertionError`` from ``_markupbase``. That
    is not a case to guess around, because ``bs4`` catches the same
    ``AssertionError`` and re-raises it as ``ParserRejectedMarkup``: a
    document that stops this scan is a document ``markdownify`` cannot
    convert either. So the partial scan is kept and the remainder of the
    source is handed to :attr:`_ParserScan.pieces` as text, which is what
    lets :meth:`GlpiContentConverter.from_transport` answer that
    rejection with the body's words instead of an exception.

    Parameters
    ----------
    content : str
        The document to walk.
    collect_text : bool, optional
        Whether the scan should accumulate the document's text.

    Returns
    -------
    _ParserScan
        The finished scan, whether or not the parser ran out of document.
    """

    scan = _ParserScan(content, collect_text=collect_text)
    try:
        scan.feed(content)
        scan.close()
    except AssertionError:
        scan.rejected = True
        scan.keep_remainder()
    return scan


def _strip_tags(content: str) -> str:
    """Reduce HTML to its text without building a tree, keeping every word.

    The fallback for a document ``markdownify`` could not walk -- deeper
    than the caller's remaining stack, or refused by the parser outright.
    One pass of :class:`_ParserScan`, then whitespace tidying. No tree,
    no recursion and no ceiling of its own, which is what qualifies it as
    the fallback: it answers for input of any shape and any depth, so
    there is always something to give the caller.

    It **degrades and never truncates.** The property, stated as
    something checkable: after collapsing whitespace, every character the
    converting path would have produced also appears here, in order. A
    superset, not an equality -- so no body says less because of the path
    it took, which is the only guarantee worth making about a fallback.

    Establishing that meant measuring what the converting path really
    keeps, construct by construct, rather than assuming. Two answers were
    counter-intuitive and each was a silent deletion here before it was
    checked: a ``CDATA`` body is kept, and so is the inside of any
    ``<!``/``<?`` construct the parser could not resolve, which it hands
    back as character data. A ``<script>``/``<style>``/``<title>`` body
    goes the other way: the converting path drops it, as a browser does,
    and this keeps it, which the superset promise allows.

    The text is plain, not Markdown: :meth:`GlpiContentConverter.from_transport`
    spells it through :func:`_literal_markdown` before handing it back, so
    it is escaped exactly as the converting path escapes literal text.

    What it does **not** reproduce, none of which loses a character of
    prose:

    * Markup that only the converter can express: a link becomes its text
      without the target, an image contributes nothing, and a fenced
      block loses its fence -- so ``<pre>`` indentation is normalised
      away with the rest. A pasted log comes back as its own lines of
      text, not as a code block.
    * Whitespace is normalised harder. Runs of spaces collapse, and
      ``&nbsp;`` counts as whitespace, so ``&nbsp;``-padded column
      alignment does not survive.
    * Character references are resolved even inside a region the parser
      handed back as raw data, so a broken comment's ``&amp;`` comes back
      as ``&``. In the other direction, a handful of semicolon-less
      references stay literal here that the converter resolves -- see
      :func:`_resolve_references`, which errs that way on purpose.
    * Whitespace falls differently at a markup boundary, in both
      directions: the converter joins ``a<b>c`` as ``a**c**`` where this
      joins it as ``ac``, and this breaks a line at a block edge the
      converter runs together. Which is why the property is about the
      order of the characters of prose and not about where the spaces
      land.

    Parameters
    ----------
    content : str
        Raw HTML.

    Returns
    -------
    str
        The document's text, block boundaries preserved as line breaks
        and character references resolved.
    """

    if ">" not in content:
        # No ``>`` means no markup to skip, so the whole document is the
        # text the parser would flush on ``close()``. Answering it here
        # also keeps the scan away from the one shape that costs
        # ``html.parser`` more than linear time: with no ``>`` to finish a
        # tag, ``close()`` advances one character at a time and rescans
        # the tail, and 32 KB of an unfinished tag takes 13 seconds.
        text = _resolve_references(content)
    else:
        text = _resolve_references("".join(_scan(content, collect_text=True).pieces))
    text = re.sub(r"[^\S\n]*\n[^\S\n]*", "\n", text)
    text = re.sub(r"[^\S\n]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _canonicalise_void_elements(content: str) -> str:
    """Rewrite ``<br />`` as ``<br>``, so the text after it is not lost.

    A workaround for a ``beautifulsoup4`` defect (measured on 4.14.3),
    reachable from ordinary editor output and silent when it fires.

    ``bs4``'s ``html.parser`` builder auto-closes a bare ``<br>`` and
    records the name in ``already_closed_empty_element``, a list keyed by
    name alone, so a later ``</br>`` can be ignored as redundant. If no
    ``</br>`` ever arrives the entry simply stays there. The next
    ``<br />`` -- which reaches the builder as ``handle_startendtag`` --
    opens a real element and then closes it itself, and *that* close
    finds the stale entry, treats the element as already closed, and
    leaves it open. Every following sibling becomes a child of the
    ``<br>``.

    ``get_text`` still walks those children, which is why the tree looks
    intact, but ``markdownify``'s ``convert_br`` ignores an element's
    children and returns a line break. The text is gone:

    ``"<p>line1<br>line2</p><p>para2<br />line4</p>"`` converted to
    ``"line1  \\nline2\\n\\npara2"`` -- and note the two spellings are in
    different paragraphs, because a name once recorded poisons the rest
    of the document. ``<img>`` and ``<hr>`` lose text the same way; they
    are the other two converters that discard children. One bare ``<br>``
    anywhere before one ``<br />`` is the whole precondition, and GLPI
    bodies are edited by more than one client.

    Rewriting to the bare spelling removes the ``handle_startendtag``
    path for void elements, which is where the asymmetry lives; both
    spellings already build the same node, so nothing else about the
    output moves. Only the names in :data:`_VOID_ELEMENTS` are touched,
    and only where the parser really reports ``handle_startendtag``: a
    self-closed ``<div/>`` is left alone, and cannot be affected anyway,
    since only a void name is ever recorded.

    Which tags those are is the parser's answer rather than this
    module's, and that is not cosmetic. Deciding it by pattern meant
    inheriting every way the pattern could be derailed, and a derailed
    scan reinstates the very defect this works around: measured,
    ``"<p>one<br>two</p><script>x</ script><p>three<br />TAIL</p>"``
    lost ``TAIL`` outright, because ``</ script>`` ends raw text for the
    parser but not for the pattern, so the ``<br />`` after it was never
    seen and never rewritten. ``<img>`` and ``<hr>`` lost their tails the
    same way.

    Parameters
    ----------
    content : str
        Raw HTML.

    Returns
    -------
    str
        The same HTML with self-closing void tags written bare.
    """

    if "/>" not in content:
        return content
    spans = _scan(content).void_spans
    if not spans:
        return content
    pieces: list[str] = []
    cursor = 0
    for start, end in spans:
        pieces.append(content[cursor:start])
        pieces.append(_VOID_SELF_CLOSE.sub(">", content[start:end]))
        cursor = end
    pieces.append(content[cursor:])
    return "".join(pieces)


# ---------------------------------------------------------------------------
# Literal text
# ---------------------------------------------------------------------------

#: The characters whose reading as Markdown depends on what surrounds them.
#:
#: Every one of them is literal in some positions and syntax in others --
#: ``#`` is a heading only at the start of a line, ``_`` is emphasis only
#: when a partner closes it -- so a text node cannot decide them alone. Each
#: is carried as a private stand-in (:class:`_StandIns`) until the container
#: it lands in is assembled, and decided there.
_LITERAL = "\\<&*_`[]!#>-+.=|~"

#: How a literal character is spelled when it would be misread, where that
#: is not a backslash in front of it.
#:
#: ``<`` and ``&`` have no backslash escape python-markdown honours -- ``\<``
#: renders both characters and the ``<`` still opens a tag -- and neither do
#: ``=`` and ``~``. A character reference is the spelling it passes through
#: as the character.
_SPELLED_OUT = {
    "\\": "\\\\",
    "<": "&lt;",
    "&": "&amp;",
    "=": "&#61;",
    "~": "&#126;",
}

#: The characters python-markdown removes a backslash from, with these
#: extensions. Asked of python-markdown rather than written down, because a
#: backslash in front of anything else is displayed.
_ESCAPABLE = frozenset(Markdown(extensions=_MARKDOWN_EXTENSIONS).ESCAPED_CHARS)

# python-markdown's own patterns, compiled the way its inline processors
# compile theirs (``re.DOTALL``: a code span or an e-mail autolink can run
# across a line break). Taken from the renderer rather than copied, so the
# reader cannot disagree with the version doing the rendering.
_CODE_SPAN = re.compile(BACKTICK_RE, re.DOTALL)
_STANDALONE = re.compile(NOT_STRONG_RE, re.DOTALL)
_AUTOMAIL = re.compile(AUTOMAIL_RE, re.DOTALL)
_AUTOLINK = re.compile(AUTOLINK_RE)
_RULE = re.compile(HRProcessor.RE)
_REFERENCE_DEFINITION = ReferenceProcessor.RE

#: What follows an ``&`` that the renderer displays as a character.
#:
#: A named reference needs its semicolon. A numeric one does not:
#: python-markdown runs ``html.parser`` over its whole source to find raw
#: HTML, and that re-emits ``&#4521`` as ``&#4521;`` -- measured, 3.10.3.
_REFERENCE_TAIL = re.compile(r"\#[0-9]|\#[xX][0-9a-fA-F]|[0-9A-Za-z]+;")

#: What makes a ``<`` open a tag, a comment, a declaration or an instruction.
_TAG_START = re.compile(r"[A-Za-z/!?]")

_LINE_BREAK = re.compile("  \n")
_WORD = re.compile(r"\w")
_SETEXT_UNDERLINE = re.compile(r"(?:=+|-+) *")
_ORDERED_MARKER = re.compile(r"\d+(?=\.[ ])")
_LEADING_BLANK_LINES = re.compile(r"\A(?:[ \t]*\n)+")
_WHITESPACE = re.compile(r"\s+")
_EDGE = " \t\r\n"

#: A character no analysis below treats as syntax: not a word character,
#: not whitespace, not punctuation python-markdown reads. Stands in for
#: anything already decided -- an escaped character, a code span.
_NEUTRAL = "\x02"

#: Elements ``markdownify`` leaves inline that a browser shows as blocks.
_EXTRA_BLOCKS = frozenset({"center", "dir", "menu"})


class _StandIns:
    """Private characters carrying literal text until its container spells it.

    ``markdownify`` calls ``escape`` on one text node at a time, and a text
    node cannot see what it will end up beside: whether its ``#`` starts a
    line, whether its ``*`` has a partner in the next node, whether its
    ``<`` is followed by a letter from a ``<span>``. So escaping replaces
    each character in :data:`_LITERAL` with a stand-in, and the converter
    for the enclosing block -- a paragraph, a list item, a cell, the
    document -- decides every stand-in in it at once, with the whole
    assembled Markdown of that block in view (:class:`_Spelling`).

    The stand-ins are a run of consecutive supplementary private-use code
    points the source does not already contain, so a body holding
    private-use characters of its own -- icon fonts map symbols there --
    cannot be confused with them. One more code point marks a hard line
    break, whose surrounding spaces are settled the same way, and one more
    starts a line no list item indents (:attr:`lazy`).

    Parameters
    ----------
    source : str
        The text about to be converted, which the stand-ins must not occur
        in.
    """

    def __init__(self, source: str) -> None:
        size = len(_LITERAL) + 2
        for base in range(0xF0000, 0xFFFFE - size, size):
            characters = [chr(base + offset) for offset in range(size)]
            if not any(character in source for character in characters):
                break
        else:  # pragma: no cover - needs a source using all of plane 15
            raise GlpiContentError(
                "Could not convert GLPI HTML content to Markdown: it uses "
                "every private-use code point the converter could work with."
            )
        literal = characters[: len(_LITERAL)]
        self.hard_break = characters[-2]
        #: Starts a line that stays at the start of the line: a quote that
        #: opens a list item is read by python-markdown only if its later
        #: lines are its lazy continuation, since the item's first block is
        #: never detabbed and ``>`` counts only three spaces in at most.
        self.lazy = characters[-1]
        self.characters = frozenset(literal)
        self._shadow = str.maketrans(dict(zip(_LITERAL, literal, strict=True)))
        self._restore = str.maketrans(dict(zip(literal, _LITERAL, strict=True)))
        self._any = re.compile("[" + "".join(literal) + "]")
        self._break = re.compile("[ ]*" + self.hard_break + "\n?[ ]*")

    def shadow(self, text: str) -> str:
        """Return ``text`` with every character in :data:`_LITERAL` stood in for."""

        return text.translate(self._shadow)

    def restore(self, text: str) -> str:
        """Return ``text`` with every stand-in back as the character it is."""

        return text.translate(self._restore)

    def carried(self, text: str) -> bool:
        """Return whether ``text`` still holds an undecided stand-in."""

        return self._any.search(text) is not None

    def positions(self, text: str) -> set[int]:
        """Return where ``text`` holds a stand-in."""

        return {found.start() for found in self._any.finditer(text)}

    def replace(self, text: str, spell: Callable[[int, str], str]) -> str:
        """Replace each stand-in with ``spell(position, character)``."""

        return self._any.sub(
            lambda found: spell(found.start(), self.restore(found.group(0))), text
        )

    def settle_breaks(self, text: str) -> str:
        """Spell every hard line break ``"  \\n"``, dropping the spaces around it.

        A browser does not display whitespace at either side of a ``<br>``,
        so it is not content, and keeping it made the same body read two
        ways: ``a<br> b`` read as ``a  \\n b`` the first time and as
        ``a  \\nb`` once python-markdown had rendered it.
        """

        if self.hard_break not in text:
            return text
        return self._break.sub("  \n", text)


def _spelled(character: str) -> str:
    """Return the escaped spelling of one literal character."""

    return _SPELLED_OUT.get(character) or "\\" + character


class _Spelling:
    """One container's Markdown, and which of its literal characters to escape.

    Built over the container's assembled text, where a stand-in is literal
    text and anything else is markup ``markdownify`` generated or text an
    inner container already decided. Each ``settle_*`` method asks one of
    python-markdown's questions of the text as it will be rendered, and
    marks the literal characters that would be read as syntax;
    :meth:`render` spells them.

    The order the methods run in is python-markdown's own inline order --
    code spans before escapes before links before emphasis -- because each
    of those consumes text the next one would otherwise see.

    Parameters
    ----------
    text : str
        The container's text, stand-ins included.
    stand_ins : _StandIns
        The stand-ins in use.
    """

    def __init__(self, text: str, stand_ins: _StandIns) -> None:
        self.text = text
        self.stand_ins = stand_ins
        self.view = stand_ins.restore(text)
        self.literal = stand_ins.positions(text)
        self.escaped: set[int] = set()
        self.hidden: set[int] = set()

    # -- bookkeeping ---------------------------------------------------------

    def escape(self, position: int) -> None:
        """Escape the character at ``position``, if it is literal."""

        if position in self.literal:
            self.escaped.add(position)

    def live(self, position: int) -> bool:
        """Return whether ``position`` is literal and not yet escaped."""

        return position in self.literal and position not in self.escaped

    def render(self) -> str:
        """Return the container's Markdown, every literal character spelled."""

        escaped = self.escaped

        def spell(position: int, character: str) -> str:
            return _spelled(character) if position in escaped else character

        return self.stand_ins.replace(self.text, spell)

    def markdown(self, start: int, end: int) -> tuple[str, list[int]]:
        """Return one span's Markdown as it stands, and each character's position."""

        pieces: list[str] = []
        origin: list[int] = []
        cursor = start
        for position in sorted(p for p in self.escaped if start <= p < end):
            pieces.append(self.view[cursor:position])
            origin.extend(range(cursor, position))
            form = _spelled(self.view[position])
            pieces.append(form)
            origin.extend([position] * len(form))
            cursor = position + 1
        pieces.append(self.view[cursor:end])
        origin.extend(range(cursor, end))
        return "".join(pieces), origin

    def working(self, *, line_breaks: bool = False) -> str:
        """Return the view with everything already decided made neutral.

        With ``line_breaks``, a hard break is neutral too: python-markdown
        replaces ``"  \\n"`` with a placeholder before it looks for emphasis,
        so the characters either side of one are not next to whitespace.
        """

        chars = list(self.view)
        for position in self.hidden | self.escaped:
            chars[position] = _NEUTRAL
        working = "".join(chars)
        if line_breaks:
            working = _LINE_BREAK.sub(_NEUTRAL * 3, working)
        return working

    # -- what depends only on the next few characters ----------------------

    def settle_local(self) -> None:
        """Decide ``\\``, ``<`` and ``&`` by the characters right after them.

        * ``\\`` before a character python-markdown would treat as escaped
          (:data:`_ESCAPABLE`) -- ``\\\\serveur``, ``C:\\_temp``;
        * ``<`` before a letter, ``/``, ``!`` or ``?`` -- anything
          python-markdown would pass through as raw HTML;
        * ``&`` opening a character reference python-markdown would pass
          through for the browser to decode (:data:`_REFERENCE_TAIL`).

        A ``<`` opening an e-mail autolink is decided once the inline
        constructs it could run through are known (:meth:`settle_automail`).
        """

        view = self.view
        for position in self.literal:
            char = view[position]
            following = view[position + 1 : position + 2]
            if char == "\\":
                if following and following in _ESCAPABLE:
                    self.escape(position)
            elif char == "<":
                if following and _TAG_START.match(following):
                    self.escape(position)
            elif char == "&" and _REFERENCE_TAIL.match(view, position + 1):
                self.escape(position)

    def settle_automail(self) -> None:
        """Escape every literal ``<`` that would open an e-mail autolink.

        python-markdown looks for ``<address@domain>`` only once code spans,
        escapes, links, images and URL autolinks have each become a
        placeholder, so an address can run through any of them:
        ``<3![a b](x.png)@c>`` is one to it. The pattern is matched against
        the text with each of those collapsed to one character, and right to
        left, because a match may also run through a ``<`` decided to its
        right: once that one is ``&lt;``, nothing stops it.

        A link's text is read the same way on its own, since python-markdown
        parses it after the link is found; an image's text is never parsed.
        """

        view = self.view
        opening = sorted(
            (p for p in self.literal if view[p] == "<" and p not in self.escaped),
            reverse=True,
        )
        if not opening or "@" not in view:
            return
        working = list(self.working())
        contexts: dict[tuple[int, int], _Collapsed] = {}
        for position in opening:
            start, end = 0, len(view)
            while True:
                if (start, end) not in contexts:
                    contexts[start, end] = self._collapsed(working, start, end)
                context = contexts[start, end]
                link = context.link_at(position)
                if link is None:
                    at = context.index[position - start]
                    if _automail_at(context.text, context.tail, at):
                        self.escape(position)
                        context.tail[at] = "&"
                    break
                if link.label is None or not link.label[0] <= position < link.label[1]:
                    break
                start, end = link.label

    def _collapsed(self, working: list[str], start: int, end: int) -> _Collapsed:
        """Return ``view[start:end]`` with every placeholder collapsed."""

        view = self.view
        links = _generated_links(view, working, self.literal, start, end)
        masked = self.hidden | self.escaped
        for link in links:
            masked = masked | set(range(*link.span))
        pieces: list[str] = []
        index: list[int] = []
        for position in range(start, end):
            if position not in masked:
                pieces.append(view[position])
            elif position == start or position - 1 not in masked:
                pieces.append(_NEUTRAL)
            index.append(len(pieces) - 1)
        return _Collapsed("".join(pieces), index, links)

    # -- python-markdown's inline patterns, in its own order ---------------

    def settle_bang(self) -> None:
        """Escape a literal ``!`` right before a generated link's ``[``.

        Otherwise ``Attention!`` followed by a link renders an image.
        """

        view = self.view
        for position in self.literal:
            if (
                view[position] == "!"
                and view[position + 1 : position + 2] == "["
                and position + 1 not in self.literal
            ):
                self.escape(position)

    def settle_backticks(self, units: Iterable[tuple[int, int]]) -> None:
        """Escape every literal backtick run python-markdown would pair.

        Found by running python-markdown's own code-span pattern over each
        unit's Markdown as it stands, escaping the literal runs it paired,
        and running it again until it pairs none: escaping an opener can hand
        its closer to the next run. A literal backtick touching a generated
        one is escaped first, since it would join the generated run and
        change the length the closer is matched on. What is left paired is
        the generated code spans, which the later passes must not look
        inside.
        """

        view = self.view
        if "`" not in view:
            return
        for position in self.literal:
            if view[position] == "`":
                for neighbour in (position - 1, position + 1):
                    if (
                        0 <= neighbour < len(view)
                        and view[neighbour] == "`"
                        and neighbour not in self.literal
                    ):
                        self.escape(position)
        for start, end in units:
            if "`" in view[start:end]:
                self._settle_code_spans(start, end)

    def _settle_code_spans(self, start: int, end: int) -> None:
        while True:
            markdown, origin = self.markdown(start, end)
            offending: set[int] = set()
            generated: list[tuple[int, int]] = []
            for opener, closer in _code_spans(markdown):
                delimiters = [origin[i] for i in range(*opener)]
                delimiters += [origin[i] for i in range(*closer)]
                live = [position for position in delimiters if self.live(position)]
                if live:
                    offending.update(live)
                else:
                    generated.append((origin[opener[0]], origin[closer[1] - 1] + 1))
            if not offending:
                for first, last in generated:
                    self.hidden.update(range(first, last))
                return
            for position in offending:
                self.escape(position)

    def hide_escapes(self) -> None:
        """Hide what a backslash already escaped in generated or decided text.

        Pairs are consumed left to right, as python-markdown's escape
        pattern consumes them, so ``\\\\`` hides both backslashes and escapes
        nothing after it.
        """

        view = self.view
        position = 0
        while position < len(view):
            if (
                view[position] == "\\"
                and position not in self.hidden
                and position not in self.literal
            ):
                following = position + 1
                if (
                    following < len(view)
                    and view[following] in _ESCAPABLE
                    and following not in self.literal
                ):
                    self.hidden.update((position, following))
                position += 2
                continue
            position += 1

    def settle_brackets(self, units: Iterable[tuple[int, int]]) -> None:
        """Escape every literal ``[`` that would open a link or an image.

        A ``[`` opens one when its balanced ``]`` is followed straight away
        by ``(``, which is python-markdown's test. Right to left, because
        escaping an inner ``[`` rebalances the brackets of an outer one; one
        pass is enough, since the brackets to a ``[``'s right are settled
        before it is.

        The pass keeps the ``]`` not yet closed by a ``[`` to their right on
        a stack, so each ``[`` finds its partner on top of it: the first
        ``]`` python-markdown's own count would stop at. An escaped ``[``
        hands its ``]`` back, to be closed by one further left. That keeps
        the pass linear, where counting forward from each ``[`` cost a body
        of unclosed brackets quadratic time.
        """

        working = list(self.working())
        for start, end in units:
            closers: list[int] = []
            for position in range(end - 1, start - 1, -1):
                char = working[position]
                if char == "]":
                    closers.append(position)
                elif char == "[" and closers:
                    close = closers.pop()
                    if (
                        self.live(position)
                        and close + 1 < end
                        and working[close + 1] == "("
                    ):
                        self.escape(position)
                        working[position] = _NEUTRAL
                        closers.append(close)

    def settle_asterisks(self, units: Iterable[tuple[int, int]]) -> None:
        """Escape literal ``*`` wherever a unit holds two possible delimiters.

        python-markdown pairs asterisks with no regard for word boundaries,
        so any two in one block -- literal or generated -- can pair. The one
        exemption is its own: a run of one to three that is literal through
        and through and stands alone between whitespace is text to it
        (``5 * 3``). A run that touches a generated delimiter is not alone.
        """

        working = self.working(line_breaks=True)
        for start, end in units:
            unit = working[start:end]
            exempt: set[int] = set()
            for found in _STANDALONE.finditer(unit):
                run = range(start + found.start(3), start + found.end(3))
                if found.group(3).startswith("*") and all(
                    position in self.literal for position in run
                ):
                    exempt.update(run)
            delimiters = [
                start + offset
                for offset, char in enumerate(unit)
                if char == "*" and start + offset not in exempt
            ]
            if len(delimiters) >= 2:
                for position in delimiters:
                    self.escape(position)

    def settle_underscores(self, units: Iterable[tuple[int, int]]) -> None:
        """Escape literal ``_`` runs that python-markdown could pair.

        Underscores are only emphasis at a word boundary, which is what
        keeps ``fichier_de_test_v2.xlsx`` literal, except in a run of three
        or more, which may open emphasis anywhere and take a mid-word run as
        its closer; a single run of seven pairs with itself. When a unit
        holds a pairing, every run that could take part in one is escaped.
        """

        working = self.working(line_breaks=True)
        for start, end in units:
            unit = working[start:end]
            exempt: set[int] = set()
            for found in _STANDALONE.finditer(unit):
                if found.group(3).startswith("_"):
                    exempt.update(range(start + found.start(3), start + found.end(3)))
            runs = [
                (start + found.start(), start + found.end())
                for found in re.finditer("_+", unit)
                if start + found.start() not in exempt
                and any(
                    self.live(position)
                    for position in range(start + found.start(), start + found.end())
                )
            ]
            if not _underscores_pair(runs, working, start, end):
                continue
            triple = any(finish - begin >= 3 for begin, finish in runs)
            for begin, finish in runs:
                left = begin == start or not _WORD.match(working[begin - 1])
                right = finish == end or not _WORD.match(working[finish])
                if left or right or triple:
                    for position in range(begin, finish):
                        self.escape(position)

    def settle_inline(self, units: list[tuple[int, int]]) -> None:
        """Run every inline question, in python-markdown's order."""

        self.settle_bang()
        self.settle_backticks(units)
        self.hide_escapes()
        self.settle_brackets(units)
        self.settle_automail()
        self.settle_asterisks(units)
        self.settle_underscores(units)


#: The longest ``<...>`` checked for an e-mail autolink. An address is at
#: most 254 characters; the pattern has no bound of its own, and checking
#: every ``<`` to the end of a long body would cost that body quadratically.
_AUTOMAIL_SPAN = 320


def _automail_at(view: str, tail: list[str], position: int) -> bool:
    """Return whether an e-mail autolink opens at ``position``.

    ``tail`` is the view with every ``<`` already decided to the right
    spelled as a character that is not one. The pattern cannot cross a
    space, and ends at the first ``>``.
    """

    end = view.find(">", position, position + _AUTOMAIL_SPAN)
    if end < 0 or " " in view[position:end]:
        return False
    return _AUTOMAIL.match("".join(tail[position : end + 1])) is not None


def _underscores_pair(
    runs: list[tuple[int, int]], working: str, start: int, end: int
) -> bool:
    """Return whether python-markdown could pair any of ``runs``.

    ``EM_STRONG2`` and ``STRONG_EM2`` take their inner text from anywhere,
    the run itself included, so a run of seven is a match on its own and a
    run of three or more pairs with any other run. The ``SMART`` patterns
    need an opener at a left word boundary and a later closer at a right
    one.
    """

    if any(finish - begin >= 7 for begin, finish in runs):
        return True
    if len(runs) < 2:
        return False
    if any(finish - begin >= 3 for begin, finish in runs):
        return True
    opened = False
    for begin, finish in runs:
        if opened and (finish == end or not _WORD.match(working[finish])):
            return True
        if begin == start or not _WORD.match(working[begin - 1]):
            opened = True
    return False


def _code_spans(markdown: str) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """Return the code spans python-markdown finds, as delimiter spans.

    Replays its backtick processor, which replaces each match with a
    placeholder and searches on from just after it. After a code span that
    is the same as searching on from the span's end: the one look-behind
    there is ``(?<!\\\\)``, and the span ends in a backtick. A run of escaped
    backslashes before a backtick is consumed on its own, though, and its
    placeholder is what leaves the backtick after it free to open -- so
    that run, and only that, is neutralised in the text searched.
    """

    spans: list[tuple[tuple[int, int], tuple[int, int]]] = []
    text = markdown
    position = 0
    while True:
        found = _CODE_SPAN.search(text, position)
        if found is None:
            return spans
        if found.group(3):
            size = len(found.group(2))
            spans.append(
                (
                    (found.start(2), found.end(2)),
                    (found.end(3), found.end(3) + size),
                )
            )
            position = found.end()
        else:
            start, end = found.span(1)
            text = text[:start] + _NEUTRAL * (end - start) + text[end:]
            position = end


class _Link(NamedTuple):
    """A link, an image or a URL autolink the reader wrote, as view spans."""

    span: tuple[int, int]
    #: The link's text, which python-markdown parses on its own; ``None``
    #: for an image or an autolink, whose text it never parses.
    label: tuple[int, int] | None


class _Collapsed:
    """A span of a view with every construct python-markdown stashes collapsed.

    Parameters
    ----------
    text : str
        The span, each stashed construct one character.
    index : list of int
        Where each position of the span went in ``text``.
    links : list of _Link
        The links, images and autolinks collapsed.
    """

    def __init__(self, text: str, index: list[int], links: list[_Link]) -> None:
        self.text = text
        self.index = index
        self.links = links
        #: ``text`` with every ``<`` decided so far spelled as a character
        #: that opens nothing.
        self.tail = list(text)

    def link_at(self, position: int) -> _Link | None:
        """Return the link or image ``position`` is inside, if any."""

        for link in self.links:
            if link.span[0] <= position < link.span[1]:
                return link
        return None


def _generated_links(
    view: str, working: list[str], literal: set[int], start: int, end: int
) -> list[_Link]:
    """Return the links, images and URL autolinks the reader wrote in a span.

    A generated ``[`` is one that is not literal, and it opens a link when
    its balanced ``]`` is followed by ``(``; the link ends at the ``)``
    that balances that one. A generated ``<`` opens an autolink when the
    text up to the next ``>`` is one.
    """

    links: list[_Link] = []
    position = start
    while position < end:
        char = working[position]
        if char == "[" and position not in literal:
            close = _balanced_close(working, position + 1, end)
            if close is not None and view[close + 1 : close + 2] == "(":
                finish = _balanced_paren(view, close + 2, end)
                if finish is not None:
                    image = position > start and view[position - 1] == "!"
                    links.append(
                        _Link(
                            (position - image, finish + 1),
                            None if image else (position + 1, close),
                        )
                    )
                    position = finish + 1
                    continue
        elif char == "<" and position not in literal:
            finish = view.find(">", position + 1, end)
            if finish > 0 and _AUTOLINK.fullmatch(view, position, finish + 1):
                links.append(_Link((position, finish + 1), None))
                position = finish + 1
                continue
        position += 1
    return links


def _balanced_paren(view: str, start: int, end: int) -> int | None:
    """Return where the ``(`` before ``start`` closes, before ``end``."""

    depth = 1
    for position in range(start, end):
        if view[position] == "(":
            depth += 1
        elif view[position] == ")":
            depth -= 1
            if depth == 0:
                return position
    return None


def _balanced_close(working: list[str], start: int, end: int) -> int | None:
    """Return where the ``[`` before ``start`` closes, as python-markdown counts."""

    depth = 1
    for position in range(start, end):
        char = working[position]
        if char == "]":
            depth -= 1
            if depth == 0:
                return position
        elif char == "[":
            depth += 1
    return None


def _blocks(view: str) -> list[list[tuple[int, int]]]:
    """Return the text's blocks -- runs of non-blank lines -- as line spans."""

    blocks: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    start = 0
    for line in view.split("\n"):
        end = start + len(line)
        if line.strip(" \t"):
            current.append((start, end))
        elif current:
            blocks.append(current)
            current = []
        start = end + 1
    if current:
        blocks.append(current)
    return blocks


def _units(
    view: str, blocks: list[list[tuple[int, int]]], *, soft_breaks: bool
) -> list[tuple[int, int]]:
    """Return the spans python-markdown parses inline text in, one at a time.

    A paragraph is one: its lines are joined by hard breaks, ``"  \\n"``.
    Every other line break the reader writes starts something python-markdown
    parses on its own -- a nested list, a quote -- even with no blank line
    before it, so a unit ends there. Pairing is only possible inside a unit,
    so this is what keeps a list item's ``*`` from being escaped for a ``*``
    in the list nested under it. Stripped text is the exception: its plain
    line breaks continue a paragraph, which ``soft_breaks`` says.
    """

    units: list[tuple[int, int]] = []
    for block in blocks:
        start, end = block[0]
        for line_start, line_end in block[1:]:
            if soft_breaks or view[end - 2 : end] == "  ":
                end = line_end
                continue
            units.append((start, end))
            start, end = line_start, line_end
        units.append((start, end))
    return units


def _settle_block(
    text: str,
    stand_ins: _StandIns,
    *,
    in_list: bool,
    top_level: bool,
    lead: tuple[str, ...] = (),
    soft_breaks: bool = False,
) -> str:
    """Spell the literal text of one block container.

    ``text`` is the container's content before its own prefix is added --
    a list item's bullet, a quote's ``>`` -- so every line starts where
    python-markdown will read it from. Each line is checked for the block
    syntax python-markdown would find there, then the whole container for
    the inline syntax (:meth:`_Spelling.settle_inline`). The line rules:

    * ``#`` at the very start of a line: an ATX heading, on any line;
    * ``>`` after up to three spaces: a block quote, on any line;
    * ``-``, ``+`` or ``*`` followed by a space, and digits followed by
      ``.`` and a space, after up to three spaces: a list item -- on a
      block's first line, or on any line inside a list item, where a
      continuation line starts a nested list;
    * a line of ``=`` or ``-`` alone as a block's second line: a setext
      underline, spelled ``&#61;`` or ``\\-``;
    * three or more ``-``, ``*`` or ``_``, spaces allowed between: a rule,
      on any line -- counting the bullet a list item is about to get;
    * ``[label]: destination`` on a line: a reference definition, which
      python-markdown consumes and which would turn every ``[label]`` in
      the document into a link;
    * three backticks or tildes at the start of a top-level line: a fence;
    * a line of only ``|``, ``:``, ``-`` and spaces: a table's separator.

    Parameters
    ----------
    text : str
        The container's text.
    stand_ins : _StandIns
        The stand-ins in use.
    in_list : bool
        Whether the container is inside a list item.
    top_level : bool
        Whether its lines start at column 0 of the document, where a fence
        can open.
    lead : tuple of str, optional
        The bullets that will precede the first line on its line, outermost
        first (:func:`_line_lead`).
    soft_breaks : bool, optional
        Whether a plain line break continues a paragraph (see :func:`_units`).

    Returns
    -------
    str
        The same text with every stand-in spelled.
    """

    if not stand_ins.carried(text):
        return text
    spelling = _Spelling(text, stand_ins)
    spelling.settle_local()
    view = spelling.view
    blocks = _blocks(view)
    for block_number, block in enumerate(blocks):
        block_start, block_end = block[0][0], block[-1][1]
        for number, (start, end) in enumerate(block):
            line = view[start:end]
            indent = len(line) - len(line.lstrip(" "))
            if line.startswith("#"):
                spelling.escape(start)
            if number == 1 and _SETEXT_UNDERLINE.fullmatch(line):
                spelling.escape(start)
            # python-markdown reads each item's content from just after its
            # own bullet, so the first line is a rule if any tail of the
            # bullets before it makes one: ``1. - --`` holds ``- --``.
            heads = ["".join(lead[i:]) for i in range(len(lead))]
            bulleted = heads if block_number == 0 and number == 0 else []
            if any(_RULE.match(head + line) for head in ["", *bulleted]):
                for position in range(start, end):
                    if view[position] in "-*_" and position in spelling.literal:
                        spelling.escape(position)
                        if view[position] == "-":
                            break
            if top_level and line.startswith(("```", "~~~")):
                if line.startswith("~"):
                    spelling.escape(start)
                else:
                    position = start
                    while position < end and view[position] == "`":
                        spelling.escape(position)
                        position += 1
            if "|" in line and set(line) <= set("|:- "):
                for position in range(start, end):
                    if view[position] == "|":
                        spelling.escape(position)
            if indent > 3 or indent == len(line):
                continue
            content = start + indent
            first = view[content]
            if first == ">":
                spelling.escape(content)
            if in_list or number == 0:
                if first in "-+*" and view[content + 1 : content + 2] == " ":
                    spelling.escape(content)
                ordered = _ORDERED_MARKER.match(view, content, end)
                if ordered:
                    spelling.escape(ordered.end())
            if first == "[" and _REFERENCE_DEFINITION.match(
                view[block_start:block_end], start - block_start
            ):
                spelling.escape(content)
    spelling.settle_inline(_units(view, blocks, soft_breaks=soft_breaks))
    return spelling.render()


def _settle_inline(
    text: str, stand_ins: _StandIns, *, cell: bool = False, heading: bool = False
) -> str:
    """Spell the literal text of a table cell or a heading.

    Neither holds block syntax, so only the inline questions are asked,
    plus one each:

    * in a cell, every ``|`` -- the table splits the row on it -- and every
      backtick, because the table pairs backtick runs across the whole row
      to decide which ``|`` it splits on;
    * in a heading, the run of ``#`` it ends with, which python-markdown
      strips as a closing sequence, and a final ``\\``, after which it
      cannot match the heading line at all.
    """

    if not stand_ins.carried(text):
        return text
    spelling = _Spelling(text, stand_ins)
    spelling.settle_local()
    view = spelling.view
    if cell:
        for position in spelling.literal:
            if view[position] in "|`":
                spelling.escape(position)
    if heading:
        position = len(view) - 1
        while position >= 0 and view[position] == "#":
            spelling.escape(position)
            position -= 1
        if view.endswith("\\"):
            spelling.escape(len(view) - 1)
    spelling.settle_inline([(0, len(view))])
    return spelling.render()


def _settle_label(text: str, stand_ins: _StandIns) -> str:
    """Spell the brackets in a link's text or an image's alt text.

    python-markdown finds a link's text by counting brackets, so literal
    brackets inside one are safe when they balance -- ``rapport
    [final].pdf`` -- and end the text early when they do not. They are
    left alone when balanced, and all escaped otherwise, or when they would
    form an image or a link of their own inside the text. The label's other
    characters are left to the block it is in.
    """

    if not stand_ins.carried(text):
        return text
    probe = _Spelling(text, stand_ins)
    view = probe.view
    brackets = sorted(position for position in probe.literal if view[position] in "[]")
    if not brackets:
        return text
    # Only generated code spans can hide a bracket: a literal backtick is
    # either escaped later or pairs with nothing.
    for position in probe.literal:
        if view[position] in "`\\":
            probe.escaped.add(position)
    probe.settle_backticks([(0, len(view))])
    probe.hide_escapes()
    working = list(probe.working())
    depth = 1
    broken = False
    for char in working:
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                broken = True
                break
    broken = broken or depth != 1
    if not broken:
        for opener in (position for position in brackets if view[position] == "["):
            close = _balanced_close(working, opener + 1, len(working))
            if close is not None and working[close + 1 : close + 2] == ["("]:
                broken = True
                break
    pieces = list(text)
    for position in brackets:
        pieces[position] = _spelled(view[position]) if broken else view[position]
    return "".join(pieces)


def _loosened(item: str, loose: bool = False) -> str:
    """Put a blank line after a list item's own text, when it is loose anyway.

    python-markdown makes an item *loose* -- its text wrapped in a paragraph
    -- as soon as anything inside it is separated by a blank line: a code
    block, a second paragraph, a nested item of either. An item following a
    loose one is loose too. Reading that output back gives a blank line
    between the item's text and the nested list after it, where the first
    read had one line break; writing the blank line from the start makes the
    first read the one every later read gives.

    The item's own text ends at its first line break that is not a hard
    break, since that is the only other newline the reader writes there.

    Parameters
    ----------
    item : str
        The item's Markdown, before its bullet and indentation.
    loose : bool, optional
        Whether the item is loose whatever it holds: it follows a loose one.
    """

    if not loose and "\n\n" not in item:
        return item
    position = 0
    while True:
        position = item.find("\n", position)
        if position < 0:
            return item
        if item[position - 2 : position] != "  ":
            break
        position += 1
    if item[position + 1 : position + 2] == "\n":
        return item
    return item[:position] + "\n" + item[position:]


#: The elements ``markdownify`` writes as a list.
_LIST_ELEMENTS = frozenset({"ul", "ol", "dir", "menu"})

#: The elements whose text is not displayed, and that the converter drops.
_UNSHOWN_ELEMENTS = frozenset({"script", "style", "title"})

#: The elements displayed with no text of their own.
_SHOWN_EMPTY = frozenset({"img", "hr"})

#: The blocks whose second line follows their first with no blank line.
_LINED_BLOCKS = _LIST_ELEMENTS | {"blockquote", "table"}


def _shows(node: PageElement, within: PageElement) -> bool:
    """Return whether ``node`` is text, an image or a rule displayed in ``within``.

    ``markdownify`` skips comments and doctypes, and whitespace between
    blocks; a ``<br>`` on its own starts no block, so it does not count.
    """

    if isinstance(node, Tag):
        if node.name not in _SHOWN_EMPTY:
            return False
    elif isinstance(node, (Comment, Doctype)) or not str(node).strip():
        return False
    for parent in node.parents:
        if parent is within:
            break
        if parent.name in _UNSHOWN_ELEMENTS:
            return False
    return True


def _last_shown(node: PageElement) -> PageElement | None:
    """Return the last thing ``node`` displays, or ``None`` if it displays nothing."""

    if isinstance(node, Tag) and node.name in _UNSHOWN_ELEMENTS:
        return None
    last = node
    while isinstance(last, Tag) and last.contents:
        last = last.contents[-1]
    for candidate in chain([last], last.previous_elements):
        if _shows(candidate, node):
            return candidate
        if candidate is node:
            break
    return None


def _opens_with_a_block(item: Tag) -> bool:
    """Return whether a list item's first line is a list's, a quote's or a table's.

    The item then has no text of its own to set apart with a blank line:
    the line after its first is that block's, and a blank line there would
    split the block in two.
    """

    for candidate in item.descendants:
        if _shows(candidate, item):
            for element in candidate.parents:
                if element is item:
                    return False
                if element.name in _LINED_BLOCKS:
                    return True
    return False


def _ends_in_a_list(node: PageElement) -> bool | None:
    """Return whether what ``node`` displays last is in a list, if it shows anything."""

    shown = _last_shown(node)
    if shown is None:
        return None
    for element in chain([shown], shown.parents):
        if isinstance(element, Tag) and element.name in _LIST_ELEMENTS:
            return True
        if element is node:
            break
    return False


def _bullet(item: Tag, numbers: dict[int, int]) -> str:
    """Return the marker the reader writes before a list item.

    ``numbers`` holds each ordered item's position among its list's items,
    filled for a whole list the first time one of its items is asked for:
    counting an item's previous siblings instead cost a long list quadratic
    time.
    """

    parent = item.parent
    if parent is not None and parent.name == "ol":
        if id(item) not in numbers:
            for index, entry in enumerate(parent.find_all("li", recursive=False)):
                numbers[id(entry)] = index
        start = str(parent.get("start") or "")
        first = int(start) if start.isdigit() else 1
        return f"{first + numbers[id(item)]}. "
    return "- "


def _line_items(element: Tag) -> list[Tag]:
    """Return the list items whose bullets are written on ``element``'s first line.

    ``element`` itself if it is an item, and every item it opens, through
    every block that opens the next, outermost first: ``<li><ul><li>-`` is
    written ``- - -``. A quote ends the line's items, since python-markdown
    parses a quote's content on its own.
    """

    items = [element] if element.name == "li" else []
    node = element
    while node.parent is not None:
        if any(_last_shown(sibling) is not None for sibling in node.previous_siblings):
            break
        node = node.parent
        if node.name == "blockquote":
            break
        if node.name == "li":
            items.insert(0, node)
    return items


def _deep_list(element: Tag | None) -> bool:
    """Return whether a list's first line carries three bullets or more.

    python-markdown's first pass over a block takes every line after
    ``- - - a`` that is indented eight spaces or more as that line's lazy
    continuation, so nothing of such a list can follow its first line
    directly: its items' own blocks, and its other items, each start a block
    of their own, which makes every item of the list loose.
    """

    return element is not None and len(_line_items(element)) >= 2


def _shown_items(element: Tag) -> int:
    """Return how many of a list's items display something."""

    items = element.find_all("li", recursive=False)
    return sum(_last_shown(item) is not None for item in items)


def _line_lead(element: Tag, numbers: dict[int, int]) -> tuple[str, ...]:
    """Return the bullets written on ``element``'s first line, its own included.

    ``- - -`` is a rule to python-markdown, so the first line of a block is
    checked against its whole line. ``numbers`` is :func:`_bullet`'s.
    """

    return tuple(_bullet(item, numbers) for item in _line_items(element))


def _code_block_fits(element: Tag) -> bool:
    """Return whether python-markdown reads an indented code block where ``element`` is.

    Inside a list item or a quote a ``<pre>`` can only be an indented code
    block, and there are two places where python-markdown reads none: as the
    item's first block, which is always its paragraph, and right after a
    list in the same item or quote, since the code's indentation is then
    exactly that of the list's last item, and its lines become a paragraph
    of that item.
    """

    node: Tag = element
    while node.parent is not None:
        for sibling in node.previous_siblings:
            in_a_list = _ends_in_a_list(sibling)
            if in_a_list is not None:
                return not in_a_list
        node = node.parent
        if node.name == "li":
            return False
        if node.name == "blockquote":
            return True
    return True


class _LiteralSafeConverter(MarkdownConverter):
    """``markdownify``'s converter, spelling literal text so it stays text.

    ``escape`` is replaced, and escapes nothing itself: it stands each
    character of :data:`_LITERAL` in for (:class:`_StandIns`). The
    converters for the containers python-markdown parses on their own -- a
    paragraph, a ``<div>``, a list item, a quote, a heading, a table cell,
    the document -- then spell every stand-in in their text at once, before
    they add their own prefix, with the whole of it in view:
    :func:`_settle_block`, :func:`_settle_inline` and :func:`_settle_label`
    list the rules. A container inside a heading, a cell or a link leaves its
    stand-ins to the one it sits in, which is the unit python-markdown will
    parse.

    It also changes what ``markdownify`` produces wherever the result lost
    or garbled content that literal-safe escaping would otherwise have kept:

    * a list item's continuation lines are indented by four spaces, which is
      what python-markdown nests at, rather than by the bullet's width;
    * whatever follows a nested list in its item -- text, a quote -- starts
      after a blank line, where ``markdownify`` ran it into the list's last
      item; a quote anywhere in an item after its text does too, and a
      quote that opens an item keeps its later lines at the start of the
      line, the only place python-markdown reads them (:attr:`_StandIns.lazy`);
    * an item whose first line it shares with another's bullet is loose,
      and so is every item of a list whose first line carries three bullets
      or more (:func:`_deep_list`), because python-markdown's first pass
      over the block cannot nest anything under such a line;
    * an item written loose by python-markdown is written loose here too, so
      the second read is the first one (:func:`_loosened`);
    * ``<script>``, ``<style>`` and ``<title>`` bodies are dropped, as a
      browser drops them;
    * ``<s>``, ``<del>`` and ``<strike>`` keep their words without the
      ``~~`` markers python-markdown would display;
    * an image stays an image inside a heading or a cell, and its alt text
      is one line;
    * a ``<pre>`` inside a list item or a quote becomes an indented code
      block, since a fence only opens at the start of a line, except where
      python-markdown reads no code block at all (:func:`_code_block_fits`),
      where its lines are kept as literal text; a top-level fence is made
      longer than any fence line the code holds;
    * a newline in text is a space, as HTML displays it.
    """

    def __init__(self, stand_ins: _StandIns, **options: Any) -> None:
        super().__init__(**options)
        self.stand_ins = stand_ins
        #: The list items whose Markdown ends in a blank line, by ``id``.
        self._loose_items: set[int] = set()
        #: Each ordered item's position in its list, by ``id`` (:func:`_bullet`).
        self._numbers: dict[int, int] = {}
        #: How many of a list's items display something, by the list's ``id``.
        self._shown: dict[int, int] = {}

    def _shown_items(self, element: Tag) -> int:
        """Return :func:`_shown_items` for a list, counted once per list."""

        if id(element) not in self._shown:
            self._shown[id(element)] = _shown_items(element)
        return self._shown[id(element)]

    def _inherited(self, name: str) -> Callable[..., Any]:
        """Return ``markdownify``'s own converter ``name``.

        Its type stub declares the constructor and ``convert`` alone, so the
        converters this class extends are reached by name.
        """

        method: Callable[..., Any] = getattr(super(), name)
        return method

    # -- text -----------------------------------------------------------------

    def escape(self, text: str, parent_tags: set[str]) -> str:
        return self.stand_ins.shadow(text) if text else ""

    def process_text(self, el: object, parent_tags: set[str] | None = None) -> str:
        """Drop the whitespace next to an element displayed as a block.

        ``markdownify`` already does for the elements it knows are blocks;
        :data:`_EXTRA_BLOCKS` are the ones it does not.
        """

        text = str(self._inherited("process_text")(el, parent_tags=parent_tags))
        before = getattr(el, "previous_sibling", None)
        after = getattr(el, "next_sibling", None)
        if isinstance(before, Tag) and before.name in _EXTRA_BLOCKS:
            text = text.lstrip(_EDGE)
        if isinstance(after, Tag) and after.name in _EXTRA_BLOCKS:
            text = text.rstrip(_EDGE)
        return text

    # -- containers that settle their own literal text ------------------------

    @staticmethod
    def _deferred(parent_tags: set[str]) -> bool:
        """Return whether an enclosing heading, cell or link settles instead."""

        return "_inline" in parent_tags or "a" in parent_tags

    def _settle(
        self, text: str, parent_tags: set[str], lead: tuple[str, ...] = ()
    ) -> str:
        text = self.stand_ins.settle_breaks(text)
        text = _LEADING_BLANK_LINES.sub("", text).rstrip(_EDGE)
        return _settle_block(
            text,
            self.stand_ins,
            in_list="li" in parent_tags,
            top_level="li" not in parent_tags and "blockquote" not in parent_tags,
            lead=lead,
        )

    def convert__document_(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        """Settle the document, stripped first: edge whitespace is never content.

        Stripped before it is settled, not after, because where the first
        line starts decides what it would be read as: ``" # x"`` is not a
        heading until the space goes. It is also why the Markdown is stripped
        at all -- a digest of a body must not depend on its edges.
        """

        text = self.stand_ins.settle_breaks(text).strip()
        return _settle_block(text, self.stand_ins, in_list=False, top_level=True)

    def convert_p(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        if self._deferred(parent_tags):
            return str(self._inherited("convert_p")(el, text, parent_tags))
        lead = _line_lead(el, self._numbers) if "li" in parent_tags else ()
        text = self._settle(text, parent_tags, lead=lead)
        return f"\n\n{text}\n\n" if text else ""

    def convert_div(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        if self._deferred(parent_tags):
            return str(self._inherited("convert_div")(el, text, parent_tags))
        lead = _line_lead(el, self._numbers) if "li" in parent_tags else ()
        text = self._settle(text, parent_tags, lead=lead)
        return f"\n\n{text}\n\n" if text else ""

    convert_article = convert_div
    convert_center = convert_div
    convert_dl = convert_div
    convert_section = convert_div
    # ``markdownify`` writes a definition as ":   text" under its term, one
    # line break apart: python-markdown, with no definition-list extension,
    # shows the colon and runs the two into one paragraph. Two paragraphs
    # keep both texts and nothing else.
    convert_dd = convert_div
    convert_dt = convert_div

    def convert_blockquote(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        if self._deferred(parent_tags):
            return str(self._inherited("convert_blockquote")(el, text, parent_tags))
        text = self._settle(text or "", parent_tags | {"blockquote"})
        if not text:
            return "\n"
        lines = [f"> {line}" if line else ">" for line in text.split("\n")]
        if "li" not in parent_tags:
            return "\n{}\n\n".format("\n".join(lines))
        if _line_items(el):
            # The quote opens a list item: python-markdown never detabs an
            # item's first block, so the quote's later lines have to be its
            # lazy continuation, at the start of the line.
            lines[1:] = [self.stand_ins.lazy + line for line in lines[1:]]
            return "\n\n{}\n\n".format("\n".join(lines))
        # Anywhere else in an item a quote opens only after a blank line: the
        # item's later lines are indented, and ``>`` counts three spaces in
        # at most.
        return "\n\n{}\n\n".format("\n".join(lines))

    def convert_li(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        bullet = _bullet(el, self._numbers)
        spaced = False
        if self._deferred(parent_tags):
            text = (text or "").strip()
        else:
            text = self.stand_ins.settle_breaks(text or "")
            text = _LEADING_BLANK_LINES.sub("", text).rstrip(_EDGE)
            parent = el.parent
            deep = _deep_list(parent)
            spaced = deep and parent is not None and self._shown_items(parent) > 1
            # The item after a loose one is loose too: python-markdown reads
            # it as the first item of a new block, and wraps its text. So is
            # an item that shares its first line with another's bullet: a
            # list after its text is eight spaces in, too deep to follow
            # that line directly (see _deep_list).
            previous = el.find_previous_sibling("li")
            stacked = len(_line_items(el)) > 1
            loose = deep or stacked or id(previous) in self._loose_items
            if not _opens_with_a_block(el):
                text = _loosened(text, loose)
            lead = _line_lead(el, self._numbers)
            text = self._settle(text, parent_tags | {"li"}, lead=lead)
        if not text:
            return "\n"
        blocks = "\n\n" in text or spaced
        if blocks:
            self._loose_items.add(id(el))
        first_line, *rest = text.split("\n")
        lazy = self.stand_ins.lazy
        indented = [
            line if not line or line.startswith(lazy) else f"    {line}"
            for line in rest
        ]
        item = "\n".join([bullet + first_line, *indented]) + "\n"
        # An item of several blocks needs a blank line after it, or the next
        # item's line is read as the last block's lazy continuation.
        return item + "\n" if blocks else item

    def convert_hN(self, n: int, el: Tag, text: str, parent_tags: set[str]) -> str:
        if self._deferred(parent_tags):
            return str(self._inherited("convert_hN")(n, el, text, parent_tags))
        text = _WHITESPACE.sub(" ", text.strip())
        text = _settle_inline(text, self.stand_ins, heading=True)
        return "\n\n{} {}\n\n".format("#" * max(1, min(6, n)), text)

    def convert_td(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        span = str(el.get("colspan") or "")
        colspan = max(1, min(1000, int(span))) if span.isdigit() else 1
        text = _settle_inline(
            text.strip().replace("\n", " "), self.stand_ins, cell=True
        )
        return " " + text + " |" * colspan

    convert_th = convert_td

    # -- markup ----------------------------------------------------------------

    def _edges(self, text: str) -> tuple[str, str, str]:
        """Split ``text`` into what goes before markup, inside it, and after.

        ``markdownify``'s ``chomp`` moves spaces outside the markup so it
        never opens or closes on whitespace; hard breaks at the edge have to
        move out the same way, or ``**a  \\n**`` is not emphasis.
        """

        edge = _EDGE + self.stand_ins.hard_break
        content = text.strip(edge)
        head = text[: len(text) - len(text.lstrip(edge))]
        tail = text[len(text.rstrip(edge)) :] if content else ""
        return self._edge(head), content, self._edge(tail)

    def _edge(self, side: str) -> str:
        breaks = side.count(self.stand_ins.hard_break)
        if breaks:
            return (self.stand_ins.hard_break + "\n") * breaks
        return " " if side else ""

    def _emphasis(self, markup: str, text: str, parent_tags: set[str]) -> str:
        if "_noformat" in parent_tags:
            return text
        before, content, after = self._edges(text)
        if not content:
            return before
        return before + markup + content + markup + after

    def convert_b(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        return self._emphasis("**", text, parent_tags)

    convert_strong = convert_b

    def convert_em(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        return self._emphasis("*", text, parent_tags)

    convert_i = convert_em

    def convert_s(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        """Keep struck text's words: python-markdown has no strikethrough."""

        return text

    convert_del = convert_s
    convert_strike = convert_s

    def convert_title(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        """Drop a ``<title>``, which a browser shows only in its tab."""

        return ""

    def convert_br(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        if "_inline" in parent_tags:
            return " "
        if "pre" in parent_tags:
            return "\n"
        if "_noformat" in parent_tags:
            return " "
        return self.stand_ins.hard_break + "\n"

    def convert_a(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        if "_noformat" in parent_tags:
            return text
        before, text, after = self._edges(text)
        if not text:
            return before
        href = el.get("href")
        title = el.get("title")
        if not href:
            return before + text + after
        href = str(href)
        pasted = self.stand_ins.restore(text) == href
        if pasted and not title and _AUTOLINK.fullmatch(f"<{href}>"):
            # A pasted URL: the one autolink python-markdown renders as a link.
            return f"{before}<{href}>{after}"
        text = _settle_label(text, self.stand_ins)
        titled = ' "{}"'.format(str(title).replace('"', r"\"")) if title else ""
        return f"{before}[{text}]({href}{titled}){after}"

    def convert_img(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        alt = _WHITESPACE.sub(" ", str(el.get("alt") or "")).strip()
        alt = _settle_label(self.stand_ins.shadow(alt), self.stand_ins)
        src = str(el.get("src") or "")
        title = _WHITESPACE.sub(" ", str(el.get("title") or "")).strip()
        titled = ' "{}"'.format(title.replace('"', r"\"")) if title else ""
        return f"![{alt}]({src}{titled})"

    def convert_pre(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        if not text:
            return ""
        text = re.sub(r"[ \n]*$", "", re.sub(r"^[ \n]*\n", "", text))
        nested = "li" in parent_tags or "blockquote" in parent_tags
        if nested and not _code_block_fits(el):
            # No code block can be written here (see _code_block_fits), so
            # the lines are kept as the literal text they are.
            lines = [line.strip(" ") for line in text.split("\n")]
            joined = (self.stand_ins.hard_break + "\n").join(filter(None, lines))
            return self.stand_ins.shadow(joined)
        if nested:
            lines = text.split("\n")
            code = "\n".join(f"    {line}" if line else "" for line in lines)
            return f"\n\n{code}\n\n"
        fence = "```"
        lines = [line.rstrip(" ") for line in text.split("\n")]
        while fence in lines:
            fence += "`"
        return f"\n\n{fence}\n{text}\n{fence}\n\n"

    def convert_list(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        """End a nested list with a blank line, for whatever its item holds next.

        ``markdownify`` ends a list inside a list item with no line break at
        all, so the item's text after it joined the list's last item, and a
        quote after it became that item's lazy continuation. When nothing
        follows, the item strips the blank line with the rest of its edge.
        """

        markdown = str(self._inherited("convert_list")(el, text, parent_tags))
        if "li" not in parent_tags or self._deferred(parent_tags):
            return markdown
        return markdown + "\n\n"

    convert_ul = convert_list
    convert_ol = convert_list
    convert_dir = convert_list
    convert_menu = convert_list


#: ``markdownify`` options; the converter's overrides decide the rest.
#:
#: ``wrap`` is what turns a newline inside text into a space, and
#: ``wrap_width=None`` is what stops it wrapping lines.
_MARKDOWNIFY_OPTIONS: dict[str, Any] = {"wrap": True, "wrap_width": None}


def html_to_markdown(html: str) -> str:
    """Convert HTML to literal-safe Markdown.

    Parameters
    ----------
    html : str
        The HTML to convert.

    Returns
    -------
    str
        The Markdown, every literal character spelled so python-markdown
        renders it as that character.
    """

    stand_ins = _StandIns(html)
    markdown = str(
        _LiteralSafeConverter(stand_ins, **_MARKDOWNIFY_OPTIONS).convert(html)
    )
    return markdown.replace(stand_ins.lazy, "")


def _literal_markdown(text: str) -> str:
    """Spell plain text as Markdown that renders as that text.

    The degraded path's final step: :func:`_strip_tags` returns text, and
    :meth:`GlpiContentConverter.from_transport` returns Markdown, so the
    text is escaped by the same rules as any text node -- every line a line
    start, one container per blank-line-separated block.
    """

    stand_ins = _StandIns(text)
    return _settle_block(
        stand_ins.shadow(text),
        stand_ins,
        in_list=False,
        top_level=True,
        soft_breaks=True,
    )


class GlpiContentConverter:
    """Convert content between GLPI HTML payloads and canonical Markdown.

    The converter keeps the translation rules in one place so ticket, followup,
    task, and solution parsing all share the same content normalization.
    """

    @staticmethod
    def from_transport(value: object) -> str:
        """Convert one GLPI transport value into canonical Markdown.

        Empty input stays empty, plain text is preserved, and HTML content is
        converted through ``markdownify`` into Markdown that python-markdown
        renders back as the same text: the HTML's text is literal, so every
        character that would otherwise read as syntax is escaped, and nothing
        else is (see the module docstring and :class:`_LiteralSafeConverter`).

        The HTML path is taken only when :func:`_looks_like_html` finds a real
        element. Both directions of that decision matter, because this method
        is also wired as the inbound validator for caller-authored content:
        text sent down the HTML path loses whatever the parser does not
        recognise, and Markdown sent down it comes back escaped -- a value
        carrying one real element is read as HTML throughout, so its
        ``**bold**`` is the eight characters it spells there.

        There are therefore three outcomes, not two. Real HTML that fits
        the stack is converted. Real HTML that does not is stripped to its
        text instead: ``markdownify`` recurses about two frames per
        nesting level, so the conversion is *attempted* and its
        ``RecursionError`` answered, rather than the depth predicted and a
        bound applied. The caller gets a readable body either way;
        **this method degrades, it does not truncate, and it does not
        raise for depth.**

        Attempting it is what makes the answer exact. The budget is not
        1000 frames, it is whatever is left of the stack when the
        conversion starts, and that belongs to the caller -- an
        application reading ``.content`` from inside a request handler, a
        template render or a recursive walk has less of it than a script
        does. No bound computed in advance can know that number, so the
        previous design guessed low, 200 against a measured cliff of 494,
        and flattened bodies that would have converted. It also had to
        estimate the depth of the tree, and three rounds of review found
        seven ways for that estimate to come in *under* the real one --
        each of which sent a document to ``markdownify`` and into the
        ``RecursionError`` the bound existed to prevent.

        One consequence is the price of that exactness and worth naming:
        the outcome now depends on the caller's remaining stack, so the
        same body can convert from one call site and degrade from a
        deeper one. Nothing is lost either way -- the degraded rendering
        keeps every character of prose -- but a caller comparing two
        renderings of one body should know which knob moved it.

        Self-closing void tags are written bare before conversion, which
        works around a ``beautifulsoup4`` defect that silently dropped
        everything after the second spelling of ``<br>`` in a body that
        used both -- see :func:`_canonicalise_void_elements`.

        A document ``html.parser`` refuses outright takes the degraded
        path as well, rather than the exception it used to. ``<![FOO[``
        is the reachable case: an unknown marked-section keyword, which
        ``_markupbase`` raises ``AssertionError`` for and ``bs4``
        re-raises as ``ParserRejectedMarkup``. A caller who can read
        their text is better off than one holding an error, and there is
        nothing else to be done with such a body, so it is stripped too.
        The stripped text is escaped like any other literal text
        (:func:`_literal_markdown`), so it renders as itself.

        Raises
        ------
        GlpiContentError
            The parser failed for some reason other than depth. The original
            exception is attached as ``__cause__``. Nothing is expected to
            reach this -- it is here so a parser fault cannot escape
            ``except GlpiError`` the way a bare ``RecursionError`` used to.
        """

        content = str(value or "")
        if not content.strip():
            return ""
        if not _looks_like_html(content):
            return content.strip()
        try:
            markdown = html_to_markdown(_canonicalise_void_elements(content))
        except (RecursionError, ParserRejectedMarkup):
            # The tree is deeper than the stack left, or the parser will
            # not build it at all. Both are answered with the text.
            try:
                return _literal_markdown(_strip_tags(content))
            except RecursionError as exc:
                # Reachable only from a caller already within a few frames
                # of the limit, where stripping cannot run either. Named
                # rather than allowed to escape as a bare builtin, which is
                # what this taxonomy exists for.
                raise GlpiContentError(
                    "Could not convert GLPI HTML content to Markdown: the "
                    "caller's stack left too little room even to strip its "
                    "tags."
                ) from exc
        except Exception as exc:
            raise GlpiContentError(
                "Could not convert GLPI HTML content to Markdown "
                f"({type(exc).__name__}: {exc})."
            ) from exc
        # Already stripped: the document converter strips before it settles.
        return markdown

    @staticmethod
    def to_transport(value: object) -> str:
        """Convert one canonical Markdown value into GLPI HTML.

        Empty Markdown stays empty, while non-empty content is rendered through
        the configured Markdown extensions used by the package.

        There is no depth ceiling on this direction and no degraded path.
        Inbound content is whatever GLPI happens to hold, so it has to be
        survivable; outbound content is what the caller just wrote, so a
        failure is worth reporting rather than papering over. ``markdown``
        recurses on nested constructs too -- measured, a list indented 495
        levels raises -- so the failure is caught and named.

        Raises
        ------
        GlpiContentError
            The Markdown could not be rendered. The original exception is
            attached as ``__cause__``.
        """

        markdown = str(value or "")
        if not markdown.strip():
            return ""
        try:
            html = markdown_to_html(
                markdown,
                extensions=_MARKDOWN_EXTENSIONS,
                output_format="html5",
            )
        except Exception as exc:
            raise GlpiContentError(
                "Could not render Markdown content as GLPI HTML "
                f"({type(exc).__name__}: {exc})."
            ) from exc
        return str(html).strip()
