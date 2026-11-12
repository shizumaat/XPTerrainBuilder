"""The build-ahead job in the engine: its commands and what it touches
(flight manager / World spec 2026-11-10 §5.2, §8; capability
``world_job``).  The job's logic is ``world_job.WorldJob``; this module
gives it the session, the World pack and X-Plane.

* :func:`world_job_start` (``world_job_start {mode: "track"}``) starts it
  on a thread that reads the shared position feed
  (``position_feed.shared``) once a second and emits ``WorldStatus``
  every 2 s.  ``mode: "flight", flight: <id>`` starts that flight's job
  (``flight_job_run``, lane F1b: the route's corridor, departure and
  destination by their deadlines, ``FlightStatus``).  Track mode runs
  BESIDE a flight, whatever the plan (owner 2026-11-12, #2019: "No
  matter what the flight plan is set to, we should still dynamically
  load tiles wherever the aircraft is"): both jobs build on one slot
  budget through ``build_share.SHARE`` -- the flight's deadlines first,
  its tiles its own, never one tile twice.  :func:`autostart` starts
  track mode beside the follow job (both apps call
  ``imagery_follow_start`` at launch) whenever the World pack is
  installed (the ``imagery_on_demand`` switch says only how new builds
  are made: it was off on the owner's Mac and nothing was draped,
  #2019), and the active flight too, when a record is still preparing,
  ready or flying.  :func:`world_job_stop` stops
  track mode (``flight_end`` stops a flight).
* :class:`_SessionBuilder` -- a ``drape`` tile, the kind build-ahead and a
  flight's corridor make (spec §17, RULINGS 2026-11-11j), is fetched and
  written straight into the staging folder on the builder's thread
  (:func:`drape_tile`: ``O4_World_Drape_Fetch`` at the user's
  ``drape_photo_px``, the water copy on ``airports -1``,
  ``O4_World_Drape``).  A ``full`` tile (a flight's departure and
  destination) is an ordinary build through the session's queue
  (``enqueue_build`` with its ``deadline`` and class; never interactive:
  ``missing_art="leave"``); ``world_publish.watch`` stages and publishes
  it as every finished build.  A tile the disk budget shrank to its
  package has it installed first (``storage_packages.restore``).
* :class:`_PackPublisher` -- swaps a staged tile when the job's rule S3
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
from .build_share import SHARE, BuildShare
from .fly_here import describe as describe_here
from .world_job import WorldJob, drape_estimate

__all__ = ["STATUS_EVERY_S", "world_job_start", "world_job_stop", "autostart"]

#: Seconds between ``WorldStatus`` events while the job runs.
STATUS_EVERY_S = 2.0
#: Seconds a finished build may wait to be staged by the publish worker
#: before the job counts it failed.
PENDING_S = 900.0
#: A drape waits at most this long (from its start) for the tile's water
#: before it goes without its water copy rather than late (lane ldrape2:
#: a cold Overpass read took 47-187 s; the job keeps up on the CYYR
#: replay at 1-3x up to ~90 s a tile, mask and write included).
WATER_WAIT_S = 75.0
#: Seconds between rereads of the pack's tiles and X-Plane's ``Log.txt``.
REREAD_S = 10.0
#: A parked aircraft's core: squares within this many square sizes of it
#: are fetched at full resolution (``O4_Imagery_Tier_Plan.CROSSING_S``'s
#: full tier: what a camera standing there wants).
CORE_FULL_S = 1.65
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


def _restore_package(tile) -> None:
    """A tile the disk budget shrank to its package gets its inputs back
    before its build (``storage_packages.restore``): only imagery is
    downloaded.  A package that will not install is logged; the build
    then downloads as any other."""
    from . import storage_packages as PACKAGES
    try:
        PACKAGES.restore(*tile)
    except Exception as error:
        WORLD.write_log({"package_restore_error": repr(error)[:300],
                         "tile": WP.tile_name(*tile)})


class _SessionBuilder:
    """The job's builds through the engine session (see the module).
    With a ``share`` (``build_share.BuildShare``) every tile is taken
    there as ``owner`` first and its result goes to whichever job owns
    it when the build ends."""

    def __init__(self, session: Any, provider: str, zoomlevel: int,
                 drape: "Optional[Callable[[tuple], bool]]" = None,
                 share: Optional[BuildShare] = None, owner: str = "") -> None:
        self.session = session
        self.provider, self.zoomlevel = provider, int(zoomlevel)
        self.drape = drape
        self.share, self.owner = share, owner
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
            if tile not in self._mine:
                return
            self._mine.discard(tile)
        self._finish(tile, bool(event.ok))

    def _finish(self, tile, ok: bool) -> None:
        if self.share is not None:
            self.share.finish(tile, ok)
            return
        with self._lock:
            self._done.append((tile, ok))

    def start(self, tile, kind: str, deadline_in_s: float, klass: str,
              core=None) -> bool:
        """``core`` ``(lat, lon)``: a drape whose core around that point is
        fetched at full resolution (a parked aircraft, ``WorldJob``)."""
        tile = (int(tile[0]), int(tile[1]))
        if self.share is not None:
            verdict = self.share.take(self.owner, tile, kind)
            if verdict != "start":
                return verdict == "adopted"
        started = self._start(tile, kind, deadline_in_s, klass, core)
        if not started and self.share is not None:
            self.share.drop(self.owner, tile)
        return started

    def _start(self, tile, kind: str, deadline_in_s: float, klass: str,
               core=None) -> bool:
        if kind == "drape":
            return self._start_drape(tile, core)
        _restore_package(tile)
        with self._lock:
            self._mine.add(tile)
        ok = self.session.enqueue_build(
            [tile], self.provider, self.zoomlevel, "",
            missing_art="leave",
            deadline=time.time() + float(deadline_in_s), klass=klass)
        if not ok:
            with self._lock:
                self._mine.discard(tile)
        return bool(ok)

    def _start_drape(self, tile, core=None) -> bool:
        if self.drape is None:
            return False
        if self._pool is None:
            # as many at once as the job's slots dispatch (it was one: a
            # 3-slot flight ran its drapes one after another)
            self._pool = ThreadPoolExecutor(thread_name_prefix="o4-drape")

        def work() -> None:
            try:
                ok = bool(self.drape(tile) if core is None
                          else self.drape(tile, core))
            except Exception as error:      # logged; the job retries once
                WORLD.write_log({"drape_error": repr(error)[:300],
                                 "tile": WP.tile_name(*tile)})
                ok = False
            self._finish(tile, ok)
        self._pool.submit(work)
        return True

    def poll(self, now: float) -> list:
        with self._lock:
            done, self._done = self._done, []
        if self.share is not None:
            done += self.share.poll(self.owner)
        return done


def drape_px() -> int:
    """The user's drape photo width now (``drape_photo_px``, read per tile
    so a change in the Fly pane applies to the next drape)."""
    try:
        return int(_settings().get("drape_photo_px") or 512)
    except (TypeError, ValueError):
        return 512


def drape_tile(tile, provider: str, zoomlevel: int, core=None,
               px: Optional[int] = None) -> bool:
    """Fetch a drape tile's imagery at ``px`` (else :func:`drape_px`; a
    departure-only flight's ring is fetched at 512, #2023) with its water
    masks, and write it, staged, in the World pack's shape: the opaque
    photo plus the water-alpha copy on ``O4_World_Drape.WATER_LAYER_GROUP``
    (``write_drape``, RULINGS 2026-11-11j).  ``core`` ``(lat, lon)``: a
    parked aircraft's airport -- the squares within :data:`CORE_FULL_S`
    of it are fetched again at full resolution (RULINGS 2026-11-12c (3)).
    The build folder goes once the tile is staged (the DDS are
    hard-linked).  True when it verifies."""
    import shutil

    import O4_File_Names as FNAMES
    import O4_World_Drape as DRAPE
    import O4_World_Drape_Fetch as FETCH
    lat, lon = tile
    px = int(px or drape_px())
    engine = os.path.dirname(os.path.dirname(os.path.abspath(WP.__file__)))
    parent = FNAMES.data_path("World_build")
    fetched = FETCH.fetch(engine, lat, lon, parent, int(zoomlevel), provider,
                          drop=FETCH.drop_for_px(px), water_alpha=True,
                          water_wait_s=WATER_WAIT_S)
    if core is not None:
        cored = FETCH.fetch(engine, lat, lon, parent, int(zoomlevel), provider,
                            drop=0, water_alpha=True, water_wait_s=WATER_WAIT_S,
                            near=(float(core[0]), float(core[1]), CORE_FULL_S))
        fetched["core_squares"] = cored.get("squares")
    staged = os.path.join(WORLD.staging_root(), WP.tile_name(lat, lon))
    if os.path.exists(staged):
        shutil.rmtree(staged)
    tool = WP.dsftool_path(engine)
    DRAPE.write_drape(lat, lon, int(zoomlevel), provider, fetched["textures"],
                      staged, tool, water_layer=DRAPE.WATER_LAYER_GROUP)
    WORLD.write_log({"drape": WP.tile_name(lat, lon), "px": px,
                     **{k: fetched.get(k) for k in (
                         "squares", "dds", "download_s", "convert_s",
                         "masked", "water_late", "water_fetch_s",
                         "water_wait_s", "core_squares")}})
    with contextlib.suppress(OSError):
        shutil.rmtree(fetched["tile"])
    return not DRAPE.verify_drape(staged, lat, lon, tool)["problems"]


def _merge_held(pack: str, staged: str, lat: int, lon: int) -> None:
    """A held tile merged in (S5: every old name kept), the staging
    folder gone, and the user offered the reload that shows it."""
    import shutil

    from . import reload_offer as RELOAD
    WP.swap_in(pack, staged, lat, lon, merge=True)
    shutil.rmtree(staged, ignore_errors=True)
    RELOAD.offer("tiles")


class _PackPublisher:
    """Swaps the job's staged tiles into the World pack (see the module)."""

    def __init__(self, scenery_dir: str, build_dir_of: Callable[[int, int], str],
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.scenery_dir = scenery_dir
        self.build_dir_of = build_dir_of
        self.clock = clock
        self._pending: dict = {}

    def settle(self, tile, kind: str, held: bool, merge: bool = False,
               fresh: bool = False) -> str:
        """``fresh``: the staged version replaces a real tile already in
        the pack (a parked aircraft's drape re-made with its core).
        ``merge``: a tile X-Plane holds, swapped for a parked aircraft
        (RULINGS 2026-11-12c (3)): merged in file by file, no name removed
        (rule S5, ``O4_World_Pack.swap_in(merge=True)``); the user is
        offered the reload that shows it (``reload_offer``)."""
        from . import imagery_follow as FOLLOW
        from . import world_publish as PUBLISH
        lat, lon = tile
        pack = WORLD.pack_dir(self.scenery_dir)
        dsf = os.path.join(pack, WP.dsf_relpath(lat, lon))
        staged = os.path.join(WORLD.staging_root(), WP.tile_name(lat, lon))
        staged_dsf = os.path.join(staged, WP.dsf_relpath(lat, lon))
        if (os.path.isfile(dsf) and not WP.is_placeholder(dsf)
                and not (fresh and os.path.isfile(staged_dsf))):
            self._pending.pop(tile, None)
            return "swapped"
        if os.path.isfile(staged_dsf):
            self._pending.pop(tile, None)
            if held:
                return "staged"
            with FOLLOW.paused("world swap", tiles=[WP.tile_name(lat, lon)]):
                if merge:
                    _merge_held(pack, staged, lat, lon)
                else:
                    WP.swap_staged(pack, WORLD.staging_root(),
                                   lambda la, lo: (la, lo) != (lat, lon))
            if kind != "drape":
                PUBLISH._after_swap(self.scenery_dir,
                                    self.build_dir_of(lat, lon), lat, lon)
            WORLD.write_log({"swap_in": WP.tile_name(lat, lon), "kind": kind,
                             "from": "world_job", "merge": merge})
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

    def kind(self, tile) -> Optional[str]:
        """The pack's kind of ``tile`` (``placeholder``, ``drape``,
        ``full``; None: not ours or another pack draws its mesh)."""
        now = time.monotonic()
        if now - self._at > REREAD_S:
            self._kinds = WP.world_tiles(WORLD.pack_dir(self.scenery_dir))
            self._at = now
        kind = self._kinds.get(tuple(tile))
        if kind is None or self._is_external(tuple(tile)):
            return None
        return kind

    def __call__(self, tile) -> bool:
        return self.kind(tile) == "placeholder"

    def _is_external(self, tile) -> bool:
        if tile not in self._external:
            import O4_Mesh_Order as ORDER
            drawn = ORDER.drawn_mesh_dsf(self.scenery_dir, *tile)
            pack = os.path.normcase(os.path.realpath(
                WORLD.pack_dir(self.scenery_dir)))
            self._external[tile] = bool(drawn) and not os.path.normcase(
                os.path.realpath(drawn)).startswith(pack)
        return self._external[tile]


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
    def __init__(self, emit, session, scenery_dir: str, port=None) -> None:
        import O4_Machine_Slots as SLOTS
        import O4_XPlane_WebAPI as WEBAPI

        from .position_feed import shared
        values = _settings()
        provider = values.get("default_website") or "BI"
        zoomlevel = int(values.get("default_zl") or 16)
        self.emit, self.scenery_dir = emit, scenery_dir
        self.feed = shared(WEBAPI.base_url(int(port)) if port else None)
        builder = _SessionBuilder(
            session, provider, zoomlevel,
            drape=lambda tile, core=None: (
                drape_tile(tile, provider, zoomlevel) if core is None
                else drape_tile(tile, provider, zoomlevel, core=core)),
            share=SHARE, owner="track")
        wanted = _Wanted(scenery_dir)

        def kind_of(tile):
            return None if SHARE.claimed("track", tile) else wanted.kind(tile)
        self.job = WorldJob(
            builder=builder,
            publisher=_PackPublisher(scenery_dir, session.tile_build_dir),
            wanted=lambda tile: (not SHARE.claimed("track", tile)
                                 and wanted(tile)),
            slot_free=lambda slots, running: SHARE.free_for(
                "track", slots, running),
            kind_of=kind_of,
            kind="drape",
            estimate_s=drape_estimate(drape_px()),
            capacity=SLOTS.session_capacity(), cores=os.cpu_count() or 4,
            fly_slots=int(values.get("fly_build_slots") or 0),
            sim_priority=values.get("fly_sim_priority") or "balanced",
            loads=_Loads(scenery_dir), stamp=_utc)
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True,
                                       name="o4-world-job")

    def run(self) -> None:
        status_at, resets = -1e18, self.feed.resets
        while not self.stop_event.wait(1.0):
            now = time.monotonic()
            try:
                rec = self.feed.read()
                if self.feed.resets != resets:      # a flight (re)load
                    resets = self.feed.resets
                    self.job.forget_window()
                self.job.tick(now, rec)
            except Exception as error:      # logged; the job goes on
                WORLD.write_log({"world_job_error": repr(error)[:300]})
            if now - status_at >= STATUS_EVERY_S:
                status_at = now
                with contextlib.suppress(Exception):
                    status = self.job.status(now)
                    status["here"] = describe_here(status["here"],
                                                   self.scenery_dir)
                    self.emit(WORLD.status_event(self.scenery_dir, **status))


