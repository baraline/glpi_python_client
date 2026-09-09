"""Raw GLPI API request and response schemas.

The ``api_schema`` package mirrors the structure of the GLPI OpenAPI contract.
Each entity exposes one strict Pydantic model per HTTP verb:

* ``Get<Name>``  - response shape used when GLPI returns the entity.
* ``Post<Name>`` - request body for the create endpoint.
* ``Patch<Name>``- request body for the partial-update endpoint.
* ``Delete<Name>`` - query/header parameters for the delete endpoint, when
  the contract exposes any.

Only the field names, types, and read-only flags advertised by
``docs/glpi_api_contract.json`` are honoured. Mandatory and optional behaviour
is left to GLPI: every field is declared optional in Python because the
contract does not advertise ``required`` arrays.

One deliberate departure from the contract's field names: a rich-text slot
on a ``Get`` model is stored under ``<name>_html`` -- ``content_html``,
``description_html`` -- because the model holds the wire value and exposes
the converted Markdown under the contract's own name as a property. The
contract spelling is still accepted on the way in, as a validation alias.
See :mod:`glpi_python_client.models.api_schema._content`.
"""
