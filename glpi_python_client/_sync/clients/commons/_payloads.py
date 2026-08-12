"""Pydantic helpers shared by the per-endpoint mixins.

The helpers convert :class:`glpi_python_client.models._base.GlpiModel`
instances into the JSON request bodies expected by the GLPI API and back
again, while honouring the per-model ``extra_payload`` escape hatch.
"""

from __future__ import annotations

from typing import TypeVar

from glpi_python_client.models._base import GlpiModel

ModelT = TypeVar("ModelT", bound=GlpiModel)


def model_to_payload(model: GlpiModel) -> dict[str, object]:
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
    """

    body = model.model_dump(mode="json", exclude_none=True, exclude={"extra_payload"})
    if model.extra_payload:
        body.update(model.extra_payload)
    return body


def model_from_payload(model_class: type[ModelT], payload: object) -> ModelT:
    """Validate one raw GLPI payload into the requested ``GlpiModel`` class.

    The helper is a thin wrapper around ``model_validate`` that keeps the
    mixin call sites concise and consistent with :func:`model_to_payload`.
    """

    return model_class.model_validate(payload)


__all__ = ["model_from_payload", "model_to_payload"]
