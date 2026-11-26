"""The staged sweep (#2175, RULINGS 2026-11-19e): a built tile that
waits staged goes into the World pack as soon as X-Plane is not loading
it, with no build or flight needed to revisit it.

``world_publish`` stages and swaps a Build-tab tile at once, X-Plane
running or not; only while X-Plane holds one of the tile's files open
(``xplane_open_files.loading``) does it wait staged (:func:`add_waiting`).
The sweep swaps those tiles in (``world_publish._swap_waiting``, the
``swap_in`` lines of ``logs/world_pack.log``):

* at the engine's start, with every verified tile an earlier run left
  staged (:meth:`Sweeper.poke` ``leftovers=True``, on the thread);
* after each publish (:meth:`Sweeper.poke`);
* every :data:`SWEEP_EVERY_S` seconds while a tile waits, on one thread
  that ends when nothing waits (a window that never stages holds none).

A tile swapped over a version X-Plane loaded this session
(:func:`note_swapped`) raises the "tiles" reload offer
(``reload_offer``): X-Plane shows the new tile at its next load of it or
when the user clicks "Reload scenery".  :class:`WorldTilesWaiting
<o4_engine.events.WorldTilesWaiting>` tells both apps which tiles wait,
which a reload would show and which did not go in at all
(``world_publish_failed``, #2226), whenever a list changes.

Tiles the build-ahead or flight jobs stage are theirs
(``world_job_run._PackPublisher``, ``flight_swap_reload``): the sweep
takes only the tiles named above.  No tile or airport is named here.
"""
from __future__ import annotations

import os
import threading
from typing import Callable, Iterable, Optional

import O4_World_Pack as WP

from . import world_commands as WORLD
from . import world_publish_failed as FAILED

__all__ = ["SWEEP_EVERY_S", "attach", "add_waiting", "note_swapped"]

#: Seconds between two sweeps while a tile waits (the owner: "retry
#: within seconds").
SWEEP_EVERY_S = 5.0

_LOCK = threading.Lock()
#: ``(lat, lon)`` tiles of ours waiting staged.
_WAITING: set = set()
#: Tile names swapped in over a version X-Plane loaded this session.
_RELOAD: set = set()


def _staged(lat: int, lon: int) -> bool:
    return os.path.isfile(os.path.join(
        WORLD.staging_root(), WP.tile_name(lat, lon), WP.dsf_relpath(lat, lon)))


def add_waiting(lat: int, lon: int) -> None:
    """Tile ``(lat, lon)`` was published staged: sweep it."""
    with _LOCK:
        _WAITING.add((int(lat), int(lon)))


def waiting_tiles() -> list:
    """The waiting tiles still staged, ``[(lat, lon)]`` (the rest are
    forgotten)."""
    with _LOCK:
        _WAITING.intersection_update(
            {tile for tile in _WAITING if _staged(*tile)})
        return sorted(_WAITING)


def note_swapped(scenery_dir: str, names: Iterable[str]) -> list:
    """Tiles ``names`` went into the pack: the ones X-Plane loaded this
    session (its ``Log.txt``, ``world_commands.xplane_reads``) raise the
    "tiles" reload offer; those names."""
    from . import reload_offer as RELOAD
    names = list(names)
    if not names or not scenery_dir:
        return []
    reads = WORLD.xplane_reads(scenery_dir)
    if not reads.get("xplane_running"):
        return []
    loads = reads.get("loads") or {}
    hit = [name for name in names if WP.parse_tile(name) in loads]
    if hit:
        RELOAD.offer("tiles")
        with _LOCK:
            _RELOAD.update(hit)
    return hit


def reload_tiles() -> list:
    """The tile names a reload would show, while the "tiles" offer stands
    (the user's "Reload scenery" clears it, and so these)."""
    from . import reload_offer as RELOAD
    with _LOCK:
        if RELOAD.current() != "tiles":
            _RELOAD.clear()
        return sorted(_RELOAD)


def _any_staged() -> bool:
    try:
        return any(not name.startswith(".")
                   for name in os.listdir(WORLD.staging_root()))
    except OSError:
        return False


