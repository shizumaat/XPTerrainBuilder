"""The build-ahead job in the engine: its commands and what it touches
(flight manager / World spec 2026-11-10 §5.2, §8; capability
``world_job``).  The job's logic is ``world_job.WorldJob``; this module
gives it the session, the World pack and X-Plane.

* :func:`world_job_start` (``world_job_start {mode: "track"}``) starts it
  on a thread that reads the shared position feed
  (``position_feed.shared``) once a second and emits ``WorldStatus``
  every 2 s; ``mode: "flight"`` arrives with the flight manager (F1b).
  :func:`autostart` starts it beside the follow job (both apps call
  ``imagery_follow_start`` at launch) when imagery on demand is on and the
  World pack is installed.  :func:`world_job_stop` stops it.
* :class:`SessionBuilder` -- a ``light`` tile is an ordinary build through
  the session's queue (``enqueue_build`` with ``overrides={"profile":
  "light"}``, its ``deadline`` and class ``P1``; never interactive:
  ``missing_art="leave"``); ``world_publish.watch`` stages and publishes it
  as every finished build.  A ``drape`` tile (setting
  ``world_intermediate``, until D1) is fetched and written straight into
  the staging folder (``O4_World_Drape_Fetch``, ``O4_World_Drape``).
* :class:`PackPublisher` -- swaps a staged tile when the job's rule S3
  allows, holding the follow job for that tile only (S7).
"""
from __future__ import annotations

import contextlib
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Optional

import O4_World_Pack as WP

from . import world_commands as WORLD
from .world_job import KINDS, WorldJob

__all__ = ["STATUS_EVERY_S", "SessionBuilder", "PackPublisher",
           "world_job_start", "world_job_stop", "autostart"]

#: Seconds between ``WorldStatus`` events while the job runs.
STATUS_EVERY_S = 2.0
#: Seconds a finished build may wait to be staged by the publish worker
#: before the job counts it failed.
PENDING_S = 900.0
#: Seconds between rereads of the pack's tiles and X-Plane's ``Log.txt``.
REREAD_S = 10.0
_GUARD = threading.Lock()
_RUNNER: "Optional[_Runner]" = None


def _settings() -> dict:
    try:
        import O4_Settings_Model as SM
        return SM.read_global_raw()
    except Exception:                       # no readable settings
        return {}


def _utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class SessionBuilder:
    """The job's builds through the engine session (see the module)."""

    def __init__(self, session: Any, provider: str, zoomlevel: int,
                 drape: "Optional[Callable[[tuple], bool]]" = None) -> None:
        self.session = session
        self.provider, self.zoomlevel = provider, int(zoomlevel)
        self.drape = drape
        self._mine: set = set()
        self._done: list = []
        self._lock = threading.Lock()
        self._pool: Optional[ThreadPoolExecutor] = None
        session.subscribe(self._on_event)

    def _on_event(self, event) -> None:
        if type(event).__name__ != "BuildDone":
            return
        tile = (int(event.lat), int(event.lon))
        with self._lock:
            if tile in self._mine:
                self._mine.discard(tile)
                self._done.append((tile, bool(event.ok)))

    def start(self, tile, kind: str, deadline_in_s: float, klass: str) -> bool:
        tile = (int(tile[0]), int(tile[1]))
        if kind == "drape":
            return self._start_drape(tile)
        with self._lock:
            self._mine.add(tile)
        ok = self.session.enqueue_build(
            [tile], self.provider, self.zoomlevel, "",
            missing_art="leave", overrides={"profile": kind},
            deadline=time.time() + float(deadline_in_s), klass=klass)
        if not ok:
            with self._lock:
                self._mine.discard(tile)
        return bool(ok)

    def _start_drape(self, tile) -> bool:
        if self.drape is None:
            return False
        if self._pool is None:
            self._pool = ThreadPoolExecutor(1, thread_name_prefix="o4-drape")

        def work() -> None:
            try:
                ok = bool(self.drape(tile))
            except Exception as error:      # logged; the job retries once
                WORLD.write_log({"drape_error": repr(error)[:300],
                                 "tile": WP.tile_name(*tile)})
                ok = False
            with self._lock:
                self._done.append((tile, ok))
        self._pool.submit(work)
        return True

    def poll(self, now: float) -> list:
        with self._lock:
            done, self._done = self._done, []
        return done


