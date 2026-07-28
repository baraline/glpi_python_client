"""Every method the bundled skills name exists on both clients.

``skills/`` is instructions for an agent, so a wrong name there is not a
typo in prose -- it is a wrong API taught to whatever reads it, and the
resulting code fails at the caller rather than here. Nothing else in the
project looks at these files: they are not imported, not built by Sphinx,
and not touched by mypy or ruff. Between them and the library there is no
gate at all.

That gap has already cost us. The move to a generated sync tree left
``skills/README.md`` instructing readers to write ``async with
GlpiClient(...)`` -- but ``GlpiClient`` is the *synchronous* client, so
the snippet raises ``AttributeError``. Six ``SKILL.md`` files described
"the asynchronous ``glpi_python_client.GlpiClient``" in their frontmatter
``description``, which is the one field an agent reads before deciding to
open the file at all. And ``glpi-client-setup`` credited the async client
with a ``threading.Lock`` around OAuth -- the exact primitive
``_concurrency.py`` documents as a deadlock on that surface, because the
lock is held across an ``await``.

None of that broke a test, a build, or a type check.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from glpi_python_client import AsyncGlpiClient, GlpiClient

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SKILLS_DIR = _REPO_ROOT / "skills"

# ``skills/`` ships in the sdist but not in the wheel, so an installed
# package legitimately has no copy to check.
pytestmark = pytest.mark.skipif(
    not _SKILLS_DIR.is_dir(), reason="skills/ is source-tree material, not in the wheel"
)

#: A method call on a client in a snippet. Both spellings appear: the
#: skills bind the client to ``client`` or, via ``from_env``, to ``glpi``.
_CALL = re.compile(r"\b(?:client|glpi)\.(\w+)\s*\(")

#: Claims that were true of the retired thread-pool bridge and are false
#: now. The last two are subtler than the rest: naming ``GlpiClient`` as
#: asynchronous inverts the two classes, and crediting the async client
#: with a ``threading.Lock`` names the primitive that deadlocks there.
_STALE = (
    r"executor=",
    r"to_thread",
    r"worker thread",
    r"async with GlpiClient",
    r"asynchronous glpi_python_client\.GlpiClient\b",
    r"threading\.Lock[^\n]*AsyncGlpiClient",
)

#: The skills *deny* the bridge's machinery on purpose -- "there is no
#: ``executor=`` argument and no thread pool to size". Denying a thing is
#: the opposite of claiming it, so a hit preceded by a negation is correct
#: prose. Without this the check reports its own corrections as failures.
_NEGATED = re.compile(r"\b(?:no|not|never|retired|removed|deleted)\b[^.]{0,60}$")


def _skill_files() -> list[pathlib.Path]:
    """Return every skill document, including the index README."""

    return [*sorted(_SKILLS_DIR.glob("*/SKILL.md")), _SKILLS_DIR / "README.md"]


def _frontmatter_name(text: str) -> str | None:
    """Return the ``name:`` field of a skill's frontmatter, if it has one.

    Parsed by hand rather than with a YAML library: the frontmatter is a
    handful of flat scalars, and this keeps the test suite from gaining a
    dependency for one field.
    """

    if not text.startswith("---"):
        return None
    _, _, rest = text.partition("---\n")
    front, _, _ = rest.partition("\n---")
    match = re.search(r"^name:\s*(\S+)\s*$", front, re.MULTILINE)
    return match.group(1) if match else None


def _stale_claims(text: str) -> list[tuple[int, str]]:
    """Return ``(lineno, matched text)`` for each unnegated stale claim."""

    hits: list[tuple[int, str]] = []
    for pattern in _STALE:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            preceding = text[max(0, match.start() - 70) : match.start()]
            if _NEGATED.search(preceding.replace("\n", " ")):
                continue
            hits.append((text[: match.start()].count("\n") + 1, match.group(0)))
    return hits


def test_the_scan_finds_skills_and_can_tell_claims_apart() -> None:
    """Positive control: the scans are not vacuous and do discriminate.

    Without this, a regex that stopped matching would leave the checks
    below passing forever without reading anything.
    """

    files = _skill_files()
    assert len(files) > 5, f"only {len(files)} skill files found -- layout changed?"

    calls = sum(len(_CALL.findall(p.read_text(encoding="utf-8-sig"))) for p in files)
    assert calls > 20, f"only {calls} client calls found -- regex broken?"

    assert _stale_claims("Use `async with GlpiClient(...)` and await everything.")
    assert _stale_claims("Pass executor= to size the pool.")
    # The negation carve-out has to hold, or the check fails on the fix.
    assert not _stale_claims("There is no `executor=` argument and no thread pool.")


def test_no_skill_starts_with_a_byte_order_mark() -> None:
    """A BOM hides the frontmatter from anything that reads the file.

    Frontmatter is recognised by the file *starting* with ``---``. Three
    bytes of UTF-8 BOM in front of it mean it does not, so a strict reader
    sees a plain document with no ``name`` and no ``description`` -- and
    the description is what an agent uses to decide whether the skill is
    relevant at all. Six of these files carried one, invisibly, which is
    also why this test reads them as ``utf-8-sig``: tolerant parsing must
    not be what stops anyone noticing.
    """

    offenders = [
        path.relative_to(_REPO_ROOT).as_posix()
        for path in sorted(_SKILLS_DIR.rglob("*.md"))
        if path.read_bytes().startswith(b"\xef\xbb\xbf")
    ]
    assert offenders == [], (
        "these skill files start with a UTF-8 BOM, which hides their "
        "frontmatter:\n" + "\n".join(offenders)
    )


def test_every_skill_name_matches_its_directory() -> None:
    """A skill is addressed by directory; a mismatched ``name`` breaks it."""

    offenders: list[str] = []
    for path in sorted(_SKILLS_DIR.glob("*/SKILL.md")):
        declared = _frontmatter_name(path.read_text(encoding="utf-8-sig"))
        if declared != path.parent.name:
            offenders.append(f"{path.parent.name}: frontmatter name is {declared!r}")
    assert offenders == [], "skill name does not match its directory:\n" + "\n".join(
        offenders
    )


def test_every_method_named_in_a_skill_exists_on_both_clients() -> None:
    """No skill teaches a method that was renamed or removed.

    Checked against *both* classes, because every skill tells the reader
    its snippets work on the other one after dropping ``await``.
    """

    offenders: list[str] = []
    for path in _skill_files():
        rel = path.relative_to(_REPO_ROOT).as_posix()
        for method in sorted(set(_CALL.findall(path.read_text(encoding="utf-8-sig")))):
            for client in (GlpiClient, AsyncGlpiClient):
                if not hasattr(client, method):
                    offenders.append(f"{rel}: {client.__name__} has no {method!r}")
    assert offenders == [], (
        "these skills name methods that do not exist:\n" + "\n".join(offenders)
    )


def test_no_skill_describes_the_retired_thread_pool_bridge() -> None:
    """No skill still explains the async client as a thread-pool wrapper."""

    offenders = [
        f"{path.relative_to(_REPO_ROOT).as_posix()}:{lineno}: {claim!r}"
        for path in _skill_files()
        for lineno, claim in _stale_claims(path.read_text(encoding="utf-8-sig"))
    ]
    assert offenders == [], (
        "these skills describe machinery that no longer exists:\n"
        + "\n".join(offenders)
    )
