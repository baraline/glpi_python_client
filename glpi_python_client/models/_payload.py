"""Shared API payload serialization helpers for rich ticket objects.

These helpers keep payload cleanup and the uniform payload entrypoint in one
place for all models that can be sent back to GLPI.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any


def drop_empty_payload_values(payload: Mapping[str, object]) -> dict[str, object]:
    """Return a payload without empty values that GLPI should not receive.

    ``None``, empty mappings, and empty sequences are removed so outgoing API
    payloads stay concise and avoid sending meaningless placeholders to GLPI.
    """

    return {
        key: value
        for key, value in payload.items()
        if value is not None and value != {} and value != []
    }


class ApiPayloadMixin(ABC):
    """Mixin exposing one uniform API payload entrypoint.

    Notes
    -----
    Subclasses must implement ``_build_api_payload`` with the keyword
    arguments they require. The public ``to_api_payload`` method remains the
    shared entrypoint used by transport clients.
    """

    def to_api_payload(self, *args: Any, **kwargs: Any) -> dict[str, object]:
        """Return the raw API payload for the model.

        Parameters
        ----------
        *args : object
            Positional arguments forwarded to the payload builder.
        **kwargs : object
            Keyword arguments forwarded to the payload builder.

        Returns
        -------
        dict[str, object]
            Raw API payload.
        """

        payload = dict(self._build_api_payload(*args, **kwargs))
        extra_payload = getattr(self, "extra_payload", None)
        if not isinstance(extra_payload, Mapping) or not extra_payload:
            return payload

        merged_payload = dict(payload)
        merged_payload.update(drop_empty_payload_values(extra_payload))
        return drop_empty_payload_values(merged_payload)

    @abstractmethod
    def _build_api_payload(self, *args: Any, **kwargs: Any) -> Mapping[str, object]:
        """Build the raw API payload for the concrete model.

        Parameters
        ----------
        *args : object
            Positional arguments supplied by the caller.
        **kwargs : object
            Keyword arguments supplied by the caller.

        Returns
        -------
        dict[str, object]
            Raw API payload.

        """
