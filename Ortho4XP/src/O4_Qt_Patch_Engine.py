"""The Qt app's door to the patch editor's engine commands (spec
patch-editor-20261015 §2, protocol 1.12).

The Qt app runs the engine in-process (``EngineSession``); it calls the SAME
functions the JSON-lines transport maps — looked up in the transport's own
command table (``o4_engine.jsonl.command_table``), never re-spelled — so a
command the engine does not have (``pack_outlines`` before its lane lands)
is simply absent (:meth:`PatchEngine.has`).

Commands are file work (a patch parse, the staleness stamps) that would
stall the map, so :meth:`PatchEngine.call` runs each on a worker thread and
hands ``callback(result, error)`` back on the GUI thread.  ``pack_objects``
is asynchronous in the engine itself: it replies ``{"status": "started"}``
and completes through the ``PackObjectsReady`` event, which the window
routes to :meth:`PatchEngine.on_pack_objects_ready`.  One box is asked
for once: the map's pack outlines and the 3D preview ask for the same box
(A9) and share the request and its answer (the last box's answer is kept).

:meth:`PatchEngine.run` is the same worker-thread round trip for the 3D
preview's own number crunching (triangulation, the terrain cut-out).

A worker THREAD still shares the GUI's interpreter lock, so the commands
that hold it for seconds (``o4_engine.command_process.COMMANDS``:
``pack_objects``, measured at HECA) run in ONE worker PROCESS instead
(issue #753): the thread only waits on its pipe, the answer comes back
through the same ``callback`` (no ``PackObjectsReady`` round trip), and
the read's session cache lives in that process.  It starts on the first
such call and stops in :meth:`PatchEngine.close` (the window's quit) or
with the app — never an orphan.
"""
from __future__ import annotations

import itertools
import threading
import typing as _t

from PySide6.QtCore import QCoreApplication, QObject, Signal

from o4_engine.command_process import COMMANDS as PROCESS_COMMANDS
from o4_engine.command_process import CommandProcess

__all__ = ["PatchEngine"]

Callback = _t.Callable[[_t.Any, _t.Optional[str]], None]


