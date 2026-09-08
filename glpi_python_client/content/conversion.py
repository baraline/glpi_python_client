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
#: it lives in ``bs4.builder._htmlparser``, which is private -- and the
#: subset invariant is asserted against a real parse in the unit tests, so
#: a future ``bs4`` cannot quietly break it.
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
#: converts is 492 levels -- and the same 492 whether the nesting is
#: ``<div>``, ``<p>``, ``<blockquote>``, ``<ul><li>`` or
#: ``<table><tr><td>``, which is what identifies the cost as per-level.
#: One level past it raises ``RecursionError``.
#:
#: The ceiling is 200 rather than 492 because the budget is not 1000 frames,
#: it is whatever is left of the stack when the conversion starts, and that
#: belongs to the caller. Measured at the conversion call site: 8 frames
#: through the synchronous client, 16 through the asynchronous one, 37 from
#: twenty nested awaits. The library's own contribution is negligible; an
#: application calling from inside a request handler, a template render or a
#: recursive walk is not. Converting a 200-level document was measured to
#: peak at 403 frames, so it stays safe until the caller's own stack passes
#: roughly 590 -- and no document a human wrote nests 200 elements deep.
#:
#: **``sys.setrecursionlimit`` is deliberately not called, here or anywhere
#: in the package.** It is process-global state that belongs to the
#: application, not to a library an application imported; and raising the
#: limit past what the C stack can hold turns a catchable ``RecursionError``
#: into a hard interpreter crash -- on Windows, an access violation with no
#: traceback. It moves the cliff and makes falling off it worse. Bounding
#: the input is the fix that does not.
MAX_HTML_DEPTH = 200

#: Every markup construct, in the order ``html.parser`` dispatches them.
#:
#: One alternation rather than a sequence of substitutions, because the
#: parser reads left to right and the constructs overlap: in
#: ``<?php x<!-- <div><div> -->`` the processing instruction ends at the
#: first ``>``, which lands *inside* what looks like a comment, and the
#: ``<div>`` after it is a real element. Removing comments globally first
#: gets that document wrong in both directions. ``finditer`` consumes each
#: match before looking for the next, so a single pattern reproduces the
#: dispatch for free; the branch order is the parser's own.
#:
#: The branches, in order:
#:
#: 1. A terminated comment. First, so a legitimate comment containing
#:    ``>`` is not cut short by branch 3.
#: 2. A ``CDATA`` section, capturing its body -- the parser keeps that
#:    body as text, and branch 3 would swallow it.
#: 3. A doctype, an unterminated comment, a bogus or malformed
#:    declaration, or a processing instruction, consumed through its first
#:    ``>``. Measured on the parser: ``<custom><!--oops</custom><br>``
#:    puts the ``<br>`` *inside* ``custom``, because ``</custom>`` fell in
#:    the bogus comment and became text -- so reading that ``</custom>``
#:    as a real close under-counts, the one error that ends in a
#:    ``RecursionError``. Conversely ``<!--oops><div><div>`` really is two
#:    levels: recovery ends at the ``>``, it does not swallow the rest of
#:    the document. Trailing ``>?`` covers running to end-of-input.
#: 4. A ``<script>`` or ``<style>`` element with its body, closed or not.
#:    Its content is raw text to the parser, so no tag inside it counts;
#:    ``strip=["script", "style"]`` discards both on the normal path, so
#:    the degraded path discards them too. The ``$`` alternative covers an
#:    unclosed one, whose body the parser also reads to the end as text.
#: 5. A tag. The ``<`` must abut the name, matching what the parser
#:    accepts -- which is what keeps ``2 < 3 > 1`` and ``x <= y`` text: a
#:    space after ``<`` means no tag, so arithmetic never reaches the HTML
#:    path in the first place.
#:
#: Branches 4 and 5 read attributes with :data:`_ATTRIBUTES` rather than
#: ``[^<>]*``, because an attribute value may legally contain ``<`` and
#: ``>``. Skipping over quotes is not cosmetic: measured,
#: ``'<div title="</div>">' * 600`` used to measure **0** levels deep when
#: the parser builds 600, because the quoted ``</div>`` was read as a real
#: close. That document went to ``markdownify`` and raised -- the one
#: direction of error the ceiling exists to prevent.
_ATTRIBUTES = r"""(?:"[^"]*"|'[^']*'|[^<>"'])*"""

