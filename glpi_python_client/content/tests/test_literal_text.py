"""Literal text reads back as the text it was, not as Markdown syntax.

``from_transport`` turns GLPI's HTML into Markdown, and ``to_transport`` -- or
any python-markdown with the same four extensions, which is what a peer
system renders the Markdown with -- turns it back. Text in the HTML is
literal: a ``__init__`` a user typed is eight characters, not bold ``init``.
Markdown has one spelling for both, so the converter has to spell the literal
one so that python-markdown cannot mistake it, and it has to do it in the
HTML-to-Markdown step: that is the last point where literal text and markup
can still be told apart.

The property every test here comes back to, checked with an HTML parser
rather than by eye:

* ``to_transport(from_transport(html))`` **displays what ``html`` displays**
  -- the same words, the same formatting on each character, the same block
  structure -- for every shape Markdown can express; and
* the Markdown is **a fixed point**: reading back what it renders gives the
  same Markdown again.

It is asserted over hand-picked regressions, over realistic ticket bodies,
and over a seeded fuzzer that puts every character python-markdown treats as
syntax at every position -- line start, word boundary, inside a word, in
cells, list items, headings and link text.

Escaping is also **minimal**: a character is escaped only where
python-markdown would otherwise read it as syntax, so ordinary prose -- a
file name with underscores, a Windows path, a mid-sentence ``#``, a hyphen,
``R&D`` -- comes back exactly as it did before escaping existed.
"""

from __future__ import annotations

import random
from html import escape

import pytest
from bs4 import (
    BeautifulSoup,
    Comment,
    Declaration,
    Doctype,
    NavigableString,
    ProcessingInstruction,
    Tag,
)
from markdown import Markdown

from glpi_python_client.content import conversion
from glpi_python_client.content.conversion import GlpiContentConverter

read = GlpiContentConverter.from_transport
render = GlpiContentConverter.to_transport

# ---------------------------------------------------------------------------
# What a browser displays of a body
# ---------------------------------------------------------------------------
#
# The comparison has to be on the display rather than on the HTML: the two
# converters legitimately respell markup -- ``<b>`` becomes ``<strong>``, a
# ``<div>`` becomes a ``<p>``, a list item's lone paragraph loses its
# ``<p>`` -- and none of that is visible. What is kept is what a reader sees:
# the blocks, the words in each (whitespace collapsed, as HTML collapses it),
# and for every character whether it is bold, italic, code or a link.

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

#: No formatting, and not in a link.
_PLAIN: tuple[bool, bool, bool, str | None] = (False, False, False, None)


class _Words:
    """The words of one paragraph, each character with its formatting."""

    def __init__(self) -> None:
        self.words: list[tuple[object, ...]] = []
        self.current: list[object] = []

    def char(self, char: str, fmt: tuple[bool, bool, bool, str | None]) -> None:
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


def _with_format(
    fmt: tuple[bool, bool, bool, str | None], name: str
) -> tuple[bool, bool, bool, str | None]:
    strong, em, code, href = fmt
    kind = _FORMATS.get(name)
    return (
        strong or kind == "strong",
        em or kind == "em",
        code or kind == "code",
        href,
    )


def _image(tag: Tag, fmt: tuple[bool, bool, bool, str | None]) -> object:
    """An image as displayed: its source, and its alt text as it is read."""

    alt = " ".join(str(tag.get("alt") or "").split())
    return (("IMG", str(tag.get("src") or ""), alt), fmt)


def _inline(node: Tag, words: _Words, fmt: tuple[bool, bool, bool, str | None]) -> None:
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
                link = (fmt[0], fmt[1], fmt[2], str(child.get("href")))
                _inline(child, words, link)
            else:
                _inline(child, words, _with_format(fmt, child.name))


def _has_block(node: Tag) -> bool:
    return any(
        isinstance(child, Tag) and child.name in _BLOCKS for child in node.descendants
    )


def _list(node: Tag, fmt: tuple[bool, bool, bool, str | None]) -> tuple[object, ...]:
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


def _display_blocks(
    node: Tag, fmt: tuple[bool, bool, bool, str | None] = _PLAIN
) -> tuple[object, ...]:
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
            out.append(("quote", _display_blocks(child, fmt)))
        elif name == "pre":
            flush()
            out.append(("pre", child.get_text().strip("\n")))
        elif name == "hr":
            flush()
            out.append(("hr",))
        elif name == "table":
            flush()
            rows = []
            for row in child.find_all("tr"):
                cells = []
                for cell in row.find_all(["td", "th"], recursive=False):
                    inner = _Words()
                    _inline(cell, inner, fmt)
                    cells.append((cell.name == "th", inner.finish()))
                rows.append(tuple(cells))
            out.append(("table", tuple(rows)))
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


def assert_survives(html: str) -> str:
    """Assert the round-trip property for one body, and return its Markdown."""

    markdown = read(html)
    rendered = render(markdown)

    assert displayed(rendered) == displayed(html), (
        f"the Markdown does not display what the HTML did\n"
        f"  html:     {html!r}\n  markdown: {markdown!r}\n  rendered: {rendered!r}"
    )
    assert read(rendered) == markdown, (
        f"the Markdown is not a fixed point\n  markdown: {markdown!r}\n"
        f"  again:    {read(rendered)!r}"
    )
    return markdown