class PatchEngine(QObject):
    """Engine commands for the patch editor, off the GUI thread."""

    _finished = Signal(object, object, object)   # callback, result, error

    def __init__(self, session, parent=None, run_async: bool = True,
                 isolate: bool | None = None):
        """``isolate`` (default: ``run_async``) answers
        ``PROCESS_COMMANDS`` in the worker process (module doc)."""
        super().__init__(parent)
        self._session = session
        self._run_async = run_async
        self._handlers: dict | None = None
        self._lock = threading.Lock()
        self._pending: dict[str, tuple] = {}
        #: The last ``pack_objects`` box: key → {"callbacks": [...], "reply": (result, error) | None}.
        self._pack: dict[tuple, dict] = {}
        self._tokens = itertools.count(1)
        self._finished.connect(self._deliver)
        #: The worker process for ``PROCESS_COMMANDS`` (``None``: in this process).
        self.process = CommandProcess() if (run_async if isolate is None else isolate) else None
        app = QCoreApplication.instance()
        if self.process is not None and app is not None:
            app.aboutToQuit.connect(self.close)

    def close(self) -> None:
        """Stop the worker process (bounded, idempotent; a later call
        starts a new one)."""
        if self.process is not None:
            self.process.close()

    def _table(self) -> dict:
        with self._lock:
            if self._handlers is None:
                from o4_engine import jsonl
                self._handlers = jsonl.command_table(self._session)
            return self._handlers

    def has(self, name: str) -> bool:
        """Whether this engine has the command (``pack_outlines`` may not)."""
        return name in self._table()

    def call_now(self, name: str, **kwargs) -> tuple[_t.Any, str | None]:
        """Run the command on THIS thread: ``(result, None)`` or ``(None,
        error sentence)`` (the unsaved-edits prompt's Save, at quit)."""
        try:
            if self.process is not None and name in PROCESS_COMMANDS:
                return self.process.call(name, **kwargs), None
            handler = self._table().get(name)
            if handler is None:
                raise ValueError(f"This engine has no {name} command; update the app.")
            return handler(**kwargs), None
        except Exception as exc:              # the engine's sentence
            return None, str(exc) or type(exc).__name__

    def run(self, work: _t.Callable[[], _t.Any], callback: Callback) -> None:
        """``work()`` on a worker thread; ``callback(result, None)`` or
        ``callback(None, error sentence)`` on the GUI thread."""
        def task() -> None:
            try:
                reply = (work(), None)
            except Exception as exc:          # the sentence, not a crash
                reply = (None, str(exc) or type(exc).__name__)
            self._finished.emit(callback, *reply)

        if self._run_async:
            threading.Thread(target=task, daemon=True, name="o4-qt-work").start()
        else:
            task()

    def call(self, name: str, callback: Callback, **kwargs) -> None:
        """Run the command with ``kwargs``; ``callback(result, None)`` or
        ``callback(None, error sentence)`` on the GUI thread."""
        def work() -> None:
            self._finished.emit(callback, *self.call_now(name, **kwargs))

        if self._run_async:
            threading.Thread(target=work, daemon=True, name=f"o4-qt-{name}").start()
        else:
            work()

    def pack_objects(self, tile: str, icao: str, bbox: _t.Sequence[float],
                     callback: Callback, footprints_only: bool = False) -> None:
        """``pack_objects`` (async in the engine): ``callback(result,
        error)`` once its ``PackObjectsReady`` arrives.  A box already asked
        for is not asked again: the callback joins the request, or gets the
        kept answer at once.  ``footprints_only`` (#797) is the map's
        small answer (plan outlines, no massing): the last box of EACH kind
        is kept, so the map and the 3D window never supersede each other."""
        only = bool(footprints_only)
        key = (tile, icao, tuple(round(float(v), 9) for v in bbox), only)
        entry = self._pack.get(key)
        if entry is not None and entry["reply"] is not None:
            callback(*entry["reply"])
            return
        if entry is not None:
            entry["callbacks"].append(callback)
            return
        self._pack = {k: v for k, v in self._pack.items() if k[-1] != only}
        self._pack[key] = {"callbacks": [callback], "reply": None}
        if self.process is not None:          # answered by the process: no event
            def read():                       # skipped if the box moved on meanwhile
                return self.process.call("pack_objects", still_wanted=lambda: key in self._pack,
                                         tile=tile, icao=icao, bbox=list(bbox),
                                         footprints_only=only)
            self.run(read, lambda r, e: self._answer(key, r, e))
            return
        token = f"qt-pack-{next(self._tokens)}"
        self._pending[token] = key

        def started(_reply, error):
            if error is not None and self._pending.pop(token, None) is not None:
                self._answer(key, None, error)

        self.call("pack_objects", started, tile=tile, icao=icao,
                  bbox=list(bbox), request=token, footprints_only=only)

    def _answer(self, key: tuple, result, error) -> None:
        entry = self._pack.get(key)
        if entry is None:
            return
        callbacks, entry["callbacks"] = entry["callbacks"], []
        if error is None:
            entry["reply"] = (result, None)
        else:                                 # a refusal is not kept: ask again next time
            self._pack.pop(key, None)
        for callback in callbacks:
            callback(result, error)

    def on_pack_objects_ready(self, event) -> None:
        """The window's handler for ``PackObjectsReady``."""
        key = self._pending.pop(getattr(event, "request", None), None)
        if key is not None:
            error = None if event.result is not None else (
                event.error or "The pack's buildings could not be read.")
            self._answer(key, event.result, error)

    @staticmethod
    def _deliver(callback: Callback, result, error) -> None:
        callback(result, error)
