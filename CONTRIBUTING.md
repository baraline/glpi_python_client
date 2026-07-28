# Contributing

Thank you for improving `glpi-python-client`.

## Development Setup

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e .[dev]
python -m pre_commit install
python -m pre_commit run --all-files
python -m pytest
```

The repository ships a root `.pre-commit-config.yaml` that runs Ruff on each
commit. The lint hook applies safe fixes first, then Ruff formats the touched
files.

## Quality Checks

Run the focused checks before opening a pull request:

```bash
python -m pre_commit run --all-files
python -m pytest
python -m ruff check .
python -m mypy glpi_python_client
```

## Documentation build

To build the documentation locally:

```bash
python -m sphinx -W --keep-going -b html docs docs/_build/html
```

## GitHub Actions

- `.github/workflows/ci.yml` runs tests for Python 3.10 through 3.13 on pull
  requests and pushes to `main`.
- The same workflow runs `ruff`, `mypy`, and a warning-free Sphinx build on
  Python 3.12.
- When `READTHEDOCS_TOKEN` and `READTHEDOCS_PROJECT` are configured as GitHub
  secrets, pushes to `main` also trigger the Read the Docs `latest` build.
- `.github/workflows/release.yml` repeats the checks for published releases,
  builds the distribution artifacts, and triggers the configured release docs
  build on Read the Docs.

## Design Guidelines

- Keep API calls behind `GlpiClient` / `AsyncGlpiClient` methods. Add
  new endpoints to the async endpoint mixin under
  `glpi_python_client/_async/`, then run `python unasync_build.py` to
  regenerate `glpi_python_client/_sync/` and commit both. Never edit
  `_sync/` by hand; CI regenerates it and fails on any difference. For
  concurrent fan-out use `gather` from `_async/_concurrency.py` rather
  than `asyncio.gather` directly, so the generated sync code stays
  correct.
- Prefer field-validated Pydantic models for request and response payloads.
- Avoid organization-specific category, entity, or profile defaults in the
  library core.
- Add tests for payload serialization and response normalization when adding
  endpoints.
