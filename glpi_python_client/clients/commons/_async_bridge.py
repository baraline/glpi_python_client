"""Synchronous-to-asynchronous bridge for the GLPI client.

The bridge inspects every public sync method exposed by the bases of a
subclass, then installs a coroutine wrapper on the subclass that defers
the blocking call to a worker thread. This keeps the synchronous client
as the single source of truth while still exposing a fully asynchronous
public surface.

Concurrency notes
-----------------
* Each wrapped call runs on a worker thread, which means concurrent
  callers contend on OS threads rather than only on the event loop. The
  underlying transport mixin protects shared state with a
  :class:`threading.Lock` for that reason.
* When many coroutines fan out at once (for example through
  :func:`asyncio.gather`) the default :func:`asyncio.to_thread`
  executor can become a bottleneck. The
  :class:`~glpi_python_client.clients.AsyncGlpiClient` exposes an
  optional ``executor`` constructor argument that callers can use to
  supply a dedicated :class:`concurrent.futures.ThreadPoolExecutor`.
* Cancellation is best-effort: cancelling the awaiting coroutine
  releases the awaiter immediately, but the in-flight HTTP request keeps
  running on the worker thread until ``requests`` returns. This matches
  the behaviour of the original async client.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
from collections.abc import Callable
from concurrent.futures import Executor
from typing import Any


class AsyncBridge:
    """Base class that converts inherited sync methods into coroutines.

    The bridge is intended to be mixed into the most-derived async
    client class **before** the sync mixins so its
    :meth:`__init_subclass__` hook can observe the full MRO and install
    coroutine wrappers on the subclass for every public method that the
    sync mixins expose.

    Subclasses may also assign a :class:`concurrent.futures.Executor`
    instance to ``_executor`` to route every wrapped call through a
    dedicated pool. When ``_executor`` is ``None`` the bridge falls back
    to :func:`asyncio.to_thread`, which uses the default loop executor.
    """

    _executor: Executor | None = None

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Install async wrappers for every inherited public sync method.

        The hook walks the resolution order from the most-derived sync
        base downwards and skips:

        * the bridge class itself and :class:`object`,
        * names that start with an underscore (private/protected),
        * attributes that are not callable, and
        * attributes that are already coroutine functions (so the
          subclass may declare hand-written async overrides such as
          :meth:`get_ticket_context`).

        Each surviving method is wrapped with a coroutine that defers
        the blocking call to a worker thread.
        """

        super().__init_subclass__(**kwargs)
        seen: set[str] = set()
        for base in cls.__mro__:
            if base in (cls, AsyncBridge, object):
                continue
            for name, member in vars(base).items():
                if name in seen or name.startswith("_"):
                    continue
                if not callable(member) or inspect.iscoroutinefunction(member):
                    continue
                # Skip if the subclass already overrides the method with
                # a coroutine function (for example async fan-outs).
                existing = getattr(cls, name, None)
                if existing is not None and inspect.iscoroutinefunction(existing):
                    seen.add(name)
                    continue
                seen.add(name)
                setattr(cls, name, _make_async_wrapper(member))


def _make_async_wrapper(sync_func: Callable[..., Any]) -> Callable[..., Any]:
    """Return one coroutine wrapper that runs ``sync_func`` off-thread.

    Parameters
    ----------
    sync_func : Callable[..., Any]
        Synchronous callable inherited from a sync mixin.

    Returns
    -------
    Callable[..., Any]
        Coroutine function that schedules ``sync_func`` on the bound
        client's executor (or :func:`asyncio.to_thread` when no
        executor is configured) and awaits its result.
    """

    @functools.wraps(sync_func)
    async def wrapper(self: AsyncBridge, *args: Any, **kwargs: Any) -> Any:
        bound = functools.partial(sync_func, self, *args, **kwargs)
        if self._executor is not None:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(self._executor, bound)
        return await asyncio.to_thread(bound)

    return wrapper


__all__ = ["AsyncBridge"]
