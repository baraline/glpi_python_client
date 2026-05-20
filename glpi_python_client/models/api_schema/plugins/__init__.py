"""Plugin entity schemas for GLPI plugin endpoints exposed via the v1 API.

These plugins are not advertised in the OpenAPI v2 contract; the field
layouts mirror what the legacy v1 REST API returns for each itemtype.
"""

from glpi_python_client.models.api_schema.plugins._fields import (
    GetPluginFieldsContainer,
    GetPluginFieldsField,
    GetPluginFieldsValueRow,
    PostPluginFieldsValueRow,
)

__all__ = [
    "GetPluginFieldsContainer",
    "GetPluginFieldsField",
    "GetPluginFieldsValueRow",
    "PostPluginFieldsValueRow",
]
