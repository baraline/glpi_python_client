"""Seeded property tests: generated bodies keep their display, words and Markdown.

Each family puts the characters and shapes one of the converter's fixes is
about at every position the generator can reach. For every body, the
converter owes three things:

* **display** -- ``to_transport(from_transport(html))`` displays what
  ``html`` displays, by :func:`.display.displayed`, compared loosely on URLs
  (cmark-gfm percent-encodes a target it renders, and a browser follows
  either spelling to the same place);
* **fixed point** -- reading back what the Markdown renders gives the same
  Markdown; and
* **words** -- the words displayed, in order, are the same
  (:func:`.display.text_words`, which does not depend on the oracle).

The generators are the synthetic ones easyvista-python-client 0.4.0
verified the converter's fixes with on 2026-10-02, ported here: the
image-alt, tilde and ``!`` attack families, inline code holding line
breaks, tables nested in a cell, a heading or a link (their cells sometimes
holding a ``<p>`` or a ``<div>``), underline and highlight in every holder,
and that package's earlier document generator. Their words are invented or
generic; every URL is under ``example.org``. Each section names the fixes
it exercises, numbered as in :mod:`.test_fixes`. At the sizes below, 0.6.0
failed 39 to 100 percent of each test's bodies, and this converter none
(measured 2026-10-02, CPython 3.12.3).

What Markdown cannot spell is either expected as the converter writes it or
left out of the generators, each marked where it applies:

* expected: a line break inside a heading -- an ATX heading is one line, so
  the converter writes a space;
* expected: a table inside a link -- Markdown has no table there, so the
  converter writes the cells as the link's text
  (:func:`.display.one_line`);
* expected: underline, highlight and inserted text, which the display
  oracle cannot see, kept as raw tags around the same words
  (:func:`_raw_spans`);
* left out: a definition list, a block inside bold, bold inside bold, and
  an image title holding a backslash -- the converter keeps their words
  but not their display or, for the title, its backslash.

The user guide's "Rich-text content" section (``docs/user_guide.rst``)
lists the shapes no generator here reaches that the converter is known to
get wrong, such as a table whose rows have more cells than its first.

The sizes are a third to a tenth of the 500 to 5,400 bodies a family the
fixes were verified with, so that the whole content suite runs in about 20
seconds (measured 2026-10-02 on CPython 3.12.3 and 3.13.14 on a developer
machine).
"""

from __future__ import annotations

import html as html_module
import random
import re
import string
from collections.abc import Callable

import pytest
from bs4 import BeautifulSoup

from glpi_python_client.content.conversion import GlpiContentConverter
from glpi_python_client.content.tests.display import (
    displayed,
    loose,
    one_line,
    text_words,
)

read = GlpiContentConverter.from_transport
render = GlpiContentConverter.to_transport

# ---------------------------------------------------------------------------
# The property
# ---------------------------------------------------------------------------

_HEADING = re.compile(r"<h([1-6])>.*?</h\1>", re.DOTALL)


def _heading_breaks_as_spaces(html: str) -> str:
    """``html`` with every ``<br>`` inside a heading displayed as a space.

    An ATX heading is one line, so Markdown has no line break inside one;
    the converter writes a space, and this is the display it owes.
    """

    return _HEADING.sub(lambda heading: heading[0].replace("<br>", " "), html)


def _problems(html: str, expected: Callable[[str], object] = displayed) -> list[str]:
    """Return what the converter got wrong about ``html``: empty when nothing."""

    markdown = read(html)
    rendered = render(markdown)
    problems = []
    if loose(displayed(rendered)) != loose(expected(_heading_breaks_as_spaces(html))):
        problems.append("display")
    if read(rendered) != markdown:
        problems.append("fixed point")
    if text_words(rendered) != text_words(html):
        problems.append("words")
    if "glpi-cell" in markdown or "data-glpi-" in markdown:
        problems.append("a private marker leaked")
    return problems


