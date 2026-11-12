"""The flight manager in the engine: one active flight's job on a thread,
with the session, the World pack and X-Plane (spec
flight-manager-and-world-20261110 §4.3, §5.2, §7.5 S6 (a), §11, §12; lane
F1b).  The logic is ``flight_manager.FlightManager``; this module gives it
what it touches:

* builds through ``world_job_run._SessionBuilder``: the corridor's
  drapes (spec §17, RULINGS 2026-11-11j) on its drape thread, the
  departure and destination (``full``) through the session's queue with
  the job's ``deadline`` and class, ``missing_art="leave"``; never
  interactive), the World pack's publish and swap
  (``world_job_run._PackPublisher``);
* the tile's state in the pack (:func:`pack_state`), its time from the
  recorded ledger (:func:`estimate`: ``plan_estimate.tile_estimate`` for a
  ``full`` build, with ``tile_time_model.airport_seconds_range`` for its
  graded airport when the tile has no history; a drape's measured
  seconds at the user's ``drape_photo_px``,
  ``O4_Flight_Schedule.drape_seconds``);
* the readiness facts (:class:`_Facts`): the World pack and this X-Plane
  session's witness (``world_commands``), the budget pre-check
  (``flight_budget`` against ``storage_budget.status``), the corridor
  pre-fetch and the network (:func:`prefetch_tile`: elevation and map
  data of every corridor tile not on disk);
* the reloads of rule S6 (a) and (b) (``flight_swap_reload.MergeReload``),
  offered and sent only on the pilot's press (``flight_reload``; owner
  2026-11-12T14:34Z): the staged tiles merged over the loaded ones (rule S5,
  ``O4_World_Pack.swap_in(merge=True)``), X-Plane reloads once, and the
  names the new tiles no longer use go once the witness shows the
  reload read them (lane F2);
* the manager's one-shot notices, each emitted as a ``FlightNotice``
  (lane F2), and :meth:`_Runner.cancel` for a diversion's old
  destination (``session.cancel_tile``).

:func:`start` runs the flight BESIDE build-ahead's track mode (``world_job_start
{mode: "flight"}``; owner 2026-11-12, #2019: tiles still load wherever the
aircraft is, whatever the plan): both build through ``build_share.SHARE``
on one slot budget; the flight publishes its slots and its waiting jobs,
so a corridor deadline wins a contended slot, and claims its tiles, so
track mode leaves them; a tile is never built twice.  :func:`stop` ends
the flight; track mode runs on.  ``FlightStatus`` every
:data:`STATUS_EVERY_S` and at once on a change; the record is saved on
every state change.
"""
from __future__ import annotations

import contextlib
import os
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

import O4_Flight_Schedule as SCHEDULE
import O4_World_Pack as WP

from . import flight_budget as BUDGET
from . import flight_record as RECORD
from . import world_commands as WORLD
from .build_share import SHARE
from .flight_manager import FlightManager, prep_drape_px
from .world_job_run import _settings, _utc

__all__ = ["STATUS_EVERY_S", "FULL_FALLBACK_S", "start",
           "stop", "current", "status_event", "pack_state",
           "estimate", "prefetch_tile"]

#: Seconds between ``FlightStatus`` events (spec §5.3).
STATUS_EVERY_S = 2.0
#: Seconds between rereads of the pack, ``Log.txt`` and the volume.
REREAD_S = 10.0
#: A flight tick this slow is logged with its phases (``flight_slow_tick``
#: in ``world_pack.log``), at most once a minute: the CYWG-KDLH flight of
#: 2026-11-12 saved and showed nothing for its first ~5 minutes.
SLOW_TICK_S = 5.0
#: A command waits this long for the flight's lock, then answers from the
#: last status (``flight_status``) or refuses (the edits): the command
#: loop is one thread, and a tick that blocks must never freeze the app.
COMMAND_WAIT_S = 0.25
EDIT_WAIT_S = 10.0
#: A ``full`` build whose estimate cannot be read [estimate, wide].
FULL_FALLBACK_S = (600.0, 3600.0)
_GUARD = threading.Lock()
_RUNNER: "Optional[_Runner]" = None


#: A built ``full`` tile an airport pack's package changed for since it
#: was built (``tile_bundle.pack_shipped``, RULINGS 2026-11-11m (4)): a
#: departure or destination is built again, any other tile is left as it is.
STALE = "stale"


