"""Structural guard against the async bridge's self-call trap.

``AsyncBridge`` wraps every public sync method into a coroutine. A sync
body running inside a worker thread that calls a sibling *public* method
through ``self`` therefore receives a coroutine object, not data: the call
is silently dropped (``RuntimeWarning: coroutine ... was never awaited``).

Any public method that transitively reaches a public method through
``self`` must be given a hand-written async override on
``AsyncGlpiClient``. This test enforces that rule so the bug class cannot
be reintroduced by a future endpoint.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

from glpi_python_client import AsyncGlpiClient, GlpiClient

# Lifecycle helpers differ between the surfaces on purpose.
_EXCLUDED = {"from_env", "close"}

# Methods known to violate the rule, removed as each is fixed. Must reach
# empty; a non-empty set here is a shipped bug, not an accepted state.
_KNOWN_UNCOVERED: frozenset[str] = frozenset(
    {
        "create_kb_article",
        "update_kb_article",
    }
)


def _public_names(cls: type) -> set[str]:
    """Return the public callable names exposed by ``cls``."""

    return {
        name
        for name, _ in inspect.getmembers(cls, predicate=callable)
        if not name.startswith("_") and name not in _EXCLUDED
    }


def _self_call_map(cls: type) -> dict[str, set[str]]:
    """Map every method of ``cls`` to the ``self.X()`` names it calls."""

    out: dict[str, set[str]] = {}
    for klass in cls.__mro__:
        if klass is object:
            continue
        for name, member in vars(klass).items():
            if name in out:
                continue
            func = member
            if isinstance(func, (classmethod, staticmethod)):
                func = func.__func__
            if not inspect.isfunction(func):
                continue
            try:
                tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
            except (OSError, TypeError, SyntaxError):  # pragma: no cover
                continue
            calls: set[str] = set()
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "self"
                ):
                    calls.add(node.func.attr)
            out[name] = calls
    return out


def _reaches_public(
    name: str,
    call_map: dict[str, set[str]],
    public: set[str],
    seen: set[str] | None = None,
) -> bool:
    """Return whether ``name`` reaches a public method through ``self``.

    Recurses through private helpers, which is what catches
    ``create_kb_article`` -> ``_apply_category_fallback`` ->
    ``set_kb_article_categories``.
    """

    if seen is None:
        seen = set()
    if name in seen:
        return False
    seen.add(name)
    for callee in call_map.get(name, set()):
        if callee in public:
            return True
        if callee.startswith("_") and _reaches_public(callee, call_map, public, seen):
            return True
    return False


def _is_real_async_override(member: object) -> bool:
    """Return whether ``member`` is a hand-written async override.

    The bridge builds its wrappers with ``functools.wraps``, so a
    bridge-generated coroutine carries ``__wrapped__`` while a real
    override does not.
    """

    if not (inspect.iscoroutinefunction(member) or inspect.isasyncgenfunction(member)):
        return False
    return not hasattr(member, "__wrapped__")


def _offenders() -> list[str]:
    """Return public methods that self-call but lack an async override."""

    public = _public_names(GlpiClient)
    call_map = _self_call_map(GlpiClient)
    return sorted(
        name
        for name in public
        if _reaches_public(name, call_map, public)
        and not _is_real_async_override(getattr(AsyncGlpiClient, name))
    )


def test_no_new_self_call_offenders() -> None:
    """No public method may self-call without a hand-written async override."""

    assert set(_offenders()) == set(_KNOWN_UNCOVERED), (
        "The set of bridge self-call offenders changed.\n"
        f"  found:    {sorted(_offenders())}\n"
        f"  expected: {sorted(_KNOWN_UNCOVERED)}\n"
        "A NEW name means a sync body calls a public method through self "
        "with no async override: it will silently drop that call on "
        "AsyncGlpiClient. Add an async override mixin (see "
        "clients/custom/_statistics_async.py) and remove the name here."
    )


def test_guard_detects_the_covered_methods() -> None:
    """The guard must recognise the existing overrides as valid.

    Without this, a guard that classified every method as covered would
    pass ``test_no_new_self_call_offenders`` vacuously.
    """

    for name in ("get_ticket_context", "get_task_statistics", "iter_search_tickets"):
        assert _is_real_async_override(getattr(AsyncGlpiClient, name)), (
            f"{name} should be a hand-written async override"
        )
    assert not _is_real_async_override(AsyncGlpiClient.get_ticket), (
        "get_ticket should be bridge-generated, not a hand-written override"
    )
