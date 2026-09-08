"""Content conversion helpers for GLPI payloads.

This module translates between GLPI's HTML transport format and the package's
canonical Markdown representation used by the rich content models.

Both conversions run third-party parsers, and both walk the document
recursively, so both have a nesting ceiling. Inbound content is measured
before it is parsed and degraded past :data:`MAX_HTML_DEPTH` rather than
allowed to hit that ceiling; anything else that goes wrong in either
direction surfaces as :class:`~glpi_python_client.GlpiContentError` so no
parser fault escapes the package's exception taxonomy.
"""

from __future__ import annotations

import re
from collections import Counter
from html import unescape
from html.entities import html5 as _HTML5_REFERENCES
from html.parser import HTMLParser

from markdown import markdown as markdown_to_html
from markdownify import markdownify as html_to_markdown

from glpi_python_client._errors import GlpiContentError

#: Element names that make a ``<...>`` sequence markup rather than text.
#:
#: The HTML5 element set, which is what the parser behind ``markdownify``
#: will actually recognise. Anything outside it -- ``<Enter>``, ``<T>``,
#: ``</dev/null>`` -- parses as an *unknown* tag, whose markup is dropped
#: while its (usually empty) body is kept, so the token silently vanishes
#: from the middle of a sentence.
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
    address article aside blockquote br col dd details dialog div dl dt
    fieldset figcaption figure footer form h1 h2 h3 h4 h5 h6 header hgroup
    hr li main menu nav ol p pre search section summary table tbody td
    tfoot th thead tr ul
    """.split()
)

#: Nesting depth past which inbound HTML is stripped instead of converted.
#:
#: ``markdownify`` walks the parsed tree recursively and spends about two
#: CPython frames per nesting level. Measured against the default
#: 1000-frame limit, from a shallow stack, the deepest document that
#: converts is 494 levels: the same 494 for ``<div>``, ``<p>``,
#: ``<blockquote>`` and ``<table><tr><td>``, and 495 for ``<ul><li>``,
#: which is what identifies the cost as per-level. One level past it
#: raises ``RecursionError``.
#:
#: The ceiling is 200 rather than 494 because the budget is not 1000 frames,
#: it is whatever is left of the stack when the conversion starts, and that
#: belongs to the caller. The package's own contribution is small and, since
#: conversion moved to the attribute, no longer depends on how the record
#: was fetched: measured, 5 frames below the caller when ``.content`` is
#: read -- the same 5 whether the model came from ``model_validate`` or from
#: ``client.get_ticket`` -- and 9 on the write path, where the renderer runs
#: inside ``model_dump``. What is not small is an application reading
#: ``.content`` from inside a request handler, a template render or a
#: recursive walk. Converting a 200-level document was measured to peak at
#: 412 frames, so it stays safe until the caller's own stack passes about
#: 588 -- and no document a human wrote nests 200 elements deep.
#:
#: **``sys.setrecursionlimit`` is deliberately not called, here or anywhere
#: in the package.** It is process-global state that belongs to the
#: application, not to a library an application imported; and raising the
#: limit past what the C stack can hold turns a catchable ``RecursionError``
#: into a hard interpreter crash -- on Windows, an access violation with no
#: traceback. It moves the cliff and makes falling off it worse. Bounding
#: the input is the fix that does not.
MAX_HTML_DEPTH = 200

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

    Everything this module needs to know before it hands content to
    ``markdownify`` -- how deep the tree will be, which self-closing void
    tags to rewrite, and what the text is when the tree is too deep to
    walk -- is a question about ``html.parser``'s dispatch. This subclass
    asks ``html.parser`` instead of describing it.

    It replaces a regular expression that reproduced that dispatch by
    imitation. The imitation was wrong in five unbounded ways at once, and
    each was found only after it shipped: a comment closes on ``--\\s*>``
    and not only on ``-->``, ``</ script>`` ends raw text, ``<![IGNORE[``
    opens a marked section, ``</ div foo>`` is a bogus comment rather than
    an end tag, and ``<a href=/>`` leaves an element *open* because the
    unquoted value swallows the ``/``. Each made a document measure one
    level deep where the real tree was hundreds, which is the one error
    that ends in the ``RecursionError`` :data:`MAX_HTML_DEPTH` exists to
    prevent. Two more were cost rather than correctness: a run of
    whitespace inside a failing tag made the attribute pattern backtrack
    as ``(a+)*``, and a 62-byte body took 7.45 seconds.

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

    One pass answers all three questions, so a conversion scans once
    rather than once per question. ``collect_text`` is what separates
    them: measuring depth needs no text, and accumulating the pieces of a
    150 KB body when only the depth is wanted is waste.

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
        #: Open element names, innermost last.
        self.stack: list[str] = []
        #: How many of each name are open, so a close with no match can be
        #: ignored without walking the stack.
        self.open_names: Counter[str] = Counter()
        #: High-water mark of :attr:`stack`.
        self.deepest = 0
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

    def _leaf(self) -> None:
        if len(self.stack) + 1 > self.deepest:
            self.deepest = len(self.stack) + 1

    def handle_starttag(self, tag: str, attrs: object) -> None:
        """Open an element, or count a void one as the leaf it is.

        A void element is a node but never a parent, so it lifts the
        high-water mark without joining the stack -- which is why
        ``"<br>" * 5000`` is one level rather than five thousand.
        """

        if tag in _VOID_ELEMENTS:
            self._leaf()
        else:
            self.stack.append(tag)
            self.open_names[tag] += 1
            if len(self.stack) > self.deepest:
                self.deepest = len(self.stack)
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

        self._leaf()
        if tag in _VOID_ELEMENTS:
            token = self.get_starttag_text()
            start = self._at()
            if token is not None and self._content.startswith(token, start):
                self.void_spans.append((start, start + len(token)))
        self._boundary(tag)

    def handle_endtag(self, tag: str) -> None:
        """Pop to the matching open element, or pop nothing at all.

        ``bs4`` looks up the stack for a match and ignores a close with no
        open element of that name. A counter that decremented anyway made
        ``"<div></p>" * 600`` -- a Word or Outlook paste rather than an
        adversarial input -- measure 1 against a real 600. Interleaved
        tags (``<b><i>x</b></i>``) pop the way the parser pops them.
        """

        if self.open_names[tag]:
            while True:
                popped = self.stack.pop()
                self.open_names[popped] -= 1
                if popped == tag:
                    break
        self._boundary(tag)

    def handle_data(self, data: str) -> None:
        """Keep character data, a raw-text element's body included.

        A ``<script>`` or ``<style>`` body arrives here because the parser
        is in CDATA mode, and it is kept for the reason recorded in
        :func:`_strip_tags`: ``markdownify``'s ``strip=`` removes an
        element's markup and still walks its children, so the body
        reaches the converted output as text.
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
    convert either. So the partial scan is kept, the remainder of the
    source is handed to :attr:`_ParserScan.pieces` as text, and the depth
    reported by :func:`_html_nesting_depth` sends the document down the
    degraded path -- where it now yields its text instead of the
    :class:`GlpiContentError` the converting path would have raised.

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