def assert_property(
    bodies: list[str], expected: Callable[[str], object] = displayed
) -> None:
    failures = []
    for html in bodies:
        problems = _problems(html, expected)
        if problems:
            failures.append(f"{', '.join(problems)}: {html!r} -> {read(html)!r}")
    assert not failures, (
        f"{len(failures)} of {len(bodies)} bodies failed; the first ones:\n  "
        + "\n  ".join(failures[:5])
    )


# ---------------------------------------------------------------------------
# Image alt text, '~~~' at a line start, '!' before a link (fixes 1 to 5)
# ---------------------------------------------------------------------------

_PUNCTUATION = list(string.punctuation)
_ATOMS = ["a", "b", "x1", "C:", "Temp", "mot", "été", "—"]
_SYNTAX = [
    "~~~", "!!", "![", "](", "^", "\\", "\\\\", "a_b", "*x*", "[x]", "(y)", "<x>",
    "&amp;", "&copy;", " ", "`x`", "``", "#", "1.", "-", "+", "|", "\\_", "\\*",
    "\\[", "^^", "!^",
]  # fmt: skip


def _piece(rng: random.Random) -> str:
    draw = rng.random()
    if draw < 0.35:
        return rng.choice(_PUNCTUATION)
    if draw < 0.65:
        return rng.choice(_ATOMS)
    return rng.choice(_SYNTAX)


def _raw_text(rng: random.Random, low: int = 1, high: int = 6) -> str:
    separator = rng.choice(["", " ", ""])
    return separator.join(_piece(rng) for _ in range(rng.randint(low, high)))


def _text(rng: random.Random, low: int = 1, high: int = 6) -> str:
    return html_module.escape(_raw_text(rng, low, high), quote=False)


def _image(rng: random.Random, alt: str | None = None) -> str:
    """An image. Never with a title: mdformat writes a title raw, so a
    backslash in one is lost -- a known limit, out of these families."""

    alt = _raw_text(rng) if alt is None else alt
    alt = html_module.escape(alt, quote=True)
    return f'<img src="https://example.org/i{rng.randint(0, 9)}.png" alt="{alt}">'


def _link(rng: random.Random, inner: str | None = None) -> str:
    inner = _text(rng) if inner is None else inner
    return f'<a href="https://example.org/p{rng.randint(0, 9)}">{inner}</a>'


_CONTEXTS = [
    "<p>{x}</p>",
    "<p>mot {x} mot</p>",
    "<p>mot{x}mot</p>",
    "<ul><li>{x}</li></ul>",
    "<ol><li>a<ul><li>b<ol><li>{x}</li></ol></li></ul></li></ol>",
    "<blockquote><p>{x}</p></blockquote>",
    "<blockquote><ul><li>{x}</li></ul></blockquote>",
    "<ul><li><blockquote><p>{x}</p></blockquote></li></ul>",
    "<h2>{x}</h2>",
    "<table><tr><th>h</th></tr><tr><td>{x}</td></tr></table>",
    "<p><b>{x}</b></p>",
    "<p><em>{x}</em></p>",
    "<div>{x}</div>",
    "<p>a<br>{x}</p>",
    "<p>{x}<br>z</p>",
]


def alt_bodies(rng: random.Random, random_bodies: int) -> list[str]:
    """Every punctuation character alone and in shapes, as alt and link text,
    then random mixes of images and links in every context."""

    bodies = []
    for char in [*_PUNCTUATION, "~~~", "^x", "^", "!", "![", "\\", "\\\\x", "&", "a b"]:
        for shape in ("{c}", "{c}y", "y{c}", "y {c} z", "{c}{c}"):
            alt = shape.format(c=char)
            bodies.append(f"<p>{_image(rng, alt)}</p>")
            bodies.append(f"<p>{_link(rng, html_module.escape(alt, quote=False))}</p>")
            bodies.append(f"<p>{_link(rng, _image(rng, alt))}</p>")
    for _ in range(random_bodies):
        draw = rng.random()
        if draw < 0.3:
            inline = _image(rng)
        elif draw < 0.5:
            inline = _link(rng)
        elif draw < 0.7:
            inline = _link(rng, _text(rng, 0, 2) + _image(rng) + _text(rng, 0, 2))
        elif draw < 0.85:
            inline = (
                _text(rng, 0, 2) + _image(rng) + _text(rng, 0, 3) + _link(rng)
                + _text(rng, 0, 2)
            )  # fmt: skip
        else:
            inline = _image(rng) + _image(rng) + _link(rng) + _image(rng)
        bodies.append(rng.choice(_CONTEXTS).format(x=inline))
    return bodies


