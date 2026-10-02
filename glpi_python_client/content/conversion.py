"""Content conversion between GLPI's HTML and the package's Markdown.

GLPI stores rich text as HTML; the package's surface is Markdown.

* **Read** -- :meth:`GlpiContentConverter.from_transport`. ``markdownify``
  writes the HTML as Markdown with every character that could be syntax
  escaped, then ``mdformat`` re-renders that Markdown from its syntax tree,
  which keeps only the escapes CommonMark needs. Text is literal:
  ``__init__`` typed into GLPI reads back as ``\\_\\_init\\_\\_``.
* **Write** -- :meth:`GlpiContentConverter.to_transport`. ``cmark-gfm``
  renders CommonMark with GFM tables; a newline is a line break and raw
  HTML passes through.

The aim is that rendering the Markdown a read gives displays what GLPI
displayed, and that reading that back gives the same Markdown. Some
synthetic shapes still lose words or the fixed point; the user guide's
"Rich-text content" section lists them. The glue below covers what the
three libraries leave out: plain text, line breaks a browser does not
show, bold and italic CommonMark would not close, link targets, and an
mdformat set up without its nesting cap and with its quadratic lookups made
linear. A body nested too deeply for the stack, or on which the
conversion raises ``ValueError`` -- markdownify does for a ``colspan`` or
``start`` it cannot read as a number -- is read as its text
(:func:`_text_of`); anything else that fails raises
:class:`~glpi_python_client.GlpiContentError`.

The reader is ``easyvista-python-client`` 0.4.1's, helper for helper: that
package ported this module at commit ``917f030`` and added fifteen fixes,
which 0.6.1 ports back with the correction to fix 11 both packages now
carry (a ``<u>``, ``<mark>`` or ``<ins>`` round a block is dropped). The
two modules differ only in names, messages, docstrings and that package's
optional-dependency import guard, and should move together: the hard part
of both is the behaviour of the same libraries, not anything either ITSM
does.
"""

from __future__ import annotations

import re
import string
import unicodedata
from collections.abc import Callable, Iterator, Mapping, MutableMapping, Sequence
from functools import cached_property
from html import escape, unescape
from typing import Any, cast

import cmarkgfm
import mdformat_tables
from bs4 import BeautifulSoup, ParserRejectedMarkup, Tag
from bs4.element import PageElement, PreformattedString
from markdown_it import MarkdownIt
from markdown_it.token import Token
from markdownify import MarkdownConverter
from mdformat.renderer import (
    DEFAULT_RENDERERS,
    MDRenderer,
    RenderContext,
    RenderTreeNode,
)
from mdformat.renderer.typing import Postprocess

from glpi_python_client._errors import GlpiContentError

#: Element names that make a ``<...>`` sequence markup rather than text: the
#: HTML5 elements, then the obsolete ones old editors and mail clients write.
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

#: ``<`` or ``</`` right before a name: one candidate tag.
_CANDIDATE_TAG = re.compile(r"</?([a-zA-Z][a-zA-Z0-9]*)\b[^<>]*>")

#: Elements a browser lays out as blocks: a line ends at their edges.
_BLOCKS = frozenset(
    """
    address article aside blockquote body caption center dd details dir div
    dl dt fieldset figcaption figure footer form h1 h2 h3 h4 h5 h6 header hr
    html li main menu nav ol p pre section summary table tbody td tfoot th
    thead tr ul
    """.split()
)

#: Anything between angle brackets, for the parser-rejected fallback.
_ANY_TAG = re.compile(r"<[^<>]*>?")

#: Elements whose content a browser does not display.
_HIDDEN = ["head", "script", "style", "template", "title"]

#: The elements whose ``*`` markers are checked, and the attributes that
#: carry the characters displayed on either side of one (:func:`_note_sides`).
_EMPHASIS = frozenset({"b", "strong", "em", "i"})
_BEFORE, _AFTER = "data-glpi-before", "data-glpi-after"
_NUMBER = "data-glpi-number"  # an ordered item's number (_Converter.convert_li)

#: The elements kept as raw tags (:meth:`_Converter.convert_u`), and the
#: attribute marking one that holds a block (:func:`_note_blocks`).
_RAW_INLINE = frozenset({"u", "mark", "ins"})
_HOLDS_BLOCK = "data-glpi-block"

