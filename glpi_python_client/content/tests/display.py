"""What a browser displays of a body, as comparable data.

The content tests compare displays rather than HTML: the converters
legitimately respell markup -- ``<b>`` becomes ``<strong>``, a ``<div>`` a
``<p>`` -- and none of that is visible. What is kept is what a reader sees:
the blocks, the words in each (whitespace collapsed, as HTML collapses it),
and for every character whether it is bold, italic, code or a link.

A table's rows are its own: a table nested in a cell is read as words in that
cell, as a browser shows it inside the cell. A table with no row displays
nothing.

Kept identical, but for the package's names, to the oracle of
``easyvista-python-client`` 0.4.0, whose converter is this one. That
package added :func:`one_line`, :func:`text_words` and :func:`loose`, and
changed two rules of the 0.6.0 oracle, each marked where it is:

* inside one line -- a cell, a heading, a link -- the edge of a block or of
  a nested table's cell is a word boundary, as a browser shows it (a new
  line, a new box) and as the converter writes it (a space); and
* an ordered list's ``start`` is read with ``isdecimal``, as the converter
  reads it, where ``isdigit`` made the oracle itself raise on ``"²"``. So
  the oracle cannot see where a browser numbers otherwise: from 3 for
  ``" 3"``, ``"+3"`` or ``"3abc"``, and from 1 for a full-width 3
  (U+FF13).

Since 0.6.1, with ``easyvista-python-client`` 0.4.1, a rule (``<hr>``)
inside an inline element counts as a block, where the oracle read it as
nothing: a browser draws ``<u><hr></u>`` as a rule.

What the oracle cannot see: underline and highlight (``<u>``, ``<mark>``,
``<ins>``), struck text, link and image titles, and line breaks inside a
heading.
"""

from __future__ import annotations

import urllib.parse

from bs4 import BeautifulSoup
from bs4.element import (
    Comment,
    Declaration,
    Doctype,
    NavigableString,
    ProcessingInstruction,
    Tag,
)

_HIDDEN = {"script", "style", "title", "head", "template"}
_PARAGRAPHS = {"p", "div", "section", "article", "center", "body", "html", "main"}
_HEADINGS = {f"h{level}" for level in range(1, 7)}
_BLOCKS = _PARAGRAPHS | _HEADINGS | {"ul", "ol", "li", "blockquote", "pre", "table"}
_FORMATS = {
    "b": "strong",
    "strong": "strong",
    "i": "em",
    "em": "em",
    "code": "code",
    "kbd": "code",
    "samp": "code",
}
_SKIPPED = (Comment, Doctype, Declaration, ProcessingInstruction)

#: Since 0.6.1: inside one line -- a cell, a heading, a link -- the
#: edge of a block or of a nested table's cell separates words. A browser
#: starts a new line or draws a new box there, so ``<td>a</td><td>b</td>``
#: or ``<p>a</p><p>b</p>`` inside a cell never displays ``ab``; the 0.6.0
#: oracle joined them, which failed the converter for writing ``a b``.
_WORD_EDGES = _BLOCKS | {"td", "th", "tr", "caption"}

Format = tuple[bool, bool, bool, str | None]

#: No formatting, and not in a link.
_PLAIN: Format = (False, False, False, None)


class _Words:
    """The words of one paragraph, each character with its formatting."""

    def __init__(self) -> None:
        self.words: list[tuple[object, ...]] = []
        self.current: list[object] = []

    def char(self, char: str, fmt: Format) -> None:
        if char.isspace():
            self.boundary()
        else:
            self.current.append((char, fmt))

    def token(self, token: object) -> None:
        self.current.append(token)

    def boundary(self) -> None:
        if self.current:
            self.words.append(tuple(self.current))
            self.current = []

    def line_break(self) -> None:
        self.boundary()
        self.words.append(("BR",))

    def finish(self) -> tuple[object, ...]:
        """The paragraph's words, less the line breaks at its edges."""

        self.boundary()
        words = list(self.words)
        while words and words[0] == ("BR",):
            words.pop(0)
        while words and words[-1] == ("BR",):
            words.pop()
        return tuple(words)


def _with_format(fmt: Format, name: str) -> Format:
    strong, em, code, href = fmt
    kind = _FORMATS.get(name)
    return (
        strong or kind == "strong",
        em or kind == "em",
        code or kind == "code",
        href,
    )


def _image(tag: Tag, fmt: Format) -> object:
    alt = " ".join(str(tag.get("alt") or "").split())
    return (("IMG", str(tag.get("src") or ""), alt), fmt)


def _inline(node: Tag, words: _Words, fmt: Format) -> None:
    for child in node.children:
        if isinstance(child, _SKIPPED):
            continue
        if isinstance(child, NavigableString):
            for char in str(child):
                words.char(char, fmt)
        elif isinstance(child, Tag) and child.name not in _HIDDEN:
            if child.name == "br":
                words.line_break()
            elif child.name == "img":
                words.token(_image(child, fmt))
            elif child.name == "a" and child.get("href"):
                _inline(child, words, (fmt[0], fmt[1], fmt[2], str(child.get("href"))))
            elif child.name in _WORD_EDGES:
                words.boundary()
                _inline(child, words, _with_format(fmt, child.name))
                words.boundary()
            else:
                _inline(child, words, _with_format(fmt, child.name))


def _has_block(node: Tag) -> bool:
    # Since 0.6.1: a rule is a block too, so <u><hr></u> draws its rule.
    return any(
        isinstance(child, Tag) and (child.name in _BLOCKS or child.name == "hr")
        for child in node.descendants
    )


