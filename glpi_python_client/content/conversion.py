"""Content conversion helpers for GLPI payloads.

This module translates between GLPI's HTML transport format and the package's
canonical Markdown representation used by the rich content models.
"""

from __future__ import annotations

from markdown import markdown as markdown_to_html
from markdownify import markdownify as html_to_markdown


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
        """

        content = str(value or "")
        if not content.strip():
            return ""
        if "<" not in content or ">" not in content:
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