#: Text split into leading line breaks and spaces, content, trailing ones.
#: The content ends on its last character that is neither, found greedily:
#: a lazy ``.*?`` rescanned the run after it at every step, quadratic.
_EDGES = re.compile(
    r"((?:\\\n|\s)*)((?:.*(?:[^\\\s]|\\(?!\n)))?)((?:\\\n|\s)*)", re.DOTALL
)

#: A URL that is its own CommonMark autolink and that markdown-it leaves as it
#: is: printable ASCII it does not percent-encode.
_AUTOLINK = re.compile(
    r"[A-Za-z][A-Za-z0-9+.-]{1,31}:[A-Za-z0-9;/?:@&=+$,\-_.!~*'()#%]*"
)

_BACKTICK_RUN = re.compile("`{3,}")


def _language(pre: Tag) -> str | None:
    """Return the language cmark-gfm wrote on a fence as ``class="language-x"``."""

    for tag in (pre.find("code"), pre):
        if isinstance(tag, Tag):
            for name in tag.get_attribute_list("class"):
                if name and name.startswith("language-"):
                    return str(name[len("language-") :])
    return None


#: ``markdownify`` options; the converter's overrides decide the rest.
_MARKDOWNIFY_OPTIONS: dict[str, Any] = {
    "code_language_callback": _language,
    "bullets": "-",
    "escape_misc": True,
    "heading_style": "atx",
    "newline_style": "backslash",
    "wrap": True,  # a newline in HTML text is a space...
    "wrap_width": None,  # ...and no line is wrapped
}

#: cmark-gfm's options: a newline is a line break, raw HTML passes through.
_RENDER_OPTIONS = (
    cmarkgfm.cmark.Options.CMARK_OPT_HARDBREAKS
    | cmarkgfm.cmark.Options.CMARK_OPT_UNSAFE
)


def _looks_like_html(content: str) -> bool:
    """Return whether ``content`` holds at least one real HTML element.

    The element *name* decides, so ``use the <Enter> key`` and
    ``if x<y then z>0`` are text. ``a<b>c`` is markup: ``b`` is an element.
    """

    return any(
        match.group(1).lower() in _HTML_ELEMENTS
        for match in _CANDIDATE_TAG.finditer(content)
    )


def _plain_text_html(text: str) -> str:
    """Return the HTML that displays ``text`` as GLPI does: literally, line by line."""

    lines = (escape(line, quote=False) for line in text.splitlines())
    return "<p>" + "<br>".join(lines) + "</p>"


def _soup(html: str) -> BeautifulSoup:
    """Parse ``html`` and drop what a browser does not display."""

    soup = BeautifulSoup(html, "html.parser")
    for hidden in soup.find_all(_HIDDEN):
        hidden.extract()
    return soup


#: The parts of a table other than its cells.
_TABLE_PARTS = frozenset(
    {"table", "thead", "tbody", "tfoot", "tr", "caption", "colgroup", "col"}
)

#: What Markdown writes on one line: a table inside one cannot be a table.
_ONE_LINE = frozenset({"td", "th", "a", "h1", "h2", "h3", "h4", "h5", "h6"})


def _flatten_nested_tables(root: Tag) -> None:
    """Write a table that sits inside a cell, a heading or a link as its cells' text.

    A GFM cell holds one line, so a nested table -- the usual layout of an
    e-mail signature -- written as a table split the outer row and lost
    every word; in a heading or a link its pipes became text. Inside one, a
    table's parts become ``span`` and its cells ``glpi-cell``, which
    :class:`_Converter` writes as spaced inline text. Renaming in one walk
    keeps it linear however deeply tables nest.
    """

    cells = 0
    counted: list[bool] = []
    for node, entering in _walk(root):
        if not isinstance(node, Tag):
            continue
        if not entering:
            if counted.pop():
                cells -= 1
            continue
        is_cell = node.name in ("td", "th")
        if cells and (is_cell or node.name in _TABLE_PARTS):
            node.name = "glpi-cell" if is_cell else "span"
            counted.append(False)
            continue
        holds = node.name in _ONE_LINE and (node.name != "a" or bool(node.get("href")))
        counted.append(holds)
        cells += holds


