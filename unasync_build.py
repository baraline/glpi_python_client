"""Generate the synchronous client tree from the asynchronous one.

``glpi_python_client/_async/`` is the only hand-written client source.
``glpi_python_client/_sync/`` is produced from it by :mod:`unasync`, checked
into the repository, and verified in CI with ``--check``. Editing anything
under ``_sync/`` by hand is a mistake the check will catch.

Usage
-----
``python unasync_build.py``          regenerate ``_sync/`` in place
``python unasync_build.py --check``  fail if ``_sync/`` is stale (CI gate)

What the codegen does and does not do
-------------------------------------
:mod:`unasync` is a token-level rewriter. It strips ``async``/``await`` and
substitutes whole NAME tokens listed in the rule. Three consequences shape
this build:

* It matches **single NAME tokens only**. A dotted key such as
  ``"asyncio.Lock"`` can never match, and supplying one fails *silently* --
  the rule is accepted and simply never fires. Anything needing a dotted
  name is handled by the hand-written ``_concurrency.py`` twins instead.
* It rewrites a **string literal whose entire content** is a substitution
  key. That is what makes ``__all__ = ["AsyncGlpiClient"]`` generate
  correctly. It is narrow: an embedded mention inside a longer string is
  left alone. That is right for prose but wrong for a *qualified path*
  written in prose, so this script repoints those itself -- see
  :data:`PROSE_PACKAGE_PREFIX`.
* It leaves ``asyncio.gather`` and friends **intact**, which would produce
  broken sync code. Those live only in ``_concurrency.py``, which is
  excluded from generation and hand-written on both sides.
"""

from __future__ import annotations

import argparse
import difflib
import pathlib
import shutil
import sys
import tempfile

import unasync

REPO_ROOT = pathlib.Path(__file__).resolve().parent
PACKAGE = REPO_ROOT / "glpi_python_client"
ASYNC_DIR = PACKAGE / "_async"
SYNC_DIR = PACKAGE / "_sync"

#: Files that are hand-written on *both* sides and never generated.
#:
#: ``_concurrency.py`` is where the two trees genuinely differ in kind
#: rather than in syntax: a fan-out is ``asyncio.gather`` on one side and
#: plain sequential evaluation on the other, and the auth lock is an
#: ``asyncio.Lock`` on one side and a ``threading.Lock`` on the other.
#: Token substitution cannot express either, so both files are maintained
#: by hand and kept deliberately tiny.
#:
#: ``test_concurrency.py`` follows for the same reason. "Two tasks contend
#: the lock without deadlocking" has no sync twin worth generating -- the
#: sync side asserts that ``gather`` preserves order and evaluates in
#: sequence, which is a different claim about a different primitive.
#:
#: Entries are paths relative to each tree's root, not bare filenames. A
#: bare name would exempt *any* file so called at *any* depth, and the
#: omission would be invisible: the scratch tree and ``_sync/`` would agree
#: on its absence, so ``--check`` would stay green while a whole module
#: silently had no twin. Colocated tests make that collision plausible --
#: generic names like ``test_concurrency.py`` now recur per package.
HAND_WRITTEN = {"_concurrency.py", "tests/test_concurrency.py"}

#: Token substitutions beyond unasync's defaults.
#:
#: The defaults cover the language-level names (``__aenter__``,
#: ``AsyncIterator``, ``StopAsyncIteration``, ...). These cover the two
#: things the defaults get wrong or do not know about:
#:
#: * **httpx naming.** unasync's built-in ``Async*`` -> ``Sync*`` convention
#:   would produce ``SyncClient``, which does not exist; the real name is
#:   ``Client``. Same for the transport classes.
#: * **This package's own public class name**, which differs between the two
#:   surfaces by design.
#:
#: Everything else -- mixins, helpers, module names -- is spelled
#: *identically* in both trees. Keeping the rename list this short is
#: deliberate: every entry is a chance for a silent collision, and the
#: shorter the list, the smaller that surface.
TOKEN_REPLACEMENTS = {
    # Intra-tree imports are absolute, so the package segment itself is a
    # NAME token and rewriting it repoints every one of them at the
    # generated tree. This is why no module needs relative imports.
    "_async": "_sync",
    "AsyncGlpiClient": "GlpiClient",
    "AsyncClient": "Client",
    "AsyncBaseTransport": "BaseTransport",
    "AsyncHTTPTransport": "HTTPTransport",
    "aclose": "close",
    "aread": "read",
}