_TILDES = [
    "~~~", "~~~~", "~~~~~~", "~~~ info", "~~~x", "~~~ ~~~", "~~~`", "~~~ a`b",
    "&#126;&#126;&#126;", "~&#126;~",
    "~ ~ ~", "~~", "```", "\\~~~", "a~~~",  # controls: no fence to guard
]  # fmt: skip
_TILDE_PREFIXES = [
    "", " ", "&nbsp;", "\t", "<span></span>", "<b></b>", "<span> </span>",
    "&#8203;", "&nbsp;&nbsp;&nbsp;&nbsp;", "\n",
]  # fmt: skip
#: Where a run can open a line. A definition list is left out: markdownify
#: writes it in a syntax CommonMark does not have.
_TILDE_PLACES = [
    "<p>{t} rest</p>",
    "<p>{t}</p>",
    "<p>intro<br>{t}<br>suite</p>",
    "<p>intro<br>{t}</p>",
    '<p><a href="https://example.org/u">intro<br>{t}</a></p>',
    "<p><strong>intro<br>{t}</strong> z</p>",
    "<p><em>intro<br>{t}</em></p>",
    "<p><s>intro<br>{t}</s></p>",
    "<p><span>intro<br>{t}</span></p>",
    "<ul><li>{t}</li></ul>",
    "<ul><li>a<br>{t}</li></ul>",
    '<ol start="3"><li>{t}</li><li>b</li></ol>',
    "<ul><li>a<ul><li>b<ol><li>{t}</li></ol></li></ul></li></ul>",
    "<ul><li>a<ul><li>b<ol><li>c<br>{t}</li></ol></li></ul></li></ul>",
    "<ul><li><p>a</p><p>{t}</p></li></ul>",
    "<blockquote>{t}</blockquote>",
    "<blockquote><p>a<br>{t}</p></blockquote>",
    "<blockquote><blockquote><p>a<br>{t}</p></blockquote></blockquote>",
    "<ul><li><blockquote><p>{t}</p></blockquote></li></ul>",
    "<blockquote><ul><li>x<br>{t}</li></ul></blockquote>",
    "<table><tr><th>h</th></tr><tr><td>{t}</td></tr></table>",
    "<table><tr><th>h</th></tr><tr><td>a<br>{t}</td></tr></table>",
    "<h3>{t}</h3>",
    "<h3>a<br>{t}</h3>",
    '<p><img src="https://example.org/i.png" alt="x"><br>{t}</p>',
    "<p>{t}<br>code<br>{t}</p>",
    "<p>{t}</p><p>text</p><p>{t}</p>",
    "<div>{t}</div>",
    "<div>a</div>{t}",
    "{t}<br><b>x</b>",
    "<pre>{t}\ncode\n{t}</pre>",
    "<p><code>{t}</code></p>",
    "<p>x<br><code>{t}</code></p>",
    '<p>a<br><a href="https://example.org/u">{t}</a></p>',
    "<p>a<br>!{t}</p>",
    '<p>a<br><img src="https://example.org/i.png" alt="{t}"></p>',
]