def _list(node: Tag, fmt: Format) -> tuple[object, ...]:
    """A list: each non-empty item with the number it displays."""

    ordered = node.name == "ol"
    start = str(node.get("start") or "1")
    # Since 0.6.1: isdecimal, as the converter reads it. isdigit
    # accepts "²", and int("²") raises.
    first = int(start) if start.isdecimal() else 1
    items: list[object] = []
    for position, item in enumerate(node.find_all("li", recursive=False)):
        content = _display_blocks(item, fmt)
        if content:  # Markdown cannot spell an empty list item
            items.append((first + position if ordered else None, content))
    return (node.name, tuple(items)) if items else ()


def _table(node: Tag, fmt: Format) -> tuple[object, ...]:
    rows = []
    for row in node.find_all("tr"):
        if row.find_parent("table") is not node:
            continue  # a nested table's row shows inside its cell
        cells = []
        for cell in row.find_all(["td", "th"], recursive=False):
            inner = _Words()
            _inline(cell, inner, fmt)
            cells.append((cell.name == "th", inner.finish()))
        rows.append(tuple(cells))
    return ("table", tuple(rows)) if rows else ()


def _display_blocks(node: Tag, fmt: Format = _PLAIN) -> tuple[object, ...]:
    out: list[object] = []
    words = _Words()

    def flush() -> None:
        nonlocal words
        paragraph = words.finish()
        if paragraph:
            out.append(("p", paragraph))
        words = _Words()

    for child in node.children:
        if isinstance(child, _SKIPPED):
            continue
        if isinstance(child, NavigableString):
            for char in str(child):
                words.char(char, fmt)
            continue
        if not isinstance(child, Tag) or child.name in _HIDDEN:
            continue
        name = child.name
        if name in _PARAGRAPHS:
            flush()
            out.extend(_display_blocks(child, fmt))
        elif name in _HEADINGS:
            flush()
            heading = _Words()
            _inline(child, heading, fmt)
            out.append((name, heading.finish()))
        elif name in {"ul", "ol"}:
            flush()
            listed = _list(child, fmt)
            if listed:
                out.append(listed)
        elif name == "blockquote":
            flush()
            quoted = _display_blocks(child, fmt)
            if quoted:
                out.append(("quote", quoted))
        elif name == "pre":
            flush()
            out.append(("pre", child.get_text().strip("\n")))
        elif name == "hr":
            flush()
            out.append(("hr",))
        elif name == "table":
            flush()
            table = _table(child, fmt)
            if table:
                out.append(table)
        elif name == "br":
            words.line_break()
        elif name == "img":
            words.token(_image(child, fmt))
        elif _has_block(child):
            flush()
            out.extend(_display_blocks(child, _with_format(fmt, name)))
        elif name == "a" and child.get("href"):
            _inline(child, words, (fmt[0], fmt[1], fmt[2], str(child.get("href"))))
        else:
            _inline(child, words, _with_format(fmt, name))
    flush()
    return tuple(out)


def displayed(html: str) -> tuple[object, ...]:
    """Return what a browser displays of ``html``, as comparable data."""

    return _display_blocks(BeautifulSoup(html, "html.parser"))


def one_line(html: str) -> tuple[object, ...]:
    """Return ``html`` read as one paragraph of inline content.

    For the one shape whose display the converter changes on purpose: a
    table inside a link, which a browser draws as a table and the converter
    writes as the link's text (Markdown has no table inside a link). What it
    owes there is this: every word, in order, each with its formatting and
    its link.
    """

    words = _Words()
    _inline(BeautifulSoup(html, "html.parser"), words, _PLAIN)
    paragraph = words.finish()
    return (("p", paragraph),) if paragraph else ()


#: Where a browser starts a new word whatever the text says: a block's
#: edges, a line break, a cell and an image.
_BREAKING = frozenset(
    """
    address article aside blockquote body br caption center dd details dir div
    dl dt fieldset figcaption figure footer form h1 h2 h3 h4 h5 h6 header hr
    html img li main menu nav ol p pre section summary table tbody td tfoot th
    thead tr ul
    """.split()
)


def text_words(html: str) -> list[str]:
    """Return the words ``html`` displays, in order, without their formatting.

    A blunt check that does not depend on :func:`displayed`. A
    word ends only where a browser breaks the text -- see ``_BREAKING`` --
    never at an inline tag's edge, so ``foo<b>bar</b>`` is one word, as it
    displays. The walk keeps its own stack, so a deep body costs no
    recursion.
    """

    soup = BeautifulSoup(html, "html.parser")
    pieces: list[str] = []
    stack: list[object] = [soup]
    while stack:
        node = stack.pop()
        if isinstance(node, Tag):
            if node.name in _HIDDEN:
                continue
            edge = " " if node.name in _BREAKING else ""
            pieces.append(edge)
            stack.append(edge)  # the closing edge, taken after the children
            stack.extend(reversed(node.contents))
        elif isinstance(node, _SKIPPED):
            continue
        else:  # a text node, or the str closing edge pushed above
            pieces.append(str(node))
    return "".join(pieces).split()


def loose(display: object) -> object:
    """Return ``display`` with every string percent-decoded.

    cmark-gfm percent-encodes a link or image target it renders -- a space
    becomes ``%20``, a backslash ``%5C`` -- and a browser follows either
    spelling to the same place. Comparing loosely lets a test hold the
    converter to the display without holding it to one URL spelling.
    """

    if isinstance(display, str):
        return urllib.parse.unquote(display)
    if isinstance(display, tuple):
        return tuple(loose(value) for value in display)
    return display
