"""Public authentication exports for the GLPI client package.

The authentication package stays small on purpose and currently exposes the
token manager used by the synchronous and asynchronous high-level clients.
"""

from __future__ import annotations

from glpi_python_client.auth.auth import GLPITokenManager

__all__ = ["GLPITokenManager"]
