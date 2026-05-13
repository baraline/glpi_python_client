from __future__ import annotations

from glpi_python_client.content.conversion import GlpiContentConverter


def test_content_converter_uses_markdown_in_python_and_html_for_glpi() -> None:
    markdown = GlpiContentConverter.from_transport(
        "<p>Hello <strong>world</strong></p>"
    )
    html = GlpiContentConverter.to_transport("Hello **world**")

    assert markdown == "Hello **world**"
    assert html == "<p>Hello <strong>world</strong></p>"