def _walk(root: Tag) -> Iterator[tuple[PageElement, bool]]:
    """Yield the nodes under ``root`` in document order, each tag in and out.

    A tag comes with ``True`` on the way in and ``False`` on the way out.
    Comments and declarations are skipped. The walk keeps its own stack, so
    it costs nothing in recursion however deep the document is.
    """

    stack = [(node, True) for node in reversed(root.contents)]
    while stack:
        node, entering = stack.pop()
        if isinstance(node, PreformattedString):
            continue
        yield node, entering
        if entering and isinstance(node, Tag):
            stack.append((node, False))
            stack.extend((child, True) for child in reversed(node.contents))


def _drop_trailing_breaks(root: Tag) -> None:
    """Turn every ``<br>`` its block shows nothing after into a ``<wbr>``.

    A browser shows no line for such a break, and CommonMark shows a
    backslash break that ends a block as a backslash. ``<wbr>`` displays
    nothing either, and renaming costs nothing where removing a node from a
    long run of siblings costs the length of the run.
    """

    pending: list[Tag] = []
    for node, entering in _walk(root):
        if not isinstance(node, Tag):
            if str(node).strip():
                pending.clear()
        elif node.name in _BLOCKS:
            for line_break in pending:
                line_break.name = "wbr"
            pending.clear()
        elif entering and node.name == "br":
            pending.append(node)
        elif entering and node.name == "img":
            pending.clear()
    for line_break in pending:
        line_break.name = "wbr"


def _note_sides(root: Tag) -> None:
    """Note on each bold or italic element the characters displayed on either side.

    One pass: ``last`` is the last character shown so far on the current
    line, and an element that has closed waits for the next one. A line edge
    counts as a space, as it does for CommonMark, and so does the edge of a
    flattened cell, which :class:`_Converter` spaces.
    """

    last = " "
    waiting: list[Tag] = []
    for node, entering in _walk(root):
        if isinstance(node, Tag):
            if node.name in _EMPHASIS:
                if entering:
                    node[_BEFORE] = last
                else:
                    waiting.append(node)
                continue
            if node.name not in _BLOCKS and node.name not in ("br", "glpi-cell"):
                continue
            first = last = " "
        else:
            text = str(node)
            if not text:
                continue
            first, last = text[0], text[-1]
        for element in waiting:
            element[_AFTER] = first
        waiting.clear()
    for element in waiting:
        element[_AFTER] = " "


def _note_blocks(root: Tag) -> None:
    """Mark each ``<u>``, ``<mark>`` or ``<ins>`` that holds a block.

    Markdown has no inline tag around blocks: such a tag wrapped round them
    showed a table, a list or a heading as its Markdown source, and round a
    ``<pre>`` left a fence open to the end of the body. One walk: a block
    marks the open ones from the innermost out and stops at one already
    marked, whose holders were marked with it, so each is marked once
    however deeply they nest.
    """

    holders: list[Tag] = []
    for node, entering in _walk(root):
        if not isinstance(node, Tag):
            continue
        if node.name in _RAW_INLINE:
            if entering:
                holders.append(node)
            else:
                holders.pop()
        elif entering and node.name in _BLOCKS:
            for holder in reversed(holders):
                if holder.has_attr(_HOLDS_BLOCK):
                    break
                holder[_HOLDS_BLOCK] = ""


def _punctuation(char: str) -> bool:
    """Return whether CommonMark counts ``char`` as punctuation."""

    return char in string.punctuation or unicodedata.category(char).startswith("P")


def _flanks(inner: str, before: str, after: str) -> bool:
    """Return whether CommonMark reads ``*`` runs around ``inner`` as emphasis.

    ``inner`` neither starts nor ends with whitespace. A run opening onto
    punctuation needs whitespace or punctuation in front of it, and a run
    closing after punctuation needs the same behind it.
    """

    opens = not _punctuation(inner[0]) or before.isspace() or _punctuation(before)
    closes = not _punctuation(inner[-1]) or after.isspace() or _punctuation(after)
    return opens and closes


def _destination(url: str) -> str:
    """Spell ``url`` as a link destination that reads back as ``url``."""

    url = re.sub(r"[\t\n\r]", "", url)
    return "<" + re.sub(r"[\\<>]", r"\\\g<0>", url) + ">"


