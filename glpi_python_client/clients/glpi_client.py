"""Public asynchronous GLPI client class.

The :class:`GlpiClient` class composes the per-endpoint mixins from
:mod:`glpi_python_client.clients.api` with the custom helpers from
:mod:`glpi_python_client.clients.custom` and the asynchronous transport
mixin from :mod:`glpi_python_client.clients.commons` to expose the full
public client surface.
"""

from __future__ import annotations

import asyncio
import logging
import os
from types import TracebackType
from typing import TYPE_CHECKING, Self

from glpi_python_client.clients.api import (
    AsyncDocumentMixin,
    AsyncEntityMixin,
    AsyncFollowupMixin,
    AsyncLocationMixin,
    AsyncSolutionMixin,
    AsyncTeamMemberMixin,
    AsyncTicketMixin,
    AsyncTicketTaskMixin,
    AsyncTimelineDocumentMixin,
    AsyncUserMixin,
)
from glpi_python_client.clients.commons._config import (
    build_client_env_config,
    build_client_resources,
)
from glpi_python_client.clients.commons._transport import AsyncTransportMixin
from glpi_python_client.clients.custom import (
    AsyncStatisticsMixin,
    AsyncTicketContextMixin,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = logging.getLogger(__name__)


class GlpiClient(
    AsyncTicketMixin,
    AsyncTicketTaskMixin,
    AsyncFollowupMixin,
    AsyncSolutionMixin,
    AsyncTimelineDocumentMixin,
    AsyncTeamMemberMixin,
    AsyncDocumentMixin,
    AsyncUserMixin,
    AsyncEntityMixin,
    AsyncLocationMixin,
    AsyncTicketContextMixin,
    AsyncStatisticsMixin,
    AsyncTransportMixin,
):
    """Asynchronous GLPI client backed by the contract-aligned API mixins.

    The client owns the shared HTTP session, OAuth token manager, and
    optional legacy v1 session used solely for binary document uploads.
    """

    def __init__(
        self,
        *,
        glpi_api_url: str,
        client_id: str | None = None,
        client_secret: str | None = None,
        username: str | None = None,
        password: str | None = None,
        glpi_entity: int | None = None,
        glpi_profile: int | None = None,
        entity_recursive: bool = False,
        language: str = "en_GB",
        verify_ssl: bool = True,
        auth_token_refresh: int | None = None,
        v1_base_url: str | None = None,
        v1_user_token: str | None = None,
        v1_app_token: str | None = None,
    ) -> None:
        """Build a GLPI client and its underlying transport resources.

        Parameters
        ----------
        glpi_api_url : str
            Base URL of the GLPI v2 REST API, e.g.
            ``https://glpi.example.com/api.php/v2``.
        client_id : str | None, optional
            OAuth client identifier used to obtain access tokens.
        client_secret : str | None, optional
            OAuth client secret paired with ``client_id``.
        username : str | None, optional
            GLPI account username used for the OAuth password grant.
        password : str | None, optional
            GLPI account password used for the OAuth password grant.
        glpi_entity : int | None, optional
            Default ``GLPI-Entity`` header sent with each request.
        glpi_profile : int | None, optional
            Default ``GLPI-Profile`` header sent with each request.
        entity_recursive : bool, optional
            When ``True`` the ``GLPI-Entity-Recursive`` header is sent so
            entity scope includes child entities.
        language : str, optional
            Default ``Accept-Language`` header value (e.g. ``"en_GB"``).
        verify_ssl : bool, optional
            Whether the HTTP session verifies the server certificate.
        auth_token_refresh : int | None, optional
            Number of seconds before token expiry at which the auth
            manager proactively refreshes the access token.
        v1_base_url : str | None, optional
            Base URL of the legacy GLPI v1 API used as a fallback for
            binary document uploads.
        v1_user_token : str | None, optional
            ``user_token`` for the v1 fallback session.
        v1_app_token : str | None, optional
            ``app_token`` for the v1 fallback session.

        Raises
        ------
        ValueError
            If the supplied configuration is incomplete or invalid (e.g.
            missing OAuth credentials together with no v1 fallback).
        """

        resources = build_client_resources(
            glpi_api_url=glpi_api_url,
            client_name=type(self).__name__,
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            verify_ssl=verify_ssl,
            auth_token_refresh=auth_token_refresh,
            v1_base_url=v1_base_url,
            v1_user_token=v1_user_token,
            v1_app_token=v1_app_token,
        )
        self.glpi_api_url = resources.glpi_api_url
        self._session = resources.session
        self._auth = resources.auth
        self._v1 = resources.v1
        self.glpi_entity = glpi_entity
        self.glpi_profile = glpi_profile
        self.entity_recursive = entity_recursive
        self.language = language
        self._auth_lock = asyncio.Lock()
        self._closed = False

    @classmethod
    def from_env(
        cls,
        *,
        env: Mapping[str, str] | None = None,
        prefix: str = "GLPI_",
        **overrides: object,
    ) -> Self:
        """Build a client instance from environment variables.

        The variables follow the conventional ``<PREFIX><NAME>`` naming
        (``GLPI_API_URL``, ``GLPI_CLIENT_ID``, ``GLPI_CLIENT_SECRET``,
        ``GLPI_USERNAME``, ``GLPI_PASSWORD``, ``GLPI_VERIFY_SSL``,
        ``GLPI_V1_BASE_URL``, ``GLPI_V1_USER_TOKEN``, ``GLPI_V1_APP_TOKEN``,
        ``GLPI_ENTITY``, ``GLPI_PROFILE``, ``GLPI_ENTITY_RECURSIVE``,
        ``GLPI_LANGUAGE``, ``GLPI_AUTH_TOKEN_REFRESH``).

        Parameters
        ----------
        env : Mapping[str, str] | None, optional
            Mapping the helper reads values from. Defaults to
            :data:`os.environ`.
        prefix : str, optional
            Common prefix shared by every environment variable name.
        **overrides : object
            Keyword overrides forwarded to :meth:`__init__`. Any value
            given here wins over the environment lookup.

        Returns
        -------
        GlpiClient
            A fully configured client ready to perform requests.

        Raises
        ------
        ValueError
            If the resolved configuration is missing a required field.
        """

        config = build_client_env_config(
            prefix=prefix,
            env=env if env is not None else os.environ,
            overrides=overrides,
        )
        return cls(**config)  # type: ignore[arg-type]

    async def close(self) -> None:
        """Release every resource owned by the client.

        The shared HTTP session is closed, the optional v1 fallback session
        is closed, and the client is marked as closed so subsequent calls
        raise immediately. The method is idempotent.

        Returns
        -------
        None
        """

        if self._closed:
            return
        try:
            await asyncio.to_thread(self._session.close)
            if self._v1 is not None:
                await asyncio.to_thread(self._v1.close)
        finally:
            self._closed = True

    async def __aenter__(self) -> Self:
        """Return the client unchanged for use in an ``async with`` block.

        Returns
        -------
        GlpiClient
            The client itself, suitable for chaining method calls.
        """

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the client on ``async with`` exit.

        Parameters
        ----------
        exc_type : type[BaseException] | None
            Exception class raised inside the ``async with`` block, if any.
        exc : BaseException | None
            Exception instance raised inside the block, if any.
        tb : TracebackType | None
            Traceback associated with ``exc``.

        Returns
        -------
        None
        """

        await self.close()


__all__ = ["GlpiClient"]