def tilde_bodies(prefixes: int) -> list[str]:
    """Every run at every place, behind ``prefixes`` of the prefixes in turn.

    The full product is 5,180 bodies; rotating the prefixes keeps every
    run at every place and spreads the prefixes over them.
    """

    bodies = []
    for i, place in enumerate(_TILDE_PLACES):
        for j, run in enumerate(_TILDES):
            for k in range(prefixes):
                prefix = _TILDE_PREFIXES[(i + j + k) % len(_TILDE_PREFIXES)]
                bodies.append(place.replace("{t}", prefix + run))
    return bodies


#: A '!' right before every inline thing a '[' can open.
_BANGS = [
    '<p>a!<a href="https://example.org/u">voir</a></p>',
    '<p>a!<a href="https://example.org/u">https://example.org/u</a></p>',
    '<p>a!<a href="mailto:x@example.org">x@example.org</a></p>',
    '<p>a!<a href="mailto:x@example.org">mailto:x@example.org</a></p>',
    '<p>a!<img src="i.png" alt="x"></p>',
    '<p>a!!<img src="i.png" alt="x"></p>',
    '<p>a!!<a href="u">v</a></p>',
    '<p>!<a href="u">v</a></p>',
    '<p>a!<a href="u"><img src="i.png" alt="x"></a></p>',
    '<p>a!<a href="u">t<img src="i.png" alt="x"></a></p>',
    '<p>a!<br><a href="u">voir</a></p>',
    '<p>a!\n<a href="u">voir</a></p>',
    '<p>a! <a href="u">voir</a></p>',
    '<p><b>a!</b><a href="u">v</a></p>',
    '<p>x<b>a!</b><a href="u">v</a></p>',
    '<p><em>a!</em><a href="u">v</a></p>',
    '<p><code>a!</code><a href="u">v</a></p>',
    '<p><a href="u">a!</a><a href="v">b</a></p>',
    '<p>a!<b><a href="u">v</a></b></p>',
    '<p>a!<span><a href="u">v</a></span></p>',
    '<p>a!<s><a href="u">v</a></s></p>',
    '<p>a&#33;<a href="u">v</a></p>',
    '<p>a\\!<a href="u">v</a></p>',
    '<p>a\\\\!<a href="u">v</a></p>',
    "<p>a![x](y)</p>",
    "<p>a!&#91;x&#93;(y)</p>",
    "<p>a!<a>[x]</a>(y)</p>",
    '<p>a!<a href="u">^x</a></p>',
    '<p>a!<a href="u" title="t">v</a></p>',
    '<p>a<br>!<a href="u">v</a></p>',
    '<p>a!<a href="u"></a><a href="v">x</a></p>',
    '<p>a!<img src="i.png" alt="^x"></p>',
    '<p><img src="i.png" alt="x!"><a href="u">v</a></p>',
    '<p>a!<a href="u"><b>v</b></a></p>',
    '<p>a!<a href="u"><code>v</code></a></p>',
    "<p>!!!</p>",
    "<p>Hello! World!</p>",
    "<p>a!b!c</p>",
    "<p><b>!</b></p>",
    "<p>a<b>!x</b>b</p>",
    '<p>a<s>!</s><a href="u">v</a></p>',
    '<p>a!<br>!<a href="u">v</a></p>',
    "<p>!<code>x</code></p>",
    '<p>a !<a href="https://example.org/u">https://example.org/u</a></p>',
    '<p>a!<a href="u">v</a>!<a href="u">w</a>!</p>',
    '<p>a!<a href="https://example.org/u">https://example.org/u</a>!</p>',
]
_BANG_CONTEXTS = [
    "<ul><li>{x}</li></ul>",
    "<blockquote>{x}</blockquote>",
    "<table><tr><th>h</th></tr><tr><td>{x}</td></tr></table>",
    "<h2>{x}</h2>",
    "<ol><li><ul><li>{x}</li></ul></li></ol>",
    "<div><b>{x}</b></div>",
]


