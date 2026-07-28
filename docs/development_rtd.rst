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

Integration Tests
-----------------

The ``integration_tests/`` directory holds end-to-end tests that drive a live
GLPI instance through the synchronous and asynchronous clients. They are
collected only when secrets resolve to a reachable instance; otherwise each
test self-skips via ``pytest.skip``. Every test cleans up the records it
creates in a ``finally`` block, but it is still recommended to point them at
a non-production GLPI.

Markers and CI behaviour
~~~~~~~~~~~~~~~~~~~~~~~~

All integration tests are tagged with the ``integration`` pytest marker
declared in ``pyproject.toml``. The ``ci.yml`` workflow runs
``pytest -m "not integration"`` for both the test matrix and the coverage
job, so the public CI never reaches a live GLPI. The default local
``python -m pytest`` invocation *does* attempt to collect them, but they
skip automatically when no secrets are configured.

To explicitly opt in or out locally:

.. code-block:: console

   python -m pytest -m integration       # run only the live suite
   python -m pytest -m "not integration" # mirror the CI behaviour

Configuration
~~~~~~~~~~~~~

The suite reads each value from a file named after the secret under
``secrets/`` at the repository root, falling back to the matching
environment variable when the file is absent. The ``secrets/`` directory is
gitignored. Each file contains a single trimmed value.

Required:

==============================  =========================  ===========================================
Secret file                     Environment variable       Purpose
==============================  =========================  ===========================================
``glpi_api_url``                ``GLPI_API_URL``           Base URL of the GLPI v2 API.
``glpi_client_id_test``         ``GLPI_CLIENT_ID``         OAuth2 client identifier.
``glpi_client_secret_test``     ``GLPI_CLIENT_SECRET``     OAuth2 client secret.
``glpi_username``               ``GLPI_USERNAME``          GLPI user for the password grant.
``glpi_password``               ``GLPI_PASSWORD``          Password for the GLPI user above.
==============================  =========================  ===========================================

Optional:

==============================  =============================  ============================================
Secret file                     Environment variable           Purpose
==============================  =============================  ============================================
``glpi_verify_ssl``             ``GLPI_VERIFY_SSL``            Toggle TLS verification (default ``false``).
``glpi_entity``                 ``GLPI_ENTITY``                Active entity id sent on every request.
``glpi_profile``                ``GLPI_PROFILE``               Active profile id sent on every request.
``glpi_entity_recursive``       ``GLPI_ENTITY_RECURSIVE``      Include sub-entities (default ``false``).
``glpi_api_v1_url``             ``GLPI_API_V1_URL``            Base URL of the legacy v1 API.
``glpi_api_v1_token_user``      ``GLPI_V1_USER_TOKEN``         v1 user token (enables document uploads).
``glpi_api_v1_app_token``       ``GLPI_V1_APP_TOKEN``          v1 application token paired with the above.
``glpi_team_member_role``       ``GLPI_TEAM_MEMBER_ROLE``      Role used to add the test user to a ticket.
==============================  =============================  ============================================

The v1 secrets are only required for the document-upload test; when they
are missing that single test skips while the rest of the suite runs.

Running the suite
~~~~~~~~~~~~~~~~~

Once secrets are in place:

.. code-block:: console

   python -m pytest integration_tests -m integration

Use a disposable GLPI instance or one whose entity is dedicated to
automated tests. The suite creates and deletes users, locations, tickets,
followups, tasks, and solutions on every run.

Package Layout
--------------

``glpi_python_client.__init__``
   Public import surface (``GlpiClient``, ``GlpiTicketContext``, public Pydantic
   models, enums, and ``__version__``).

``glpi_python_client._async.clients.client``
   Composition root. ``GlpiClient`` mixes the per-resource async API mixins,
   the OAuth2 token manager, the asynchronous v2 transport, and the optional
   internal v1 session used for document uploads.

``glpi_python_client._async.clients.api``
   Async API mixins generated from the GLPI v2 OpenAPI contract: tickets,
   ticket timeline (followups, tasks, solutions, documents), team members,
   documents, users, locations, entities, ...

``glpi_python_client._async.clients.custom``
   Higher-level helpers built on top of the contract mixins:
   ``get_ticket_context``, ``get_ticket_statistics``, ``get_task_statistics``.

``glpi_python_client._async.clients.commons``
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
#. Add the async mixin and method under ``glpi_python_client._async.clients.api``,
   mirroring the OpenAPI path and HTTP verb.
#. When the live server diverges from the contract, document the choice in the
   module docstring and (when needed) wire an unwrap helper from
   ``glpi_python_client._async.clients.commons``.
#. Re-export new public symbols from ``glpi_python_client.__init__``.
#. Add tests for payload serialization, response parsing, and client behaviour.
#. Document the workflow in :doc:`user_guide` and the matching skill in
   ``skills/``.

Keep organization-specific entity, profile, and category defaults outside the
library core. Applications can apply their own mapping before calling the
client.