def _html_nesting_depth(content: str) -> int:
    """Return how deeply ``content`` nests, without recursing to find out.

    One pass of :class:`_ParserScan`, keeping the open elements on a list
    and its high-water mark. Flat in the stack, which is the point: the
    number this returns decides whether a recursive parser is safe to
    run, so computing it must not need one. ``html.parser`` is itself an
    iterative scanner -- the recursion in the pipeline is
    ``markdownify``'s walk of the finished tree, not the parse that
    builds it.

    Exact, now, rather than approximately right. The count is the depth
    of the tree ``bs4`` will really build, because it is derived from the
    events of the parser ``bs4`` will really use; the rules that used to
    have to be restated here -- a close pops by name or is ignored, a
    childless node is still a node, an unknown name counts, an unclosed
    tag counts -- are either the parser's own behaviour or live on
    :class:`_ParserScan` beside the handler that implements them.

    Cost is linear in the document, and small against what it guards:
    measured at 6-18% of the ``markdownify`` call for tag-dense bodies (a
    400-row table, 8.4 ms against 47 ms) and 6% for sparse prose (154 KB,
    0.87 ms against 14 ms), where it is four times *faster* than the
    pattern it replaced.

    The one shape where ``html.parser`` is worse than linear is a
    document carrying no ``>`` at all: ``check_for_whole_start_tag``
    cannot complete a tag, ``close()`` then advances one character at a
    time, and each step rescans the tail -- measured, 32 KB of
    ``'<div a="'`` takes 13 seconds. The guard below answers that shape
    in constant time. It is also unreachable from
    :meth:`GlpiContentConverter.from_transport`, which runs
    :func:`_looks_like_html` first and needs a ``>`` to find an element
    at all; the guard is what makes a direct call safe as well. Once a
    ``>`` is present the parser is no longer the slower of the two:
    128 KB of the same shape costs it 57 ms against the pattern's 66 ms.

    Verified against a ground-truth iterative walk of the tree ``bs4``
    actually builds, over fuzzed documents whose token alphabet carries
    every construct any review round raised -- including the four whose
    absence is why the previous corpus could not have found the defects
    it missed: ``-- >``, ``</ script>``, ``<![IGNORE[`` and runs of
    whitespace and quotes inside a tag.

    Parameters
    ----------
    content : str
        Raw HTML, or text that may contain angle brackets.

    Returns
    -------
    int
        The depth of the deepest element the parser would build. ``0``
        for text with no tags at all, and ``MAX_HTML_DEPTH + 1`` for a
        document the parser rejects, so that it degrades to text rather
        than being handed to a converter that will reject it too.
    """

    if "<" not in content or ">" not in content:
        return 0
    scan = _scan(content)
    if scan.rejected:
        return MAX_HTML_DEPTH + 1
    return scan.deepest


