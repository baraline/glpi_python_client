"""Content conversion helpers for GLPI payloads.

This module translates between GLPI's HTML transport format and the package's
canonical Markdown representation used by the rich content models.
"""

from __future__ import annotations

import re

from markdown import markdown as markdown_to_html
from markdownify import markdownify as html_to_markdown

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

#: One candidate tag: ``<`` or ``</`` immediately followed by a name.
#:
#: The ``<`` must abut the name, matching what an HTML parser accepts. That
#: is what keeps ``2 < 3 > 1`` and ``x <= y`` text: a space after ``<``
#: means no tag, so arithmetic never reaches the HTML path in the first
#: place.
_CANDIDATE_TAG = re.compile(r"</?([a-zA-Z][a-zA-Z0-9]*)\b[^<>]*>")


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
        """

        content = str(value or "")
        if not content.strip():
            return ""
        if not _looks_like_html(content):
            return content.strip()

        markdown = html_to_markdown(
            content,
            heading_style="ATX",
            bullets="-",
            strip=["script", "style"],
        )
        return str(markdown).strip()

    @staticmethod
    def to_transport(value: object) -> str:
        """Convert one canonical Markdown value into GLPI HTML.

        Empty Markdown stays empty, while non-empty content is rendered through
        the configured Markdown extensions used by the package.
        """

        markdown = str(value or "")
        if not markdown.strip():
            return ""
        html = markdown_to_html(
            markdown,
            extensions=["nl2br", "sane_lists"],
            output_format="html5",
        )
        return str(html).strip()