# ---------------------------------------------------------------------------
# Ordinary prose is left alone
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        pytest.param(
            "<p>Voir fichier_de_test_v2.xlsx et mon_fichier_final.docx</p>",
            "Voir fichier_de_test_v2.xlsx et mon_fichier_final.docx",
            id="file-names",
        ),
        pytest.param(
            r"<p>Chemin C:\Temp\logs et C:\Users\Admin\Documents</p>",
            r"Chemin C:\Temp\logs et C:\Users\Admin\Documents",
            id="windows-paths",
        ),
        pytest.param(
            "<p>Le ticket # 3 et le #4521 sont liés, C# aussi</p>",
            "Le ticket # 3 et le #4521 sont liés, C# aussi",
            id="mid-sentence-hash",
        ),
        pytest.param(
            "<p>Porte-monnaie - un tiret - et -- deux</p>",
            "Porte-monnaie - un tiret - et -- deux",
            id="dashes-and-hyphens",
        ),
        pytest.param(
            "<p>Service R&amp;D, bâtiment A &amp; B</p>",
            "Service R&D, bâtiment A & B",
            id="ampersands",
        ),
        pytest.param(
            "<p>5 * 3 = 15 et prix 5*3 et note * importante</p>",
            "5 * 3 = 15 et prix 5*3 et note * importante",
            id="lone-asterisks",
        ),
        pytest.param(
            "<p>[INFO] tâche [1] terminée (voir note)</p>",
            "[INFO] tâche [1] terminée (voir note)",
            id="brackets",
        ),
        pytest.param(
            "<p>si a &lt; b et x &lt;= y alors 2 &lt; 3</p>",
            "si a < b et x <= y alors 2 < 3",
            id="less-than",
        ),
        pytest.param(
            "<p>2 + 2 = 4, +33 6 12 34 56 78, 1) un, 3.14</p>",
            "2 + 2 = 4, +33 6 12 34 56 78, 1) un, 3.14",
            id="numbers",
        ),
        pytest.param(
            "<p>Cordialement,<br>Jean Dupont<br>--<br>Service IT</p>",
            "Cordialement,  \nJean Dupont  \n--  \nService IT",
            id="signature-dashes-on-a-third-line",
        ),
        pytest.param(
            "<p>Voir https://example.org/doc?a=1&amp;b=2 ou support@example.org</p>",
            "Voir https://example.org/doc?a=1&b=2 ou support@example.org",
            id="bare-url-and-address",
        ),
        pytest.param(
            "<p>Pourquoi ? Parce que ! 100 % a/b a=b ~5 minutes</p>",
            "Pourquoi ? Parce que ! 100 % a/b a=b ~5 minutes",
            id="punctuation",
        ),
        pytest.param(
            "<p>l`imprimante et la variable user_id et _temp</p>",
            "l`imprimante et la variable user_id et _temp",
            id="unpaired-backtick-and-underscore",
        ),
        pytest.param(
            "<p>ps aux | grep java</p>",
            "ps aux | grep java",
            id="pipe-outside-a-table",
        ),
    ],
)
def test_ordinary_prose_carries_no_escape(html: str, expected: str) -> None:
    """Minimal means none of these grows a backslash or a reference.

    Each of these characters *can* be Markdown syntax, and none of them is
    here, so python-markdown already renders every one of them literally.
    Escaping them anyway would be harmless to the rendering and a nuisance to
    everyone who reads the Markdown -- and a change for every existing body.
    """

    assert read(html) == expected
    assert_survives(html)