def bang_bodies(rng: random.Random, random_bodies: int) -> list[str]:
    """Each case alone and in every context, then random ``!``-then-inline runs.

    Bold inside bold is left out of the ``<b>`` context: CommonMark spells
    both with ``**``, and ``****`` is not bold.
    """

    bodies = []
    for case in _BANGS:
        bodies.append(case)
        inner = case[3:-4]
        for context in _BANG_CONTEXTS:
            if not ("<b>" in context and "<b>" in inner):
                bodies.append(context.format(x=inner))
    for _ in range(random_bodies):
        before = _text(rng, 0, 3) + rng.choice(["!", "!!", "&#33;", "\\!", "! "])
        after = rng.choice(
            [
                _link(rng),
                _image(rng),
                _link(rng, _image(rng)),
                "<br>" + _link(rng),
                '<a href="https://example.org/q">https://example.org/q</a>',
                "<b>" + _link(rng) + "</b>",
                "<code>c</code>" + _link(rng),
            ]
        )
        context = rng.choice(_CONTEXTS)
        if "<b>" in context and "<b>" in after:
            context = "<p>{x}</p>"  # bold inside bold: left out, as above
        bodies.append(context.format(x=before + after + _text(rng, 0, 2)))
    return bodies


@pytest.mark.parametrize("seed", [1, 2])
def test_image_alt_and_link_text_survive(seed: int) -> None:
    rng = random.Random(seed)
    bodies = alt_bodies(rng, 150)
    if seed != 1:  # the enumerated part is the same for every seed
        bodies = bodies[-150:]
    assert_property(bodies)


def test_a_tilde_run_opening_a_line_stays_text() -> None:
    assert_property(tilde_bodies(prefixes=1))


@pytest.mark.parametrize("seed", [1, 2])
def test_a_bang_before_a_link_or_an_image_stays_text(seed: int) -> None:
    rng = random.Random(seed)
    bodies = bang_bodies(rng, 150)
    if seed != 1:
        bodies = bodies[-150:]
    assert_property(bodies)


# ---------------------------------------------------------------------------
# Inline code holding line breaks (fix 6)
# ---------------------------------------------------------------------------

_CODE_WORDS = [
    "alpha", "beta", "C:\\Temp", "a_b", "x|y", "5*3", "R&amp;D", "[x]", "`tick`",
    "--", "#4521", "&lt;b&gt;",
]  # fmt: skip


def _code_text(rng: random.Random) -> str:
    out = []
    for _ in range(rng.randint(1, 5)):
        out.append(rng.choice(_CODE_WORDS))
        out.append(rng.choice([" ", " ", "<br>", "<br><br>", ""]))
    if rng.random() < 0.2:
        out.insert(0, "<br>")
    return "".join(out).strip() or "x"


def code_break_body(rng: random.Random) -> str:
    """``<code>``, ``<kbd>`` or ``<samp>`` holding line breaks, in every holder."""

    tag = rng.choice(["code", "code", "kbd", "samp"])
    code = f"<{tag}>{_code_text(rng)}</{tag}>"
    before = rng.choice(["", "mot ", "a<br>"])
    after = rng.choice(["", " fin", "<br>b", "fin"])
    inline = f"{before}{code}{after}"
    shape = rng.choice(["p", "li", "quote", "h2", "a", "td", "p-strong"])
    if shape == "p":
        return f"<p>{inline}</p>"
    if shape == "p-strong":
        return f"<p>x <strong>{inline}</strong> y</p>"
    if shape == "li":
        return f"<ul><li>{inline}</li><li>deux</li></ul>"
    if shape == "quote":
        return f"<blockquote><p>{inline}</p></blockquote>"
    if shape == "h2":
        return f"<h2>{inline}</h2>"
    if shape == "a":
        return f'<p><a href="https://example.org/{rng.randint(1, 9)}">{inline}</a></p>'
    return (
        "<table><tr><th>H</th><th>I</th></tr>"
        f"<tr><td>{inline}</td><td>z</td></tr></table>"
    )


