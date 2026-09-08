"""Annotated content types for transparent Markdown/HTML transport handling.

GLPI exchanges rich-text fields (ticket ``content``, followup ``content``,
task ``content``, solution ``content``, ...) over the wire as HTML
(``format: html`` in the OpenAPI contract), while the public package
surface is Markdown: a caller never has to author HTML, and reading
``.content`` on any model gives Markdown back. The annotated types here
wire :class:`glpi_python_client.content.conversion.GlpiContentConverter`
into Pydantic to make that so, and they are deliberately not symmetric.

**Write models** (``Post*``, ``Patch*``) use :data:`GlpiMarkdownContent`,
which converts eagerly:

* On validation the caller's Markdown is normalised, so it is checked at
  the point the caller supplied it rather than somewhere later.
* On serialisation (outgoing request bodies built via
  :func:`glpi_python_client._sync.clients.commons._payloads.model_to_payload`)
  the Markdown value is rendered back to HTML so GLPI receives the format
  it expects.

**Read models** (``Get*``) use :data:`GlpiRawContent` or
:data:`GlpiRawDescription` on a field named ``content_html`` /
``description_html``, which holds exactly what GLPI sent and converts
nothing. Each read model pairs that field with a ``cached_property`` --
``content``, ``description`` -- that converts on first access and caches
the result, over :func:`markdown_view`.

The asymmetry is the point. Conversion used to run inside the Pydantic
validator, which cost two things a caller could not opt out of:

* **A list read converted every body.** Someone who wanted only ``id``
  and ``date_mod`` still paid HTML-to-Markdown on every record of every
  page.
* **A failure took its page-mates with it.**
  ``TransportMixin._resource_list`` builds every item of a page in one
  comprehension, so one unconvertible body made the whole page
  unreadable. Conversion now happens at the attribute, so whatever can go
  wrong is scoped to the attribute.

The field keeps ``content`` as a validation alias, so a GLPI payload and a
hand-written ``GetTicket(content=...)`` both still populate it -- which is
why :class:`glpi_python_client.models._base.GlpiModel` has to know about
aliases when it captures unknown keys: that validator runs *before*
Pydantic resolves them, and would otherwise divert the wire's ``content``
into ``extra_payload``.

Plain-text content is preserved verbatim on the inbound path and rendered
as HTML paragraphs on the outbound path, matching the converter's default
behaviour. "Plain text" means text carrying no recognised HTML element:
``use the <Enter> key`` and ``if x<y then z>0`` are text, because ``Enter``
and ``y`` are not elements, while ``a<b>c`` is treated as markup because
``b`` is. ``None`` values are passed through unchanged so optional fields
and ``exclude_none`` semantics keep working.

Note that the inbound converter also runs on **outbound** content: the
``BeforeValidator`` below fires when a caller constructs a ``Post*`` model,
so caller-authored Markdown passes through it before the serializer renders
it. That is why the plain-text path has to stay verbatim -- routing Markdown
through the HTML normaliser escapes it, and GLPI receives literal asterisks.

One sharp edge comes with the read side, from ``functools.cached_property``:
assigning to ``content_html`` after ``content`` has been read leaves the
cached Markdown in place, and so does
``model_copy(update={"content_html": ...})``. Neither equality, ``repr``
nor any ``model_dump`` shows it. Treat a read model as immutable once
validated; if something really must rewrite the raw value, drop the cache
with ``obj.__dict__.pop("content", None)`` or rebuild the model through
``model_validate``.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import AliasChoices, BeforeValidator, Field, PlainSerializer

from glpi_python_client.content.conversion import GlpiContentConverter


def _from_transport(value: object) -> str | None:
    """Normalise a content value supplied to a write model into Markdown.

    Pydantic invokes this before validation, so the field type stays ``str``
    while the caller-visible value is always Markdown. ``None`` is preserved
    unchanged so optional content fields keep their tri-state semantics.

    Only write models still normalise on validation; a read model stores
    what GLPI sent and converts at the attribute instead, through
    :func:`markdown_view`.
    """

    if value is None:
        return None
    return GlpiContentConverter.from_transport(value)


def markdown_view(raw: str | None) -> str | None:
    """Convert one stored raw transport value into Markdown.

    The body of every ``content`` / ``description`` ``cached_property`` on
    the read models. It is a plain function rather than a method so the
    seven properties share one implementation while each keeps its own
    docstring and its own cache slot.

    ``None`` passes through, so a field GLPI never sent reads back as
    ``None`` rather than as an empty string.

    Parameters
    ----------
    raw : str or None
        The raw transport value as stored, normally HTML.

    Returns
    -------
    str or None
        Canonical Markdown, or ``None``.

    Raises
    ------
    GlpiContentError
        The value could not be converted. Content nested past
        :data:`glpi_python_client.content.conversion.MAX_HTML_DEPTH` is
        degraded to text instead, so this is a backstop rather than an
        expected outcome -- but note that it surfaces from the attribute
        read, not from ``model_validate``, which is the deliberate
        difference from the write-model path.
    """

    if raw is None:
        return None
    return GlpiContentConverter.from_transport(raw)


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

Use this annotation on a **write** model field that maps to a GLPI
``format: html`` content slot (ticket descriptions, followup bodies, task
bodies, solution bodies). The conversion is invisible to package users: the
field accepts Markdown on construction, exposes Markdown on attribute
access, and emits HTML on serialisation.

A read model wants :data:`GlpiRawContent` instead, and a
``cached_property`` beside it. See the module docstring for why the two
directions differ.
"""

GlpiRawContent = Annotated[
    str | None,
    Field(
        validation_alias=AliasChoices("content", "content_html"),
        serialization_alias="content",
    ),
]
"""Annotated ``str | None`` holding one raw GLPI ``content`` value, unconverted.

Use this on a **read** model field named ``content_html``, paired with a
``content`` ``cached_property`` over :func:`markdown_view`. Nothing is
converted on validation, so building a page of records costs nothing per
body and no body can spoil another.

The validation alias accepts both spellings, so a GLPI payload
(``content``) and a hand-written ``GetTicket(content_html=...)`` both
populate the field. The name must be listed in the alias alongside the
wire key: a bare ``validation_alias="content"`` would silently divert
by-name construction into ``extra_payload`` rather than raising, because
the base model allows extra keys.
"""

GlpiRawDescription = Annotated[
    str | None,
    Field(
        validation_alias=AliasChoices("description", "description_html"),
        serialization_alias="description",
    ),
]
""":data:`GlpiRawContent` for the second content slot on a knowledge-base article.

``KBArticle`` carries both ``content`` and ``description`` as
``format: html``, and an alias names one wire key, so the two need
separate annotations.
"""

__all__ = [
    "GlpiMarkdownContent",
    "GlpiRawContent",
    "GlpiRawDescription",
    "markdown_view",
]
