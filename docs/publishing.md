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

Publish to TestPyPI first:

```bash
python -m twine upload --repository testpypi dist/*
```

Then publish to PyPI:

```bash
python -m twine upload dist/*
```

Tag the release after the package is available from the registry.
