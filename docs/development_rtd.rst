Development
===========

Local Setup
-----------

Create a virtual environment and install the development dependencies:

.. code-block:: console

   python -m venv .venv
   .venv\Scripts\activate
   python -m pip install --upgrade pip
   python -m pip install -e .[dev]
   python -m pre_commit install

The repository ships a root ``.pre-commit-config.yaml`` that runs Ruff on each
commit. The lint hook applies safe fixes first, then Ruff formats the touched
files.

Quality Checks
--------------

Run the focused checks before opening a pull request:

.. code-block:: console

   python -m pre_commit run --all-files
   python -m pytest
   python -m ruff check .
   python -m mypy glpi_python_client
   python -m sphinx -b html docs docs/_build/html

Package Layout
--------------

``glpi_python_client.__init__``
   Public import surface (``GlpiClient``, ``GlpiTicketContext``, public Pydantic
   models, enums, and ``__version__``).

``glpi_python_client.clients.glpi_client``
   Composition root. ``GlpiClient`` mixes the per-resource async API mixins,
   the OAuth2 token manager, the asynchronous v2 transport, and the optional
   internal v1 session used for document uploads.

``glpi_python_client.clients.api``
   Async API mixins generated from the GLPI v2 OpenAPI contract: tickets,
   ticket timeline (followups, tasks, solutions, documents), team members,
   documents, users, locations, entities, ...

``glpi_python_client.clients.custom``
   Higher-level helpers built on top of the contract mixins:
   ``get_ticket_context``, ``get_ticket_statistics``, ``get_task_statistics``.

``glpi_python_client.clients.commons``
   Shared HTTP transport pieces, including the timeline envelope unwrap that
   reconciles live server behaviour with the OpenAPI contract.

``glpi_python_client.models.api_schema``
   Contract-aligned Pydantic v2 models (``Get``/``Post``/``Patch``/``Delete``)
   for each GLPI v2 resource.

``glpi_python_client.models.custom_schema``
   Composite models such as ``GlpiTicketContext`` returned by the custom
   helpers.

Adding Endpoints
----------------

#. Add or extend the contract-aligned models in
   ``glpi_python_client.models.api_schema``.
#. Add the async mixin and method under ``glpi_python_client.clients.api``,
   mirroring the OpenAPI path and HTTP verb.
#. When the live server diverges from the contract, document the choice in the
   module docstring and (when needed) wire an unwrap helper from
   ``glpi_python_client.clients.commons``.
#. Re-export new public symbols from ``glpi_python_client.__init__``.
#. Add tests for payload serialization, response parsing, and client behaviour.
#. Document the workflow in :doc:`user_guide` and the matching skill in
   ``skills/``.

Keep organization-specific entity, profile, and category defaults outside the
library core. Applications can apply their own mapping before calling the
client.
