from __future__ import annotations

from glpi_python_client import GlpiSolution


def test_solution_payload_renders_markdown_to_html() -> None:
    solution = GlpiSolution(content="Rebooted and **validated**")

    assert solution.to_api_payload()["content"] == (
        "<p>Rebooted and <strong>validated</strong></p>"
    )