# ---------------------------------------------------------------------------
# The measured misreadings, one by one
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        # The reviewers' measurements through GLPI's reader into
        # python-markdown, before this change.
        pytest.param(
            r"<p>Accès au partage \\serveur\compta\2026 refusé</p>",
            r"Accès au partage \\\serveur\compta\2026 refusé",
            id="unc-path-lost-a-backslash",
        ),
        pytest.param(
            r"<p>Dossier C:\_temp\logs</p>",
            r"Dossier C:\\_temp\logs",
            id="backslash-underscore-lost-the-backslash",
        ),
        pytest.param(
            "<p>Fichier mon_fichier_final.docx et __init__</p>",
            r"Fichier mon_fichier_final.docx et \_\_init\_\_",
            id="dunder-became-bold",
        ),
        pytest.param(
            "<p>Nom : ______ Prénom : ______</p>",
            r"Nom : \_\_\_\_\_\_ Prénom : \_\_\_\_\_\_",
            id="form-blanks-became-emphasis",
        ),
        pytest.param(
            "<p>Merci<br>-----------<br>Jean Dupont</p>",
            "Merci  \n\\-----------  \nJean Dupont",
            id="dash-line-made-a-heading",
        ),
        pytest.param(
            "<p>* point un<br>* point deux</p>",
            "\\* point un  \n* point deux",
            id="star-lines-made-a-list",
        ),
        pytest.param(
            "<p>Le 30/09, Jean a écrit :<br>&gt; merci<br>&gt; cordialement</p>",
            "Le 30/09, Jean a écrit :  \n\\> merci  \n\\> cordialement",
            id="quoted-reply-made-a-blockquote",
        ),
        pytest.param(
            "<p>voir la note [1]</p><p>[1]: https://example.org/note</p>",
            "voir la note [1]\n\n\\[1]: https://example.org/note",
            id="footnote-line-was-consumed",
        ),
        pytest.param(
            "<p># pas un titre</p>", r"\# pas un titre", id="hash-made-a-heading"
        ),
        pytest.param(
            "<p>#4521 est un doublon</p>",
            r"\#4521 est un doublon",
            id="ticket-number-made-a-heading",
        ),
        pytest.param(
            "<p>2026. Une annee</p>", r"2026\. Une annee", id="year-made-a-list"
        ),
        pytest.param(
            "<table><tr><th>Commande</th></tr>"
            "<tr><td>ps aux | grep java</td></tr></table>",
            "| Commande |\n| --- |\n| ps aux \\| grep java |",
            id="pipe-in-a-cell-dropped-the-rest",
        ),
    ],
)
def test_the_measured_misreadings_read_back_as_their_text(
    html: str, expected: str
) -> None:
    """Every shape the reviewers measured, now spelled so it survives."""

    assert read(html) == expected
    assert_survives(html)


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        # Backslashes: escaped exactly when the next character is one
        # python-markdown would take as escaped.
        pytest.param(
            r"<p>D:\logs\.cache et \\srv\share\[archive] et HKLM\SOFTWARE\#1</p>",
            r"D:\logs\\.cache et \\\srv\share\\[archive] et HKLM\SOFTWARE\\#1",
            id="backslash-before-punctuation",
        ),
        pytest.param(
            r"<p>fin de ligne \<br>suite</p>",
            "fin de ligne \\  \nsuite",
            id="backslash-before-a-break",
        ),
        pytest.param(
            r"<h2>Chemin C:\</h2>",
            r"## Chemin C:\\",
            id="backslash-ending-a-heading",
        ),
        # Emphasis delimiters.
        pytest.param("<p>_______</p>", r"\_" * 7, id="seven-underscores"),
        pytest.param(
            "<p>a*b*c et 5*3 <strong>gras</strong></p>",
            r"a\*b\*c et 5\*3 **gras**",
            id="asterisks-beside-real-emphasis",
        ),
        pytest.param(
            "<p><strong>x</strong>* suite</p>",
            r"**x**\* suite",
            id="asterisk-touching-a-delimiter",
        ),
        # Block syntax at the start of a line.
        pytest.param("<p>+ un<br>+ deux</p>", "\\+ un  \n+ deux", id="plus-list"),
        pytest.param("<p>- pas une liste</p>", r"\- pas une liste", id="dash-list"),
        pytest.param(
            "<p>Bonjour<br>#4521 doublon</p>",
            "Bonjour  \n\\#4521 doublon",
            id="hash-after-a-break",
        ),
        pytest.param("<p>Titre<br>=====</p>", "Titre  \n&#61;====", id="setext-equals"),
        pytest.param(
            "<p>---</p><p>signature</p>",
            "\\---\n\nsignature",
            id="rule-of-dashes",
        ),
        pytest.param("<p>***</p>", r"\*\*\*", id="rule-of-asterisks"),
        pytest.param("<ul><li>--</li></ul>", r"- \--", id="bullet-completes-a-rule"),
        pytest.param("<ul><li>___</li></ul>", r"- \_\_\_", id="rule-in-a-list-item"),
        pytest.param(
            "<ul><li><ul><li>-</li></ul></li></ul>",
            r"- - \-",
            id="two-bullets-complete-a-rule",
        ),
        pytest.param(
            "<ol><li><ul><li>--</li></ul></li></ol>",
            r"1. - \--",
            id="rule-inside-a-numbered-item",
        ),
        pytest.param(
            "<ul><li><p>--</p><p>suite</p></li></ul>",
            "- \\--\n\n    suite",
            id="rule-in-an-item-paragraph",
        ),
        pytest.param("<h1>C#</h1>", r"# C\#", id="heading-trailing-hash"),
        pytest.param("<h2>Titre ##</h2>", r"## Titre \#\#", id="heading-closing-run"),
        pytest.param(
            "<p>```<br>code<br>```</p>",
            "\\`\\`\\`  \ncode  \n\\`\\`\\`",
            id="backtick-fence",
        ),
        pytest.param(
            "<p>~~~<br>code<br>~~~</p>",
            "&#126;~~  \ncode  \n&#126;~~",
            id="tilde-fence",
        ),
        pytest.param(
            "<p>a | b<br>--- | ---</p>",
            "a | b  \n--- \\| ---",
            id="table-separator",
        ),
        # Link and image syntax typed as text.
        pytest.param(
            "<p>[x](https://example.org/y) et ![x](https://example.org/y.png)</p>",
            r"\[x](https://example.org/y) et !\[x](https://example.org/y.png)",
            id="link-and-image-syntax",
        ),
        pytest.param(
            '<p>Attention!<a href="https://example.org/u">voir</a></p>',
            r"Attention\![voir](https://example.org/u)",
            id="bang-before-a-link",
        ),
        pytest.param(
            '<p><a href="https://example.org/u">rapport [final].pdf</a></p>',
            "[rapport [final].pdf](https://example.org/u)",
            id="balanced-brackets-in-link-text",
        ),
        pytest.param(
            '<p><a href="https://example.org/u">a]b</a></p>',
            r"[a\]b](https://example.org/u)",
            id="unbalanced-bracket-in-link-text",
        ),
        pytest.param(
            '<p><a href="https://example.org/u">voir [x](y)</a></p>',
            r"[voir \[x\](y)](https://example.org/u)",
            id="link-syntax-in-link-text",
        ),
        pytest.param(
            '<p><img src="https://example.org/c.png" alt="capture [1].png"></p>',
            "![capture [1].png](https://example.org/c.png)",
            id="balanced-brackets-in-alt-text",
        ),
        pytest.param(
            '<p><img src="https://example.org/c.png" alt="a]b"></p>',
            r"![a\]b](https://example.org/c.png)",
            id="unbalanced-bracket-in-alt-text",
        ),
        # Raw HTML and references typed as text.
        pytest.param(
            "<p>appuyer sur &lt;Entrée&gt; puis valider</p>",
            "appuyer sur &lt;Entrée> puis valider",
            id="angle-bracketed-word",
        ),
        pytest.param(
            "<p>if x&lt;y then z&gt;0</p>",
            "if x&lt;y then z>0",
            id="comparison-that-looks-like-a-tag",
        ),
        pytest.param(
            "<p>&lt;https://example.org/x&gt; et &lt;support@example.org&gt;</p>",
            "&lt;https://example.org/x> et &lt;support@example.org>",
            id="autolink-syntax",
        ),
        pytest.param(
            '<p>&lt;3<img src="https://example.org/i.png" alt="a b">@c&gt;</p>',
            "&lt;3![a b](https://example.org/i.png)@c>",
            id="address-running-through-an-image",
        ),
        pytest.param(
            '<p><a href="https://example.org/u">&lt;&lt;a@c&gt;</a></p>',
            "[&lt;&lt;a@c>](https://example.org/u)",
            id="address-in-link-text",
        ),
        pytest.param(
            '<p>&lt;3<a href="https://example.org">https://example.org</a>@c&gt;</p>',
            "&lt;3<https://example.org>@c>",
            id="address-running-through-an-autolink",
        ),
        pytest.param(
            '<p>&lt;a <a href="https://example.org/T_(x)">wiki</a>b@c&gt;</p>',
            "&lt;a [wiki](https://example.org/T_(x))b@c>",
            id="link-target-holding-parentheses",
        ),
        pytest.param(
            "<p>&lt;!-- note --&gt;</p>", "&lt;!-- note -->", id="comment-syntax"
        ),
        pytest.param(
            "<p>&amp;amp; &amp;lt; &amp;#65; &amp;#4521 &amp;copy; &amp;copy</p>",
            "&amp;amp; &amp;lt; &amp;#65; &amp;#4521 &amp;copy; &copy",
            id="character-references",
        ),
        # Code spans typed as text.
        pytest.param(
            "<p>a`b`c et <code>x</code> puis `</p>",
            r"a\`b\`c et `x` puis `",
            id="backtick-pair",
        ),
        pytest.param(
            "<table><tr><th>a</th><th>b</th></tr>"
            "<tr><td>x`y</td><td>`z</td></tr></table>",
            "| a | b |\n| --- | --- |\n| x\\`y | \\`z |",
            id="backticks-pair-across-cells",
        ),
    ],
)
def test_literal_text_is_escaped_where_python_markdown_would_read_it(
    html: str, expected: str
) -> None:
    """One case per construct, each with the escape it needs and no other."""

    assert read(html) == expected
    assert_survives(html)


