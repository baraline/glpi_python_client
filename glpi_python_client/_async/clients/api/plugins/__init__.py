"""GLPI plugin endpoint mixins exposed via the legacy v1 REST API.

Plugins are not advertised in the v2 OpenAPI contract so the mixins
under this package go through the v1 session helper exposed by
:class:`~glpi_python_client._async.auth._v1_session.GLPIV1Session`.
"""

from glpi_python_client._async.clients.api.plugins._fields import PluginFieldsMixin

__all__ = ["PluginFieldsMixin"]