def world_job_start(session, emit=None, mode: str = "track", flight=None,
                    scenery_dir: str = "", port=None,
                    if_enabled: bool = False, **_ignored) -> dict:
    """ENGINE COMMAND ``world_job_start``: ``{"status": "started" |
    "running" | "off"}`` ("off": ``if_enabled`` and no World pack is
    installed; the ``imagery_on_demand`` switch says only how new builds
    are made, #2019)."""
    global _RUNNER
    if mode == "flight":
        return _flight_start(session, emit, flight, scenery_dir, port)
    if mode != "track":
        raise ValueError(f"world_job_start: unknown mode {mode!r} "
                         "(known: 'track', 'flight').")
    scenery_dir = WORLD.scenery_dir_or_default(scenery_dir)
    if if_enabled and not WORLD.managed(scenery_dir):
        return {"status": "off"}
    if not WORLD.managed(scenery_dir):
        raise ValueError("world_job_start: the World pack is not installed.")
    with _GUARD:
        if _RUNNER is not None and _RUNNER.thread.is_alive():
            return {"status": "running"}
        _RUNNER = _Runner(emit or session._emit, session, scenery_dir, port)
        _RUNNER.thread.start()
    WORLD.write_log({"world_job": "start", "kind": "drape", "mode": mode})
    return {"status": "started"}


