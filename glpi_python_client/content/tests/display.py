"""What a browser displays of a body, as comparable data.

The content tests compare displays rather than HTML: the converters
legitimately respell markup -- ``<b>`` becomes ``<strong>``, a ``<div>`` a
``<p>`` -- and none of that is visible. What is kept is what a reader sees:
the blocks, the words in each (whitespace collapsed, as HTML collapses it),
and for every character whether it is bold, italic, code or a link.

A table's rows are its own: a table nested in a cell is read as words in that
cell, as a browser shows it inside the cell. A table with no row displays
nothing.
"""

from __future__ import annotations

from bs4 import (
    BeautifulSoup,
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
            else:
                _inline(child, words, _with_format(fmt, child.name))


def _has_block(node: Tag) -> bool:
    return any(
        isinstance(child, Tag) and child.name in _BLOCKS for child in node.descendants
    )


def _list(node: Tag, fmt: Format) -> tuple[object, ...]:
    """A list: each non-empty item with the number it displays."""

    ordered = node.name == "ol"
    start = str(node.get("start") or "1")
    first = int(start) if start.isdigit() else 1
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