def _package_stale(scenery_dir: str, tiles) -> set:
    try:
        from tile_bundle import pack_shipped
        return pack_shipped.stale_tiles(scenery_dir, tiles) if tiles else set()
    except Exception:                       # the flight plans without it
        return set()


def pack_state(scenery_dir: str) -> Callable[[Tuple[int, int]], Optional[str]]:
    """``state_of(tile)`` for :func:`flight_manager.flight_jobs`: the
    World pack's kind of the tile, ``external`` when another enabled pack
    draws its mesh (spec §7.2), :data:`STALE` for a built tile a pack's
    package changed for, None when neither."""
    import O4_Mesh_Order as ORDER
    pack = WORLD.pack_dir(scenery_dir)
    kinds = WP.world_tiles(pack) if WORLD.managed(scenery_dir) else {}
    real_pack = os.path.normcase(os.path.realpath(pack))
    stale = _package_stale(scenery_dir, [t for t, k in kinds.items() if k == "full"])

    def state_of(tile) -> Optional[str]:
        tile = (int(tile[0]), int(tile[1]))
        kind = kinds.get(tile)
        if kind == "full" and tile in stale:
            return STALE
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


def estimate(provider: str = "", zoomlevel: int = 0,
             px_of: Callable[[], Optional[int]] = lambda: None
             ) -> Callable[[Tuple[int, int], str, str], Tuple[float, float]]:
    """``estimate(tile, kind, role)`` from the recorded times (see the
    module).  ``px_of()``: the drape width the flight fetches at when it
    is not the user's (``flight_manager.prep_drape_px``, #2023)."""
    def seconds(tile, kind, role) -> Tuple[float, float]:
        if kind == "drape":
            from .world_job_run import drape_px
            return SCHEDULE.job_estimate(kind, SCHEDULE.drape_seconds(
                px_of() or drape_px()))
        if kind != "full":
            return SCHEDULE.job_estimate(kind)
        # a full build is on demand: its airport's cores land before
        # it is published (world_publish), so before it counts done
        from .imagery_after_build import core_seconds
        c_lo, c_hi = core_seconds(1)
        lo, hi = _build_seconds(tile, provider, zoomlevel)
        return lo + c_lo, hi + c_hi
    return seconds


def _build_seconds(tile, provider: str, zoomlevel: int
                   ) -> Tuple[float, float]:
    """A ``full`` build's ``(low, high)`` seconds from the ledger (see
    :func:`estimate`), else :data:`FULL_FALLBACK_S`."""
    try:
        from . import tile_time_model as TTM
        from .plan_estimate import tile_estimate
        row = tile_estimate(tile[0], tile[1], provider, zoomlevel, "")
        lo, hi = (float(t) for t in row["time_s"])
        if not row["has_history"]:
            a_lo, a_hi = TTM.airport_seconds_range(tile[0], tile[1])
            lo, hi = lo + a_lo, hi + a_hi
        return (lo, hi) if hi > 0 else FULL_FALLBACK_S
    except Exception:                       # no defensible figure: wide
        return FULL_FALLBACK_S


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
        self.values["offline_tiles"] = ()
        self.values["prefetch_done"] = None if missing else True
        threading.Thread(target=self._budget, args=(jobs, flight_s, len(missing)),
                         daemon=True, name="o4-flight-budget").start()
        if missing:
            threading.Thread(target=self._prefetch, args=(missing, prefetch),
                             daemon=True, name="o4-flight-prefetch").start()

    def _budget(self, jobs, flight_s: float, uncached: int) -> None:
        from .world_job_run import drape_px
        need = BUDGET.need_bytes(jobs, flight_s, uncached, drape_px())
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
        failed = []
        for lat, lon in tiles:
            try:
                prefetch(lat, lon)
            except Exception as error:      # offline or a source down
                WORLD.write_log({"flight_prefetch_error": repr(error)[:300],
                                 "tile": WP.tile_name(lat, lon)})
                failed.append((lat, lon))
        self.values.update(network_ok=not failed, prefetch_done=not failed,
                           offline_tiles=tuple(failed))

    def __call__(self) -> dict:
        """The facts now.  X-Plane's side is reread every
        :data:`REREAD_S`: the first time here (the flight's first status
        needs it), after that on a worker, so a tick never waits on a
        file read."""
        now = time.monotonic()
        if now - self._at > REREAD_S:
            first, self._at = self._at < 0, now
            if first:
                self._reread()
            else:
                threading.Thread(target=self._reread, daemon=True,
                                 name="o4-flight-facts").start()
        return dict(self.values)

    def _reread(self) -> None:
        with contextlib.suppress(Exception):
            self._world()

    def _world(self) -> None:
        reads = WORLD.xplane_reads(self.scenery_dir)   # never the tile walk
        loads = reads["loads"]
        self.values.update(
            world_installed=reads["installed"],
            world_seen=reads["seen_by_xplane"],
            xplane_running=reads["xplane_running"], loads=set(loads),
            load_stamps={tile: r.t_s for tile, r in loads.items()})


