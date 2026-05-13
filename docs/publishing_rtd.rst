Publishing
==========

Release Checklist
-----------------

#. Update ``glpi_python_client.__version__``.
#. Update the project version in ``pyproject.toml``.
#. Update ``CHANGELOG.md``.
#. Run the full check suite.

.. code-block:: console

   python -m pytest
   python -m ruff check .
   python -m mypy glpi_python_client
   python -m sphinx -b html docs docs/_build/html
   python -m build

Build Artifacts
---------------

.. code-block:: console

   python -m pip install build twine
   python -m build
   python -m twine check dist/*

Publish
-------

Publish to TestPyPI first:

.. code-block:: console

   python -m twine upload --repository testpypi dist/*

Then publish to PyPI:

.. code-block:: console

   python -m twine upload dist/*

Tag the release after the package is available from the registry.

GitHub Actions and Read the Docs
--------------------------------

The repository ships with two GitHub Actions workflows:

* ``.github/workflows/ci.yml`` runs on pull requests and pushes to ``main``.
   It executes ``pytest`` on Python 3.10 through 3.13, then runs ``ruff``,
   ``mypy``, and the Sphinx build on Python 3.12.
* ``.github/workflows/release.yml`` runs on published GitHub releases. It
   repeats the quality checks, builds the source and wheel distributions, and
   validates them with ``twine check``.

Read the Docs publication is triggered from those workflows when the following
GitHub repository secrets are configured:

* ``READTHEDOCS_TOKEN``
* ``READTHEDOCS_PROJECT``

Optional GitHub repository variables can override the defaults used by the
workflows:

* ``READTHEDOCS_BASE_URL`` (defaults to ``https://app.readthedocs.org``)
* ``READTHEDOCS_MAIN_VERSION`` (defaults to ``latest``)
* ``READTHEDOCS_RELEASE_VERSION`` (defaults to ``stable``)

The CI workflow triggers the configured main-branch documentation build after a
successful push to ``main``. The release workflow first calls the Read the Docs
``sync-versions`` endpoint, then triggers the configured release version build.
