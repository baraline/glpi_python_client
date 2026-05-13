"""Shared helper functions for rich ticket normalization.

This module contains small model-normalization helpers used by the richer GLPI
objects when they accept either typed models or plain mappings.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def _model_data(value: object) -> dict[str, Any]:
    """Normalize one model-like value to a plain mapping.

    Parameters
    ----------
    value : object
        Model-like value to normalize.

    Returns
    -------
    dict[str, Any]
        Plain mapping representation of the value.

    Raises
    ------
    TypeError
        Raised when the value is neither a Pydantic model nor a mapping.
    """

    if isinstance(value, BaseModel):
        return value.model_dump(mode="python")
    if isinstance(value, dict):
        return dict(value)
    raise TypeError(f"Unsupported model value {type(value)!r}")