def _strip_tags(content: str) -> str:
    """Reduce HTML to its text without building a tree, keeping every word.

    The degraded path for a document too deeply nested to convert. One
    pass of :class:`_ParserScan` -- the same scan the depth measurement
    uses, so the two cannot disagree about what is markup -- then
    whitespace tidying. No tree, no recursion, no depth ceiling of its
    own, so it answers for input of any shape.

    It **degrades and never truncates.** The property, stated as
    something checkable: after collapsing whitespace, every character the
    converting path would have produced also appears here, in order. A
    superset, not an equality -- so no body says less because of the path
    it took, which is the only guarantee worth making about a fallback.

    Establishing that meant measuring what the converting path really
    keeps, construct by construct, rather than assuming. Three answers
    were counter-intuitive and each was a silent deletion here before it
    was checked: a ``<script>``/``<style>`` body is *kept*, because
    ``markdownify``'s ``strip=`` removes an element's markup and still
    walks its children; so is a ``CDATA`` body; and so is the inside of
    any ``<!``/``<?`` construct the parser could not resolve, which it
    hands back as character data.

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
        # text the parser would flush on ``close()`` -- and answering it
        # here keeps the scan away from the one shape that costs
        # ``html.parser`` more than linear time. See
        # :func:`_html_nesting_depth`.
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


class GlpiContentConverter:
    """Convert content between GLPI HTML payloads and canonical Markdown.

    The converter keeps the translation rules in one place so ticket, followup,
    task, and solution parsing all share the same content normalization.
    """

    @staticmethod
    def from_transport(value: object) -> str:
        """Convert one GLPI transport value into canonical Markdown.

        Empty input stays empty, plain text is preserved, and HTML content is
        normalized through ``markdownify`` with the package's preferred options.

        The HTML path is taken only when :func:`_looks_like_html` finds a real
        element. Both directions of that decision matter, because this method
        is also wired as the inbound validator for caller-authored content:
        text sent down the HTML path loses whatever the parser does not
        recognise, and Markdown sent down it comes back escaped.

        There are therefore three outcomes, not two. Real HTML nested no
        deeper than :data:`MAX_HTML_DEPTH` is converted. Real HTML nested
        deeper than that is stripped to its text instead -- ``markdownify``
        recurses per level and would exhaust the interpreter's stack, so the
        depth is measured first, flatly, by :func:`_html_nesting_depth`. The
        caller gets a readable body either way; **this method degrades, it
        does not truncate, and it does not raise for depth.**

        Self-closing void tags are written bare before conversion, which
        works around a ``beautifulsoup4`` defect that silently dropped
        everything after the second spelling of ``<br>`` in a body that
        used both -- see :func:`_canonicalise_void_elements`.

        A document ``html.parser`` refuses outright takes the degraded
        path as well, rather than the exception it used to. ``<![FOO[``
        is the reachable case: an unknown marked-section keyword, which
        ``bs4`` turns into ``ParserRejectedMarkup``. There is nothing to
        gain from handing such a body to a converter that will reject it
        too, and a caller who can read their text is better off than one
        holding an error -- so :func:`_html_nesting_depth` reports past
        the ceiling and the body is stripped.

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
        if _html_nesting_depth(content) > MAX_HTML_DEPTH:
            return _strip_tags(content)

        try:
            markdown = html_to_markdown(
                _canonicalise_void_elements(content),
                heading_style="ATX",
                bullets="-",
                strip=["script", "style"],
                escape_underscores=False,
                escape_asterisks=False,
            )
        except Exception as exc:
            raise GlpiContentError(
                "Could not convert GLPI HTML content to Markdown "
                f"({type(exc).__name__}: {exc})."
            ) from exc
        return str(markdown).strip()

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
