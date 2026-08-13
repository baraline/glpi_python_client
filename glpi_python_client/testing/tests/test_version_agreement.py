"""The version is written down in eleven places; they must agree.

``pyproject.toml`` is the source of truth -- ``release.yml`` validates the
git tag against it, and that is the only version check anything performs.
Nothing checks the other ten, so they drift silently, and they had: at the
time this was written ``__version__`` was one release behind and all nine
skills were two.

That matters most for the skills. ``metadata.version`` tells a consumer
which release the skill describes, and nine of them claimed 0.4.1 while
documenting a branch that had since made ``server_timezone`` required and
turned a swallowed 4xx into a raise. An agent trusting the stamp would have
written client constructions that raise ``TypeError`` on the first call.
"""

from __future__ import annotations

import pathlib
import re
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on 3.10 only
    import tomli as tomllib

import glpi_python_client

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

#: ``version:`` under the ``metadata:`` key of a SKILL.md front-matter block.
_SKILL_VERSION = re.compile(r'^\s+version:\s*"(?P<version>[^"]+)"', re.MULTILINE)


def _declared_version() -> str:
    """Return the version in ``pyproject.toml``, the source of truth."""

    with (_REPO_ROOT / "pyproject.toml").open("rb") as handle:
        config = tomllib.load(handle)
    version = config["project"]["version"]
    assert isinstance(version, str)
    return version


def _skills() -> list[pathlib.Path]:
    """Return every skill definition that stamps a package version."""

    return sorted((_REPO_ROOT / "skills").rglob("SKILL.md"))


def test_package_dunder_version_matches_pyproject() -> None:
    """``glpi_python_client.__version__`` is what the build publishes."""

    assert glpi_python_client.__version__ == _declared_version()


def test_every_skill_stamps_the_released_version() -> None:
    """No skill claims to describe a release other than this one."""

    expected = _declared_version()
    stamped = {
        path.relative_to(_REPO_ROOT).as_posix(): match["version"]
        for path in _skills()
        if (match := _SKILL_VERSION.search(path.read_text(encoding="utf-8")))
    }

    assert len(stamped) == len(_skills()), f"a skill has no metadata.version: {stamped}"
    assert set(stamped.values()) == {expected}, (
        f"skills disagree with pyproject ({expected}): "
        f"{ {k: v for k, v in stamped.items() if v != expected} }"
    )


def test_the_changelog_records_the_released_version() -> None:
    """A release has a section; the notes are not left under 'Unreleased'.

    Every release through 0.4.2 was tagged with its notes still under an
    ``## Unreleased`` heading, so three releases' entries accumulated into
    one undifferentiated block.
    """

    changelog = (_REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    expected = _declared_version()

    headings = re.findall(r"^## +(.+)$", changelog, re.MULTILINE)

    assert any(head.startswith(expected) for head in headings), (
        f"CHANGELOG.md has no section for {expected}; found {headings}"
    )