def drape_tile(tile, provider: str, zoomlevel: int) -> bool:
    """Fetch a drape tile's imagery and write it, staged, in the World
    pack's shape (``O4_World_Drape.write_drape``); True when it
    verifies."""
    import O4_File_Names as FNAMES
    import O4_World_Drape as DRAPE
    import O4_World_Drape_Fetch as FETCH
    lat, lon = tile
    engine = os.path.dirname(os.path.dirname(os.path.abspath(WP.__file__)))
    parent = FNAMES.data_path("World_build")
    fetched = FETCH.fetch(engine, lat, lon, parent, int(zoomlevel), provider,
                          drop=3)
    staged = os.path.join(WORLD.staging_root(), WP.tile_name(lat, lon))
    if os.path.exists(staged):
        import shutil
        shutil.rmtree(staged)
    tool = WP.dsftool_path(engine)
    DRAPE.write_drape(lat, lon, int(zoomlevel), provider, fetched["textures"],
                      staged, tool)
    return not DRAPE.verify_drape(staged, lat, lon, tool)["problems"]


class PackPublisher:
    """Swaps the job's staged tiles into the World pack (see the module)."""

    def __init__(self, scenery_dir: str, build_dir_of: Callable[[int, int], str],
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.scenery_dir = scenery_dir
        self.build_dir_of = build_dir_of
        self.clock = clock
        self._pending: dict = {}

    def settle(self, tile, kind: str, held: bool) -> str:
        from . import imagery_follow as FOLLOW
        from . import world_publish as PUBLISH
        lat, lon = tile
        pack = WORLD.pack_dir(self.scenery_dir)
        dsf = os.path.join(pack, WP.dsf_relpath(lat, lon))
        if os.path.isfile(dsf) and not WP.is_placeholder(dsf):
            self._pending.pop(tile, None)
            return "swapped"
        staged = os.path.join(WORLD.staging_root(), WP.tile_name(lat, lon))
        if os.path.isfile(os.path.join(staged, WP.dsf_relpath(lat, lon))):
            self._pending.pop(tile, None)
            if held:
                return "staged"
            with FOLLOW.paused("world swap", tiles=[WP.tile_name(lat, lon)]):
                WP.swap_staged(pack, WORLD.staging_root(),
                               lambda la, lo: (la, lo) != (lat, lon))
            if kind != "drape":
                PUBLISH._after_swap(self.scenery_dir,
                                    self.build_dir_of(lat, lon), lat, lon)
            WORLD.write_log({"swap_in": WP.tile_name(lat, lon), "kind": kind,
                             "from": "world_job"})
            return "swapped"
        first = self._pending.setdefault(tile, self.clock())
        return "failed" if self.clock() - first > PENDING_S else "pending"


class _Wanted:
    """May the job build a tile: the pack holds a placeholder for it (its
    region is on, ``world_regions_set``) and no other enabled pack draws
    its mesh (``external``, spec §7.2).  Reread every :data:`REREAD_S`."""

    def __init__(self, scenery_dir: str) -> None:
        self.scenery_dir = scenery_dir
        self._kinds: dict = {}
        self._external: dict = {}
        self._at = -1e18

    def __call__(self, tile) -> bool:
        now = time.monotonic()
        if now - self._at > REREAD_S:
            self._kinds = WP.world_tiles(WORLD.pack_dir(self.scenery_dir))
            self._at = now
        if self._kinds.get(tuple(tile)) != "placeholder":
            return False
        if tile not in self._external:
            import O4_Mesh_Order as ORDER
            drawn = ORDER.drawn_mesh_dsf(self.scenery_dir, *tile)
            pack = os.path.normcase(os.path.realpath(
                WORLD.pack_dir(self.scenery_dir)))
            self._external[tile] = bool(drawn) and not os.path.normcase(
                os.path.realpath(drawn)).startswith(pack)
        return not self._external[tile]


class _Loads:
    """The World tiles X-Plane loaded this session (``Log.txt``), reread
    every :data:`REREAD_S`."""

    def __init__(self, scenery_dir: str) -> None:
        self.scenery_dir = scenery_dir
        self._tiles: set = set()
        self._at = -1e18

    def __call__(self) -> set:
        now = time.monotonic()
        if now - self._at > REREAD_S:
            with contextlib.suppress(Exception):
                self._tiles = set(WORLD._witness(self.scenery_dir)[0])
            self._at = now
        return self._tiles


class _Runner:
    def __init__(self, emit, session, scenery_dir: str, kind: str,
                 port=None) -> None:
        import O4_Machine_Slots as SLOTS
        import O4_XPlane_WebAPI as WEBAPI

        from .position_feed import shared
        values = _settings()
        provider = values.get("default_website") or "BI"
        zoomlevel = int(values.get("default_zl") or 16)
        self.emit, self.scenery_dir = emit, scenery_dir
        self.feed = shared(WEBAPI.base_url(int(port)) if port else None)
        builder = SessionBuilder(
            session, provider, zoomlevel,
            drape=lambda tile: drape_tile(tile, provider, zoomlevel))
        self.job = WorldJob(
            builder=builder,
            publisher=PackPublisher(scenery_dir, session.tile_build_dir),
            wanted=_Wanted(scenery_dir), kind=kind,
            capacity=SLOTS.session_capacity(), cores=os.cpu_count() or 4,
            fly_slots=int(values.get("fly_build_slots") or 0),
            sim_priority=values.get("fly_sim_priority") or "balanced",
            loads=_Loads(scenery_dir), stamp=_utc)
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True,
                                       name="o4-world-job")

    def run(self) -> None:
        status_at = -1e18
        while not self.stop_event.wait(1.0):
            now = time.monotonic()
            try:
                self.job.tick(now, self.feed.read())
            except Exception as error:      # logged; the job goes on
                WORLD.write_log({"world_job_error": repr(error)[:300]})
            if now - status_at >= STATUS_EVERY_S:
                status_at = now
                with contextlib.suppress(Exception):
                    self.emit(WORLD.status_event(self.scenery_dir,
                                                 **self.job.status(now)))


