"""A window's background probe: one in flight, the newest request wins,
cancelled and joined when the window closes (#1546).

A thread per request piled up ~200 reanchor probes in one Qt suite
process (each a full Custom Scenery scan that outlived its window) and
Python 3.14's collector crashed in one of them.  This runner keeps ONE
worker per owner: a request made while it runs replaces the queued one
(superseded requests never run), a result for a superseded or closed
request is dropped, and :meth:`close` stops delivery under the lock and
joins the worker.  The worker holds no Qt object of the window's: it
calls ``work(*args, should_stop=...)`` and hands the result to
``deliver`` — a bridge Signal's ``emit``, the one supported cross-thread
hand-off — never after :meth:`close` has returned.

Plain Python (no Qt import), so the bound is unit-testable headless.
"""

import threading

__all__ = ["LatestProbe"]


class LatestProbe:
    """Single-flight, latest-wins background runner for one owner."""

    def __init__(self, work, deliver, name):
        self._work = work
        self._deliver = deliver
        self._name = name
        self._lock = threading.Lock()
        self._generation = 0
        self._pending = None
        self._thread = None
        self._closed = False

    def submit(self, *args):
        """Ask for a probe of ``args``; supersedes any queued request.
        Thread-safe; a no-op once closed."""
        with self._lock:
            if self._closed:
                return
            self._generation += 1
            self._pending = (self._generation, args)
            if self._thread is None:
                self._thread = threading.Thread(
                    target=self._run, name=self._name, daemon=True)
                self._thread.start()

    def in_flight(self):
        """True while a worker thread is alive for this owner."""
        with self._lock:
            return self._thread is not None

    def close(self, timeout=2.0):
        """Drop queued work, stop delivery, and join the worker (bounded:
        the work's ``should_stop`` turns true at once)."""
        with self._lock:
            self._closed = True
            self._pending = None
            self._deliver = None
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout)

    def _stale(self, generation):
        return self._closed or generation != self._generation

    def _run(self):
        while True:
            with self._lock:
                if self._closed or self._pending is None:
                    self._thread = None
                    return
                generation, args = self._pending
                self._pending = None
            try:
                result = self._work(
                    *args, should_stop=lambda g=generation: self._stale(g))
            except Exception:
                continue
            with self._lock:
                # Under the lock, so close() returning means no emit
                # follows; a queued Signal emit does not block.
                if not self._stale(generation) and self._deliver:
                    self._deliver(result)
