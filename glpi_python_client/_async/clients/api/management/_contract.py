"""GLPI ``/Management/Contract`` mixin.

The mixin exposes search, fetch, create, update, and delete helpers for the
GLPI contract resource using the contract-aligned ``api_schema`` models.
Cost-line helpers are added to this same class by a later task; this
module holds CRUD only.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from glpi_python_client._async.clients.commons._constants import (
    CONTRACT_ENDPOINT,
    GlpiId,
)
from glpi_python_client._async.clients.commons._transport import TransportMixin
from glpi_python_client.models.api_schema.management._contract import (
    DeleteContract,
    GetContract,
    PatchContract,
    PostContract,
)


class ContractMixin(TransportMixin):
    """CRUD helpers for ``/Management/Contract``."""

    async def search_contracts(
        self,
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        sort: str | None = None,
    ) -> list[GetContract]:
        """Search GLPI contracts with an optional RSQL filter.

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
            for example ``"date_begin:desc"``. Omitted when :data:`None`,
            leaving the server default ordering in place.

        Returns
        -------
        list[GetContract]
            Contracts matching the filter.
        """

        params: dict[str, object] = {"limit": limit, "start": start}
        if rsql_filter:
            params["filter"] = rsql_filter
        if sort is not None:
            params["sort"] = sort
        return await self._resource_list(CONTRACT_ENDPOINT, GetContract, params=params)

    async def iter_search_contracts(
        self,
        rsql_filter: str = "",
        *,
        batch_size: int = 50,
        sort: str | None = None,
    ) -> AsyncIterator[list[GetContract]]:
        """Yield successive pages of GLPI contracts until exhausted.

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
            ``limit`` parameter on each underlying :meth:`search_contracts`
            call.
        sort : str | None, optional
            Server-side ordering expressed as ``"<field>:<direction>"``,
            for example ``"date_begin:desc"``. Forwarded to each page
            request; omitted when :data:`None`, leaving the server default
            ordering in place.

        Yields
        ------
        list[GetContract]
            One page per iteration. The last yielded batch may be shorter
            than ``batch_size``.
        """

        start = 0
        while True:
            batch = await self.search_contracts(
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

    async def get_contract(self, contract_id: GlpiId) -> GetContract:
        """Fetch one GLPI contract by identifier.

        Parameters
        ----------
        contract_id : GlpiId
            Numeric identifier of the contract to retrieve.

        Returns
        -------
        GetContract
            Validated contract payload.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        return await self._resource_get(
            f"{CONTRACT_ENDPOINT}/{contract_id}",
            GetContract,
            failure_message=f"Failed to get contract {contract_id}",
        )

    async def create_contract(self, contract: PostContract) -> int:
        """Create one GLPI contract.

        Parameters
        ----------
        contract : PostContract
            Request body describing the contract to create.

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
            CONTRACT_ENDPOINT,
            contract,
            failure_message="Failed to create contract",
            missing_message="GLPI contract create response did not include an ID",
            log_message_factory=(lambda new_id: f"GLPI API created contract {new_id}"),
        )

    async def update_contract(
        self, contract_id: GlpiId, contract: PatchContract
    ) -> None:
        """Update one GLPI contract with a partial body.

        Parameters
        ----------
        contract_id : GlpiId
            Numeric identifier of the contract to update.
        contract : PatchContract
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
            f"{CONTRACT_ENDPOINT}/{contract_id}",
            contract,
            failure_message=f"Failed to update contract {contract_id}",
            log_message=f"GLPI API updated contract {contract_id}",
        )

    async def delete_contract(
        self, contract_id: GlpiId, *, force: bool | None = None
    ) -> None:
        """Delete one GLPI contract by identifier.

        Parameters
        ----------
        contract_id : GlpiId
            Numeric identifier of the contract to delete.
        force : bool | None, optional
            When ``True`` the contract is permanently deleted instead of
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
            f"{CONTRACT_ENDPOINT}/{contract_id}",
            failure_message=f"Failed to delete contract {contract_id}",
            log_message=f"GLPI API deleted contract {contract_id}",
            force=force,
            delete_model_cls=DeleteContract,
        )


__all__ = ["ContractMixin"]