# ---------------------------------------------------------------------------
# Structure that used to be lost on the way through
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        pytest.param(
            "<ul><li>Réseau<ul><li>switch 3</li><li>borne wifi</li></ul></li>"
            "<li>Imprimante</li></ul>",
            "- Réseau\n    - switch 3\n    - borne wifi\n- Imprimante",
            id="ul-in-ul",
        ),
        pytest.param(
            "<ol><li>Arreter</li><li>Sauvegarder<ol><li>la base</li>"
            "<li>les fichiers</li></ol></li><li>Redemarrer</li></ol>",
            "1. Arreter\n2. Sauvegarder\n    1. la base\n    2. les fichiers\n"
            "3. Redemarrer",
            id="ol-in-ol-keeps-its-numbering",
        ),
        pytest.param(
            "<ol><li>un<ul><li>a</li></ul></li><li>deux</li></ol>",
            "1. un\n    - a\n2. deux",
            id="ul-in-ol",
        ),
        pytest.param(
            "<ul><li>a<ul><li>b<ul><li>c<ul><li>d</li></ul></li></ul></li></ul>"
            "</li></ul>",
            "- a\n    - b\n        - c\n            - d",
            id="four-levels",
        ),
        pytest.param(
            '<p>intro</p><ol start="3"><li>trois</li><li>quatre</li></ol>',
            "intro\n\n3. trois\n4. quatre",
            id="ordered-list-starting-at-three",
        ),
        pytest.param(
            "<ul><li><p>point un</p><p>suite du point</p></li><li>point deux</li></ul>",
            "- point un\n\n    suite du point\n\n- point deux",
            id="item-with-two-paragraphs",
        ),
    ],
)
def test_nested_lists_nest_and_keep_their_numbers(html: str, expected: str) -> None:
    """python-markdown nests only at four spaces; the reader indents by four.

    ``markdownify`` indented a continuation by its bullet's width -- two for
    ``- ``, three for ``1. `` -- so the first write flattened a nested list
    and renumbered a nested ordered one, one level per pass.
    """

    assert read(html) == expected
    assert_survives(html)


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        pytest.param(
            "<ul><li>Réseau<ul><li>switch 3</li></ul>à vérifier</li></ul>",
            "- Réseau\n\n    - switch 3\n\n    à vérifier",
            id="text-after-a-nested-list",
        ),
        pytest.param(
            "<ul><li>Réseau<ul><li>switch 3</li></ul><blockquote>cité</blockquote>"
            "</li></ul>",
            "- Réseau\n\n    - switch 3\n\n    > cité",
            id="quote-after-a-nested-list",
        ),
        pytest.param(
            "<ul><li>Réponse :<blockquote>cité</blockquote></li></ul>",
            "- Réponse :\n\n    > cité",
            id="quote-after-an-items-text",
        ),
        pytest.param(
            "<ul><li><blockquote>cité<br>suite</blockquote></li></ul>",
            "- > cité  \n> suite",
            id="quote-opening-an-item",
        ),
        pytest.param(
            "<ul><li><ul><li>un</li><li>deux</li></ul></li></ul>",
            "- - un\n    - deux",
            id="item-opening-with-a-list",
        ),
        pytest.param(
            "<ul><li><ul><li>un<ul><li>a</li></ul></li></ul></li></ul>",
            "- - un\n\n        - a",
            id="list-under-an-item-sharing-its-line",
        ),
        pytest.param(
            "<ul><li><ul><li><ul><li>un</li><li>deux</li></ul></li></ul></li>"
            "<li>trois</li></ul>",
            "- - - un\n\n        - deux\n\n- trois",
            id="three-bullets-on-one-line",
        ),
    ],
)
def test_blocks_inside_a_list_item_stay_in_it(html: str, expected: str) -> None:
    """python-markdown only nests a block where its first pass lets it.

    That pass never detabs an item's first block, and reads ``>`` only three
    spaces in at most, so what follows a list item's text or its nested list
    needs a blank line before it -- ``markdownify`` gave none after a nested
    list, and the item's text ran into the list's last item -- and a quote
    opening an item needs its later lines unindented. On a line already
    carrying two bullets, anything eight spaces in is taken as that line's
    continuation, so what follows it starts a block of its own.
    """

    assert read(html) == expected
    assert_survives(html)


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        pytest.param(
            '<p><a name="_MailEndCompose">Bonjour</a> Jean</p>',
            "Bonjour Jean",
            id="anchor-without-a-target",
        ),
        pytest.param(
            '<p><a href="https://example.org/u"></a>texte</p>', "texte", id="empty-link"
        ),
        pytest.param("<p><strong></strong>texte</p>", "texte", id="empty-emphasis"),
        pytest.param(
            '<p><a href="https://example.org/u">un<br>deux</a></p>',
            "[un  \ndeux](https://example.org/u)",
            id="break-in-link-text",
        ),
        pytest.param("<p>a<center>b</center>c</p>", "a\n\nb\n\nc", id="center-block"),
        pytest.param(
            "<table><tr><th><h3>titre</h3></th></tr><tr><td>x</td></tr></table>",
            "| titre |\n| --- |\n| x |",
            id="heading-in-a-cell",
        ),
        pytest.param(
            "<h2><blockquote>cité</blockquote></h2>", "## cité", id="quote-in-a-heading"
        ),
        pytest.param(
            "<ul><li><script>x()</script><pre>code</pre></li></ul>",
            "- code",
            id="code-opening-an-item-after-a-script",
        ),
        pytest.param(
            "<ul><li><!-- note --><pre>code</pre></li></ul>",
            "- code",
            id="code-opening-an-item-after-a-comment",
        ),
        pytest.param(
            "<ul><li><ul></ul><pre>code</pre></li></ul>",
            "- code",
            id="code-opening-an-item-after-an-empty-list",
        ),
        pytest.param(
            '<ul><li><img src="https://example.org/i.png" alt="i"><pre>code</pre>'
            "</li></ul>",
            "- ![i](https://example.org/i.png)\n\n        code",
            id="code-after-an-image",
        ),
    ],
)
def test_shapes_with_a_rule_of_their_own(html: str, expected: str) -> None:
    """The converter's special cases, each on the shape that reaches it.

    What displays nothing -- a comment, a script, an empty list -- does not
    count as content before a code block, so the code still opens its item.
    """

    assert read(html) == expected