def _flight_start(session, emit, flight, scenery_dir: str, port) -> dict:
    """``world_job_start {mode: "flight", flight}``: run that flight's job
    (``flight_job_run.start``); the World pack must be installed."""
    from . import flight_job_run as FLIGHT
    from . import flight_record as RECORD
    scenery_dir = WORLD.scenery_dir_or_default(scenery_dir)
    if not WORLD.managed(scenery_dir):
        raise ValueError("Install the World pack first (XPTerrainBuilder makes it when it starts): "
                         "a flight's tiles go into it.")
    path = os.path.join(RECORD.flights_dir(), f"{flight}.json")
    try:
        record = RECORD.load(path)
    except (OSError, ValueError) as error:
        raise ValueError(f"world_job_start: no flight {flight!r}.") from error
    status = FLIGHT.start(session, emit or session._emit, record,
                          RECORD.plan_of(record), scenery_dir, port)
    return {"status": status, "mode": "flight", "flight": record.id}


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
    SHARE.leave("track")
    jobs = runner.job.jobs.values()
    WORLD.write_log({"world_job": "stop"})
    return {"status": "stopped",
            "swapped": sum(1 for j in jobs if j.state == "swapped"),
            "late": sum(1 for j in jobs if j.state == "late")}


def autostart(session, port=None, **_ignored) -> Optional[dict]:
    """Start track mode beside the follow job when it may run (see
    :func:`world_job_start`, ``if_enabled``) and the active flight beside
    it; never raises.  The reply is track mode's, with the flight's
    ``mode`` and ``flight`` when one started."""
    reply: Optional[dict] = None
    try:
        reply = world_job_start(session, port=port, if_enabled=True)
    except Exception as error:              # logged; the follow job starts
        WORLD.write_log({"world_job_autostart": repr(error)[:300]})
    try:
        from . import flight_record as RECORD
        active = RECORD.active_flight(RECORD.flights_dir())
        if active is not None and WORLD.managed(WORLD.scenery_dir_or_default()):
            flight = world_job_start(session, mode="flight", flight=active.id,
                                     port=port)
            reply = dict(reply or {}, **flight, track=(reply or {}).get("status"))
    except Exception as error:              # logged; track mode runs on
        WORLD.write_log({"world_job_autostart": repr(error)[:300]})
    return reply