def _reloader(scenery_dir: str, build_dir_of, port=None):
    """Rules S6 (a), (b) with S5 (``flight_swap_reload.MergeReload``);
    called only on the pilot's press (``flight_reload``); the reload goes
    through ``reload_offer.send``, the one sender."""
    import O4_XPlane_WebAPI as WEBAPI

    from . import reload_offer as RELOAD
    from .flight_swap_reload import MergeReload

    def send() -> bool:
        return RELOAD.send(WEBAPI.base_url(int(port)) if port else None)

    def witness() -> dict:
        if not WORLD._xplane_running():
            return {}
        return {tile: r.t_s for tile, r in
                WORLD._witness(scenery_dir)[0].items()}
    return MergeReload(scenery_dir, build_dir_of, send, witness)


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
        self.session = session
        self.reloader = _reloader(scenery_dir, session.tile_build_dir, port)
        def px_of() -> Optional[int]:       # #2023: a departure-only ring
            manager = getattr(self, "manager", None)
            return prep_drape_px(manager.plan if manager else plan)
        builder = _SessionBuilder(
            session, provider, zoomlevel,
            drape=lambda tile: drape_tile(tile, provider, zoomlevel,
                                          px=px_of()),
            share=SHARE, owner="flight")
        self.manager = FlightManager(
            record, plan, builder=builder,
            publisher=_PackPublisher(scenery_dir, session.tile_build_dir),
            facts=lambda: {}, state_of=pack_state(scenery_dir),
            estimate=estimate(provider, zoomlevel, px_of),
            intermediate="drape",
            parked_slots=GOVERNOR.parked_slots(SLOTS.session_capacity()),
            flight_slots=self.cap,
            ground_reload=self.reloader,
            others_running=lambda: SHARE.others_running("flight"),
            stamp=_utc)
        self.manager.facts = _Facts(scenery_dir, self.manager.jobs,
                                    self.manager.times[-1])
        _share_slots(self.manager)
        _core_points(self.manager)
        self.t0 = time.monotonic()
        # the rows and the countdown before the first tick: the pane shows
        # the flight at once, whatever the first tick waits for
        self.manager.prime(0.0, self.manager.facts())
        self.snapshot = self.manager.status(0.0)
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True,
                                       name="o4-flight")

    def now(self) -> float:
        return time.monotonic() - self.t0

    def cancel(self, tile) -> None:
        """A diversion's old destination: its build stops after the
        current step (``session.cancel_tile``)."""
        with contextlib.suppress(Exception):
            self.session.cancel_tile(int(tile[0]), int(tile[1]))

    def _emit_notices(self) -> None:
        from .events import FlightNotice
        flight = self.manager.record.id
        for notice in self.manager.notices():
            self.emit(FlightNotice(flight=flight, **notice))
            WORLD.write_log({"flight_notice": notice["code"]})

    def status(self) -> dict:
        """The status now; the last tick's when a tick holds the lock
        (``flight_status`` never waits on a tick: see
        :data:`COMMAND_WAIT_S`)."""
        if not self.lock.acquire(timeout=COMMAND_WAIT_S):
            return dict(self.snapshot)
        try:
            return self.manager.status(self.now())
        finally:
            self.lock.release()

    @contextlib.contextmanager
    def locked(self, wait: float = EDIT_WAIT_S):
        """The lock for a command that edits the flight; refuses after
        ``wait`` seconds instead of freezing the command loop."""
        if not self.lock.acquire(timeout=wait):
            raise ValueError("The flight is busy for a moment: try again.")
        try:
            yield
        finally:
            self.lock.release()

    def run(self) -> None:
        sent_at, last, saved, logged = -1e18, None, None, -1e18
        while not self.stop_event.wait(1.0):
            now = self.now()
            try:
                clock = _PhaseClock()
                rec = self.feed.read()
                clock.mark("feed")
                with self.lock:
                    clock.mark("lock")
                    if rec is not None:
                        building = any(j.state == "building"
                                       for j in self.manager.jobs)
                        self.governor.observe(now, rec.get("frame_s"), building)
                        self.manager.flight_slots = self.governor.allowed(self.cap)
                    self.manager.facts()
                    clock.mark("facts")
                    self.manager.tick(now, rec)
                    clock.mark("tick")
                    _share_slots(self.manager)
                    _core_points(self.manager)
                    self.reloader.sweep(self.manager.facts().get("load_stamps"))
                    clock.mark("share")
                    fields = self.snapshot = self.manager.status(now)
                    record = self.manager.record
                    record.tiles = self.manager.record_tiles()
                    clock.mark("status")
                key = (record.state, record.phase, tuple(
                    (tuple(t.tile), t.state) for t in record.tiles))
                if key != saved:
                    saved = key
                    RECORD.save(record, RECORD.flights_dir())
                changed = (fields["state"], fields["items"], fields["reload"])
                if changed != last or now - sent_at >= STATUS_EVERY_S:
                    last, sent_at = changed, now
                    self.emit(status_event(fields))
                self._emit_notices()
                clock.mark("save_emit")
                if clock.total() >= SLOW_TICK_S and now - logged >= 60.0:
                    logged = now
                    WORLD.write_log({"flight_slow_tick": clock.phases(),
                                     "at_s": round(now, 1)})
            except Exception as error:      # logged; the flight goes on
                WORLD.write_log({"flight_error": repr(error)[:300]})


