"""GLPI ``/Administration/Group`` mixin.

The mixin exposes search, fetch, create, update, and delete helpers for the
GLPI group resource. Every call sends the client's ``GLPI-Entity`` header
(and the profile and recursion headers that travel with it) except where a
search is told to skip it with ``skip_entity=True``.
"""

from __future__ import annotations

from collections.abc import Iterator

from glpi_python_client._sync.clients.commons._constants import GROUP_ENDPOINT, GlpiId
from glpi_python_client._sync.clients.commons._payloads import (
    ensure_v1_write_accepted,
)
from glpi_python_client._sync.clients.commons._transport import TransportMixin
from glpi_python_client.models.api_schema.administration._group import (
    DeleteGroup,
    GetGroup,
    PatchGroup,
    PostGroup,
)

_V1_GROUP_FEATURE_LABEL = "group recursion"


class GroupMixin(TransportMixin):
    """CRUD helpers for ``/Administration/Group``."""

    def search_groups(
        self,
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        skip_entity: bool = False,
    ) -> list[GetGroup]:
        """Search GLPI groups with an optional RSQL filter.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter,
            for example ``"name==Support"``. Empty by default.
        limit : int, optional
            Maximum number of records returned by the GLPI server.
        start : int, optional
            Zero-based offset of the first record returned.
        skip_entity : bool, optional
            When ``True`` the ``GLPI-Entity`` header is omitted so the
            search spans every entity the caller has access to.

        Returns
        -------
        list[GetGroup]
            Groups matching the filter.
        """

        params: dict[str, object] = {"limit": limit, "start": start}
        if rsql_filter:
            params["filter"] = rsql_filter
        return self._resource_list(
            GROUP_ENDPOINT, GetGroup, params=params, skip_entity=skip_entity
        )

    def iter_search_groups(
        self,
        rsql_filter: str = "",
        *,
        batch_size: int = 50,
        skip_entity: bool = False,
    ) -> Iterator[list[GetGroup]]:
        """Yield successive pages of GLPI groups until exhausted.

        Pagination advances the ``start`` offset after each batch and stops
        when the server returns fewer items than ``batch_size``.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter.
        batch_size : int, optional
            Number of records requested per page (default 50).
        skip_entity : bool, optional
            When ``True`` the ``GLPI-Entity`` header is omitted so the
            search spans every entity the caller has access to.

        Yields
        ------
        list[GetGroup]
            One page of groups per iteration. The last yielded batch may
            be shorter than ``batch_size``.
        """

        start = 0
        while True:
            batch = self.search_groups(
                rsql_filter,
                limit=batch_size,
                start=start,
                skip_entity=skip_entity,
            )
            if batch:
                yield batch
            if len(batch) < batch_size:
                break
            start += batch_size

    def get_group(self, group_id: GlpiId) -> GetGroup:
        """Fetch one GLPI group by identifier.

        Parameters
        ----------
        group_id : GlpiId
            Numeric identifier of the group to retrieve.

        Returns
        -------
        GetGroup
            Validated group payload.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        return self._resource_get(
            f"{GROUP_ENDPOINT}/{group_id}",
            GetGroup,
            failure_message=f"Failed to get group {group_id}",
        )

    def create_group(self, group: PostGroup) -> int:
        """Create one GLPI group.

        Parameters
        ----------
        group : PostGroup
            Request body describing the group to create.

        Returns
        -------
        int
            Identifier assigned by the GLPI server.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        GlpiProtocolError
            If the create response is missing the ``id`` field.
        """

        return self._resource_create(
            GROUP_ENDPOINT,
            group,
            failure_message="Failed to create group",
            missing_message="GLPI group create response did not include an ID",
            log_message_factory=lambda new_id: f"GLPI API created group {new_id}",
        )

    def update_group(self, group_id: GlpiId, group: PatchGroup) -> None:
        """Update one GLPI group with a partial body.

        Parameters
        ----------
        group_id : GlpiId
            Numeric identifier of the group to update.
        group : PatchGroup
            Partial request body.

        Returns
        -------
        None

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        self._resource_update(
            f"{GROUP_ENDPOINT}/{group_id}",
            group,
            failure_message=f"Failed to update group {group_id}",
            log_message=f"GLPI API updated group {group_id}",
        )

    def delete_group(
        self, group_id: GlpiId, *, force: bool | None = None
    ) -> None:
        """Delete one GLPI group by identifier.

        Parameters
        ----------
        group_id : GlpiId
            Numeric identifier of the group to delete.
        force : bool | None, optional
            When ``True`` the group is permanently deleted instead of
            being moved to the trash.

        Returns
        -------
        None

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        self._resource_delete(
            f"{GROUP_ENDPOINT}/{group_id}",
            failure_message=f"Failed to delete group {group_id}",
            log_message=f"GLPI API deleted group {group_id}",
            force=force,
            delete_model_cls=DeleteGroup,
        )

    def set_group_recursive(
        self, group_id: GlpiId, recursive: bool = True
    ) -> None:
        """Set whether one group is visible in the sub-entities of its entity.

        The GLPI v2 ``Group`` schema has no ``is_recursive`` property (a v2
        create or update silently drops the key), so this helper writes the
        flag through the legacy v1 API, which requires
        ``v1_base_url``/``v1_user_token`` to be configured (pointing at the
        legacy ``apirest.php``).

        Parameters
        ----------
        group_id : int | str
            Identifier of the group.
        recursive : bool, optional
            ``True`` (the default) makes the group apply to the sub-entities
            of its entity; ``False`` restricts it to its own entity.

        Raises
        ------
        RuntimeError
            When no legacy v1 session is configured on the client.
        GlpiStatusError
            When the legacy API returns a non-success status.
        GlpiProtocolError
            When the legacy API answers that the update was refused.
        """

        v1 = self._require_v1_session(_V1_GROUP_FEATURE_LABEL)
        payload = v1.request_json(
            "PUT",
            f"Group/{group_id}",
            json_body={"input": {"id": int(group_id), "is_recursive": int(recursive)}},
            failure_message=f"Failed to set is_recursive on group {group_id}",
        )
        ensure_v1_write_accepted(payload, f"Setting is_recursive on group {group_id}")


__all__ = ["GroupMixin"]
