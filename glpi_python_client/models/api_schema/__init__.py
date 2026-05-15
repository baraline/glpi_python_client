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
"""
