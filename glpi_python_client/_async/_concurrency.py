"""Asyncio concurrency primitives for the async client tree.

This module and its ``_sync`` twin are the only files maintained by hand on
both sides of the codegen. Everything else under ``_sync/`` is generated
from ``_async/`` by :mod:`unasync`, which rewrites tokens and strips
``async``/``await``. That works for syntax; it cannot work here, because the
two surfaces need genuinely *different primitives*, not differently-spelled
ones:

* A fan-out is :func:`asyncio.gather` on this side and plain sequential
  evaluation on the other. ``unasync`` leaves ``asyncio.gather`` untouched,
  so a generated twin would call it from synchronous code and break.
* The auth lock must be an :class:`asyncio.Lock` here and a
  :class:`threading.Lock` there -- see :data:`Lock` for why substituting one
  for the other is wrong in *both* directions.

Keeping both twins tiny is deliberate: hand-maintained duplication is a
liability, so it is confined to the smallest possible surface.
"""

from __future__ import annotations

import asyncio
from typing import Any

#: Lock type guarding OAuth token acquisition on the async surface.
#:
#: An :class:`asyncio.Lock`, and the ``_sync`` twin uses a
#: :class:`threading.Lock`. Neither choice is substitutable for the other,
#: which is exactly why this is hand-written:
#:
#: * A :class:`threading.Lock` here would **deadlock**. The lock is held
#:   across an ``await``, so a second task blocking on it blocks the whole
#:   event loop -- and the task holding it can then never resume to release
#:   it. A single-threaded loop has no way out of that.
#: * An :class:`asyncio.Lock` on the sync side would be worse than useless:
#:   it is bound to the loop that first contends it, so sharing one client
#:   across threads raises ``RuntimeError: ... bound to a different event
#:   loop`` and can deadlock a thread permanently. The failure is latent --
#:   ``acquire()`` only looks up the loop on the *contended* path, so
#:   uncontended use passes and tests stay green.
Lock = asyncio.Lock


async def gather(*awaitables: Any) -> list[Any]:
    """Run ``awaitables`` concurrently and return their results in order.

    The ``_sync`` twin takes already-computed values and simply returns
    them. That is not a stub: once ``unasync`` strips the ``await`` from a
    call site, each argument expression evaluates eagerly at the point it is
    written, which *is* sequential execution. So the same call shape --
    ``await gather(self.a(), self.b())`` -- means "concurrently" here and
    "one after the other" there, with no change to the calling code.
    """

    return list(await asyncio.gather(*awaitables))


__all__ = ["Lock", "gather"]