class _PhaseClock:
    """Seconds per phase of one flight tick (``flight_slow_tick``)."""

    def __init__(self) -> None:
        self._at = self._t0 = time.monotonic()
        self._phases: Dict[str, float] = {}

    def mark(self, name: str) -> None:
        now = time.monotonic()
        self._phases[name] = round(now - self._at, 2)
        self._at = now

    def total(self) -> float:
        return self._at - self._t0

    def phases(self) -> Dict[str, float]:
        return dict(self._phases)


#: The flight's states that dispatch builds (``FlightManager.tick``).
_DISPATCHING = ("preparing", "ready", "flying")


def _share_slots(manager, share=SHARE) -> None:
    """Tell ``share`` the flight's tiles (track mode leaves them), its
    slot count and the jobs waiting for a slot (track mode starts only
    in what is left)."""
    jobs = manager.jobs
    waiting = (sum(1 for j in jobs if j.state == "queued")
               if manager.record.state in _DISPATCHING else 0)
    share.claim("flight", [j.tile for j in jobs])
    share.publish("flight", manager.slots(), waiting)


def _core_points(manager) -> None:
    """Name the plan's departure and destination airports to the World
    publish (``world_publish.add_core_point``): their tiles' cores are
    fetched around them even when the build graded no airport there."""
    import O4_Flight_Plan as FP

    from . import world_publish as PUBLISH
    waypoints = manager.plan.waypoints
    for point in {waypoints[0], waypoints[-1]} if waypoints else ():
        PUBLISH.add_core_point(*FP.tile_of(point.lat, point.lon),
                               (point.ident, point.lat, point.lon))


def current() -> "Optional[_Runner]":
    """The running flight's runner, or None."""
    runner = _RUNNER
    return runner if runner is not None and runner.thread.is_alive() else None


def start(session, emit, record, plan, scenery_dir: str, port=None) -> str:
    """Run ``record``'s flight beside track mode: ``"started"``, or
    ``"running"`` when that flight already runs; a different active
    flight raises ``ValueError``."""
    global _RUNNER
    with _GUARD:
        runner = current()
        if runner is not None:
            if runner.manager.record.id == record.id:
                return "running"
            raise ValueError("A flight is already active (%s): end it first."
                             % runner.manager.record.id)
        _RUNNER = _Runner(emit, session, record, plan, scenery_dir, port)
        _RUNNER.thread.start()
    # the first FlightStatus before the first tick: the pane shows the
    # flight's rows and countdown at once
    emit(status_event(_RUNNER.snapshot))
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
    SHARE.leave("flight")
    WORLD.write_log({"flight": "stop", "id": runner.manager.record.id})
    return runner.manager.record
