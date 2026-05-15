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
   Public import surface.

``glpi_python_client._client_v2``
   Main ``GlpiClient`` implementation, configuration, authentication, and
   context-manager cleanup.

``glpi_python_client._api``
   High-level GLPI endpoint helpers.

``glpi_python_client._client_v1``
   Legacy v1 session used for document operations.

``glpi_python_client.models``
   Typed request and response models.

``glpi_python_client._records``
   Raw GLPI payload normalization and model conversion.

Adding Endpoints
----------------

#. Add or extend a model in ``glpi_python_client.models``.
#. Add response parsing in ``glpi_python_client._records`` when needed.
#. Add the client method in ``glpi_python_client._api``.
#. Add tests for payload serialization, response parsing, and client behavior.
#. Document the workflow in :doc:`user_guide` or the README.

Keep organization-specific entity, profile, and category defaults outside the
library core. Applications can apply their own mapping before calling the
client.