_MARKUP = re.compile(
    r"<!--.*?-->"
    r"|<!\[CDATA\[(?P<cdata>.*?)\]\]>"
    r"|(?P<decl><[!?][^>]*>?)"
    r"|<(?P<raw>script|style)\b" + _ATTRIBUTES + r">"
    r"(?P<rawbody>.*?)(?:</(?P=raw)\s*>|(?P<rawcut>$))"
    r"|</?(?P<name>[a-zA-Z][a-zA-Z0-9]*)" + _ATTRIBUTES + r">",
    re.DOTALL | re.IGNORECASE,
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

#: A declaration the parser can resolve, whose text is therefore not text.
#:
#: ``html.parser`` turns ``<!DOCTYPE html>`` and ``<!anything>`` into a
#: declaration node, which ``markdownify`` renders as nothing -- so
#: :func:`_strip_tags` drops them too. Everything else matched by the
#: ``decl`` branch (an unterminated comment, an unterminated marked
#: section, a processing instruction) the parser hands back as character
#: data and the converting path prints, so it is kept. Measured against
#: the converting path, construct by construct.
_RESOLVED_DECLARATION = re.compile(r"<!\s*[A-Za-z]")


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


def _html_nesting_depth(content: str) -> int:
    """Return how deeply ``content`` nests, without recursing to find out.

    One linear pass over the tag candidates, keeping the open elements on a
    list and its high-water mark. Linear in the length of the input and flat
    in the stack, which is the point: the number this returns decides
    whether a recursive parser is safe to run, so computing it must not need
    one. Measured, it costs 4-6% of the ``markdownify`` call it guards.

    Four rules make the count match the tree ``html.parser`` will actually
    build. The first two are what an open/close counter would get wrong:

    * **A closing tag pops by name, or is ignored.** ``bs4`` looks up the
      stack for a matching open element and pops nothing when there is
      none. A plain counter decrements anyway, and then
      ``"<div></p>" * 600`` -- a Word or Outlook paste, not an adversarial
      input -- measures 1 when the parser builds 600. Measured: that
      document reached ``markdownify`` and raised. Interleaved tags
      (``<b><i>x</b></i>``) pop the same way the parser does.
    * **A childless node is still a node.** A void element or a ``<foo/>``
      sits one level below its parent, so ``"<br>" * 5000`` is one level,
      not none.
    * **Unknown names count.** ``html.parser`` gives ``<foo>`` a node like
      any other, so it nests like any other -- measured, ``"<foo>" * 600``
      inside a document with one real element raises just as ``<div>``
      does. Whether ``markdownify`` later knows how to *render* the element
      is a separate question from whether it has to walk it.
    * **An unclosed tag still counts.** ``html.parser`` does not auto-close
      ``<p>`` or ``<li>``, so ``"<p>" * 5000`` really is 5000 levels, and
      raises exactly like the balanced shape.

    Comments, declarations, processing instructions and raw-text elements
    are skipped by :data:`_MARKUP` itself, which is where the ordering
    subtleties live. That is not only about over-counting a ``<div>`` in a
    code sample: a closing tag swallowed by a bogus comment is a level the
    parser keeps and a careless scan gives back.

    The result was checked against a ground-truth iterative walk of the
    tree ``bs4`` actually builds, over 15000 fuzzed documents mixing every
    construct above plus attribute values containing ``<``, ``>`` and
    whole tags: **worst error 0 in either direction.** Where the two could
    still disagree, over-counting is the direction to err in -- it costs a
    document that degrades when it need not have, while under-counting is
    a crash.

    Parameters
    ----------
    content : str
        Raw HTML, or text that may contain angle brackets.

    Returns
    -------
    int
        The depth of the deepest element the parser would build. ``0`` for
        text with no tags at all.
    """

    if "<" not in content:
        return 0
    stack: list[str] = []
    open_names: Counter[str] = Counter()
    deepest = 0
    for match in _MARKUP.finditer(content):
        if match.group("raw") is not None:
            # Raw-text elements hold no markup, but the element is still a
            # node one level below whatever is open around it.
            deepest = max(deepest, len(stack) + 1)
            continue
        name = match.group("name")
        if name is None:
            continue  # a comment, a declaration or a processing instruction
        name = name.lower()
        token = match.group(0)
        if token[1] == "/":
            if not open_names[name]:
                continue  # nothing of that name is open, so bs4 pops nothing
            while True:
                popped = stack.pop()
                open_names[popped] -= 1
                if popped == name:
                    break
        elif token.endswith("/>") or name in _VOID_ELEMENTS:
            deepest = max(deepest, len(stack) + 1)
        else:
            stack.append(name)
            open_names[name] += 1
            deepest = max(deepest, len(stack))
    return deepest


def _strip_tags(content: str) -> str:
    """Reduce HTML to its text without parsing it, keeping every word.

    The degraded path for a document too deeply nested to convert. One pass
    of :data:`_MARKUP` -- the same scanner the depth measurement uses, so
    the two agree about what is markup -- then whitespace tidying. No tree,
    no recursion, no depth ceiling of its own, so it answers for input of
    any shape. Measured at 4-8 MB/s depending on tag density, roughly ten
    times faster than the ``markdownify`` call it stands in for.

    It **degrades and never truncates.** The property, stated as something
    checkable: after collapsing whitespace, every character the converting
    path would have produced also appears here, in order. A superset, not
    an equality -- so no body says less because of the path it took, which
    is the only guarantee worth making about a fallback. Checked as a
    subsequence over 15000 fuzzed documents mixing tags, quoted
    attributes, entities, comments, marked sections, declarations,
    processing instructions and raw-text elements: **0 losing text.**

    Establishing that meant measuring what the converting path really
    keeps, construct by construct, rather than assuming. Three answers
    were counter-intuitive and each one was a silent deletion here before
    it was checked: a ``<script>``/``<style>`` body is *kept* (see
    :func:`_strip_tags` for why), so is a ``CDATA`` body, and so is the
    inside of any ``<!``/``<?`` construct the parser could not resolve.

    What it does **not** reproduce, none of which loses a character of
    prose:

    * Markup that only the converter can express: a link becomes its text
      without the target, an image contributes nothing, and a fenced block
      loses its fence -- so ``<pre>`` indentation is normalised away with
      the rest. A pasted log comes back as its own lines of text, not as
      a code block.
    * Whitespace is normalised harder. Runs of spaces collapse, and
      ``&nbsp;`` counts as whitespace, so ``&nbsp;``-padded column
      alignment does not survive.
    * Character references are resolved even inside a region the parser
      handed back as raw data, so a broken comment's ``&amp;`` comes back
      as ``&``. In the other direction, a handful of semicolon-less
      references stay literal here that the converter resolves -- see
      :func:`_resolve_references`, which errs that way on purpose.
    * A processing instruction keeps its ``<?`` and ``>`` as literal
      text, where the converter strips them.

    Parameters
    ----------
    content : str
        Raw HTML.

    Returns
    -------
    str
        The document's text, block boundaries preserved as line breaks and
        character references resolved.
    """

    pieces: list[str] = []
    cursor = 0
    for match in _MARKUP.finditer(content):
        pieces.append(content[cursor : match.start()])
        cursor = match.end()
        cdata = match.group("cdata")
        if cdata is not None:
            pieces.append(cdata)
            continue
        name = match.group("name")
        if name is not None:
            if name.lower() in _BLOCK_ELEMENTS:
                pieces.append("\n")
            continue
        if match.group("raw") is not None:
            # A `<script>`/`<style>` body. Kept, because -- against
            # first expectations -- the converting path keeps it:
            # ``markdownify``'s ``strip=`` removes an element's *markup*
            # and still walks its children, so the body arrives as text.
            # Dropping it here would make the same document say different
            # things depending on how deeply it happened to nest. An
            # *unterminated* one is the exception: the parser reads the
            # rest of the input as script text and prints none of it.
            if match.group("rawcut") is None:
                pieces.append("\n" + (match.group("rawbody") or "") + "\n")
            continue
        decl = match.group("decl")
        if decl is not None and not _RESOLVED_DECLARATION.match(decl):
            # An unterminated comment, an unterminated marked section, or
            # a processing instruction. ``html.parser`` resolves none of
            # them, gives up, and emits the region as character data --
            # so the converting path prints it and this keeps it. Only a
            # resolvable declaration is text on neither path.
            pieces.append(decl)
    pieces.append(content[cursor:])

    text = _resolve_references("".join(pieces))
    text = re.sub(r"[^\S\n]*\n[^\S\n]*", "\n", text)
    text = re.sub(r"[^\S\n]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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
                content,
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