@pytest.mark.parametrize("seed", [20261001, 2])
def test_a_line_break_in_inline_code_survives(seed: int) -> None:
    rng = random.Random(seed)
    assert_property([code_break_body(rng) for _ in range(300)])


# ---------------------------------------------------------------------------
# Generic inline content, and tables nested in a cell, a heading or a link
# (fixes 7 to 9; 8 is a block in a flattened cell)
# ---------------------------------------------------------------------------

#: Literal text snippets: Markdown syntax alone and in the shapes that
#: trigger it, beside ordinary words, so that each lands at line starts, at
#: word boundaries and inside words.
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

#: Code content: a numeric reference with no semicolon is left out, as it
#: was from the generator this one is ported from.
_CODE_SPECIAL = [special for special in _SPECIAL if not special.startswith("&#")]


def _prose(rng: random.Random, pieces: int, specials: list[str] = _SPECIAL) -> str:
    out = []
    for _ in range(pieces):
        out.append(rng.choice(specials) if rng.random() < 0.45 else rng.choice(_WORDS))
        out.append(rng.choice(["", " ", " ", " "]))
    return "".join(out).strip()


def _inline_html(rng: random.Random, formatted: bool = False, depth: int = 0) -> str:
    """Inline HTML Markdown can express.

    No emphasis inside emphasis -- ``****`` is not bold -- no link inside a
    link, and a word on either side of every code element, which keeps two
    code spans from touching.
    """

    parts = []
    for _ in range(rng.randint(1, 4)):
        kind = rng.random()
        if kind < 0.55 or depth > 2:
            parts.append(
                html_module.escape(_prose(rng, rng.randint(1, 4)), quote=False)
            )
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
            code = html_module.escape(rng.choice(_WORDS + _SPECIAL[:20]), quote=False)
            parts.append(f" mot <code>{code}</code> mot ")
        elif kind < 0.94:
            alt = html_module.escape(_prose(rng, rng.randint(0, 2)), quote=True)
            parts.append(
                f'<img src="https://example.org/{rng.randint(1, 9)}.png" alt="{alt}">'
            )
        else:
            parts.append(f"<span>{_inline_html(rng, formatted, depth + 1)}</span>")
        parts.append(rng.choice(["", " ", " "]))
    return "".join(parts).strip() or "mot"


