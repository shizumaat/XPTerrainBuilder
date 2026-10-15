"""The Qt app's door to the patch editor's engine commands (spec
patch-editor-20261015 §2, protocol 1.12).

The Qt app runs the engine in-process (``EngineSession``); it calls the SAME
functions the JSON-lines transport maps — looked up in the transport's own
command table (``o4_engine.jsonl._build_handlers``), never re-spelled — so a
command the engine does not have (``pack_outlines`` before its lane lands)
is simply absent (:meth:`PatchEngine.has`).

Commands are file work (a patch parse, the staleness stamps) that would
stall the map, so :meth:`PatchEngine.call` runs each on a worker thread and
hands ``callback(result, error)`` back on the GUI thread.  ``pack_objects``
is asynchronous in the engine itself: it replies ``{"status": "started"}``
and completes through the ``PackObjectsReady`` event, which the window
routes to :meth:`PatchEngine.on_pack_objects_ready`.
"""
from __future__ import annotations

import itertools
import threading
import typing as _t

from PySide6.QtCore import QObject, Signal

__all__ = ["PatchEngine"]

Callback = _t.Callable[[_t.Any, _t.Optional[str]], None]


class PatchEngine(QObject):
    """Engine commands for the patch editor, off the GUI thread."""

    _finished = Signal(object, object, object)   # callback, result, error

    def __init__(self, session, parent=None, run_async: bool = True):
        super().__init__(parent)
        self._session = session
        self._run_async = run_async
        self._handlers: dict | None = None
        self._lock = threading.Lock()
        self._pending: dict[str, Callback] = {}
        self._tokens = itertools.count(1)
        self._finished.connect(self._deliver)

    def _table(self) -> dict:
        with self._lock:
            if self._handlers is None:
                from o4_engine import jsonl
                self._handlers = jsonl._build_handlers(self._session)
            return self._handlers

    def has(self, name: str) -> bool:
        """Whether this engine has the command (``pack_outlines`` may not)."""
        return name in self._table()

    def call_now(self, name: str, **kwargs) -> tuple[_t.Any, str | None]:
        """Run the command on THIS thread: ``(result, None)`` or ``(None,
        error sentence)`` (the unsaved-edits prompt's Save, at quit)."""
        try:
            handler = self._table().get(name)
            if handler is None:
                raise ValueError(f"This engine has no {name} command; update the app.")
            return handler(**kwargs), None
        except Exception as exc:              # the engine's sentence
            return None, str(exc) or type(exc).__name__

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
                     callback: Callback) -> None:
        """``pack_objects`` (async in the engine): ``callback(result,
        error)`` once its ``PackObjectsReady`` arrives."""
        token = f"qt-pack-{next(self._tokens)}"
        self._pending[token] = callback

        def started(_reply, error):
            if error is not None and self._pending.pop(token, None) is not None:
                callback(None, error)

        self.call("pack_objects", started, tile=tile, icao=icao,
                  bbox=list(bbox), request=token)

    def on_pack_objects_ready(self, event) -> None:
        """The window's handler for ``PackObjectsReady``."""
        callback = self._pending.pop(getattr(event, "request", None), None)
        if callback is not None:
            error = None if event.result is not None else (
                event.error or "The pack's buildings could not be read.")
            callback(event.result, error)

    @staticmethod
    def _deliver(callback: Callback, result, error) -> None:
        callback(result, error)