def test_an_ordered_list_keeps_its_start_when_rendered() -> None:
    """``sane_lists`` is what keeps ``3.`` from restarting the count at 1."""

    assert '<ol start="3">' in render("intro\n\n3. trois\n4. quatre")


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        pytest.param(
            "<ul><li>item<pre>#4521 code</pre></li></ul>",
            "- item\n\n        #4521 code",
            id="in-a-list-item",
        ),
        pytest.param(
            "<blockquote><pre>#4521 C:\\Temp\n  indenté</pre></blockquote>",
            ">     #4521 C:\\Temp\n>       indenté",
            id="in-a-blockquote",
        ),
        pytest.param(
            "<pre>ligne\n```\nfin</pre>",
            "````\nligne\n```\nfin\n````",
            id="holding-a-fence-line",
        ),
    ],
)
def test_a_preformatted_block_stays_one(html: str, expected: str) -> None:
    """A fence opens only at the start of a line, so nested code is indented.

    Inside a list item or a block quote, python-markdown never sees
    ``` ``` ``` at the start of a line and reads the fence as text -- the
    code's own ``#4521`` then became a heading. An indented code block is the
    spelling it does read there. At the top level the fence is made longer
    than any fence line the code holds.
    """

    assert read(html) == expected
    assert_survives(html)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "python-markdown runs html.parser over its whole source to find raw "
        "HTML, before an indented code block is recognised, and re-emits a "
        "numeric reference written without its semicolon with one: the code "
        "then shows '&#4521;'. A fence is stashed before that pass, which is "
        "why a top-level <pre> is unaffected; inside a list item or a quote no "
        "fence can open. Measured on 3.10.3."
    ),
)
def test_a_numeric_reference_in_nested_code_gains_a_semicolon() -> None:
    assert_survives("<blockquote><pre>echo &amp;#4521</pre></blockquote>")


def test_a_preformatted_block_opening_a_list_item_keeps_its_text() -> None:
    """The one place python-markdown can start no code block at all.

    A list item's first line is its paragraph, so the code there degrades to
    its lines, each escaped as the literal text it is -- the words survive,
    the preformatting does not.
    """

    html = "<ul><li><pre>#4521 code\n  suite</pre></li></ul>"

    markdown = read(html)

    assert markdown == "- \\#4521 code  \n    suite"
    assert "#4521 code" in render(markdown)
    assert read(render(markdown)) == markdown


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        pytest.param(
            "<ul><li>item<ul><li>sous-item</li></ul><pre>#4521 code</pre></li></ul>",
            "- item\n\n    - sous-item\n\n    \\#4521 code",
            id="in-a-list-item",
        ),
        pytest.param(
            "<blockquote><ul><li>item</li></ul><pre>#4521 code</pre></blockquote>",
            "> - item\n>\n> \\#4521 code",
            id="in-a-quote",
        ),
    ],
)
def test_code_right_after_a_nested_list_keeps_its_text(
    html: str, expected: str
) -> None:
    """The other place python-markdown can start no code block.

    An indented code block right after a list in the same item or quote is
    indented exactly as the list's last item's own content, and
    python-markdown reads it as a paragraph of that item. The lines are
    kept as literal text in the right place instead.
    """

    markdown = read(html)

    assert markdown == expected
    assert "#4521 code" in render(markdown)
    assert read(render(markdown)) == markdown


#: What the format loses, whatever the escaping does: each body with why.
#:
#: None of these is literal text misread. Each is structure python-markdown
#: has no spelling for, or spells as something else.
LOSSES = [
    pytest.param(
        "<ul><li>a</li></ul><ul><li>b</li></ul>",
        "python-markdown continues a list across a blank line: two lists are "
        "read back as one list of loose items.",
        id="two-adjacent-lists",
    ),
    pytest.param(
        "<blockquote>a</blockquote><blockquote>b</blockquote>",
        "python-markdown continues a quote across a blank line: two quotes are "
        "read back as one quote of two paragraphs.",
        id="two-adjacent-quotes",
    ),
    pytest.param(
        "<p>a<br><br>b</p>",
        "Markdown has no blank line inside a paragraph: two breaks in a row "
        "are a paragraph break, and read back as one.",
        id="two-breaks-in-a-row",
    ),
    pytest.param(
        "<p><code>a</code><code>b</code></p>",
        "'`a``b`' is one code span holding 'a``b' to python-markdown.",
        id="two-adjacent-code-spans",
    ),
    pytest.param(
        "<p><em>a <strong>b</strong> c</em></p>",
        "python-markdown pairs '*a **b** c*' as three emphasis runs, and b "
        "loses its bold.",
        id="strong-inside-emphasis",
    ),
    pytest.param(
        "<table><tr><td>a</td><td>b</td></tr></table>",
        "A Markdown table starts with its header row, so one without gains an "
        "empty header.",
        id="table-without-a-header",
    ),
    pytest.param(
        "<table><tr><th>a</th><th>b</th></tr></table>",
        "python-markdown renders a header-only table with one empty body row.",
        id="table-without-a-body",
    ),
    pytest.param(
        "<table><tr><th>a</th></tr><tr><td><ul><li>x</li></ul></td></tr></table>",
        "A table cell holds one line of inline Markdown: its list is written "
        "as its text.",
        id="list-in-a-cell",
    ),
    pytest.param(
        "<table><tr><th>a</th></tr><tr><td><pre>x\ny</pre></td></tr></table>",
        "A table cell holds one line of inline Markdown: its code block is "
        "written as inline code.",
        id="code-block-in-a-cell",
    ),
    pytest.param(
        "<ul><li><pre>a</pre></li></ul>",
        "An item's first block is its paragraph: the code is kept as text "
        "(test_a_preformatted_block_opening_a_list_item_keeps_its_text).",
        id="code-opening-a-list-item",
    ),
    pytest.param(
        "<ul><li>a<ul><li>b</li></ul><pre>c</pre></li></ul>",
        "The code would be indented as the nested item's own content: it is "
        "kept as text (test_code_right_after_a_nested_list_keeps_its_text).",
        id="code-after-a-nested-list",
    ),
]


@pytest.mark.parametrize(("html", "reason"), LOSSES)
def test_what_markdown_cannot_carry(html: str, reason: str) -> None:
    """The inventory of losses, each asserted to still be one.

    ``xfail(strict=True)`` is the point: a loss that stops being one fails
    here, so the inventory stays true. Struck and underlined text lose their
    line too, which this comparison does not see:
    ``test_struck_text_keeps_its_words_and_loses_its_line``.
    """

    with pytest.raises(AssertionError):
        assert_survives(html)
    pytest.xfail(reason)


@pytest.mark.parametrize(("html", "reason"), LOSSES)
def test_what_is_lost_is_lost_once(html: str, reason: str) -> None:
    """Whatever a loss costs, it costs on the first cycle and never again."""

    again = read(render(read(html)))

    assert read(render(again)) == again, reason


