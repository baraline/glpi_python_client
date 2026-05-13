# Publishing Checklist

This project uses `pyproject.toml` with Hatchling as the build backend.

## Before Release

1. Update `glpi_python_client.__version__`.
2. Update `pyproject.toml` project version.
3. Update `CHANGELOG.md`.
4. Run the full check suite:

```bash
python -m pytest
python -m ruff check .
python -m mypy glpi_python_client
python -m build
```

## Build

```bash
python -m pip install build twine
python -m build
python -m twine check dist/*
```

## Publish

Published GitHub releases now upload the package to PyPI automatically through
`.github/workflows/release.yml`.

This repository now uses PyPI Trusted Publishing rather than a long-lived PyPI
API token stored in GitHub secrets.

GitHub Actions side:

- Workflow: `.github/workflows/release.yml`
- Job: `publish-pypi`
- Environment: `pypi`
- Required permission: `id-token: write`

PyPI side:

- If the `glpi-python-client` project already exists on PyPI, add a trusted
   publisher with owner `baraline`, repository `glpi_python_client`, workflow
   `release.yml`, and environment `pypi`.
- If the project does not exist yet on PyPI, create a pending trusted
   publisher with the same GitHub configuration and the PyPI project name
   `glpi-python-client`.

Release flow:

1. Push the release commit and tag.
2. Publish the GitHub release.
3. Let the release workflow run the test, quality, build, metadata, and PyPI
    publication steps.

No `PYPI_API_TOKEN` GitHub secret is required for this flow.

Manual fallback:

Publish to TestPyPI first if you need to validate the artifacts manually:

```bash
python -m twine upload --repository testpypi dist/*
```

Then publish to PyPI manually if the workflow is unavailable:

```bash
python -m twine upload dist/*
```

The GitHub release should only be published after the version and changelog are
ready, because publishing the release now triggers the PyPI upload.
