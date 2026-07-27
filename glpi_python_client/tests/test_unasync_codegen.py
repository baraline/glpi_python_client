"""Guards for the ``_async`` -> ``_sync`` code generation.

The generated tree is protected in CI by regenerating it and diffing. That
catches *staleness* -- someone editing ``_async/`` without rerunning the
build -- and nothing else. In particular it cannot catch the failure mode
that actually worries us:

**A token collision is deterministic, so the diff stays empty.** If a local
variable, parameter or attribute happens to be spelled like a substitution
key, ``unasync`` rewrites it every single time. Regenerating produces
exactly the same wrong file, ``git diff`` is clean, CI is green, and the
sync client is silently incorrect. No amount of diffing finds that.

These tests find it, by scanning the source for identifiers that the
substitution map would rewrite and failing on any that are not an
intentional rename.
"""

from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

import pytest

unasync = pytest.importorskip(
    "unasync",
    reason="unasync is a dev-only dependency; codegen guards need it installed",
)

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_BUILD_SCRIPT = _REPO_ROOT / "unasync_build.py"
_ASYNC_DIR = _REPO_ROOT / "glpi_python_client" / "_async"
_SYNC_DIR = _REPO_ROOT / "glpi_python_client" / "_sync"

#: Names the codegen is *supposed* to rewrite wherever they appear.
#:
#: Everything else in the substitution map is a language-level or
#: third-party name; if one of those shows up as an identifier this package
#: defines, it is a collision and the scan below fails.
_INTENTIONAL_RENAMES = {
    # unasync's built-in map turns the async context-manager protocol into
    # the sync one; defining these is the whole point.
    "__aenter__",
    "__aexit__",
    "AsyncGlpiClient",
    "AsyncClient",
    "AsyncBaseTransport",
    "AsyncHTTPTransport",
    "aclose",
    "aread",
}


def _build_module() -> object:
    """Import ``unasync_build`` from the repository root."""

    sys.path.insert(0, str(_REPO_ROOT))
    try:
        import unasync_build

        return unasync_build
    finally:
        sys.path.remove(str(_REPO_ROOT))


def _substitution_keys() -> set[str]:
    """Return every NAME token the codegen would rewrite."""

    build = _build_module()
    rule = unasync.Rule(
        fromdir=str(_ASYNC_DIR),
        todir=str(_SYNC_DIR),
        additional_replacements=build.TOKEN_REPLACEMENTS,  # type: ignore[attr-defined]
    )
    return set(rule.token_replacements)


def _identifier_sites() -> list[tuple[str, int, str]]:
    """Return ``(module, lineno, identifier)`` for every name the package defines."""

    sites: list[tuple[str, int, str]] = []
    for path in sorted(_ASYNC_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(_REPO_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                sites.append((rel, node.lineno, node.name))
            elif isinstance(node, ast.arg):
                sites.append((rel, node.lineno, node.arg))
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                sites.append((rel, node.lineno, node.id))
            elif isinstance(node, ast.Attribute):
                sites.append((rel, node.lineno, node.attr))
    return sites


def test_the_substitution_map_is_reachable() -> None:
    """Positive control: the map is non-empty and contains a known key.

    Without this, a refactor that made ``_substitution_keys`` return an
    empty set would turn the collision scan into a test that can never
    fail -- passing vacuously forever.
    """

    keys = _substitution_keys()
    assert keys, "the substitution map is empty -- the collision scan is vacuous"
    assert "AsyncGlpiClient" in keys
    assert "__aenter__" in keys, "unasync's built-in defaults are missing"


def test_no_identifier_collides_with_a_substitution_key() -> None:
    """No name this package defines is silently rewritten by the codegen.

    This is the check the CI diff gate cannot perform. A collision is
    deterministic, so regenerating reproduces it byte for byte and the diff
    stays clean while the generated client misbehaves.
    """

    keys = _substitution_keys() - _INTENTIONAL_RENAMES
    offenders = [site for site in _identifier_sites() if site[2] in keys]
    assert offenders == [], (
        "these identifiers would be silently rewritten by the codegen; "
        f"rename them or add them to the intentional list: {offenders}"
    )


def test_the_concurrency_twins_expose_the_same_surface() -> None:
    """Both hand-written ``_concurrency`` twins export the same names.

    These two files are the only ones maintained by hand on both sides, so
    they are the only place the trees can diverge without the diff gate
    noticing. If one grows a helper the other lacks, the generated tree
    stops importing cleanly -- but only for the code paths that use it,
    which may not be covered.
    """

    from glpi_python_client._async import _concurrency as async_twin
    from glpi_python_client._sync import _concurrency as sync_twin

    assert set(async_twin.__all__) == set(sync_twin.__all__)
    for name in async_twin.__all__:
        assert hasattr(sync_twin, name), f"_sync/_concurrency.py is missing {name!r}"


def test_gather_twins_agree_on_ordering() -> None:
    """The sync ``gather`` preserves order, as ``asyncio.gather`` does.

    Ordering is the whole contract callers rely on: results are matched to
    arguments by position, never by completion time.
    """

    from glpi_python_client._sync._concurrency import gather

    assert gather("a", "b", "c") == ["a", "b", "c"]
    assert gather() == []


def test_the_checked_in_sync_tree_is_not_stale() -> None:
    """``_sync/`` matches what ``_async/`` currently generates.

    Mirrors the CI gate so the failure shows up locally, at the pre-push
    hook, rather than after a push.
    """

    result = subprocess.run(
        [sys.executable, str(_BUILD_SCRIPT), "--check"],
        capture_output=True,
        text=True,
        cwd=_REPO_ROOT,
    )
    assert result.returncode == 0, (
        "the generated sync tree is out of date -- run `python unasync_build.py`\n"
        f"{result.stdout}\n{result.stderr}"
    )