@pytest.mark.parametrize(
    "html",
    [
        pytest.param(
            "<style>p.MsoNormal{margin:0cm;font-size:11pt}</style><p>Bonjour</p>",
            id="style",
        ),
        pytest.param("<p>Bonjour</p><script>track()</script>", id="script"),
        pytest.param(
            "<html><head><title>RE: Imprimante</title>"
            "<style><!-- p.MsoNormal {margin:0cm;} --></style></head>"
            "<body><p>Bonjour</p><script>track()</script></body></html>",
            id="outlook-shaped",
        ),
    ],
)
def test_style_script_and_title_bodies_are_not_text(html: str) -> None:
    """A browser displays none of these, so neither does the Markdown.

    ``strip=["script", "style"]`` used to be passed to ``markdownify``, and
    ``strip`` skips an element's own converter -- ``convert_script`` and
    ``convert_style`` return ``""`` -- so the bodies leaked into the text as
    prose. ``<title>`` has no converter at all and leaked the same way.
    """

    assert read(html) == "Bonjour"


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        pytest.param(
            '<font color="red">URGENT</font> serveur HS', "URGENT serveur HS", id="font"
        ),
        pytest.param("<center>Titre</center> suite", "Titre\n\nsuite", id="center"),
        pytest.param("<strike>ancien</strike> nouveau", "ancien nouveau", id="strike"),
        pytest.param("<big>gros</big> texte", "gros texte", id="big"),
        pytest.param("<tt>code</tt> texte", "code texte", id="tt"),
        pytest.param("<nobr>sans coupure</nobr>", "sans coupure", id="nobr"),
    ],
)
def test_a_body_marked_up_only_with_obsolete_elements_is_html(
    html: str, expected: str
) -> None:
    """Old editors still write these; without them the tags were kept as text."""

    assert read(html) == expected


def test_every_obsolete_element_name_makes_a_body_html() -> None:
    """The HTML standard's list of obsolete elements, all of them recognised."""

    obsolete = (
        "acronym applet basefont bgsound big blink center dir font frame "
        "frameset isindex keygen listing marquee menuitem multicol nextid nobr "
        "noembed noframes plaintext rb rtc spacer strike tt xmp"
    ).split()

    assert set(obsolete) <= conversion._HTML_ELEMENTS


@pytest.mark.parametrize(
    "html",
    [
        pytest.param("<p><s>ancien</s> nouveau</p>", id="s"),
        pytest.param("<p><del>ancien</del> nouveau</p>", id="del"),
        pytest.param("<p><strike>ancien</strike> nouveau</p>", id="strike"),
    ],
)
def test_struck_text_keeps_its_words_and_loses_its_line(html: str) -> None:
    """python-markdown has no strikethrough, so ``~~x~~`` would show literally.

    Keeping the words and losing the line is the honest loss: the text is
    all there, and what is missing is recorded in the round-trip inventory.
    """

    assert read(html) == "ancien nouveau"


@pytest.mark.parametrize(
    "html", ["<P>Bonjour</P>", "<BR>Bonjour", "<DIV><B>Bonjour</B></DIV>"]
)
def test_upper_case_tags_are_html(html: str) -> None:
    """Element names are case-insensitive; the probe has to be too."""

    assert "<" not in read(html)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("  texte  ", "texte", id="plain-text"),
        pytest.param(" <b>x</b> ", "**x**", id="html"),
        pytest.param("<br>x<br>", "x", id="html-with-edge-breaks"),
    ],
)
def test_the_result_is_stripped_on_both_paths(value: str, expected: str) -> None:
    """Edge whitespace is never content, and a digest must not depend on it."""

    assert read(value) == expected


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        pytest.param(
            '<h2>Titre <img src="https://example.org/i.png" alt="logo"></h2>',
            "## Titre ![logo](https://example.org/i.png)",
            id="heading",
        ),
        pytest.param(
            "<table><tr><th>a</th></tr><tr><td>"
            '<img src="https://example.org/i.png" alt="x"></td></tr></table>',
            "| a |\n| --- |\n| ![x](https://example.org/i.png) |",
            id="table-cell",
        ),
    ],
)
def test_an_image_in_a_heading_or_a_cell_stays_an_image(
    html: str, expected: str
) -> None:
    """``markdownify`` reduced these to their alt text; python-markdown needs not."""

    assert read(html) == expected
    assert_survives(html)


def test_a_newline_in_text_is_a_space() -> None:
    """HTML displays a source newline as a space; ``nl2br`` would break the line.

    Outlook wraps its HTML source mid-sentence, so every e-mail created
    ticket used to gain line breaks where the reader saw none.
    """

    html = "<p>Bonjour,\nle serveur\nest redémarré.</p>"

    assert read(html) == "Bonjour, le serveur est redémarré."
    assert_survives(html)


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        pytest.param("<p>a<br> b<br>  c</p>", "a  \nb  \nc", id="space-after-break"),
        pytest.param("<p>a <br>b</p>", "a  \nb", id="space-before-break"),
        pytest.param("<p><strong>a<br></strong>b</p>", "**a**  \nb", id="edge-break"),
    ],
)
def test_a_line_break_has_one_spelling(html: str, expected: str) -> None:
    """Whitespace around ``<br>`` is not displayed, so it is not kept either.

    Without this the first read of ``a<br> b`` was ``a  \\n b`` and the
    second ``a  \\nb``: the same body, read twice, disagreeing.
    """

    assert read(html) == expected
    assert_survives(html)


# ---------------------------------------------------------------------------
# The degraded path spells text the same way
# ---------------------------------------------------------------------------


def test_a_body_too_deep_to_convert_is_still_literal_safe() -> None:
    """The stripped text is Markdown too, and it is escaped like the rest."""

    html = "<div>" * 600 + r"<p>__init__ \\serveur</p><p># pas un titre</p>"

    markdown = read(html)

    assert markdown == "\\_\\_init\\_\\_ \\\\\\serveur\n\n\\# pas un titre"
    assert "__init__ \\\\serveur" in render(markdown)


@pytest.mark.parametrize("seed", range(4))
def test_stripped_text_renders_as_itself(seed: int) -> None:
    """Any text, line by line, renders as exactly that text.

    The degraded path's contract, over generated text dense with the
    characters python-markdown treats as syntax.
    """

    rng = random.Random(seed)
    for _ in range(60):
        lines = [_text(rng, rng.randint(1, 6)) for _ in range(rng.randint(1, 4))]
        text = "\n".join(line for line in lines if line)
        if not text:
            continue

        soup = BeautifulSoup(render(conversion._literal_markdown(text)), "html.parser")
        for line_break in soup.find_all("br"):
            line_break.replace_with("\u2029")
        shown = soup.get_text().replace("\n", " ").replace("\u2029", "\n")

        assert [" ".join(line.split()) for line in shown.split("\n")] == [
            " ".join(line.split()) for line in text.split("\n")
        ], text


# ---------------------------------------------------------------------------
# The property, over realistic bodies and over a fuzzer
# ---------------------------------------------------------------------------

