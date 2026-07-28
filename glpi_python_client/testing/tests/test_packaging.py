"""Unit tests must never be published.

The wheel is what users install. Shipping the suite inside it bloats the
install, exposes fixtures as though they were API, and lets a test file
be imported from an installed package where its dev-only dependencies do
not exist.

This asserts the exclusion patterns rather than building a wheel: a build
takes seconds and needs the ``build`` package, and the patterns are the
thing that actually regresses. The real wheel is asserted in CI.
"""

from __future__ import annotations

import pathlib
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on 3.10 only
    import tomli as tomllib

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


def _build_excludes() -> list[str]:
    """Return the hatch build exclusion patterns."""

    with (_REPO_ROOT / "pyproject.toml").open("rb") as handle:
        config = tomllib.load(handle)
    excludes = config["tool"]["hatch"]["build"]["exclude"]
    assert isinstance(excludes, list)
    return excludes


def test_test_directories_are_excluded_from_the_build() -> None:
    """Any directory named ``tests`` is dropped from the wheel and sdist."""

    assert "tests/" in _build_excludes()


def test_conftest_is_excluded_from_the_build() -> None:
    """The generated per-tree conftest files are not published."""

    assert "conftest.py" in _build_excludes()


def test_integration_tests_are_still_excluded() -> None:
    """The pre-existing exclusion is not lost while adding the new ones."""

    assert "integration_tests/" in _build_excludes()


def test_the_testing_helpers_are_still_published() -> None:
    """``glpi_python_client.testing`` is a documented downstream helper.

    It is deliberately *not* excluded: docs/development.md advertises
    ``make_client`` and ``make_async_client`` for downstream test suites.
    A pattern that swept it up would break them silently.
    """

    excludes = _build_excludes()
    assert "testing/" not in excludes
    assert "glpi_python_client/testing/" not in excludes