def _leftovers() -> list:
    """The verified tiles an earlier run left staged."""
    try:
        names = sorted(os.listdir(WORLD.staging_root()))
    except OSError:
        return []
    out = []
    for name in names:
        try:
            lat, lon = WP.parse_tile(name)
        except ValueError:
            continue
        if not _staged(lat, lon):
            continue
        check = WP.verify_tile(os.path.join(WORLD.staging_root(), name),
                               lat, lon)
        if check["problems"]:
            WORLD.write_log({"staged_leftover": name,
                             "problems": check["problems"][:5]})
            continue
        out.append((lat, lon))
    return out


class Sweeper:
    """The sweep's one thread (module doc).  ``emit`` takes the
    ``WorldTilesWaiting`` events, ``scenery_dir()`` the Custom Scenery
    folder now, ``build_dir_of(lat, lon)`` a tile's build folder."""

    def __init__(self, emit: Callable, scenery_dir: Callable[[], str],
                 build_dir_of: Callable[[int, int], str],
                 every_s: float = SWEEP_EVERY_S) -> None:
        self.emit, self.scenery_dir = emit, scenery_dir
        self.build_dir_of, self.every_s = build_dir_of, every_s
        self._wake = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._shown: tuple = ((), (), ())
        self._leftovers = False
        self._guard = threading.Lock()

    def sweep_once(self) -> dict:
        """One sweep: ``{"swapped", "waiting", "reload"}`` (the event is
        emitted when the lists changed)."""
        from . import world_publish as PUBLISH
        swapped = []
        tiles = waiting_tiles()
        if tiles:
            swapped = PUBLISH._swap_waiting(self.scenery_dir(),
                                            self.build_dir_of, only=tiles)
        waiting = tuple(WP.tile_name(*t) for t in waiting_tiles())
        reload = tuple(reload_tiles())
        failed = FAILED.entries()
        self._show(waiting, reload, failed)
        return {"swapped": swapped, "waiting": waiting, "reload": reload,
                "failed": failed}

    def _show(self, waiting: tuple, reload: tuple, failed: tuple = ()
              ) -> None:
        from .events import WorldTilesWaiting
        with self._guard:
            if (waiting, reload, failed) == self._shown:
                return
            self._shown = (waiting, reload, failed)
        self.emit(WorldTilesWaiting(waiting=waiting, reload=reload,
                                    failed=failed))

    def poke(self, leftovers: bool = False) -> None:
        """Sweep now; a thread keeps sweeping while a tile waits or a
        reload is offered.  ``leftovers``: first adopt every verified tile
        an earlier run left staged (the engine's start).  Nothing while the
        app's World pack is not installed (no pack to swap into)."""
        if not self._managed():
            return
        if not (waiting_tiles() or reload_tiles() or FAILED.entries()
                or self._shown != ((), (), ())
                or (leftovers and _any_staged())):
            return
        with self._guard:
            self._leftovers = self._leftovers or leftovers
            if self._thread is None:
                self._thread = threading.Thread(
                    target=self._run, daemon=True, name="o4-world-staged")
                self._thread.start()
        self._wake.set()

    def _managed(self) -> bool:
        try:
            return WORLD.managed(self.scenery_dir())
        except (OSError, ValueError):
            return False

    def _run(self) -> None:
        while True:
            self._wake.clear()
            if not self._managed():
                with self._guard:
                    self._thread = None
                return
            with self._guard:
                adopt, self._leftovers = self._leftovers, False
            try:
                for tile in (_leftovers() if adopt else ()):
                    add_waiting(*tile)
                done = self.sweep_once()
            except Exception as error:      # logged; the next beat retries
                WORLD.write_log({"staged_sweep_error": repr(error)[:300]})
                done = {"waiting": True, "reload": ()}
            if not done["waiting"] and not done["reload"]:
                with self._guard:
                    if not self._wake.is_set():
                        self._thread = None
                        return
                continue
            self._wake.wait(self.every_s)


_SWEEPER: dict = {}


def attach(emit: Callable, scenery_dir: Callable[[], str],
           build_dir_of: Callable[[int, int], str]) -> Sweeper:
    """The engine's one :class:`Sweeper`, now emitting through ``emit``
    (the latest session's)."""
    with _LOCK:
        sweeper = _SWEEPER.get("one")
        if sweeper is None:
            sweeper = _SWEEPER["one"] = Sweeper(emit, scenery_dir, build_dir_of)
        else:
            sweeper.emit, sweeper.scenery_dir = emit, scenery_dir
            sweeper.build_dir_of = build_dir_of
    return sweeper