#: Ticket bodies shaped the way GLPI's editor and mail collector store them.
REALISTIC = [
    "<p>Bonjour,</p><p>Le PC du poste 12 ne démarre plus depuis ce matin.</p>",
    "<p>Bonjour,<br>Le PC ne démarre plus.<br>Cordialement,<br>Jean</p>",
    "<p>Merci de <strong>redémarrer</strong> le serveur <em>avant</em> 18h.</p>",
    "<p>Étapes :</p><ul><li>ouvrir la session</li><li>lancer Outlook</li></ul>",
    "<table><thead><tr><th>Poste</th><th>IP</th></tr></thead>"
    "<tbody><tr><td>PC12</td><td>10.0.0.12</td></tr></tbody></table>",
    "<h2>Contexte</h2><p>Migration du serveur.</p>",
    '<p>Voir <a href="https://example.org/doc">https://example.org/doc</a></p>',
    '<p>Voir <a title="doc" href="https://example.org/doc">la doc</a></p>',
    '<p><a href="https://example.org/wiki/Test_(informatique)">wiki</a></p>',
    "<p>prix 5*3 et note * importante</p>",
    "<p>appuyer sur &lt;Entrée&gt; puis valider</p>",
    "<p>Service R&amp;D, bâtiment A &amp; B</p>",
    "<p>Montant&nbsp;: 12&nbsp;000&nbsp;€</p>",
    '<p><span style="color: #e03e2d;">URGENT</span> <u>à traiter</u></p>',
    '<p>Cordialement</p><p><img src="https://example.org/logo.png" alt="Logo"></p>',
    "<p>Bonjour</p><blockquote><p>Message d'origine</p></blockquote>",
    '<pre>Traceback (most recent call last):\n  File "x.py", line 1\nError</pre>',
    "<p>Lancer <code>ipconfig /all</code> puis envoyer.</p>",
    "<p>Fichier mon_fichier_final.docx et __init__</p>",
    "<p># pas un titre</p><p>- pas une liste</p>",
    '<p>Contact <a href="mailto:support@example.org">support@example.org</a></p>',
    "<div>Bonjour,</div><div><br></div><div>Le serveur est down.</div>",
    "<p>* point un<br>* point deux</p>",
    "<p>&lt;https://example.org/x&gt;</p>",
    "<p>[INFO] tâche [1] terminée</p>",
    "<p>[1]: https://example.org/note</p>",
    "<p>m<sup>2</sup></p>",
    r"<p>Chemin C:\Users\jdupont\Desktop</p>",
    "<p>Merci 👍</p>",
    "<p>Titre<br>=====</p>",
    "<p>---</p><p>signature</p>",
    "<p>1) un<br>2) deux</p>",
    "<p>&lt;support@example.org&gt;</p>",
    "<p>&lt;!-- note --&gt;</p>",
    "<ul><li><p>point un</p><p>suite du point</p></li><li>point deux</li></ul>",
    "<blockquote><ul><li>a</li><li>b</li></ul></blockquote>",
    "<p>Nom : ______ Prénom : ______</p>",
    "<p>~~pas barré~~</p>",
    "<p>a | b | c</p>",
    "<p>&gt; pas une citation</p>",
    "<p>+ un<br>+ deux</p>",
    "<p>Cordialement,<br>Jean Dupont<br>--<br>Service IT</p>",
    "<p>Merci<br>-----------<br>Jean Dupont</p>",
    "<p>calcul 5 * 3 * 2 = 30</p>",
    r"<p>voir \\srv\partage\__archive__\2026</p>",
    "<p>Le 30/09, Jean a écrit :<br>&gt; merci<br>&gt; cordialement</p>",
    r"<p>Accès au partage \\serveur\compta\2026 refusé</p>",
    r"<p>Dossier C:\_temp\logs</p>",
    "<p>voir la note [1]</p><p>[1]: https://example.org/note</p>",
    "<ul><li>Réseau<ul><li>switch 3</li><li>borne wifi</li></ul></li></ul>",
    "<p><b>Important</b> : voir <i>ci-dessous</i></p>",
    '<p><font color="red">rouge</font> <span style="font-size:14px">texte</span></p>',
    "<p>module __init__ et _x_</p>",
    "<p>1) un<br>2) deux</p><pre>ligne 1\n    ligne indentée</pre>",
    "<p>Suite à la mise à jour, <strong>3 postes</strong> ne se connectent plus :"
    "</p><ul><li>PC12 (salle 3)</li><li>PC14 &ndash; <em>poste d'accueil</em></li>"
    '</ul><p>Voir <a href="https://example.org/kb/42">https://example.org/kb/42</a>'
    ' et le <a href="https://example.org/kb/43" title="KB 43">KB 43</a>.</p>',
]


@pytest.mark.parametrize("html", REALISTIC)
def test_realistic_bodies_display_the_same_after_the_round_trip(html: str) -> None:
    assert_survives(html)


#: Literal text snippets: every character python-markdown treats as syntax,
#: alone and in the shapes that trigger it, beside ordinary words so that
#: each lands at line starts, at word boundaries and inside words.
_SPECIAL = (
    "\\ \\\\ \\* \\_ \\[ \\# \\. \\` \\\\serveur * ** *** _ __ ___ ______ __init__ "
    "_x_ ` `` ``` ~ ~~ ~~~ [ ] [x] [x](y) ![x](y) [1]: [1]:https://example.org/n "
    "( ) (y) ! # ## #4521 > - -- --- + . 1. 2026. = == === | a|b --- < <b> </b> "
    "<Enter> <!-- --> <https://example.org> <a@b.c> <3 <= & &amp; &lt; &#65; "
    "&#x41; &#4521 &copy; &copy &D; { } : \" '"
).split(" ")
_WORDS = (
    "alpha beta snake_case C:\\Temp R&D x mot 5*3 a_b é fichier_de_test_v2.xlsx"
).split(" ")


#: Code content. A numeric reference with no semicolon is left out: inside an
#: indented code block python-markdown's raw-HTML pass adds the semicolon
#: (``test_a_numeric_reference_in_nested_code_gains_a_semicolon``).
_CODE_SPECIAL = [special for special in _SPECIAL if not special.startswith("&#")]


def _text(rng: random.Random, pieces: int, specials: list[str] = _SPECIAL) -> str:
    out = []
    for _ in range(pieces):
        out.append(rng.choice(specials) if rng.random() < 0.45 else rng.choice(_WORDS))
        out.append(rng.choice(["", " ", " ", " "]))
    return "".join(out).strip()


def _code_text(rng: random.Random, pieces: int) -> str:
    return escape(_text(rng, pieces, _CODE_SPECIAL), quote=False)


