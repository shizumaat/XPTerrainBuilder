"""The flight manager in the engine: one active flight's job on a thread,
with the session, the World pack and X-Plane (spec
flight-manager-and-world-20261110 §4.3, §5.2, §7.5 S6 (a), §11, §12; lane
F1b).  The logic is ``flight_manager.FlightManager``; this module gives it
what it touches:

* builds through the session's queue (``world_job_run._SessionBuilder``:
  ``enqueue_build`` with ``overrides={"profile": kind}``, the job's
  ``deadline`` and class, ``missing_art="leave"``; never interactive),
  the World pack's publish and swap (``world_job_run._PackPublisher``);
* the tile's state in the pack (:func:`pack_state`), its time from the
  recorded ledger (:func:`estimate`: ``plan_estimate.tile_estimate`` for a
  ``full`` build, with ``tile_time_model.airport_seconds_range`` for its
  graded airport when the tile has no history; the CYYR / ldrape
  constants for the intermediate kinds until one is recorded);
* the readiness facts (:class:`_Facts`): the World pack and this X-Plane
  session's witness (``world_commands``), the budget pre-check
  (``flight_budget`` against ``storage_budget.status``), the corridor
  pre-fetch and the network (:func:`prefetch_tile`: elevation and map
  data of every corridor tile not on disk);
* the ground reload of rule S6 (a) (:func:`_ground_reload`): the staged
  departure and first-window tiles merged over the loaded ones (rule S5,
  ``O4_World_Pack.swap_in(merge=True)``), then X-Plane reloads once.

:func:`start` replaces build-ahead's track mode while a flight is active
(``world_job_start {mode: "flight"}``); :func:`stop` ends it and track
mode may start again.  ``FlightStatus`` every :data:`STATUS_EVERY_S` and
at once on a change; the record is saved on every state change.
"""
from __future__ import annotations

import contextlib
import os
import shutil
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import O4_Flight_Schedule as SCHEDULE
import O4_World_Pack as WP

from . import flight_budget as BUDGET
from . import flight_record as RECORD
from . import world_commands as WORLD
from .flight_manager import FlightManager

__all__ = ["STATUS_EVERY_S", "FULL_FALLBACK_S", "start", "stop", "current",
           "status_event", "pack_state", "estimate", "prefetch_tile"]

#: Seconds between ``FlightStatus`` events (spec §5.3).
STATUS_EVERY_S = 2.0
#: Seconds between rereads of the pack, ``Log.txt`` and the volume.
REREAD_S = 10.0
#: A ``full`` build whose estimate cannot be read [estimate, wide].
FULL_FALLBACK_S = (600.0, 3600.0)
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


def pack_state(scenery_dir: str) -> Callable[[Tuple[int, int]], Optional[str]]:
    """``state_of(tile)`` for :func:`flight_manager.flight_jobs`: the
    World pack's kind of the tile, ``external`` when another enabled pack
    draws its mesh (spec §7.2), None when neither."""
    import O4_Mesh_Order as ORDER
    pack = WORLD.pack_dir(scenery_dir)
    kinds = WP.world_tiles(pack) if WORLD.managed(scenery_dir) else {}
    real_pack = os.path.normcase(os.path.realpath(pack))

    def state_of(tile) -> Optional[str]:
        tile = (int(tile[0]), int(tile[1]))
        kind = kinds.get(tile)
        if kind not in (None, "placeholder"):
            return kind
        try:
            drawn = ORDER.drawn_mesh_dsf(scenery_dir, *tile)
        except Exception:                   # an unreadable pack list
            drawn = None
        if drawn and not os.path.normcase(os.path.realpath(drawn)).startswith(
                real_pack):
            return "external"
        return kind
    return state_of


def estimate(provider: str = "", zoomlevel: int = 0
             ) -> Callable[[Tuple[int, int], str, str], Tuple[float, float]]:
    """``estimate(tile, kind, role)`` from the recorded times (see the
    module)."""
    def seconds(tile, kind, role) -> Tuple[float, float]:
        if kind != "full":
            return SCHEDULE.job_estimate(kind)
        try:
            from . import tile_time_model as TTM
            from .plan_estimate import tile_estimate
            row = tile_estimate(tile[0], tile[1], provider, zoomlevel, "")
            lo, hi = (float(t) for t in row["time_s"])
            if not row["has_history"]:
                a_lo, a_hi = TTM.airport_seconds_range(tile[0], tile[1])
                lo, hi = lo + a_lo, hi + a_hi
            return (lo, hi) if hi > 0 else FULL_FALLBACK_S
        except Exception:                   # no defensible figure: wide
            return FULL_FALLBACK_S
    return seconds


