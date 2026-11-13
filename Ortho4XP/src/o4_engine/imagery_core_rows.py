"""The Build view's row for each tile whose airport cores are sharpening
(#2039, owner 2026-11-13T04:32Z: background imagery work shows a row).

``imagery_after_build.fetch_cores`` lands the core squares of every
tile handed to it -- after a build in on-demand mode, the World publish
(``world_publish._sharpen``), a flight's kept endpoints (#2028) and the
adopt's ``world_adopt.keep_cores``.  Each batch reports here
(:class:`CoreRows`): one ``ImageryCoresProgress`` per tile when it
starts, one per landed or failed square, and its outcome.  The session
watcher (``imagery_after_build.watch``) names the sink (:func:`set_sink`,
the session's own ``_emit``), so every batch reaches both apps, which
show it in the Activity list (``O4_Imagery_OnDemand_Text.cores_row_status``).

Stop (:func:`stop`, engine command ``imagery_cores_stop``): the tile's
squares not yet started are left as they are (the follow job sharpens
them when X-Plane flies near); the ones landing finish.
"""
from __future__ import annotations

import threading
from typing import Callable, Dict, Optional, Tuple

__all__ = ["set_sink", "stop", "stopped", "CoreRows", "imagery_cores_stop"]

_LOCK = threading.Lock()
_SINK: "list[Optional[Callable]]" = [None]
#: Tiles a batch is sharpening now.
_LIVE: set = set()
#: Tiles the user stopped, until their batch ends.
_STOPPED: set = set()

Tile = Tuple[int, int]


def set_sink(emit: Optional[Callable]) -> None:
    """Send every batch's rows to ``emit`` (an ``EngineSession._emit``);
    None sends them nowhere."""
    with _LOCK:
        _SINK[0] = emit


def stop(lat: int, lon: int) -> bool:
    """Stop tile ``(lat, lon)``'s sharpening; False when none runs."""
    tile = (int(lat), int(lon))
    with _LOCK:
        live = tile in _LIVE
        if live:
            _STOPPED.add(tile)
    return live


def stopped(lat: int, lon: int) -> bool:
    with _LOCK:
        return (int(lat), int(lon)) in _STOPPED


def imagery_cores_stop(lat=None, lon=None, **_ignored) -> dict:
    """ENGINE COMMAND ``imagery_cores_stop``: the row's stop button.
    ``{"stopped": bool}``."""
    return {"stopped": stop(int(lat), int(lon))}


class CoreRows:
    """One batch's rows: ``totals`` squares per tile (a tile with none has
    no row)."""

    def __init__(self, totals: Dict[Tile, int]):
        self._counts = {tile: {"done": 0, "failed": 0, "skipped": 0,
                               "total": int(n)}
                        for tile, n in totals.items() if n > 0}
        with _LOCK:
            _LIVE.update(self._counts)
        for tile in self._counts:
            self._emit(tile, "active")

    def landed(self, tile: Tile, ok: bool) -> None:
        self._step(tile, "done" if ok else "failed")

    def skipped(self, tile: Tile) -> None:
        self._step(tile, "skipped")

    def _step(self, tile: Tile, key: str) -> None:
        counts = self._counts.get(tuple(tile))
        if counts is None:
            return
        counts[key] += 1
        self._emit(tuple(tile), "active")

    def finish(self) -> None:
        """Each tile's outcome: ``done``, ``error`` (a square failed) or
        ``stopped`` (stopped, or left for a build)."""
        for tile, counts in self._counts.items():
            self._emit(tile, _outcome(counts))
        with _LOCK:
            _LIVE.difference_update(self._counts)
            _STOPPED.difference_update(self._counts)

    def _emit(self, tile: Tile, state: str) -> None:
        with _LOCK:
            emit = _SINK[0]
        if emit is None:
            return
        from .events import ImageryCoresProgress
        counts = self._counts[tile]
        try:
            emit(ImageryCoresProgress(
                lat=tile[0], lon=tile[1], state=state,
                done=counts["done"], failed=counts["failed"],
                total=counts["total"]))
        except Exception:               # a row is never worth the batch
            pass


def _outcome(counts: Dict[str, int]) -> str:
    """The row's last state for a batch's ``counts`` of one tile."""
    if counts["failed"]:
        return "error"
    if counts["skipped"] or counts["done"] < counts["total"]:
        return "stopped"
    return "done"

