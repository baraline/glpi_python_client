"""GLPI ``/Dropdowns/ContractType`` mixin.

The mixin exposes search, fetch, create, update, and delete helpers for the
GLPI contract type dropdown resource using the contract-aligned
``api_schema`` models.
"""

from __future__ import annotations

from collections.abc import Iterator

from glpi_python_client._sync.clients.commons._constants import (
    CONTRACT_TYPE_ENDPOINT,
    GlpiId,
)
from glpi_python_client._sync.clients.commons._transport import TransportMixin
from glpi_python_client.models.api_schema.dropdowns._contract_type import (
    DeleteContractType,
    GetContractType,
    PatchContractType,
    PostContractType,
)


class ContractTypeMixin(TransportMixin):
    """CRUD helpers for ``/Dropdowns/ContractType``."""

    def search_contract_types(
        self,
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
    ) -> list[GetContractType]:
        """Search GLPI contract types with an optional RSQL filter.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter.
        limit : int, optional
            Maximum number of records returned by the GLPI server.
        start : int, optional
            Zero-based offset of the first record returned.

        Returns
        -------
        list[GetContractType]
            Contract types matching the filter.
        """

        params: dict[str, object] = {"limit": limit, "start": start}
        if rsql_filter:
            params["filter"] = rsql_filter
        return self._resource_list(
            CONTRACT_TYPE_ENDPOINT, GetContractType, params=params
        )

    def iter_search_contract_types(
        self,
        rsql_filter: str = "",
        *,
        batch_size: int = 50,
    ) -> Iterator[list[GetContractType]]:
        """Yield successive pages of GLPI contract types until exhausted.

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
            ``limit`` parameter on each underlying
            :meth:`search_contract_types` call.

        Yields
        ------
        list[GetContractType]
            One page per iteration. The last yielded batch may be shorter
            than ``batch_size``.
        """

        start = 0
        while True:
            batch = self.search_contract_types(
                rsql_filter,
                limit=batch_size,
                start=start,
            )
            if batch:
                yield batch
            if len(batch) < batch_size:
                break
            start += batch_size

    def get_contract_type(self, contract_type_id: GlpiId) -> GetContractType:
        """Fetch one GLPI contract type by identifier.

        Parameters
        ----------
        contract_type_id : GlpiId
            Numeric identifier of the contract type to retrieve.

        Returns
        -------
        GetContractType
            Validated contract type payload.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        return self._resource_get(
            f"{CONTRACT_TYPE_ENDPOINT}/{contract_type_id}",
            GetContractType,
            failure_message=f"Failed to get contract type {contract_type_id}",
        )

    def create_contract_type(self, contract_type: PostContractType) -> int:
        """Create one GLPI contract type.

        Parameters
        ----------
        contract_type : PostContractType
            Request body describing the contract type to create.

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
            CONTRACT_TYPE_ENDPOINT,
            contract_type,
            failure_message="Failed to create contract type",
            missing_message=(
                "GLPI contract type create response did not include an ID"
            ),
            log_message_factory=(
                lambda new_id: f"GLPI API created contract type {new_id}"
            ),
        )

    def update_contract_type(
        self, contract_type_id: GlpiId, contract_type: PatchContractType
    ) -> None:
        """Update one GLPI contract type with a partial body.

        Parameters
        ----------
        contract_type_id : GlpiId
            Numeric identifier of the contract type to update.
        contract_type : PatchContractType
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
            f"{CONTRACT_TYPE_ENDPOINT}/{contract_type_id}",
            contract_type,
            failure_message=(f"Failed to update contract type {contract_type_id}"),
            log_message=f"GLPI API updated contract type {contract_type_id}",
        )

    def delete_contract_type(
        self, contract_type_id: GlpiId, *, force: bool | None = None
    ) -> None:
        """Delete one GLPI contract type by identifier.

        Parameters
        ----------
        contract_type_id : GlpiId
            Numeric identifier of the contract type to delete.
        force : bool | None, optional
            When ``True`` the contract type is permanently deleted instead
            of being moved to the trash.

        Returns
        -------
        None

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        self._resource_delete(
            f"{CONTRACT_TYPE_ENDPOINT}/{contract_type_id}",
            failure_message=(f"Failed to delete contract type {contract_type_id}"),
            log_message=f"GLPI API deleted contract type {contract_type_id}",
            force=force,
            delete_model_cls=DeleteContractType,
        )


__all__ = ["ContractTypeMixin"]
