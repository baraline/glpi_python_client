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
import re
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


#: Matches ``_async`` as its own NAME token -- i.e. a qualified reference
#: such as ``glpi_python_client._async.clients.api`` or a bare directory
#: mention such as ``_async/`` -- but not as a fragment embedded inside a
#: larger identifier such as ``test_glpi_client_async_context_manager``.
#: Python's tokenizer never splits an identifier at an underscore, so a
#: name like that is a single NAME token the codegen's own substitution
#: cannot touch and is not a reference to the async tree at all; only the
#: word-boundary-delimited occurrence is the thing this guard cares about.
_BARE_ASYNC_MENTION = re.compile(r"(?<![\w])_async(?![\w])")


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("from glpi_python_client._async import foo", True),
        ("See :mod:`glpi_python_client._async.clients.api`.", True),
        ("checked into ``_async/`` by hand", True),
        ("def test_glpi_client_async_context_manager() -> None:", False),
        ("def test_async_transport_ensure_open_blocks_after_close() -> None:", False),
    ],
)
def test_bare_async_mention_pattern_distinguishes_token_from_fragment(
    line: str, expected: bool
) -> None:
    """The pattern flags a standalone ``_async`` token but not an embedded one.

    Positive control for :data:`_BARE_ASYNC_MENTION`: without this, a future
    edit could widen or narrow the pattern and
    ``test_the_generated_tree_never_names_the_async_one`` would only notice
    if the checked-in tree happened to contain a matching line that day.
    """

    assert bool(_BARE_ASYNC_MENTION.search(line)) is expected


def test_the_generated_tree_never_names_the_async_one() -> None:
    """No module under ``_sync/`` mentions ``_async`` anywhere.

    unasync repoints the imports for free, because there ``_async`` is
    its own NAME token. Inside a docstring the whole thing is a *single*
    string token, and substitution only fires when a literal's entire
    content is a key -- so a cross-reference such as
    ``:mod:`glpi_python_client._async.clients.api``` passes straight
    through, and the shipped sync client ends up documenting itself in
    terms of a tree its users never import.

    The diff gate cannot see this either: the omission is deterministic,
    so regeneration reproduces it and the diff stays clean.
    ``unasync_build`` rewrites the qualified prefix; this asserts the
    result from the other end, and additionally catches a *bare* mention
    that the prefix rewrite is deliberately too narrow to touch.

    The hand-written twins are exempt. They are not generated, and each
    one names its counterpart on purpose: pointing at the other file is
    the only way to explain why the pair exists.

    The scan looks for ``_async`` as its own token, not as a substring --
    a colocated test such as ``test_glpi_client_async_context_manager``
    legitimately contains the letters ``_async`` without naming the async
    tree, because it is a single identifier a reader (and the codegen) can
    never split. See :data:`_BARE_ASYNC_MENTION`.
    """

    build = _build_module()
    hand_written: set[str] = build.HAND_WRITTEN  # type: ignore[attr-defined]
    offenders = [
        f"{path.relative_to(_REPO_ROOT).as_posix()}:{lineno}: {line.strip()}"
        for path in sorted(_SYNC_DIR.rglob("*.py"))
        if "__pycache__" not in path.parts and path.name not in hand_written
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if _BARE_ASYNC_MENTION.search(line)
    ]
    assert offenders == [], (
        "the generated sync tree still refers to the async one:\n"
        + "\n".join(offenders)
    )


def _async_generator_names() -> set[str]:
    """Return the name of every ``async def`` in ``_async/`` that yields."""

    names: set[str] = set()
    for path in sorted(_ASYNC_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            if any(
                isinstance(inner, ast.Yield | ast.YieldFrom) for inner in ast.walk(node)
            ):
                names.add(node.name)
    return names


def test_no_async_generator_is_awaited() -> None:
    """An async generator is driven with ``async for``, never awaited.

    This is a mistake the sync tree cannot reveal. ``await gen()`` and
    ``async for x in gen()`` both generate the *same* correct synchronous
    loop once ``async``/``await`` are stripped, so the generated client
    works, the diff gate is clean, mypy is satisfied on both trees, and
    every test that exercises the sync surface passes -- while the async
    surface raises ``TypeError: object async_generator can't be used in
    'await' expression`` the moment that code path is reached.

    It was found by running the async client against a live server; this
    check makes that failure a static one.
    """

    generators = _async_generator_names()
    assert generators, "no async generators found -- this check is vacuous"

    offenders: list[tuple[str, int, str]] = []
    for path in sorted(_ASYNC_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(_REPO_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Await):
                continue
            call = node.value
            if not isinstance(call, ast.Call):
                continue
            func = call.func
            name = (
                func.attr
                if isinstance(func, ast.Attribute)
                else func.id
                if isinstance(func, ast.Name)
                else None
            )
            if name in generators:
                offenders.append((rel, node.lineno, name or "?"))

    assert offenders == [], (
        "these async generators are awaited instead of being driven with "
        f"`async for`: {offenders}"
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


def test_the_concurrency_test_twins_both_exist() -> None:
    """Neither hand-written concurrency suite can go missing unnoticed.

    These two are exempt from generation, so the diff gate says nothing
    about them. If one is deleted, its surface simply stops being tested
    and everything stays green.
    """

    assert (_ASYNC_DIR / "tests" / "test_concurrency.py").is_file()
    assert (_SYNC_DIR / "tests" / "test_concurrency.py").is_file()


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
