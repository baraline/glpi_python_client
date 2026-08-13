"""Parse every Python snippet in the skills, the guide and the README.

The snippets are the package's primary teaching surface -- nine ``SKILL.md``
files an agent reads before writing any GLPI code -- and nothing compiles
them. A sweep that adds an argument to every client construction example can
therefore leave a duplicated keyword or a broken indent in a block that still
*looks* right in a diff, and the first thing to notice is whoever copies it.

This guard only compiles: a snippet is checked for syntax, not executed and
not type-checked. That is deliberate -- most blocks are fragments referring
to names they never define -- but it is enough to catch the class of damage a
mechanical edit does.

It uses :func:`compile` rather than :func:`ast.parse` because the two differ
on exactly the case that prompted it. ``ast.parse`` accepts a call with the
same keyword twice; the duplicate is rejected later, when the tree is
compiled. A sweep that inserts an argument into every construction example
can produce precisely that, so parsing alone would have passed the file it
was written to catch.

``PyCF_ALLOW_TOP_LEVEL_AWAIT`` is set because most async examples are
fragments -- ``ticket = await client.get_ticket(1)`` with no surrounding
``async def``, which is how they are meant to be read. Without the flag the
guard would reject 28 perfectly good snippets and teach whoever hit it to
wrap examples in scaffolding no reader needs.

Blocks that are illustrative rather than runnable opt out with a
``# doc: no-parse`` comment on the fence line.
"""

from __future__ import annotations

import ast
import pathlib
import re
import textwrap

import pytest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

#: A fenced block introduced as Python, capturing any fence-line flags.
_MARKDOWN_BLOCK = re.compile(
    r"^```py(?:thon)?[^\S\n]*(?P<flags>[^\n]*)\n(?P<code>.*?)^```",
    re.MULTILINE | re.DOTALL,
)

#: A Sphinx ``code-block:: python`` and everything indented beneath it.
_RST_BLOCK = re.compile(
    r"^\.\.[^\S\n]+code-block::[^\S\n]+python\n"
    r"(?:^[^\S\n]+:[a-z]+:[^\n]*\n)*"
    r"\n"
    r"(?P<code>(?:^(?:[^\S\n]+[^\n]*)?\n)+)",
    re.MULTILINE,
)


def _documents() -> list[pathlib.Path]:
    """Return every file whose Python snippets are meant to be copied."""

    return [
        *sorted((_REPO_ROOT / "skills").rglob("SKILL.md")),
        *sorted((_REPO_ROOT / "docs").rglob("*.rst")),
        _REPO_ROOT / "README.md",
    ]


def _snippets() -> list[tuple[str, str]]:
    """Return every ``(location, source)`` pair worth parsing."""

    found: list[tuple[str, str]] = []
    for path in _documents():
        text = path.read_text(encoding="utf-8")
        where = path.relative_to(_REPO_ROOT).as_posix()
        pattern = _RST_BLOCK if path.suffix == ".rst" else _MARKDOWN_BLOCK
        for match in pattern.finditer(text):
            if "no-parse" in (match.groupdict().get("flags") or ""):
                continue
            line = text[: match.start()].count("\n") + 1
            found.append((f"{where}:{line}", textwrap.dedent(match["code"])))
    return found


def test_the_documents_actually_contain_snippets() -> None:
    """Guard the guard: a broken regex must not silently check nothing."""

    assert len(_snippets()) > 40


@pytest.mark.parametrize(
    ("location", "source"), _snippets(), ids=[where for where, _ in _snippets()]
)
def test_documentation_snippet_compiles(location: str, source: str) -> None:
    """Every documented snippet is syntactically valid Python."""

    try:
        compile(source, location, "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
    except SyntaxError as error:  # pragma: no cover - the message is the point
        pytest.fail(f"{location} does not compile: {error}")
