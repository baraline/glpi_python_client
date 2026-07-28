"""Guard against a test silently disappearing during the colocation move.

The migration relocates individual test functions between files. Nothing
in the suite fails if one is dropped on the way, so this records the set
of collected test function names up front and re-checks it after every
slice.

Usage
-----
``python scripts/check_test_names.py --baseline``  write the baseline
``python scripts/check_test_names.py --verify``    fail on any name lost
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
BASELINE = REPO_ROOT / ".test-name-baseline.txt"


def collect() -> set[str]:
    """Return the bare name of every collected test function."""

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-m",
            "not integration",
            "--collect-only",
            "-q",
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit("collection failed")

    names: set[str] = set()
    for line in result.stdout.splitlines():
        if "::" not in line:
            continue
        names.add(line.split("::")[-1].split("[")[0].strip())
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--baseline", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    names = collect()

    if args.baseline:
        BASELINE.write_text("\n".join(sorted(names)) + "\n", encoding="utf-8")
        print(f"baseline written: {len(names)} unique test function names")
        return 0

    expected = set(BASELINE.read_text(encoding="utf-8").split())
    missing = sorted(expected - names)
    if missing:
        print(f"{len(missing)} test function name(s) no longer collected:")
        for name in missing:
            print(f"  {name}")
        return 1
    print(f"all {len(expected)} baseline names still collected ({len(names)} total)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
