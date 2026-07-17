"""Synchronous GLPI ``/Knowledgebase/Category`` mixin.

The mixin exposes search, fetch, create, update, and delete helpers for the
GLPI knowledge base category resource using the contract-aligned
``api_schema`` models.
"""

from __future__ import annotations

from glpi_python_client.clients.commons._constants import (
    KB_CATEGORY_ENDPOINT,
    GlpiId,
)
from glpi_python_client.clients.commons._transport import TransportMixin
from glpi_python_client.models.api_schema.knowledgebase._category import (
    DeleteKBCategory,
    GetKBCategory,
    PatchKBCategory,
    PostKBCategory,
)


class KBCategoryMixin(TransportMixin):
    """Synchronous CRUD helpers for ``/Knowledgebase/Category``."""

    def search_kb_categories(
        self,
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
        language: str | None = None,
    ) -> list[GetKBCategory]:
        """Search GLPI knowledge base categories with an optional RSQL filter.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter.
        limit : int, optional
            Maximum number of records returned by the GLPI server.
        start : int, optional
            Zero-based offset of the first record returned.
        sort : str | None, optional
            ``sort`` query parameter forwarded as-is, e.g. ``"name asc"``.
        language : str | None, optional
            GLPI language code forwarded as the ``language`` query
            parameter to select a translated view.

        Returns
        -------
        list[GetKBCategory]
            Categories matching the filter.
        """

        params: dict[str, object] = {"limit": limit, "start": start}
        if rsql_filter:
            params["filter"] = rsql_filter
        if sort:
            params["sort"] = sort
        if language:
            params["language"] = language
        return self._resource_list(KB_CATEGORY_ENDPOINT, GetKBCategory, params=params)

    def get_kb_category(self, category_id: GlpiId) -> GetKBCategory:
        """Fetch one knowledge base category by identifier.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        return self._resource_get(
            f"{KB_CATEGORY_ENDPOINT}/{category_id}",
            GetKBCategory,
            failure_message=f"Failed to get KB category {category_id}",
        )

    def create_kb_category(self, category: PostKBCategory) -> int:
        """Create one knowledge base category and return its new identifier."""

        return self._resource_create(
            KB_CATEGORY_ENDPOINT,
            category,
            failure_message="Failed to create KB category",
            missing_message="GLPI KB category create response did not include an ID",
            log_message_factory=lambda new_id: f"GLPI API created KB category {new_id}",
        )

    def update_kb_category(
        self, category_id: GlpiId, category: PatchKBCategory
    ) -> None:
        """Update one knowledge base category with a partial body."""

        self._resource_update(
            f"{KB_CATEGORY_ENDPOINT}/{category_id}",
            category,
            failure_message=f"Failed to update KB category {category_id}",
            log_message=f"GLPI API updated KB category {category_id}",
        )

    def delete_kb_category(
        self, category_id: GlpiId, *, force: bool | None = None
    ) -> None:
        """Delete one knowledge base category by identifier."""

        self._resource_delete(
            f"{KB_CATEGORY_ENDPOINT}/{category_id}",
            failure_message=f"Failed to delete KB category {category_id}",
            log_message=f"GLPI API deleted KB category {category_id}",
            force=force,
            delete_model_cls=DeleteKBCategory,
        )


__all__ = ["KBCategoryMixin"]