def world_job_start(session, emit=None, mode: str = "track", flight=None,
                    kind: str = "", scenery_dir: str = "", port=None,
                    if_enabled: bool = False, **_ignored) -> dict:
    """ENGINE COMMAND ``world_job_start``: ``{"status": "started" |
    "running" | "off"}`` ("off": ``if_enabled`` and on-demand is off or
    no World pack is installed)."""
    global _RUNNER
    if mode != "track":
        raise ValueError("world_job_start: only mode 'track' is available "
                         "(mode 'flight' arrives with the flight manager).")
    values = _settings()
    kind = kind or values.get("world_intermediate") or "light"
    if kind not in KINDS:
        raise ValueError(f"world_job_start: unknown kind {kind!r} "
                         f"(known: {list(KINDS)}).")
    scenery_dir = WORLD.scenery_dir_or_default(scenery_dir)
    on = str(values.get("imagery_on_demand", "True")).lower() not in (
        "false", "0", "no", "off")
    if if_enabled and not (on and WORLD.managed(scenery_dir)):
        return {"status": "off"}
    if not WORLD.managed(scenery_dir):
        raise ValueError("world_job_start: the World pack is not installed.")
    with _GUARD:
        if _RUNNER is not None and _RUNNER.thread.is_alive():
            return {"status": "running"}
        _RUNNER = _Runner(emit or session._emit, session, scenery_dir, kind,
                          port)
        _RUNNER.thread.start()
    WORLD.write_log({"world_job": "start", "kind": kind, "mode": mode})
    return {"status": "started"}


def world_job_stop(**_ignored) -> dict:
    """ENGINE COMMAND ``world_job_stop``: stops the job (builds it queued
    finish; staged tiles wait for the next start).  ``{"status",
    "swapped", "late"}``."""
    global _RUNNER
    with _GUARD:
        runner, _RUNNER = _RUNNER, None
    if runner is None:
        return {"status": "stopped", "swapped": 0, "late": 0}
    runner.stop_event.set()
    runner.thread.join(timeout=5.0)
    jobs = runner.job.jobs.values()
    WORLD.write_log({"world_job": "stop"})
    return {"status": "stopped",
            "swapped": sum(1 for j in jobs if j.state == "swapped"),
            "late": sum(1 for j in jobs if j.state == "late")}


def autostart(session, port=None, **_ignored) -> Optional[dict]:
    """Start the job beside the follow job when it may run (see
    :func:`world_job_start`, ``if_enabled``); never raises."""
    try:
        return world_job_start(session, port=port, if_enabled=True)
    except Exception as error:              # logged; the follow job starts
        WORLD.write_log({"world_job_autostart": repr(error)[:300]})
        return None
