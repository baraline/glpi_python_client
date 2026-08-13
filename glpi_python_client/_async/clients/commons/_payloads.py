"""Pydantic helpers shared by the per-endpoint mixins.

The helpers convert :class:`glpi_python_client.models._base.GlpiModel`
instances into the JSON request bodies expected by the GLPI API and back
again, while honouring the per-model ``extra_payload`` escape hatch.
"""

from __future__ import annotations

from datetime import tzinfo
from typing import TypeVar

from glpi_python_client.models._base import (
    SERVER_TIMEZONE_CONTEXT_KEY,
    GlpiModel,
)

ModelT = TypeVar("ModelT", bound=GlpiModel)


def model_to_payload(
    model: GlpiModel,
    *,
    server_timezone: tzinfo | None = None,
) -> dict[str, object]:
    """Serialise one :class:`GlpiModel` into a request body.

    ``None`` fields are omitted, the meta ``extra_payload`` field is
    excluded from the dump, and any user-provided ``extra_payload`` keys are
    merged on top so callers can inject contract-validated extras the
    package does not yet model.

    The dump runs in JSON mode. The returned mapping is handed to the HTTP
    library as a JSON body, and its encoder is :func:`json.dumps`, which
    cannot represent a ``datetime`` -- python mode leaves those as live
    objects and every write of a date field then fails at the encoder, past
    the point any transport stub can see. JSON mode renders them as ISO-8601
    strings instead, so what the model validated is what GLPI receives.

    ``server_timezone`` is passed as a Pydantic serialisation context, the
    mirror of the validation context in :func:`model_from_payload` and
    threaded the same way, so it reaches nested submodels. It is needed
    because JSON mode alone renders an aware datetime *with* its offset, and
    GLPI 11 does not read that offset: it takes the naive prefix, interprets
    it in the server's own timezone, and discards the rest -- measured across
    offsets from ``-08:00`` to ``+14:00``, which all stored the same moment.
    The context lets the value be converted onto that clock first -- see
    :meth:`GlpiModel._render_datetimes_on_the_server_clock`. ``None``
    converts nothing, so a model dumped outside the client is unchanged.
    """

    context = (
        {SERVER_TIMEZONE_CONTEXT_KEY: server_timezone}
        if server_timezone is not None
        else None
    )
    body = model.model_dump(
        mode="json",
        exclude_none=True,
        exclude={"extra_payload"},
        context=context,
    )
    if model.extra_payload:
        body.update(model.extra_payload)
    return body


def model_from_payload(
    model_class: type[ModelT],
    payload: object,
    *,
    server_timezone: tzinfo | None = None,
) -> ModelT:
    """Validate one raw GLPI payload into the requested ``GlpiModel`` class.

    The helper wraps ``model_validate`` so the mixin call sites stay concise
    and consistent with :func:`model_to_payload`, and so the server timezone
    is threaded through one place instead of forty field declarations.

    ``server_timezone`` is passed as a Pydantic validation context, which
    reaches nested submodels as well as the top-level one -- necessary
    because the timestamps GLPI sends without an offset are nested
    (``KBArticle.revisions[].date``). ``None`` supplies no context at all,
    so naive values stay naive rather than being stamped with a guess.
    """

    context = (
        {SERVER_TIMEZONE_CONTEXT_KEY: server_timezone}
        if server_timezone is not None
        else None
    )
    return model_class.model_validate(payload, context=context)


__all__ = ["model_from_payload", "model_to_payload"]
