"""The transport's view lane (#2061): the map's patch reads never queue
behind the serial command loop.

The JSON-lines transport answers commands one at a time on its read loop.
At an app's launch that loop is busy for seconds (MEASURED on the owner's
install, 1,474 packs: ``reanchor_status`` 2.9 s, ``custom_patches`` 0.7 s
among a dozen launch commands), so the patch of the airport the user just
zoomed to waited behind all of it before its own read even started.

:data:`VIEW_COMMANDS` are the reads that put the airport in view on the
map: each runs on ONE view worker thread, in arrival order among
themselves, beside the read loop.  They are the same functions the Qt app
already runs on worker threads beside its session (``O4_Qt_Patch_Engine``)
-- read-only file work, no session state.  The patch WRITES
(``patch_save``, ``patch_revert``, ...) stay on the read loop; an app sends
a read of a written patch only after the write's reply.

:data:`OWN_THREAD_COMMANDS` are slow reads whose answer only completes the
view (``patch_staleness``: 11-24 s in a fresh engine on that install): each
runs on its own thread so the next patch in view does not wait for it.
"""
from __future__ import annotations

import queue
import threading
import typing as _t

__all__ = ["VIEW_COMMANDS", "OWN_THREAD_COMMANDS", "ViewLane"]

#: Commands answered on the view worker, never behind the read loop.
VIEW_COMMANDS = frozenset({"patch_list", "patch_load", "pack_outlines"})

#: Commands answered each on its own thread (slow, read-only).
OWN_THREAD_COMMANDS = frozenset({"patch_staleness"})

Run = _t.Callable[[], None]


class ViewLane:
    """Runs view commands off the read loop; :meth:`drain` waits for them."""

    def __init__(self) -> None:
        self._queue: "queue.Queue[Run | None]" = queue.Queue()
        self._worker: threading.Thread | None = None
        self._lock = threading.Lock()
        self._threads: list[threading.Thread] = []

    @staticmethod
    def takes(command: _t.Any) -> bool:
        """Whether ``command`` is answered here instead of on the loop."""
        return command in VIEW_COMMANDS or command in OWN_THREAD_COMMANDS

    def submit(self, command: str, run: Run) -> None:
        """Answer ``command`` by calling ``run`` (which writes its reply)."""
        if command in OWN_THREAD_COMMANDS:
            thread = threading.Thread(target=run, daemon=True,
                                      name="o4-engine-" + command)
            with self._lock:
                self._threads = [t for t in self._threads if t.is_alive()]
                self._threads.append(thread)
            thread.start()
            return
        with self._lock:
            if self._worker is None:
                self._worker = threading.Thread(
                    target=self._serve, daemon=True, name="o4-engine-view")
                self._worker.start()
            self._queue.put(run)

    def _serve(self) -> None:
        while True:
            run = self._queue.get()
            if run is None:
                return
            run()

    def drain(self, timeout: float = 30.0) -> None:
        """Let every submitted command reply (the transport's end of input)."""
        with self._lock:
            worker, self._worker = self._worker, None
            threads, self._threads = self._threads, []
            if worker is not None:
                self._queue.put(None)
        if worker is not None:
            worker.join(timeout)
        for thread in threads:
            thread.join(timeout)