def prefetch_tile(lat: int, lon: int) -> None:
    """Elevation and map data of one corridor tile into the data folder
    (spec §11), as its build would fetch them; raises on a download
    failure."""
    import O4_Config_Utils as CFG
    import O4_DEM_Utils as DEM
    import O4_Vector_Map as VMAP
    tile = CFG.Tile(lat, lon, "")
    tile.read_from_config()
    base = (getattr(tile, "custom_dem", "") or "").split(";")[0]
    DEM.DEM(lat, lon, base, "to zero", info_only=True,
            elevation_level=getattr(tile, "elevation_level", "auto"))
    VMAP.start_background_osm_prefetch(tile)
    VMAP.wait_for_background_osm_prefetch()


def _on_disk(tile) -> bool:
    from .plan_estimate import _terrain_data_cached
    return bool(_terrain_data_cached(int(tile[0]), int(tile[1])))


class _Facts:
    """The readiness facts (see the module); the slow ones on workers."""

    def __init__(self, scenery_dir: str, jobs, flight_s: float,
                 prefetch: Callable[[int, int], None] = prefetch_tile,
                 on_disk: Callable[[Any], bool] = _on_disk) -> None:
        self.scenery_dir = scenery_dir
        self.values: Dict[str, Any] = {}
        self._at = -1e18
        tiles = sorted({j.tile for j in jobs})
        missing = [t for t in tiles if not on_disk(t)]
        self.values["all_on_disk"] = not missing
        self.values["prefetch_done"] = None if missing else True
        threading.Thread(target=self._budget, args=(jobs, flight_s, len(missing)),
                         daemon=True, name="o4-flight-budget").start()
        if missing:
            threading.Thread(target=self._prefetch, args=(missing, prefetch),
                             daemon=True, name="o4-flight-prefetch").start()

    def _budget(self, jobs, flight_s: float, uncached: int) -> None:
        need = BUDGET.need_bytes(jobs, flight_s, uncached)
        try:
            import O4_File_Names as FNAMES

            from . import storage as STORAGE
            from . import storage_budget as STORAGE_BUDGET
            from .plan_estimate import _free_bytes
            figures = STORAGE_BUDGET.status(STORAGE.storage_scan()["stores"])
            free = _free_bytes(FNAMES.data_path(""))
        except Exception as error:          # unread: the volume decides alone
            WORLD.write_log({"flight_budget_error": repr(error)[:300]})
            figures, free = None, None
        fits, detail = BUDGET.verdict(need, figures, free)
        self.values.update(budget_fits=fits, budget_detail=detail)

    def _prefetch(self, tiles, prefetch) -> None:
        ok = True
        for lat, lon in tiles:
            try:
                prefetch(lat, lon)
            except Exception as error:      # offline or a source down
                WORLD.write_log({"flight_prefetch_error": repr(error)[:300],
                                 "tile": WP.tile_name(lat, lon)})
                ok = False
        self.values.update(network_ok=ok, prefetch_done=ok)

    def __call__(self) -> dict:
        now = time.monotonic()
        if now - self._at > REREAD_S:
            self._at = now
            with contextlib.suppress(Exception):
                self._world()
        return dict(self.values)

    def _world(self) -> None:
        fields = WORLD._status_fields(self.scenery_dir)
        running = WORLD._xplane_running()
        loads: dict = {}
        if running and fields["installed"]:
            loads = WORLD._witness(self.scenery_dir)[0]
        self.values.update(
            world_installed=fields["installed"],
            world_seen=fields["seen_by_xplane"], xplane_running=running,
            loads=set(loads))


def _ground_reload(scenery_dir: str, build_dir_of, port=None
                   ) -> Callable[[List[Tuple[int, int]]], bool]:
    """Rule S6 (a) (see the module); True when X-Plane took the reload."""
    def reload(tiles) -> bool:
        import O4_XPlane_WebAPI as WEBAPI

        from . import world_publish as PUBLISH
        pack = WORLD.pack_dir(scenery_dir)
        for lat, lon in tiles:
            staged = os.path.join(WORLD.staging_root(), WP.tile_name(lat, lon))
            if not os.path.isfile(os.path.join(staged, WP.dsf_relpath(lat, lon))):
                continue
            done = WP.swap_in(pack, staged, lat, lon, merge=True)
            shutil.rmtree(staged, ignore_errors=True)
            PUBLISH._after_swap(scenery_dir, build_dir_of(lat, lon), lat, lon)
            WORLD.write_log({"swap_in": done["tile"], "merge": True,
                             "stale": len(done["stale"]), "from": "flight"})
        base = WEBAPI.base_url(int(port)) if port else None
        sent = bool(WEBAPI.reload_scenery(base))
        WORLD.write_log({"flight_reload": sent, "tiles": len(tiles)})
        return sent
    return reload