#: The qualified package prefix, and what it becomes in the generated tree.
#:
#: In an ``import`` statement ``_async`` is its own NAME token, so unasync
#: repoints every intra-tree import for free. Inside a docstring the whole
#: thing is a *single* string token, and substitution only fires when a
#: literal's entire content is a key -- so a cross-reference such as
#: ``:mod:`glpi_python_client._async.clients.api``` sails through untouched
#: and the generated client documents itself in terms of the other tree.
#:
#: Rewriting the qualified prefix afterwards is safe precisely because it is
#: qualified: it names this package and a tree that the generated code must
#: never mention. A bare ``_async`` in prose would be ambiguous; this is not.
#: ``tests/test_unasync_codegen.py`` holds the invariant from the other end,
#: asserting the generated tree contains no ``_async`` at all -- which also
#: fails if someone writes a bare mention this rewrite cannot see.
PROSE_PACKAGE_PREFIX = ("glpi_python_client._async", "glpi_python_client._sync")


def _source_files() -> list[pathlib.Path]:
    """Return every ``_async/`` module that should be generated from."""

    return sorted(
        path
        for path in ASYNC_DIR.rglob("*.py")
        if (
            path.relative_to(ASYNC_DIR).as_posix() not in HAND_WRITTEN
            and "__pycache__" not in path.parts
        )
    )


def _repoint_prose(into: pathlib.Path, generated: list[pathlib.Path]) -> None:
    """Point qualified package paths in the generated files at the sync tree.

    Runs over the freshly written modules only, and is idempotent: unasync
    has already turned the import statements into ``_sync``, so the stale
    prefix survives nowhere but inside string literals.
    """

    stale, fresh = PROSE_PACKAGE_PREFIX
    for rel in generated:
        path = into / rel
        text = path.read_text(encoding="utf-8")
        if stale in text:
            path.write_text(text.replace(stale, fresh), encoding="utf-8")


def _generate(into: pathlib.Path) -> None:
    """Run unasync over the async tree, writing the sync tree into ``into``."""

    rule = unasync.Rule(
        fromdir=str(ASYNC_DIR),
        todir=str(into),
        additional_replacements=TOKEN_REPLACEMENTS,
    )
    sources = _source_files()
    unasync.unasync_files([str(p) for p in sources], [rule])
    _repoint_prose(into, [p.relative_to(ASYNC_DIR) for p in sources])

    # The hand-written twins are never generated. When building into a
    # scratch directory for --check they must still be carried across, or
    # the comparison would report them as missing from the generated tree
    # and demand their deletion. Generating in place leaves them untouched.
    if into == SYNC_DIR:
        return
    for rel in sorted(HAND_WRITTEN):
        target = into / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SYNC_DIR / rel, target)


def _relative_sync_files(root: pathlib.Path) -> dict[pathlib.Path, str]:
    """Return ``{relative path: text}`` for every module under ``root``."""

    return {
        path.relative_to(root): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*.py"))
        if "__pycache__" not in path.parts
    }


def _check() -> int:
    """Regenerate into a temp dir and report any drift from the checked-in tree."""

    with tempfile.TemporaryDirectory() as tmp:
        scratch = pathlib.Path(tmp) / "_sync"
        _generate(scratch)
        expected = _relative_sync_files(scratch)
        actual = _relative_sync_files(SYNC_DIR)

    problems: list[str] = []
    for rel in sorted(set(expected) | set(actual)):
        want = expected.get(rel)
        have = actual.get(rel)
        if want == have:
            continue
        if want is None:
            problems.append(f"{rel}: present in _sync/ but not generated by _async/")
            continue
        if have is None:
            problems.append(
                f"{rel}: missing from _sync/ -- run: python unasync_build.py"
            )
            continue
        diff = "".join(
            difflib.unified_diff(
                have.splitlines(keepends=True),
                want.splitlines(keepends=True),
                fromfile=f"_sync/{rel} (checked in)",
                tofile=f"_sync/{rel} (regenerated)",
            )
        )
        problems.append(diff)

    if problems:
        print("_sync/ is out of date with respect to _async/.\n")
        print("\n".join(problems))
        print(
            "\nThe sync tree is generated. Edit glpi_python_client/_async/ and "
            "run `python unasync_build.py`."
        )
        return 1

    print(f"_sync/ is up to date ({len(actual)} modules).")
    return 0


def main() -> int:
    """Entry point for both regeneration and the CI staleness check."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify _sync/ matches what _async/ generates instead of writing it",
    )
    args = parser.parse_args()

    if not ASYNC_DIR.is_dir():
        print(f"no async source tree at {ASYNC_DIR}", file=sys.stderr)
        return 1
    if args.check:
        return _check()

    _generate(SYNC_DIR)
    print(f"regenerated {SYNC_DIR} from {len(_source_files())} async modules.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
