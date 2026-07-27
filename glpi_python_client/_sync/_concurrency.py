"""Threading concurrency primitives for the sync client tree.

Hand-written twin of ``glpi_python_client/_async/_concurrency.py`` -- see
that module for why these two files are the only ones not generated.

**This file is not produced by the codegen and must be edited alongside its
async twin.** ``unasync_build.py`` excludes it by name.
"""

from __future__ import annotations

import threading
from typing import Any

#: Lock type guarding OAuth token acquisition on the sync surface.
#:
#: A :class:`threading.Lock`, because one sync client may legitimately be
#: shared across user threads. An :class:`asyncio.Lock` here would bind
#: itself to whichever event loop first contended it and then raise
#: ``RuntimeError: ... bound to a different event loop`` -- or deadlock a
#: thread outright -- for every other caller. That failure is latent:
#: ``acquire()`` resolves the loop only on the contended path, so
#: uncontended use passes and the tests stay green.
Lock = threading.Lock


def gather(*values: Any) -> list[Any]:
    """Return ``values`` unchanged, preserving order.

    This looks like a no-op and is doing real work. On the async side the
    call reads ``await gather(self.a(), self.b())`` and runs the two
    concurrently. Stripping the ``await`` leaves ``gather(self.a(),
    self.b())``, where each argument has already been evaluated -- in
    order -- by the time this is entered. Collecting them is therefore the
    correct and complete synchronous meaning of the same expression.
    """

    return list(values)


__all__ = ["Lock", "gather"]
