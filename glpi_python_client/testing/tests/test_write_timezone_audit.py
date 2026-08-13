"""Audit that every library write serialises on the server's clock.

This is a structural guard, not a behavioural one, and it exists because
the failure it prevents is silent. :func:`model_to_payload` takes
``server_timezone`` as an optional keyword, so a call site that omits it
still returns a valid body, still passes every transport stub, and still
gets a 200 from GLPI. What it does not do is name the right moment: GLPI 11
reads the naive prefix of a timestamp and discards the offset, so an aware
datetime written without the conversion is wrong by that offset -- measured
at up to twelve hours, with nothing in the response to show it.

The rule is that library code calls ``self._body(...)`` on the transport,
which binds the client's timezone once. Tests and the helper's own module
are exempt; nothing else calls :func:`model_to_payload` directly.
"""

from __future__ import annotations

import ast
import pathlib

_PACKAGE_ROOT = pathlib.Path(__file__).resolve().parents[2]

#: Modules allowed to name ``model_to_payload`` directly.
#:
#: ``_payloads`` defines it, and ``_transport`` wraps it in the one helper
#: that supplies the timezone.
_EXEMPT = {"_payloads.py", "_transport.py"}


def _library_modules() -> list[pathlib.Path]:
    """Return every non-test, non-testing module in the package."""

    return [
        path
        for path in sorted(_PACKAGE_ROOT.rglob("*.py"))
        if "tests" not in path.parts
        and "testing" not in path.parts
        and not path.name.startswith("test_")
        and path.name not in _EXEMPT
    ]


def test_no_library_module_serialises_a_body_without_the_server_timezone() -> None:
    """Only the transport helper may call ``model_to_payload``."""

    offenders = [
        f"{path.relative_to(_PACKAGE_ROOT)}:{node.lineno}"
        for path in _library_modules()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "model_to_payload"
    ]

    assert not offenders, (
        "these call model_to_payload directly and so send timestamps GLPI "
        f"will reinterpret; use self._body(...) instead: {offenders}"
    )


def test_the_transport_helper_passes_the_client_timezone() -> None:
    """The one exempt call site actually supplies what the others delegate.

    Without this, the audit above could pass while the helper it points
    everyone at had quietly dropped the argument.
    """

    source = (
        _PACKAGE_ROOT / "_async" / "clients" / "commons" / "_transport.py"
    ).read_text(encoding="utf-8")

    assert "model_to_payload(model, server_timezone=self.server_timezone)" in source
