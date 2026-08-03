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

Published GitHub releases now upload the package to PyPI automatically through
``.github/workflows/release.yml``.

This repository now uses PyPI Trusted Publishing rather than a long-lived PyPI
API token stored in GitHub secrets.

GitHub Actions side:

* Workflow: ``.github/workflows/release.yml``
* Job: ``publish-pypi``
* Environment: ``pypi``
* Required permission: ``id-token: write``

PyPI side:

* If the ``glpi-python-client`` project already exists on PyPI, add a trusted
   publisher for:

   * owner: ``baraline``
   * repository: ``glpi_python_client``
   * workflow: ``release.yml``
   * environment: ``pypi``

* If the project does not exist yet on PyPI, create a pending trusted
   publisher with the same GitHub configuration and the PyPI project name
   ``glpi-python-client``.

Release flow:

#. Push the release commit and tag.
#. Publish the GitHub release.
#. Let the release workflow run the test, quality, build, metadata, and PyPI
   publication steps.

The release workflow validates that the GitHub release tag,
``pyproject.toml`` version, and ``glpi_python_client.__version__`` all match
before it builds and publishes the package.

No ``PYPI_API_TOKEN`` GitHub secret is required for this flow.

Manual fallback:

Publish to TestPyPI first if you need to validate the artifacts manually:

.. code-block:: console

   python -m twine upload --repository testpypi dist/*

Then publish to PyPI manually if the workflow is unavailable:

.. code-block:: console

   python -m twine upload dist/*

The GitHub release should only be published after the version and changelog are
ready, because publishing the release now triggers the PyPI upload.

GitHub Actions and Read the Docs
--------------------------------

The repository ships with two GitHub Actions workflows:

* ``.github/workflows/ci.yml`` runs on pull requests and pushes to ``main``.
   It executes ``pytest`` on Python 3.10 through 3.14, then runs ``ruff``,
   ``mypy``, and the Sphinx build on Python 3.12.
* ``.github/workflows/release.yml`` runs on published GitHub releases. It
   repeats the quality checks, builds the source and wheel distributions,
   validates them with ``twine check``, and publishes them to PyPI through a
   GitHub Actions trusted publisher configuration on PyPI.

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
