"""Annotated content types for transparent Markdown/HTML transport handling.

GLPI exchanges rich-text fields (ticket ``content``, followup ``content``,
task ``content``, solution ``content``, ...) over the wire as HTML
(``format: html`` in the OpenAPI contract), but the public package surface
is intentionally Markdown-only: callers should never need to author or read
HTML. The annotated type defined here wires
:class:`glpi_python_client.content.conversion.GlpiContentConverter` into
Pydantic so the conversion happens transparently on every model boundary:

* On validation (incoming HTML payloads from GLPI) the value is normalised
  to canonical Markdown before being assigned to the field, so attribute
  access always returns Markdown.
* On serialisation (outgoing request bodies built via
  :func:`glpi_python_client.clients.commons._payloads.model_to_payload`)
  the Markdown value is rendered back to HTML so GLPI receives the format
  it expects.

Plain-text content (no ``<...>`` markup) is preserved verbatim on the
inbound path and rendered as HTML paragraphs on the outbound path, matching
the converter's default behaviour. ``None`` values are passed through
unchanged so optional fields and ``exclude_none`` semantics keep working.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator, PlainSerializer

from glpi_python_client.content.conversion import GlpiContentConverter


def _from_transport(value: object) -> str | None:
    """Normalise an inbound GLPI content value into canonical Markdown.

    Pydantic invokes this before validation, so the field type stays ``str``
    while the caller-visible value is always Markdown. ``None`` is preserved
    unchanged so optional content fields keep their tri-state semantics.
    """

    if value is None:
        return None
    return GlpiContentConverter.from_transport(value)


def _to_transport(value: str | None) -> str | None:
    """Render an outbound Markdown content value as the HTML GLPI expects.

    ``None`` is preserved so ``model_dump(exclude_none=True)`` continues to
    drop unset fields from request bodies. Empty Markdown is rendered as an
    empty string to stay consistent with the inbound converter behaviour.
    """

    if value is None:
        return None
    return GlpiContentConverter.to_transport(value)


GlpiMarkdownContent = Annotated[
    str | None,
    BeforeValidator(_from_transport),
    PlainSerializer(_to_transport, return_type=str | None, when_used="always"),
]
"""Annotated ``str | None`` that round-trips Markdown through GLPI's HTML wire format.

Use this annotation on every model field that maps to a GLPI ``format: html``
content slot (ticket descriptions, followup bodies, task bodies, solution
bodies). The conversion is invisible to package users: the field accepts
Markdown on construction, exposes Markdown on attribute access, and emits
HTML on serialisation.
"""

__all__ = ["GlpiMarkdownContent"]