def status_event(fields: dict):
    """A ``FlightStatus`` of the manager's :meth:`status` fields."""
    from .events import FlightStatus
    return FlightStatus(**fields)


class _Runner:
    def __init__(self, emit, session, record, plan, scenery_dir: str,
                 port=None) -> None:
        import O4_Machine_Slots as SLOTS
        import O4_World_Governor as GOVERNOR
        import O4_XPlane_WebAPI as WEBAPI

        from .position_feed import shared
        from .world_job_run import _PackPublisher, _SessionBuilder, drape_tile
        values = _settings()
        provider = values.get("default_website") or "BI"
        zoomlevel = int(values.get("default_zl") or 16)
        self.emit, self.scenery_dir = emit, scenery_dir
        self.feed = shared(WEBAPI.base_url(int(port)) if port else None)
        self.cap = GOVERNOR.flight_slots(os.cpu_count() or 4,
                                         int(values.get("fly_build_slots") or 0),
                                         SLOTS.session_capacity())
        self.governor = GOVERNOR.FrameGovernor(
            values.get("fly_sim_priority") or "balanced")
        builder = _SessionBuilder(
            session, provider, zoomlevel,
            drape=lambda tile: drape_tile(tile, provider, zoomlevel))
        self.manager = FlightManager(
            record, plan, builder=builder,
            publisher=_PackPublisher(scenery_dir, session.tile_build_dir),
            facts=lambda: {}, state_of=pack_state(scenery_dir),
            estimate=estimate(provider, zoomlevel),
            intermediate=values.get("world_intermediate") or "light",
            parked_slots=GOVERNOR.parked_slots(SLOTS.session_capacity()),
            flight_slots=self.cap,
            ground_reload=_ground_reload(scenery_dir, session.tile_build_dir,
                                         port),
            stamp=_utc)
        self.manager.facts = _Facts(scenery_dir, self.manager.jobs,
                                    self.manager.times[-1])
        self.t0 = time.monotonic()
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True,
                                       name="o4-flight")

    def now(self) -> float:
        return time.monotonic() - self.t0

    def status(self) -> dict:
        with self.lock:
            return self.manager.status(self.now())

    def run(self) -> None:
        sent_at, last, saved = -1e18, None, None
        while not self.stop_event.wait(1.0):
            now = self.now()
            try:
                rec = self.feed.read()
                with self.lock:
                    if rec is not None:
                        building = any(j.state == "building"
                                       for j in self.manager.jobs)
                        self.governor.observe(now, rec.get("frame_s"), building)
                        self.manager.flight_slots = self.governor.allowed(self.cap)
                    self.manager.tick(now, rec)
                    fields = self.manager.status(now)
                    record = self.manager.record
                    record.tiles = self.manager.record_tiles()
                key = (record.state, record.phase, tuple(
                    (tuple(t.tile), t.state) for t in record.tiles))
                if key != saved:
                    saved = key
                    RECORD.save(record, RECORD.flights_dir())
                changed = (fields["state"], fields["items"], fields["reload"])
                if changed != last or now - sent_at >= STATUS_EVERY_S:
                    last, sent_at = changed, now
                    self.emit(status_event(fields))
            except Exception as error:      # logged; the flight goes on
                WORLD.write_log({"flight_error": repr(error)[:300]})


def current() -> "Optional[_Runner]":
    """The running flight's runner, or None."""
    runner = _RUNNER
    return runner if runner is not None and runner.thread.is_alive() else None


def start(session, emit, record, plan, scenery_dir: str, port=None) -> str:
    """Run ``record``'s flight (build-ahead's track mode stops first):
    ``"started"``, or ``"running"`` when that flight already runs; a
    different active flight raises ``ValueError``."""
    global _RUNNER
    from . import world_job_run as TRACK
    with _GUARD:
        runner = current()
        if runner is not None:
            if runner.manager.record.id == record.id:
                return "running"
            raise ValueError("A flight is already active (%s): end it first."
                             % runner.manager.record.id)
        TRACK.world_job_stop()
        _RUNNER = _Runner(emit, session, record, plan, scenery_dir, port)
        _RUNNER.thread.start()
    WORLD.write_log({"flight": "start", "id": record.id})
    return "started"


def stop() -> "Optional[Any]":
    """Stop the running flight's job; its record (None when none ran).
    Builds already queued finish; staged tiles wait for the next swap."""
    global _RUNNER
    with _GUARD:
        runner, _RUNNER = _RUNNER, None
    if runner is None:
        return None
    runner.stop_event.set()
    runner.thread.join(timeout=5.0)
    WORLD.write_log({"flight": "stop", "id": runner.manager.record.id})
    return runner.manager.record
