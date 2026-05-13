"""Base model contracts for GLPI data objects.

This module defines the common Pydantic base class used by the package's typed
GLPI models.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class GlpiModel(BaseModel):
    """Base class for field-validated GLPI data models.

    The shared base model forbids undeclared fields and exposes ``extra_payload``
    so instance-specific API extensions can still be forwarded intentionally.
    """

    model_config = ConfigDict(extra="forbid")
    extra_payload: dict[str, Any] = Field(default_factory=dict)