def _inline_html(rng: random.Random, formatted: bool = False, depth: int = 0) -> str:
    """Inline HTML that Markdown can express.

    No emphasis inside emphasis, no link inside a link, and a word on either
    side of every code element: python-markdown mis-pairs nested ``*`` runs
    across constructs and merges two adjacent code spans, neither of which
    involves literal text -- they are recorded in the round-trip inventory.
    """

    parts = []
    for _ in range(rng.randint(1, 4)):
        kind = rng.random()
        if kind < 0.55 or depth > 2:
            parts.append(escape(_text(rng, rng.randint(1, 4)), quote=False))
        elif kind < 0.65 and not formatted:
            parts.append(f" <strong>{_inline_html(rng, True, depth + 1)}</strong> ")
        elif kind < 0.75 and not formatted:
            parts.append(f" <em>{_inline_html(rng, True, depth + 1)}</em> ")
        elif kind < 0.82 and depth == 0:
            inner = _inline_html(rng, formatted, depth + 1)
            parts.append(
                f'<a href="https://example.org/{rng.randint(1, 9)}">{inner}</a>'
            )
        elif kind < 0.88:
            code = escape(rng.choice(_WORDS + _SPECIAL[:20]), quote=False)
            parts.append(f" mot <code>{code}</code> mot ")
        elif kind < 0.94:
            alt = escape(_text(rng, rng.randint(0, 2)), quote=True)
            parts.append(
                f'<img src="https://example.org/{rng.randint(1, 9)}.png" alt="{alt}">'
            )
        else:
            parts.append(f"<span>{_inline_html(rng, formatted, depth + 1)}</span>")
        parts.append(rng.choice(["", " ", " "]))
    return "".join(parts).strip() or "mot"


def _paragraph(rng: random.Random) -> str:
    return "<br>".join(_inline_html(rng) for _ in range(rng.randint(1, 3)))


def _list_html(rng: random.Random, depth: int) -> str:
    """A list whose items hold text, and sometimes code, a list, and more text.

    The code goes before an item's nested list, never right after it:
    python-markdown has no way to write a code block there
    (``test_code_right_after_a_nested_list_keeps_its_text``).
    """

    tag = rng.choice(["ul", "ol"])
    items = []
    for _ in range(rng.randint(1, 3)):
        shape = rng.random()
        if depth < 3 and shape < 0.1:
            # An item that opens with a list: one line holds both bullets.
            items.append(f"<li>{_list_html(rng, depth + 1)}</li>")
            continue
        inner = f"<p>{_paragraph(rng)}</p>" if shape < 0.3 else _paragraph(rng)
        if rng.random() < 0.1:
            inner += f"<pre>{_code_text(rng, 3)}</pre>"
        if depth < 3 and rng.random() < 0.3:
            inner += _list_html(rng, depth + 1)
            after = rng.random()
            if after < 0.15:
                inner += _inline_html(rng)
            elif after < 0.25:
                inner += f"<p>{_paragraph(rng)}</p>"
            elif after < 0.3:
                inner += f"<blockquote><p>{_paragraph(rng)}</p></blockquote>"
        items.append(f"<li>{inner}</li>")
    return f"<{tag}>{''.join(items)}</{tag}>"


def _block(rng: random.Random, depth: int = 0) -> str:
    kind = rng.random()
    if kind < 0.35 or depth > 1:
        return f"<p>{_paragraph(rng)}</p>"
    if kind < 0.45:
        level = rng.randint(1, 3)
        return f"<h{level}>{_inline_html(rng)}</h{level}>"
    if kind < 0.60:
        return _list_html(rng, depth + 1)
    if kind < 0.70:
        return f"<blockquote>{_block(rng, depth + 1)}</blockquote>"
    if kind < 0.80:
        head = "".join(f"<th>{_inline_html(rng)}</th>" for _ in range(2))
        rows = "".join(
            "<tr>"
            + "".join(f"<td>{_inline_html(rng)}</td>" for _ in range(2))
            + "</tr>"
            for _ in range(rng.randint(1, 2))
        )
        return f"<table><tr>{head}</tr>{rows}</table>"
    if kind < 0.87:
        return f"<pre>{_code_text(rng, 4)}</pre>"
    return f"<div>{_paragraph(rng)}</div>"


def _document(rng: random.Random) -> str:
    """A body of one to four blocks.

    python-markdown merges two adjacent lists of one type, or two adjacent
    block quotes, into one -- a limitation of the format -- so a paragraph
    separates them.
    """

    blocks: list[str] = []
    for _ in range(rng.randint(1, 4)):
        block = _block(rng)
        mergeable = block[:4] in {"<ul>", "<ol>", "<blo"}
        if blocks and mergeable and block[:4] == blocks[-1][:4]:
            blocks.append("<p>mot</p>")
        blocks.append(block)
    return "".join(blocks)


@pytest.mark.parametrize("seed", range(8))
def test_generated_bodies_display_the_same_after_the_round_trip(seed: int) -> None:
    """The property over a seeded fuzzer, 50 bodies a seed."""

    rng = random.Random(seed)
    for _ in range(50):
        assert_survives(_document(rng))


# ---------------------------------------------------------------------------
# What the escaping rests on
# ---------------------------------------------------------------------------


def test_python_markdown_undoes_every_backslash_the_reader_writes() -> None:
    """A backslash escape is only safe if python-markdown removes it again.

    Measured on 3.10.3 with the four extensions: ``\\``, backtick, ``*``,
    ``_``, ``{``, ``}``, ``[``, ``]``, ``(``, ``)``, ``>``, ``#``, ``+``,
    ``-``, ``.``, ``!`` and ``|``. ``=`` and ``~`` are not among them, which
    is why those two are spelled as character references instead.
    """

    escapable = set(Markdown(extensions=conversion._MARKDOWN_EXTENSIONS).ESCAPED_CHARS)
    backslashed = set(conversion._LITERAL) - set(conversion._SPELLED_OUT) | {"\\"}

    assert backslashed <= escapable
    assert not {"=", "~", "<", "&"} & escapable


def test_a_body_holding_the_private_stand_ins_converts_like_any_other() -> None:
    """Literal text is carried in private-use characters until it is spelled.

    A body that already holds one of them -- an icon font maps symbols
    there -- must not be confused with them, so the converter picks a block
    the body does not use.
    """

    first_block = [chr(0xF0000 + offset) for offset in range(32)]
    html = "<p>" + "".join(first_block) + " __init__ et #4521</p>"

    markdown = read(html)

    assert "".join(first_block) in markdown
    assert markdown.endswith("\\_\\_init\\_\\_ et #4521")
