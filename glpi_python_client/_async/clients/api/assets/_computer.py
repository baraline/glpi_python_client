"""GLPI ``/Assets/Computer`` mixin.

The mixin exposes search, fetch, create, update, and delete helpers for the
GLPI computer resource using the contract-aligned ``api_schema`` models. It
also exposes CRUD helpers for the ``/Assets/Computer/{id}/Contract``
sub-resource, the join answering which contracts cover a given computer.

``link_computer_contract`` and ``update_computer_contract`` set ``itemtype``
and ``items_id`` themselves rather than trusting the caller-supplied values
on the request body; see ``models/api_schema/assets/_contract_item.py`` for
why.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from glpi_python_client._async.clients.commons._constants import (
    COMPUTER_ENDPOINT,
    GlpiId,
)
from glpi_python_client._async.clients.commons._transport import TransportMixin
from glpi_python_client.models.api_schema.assets._computer import (
    DeleteComputer,
    GetComputer,
    PatchComputer,
    PostComputer,
)
from glpi_python_client.models.api_schema.assets._contract_item import (
    DeleteContractItem,
    GetContractItem,
    PatchContractItem,
    PostContractItem,
)


class ComputerMixin(TransportMixin):
    """CRUD helpers for ``/Assets/Computer``."""

    async def search_computers(
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
        return await self._resource_list(COMPUTER_ENDPOINT, GetComputer, params=params)

    async def iter_search_computers(
        self,
        rsql_filter: str = "",
        *,
        batch_size: int = 50,
        sort: str | None = None,
    ) -> AsyncIterator[list[GetComputer]]:
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
            batch = await self.search_computers(
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

    async def get_computer(self, computer_id: GlpiId) -> GetComputer:
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

        return await self._resource_get(
            f"{COMPUTER_ENDPOINT}/{computer_id}",
            GetComputer,
            failure_message=f"Failed to get computer {computer_id}",
        )

    async def create_computer(self, computer: PostComputer) -> int:
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

        return await self._resource_create(
            COMPUTER_ENDPOINT,
            computer,
            failure_message="Failed to create computer",
            missing_message="GLPI computer create response did not include an ID",
            log_message_factory=(lambda new_id: f"GLPI API created computer {new_id}"),
        )

    async def update_computer(
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

        await self._resource_update(
            f"{COMPUTER_ENDPOINT}/{computer_id}",
            computer,
            failure_message=f"Failed to update computer {computer_id}",
            log_message=f"GLPI API updated computer {computer_id}",
        )

    async def delete_computer(
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

        await self._resource_delete(
            f"{COMPUTER_ENDPOINT}/{computer_id}",
            failure_message=f"Failed to delete computer {computer_id}",
            log_message=f"GLPI API deleted computer {computer_id}",
            force=force,
            delete_model_cls=DeleteComputer,
        )

    async def list_computer_contracts(
        self,
        computer_id: GlpiId,
        *,
        limit: int = 50,
        start: int = 0,
    ) -> list[GetContractItem]:
        """List the contracts linked to one GLPI computer.

        Parameters
        ----------
        computer_id : GlpiId
            Numeric identifier of the owning computer.
        limit : int, optional
            Maximum number of records returned by the GLPI server.
        start : int, optional
            Zero-based offset of the first record returned.

        Returns
        -------
        list[GetContractItem]
            Contract links belonging to the computer.
        """

        params: dict[str, object] = {"limit": limit, "start": start}
        return await self._resource_list(
            f"{COMPUTER_ENDPOINT}/{computer_id}/Contract",
            GetContractItem,
            params=params,
        )

    async def get_computer_contract(
        self, computer_id: GlpiId, link_id: GlpiId
    ) -> GetContractItem:
        """Fetch one contract link recorded against a GLPI computer.

        Parameters
        ----------
        computer_id : GlpiId
            Numeric identifier of the owning computer.
        link_id : GlpiId
            Numeric identifier of the contract link to retrieve.

        Returns
        -------
        GetContractItem
            Validated contract link payload.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        return await self._resource_get(
            f"{COMPUTER_ENDPOINT}/{computer_id}/Contract/{link_id}",
            GetContractItem,
            failure_message=(
                f"Failed to get contract link {link_id} for computer {computer_id}"
            ),
        )

    async def link_computer_contract(
        self, computer_id: GlpiId, link: PostContractItem
    ) -> int:
        """Link one GLPI contract to one computer.

        The ``itemtype`` and ``items_id`` fields are set from
        ``computer_id`` rather than taken from ``link``. The GLPI contract
        types ``itemtype`` as a free string, so a caller-supplied value is
        a silent mis-link waiting to happen; this helper already knows
        which asset it is working on.

        Parameters
        ----------
        computer_id : GlpiId
            Numeric identifier of the computer the contract covers.
        link : PostContractItem
            Request body naming the contract to link. Any ``itemtype`` or
            ``items_id`` set on it is replaced.

        Returns
        -------
        int
            Identifier assigned to the new link by the GLPI server.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        GlpiProtocolError
            If the create response is missing the ``id`` field.
        """

        body = link.model_copy(update={"itemtype": "Computer", "items_id": computer_id})
        return await self._resource_create(
            f"{COMPUTER_ENDPOINT}/{computer_id}/Contract",
            body,
            failure_message=f"Failed to link a contract to computer {computer_id}",
            missing_message=(
                "GLPI contract link create response did not include an ID"
            ),
            log_message_factory=(
                lambda new_id: (
                    f"GLPI API linked contract item {new_id} to computer {computer_id}"
                )
            ),
        )

    async def update_computer_contract(
        self, computer_id: GlpiId, link_id: GlpiId, link: PatchContractItem
    ) -> None:
        """Update one computer-contract link with a partial body.

        The ``itemtype`` and ``items_id`` fields are set from
        ``computer_id`` rather than taken from ``link``, for the same
        reason as :meth:`link_computer_contract`.

        Parameters
        ----------
        computer_id : GlpiId
            Numeric identifier of the owning computer.
        link_id : GlpiId
            Numeric identifier of the contract link to update.
        link : PatchContractItem
            Partial request body. Any ``itemtype`` or ``items_id`` set on
            it is replaced.

        Returns
        -------
        None

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        body = link.model_copy(update={"itemtype": "Computer", "items_id": computer_id})
        await self._resource_update(
            f"{COMPUTER_ENDPOINT}/{computer_id}/Contract/{link_id}",
            body,
            failure_message=(
                f"Failed to update contract link {link_id} for computer {computer_id}"
            ),
            log_message=(
                f"GLPI API updated contract link {link_id} for computer {computer_id}"
            ),
        )

    async def unlink_computer_contract(
        self, computer_id: GlpiId, link_id: GlpiId, *, force: bool | None = None
    ) -> None:
        """Remove one contract link from a GLPI computer.

        Parameters
        ----------
        computer_id : GlpiId
            Numeric identifier of the owning computer.
        link_id : GlpiId
            Numeric identifier of the contract link to remove.
        force : bool | None, optional
            When ``True`` the link is permanently deleted instead of
            being moved to the trash.

        Returns
        -------
        None

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        await self._resource_delete(
            f"{COMPUTER_ENDPOINT}/{computer_id}/Contract/{link_id}",
            failure_message=(
                f"Failed to unlink contract link {link_id} from computer {computer_id}"
            ),
            log_message=(
                f"GLPI API unlinked contract link {link_id} from computer {computer_id}"
            ),
            force=force,
            delete_model_cls=DeleteContractItem,
        )


__all__ = ["ComputerMixin"]
