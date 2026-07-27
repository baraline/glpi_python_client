"""Synchronous GLPI ``/Administration/User`` mixin.

The mixin exposes search, fetch, create, update, and delete helpers for the
GLPI user resource. All operations exchange the
:mod:`glpi_python_client.models.api_schema.administration` models and rely on
the Synchronous transport mixin for HTTP dispatch.
"""

from __future__ import annotations

from collections.abc import Iterator

from glpi_python_client.clients.commons._constants import USER_ENDPOINT, GlpiId
from glpi_python_client.clients.commons._transport import TransportMixin
from glpi_python_client.models.api_schema.administration._user import (
    DeleteUser,
    GetUser,
    PatchUser,
    PostUser,
)


class UserMixin(TransportMixin):
    """Synchronous CRUD helpers for ``/Administration/User``.

    The helpers follow the contract-first naming convention and forward all
    server-side validation to the GLPI API instead of duplicating checks on
    the client side.
    """

    def search_users(
        self,
        rsql_filter: str = "",
        *,
        limit: int = 50,
        start: int = 0,
        skip_entity: bool = False,
    ) -> list[GetUser]:
        """Search GLPI users with an optional RSQL filter.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter,
            for example ``"username==alice"``. Empty by default.
        limit : int, optional
            Maximum number of records returned by the GLPI server.
        start : int, optional
            Zero-based offset of the first record returned.
        skip_entity : bool, optional
            When ``True`` the ``GLPI-Entity`` header is omitted so the
            search spans every entity the caller has access to.

        Returns
        -------
        list[GetUser]
            Users matching the filter, validated against the contract
            ``User`` schema.
        """

        params: dict[str, object] = {"limit": limit, "start": start}
        if rsql_filter:
            params["filter"] = rsql_filter
        return self._resource_list(
            USER_ENDPOINT, GetUser, params=params, skip_entity=skip_entity
        )

    def iter_search_users(
        self,
        rsql_filter: str = "",
        *,
        batch_size: int = 50,
        skip_entity: bool = False,
    ) -> Iterator[list[GetUser]]:
        """Yield successive pages of GLPI users until exhausted.

        The generator drives pagination automatically by advancing the
        ``start`` offset after each batch. Iteration stops when the server
        returns fewer items than ``batch_size``, which signals the last page.

        Parameters
        ----------
        rsql_filter : str, optional
            Raw RSQL filter forwarded as the ``filter`` query parameter.
            Empty by default, which lists every visible user.
        batch_size : int, optional
            Number of records requested per page (default 50).
        skip_entity : bool, optional
            When ``True`` the ``GLPI-Entity`` header is omitted so the
            search spans every entity the caller has access to.

        Yields
        ------
        list[GetUser]
            One page of users per iteration. The last yielded batch may
            be shorter than ``batch_size``.
        """

        start = 0
        while True:
            batch = self.search_users(
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

    def get_user(self, user_id: GlpiId) -> GetUser:
        """Fetch one GLPI user by identifier.

        Parameters
        ----------
        user_id : GlpiId
            Numeric identifier of the user to retrieve.

        Returns
        -------
        GetUser
            Validated user payload.

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        return self._resource_get(
            f"{USER_ENDPOINT}/{user_id}",
            GetUser,
            failure_message=f"Failed to get user {user_id}",
        )

    def create_user(self, user: PostUser) -> int:
        """Create one GLPI user.

        Parameters
        ----------
        user : PostUser
            Request body describing the user to create.

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
            USER_ENDPOINT,
            user,
            failure_message="Failed to create user",
            missing_message="GLPI user create response did not include an ID",
            log_message_factory=lambda new_id: f"GLPI API created user {new_id}",
        )

    def update_user(self, user_id: GlpiId, user: PatchUser) -> None:
        """Update one GLPI user with a partial body.

        Parameters
        ----------
        user_id : GlpiId
            Numeric identifier of the user to update.
        user : PatchUser
            Partial request body. Only fields explicitly set are sent.

        Returns
        -------
        None

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        self._resource_update(
            f"{USER_ENDPOINT}/{user_id}",
            user,
            failure_message=f"Failed to update user {user_id}",
            log_message=f"GLPI API updated user {user_id}",
        )

    def delete_user(self, user_id: GlpiId, *, force: bool | None = None) -> None:
        """Delete one GLPI user by identifier.

        Parameters
        ----------
        user_id : GlpiId
            Numeric identifier of the user to delete.
        force : bool | None, optional
            When ``True`` the user is permanently deleted instead of
            being moved to the trash. ``None`` omits the query parameter.

        Returns
        -------
        None

        Raises
        ------
        GlpiStatusError
            If the GLPI server returns a non-success HTTP status.
        """

        self._resource_delete(
            f"{USER_ENDPOINT}/{user_id}",
            failure_message=f"Failed to delete user {user_id}",
            log_message=f"GLPI API deleted user {user_id}",
            force=force,
            delete_model_cls=DeleteUser,
        )


__all__ = ["UserMixin"]
