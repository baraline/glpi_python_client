"""GLPI ``/Assets/Computer`` mixin.

The mixin exposes search, fetch, create, update, and delete helpers for the
GLPI computer resource using the contract-aligned ``api_schema`` models.
"""

from __future__ import annotations

from collections.abc import Iterator

from glpi_python_client._sync.clients.commons._constants import (
    COMPUTER_ENDPOINT,
    GlpiId,
)
from glpi_python_client._sync.clients.commons._transport import TransportMixin
from glpi_python_client.models.api_schema.assets._computer import (
    DeleteComputer,
    GetComputer,
    PatchComputer,
    PostComputer,
)


class ComputerMixin(TransportMixin):
    """CRUD helpers for ``/Assets/Computer``."""

    def search_computers(
        self,
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
    ) -> list[GetComputer]:
        """Search GLPI computers with an optional RSQL filter.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter.
        limit : int, optional
            Maximum number of records returned by the GLPI server.
        start : int, optional
            Zero-based offset of the first record returned.
        sort : str | None, optional
            Server-side ordering expressed as ``"<field>:<direction>"``,
            for example ``"date_mod:desc"``. Omitted when :data:`None`,
            leaving the server default ordering in place.

        Returns
        -------
        list[GetComputer]
            Computers matching the filter.
        """

        params: dict[str, object] = {"limit": limit, "start": start}
        if rsql_filter:
            params["filter"] = rsql_filter
        if sort is not None:
            params["sort"] = sort
        return self._resource_list(COMPUTER_ENDPOINT, GetComputer, params=params)

    def iter_search_computers(
        self,
        rsql_filter: str = "",
        *,
        batch_size: int = 50,
        sort: str | None = None,
    ) -> Iterator[list[GetComputer]]:
        """Yield successive pages of GLPI computers until exhausted.

        The generator drives pagination automatically by advancing the
        ``start`` offset after each batch. Iteration stops when the server
        returns fewer items than ``batch_size``, which signals the last page.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter.
            Empty by default, which lists every visible record.
        batch_size : int, optional
            Number of records requested per page (default 50). Acts as the
            ``limit`` parameter on each underlying :meth:`search_computers`
            call.
        sort : str | None, optional
            Server-side ordering expressed as ``"<field>:<direction>"``,
            for example ``"date_mod:desc"``. Forwarded to each page
            request; omitted when :data:`None`, leaving the server default
            ordering in place.

        Yields
        ------
        list[GetComputer]
            One page per iteration. The last yielded batch may be shorter
            than ``batch_size``.
        """

        start = 0
        while True:
            batch = self.search_computers(
                rsql_filter,
                limit=batch_size,
                start=start,
                sort=sort,
            )
            if batch:
                yield batch
            if len(batch) < batch_size:
                break
            start += batch_size

    def get_computer(self, computer_id: GlpiId) -> GetComputer:
        """Fetch one GLPI computer by identifier.

        Parameters
        ----------
        computer_id : GlpiId
            Numeric identifier of the computer to retrieve.

        Returns
        -------
        GetComputer
            Validated computer payload.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        return self._resource_get(
            f"{COMPUTER_ENDPOINT}/{computer_id}",
            GetComputer,
            failure_message=f"Failed to get computer {computer_id}",
        )

    def create_computer(self, computer: PostComputer) -> int:
        """Create one GLPI computer.

        Parameters
        ----------
        computer : PostComputer
            Request body describing the computer to create.

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
            COMPUTER_ENDPOINT,
            computer,
            failure_message="Failed to create computer",
            missing_message="GLPI computer create response did not include an ID",
            log_message_factory=(lambda new_id: f"GLPI API created computer {new_id}"),
        )

    def update_computer(
        self, computer_id: GlpiId, computer: PatchComputer
    ) -> None:
        """Update one GLPI computer with a partial body.

        Parameters
        ----------
        computer_id : GlpiId
            Numeric identifier of the computer to update.
        computer : PatchComputer
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
            f"{COMPUTER_ENDPOINT}/{computer_id}",
            computer,
            failure_message=f"Failed to update computer {computer_id}",
            log_message=f"GLPI API updated computer {computer_id}",
        )

    def delete_computer(
        self, computer_id: GlpiId, *, force: bool | None = None
    ) -> None:
        """Delete one GLPI computer by identifier.

        Parameters
        ----------
        computer_id : GlpiId
            Numeric identifier of the computer to delete.
        force : bool | None, optional
            When ``True`` the computer is permanently deleted instead of
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
            f"{COMPUTER_ENDPOINT}/{computer_id}",
            failure_message=f"Failed to delete computer {computer_id}",
            log_message=f"GLPI API deleted computer {computer_id}",
            force=force,
            delete_model_cls=DeleteComputer,
        )


__all__ = ["ComputerMixin"]