def _nested_table(rng: random.Random, depth: int) -> str:
    """A table whose cells hold inline content, a block of it, or a table.

    A block -- a ``<p>`` or a ``<div>`` -- in a flattened cell is what fix 8
    keeps on its holder's line.
    """

    rows = []
    for _ in range(rng.randint(1, 2)):
        cells = []
        for _ in range(rng.randint(1, 3)):
            if depth < 3 and rng.random() < 0.35:
                inner = _nested_table(rng, depth + 1)
                content = rng.choice([inner, "avant " + inner, inner + " apres"])
            elif rng.random() < 0.3:
                block = rng.choice(["p", "div"])
                content = "".join(
                    f"<{block}>{_inline_html(rng)}</{block}>"
                    for _ in range(rng.randint(1, 2))
                )
            else:
                content = _inline_html(rng)
            tag = "th" if rng.random() < 0.2 else "td"
            cells.append(f"<{tag}>{content}</{tag}>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    caption = "<caption>Legende</caption>" if rng.random() < 0.15 else ""
    return f"<table>{caption}{''.join(rows)}</table>"


def nested_table_body(rng: random.Random, where: str) -> str:
    """Tables nested up to three deep, inside a cell, a heading or a link."""

    inner = _nested_table(rng, 2)
    if where == "cell":
        return (
            "<table><tr><th>A</th><th>B</th></tr>"
            f"<tr><td>x</td><td>{inner}</td></tr></table>"
        )
    if where == "heading":
        return f"<h3>Titre {inner}</h3>"
    # No link inside a link. A space where each tag was, or removing a link
    # around emphasis could leave it touching the next: "****" is not bold.
    inner = re.sub(r"</?a\b[^>]*>", " ", inner)
    return f'<p><a href="https://example.org/t">{inner}</a></p>'


@pytest.mark.parametrize("where", ["cell", "heading"])
def test_a_nested_table_reads_as_its_cells_words(where: str) -> None:
    """A browser shows the nested table inside its cell or heading; the
    converter writes its cells' words there, in order, spaced."""

    rng = random.Random(20261001)
    assert_property([nested_table_body(rng, where) for _ in range(80)])


def test_a_table_inside_a_link_reads_as_the_links_text() -> None:
    """A browser draws the table inside the link; Markdown has no table there,
    so the converter writes its cells' words as the link's text, in order,
    each still linked and formatted -- which is what is checked."""

    rng = random.Random(20261001)
    assert_property([nested_table_body(rng, "link") for _ in range(80)], one_line)


# ---------------------------------------------------------------------------
# Underline, highlight and inserted text (fix 11)
# ---------------------------------------------------------------------------

_RAW_TAGS = ("u", "mark", "ins")
_MARKED_WORDS = [
    "alpha", "beta", "a_b", "*x*", "C:\\Temp", "R&amp;D", "[y]", "!", "~~~",
    "&lt;&lt;z",
]  # fmt: skip


def _marked_inline(
    rng: random.Random, inside: frozenset[str] = frozenset(), depth: int = 0
) -> str:
    """Inline content with ``<u>``, ``<mark>`` and ``<ins>`` at any depth.

    The three nest in each other and in themselves. Left out, as in
    :func:`_inline_html`: bold or italic inside either, a link inside a
    link, and anything but a word inside code; bold, italic and code keep a
    space on each side. Let in, with those spaces dropped too, bold and
    italic failed 129 of 2,000 bodies (measured 2026-10-02): they are what
    the generator this one is ported from tripped on.
    """

    parts = []
    for _ in range(rng.randint(1, 4)):
        draw = rng.random()
        if draw < 0.4 or depth > 2:
            parts.append(rng.choice(_MARKED_WORDS))
        elif draw < 0.6:
            tag = rng.choice(_RAW_TAGS)
            pad = rng.choice(["", " "]), rng.choice(["", " "])
            body = _marked_inline(rng, inside, depth + 1)
            parts.append(f"<{tag}>{pad[0]}{body}{pad[1]}</{tag}>")
        elif draw < 0.68 and not inside & {"b", "em"}:
            tag = rng.choice(["b", "em"])
            body = _marked_inline(rng, inside | {"b", "em"}, depth + 1)
            parts.append(f" <{tag}>{body}</{tag}> ")
        elif draw < 0.72 and "s" not in inside:
            parts.append(f"<s>{_marked_inline(rng, inside | {'s'}, depth + 1)}</s>")
        elif draw < 0.78:
            parts.append(f" mot <code>{rng.choice(_MARKED_WORDS)}</code> mot ")
        elif draw < 0.86 and "a" not in inside:
            body = _marked_inline(rng, inside | {"a"}, depth + 1)
            parts.append(
                f'<a href="https://example.org/{rng.randint(1, 9)}">{body}</a>'
            )
        elif draw < 0.93:
            parts.append("<br>")
        else:
            alt = rng.choice(_MARKED_WORDS)
            parts.append(f'<img src="https://example.org/i.png" alt="{alt}">')
    return rng.choice([" ", "", " "]).join(parts)


def marked_body(rng: random.Random) -> str:
    """One to three blocks of :func:`_marked_inline`, in every kind of holder."""

    def block() -> str:
        draw = rng.random()
        if draw < 0.15:
            level = rng.randint(1, 3)
            return f"<h{level}>{_marked_inline(rng)}</h{level}>"
        if draw < 0.3:
            return (
                f"<ul><li>{_marked_inline(rng)}</li><li>{_marked_inline(rng)}</li></ul>"
            )
        if draw < 0.4:
            return (
                "<table><tr><th>h</th><th>i</th></tr>"
                f"<tr><td>{_marked_inline(rng)}</td><td>{_marked_inline(rng)}</td></tr>"
                "</table>"
            )
        if draw < 0.5:
            return f"<blockquote><p>{_marked_inline(rng)}</p></blockquote>"
        return f"<p>{_marked_inline(rng)}</p>"

    blocks: list[str] = []
    for _ in range(rng.randint(1, 3)):
        new = block()
        if blocks and new[:4] in {"<ul>", "<blo"} and new[:4] == blocks[-1][:4]:
            blocks.append("<p>mot</p>")  # two of these in a row merge in Markdown
        blocks.append(new)
    return "".join(blocks)


def _raw_spans(html: str) -> list[tuple[str, str]]:
    """Each ``<u>``, ``<mark>`` and ``<ins>`` with text, and its text, in order.

    The display oracle cannot see these tags, so this is what holds the
    converter to keeping them. The text is the tag's words
    (:func:`.display.text_words`): the converter moves a tag's edge spaces
    and line breaks outside it.
    """

    soup = BeautifulSoup(html, "html.parser")
    spans = []
    for tag in soup.find_all(_RAW_TAGS):
        words = text_words(str(tag))
        if words:
            spans.append((tag.name, " ".join(words)))
    return spans


@pytest.mark.parametrize("seed", [20261002, 2])
def test_underline_and_highlight_keep_their_text_and_their_tags(seed: int) -> None:
    rng = random.Random(seed)
    bodies = [marked_body(rng) for _ in range(150)]

    assert_property(bodies)
    lost = [
        html for html in bodies if _raw_spans(render(read(html))) != _raw_spans(html)
    ]
    assert not lost, f"{len(lost)} bodies lost a raw tag; the first: {lost[0]!r}"


# ---------------------------------------------------------------------------
# Whole documents
# ---------------------------------------------------------------------------


def _paragraph(rng: random.Random) -> str:
    return "<br>".join(_inline_html(rng) for _ in range(rng.randint(1, 3)))


def _list_html(rng: random.Random, depth: int) -> str:
    """A list whose items hold text, and sometimes code, a list, and more text."""

    tag = rng.choice(["ul", "ol"])
    items = []
    for _ in range(rng.randint(1, 3)):
        shape = rng.random()
        if depth < 3 and shape < 0.1:
            items.append(f"<li>{_list_html(rng, depth + 1)}</li>")
            continue
        inner = f"<p>{_paragraph(rng)}</p>" if shape < 0.3 else _paragraph(rng)
        if rng.random() < 0.1:
            code = html_module.escape(_prose(rng, 3, _CODE_SPECIAL), quote=False)
            inner += f"<pre>{code}</pre>"
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
        code = html_module.escape(_prose(rng, 4, _CODE_SPECIAL), quote=False)
        return f"<pre>{code}</pre>"
    return f"<div>{_paragraph(rng)}</div>"


def document(rng: random.Random) -> str:
    """A body of one to four blocks.

    Markdown merges two adjacent lists of one type, or two adjacent block
    quotes, into one -- a limit of the format -- so a paragraph separates
    them.
    """

    blocks: list[str] = []
    for _ in range(rng.randint(1, 4)):
        block = _block(rng)
        mergeable = block[:4] in {"<ul>", "<ol>", "<blo"}
        if blocks and mergeable and block[:4] == blocks[-1][:4]:
            blocks.append("<p>mot</p>")
        blocks.append(block)
    return "".join(blocks)


@pytest.mark.parametrize("seed", range(4))
def test_a_generated_document_survives(seed: int) -> None:
    """The earlier generator of easyvista-python-client, 40 bodies a seed."""

    rng = random.Random(seed)
    assert_property([document(rng) for _ in range(40)])
