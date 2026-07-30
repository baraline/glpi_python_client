"""Every qualified cross-reference in the package points at something real.

Sphinx cannot provide this guarantee. ``nitpicky`` is off, so an
unresolvable ``:class:`` or ``:mod:`` target renders as plain text
instead of failing the build -- and most of these modules are private,
so autodoc never visits them in the first place. A reference to a module
that was since renamed or deleted therefore rots in complete silence.

That is not hypothetical. The move to a generated sync tree renamed one
client module and deleted four others, and seven docstring references to
them survived the rewrite with a green suite, a green ``-W`` docs build,
and a clean codegen diff. This test is the check that would have caught
them, so the next rename cannot repeat it.
"""

from __future__ import annotations

import importlib
import pathlib
import re

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_PACKAGE = _REPO_ROOT / "glpi_python_client"

#: A qualified reference to this package: the root name plus at least one
#: dotted segment. Bare mentions are excluded on purpose -- ``GlpiClient``
#: on its own is prose, not a reference that can rot.
_REFERENCE = re.compile(r"\bglpi_python_client(?:\.[A-Za-z_]\w*)+")


def _resolves(dotted: str) -> bool:
    """Return whether ``dotted`` names a real module or attribute chain.

    Tries the longest importable module prefix first, then walks the
    remainder with :func:`getattr`. A reference may end in a module, a
    class, or a method, and all three have to be accepted.
    """

    parts = dotted.split(".")
    for stop in range(len(parts), 0, -1):
        try:
            target: object = importlib.import_module(".".join(parts[:stop]))
        except ImportError:
            continue
        for attribute in parts[stop:]:
            if hasattr(target, attribute):
                target = getattr(target, attribute)
                continue
            # Pydantic v2 moves declared fields into ``model_fields`` and
            # takes them out of the class namespace, so ``hasattr`` says no
            # to a field that autodoc documents perfectly well. Accepting
            # them matters: without this the check reports noise, and a
            # check that cries wolf gets deleted.
            fields = getattr(target, "model_fields", None)
            if isinstance(fields, dict) and attribute in fields:
                return True
            return False
        return True
    return False


def _reference_sites() -> list[tuple[str, int, str]]:
    """Return ``(module, lineno, reference)`` for every qualified mention."""

    sites: list[tuple[str, int, str]] = []
    this_module = pathlib.Path(__file__).resolve()
    for path in sorted(_PACKAGE.rglob("*.py")):
        # This module names dead targets on purpose, as controls.
        if "__pycache__" in path.parts or path.resolve() == this_module:
            continue
        rel = path.relative_to(_REPO_ROOT).as_posix()
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for match in _REFERENCE.findall(line):
                sites.append((rel, lineno, match.rstrip(".")))
    return sites


def test_the_scan_finds_references_and_can_tell_them_apart() -> None:
    """Positive control: the scan is not vacuous and ``_resolves`` discriminates.

    Without this, a regex that stopped matching would turn the check
    below into a test that passes forever without looking at anything.
    """

    sites = _reference_sites()
    assert len(sites) > 50, f"only {len(sites)} references found -- regex broken?"

    assert _resolves("glpi_python_client.GlpiClient")
    assert _resolves("glpi_python_client.AsyncGlpiClient.get_ticket_context")
    assert _resolves("glpi_python_client._async.clients.commons._transport")
    # One of the targets the codegen rewrite actually left behind.
    assert not _resolves(
        "glpi_python_client._async.clients.async_client.AsyncGlpiClient"
    )
    assert not _resolves("glpi_python_client.nope")


def test_every_qualified_reference_resolves() -> None:
    """No docstring names a module, class, or method that does not exist."""

    offenders = [
        f"{module}:{lineno}: {reference}"
        for module, lineno, reference in _reference_sites()
        if not _resolves(reference)
    ]
    assert offenders == [], (
        "these references point at nothing -- the target was renamed or "
        "deleted and the docstring was not updated:\n" + "\n".join(offenders)
    )
