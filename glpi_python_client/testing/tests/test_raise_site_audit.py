"""Audit every raise statement in library code against the error contract.

This is a structural guard, not a behavioural one. It exists because the
0.4.0 error migration is a mechanical sweep across raise sites in
non-test library code -- as of this writing 24 ``GlpiValidationError``,
9 ``GlpiProtocolError``, 4 ``RuntimeError``, 2 ``TypeError``,
1 ``GlpiServerError``, plus 2 ``status_error_class(...)`` dispatch sites
(42 total) -- and a missed one is invisible: a bare ValueError still
passes every existing ``pytest.raises(ValueError)`` test.

The RuntimeError and TypeError sites are deliberately exempt. Converting
them to GlpiValidationError -- which inherits ValueError, not TypeError --
would silently break ``except TypeError`` / ``except RuntimeError`` in user
code and the 12 tests in this repo that assert on those two types. See
plan-1 decision D3.
"""

from __future__ import annotations

import ast
import pathlib

_PACKAGE_ROOT = pathlib.Path(__file__).resolve().parents[2]

_ALLOWED = {
    "GlpiValidationError",
    "GlpiProtocolError",
    "GlpiServerError",
    "GlpiStatusError",
    "error_class",  # status_error_class(...) dispatch result
    # transport_error_from(...) returns GlpiTransportError or its
    # GlpiTimeoutError subclass; the AST sees the factory, not the class.
    "transport_error_from",
    "RuntimeError",  # exempt by design -- see module docstring
    "TypeError",  # exempt by design -- see module docstring
}


def _library_modules() -> list[pathlib.Path]:
    """Return every non-test, non-testing module in the package."""

    return [
        path
        for path in sorted(_PACKAGE_ROOT.rglob("*.py"))
        if "tests" not in path.parts
        and "testing" not in path.parts
        and not path.name.startswith("test_")
    ]


def _raise_sites() -> list[tuple[str, int, str]]:
    """Return ``(module, lineno, exception_name)`` for every raise statement."""

    sites: list[tuple[str, int, str]] = []
    for path in _library_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or node.exc is None:
                continue
            exc = node.exc
            name = (
                ast.unparse(exc.func) if isinstance(exc, ast.Call) else ast.unparse(exc)
            )
            sites.append(
                (path.relative_to(_PACKAGE_ROOT).as_posix(), node.lineno, name)
            )
    return sites


def test_the_ast_walk_finds_a_known_raise_site() -> None:
    """Positive control: prove the walk actually finds raise statements.

    If ``_raise_sites`` ever silently returned ``[]`` (e.g. because
    ``_library_modules`` globbed the wrong root, or the AST walk predicate
    stopped matching ``ast.Raise`` nodes), every other test in this module
    would pass vacuously. Pin that at least one known-good, never-removed
    raise site is found so a broken walk fails loudly instead.
    """

    sites = _raise_sites()
    assert sites, "the raise-site walk found nothing -- it is broken"
    # A root one level too shallow finds nothing and fails loudly above. A
    # root one level too deep would still satisfy the endswith below, just
    # with an extra leading segment -- so pin the root itself.
    assert _PACKAGE_ROOT.name == "glpi_python_client", (
        f"_PACKAGE_ROOT resolved to {_PACKAGE_ROOT}, not the package root"
    )
    # clients/commons/_transport.py raises a deliberately-exempt
    # RuntimeError (decision D3) that this migration never touches, making
    # it a stable landmark to confirm the walk actually inspects source.
    transport_modules = {
        site[0]
        for site in sites
        if site[0].endswith("clients/commons/_transport.py")
        and site[2] == "RuntimeError"
    }
    # Both trees, named exactly: _transport.py is generated, so the twin is
    # as much a landmark as the source. Exact paths rather than a suffix
    # test, so a root resolved one level too deep -- which would prefix
    # every path with "glpi_python_client/" and still satisfy endswith --
    # fails here instead of passing quietly.
    assert transport_modules == {
        "_async/clients/commons/_transport.py",
        "_sync/clients/commons/_transport.py",
    }, (
        "the raise-site walk did not find the known RuntimeError raise in "
        "both copies of clients/commons/_transport.py -- it is not actually "
        f"walking the package. Found: {sorted(transport_modules)}"
    )


def test_no_bare_value_error_is_raised_by_library_code() -> None:
    """Every caller-facing error is typed; bare ``ValueError`` is gone."""

    offenders = [site for site in _raise_sites() if site[2] == "ValueError"]
    assert offenders == [], f"bare ValueError raise sites remain: {offenders}"


def test_no_third_party_http_exception_is_raised_by_library_code() -> None:
    """The library never raises a third-party HTTP exception directly.

    Both spellings are checked, not just the transport currently in use: the
    point of the audit is that a raise site cannot drift back to a
    third-party type, and naming only the current library would let the
    previous one silently reappear.
    """

    offenders = [
        site for site in _raise_sites() if site[2].startswith(("requests.", "httpx."))
    ]
    assert offenders == [], f"third-party exception raise sites remain: {offenders}"


def test_every_raise_site_uses_an_allowed_exception() -> None:
    """No raise site drifts outside the documented error contract."""

    offenders = [site for site in _raise_sites() if site[2] not in _ALLOWED]
    assert offenders == [], f"unexpected raise sites: {offenders}"
