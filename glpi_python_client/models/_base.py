"""Base model contracts for GLPI data objects.

This module defines the common Pydantic base class used by the package's typed
GLPI models.

Notes
-----
The base relaxes Pydantic's ``extra="forbid"`` policy because the live GLPI
v2 server consistently returns helper fields (``href``, ``display_name``,
``firstname``, ``realname``, ``completename``, ...) that are absent from the
OpenAPI contract. Per the project rule that real behaviour wins over the
contract, undeclared fields are accepted and funnelled into the existing
``extra_payload`` escape hatch instead of raising. ``extra_payload`` keys
provided explicitly by callers still take precedence on serialisation.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GlpiModel(BaseModel):
    """Base class for field-validated GLPI data models.

    The shared base model accepts undeclared fields and routes them into
    the explicit ``extra_payload`` mapping, so instance-specific API
    extensions can still be inspected or forwarded intentionally.
    """

    model_config = ConfigDict(extra="allow")
    extra_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _capture_unknown_fields(cls, data: Any) -> Any:
        """Funnel unknown payload keys into ``extra_payload``.

        The validator only runs when ``data`` is a mapping. Keys that are
        not declared as fields on the concrete subclass (and are not the
        ``extra_payload`` meta field itself) are removed from the incoming
        mapping and merged into the ``extra_payload`` mapping. Any keys the
        caller already placed in ``extra_payload`` win on conflicts.
        """

        if not isinstance(data, dict):
            return data
        known = set(cls.model_fields.keys())
        existing_extras = data.get("extra_payload")
        captured: dict[str, Any] = {}
        for key in list(data.keys()):
            if key in known:
                continue
            captured[key] = data.pop(key)
        if captured:
            merged = dict(captured)
            if isinstance(existing_extras, dict):
                merged.update(existing_extras)
            data["extra_payload"] = merged
        return data
