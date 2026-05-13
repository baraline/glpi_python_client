"""Concrete synchronous client for the GLPI high-level API.

This module defines the public ``GlpiClient`` class that assembles the shared
v2 sync mixins, owns runtime resources, and exposes the small v1-backed
document-upload surface.
"""

from __future__ import annotations

import os
import threading
from types import TracebackType

from glpi_python_client.clients.api_v1_session import GLPIV1Session
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
from glpi_python_client.clients.v2.sync import GlpiApiClientMixin
from glpi_python_client.content.records.core.scalars import _optional_text
from glpi_python_client.models import GlpiDocument, GlpiLocation, GlpiUser


class GlpiClient(GlpiApiClientMixin):
    """Concrete GLPI API client.

    Provide either ``client_id`` and ``client_secret``, ``username`` and
    ``password``, or both credential sets depending on your GLPI instance's
    authentication requirements.

    Parameters
    ----------
    glpi_api_url : str
        Base URL of the GLPI high-level API.
    client_id : str | None, optional
        OAuth2 client ID. Provide it together with ``client_secret`` when the
        GLPI instance requires client authentication.
    client_secret : str | None, optional
        OAuth2 client secret. Provide it together with ``client_id``.
    username : str | None, optional
        GLPI username for password-grant authentication. Provide it together
        with ``password``.
    password : str | None, optional
        GLPI password for password-grant authentication. Provide it together
        with ``username``.
    glpi_entity : int | None
        Default GLPI entity scope.
    glpi_profile : int | None
        Default GLPI profile scope.
    entity_recursive : bool
        Whether entity recursion is enabled.
    language : str
        Language used for API responses.
    verify_ssl : bool, optional
        Whether TLS certificates are verified.
    auth_token_refresh : int | None, optional
        Maximum OAuth token age in seconds before a refresh is attempted.
        ``None`` disables interval-based refreshes.
    v1_base_url : str | None, optional
        Legacy GLPI v1 base URL for document upload.
    v1_user_token : str | None, optional
        GLPI v1 user token.
    v1_app_token : str | None, optional
        GLPI v1 app token.
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
            client_name="GlpiClient",
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
        self._auth_lock = threading.RLock()
        self._closed = False
        self._session = resources.session
        self._auth = resources.auth
        self._v1 = resources.v1

    @classmethod
    def from_env(cls, *, prefix: str = "GLPI_", **overrides: object) -> GlpiClient:
        """Build a client from environment variables.

        This convenience constructor maps environment variables to the standard
        client arguments. Explicit keyword overrides win over values read from
        the environment. At least one complete auth pair must be supplied:
        ``CLIENT_ID`` and ``CLIENT_SECRET``, ``USERNAME`` and ``PASSWORD``, or
        both pairs.
        """

        config = build_client_env_config(
            prefix=prefix,
            env=os.environ,
            overrides=overrides,
        )
        return cls(**config)  # type: ignore[arg-type]

    def create_user(self, user: GlpiUser) -> str:
        """Create a GLPI user and return the identifier assigned by GLPI.

        The provided model is serialized through ``GlpiUser.to_api_payload()``
        and the method raises when the server accepts the request but does not
        return the created user ID.
        """

        payload = user.to_api_payload()
        response = self._post_request(USER_ENDPOINT, payload)
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

    def delete_user(self, user_id: GlpiId, *, skip_entity: bool = False) -> None:
        """Delete a GLPI user by identifier.

        This method succeeds only when GLPI returns a normal delete status and
        otherwise raises a ``ValueError`` with the server response context.
        """

        response = self._delete_request(
            f"{USER_ENDPOINT}/{user_id}",
            skip_entity=skip_entity,
        )
        ensure_response_status(
            response,
            success_statuses=(200, 204),
            failure_message=f"Failed to delete user {user_id}",
        )
        return None

    def create_location(self, location: GlpiLocation) -> str:
        """Create a GLPI location and return the identifier assigned by GLPI.

        The method performs the local name validation required by the package
        before sending the payload to the remote API.
        """

        require_non_empty_text(
            location.name,
            error_message="GLPI location creation requires a name",
        )

        response = self._post_request(
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

    def delete_location(self, location_id: GlpiId) -> None:
        """Delete a GLPI location by identifier.

        Successful deletes return ``None`` and keep the behavior consistent
        with the other mutation helpers on the synchronous client.
        """

        response = self._delete_request(f"{LOCATION_ENDPOINT}/{location_id}")
        ensure_response_status(
            response,
            success_statuses=(200, 204),
            failure_message=f"Failed to delete location {location_id}",
        )
        return None

    def upload_document_to_ticket(
        self,
        document: GlpiDocument,
    ) -> GlpiDocument:
        """Upload a document to a ticket through the legacy v1 document API.

        The input model is validated and normalized first, then copied with the
        resulting ticket and document identifiers so callers receive the final
        upload metadata in one object.
        """

        parsed_ticket_id, filename, content, mime_type, document_name = (
            prepare_document_upload(
                ticket_id=document.ticket_id,
                filename=document.filename,
                content=document.content,
                mime_type=document.mime_type,
            )
        )
        v1 = self._require_v1()
        result = v1.upload_document(
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
        """Return the configured v1 session required for document upload.

        Document upload is the only remaining workflow that still depends on
        the legacy GLPI API, so this guard fails fast when the client was not
        configured with the required v1 credentials.
        """

        self._ensure_open()
        if self._v1 is None:
            raise RuntimeError(
                "Document upload requires GLPI v1 API credentials "
                "(v1_base_url and v1_user_token)."
            )
        return self._v1

    def close(self) -> None:
        """Release client-owned authentication and HTTP resources.

        Closing is idempotent. The method clears cached OAuth state, closes the
        optional v1 session when present, and then closes the shared v2 HTTP
        session.
        """

        if self._closed:
            return

        self._closed = True
        self._auth.logout()

        if self._v1 is not None:
            self._v1.close()
        self._session.close()

    def __enter__(self) -> GlpiClient:
        """Return the client instance for ``with`` statement usage.

        The synchronous client uses itself as the context-manager value and
        defers cleanup to ``__exit__``.
        """

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close client resources when leaving a ``with`` block.

        Exception details are ignored because cleanup is unconditional and the
        context manager does not suppress caller exceptions.
        """

        _ = (exc_type, exc_value, traceback)
        self.close()


__all__ = ["GlpiClient"]
