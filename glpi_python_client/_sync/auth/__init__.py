"""Public authentication exports for the GLPI client package.

The authentication package owns the OAuth2 token manager used by the
GLPI client and the legacy v1 session wrapper used solely by
the management document upload mixin.
"""

from __future__ import annotations

from glpi_python_client._sync.auth._v1_session import GLPIV1Session
from glpi_python_client._sync.auth.auth import GLPITokenManager

__all__ = ["GLPITokenManager", "GLPIV1Session"]