def _title(title: str) -> str:
    """Spell a link or image title, with the space before it."""

    title = " ".join(title.split())
    return ' "' + re.sub(r'[\\"]', r"\\\g<0>", title) + '"' if title else ""


class _Converter(MarkdownConverter):
    """``markdownify``, with what CommonMark and the reader's glue need on top.

    The stub ``markdownify`` ships declares the constructor and ``convert``
    alone, so its converters are reached through :meth:`_inherited`.
    """

    def _inherited(self, name: str) -> Any:
        return getattr(super(), name)

    def escape(self, text: str, parent_tags: set[str]) -> str:
        """Escape a text's last ``!`` as well: before a link it makes an image.

        A ``!`` meets a ``[`` only there, markdownify escaping a ``[`` in text;
        mdformat keeps that escape before a link and drops it anywhere else.
        """

        text = str(self._inherited("escape")(text, parent_tags))
        return text[:-1] + "\\!" if text.endswith("!") else text

    def process_tag(self, node: Any, parent_tags: Any = None) -> str:
        if node.name == "glpi-cell":  # one line, as a cell is: its blocks are inline
            parent_tags = {*(parent_tags or ()), "_inline"}
        return str(self._inherited("process_tag")(node, parent_tags))

    def _markup(
        self, el: Tag, text: str, parent_tags: set[str], markers: str, tag: str
    ) -> str:
        """Wrap ``text`` in ``markers``, or in raw ``<tag>`` where they would not close.

        Line breaks and spaces at the edges move outside, where they cannot
        stop the markers closing.
        """

        edges = _EDGES.fullmatch(text)
        if "_noformat" in parent_tags or edges is None or not edges[2]:
            return text
        before, inner, after = edges.groups()
        prev = before[-1:] or str(el.get(_BEFORE) or " ")
        succ = after[:1] or str(el.get(_AFTER) or " ")
        if markers and _flanks(inner, prev, succ):
            return f"{before}{markers}{inner}{markers}{after}"
        return f"{before}<{tag}>{inner}</{tag}>{after}"

    def convert_b(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        return self._markup(el, text, parent_tags, "**", "strong")

    convert_strong = convert_b

    def convert_em(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        return self._markup(el, text, parent_tags, "*", "em")

    convert_i = convert_em

    def convert_s(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        """Struck text: CommonMark has no strikethrough, so always raw ``<s>``."""

        return self._markup(el, text, parent_tags, "", "s")

    convert_del = convert_s
    convert_strike = convert_s

    def convert_u(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        """Underlined or highlighted text: CommonMark has neither, so raw HTML.

        Round a block the tag is dropped and the blocks kept, except on the
        one line of a cell or a heading, where the blocks are inline text.
        """

        if el.has_attr(_HOLDS_BLOCK) and "_inline" not in parent_tags:
            return text
        return self._markup(el, text, parent_tags, "", el.name)

    convert_mark = convert_ins = convert_u

    def convert_center(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        """``<center>``, obsolete, is a block, as ``<div>`` is."""

        if "pre" in parent_tags:
            return text
        return str(self._inherited("convert_div")(el, text, parent_tags))

    def convert_glpi_cell(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        """A cell of a table nested in a cell: its text, set apart by spaces."""

        return f" {text.strip()} "

    def convert_br(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        if "_noformat" in parent_tags:
            return "\n"  # in <pre>, or in inline code, which convert_code splits
        if "td" in parent_tags or "th" in parent_tags:
            return "<br>"  # a cell is one line of Markdown; cmark-gfm passes the tag
        return str(self._inherited("convert_br")(el, text, parent_tags))

    def convert_code(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        """Inline code, a span per line: a code span cannot hold a line break."""

        cell = "td" in parent_tags or "th" in parent_tags
        lines = [text] if "_noformat" in parent_tags else text.split("\n")
        join = "<br>" if cell else " " if "_inline" in parent_tags else "\\\n"
        code = join.join(
            str(self._inherited("convert_code")(el, line, parent_tags))
            for line in lines
        )
        if cell:
            code = code.replace(
                "|", "\\|"
            )  # GFM splits a row on "|" before it reads code
        return code

    convert_kbd = convert_samp = convert_code

    def convert_list(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        """A list; a nested one ends in a blank line.

        Otherwise the item's text after it joins the nested list's last item.
        """

        markdown = str(self._inherited("convert_list")(el, text, parent_tags))
        return markdown + "\n\n" if "li" in parent_tags else markdown

    convert_ul = convert_list
    convert_ol = convert_list

    def convert_li(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        """An item; an ordered one numbered one past the item before it.

        markdownify counts every item before each one, quadratic in a long
        list, so each item keeps its number for the next. ``isdecimal``,
        where markdownify's ``isnumeric`` let ``int("²")`` raise.
        """

        if el.parent is None or el.parent.name != "ol":
            return str(self._inherited("convert_li")(el, text, parent_tags))
        before = el.find_previous_sibling("li")
        start = str(el.parent.get("start") or "")
        first = int(start) if start.isdecimal() else 1
        number = int(str(before[_NUMBER])) + 1 if isinstance(before, Tag) else first
        el[_NUMBER] = str(number)
        if not text.strip():
            return "\n"
        bullet = f"{number}. "
        body = re.sub("^(?=.)", " " * len(bullet), text.strip(), flags=re.M)
        return bullet + body[len(bullet) :] + "\n"

    def convert_pre(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        """A fenced block, its fence longer than any backtick run in the code."""

        markdown = str(self._inherited("convert_pre")(el, text, parent_tags))
        longest = max((len(run) for run in _BACKTICK_RUN.findall(text)), default=0)
        if longest < 3 or markdown.count("```") < 2:
            return markdown
        fence = "`" * (longest + 1)
        head, _, rest = markdown.partition("```")
        body, _, tail = rest.rpartition("```")
        return f"{head}{fence}{body}{fence}{tail}"

    def convert_a(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        """A link; ``<url>`` when its text is its URL and reads back unchanged."""

        href = str(el.get("href") or "")
        edges = _EDGES.fullmatch(text)
        if "_noformat" in parent_tags or not href or edges is None or not edges[2]:
            return text
        before, inner, after = edges.groups()
        title = str(el.get("title") or "")
        if not title and el.get_text() == href and _AUTOLINK.fullmatch(href):
            return f"{before}<{href}>{after}"
        return f"{before}[{inner}]({_destination(href)}{_title(title)}){after}"

    def convert_img(self, el: Tag, text: str, parent_tags: set[str]) -> str:
        """An image, wherever it is: a cell or a heading holds one too."""

        alt = " ".join(str(el.get("alt") or "").split())
        alt = str(self._inherited("escape")(alt, parent_tags))
        if alt.startswith("^") and "_noformat" not in parent_tags:
            alt = "\\" + alt  # cmark-gfm reads "![^" as "!" and a link
        src = _destination(str(el.get("src") or ""))
        return f"![{alt}]({src}{_title(str(el.get('title') or ''))})"


class _Node(RenderTreeNode):
    """mdformat's syntax-tree node, answering in constant time what it asks often.

    mdformat asks every text node for its next sibling, every list for its
    previous one, and every list item whether its list is tight. The base
    class answers each by scanning, which made a long paragraph or a long
    list quadratic.
    """

    _index = -1

    def _position(self) -> int:
        if self._index < 0:
            for index, sibling in enumerate(self.siblings):
                sibling._index = index
        return self._index

    @property
    def next_sibling(self) -> _Node | None:
        siblings = self.siblings
        index = self._position() + 1
        return siblings[index] if index < len(siblings) else None

    @property
    def previous_sibling(self) -> _Node | None:
        index = self._position() - 1
        return self.siblings[index] if index >= 0 else None

    @cached_property
    def tight(self) -> bool:
        """Whether this list is tight: no paragraph in it is shown as one."""

        return all(
            grandchild.hidden
            for child in self.children
            for grandchild in child.children
            if grandchild.type == "paragraph"
        )


def _list_item(node: RenderTreeNode, context: RenderContext) -> str:
    """Render a list item as mdformat does, asking its list's tightness once."""

    separator = "\n" if cast(_Node, node.parent).tight else "\n\n"
    text = separator.join(
        filter(None, (child.render(context) for child in node.children))
    )
    return text if text.strip() else ""


#: ``2k`` backslashes, which mdformat writes for ``k`` literal ones, before a
#: character no backslash escapes. ``2k - 1`` read as the same ``k`` there.
_NEEDLESS_DOUBLING = re.compile(r"(?<!\\)((?:\\\\)+)(?=[^!-/:-@\[-`{-~\\\s])")

#: The ``<`` mdformat leaves bare after one it escaped: its pattern eats the
#: next character, so ``<<a@b.c>`` became ``\<<a@b.c>``, an autolink.
_SECOND_LESS_THAN = re.compile(r"(?<=\\<)<(?=[^ ]|$)")


def _text(node: RenderTreeNode, context: RenderContext) -> str:
    """Render text as mdformat does, less one backslash where it escapes nothing.

    ``C:\\Temp`` stays ``C:\\Temp`` instead of becoming ``C:\\\\Temp``.
    """

    text = DEFAULT_RENDERERS["text"](node, context)
    text = _SECOND_LESS_THAN.sub(r"\\<", text)
    return _NEEDLESS_DOUBLING.sub(lambda found: found.group(1)[:-1], text)


#: A paragraph line opening with ``~~~``, which CommonMark reads as a fence.
_TILDE_FENCE = re.compile("^~~~", re.MULTILINE)


class _Lists:
    """An mdformat extension: linear list items, short text and rules."""

    RENDERERS: Mapping[str, Callable[[RenderTreeNode, RenderContext], str]] = {
        "list_item": _list_item,
        "text": _text,
        "hr": lambda node, context: "---",
    }
    #: What mdformat drops: an escape or entity in an image's alt text, which
    #: markdown-it-py 3 leaves a ``text_special`` token mdformat renders as
    #: nothing, and the escape on a paragraph line opening with ``~~~``.
    POSTPROCESSORS: Mapping[str, Postprocess] = {
        "text_special": lambda text, node, context: node.markup,
        "paragraph": lambda text, node, context: _TILDE_FENCE.sub(r"\\~~~", text),
    }


class _Renderer(MDRenderer):
    """mdformat's renderer, over :class:`_Node`."""

    def render(
        self,
        tokens: Sequence[Token],
        options: Mapping[str, Any],
        env: MutableMapping[Any, Any],
        *,
        finalize: bool = True,
    ) -> str:
        return self.render_tree(_Node(tokens), options, env, finalize=finalize)


class _Parser(MarkdownIt):
    """markdown-it keeping every link: it reformats Markdown, never renders it."""

    def validateLink(self, url: str) -> bool:
        return True


def _formatter() -> MarkdownIt:
    """Return mdformat as ``mdformat.text`` builds it, less what this module cannot use.

    ``mdformat.text`` keeps markdown-it's nesting cap of 20, beyond which the
    parser drops the rest of the block without a word: a list ten deep lost
    its text. The cap is lifted, so a document too deep raises
    ``RecursionError`` instead, which :meth:`GlpiContentConverter.from_transport`
    answers. Link validation is lifted too, or a ``file:`` link read back as
    escaped text.
    """

    parser = _Parser(
        "commonmark",
        {"maxNesting": 1_000_000},
        renderer_cls=cast(Any, _Renderer),
    )
    parser.options["mdformat"] = {
        "wrap": "keep",
        "number": True,
        "compact_tables": True,
    }
    parser.options["store_labels"] = True
    parser.options["parser_extension"] = [mdformat_tables, _Lists]
    parser.options["codeformatters"] = {}
    mdformat_tables.update_mdit(parser)
    return parser


# The shared objects keep no state between calls: markdownify fills a
# per-tag cache of its own methods, the same on every thread, and markdown-it
# and cmark-gfm parse into fresh state. What they set up once -- markdown-it's
# rule chains, cmark-gfm's extension registry, which has no lock -- is set up
# here, under the import lock, before any thread can race for it.
_CONVERTER = _Converter(**_MARKDOWNIFY_OPTIONS)
_FORMATTER = _formatter()
_FORMATTER.render("*warm* [up](x)\n\n- a\n\n| a |\n| - |")
cmarkgfm.cmark.core_extensions_ensure_registered()


def html_to_markdown(html: str) -> str:
    """Convert HTML to Markdown that cmark-gfm renders as the same display.

    Needs ``beautifulsoup4`` 4.15 or later: before it, a ``<br />`` in a body
    that also held a bare ``<br>`` swallowed the text after it.

    Raises
    ------
    RecursionError
        ``markdownify`` or mdformat recursed deeper than the stack left.
    """

    soup = _soup(html)
    _flatten_nested_tables(soup)
    _drop_trailing_breaks(soup)
    _note_sides(soup)
    _note_blocks(soup)
    return str(_FORMATTER.render(_CONVERTER.convert_soup(soup))).strip()


def markdown_to_html(markdown: str) -> str:
    """Render Markdown as HTML: CommonMark with GFM tables, through cmark-gfm."""

    html: str = cmarkgfm.markdown_to_html_with_extensions(
        markdown, options=_RENDER_OPTIONS, extensions=["table"]
    )
    return html.strip()


def _text_of(html: str) -> str:
    """Return the text ``html`` displays, a line per block, without recursing."""

    pieces: list[str] = []
    for node, _ in _walk(_soup(html)):
        if not isinstance(node, Tag):
            pieces.append(str(node))
        elif node.name in _BLOCKS or node.name == "br":
            pieces.append("\n")
    lines = (" ".join(line.split()) for line in "".join(pieces).split("\n"))
    return "\n".join(line for line in lines if line)


class GlpiContentConverter:
    """Convert content between GLPI HTML payloads and canonical Markdown."""

    @staticmethod
    def from_transport(value: object, *, plain_text_is_markdown: bool = False) -> str:
        """Convert one GLPI transport value into Markdown.

        Parameters
        ----------
        value : object
            HTML, or plain text: a value with no HTML element in it.
        plain_text_is_markdown : bool, optional
            How a value that is not an HTML document is read. ``False``, the
            read path, reads plain text as GLPI displays it -- literal
            characters, one line per line -- so ``__init__`` comes back
            escaped. ``True`` is the write models' validator: the value is
            the caller's own Markdown and passes through, stripped, unless
            it starts with ``<`` and holds a real HTML element anywhere. So
            Markdown carrying an inline ``<br>`` or ``<kbd>`` is still
            Markdown, but Markdown that opens with an autolink or other
            angle-bracketed text and carries inline HTML further on is read
            as HTML, and loses that autolink.

        Returns
        -------
        str
            The Markdown, stripped; empty for an empty value.

        Raises
        ------
        GlpiContentError
            The value could not be converted. A body nested too deeply for
            the stack left, or on which the conversion raises
            ``ValueError`` (a ``colspan`` or ``start`` markdownify cannot
            read as a number, among others), is read as its text instead,
            so this is a backstop.
        RecursionError
            Only when called from within a few frames of the recursion
            limit, where no stack is left even to report the failure as
            ``GlpiContentError`` (the user guide gives the measured
            depths).
        """

        content = str(value or "").strip()
        if not content:
            return ""
        if plain_text_is_markdown and not (
            content.startswith("<") and _looks_like_html(content)
        ):
            return content
        if not _looks_like_html(content):
            content = _plain_text_html(content)
        # No "<" after the last ">" can finish a tag; CPython's html.parser before
        # 3.11.14/3.12.12/3.13.6 rescans to the end for each (quadratic).
        head, end, tail = content.rpartition(">")
        content = head + end + tail.replace("<", "&lt;")
        try:
            try:
                return html_to_markdown(content)
            except (RecursionError, ValueError):  # ValueError: markdownify's
                # int() of a colspan or start such as "²" or 5,000 digits
                return html_to_markdown(_plain_text_html(_text_of(content)))
            except ParserRejectedMarkup:
                # html.parser gives up on a few malformed declarations; the
                # body's words are still worth more than an exception.
                text = unescape(_ANY_TAG.sub(" ", content))
                return html_to_markdown(_plain_text_html(" ".join(text.split())))
        except Exception as exc:
            raise GlpiContentError(
                "Could not convert GLPI HTML content to Markdown "
                f"({type(exc).__name__}: {exc})."
            ) from exc

    @staticmethod
    def to_transport(value: object) -> str:
        """Convert one Markdown value into GLPI HTML.

        Raises
        ------
        GlpiContentError
            The Markdown could not be rendered.
        """

        markdown = str(value or "")
        if not markdown.strip():
            return ""
        try:
            return markdown_to_html(markdown)
        except Exception as exc:
            raise GlpiContentError(
                "Could not render Markdown content as GLPI HTML "
                f"({type(exc).__name__}: {exc})."
            ) from exc
