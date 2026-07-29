"""The sync concurrency twin behaves as the async one's counterpart.

Hand-written on this side, like ``_concurrency.py`` itself. The async twin
asserts that ``gather`` overlaps work and that concurrent tasks contend the
auth lock; neither claim exists here. What does have to hold is that the
sequential ``gather`` keeps the contract callers actually rely on --
results matched to arguments by position -- and that the lock is a real
mutual-exclusion primitive rather than a no-op stand-in.
"""

from __future__ import annotations

import threading

from glpi_python_client._sync._concurrency import Lock, gather


def test_gather_preserves_argument_order() -> None:
    """Results come back positionally, never in completion order."""

    assert gather("a", "b", "c") == ["a", "b", "c"]


def test_gather_of_nothing_is_empty() -> None:
    """An empty fan-out is legal and yields an empty list."""

    assert gather() == []


def test_the_lock_is_a_real_threading_primitive() -> None:
    """The auth lock actually excludes, so token acquisition cannot race."""

    lock = Lock()
    with lock:
        assert not lock.acquire(blocking=False)
    assert lock.acquire(blocking=False)
    lock.release()


def test_the_lock_serialises_concurrent_threads() -> None:
    """Two threads cannot hold the lock at once."""

    lock = Lock()
    overlaps: list[int] = []
    inside = 0

    def _worker() -> None:
        nonlocal inside
        with lock:
            inside += 1
            overlaps.append(inside)
            inside -= 1

    threads = [threading.Thread(target=_worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert overlaps == [1] * 8
