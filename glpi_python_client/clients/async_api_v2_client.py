"""Concrete async client for the GLPI high-level API (v2)."""

from __future__ import annotations

import asyncio
import os
from types import TracebackType

from glpi_python_client.clients.api_v1_session import GLPIV1Session
from glpi_python_client.clients.v2.async_.api import AsyncGlpiApiClientMixin
from glpi_python_client.clients.v2.common.client_config import (
    build_client_env_config,
    build_v2_client_resources,
)
from glpi_python_client.clients.v2.common.constants import (
    LOCATION_ENDPOINT,
    USER_ENDPOINT,
    GlpiId,
)
from glpi_python_client.clients.v2.common.payloads import prepare_document_upload
from glpi_python_client.clients.v2.common.request_http import (
    ensure_response_status,
    require_non_empty_text,
    require_response_text,
)
from glpi_python_client.content.records.core.scalars import _optional_text
from glpi_python_client.models import GlpiDocument, GlpiLocation, GlpiUser


class AsyncGlpiClient(AsyncGlpiApiClientMixin):
    """Concrete asynchronous GLPI API client.

    The async client exposes the same high-level operations as
    :class:`glpi_python_client.GlpiClient`, but methods that perform remote API
    work are awaitable and use async transport wrappers.
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
        resources = build_v2_client_resources(
            glpi_api_url=glpi_api_url,
            client_name="AsyncGlpiClient",
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
        self.glpi_entity = glpi_entity
        self.glpi_profile = glpi_profile
        self.entity_recursive = entity_recursive
        self.language = language
        self._auth_lock = asyncio.Lock()
        self._closed = False
        self._session = resources.session
        self._auth = resources.auth
        self._v1 = resources.v1

    @classmethod
    def from_env(cls, *, prefix: str = "GLPI_", **overrides: object) -> AsyncGlpiClient:
        """Build an async client from environment variables."""

        config = build_client_env_config(
            prefix=prefix,
            env=os.environ,
            overrides=overrides,
        )
        return cls(**config)  # type: ignore[arg-type]

    async def create_user(self, user: GlpiUser) -> str:
        """Create one GLPI user asynchronously and return its identifier."""

        payload = user.to_api_payload()
        response = await self._post_request(USER_ENDPOINT, payload)
        ensure_response_status(
            response,
            success_statuses=(200, 201),
            failure_message=f"Failed to create user {payload.get('username')!r}",
        )
        return require_response_text(
            response,
            keys=("id",),
            missing_message="GLPI user create response did not include an ID",
        )

    async def delete_user(
        self,
        user_id: GlpiId,
        *,
        skip_entity: bool = False,
    ) -> None:
        """Delete one GLPI user asynchronously."""

        response = await self._delete_request(
            f"{USER_ENDPOINT}/{user_id}",
            skip_entity=skip_entity,
        )
        ensure_response_status(
            response,
            success_statuses=(200, 204),
            failure_message=f"Failed to delete user {user_id}",
        )
        return None

    async def create_location(self, location: GlpiLocation) -> str:
        """Create one GLPI location asynchronously and return its identifier."""

        require_non_empty_text(
            location.name,
            error_message="GLPI location creation requires a name",
        )

        response = await self._post_request(
            LOCATION_ENDPOINT,
            location.to_api_payload(),
        )
        ensure_response_status(
            response,
            success_statuses=(200, 201),
            failure_message=f"Failed to create location {location.name!r}",
        )
        return require_response_text(
            response,
            keys=("id",),
            missing_message="GLPI location create response did not include an ID",
        )

    async def delete_location(self, location_id: GlpiId) -> None:
        """Delete one GLPI location asynchronously."""

        response = await self._delete_request(f"{LOCATION_ENDPOINT}/{location_id}")
        ensure_response_status(
            response,
            success_statuses=(200, 204),
            failure_message=f"Failed to delete location {location_id}",
        )
        return None

    async def upload_document_to_ticket(
        self,
        document: GlpiDocument,
    ) -> GlpiDocument:
        """Upload one GLPI document to one ticket asynchronously."""

        parsed_ticket_id, filename, content, mime_type, document_name = (
            prepare_document_upload(
                ticket_id=document.ticket_id,
                filename=document.filename,
                content=document.content,
                mime_type=document.mime_type,
            )
        )
        v1 = self._require_v1()
        result = await asyncio.to_thread(
            v1.upload_document,
            filename,
            content,
            mime_type,
            document_name=document_name,
            ticket_id=parsed_ticket_id,
            entity_id=self.glpi_entity,
        )
        document_id = _optional_text(result.get("id"))
        return document.model_copy(
            update={
                "ticket_id": parsed_ticket_id,
                "document_id": document_id,
                "document_name": document_name,
                "filename": filename,
            }
        )

    def _require_v1(self) -> GLPIV1Session:
        """Return the configured GLPI v1 session required for document upload."""

        self._ensure_open()
        if self._v1 is None:
            raise RuntimeError(
                "Document upload requires GLPI v1 API credentials "
                "(v1_base_url and v1_user_token)."
            )
        return self._v1

    async def close(self) -> None:
        """Log out locally and release HTTP sessions held by the async client."""

        if self._closed:
            return

        self._closed = True
        self._auth.logout()

        if self._v1 is not None:
            await asyncio.to_thread(self._v1.close)
        await asyncio.to_thread(self._session.close)

    async def __aenter__(self) -> AsyncGlpiClient:
        """Return this client for async context-manager usage."""

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Log out and close network sessions when leaving an async context manager."""

        _ = (exc_type, exc_value, traceback)
        await self.close()


__all__ = ["AsyncGlpiClient"]
