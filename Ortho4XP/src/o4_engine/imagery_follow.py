"""The follow job: finer imagery tiers fetched ahead of the aircraft
while X-Plane flies (#1992 local-imagery-cache spec §4, §8, phase P3b).

Once a second the job reads the camera from X-Plane's Web API
(``O4_XPlane_WebAPI``), derives track and speed from the camera's
POSITION DELTAS (``O4_Imagery_Follow_Motion``; never the groundspeed
dataref, which a ground-speed multiplier makes wrong), plans which tier
each nearby square needs by when (``O4_Imagery_Tier_Plan.plan`` over the
index rows, ``O4_Imagery_OnDemand_Index``) and hands the due fetches,
earliest deadline first, to the lander (``imagery_follow_land.TierLander``)
on worker threads.

ADAPTIVE LIKE VIDEO STREAMING (owner ruling 2026-11-10T05:18Z): the
queue's tightest slack is the BUFFER; one texture is in flight while it
holds, more while it depletes, back to one when it recovers
(``O4_Imagery_Fetch_Slots``).

The rules it keeps (spec §4.7, §8):

* every landing is a whole file under the texture's own name (the
  lander's ``O4_DDS_File.land``); the job never deletes or truncates a
  texture name, never touches ``.ter``, DSF or masks;
* at most ``lands_per_s`` landings start per second (R6);
* at start, partials are swept and ``upgrading`` rows reset (R7);
* a tier landed after its crossing is counted ``late`` (R5, U5);
* PAUSE: no new fetch starts while a Library command that changes tiles
  holds :func:`paused` — the converter would race on ``textures/``;
  fetches in flight finish.  A build or a World-pack swap holds only ITS
  tiles (World spec §8.7, S7): ``busy()`` returns the names of the tiles
  being built (a bare ``True`` still holds every tile) and
  ``paused(tiles=...)`` holds the tiles named; fetches for every other
  tile go on;
* no network: :data:`OFFLINE_AFTER` failures in a row pause fetching for
  :data:`OFFLINE_PAUSE_S` ("Offline: imagery stays low-res"; files that
  need no download still land); a texture that fails
  :data:`MAX_FAILURES` times is ``failed`` until next session;
* X-Plane not running or its Web API off, or X-Plane loading a flight
  (its clock not running: no position is trusted then, #2028): the job
  idles and says so;
* SPAWN AND JUMP (spec §4.5, P5; ``O4_Imagery_Spawn``): the first
  position of a session, positions resumed after a Web API drop or a
  load (a flight load, ``flight_loads``) and a camera jump (``jumps``:
  any move between two samples no aircraft flies) each open
  an episode: the new place's core is fetched first, straight at the
  tiers a camera standing there wants, files that need no download
  (``lander.local``) first and up to ``max_slots`` at once, against the
  end of X-Plane's flight-start window (a session's first position has
  none: X-Plane may have loaded long ago).  When the core has landed and
  a file missed the window where X-Plane still shows it coarse, the job
  OFFERS the user one reload (``reloader``: ``reload_offer.offer``;
  ``reloads`` counts the offers; ``reload_offer`` is the one pending):
  X-Plane is never asked to reload unless the user clicks "Reload
  scenery" (owner 2026-11-12T14:34Z); nothing missed, or nothing landed
  (no network): no offer.

``last_near_at`` is written for the rows the camera is within their
tier's distance of, while the sim is not paused (spec §5.3).  The job
reports through ``ImageryFollowStatus`` events.

OFF THE TICK (#2037): the reread of every row, the storage measure and
sweep and the ``last_near_at`` writes run on the job's house thread
(``imagery_follow_house.FollowHouse``); the tick takes the newest rows it
read.  The fetches run under ``O4_Machine_Slots.net_priority``: in the
session's per-server budget the camera's squares go before a World drape
or an after-build core.
"""
from __future__ import annotations

import concurrent.futures as _futures
import contextlib
import math
import os
import threading
import time
import typing as _t

import O4_Imagery_Fetch_Slots as SLOTS
import O4_Imagery_Follow_Reach as REACH
import O4_Imagery_OnDemand_Index as INDEX
import O4_Imagery_Spawn as SPAWN
import O4_Imagery_Tier_Plan as PLAN
import O4_Machine_Slots as MACHINE_SLOTS
import O4_XPlane_WebAPI as WEBAPI
from O4_Imagery_Follow_Motion import MotionTracker

from .imagery_follow_house import ROWS_EVERY_S, SWEEP_EVERY_S, FollowHouse

__all__ = ["MAX_FAILURES", "OFFLINE_AFTER", "OFFLINE_PAUSE_S", "FollowJob",
           "ROWS_EVERY_S", "SWEEP_EVERY_S", "paused", "held_tiles",
           "log_path", "write_log"]

#: A texture that fails this many times is ``failed`` for the session.
MAX_FAILURES = 3
#: Failures in a row (any textures) that read as "no network".
OFFLINE_AFTER = 3
#: Seconds fetching pauses after that (the fetcher's own AIMD pause runs
#: inside each fetch; this is the job's).
OFFLINE_PAUSE_S = 60.0
#: The status sentence while that pause lasts.
OFFLINE_REASON = "Offline: imagery stays low-res"
#: The status sentence while X-Plane loads a flight: no position is
#: trusted until its clock runs (``O4_XPlane_WebAPI.PositionReader``).
LOADING_REASON = "it is loading a flight"
#: Seconds between status events when nothing changed.
STATUS_EVERY_S = 2.0
#: Seconds between ``last_near_at`` writes (the index throttles per row).
#: (``ROWS_EVERY_S`` and ``SWEEP_EVERY_S``: ``imagery_follow_house``.)
NEAR_EVERY_S = 10.0
#: The finest tier (a "sharp" row of the status).
_FINEST = len(PLAN.TIER_WIDTH) - 1
#: Default seconds one landing takes per tier before any is measured
#: (the P3a replay's model at 85 requests/s and a 2 s full convert).
DEFAULT_FETCH_S = {1: 0.3, 2: 1.9, 3: 5.0}

_PAUSES = 0
_PAUSES_GUARD = threading.Lock()
#: tile name -> holders of :func:`paused` for that tile alone.
_TILE_PAUSES: dict = {}


@contextlib.contextmanager
def paused(_reason: str = "", tiles=None):
    """While held, no follow job starts a new fetch (a Library command that
    deletes or replaces tiles holds it); with ``tiles`` (names such as
    ``+53-064``), none for those tiles only (a World-pack swap, S7)."""
    global _PAUSES
    names = None if tiles is None else [str(t) for t in tiles]
    with _PAUSES_GUARD:
        if names is None:
            _PAUSES += 1
        for name in names or ():
            _TILE_PAUSES[name] = _TILE_PAUSES.get(name, 0) + 1
    try:
        yield
    finally:
        with _PAUSES_GUARD:
            if names is None:
                _PAUSES -= 1
            for name in names or ():
                _TILE_PAUSES[name] -= 1
                if not _TILE_PAUSES[name]:
                    del _TILE_PAUSES[name]


def held_tiles() -> "set[str]":
    """The tiles :func:`paused` holds one by one now."""
    with _PAUSES_GUARD:
        return set(_TILE_PAUSES)


def pause_count() -> int:
    """How many holders of :func:`paused` there are now."""
    return _PAUSES


def _placeholder_root() -> str:
    import O4_File_Names as FNAMES
    import O4_Imagery_Placeholder as PLACEHOLDER
    return os.path.join(FNAMES.data_path(PLACEHOLDER.STORE_DIR),
                        "placeholders")


def _is_sharp(row: dict) -> int:
    return int(PLAN.tier_of_width(row["tier_px"]) == _FINEST)


def _key(row: dict) -> str:
    return f"{row['tile']}/{row['name']}"


class _InFlight(_t.NamedTuple):
    future: _futures.Future
    fetch: PLAN.Fetch
    row: dict
    started: float
    due_at: float           # absolute time of the crossing it serves



def _pending_offer() -> str:
    """The reload offered to the user and not taken yet (``reload_offer``)."""
    from . import reload_offer as RELOAD
    return RELOAD.current()

class FollowJob:
    """One follow session.  ``reader`` is an ``O4_XPlane_WebAPI``
    ``PositionReader``; ``lander(row, tier)`` lands one file and returns
    the index facts (``imagery_follow_land.TierLander``); ``index_path``
    the index file; ``rebuild_tiles`` ``(build_dir, lat, lon)`` rescanned
    into it at :meth:`open`; ``rescan_dir``: every on-demand tile under
    that working folder rescanned BESIDE the job (``imagery_ondemand.
    on_demand_tiles``; hundreds of tiles take minutes, #2028), which
    follows the index as it stands meanwhile; ``busy()`` names the tiles being built (``True``:
    every tile is held, see the module); ``emit``
    receives each ``ImageryFollowStatus``; ``reloader()`` asks X-Plane to
    reload its scenery and says whether it took the request (``None``:
    the job never reloads)."""

    def __init__(self, emit, *, reader, lander, index_path=None,
                 busy=lambda: False, lead_s: float = PLAN.DEFAULT_LEAD_S,
                 period_s: float = 1.0, max_slots: int = SLOTS.MAX_SLOTS,
                 lands_per_s: float = 4.0, clock=time.time, log_path=None,
                 slots: SLOTS.FetchSlots | None = None, rebuild_tiles=(),
                 cap_bytes: int | None = None, reloader=None,
                 rescan_dir: str | None = None):
        self.emit = emit
        self.reader, self.lander = reader, lander
        self.reloader = reloader
        self.spawn = SPAWN.SpawnWatch()
        self._read_at: float | None = None      # the last good position
        self._resets = 0                        # reader.resets seen
        self.index_path = index_path
        self.rebuild_tiles = [tuple(t) for t in rebuild_tiles or ()]
        self.rescan_dir = rescan_dir
        self.rescan: threading.Thread | None = None
        self._focus = None                      # a plan's place, to take
        self._focus_guard = threading.Lock()
        self.cap_bytes = cap_bytes
        self.house: FollowHouse | None = None
        self._seq = 0                           # landings recorded
        self._committed = 0                     # ... and in the index
        self._writes: list = []                 # this tick's index writes
        self._touched: dict[str, int] = {}      # key -> seq it landed at
        self.busy = busy
        self.lead_s, self.period_s = float(lead_s), float(period_s)
        self.lands_per_s = float(lands_per_s)
        self.clock = clock
        self.log_path = log_path
        self.slots = slots or SLOTS.for_lead(self.lead_s, max_slots)
        self.tracker = MotionTracker()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._pool = _futures.ThreadPoolExecutor(
            max_workers=self.slots.max_slots,
            thread_name_prefix="o4-imagery-follow-fetch")
        self._conn = None
        self._rows: dict[str, dict] = {}
        self._tiles: dict = {}                  # REACH.by_tile(_rows)
        self._sharp = 0                         # rows at the finest tier
        self._inflight: dict[str, _InFlight] = {}
        self._failures: dict[str, int] = {}
        self._failed: set[str] = set()
        self._fail_streak = 0
        self._offline_until = -math.inf
        self._tokens, self._tokens_at = self.lands_per_s, None
        self._near_at = -math.inf
        self._near: set[str] = set()
        self._status_at = -math.inf
        self._last_status: tuple | None = None
        self._fetch_s = dict(DEFAULT_FETCH_S)
        self.counts = {"landed": 0, "late": 0, "failed": 0, "bytes": 0,
                       "network": 0, "downgraded": 0, "reloads": 0}
        self.landings: list[dict] = []       # what landed, in order
        self.state, self.reason = "starting", ""
        self.buffer_s = math.inf
        self.queued = 0
        self.motion: PLAN.Motion | None = None
        self.last_plan: list[PLAN.Fetch] = []        # this tick's plan
        self.last_dispatched: list[PLAN.Fetch] = []  # ... and what started

    # ---------------------------------------------------------- lifecycle

    def start(self) -> "FollowJob":
        """Run the job on its own thread."""
        self._thread = threading.Thread(target=self.run, daemon=True,
                                        name="o4-imagery-follow")
        self._thread.start()
        return self

    def stop(self, timeout: float = 15.0) -> dict:
        """Stop: no new fetch starts; fetches in flight get ``timeout`` s
        to land (a later one is a whole file or nothing, and its index row
        is reset at the next start).  Returns the counts."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
        return dict(self.counts, state=self.state)

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def run(self) -> None:
        """The loop: :meth:`open`, then :meth:`tick` every ``period_s``.  A
        tick that raises (a bad position record, a texture that will not
        read) is logged (``tick_error``) and the next tick runs: one bad
        record never ends the job (#2019).  Only a failed :meth:`open`
        stops it (``error``)."""
        try:
            self._status(self.clock(), force=True)      # "starting", at once
            self.open()
            self.house.start()          # the slow index work off the tick
            while not self._stop.is_set():
                t0 = time.monotonic()
                try:
                    self.tick()
                except Exception as error:      # logged; the job goes on
                    self._log({"tick_error": repr(error)[:300]})
                self._stop.wait(max(0.02, self.period_s
                                    - (time.monotonic() - t0)))
        except Exception as error:      # the event carries it; the engine lives on
            self.state, self.reason = "error", repr(error)[:300]
        finally:
            self.close()

    def open(self) -> None:
        """Start clean (R7): the index opened (the ``rebuild_tiles``
        ``(build_dir, lat, lon)`` rescanned first), partials swept and
        ``upgrading`` rows reset."""
        self._conn = INDEX.open_index(self.index_path)
        if self.rebuild_tiles:
            INDEX.rebuild(self._conn, self.rebuild_tiles,
                          placeholder_root=_placeholder_root())
        INDEX.reset_upgrading(self._conn)
        if self.cap_bytes is None:
            from .imagery_downgrade import cap_bytes
            self.cap_bytes = cap_bytes()
        self.house = FollowHouse(
            self.index_path, self._conn, seq=lambda: self._committed,
            cap_bytes=self.cap_bytes, clock=self.clock, log=self._log,
            abort=self._stop.is_set)
        self._reload_rows(self.clock())
        self._log({"start": len(self.rebuild_tiles), "textures": len(self._rows)})
        if self.rescan_dir is not None:
            self.rescan = threading.Thread(target=self._rescan, daemon=True,
                                           name="o4-imagery-follow-rescan")
            self.rescan.start()

    def _rescan(self) -> None:
        """Every on-demand tile under ``rescan_dir`` into the index, on
        its own connection, one tile at a time (the job follows the rows
        it has meanwhile and rereads them when this is done)."""
        from .imagery_ondemand import on_demand_tiles
        conn = None
        try:
            tiles = list(on_demand_tiles(self.rescan_dir))
            self._log({"rescan": len(tiles)})
            conn = INDEX.open_index(self.index_path)
            written = 0
            for tile in tiles:
                while (self.spawn.episode is not None
                       and not self._stop.is_set()):
                    self._stop.wait(1.0)    # low priority: a core first
                if self._stop.is_set():
                    break
                written += INDEX.rebuild(conn, [tile],
                                         placeholder_root=_placeholder_root())
            self.house.want_rows()              # reread soon
            self._log({"rescanned": len(tiles), "textures": written})
        except Exception as error:      # logged; the job follows what it has
            self._log({"rescan_error": repr(error)[:300]})
        finally:
            if conn is not None:
                conn.close()

    def close(self) -> None:
        """Let the fetches in flight finish (bounded), record them, and
        say "stopped"."""
        pending = [f.future for f in self._inflight.values()]
        if pending:
            _futures.wait(pending, timeout=10.0)
        self._harvest(self.clock())
        try:
            self._commit()
        except Exception as error:      # logged; the next open resets them
            self._log({"commit_error": repr(error)[:300]})
        self._pool.shutdown(wait=False, cancel_futures=True)
        if self.house is not None:
            self.house.stop()
        if self.state != "error":
            self.state, self.reason = "stopped", ""
        self._status(self.clock(), force=True)
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # --------------------------------------------------------------- tick

    def tick(self) -> None:
        """One cycle: read, plan, harvest, dispatch, report; its index
        writes committed once, at its end (:meth:`_commit`)."""
        try:
            self._tick()
        finally:
            self._commit()

    def _write(self, fn, *args, **columns) -> None:
        """``fn(conn, *args, **columns)`` (an ``INDEX`` write), committed
        with the tick's others at its end."""
        self._writes.append((fn, args, columns))

    def _commit(self) -> None:
        """The tick's index writes in ONE transaction (#2037: 0-12
        autocommits a tick, each a disk flush, held the windows-latest
        tick 3.7-5 s).  The house's reread trusts the index for the
        landings committed (:attr:`_committed`); later ones stay the
        job's.  A failed commit keeps the writes for the next tick."""
        writes, self._writes = self._writes, []
        if writes:
            try:
                with INDEX.transaction(self._conn):
                    for fn, args, columns in writes:
                        fn(self._conn, *args, **columns)
            except Exception:
                self._writes[:0] = writes
                raise
        self._committed = self._seq

    def _tick(self) -> None:
        now = self.clock()
        self.last_dispatched = []
        self._harvest(now)
        self._house_work(now)
        self._take_focus(now)
        rec = self.reader.read()
        if rec is None:
            # a plan's departure needs no camera: its core goes on
            if self.spawn.episode is not None:
                self._run(self._plan(now, planner=False), now)
            self.state = "waiting"
            self.reason = (LOADING_REASON if getattr(self.reader, "loading", False)
                           else "X-Plane is not running or its Web API is off")
            self._status(now)
            return
        lat, lon = WEBAPI.camera_position(rec)
        self._locate(now, lat, lon, float(rec.get("elev_m") or 0.0),
                     WEBAPI.camera_agl_m(rec))
        fetches = self._plan(now)
        if not rec.get("paused"):
            self._mark_near(now)
        self._run(fetches, now)
        self._settle_spawn(now, lat, lon)
        self._status(now)

    def _run(self, fetches, now: float) -> None:
        """This tick's ``fetches`` to the slots: held tiles left out, no
        download while offline, none at all while a build holds every
        tile; :attr:`state` says which."""
        self.last_plan = fetches
        self._update_slots(fetches, now)
        offline = now < self._offline_until
        held = self._held()
        if held is True or pause_count():
            self.state = "paused"
            self.reason = "A build is running; imagery waits for it"
            return
        self.state, self.reason = ("paused", OFFLINE_REASON) if offline \
            else ("following", "")
        if held:
            fetches = [f for f in fetches
                       if (self._rows.get(f.square) or {}).get("tile")
                       not in held]
        guard = self.house.dispatch_guard if self.house else threading.Lock()
        if not guard.acquire(blocking=False):
            return              # the house's sweep downgrades: next tick
        try:
            self._dispatch(fetches, now, downloads=not offline)
            self._commit()      # "upgrading" in the index before a sweep
        finally:
            guard.release()

    # ---------------------------------------------------- a flight plan

    def focus(self, lat: float, lon: float, tiles=()) -> None:
        """A flight plan was entered (owner 2026-11-12T23:40:51Z: "it
        should end any other flight, stop processing any other region
        and prioritize the newly input flight plan"): at the next tick
        the departure ``(lat, lon)`` opens a ``plan`` episode -- its core
        first, whether X-Plane is there yet or not, every other region's
        episode dropped and the planner's fetches held until it has
        landed -- after ``tiles`` (``(build_dir, lat, lon)``) the index
        has no rows of are rescanned, ahead of any startup rescan (which
        waits while an episode is open)."""
        with self._focus_guard:
            self._focus = (float(lat), float(lon),
                           [tuple(t) for t in tiles or ()])

    def _take_focus(self, now: float) -> None:
        with self._focus_guard:
            focus, self._focus = self._focus, None
        if focus is None:
            return
        import O4_File_Names as FNAMES
        lat, lon, tiles = focus
        indexed = set(self._tiles)
        missing = [t for t in tiles
                   if FNAMES.short_latlon(t[1], t[2]) not in indexed]
        if missing:
            self._commit()                  # the reread sees this tick's
            INDEX.rebuild(self._conn, missing,
                          placeholder_root=_placeholder_root())
            self._reload_rows(now)
        episode = self.spawn.witness(
            "plan", now, lat, lon, self._rows,
            is_local=getattr(self.lander, "local", None), tiles=self._tiles)
        self._log({"spawn": "plan", "core": len(episode.wants),
                   "local": len(episode.local), "rescanned": len(missing)})

    def _held(self):
        """``True`` when every tile is held, else the names of the tiles
        held now (``busy()`` and :func:`held_tiles`)."""
        busy = self.busy()
        if busy is True or (busy and not isinstance(
                busy, (set, frozenset, list, tuple))):
            return True
        return set(busy or ()) | held_tiles()

    # ------------------------------------------------- spawn and jump

    def _locate(self, now: float, lat: float, lon: float,
                alt_m: float, agl_m: float = 0.0) -> None:
        """The camera sample into the motion tracker, and the witness it
        is (spec §4.5): the session's first position, positions resumed
        after a drop, or a jump opens the spawn episode of the place."""
        kind, moved, down = "", math.inf, 0.0
        if self._read_at is None:
            kind = "spawn"
        elif self.reader.resets != self._resets:
            kind = "flight_load"
            moved, down = self.tracker.moved_m(lat, lon), now - self._read_at
            if moved > SPAWN.SAME_PLACE_M:
                self.tracker.restart()  # no track or speed across a load
        self._resets, self._read_at = self.reader.resets, now
        self.motion = self.tracker.add(now, lat, lon, alt_m, agl_m)
        if self.tracker.jumped:
            kind, moved = "jump", math.inf
        if not kind:
            return
        if kind == "spawn" and getattr(self.spawn.episode, "witness",
                                       "") == "plan":
            return          # the plan's departure first; the planner follows
        episode = self.spawn.witness(
            kind, now, lat, lon, self._rows, moved_m=moved, down_s=down,
            is_local=getattr(self.lander, "local", None), agl_m=agl_m,
            tiles=self._tiles)
        if episode is not None:
            self._log({"spawn": kind, "core": len(episode.wants),
                       "local": len(episode.local),
                       "window_s": round(episode.window_end - now, 1)})

    def _settle_spawn(self, now: float, lat: float, lon: float) -> None:
        """When the open episode's core has landed: one scenery reload if
        a file missed the window where X-Plane still shows it coarse."""
        episode = self.spawn.episode
        stale = self.spawn.settle(self._rows, lat, lon, self._failed)
        if stale is None:
            return
        sent, error = False, ""
        if stale and self.reloader is not None:
            try:
                sent = bool(self.reloader())
            except Exception as failure:    # X-Plane gone: no reload
                error = repr(failure)[:200]
        if sent:
            self.spawn.reloaded(now)
            self.counts["reloads"] += 1
        self._log({"spawn_done": episode.witness,
                   "landed": len(episode.landed),
                   "missed": len(episode.missed), "stale": len(stale),
                   "reload": "sent" if sent else "no",
                   **({"error": error} if error else {})})

    # ------------------------------------------------------------- plan

    def _reload_rows(self, now: float) -> None:
        """The rows read at once, on the tick (the open, a flight plan's
        tiles just rescanned)."""
        self._take_snapshot(self.house.read_now())

    def _house_work(self, now: float) -> None:
        """The house's work inline when it has no thread (the tests);
        then the newest rows it read, and the camera for its sweep."""
        self.house.camera = self.motion
        if not self.house.threaded:
            self.house.step(now)
        snap = self.house.take_rows()
        if snap is not None:
            self._take_snapshot(snap)
        self.counts["downgraded"] = self.house.downgraded

    def _take_snapshot(self, snap) -> None:
        """``snap``'s rows, with the rows this job landed after its read
        began kept as the job has them."""
        rows, sharp = snap.rows, snap.sharp
        for key, seq in list(self._touched.items()):
            if seq <= snap.seq:
                del self._touched[key]
            elif key in rows and key in self._rows:
                sharp += (_is_sharp(self._rows[key]) - _is_sharp(rows[key]))
                rows[key] = self._rows[key]
        self._rows, self._tiles, self._sharp = rows, snap.tiles, sharp

    def _plan(self, now: float, planner: bool = True) -> list[PLAN.Fetch]:
        """An open spawn episode's core first, then the planner's fetches
        for every other square (none while a ``plan`` episode is open, or
        with ``planner`` false).  The core follows the camera
        (``Episode.follow``), and once its flight-start window has passed
        its files show only at a reload: the planner's fetches for a
        crossing still AHEAD (deadline in the future: X-Plane reads the
        file at its own step-up) go before it, the rest after (#2037)."""
        episode, m = self.spawn.episode, self.motion
        if episode is not None and planner and m is not None:
            episode.follow(self._rows, m.lat, m.lon, m.agl_m)
        core = (episode.fetches(self._rows, now, self._failed)
                if episode is not None else [])
        if not planner or (episode is not None and episode.witness == "plan"):
            return core
        if m is None:
            return core
        in_core = {f.square for f in core}
        squares, on_disk = [], {}
        for key in REACH.keys_within(self._tiles, m.lat, m.lon,
                                     REACH.plan_reach(m, PLAN.HORIZON_S)):
            row = self._rows[key]
            if (key in self._failed or row["state"] == "failed"
                    or key in in_core):
                continue
            squares.append(PLAN.Square(key, row["centre_lat"],
                                       row["centre_lon"], row["load_size_m"]))
            on_disk[key] = PLAN.tier_of_width(row["tier_px"])
        planned = PLAN.plan(m, squares, on_disk,
                            lead_s=self.lead_s, fetch_s=self._fetch_s)
        if episode is None or now < episode.window_end:
            return core + planned
        ahead = [f for f in planned if not f.late and f.deadline_s > 0.0]
        return ahead + core + [f for f in planned if f not in ahead]

    def _local(self):
        """Does a square need no download?  The open episode's local
        squares, and any square the lander lands from its source
        (``TierLander.from_source``: a built tile's full DDS on a mounted
        volume, #2037): they take no fetch slot (a slot bounds what is
        asked of a provider)."""
        episode = self.spawn.episode
        local = episode.local if episode is not None else frozenset()
        from_source = getattr(self.lander, "from_source", None)
        if from_source is None:
            return local.__contains__
        rows = self._rows
        return lambda key: key in local or (
            key in rows and from_source(rows[key]))

    def _update_slots(self, fetches, now: float) -> None:
        """The buffer: in-flight work first (its remaining seconds), then
        the queue in planner order, at the current slots."""
        deadlines, costs = [], []
        local = self._local()
        for key, item in self._inflight.items():
            if local(key):
                continue
            deadlines.append(item.due_at - now)
            costs.append(max(0.0, self._fetch_s[item.fetch.tier]
                             - (now - item.started)))
        queue = [f for f in fetches if not f.late
                 and f.square not in self._inflight and not local(f.square)]
        for f in queue:
            deadlines.append(f.deadline_s)
            costs.append(self._fetch_s[f.tier])
        self.queued = len(queue)
        self.buffer_s = SLOTS.buffer_s(deadlines, costs, self.slots.slots)
        self.slots.update(self.buffer_s, now)

    # --------------------------------------------------------- dispatch

    def _take_token(self, now: float) -> bool:
        """R6: at most ``lands_per_s`` landings start per second."""
        if self._tokens_at is not None:
            self._tokens = min(self.lands_per_s, self._tokens + (
                now - self._tokens_at) * self.lands_per_s)
        self._tokens_at = now
        if self._tokens < 1.0:
            return False
        self._tokens -= 1.0
        return True

    def _dispatch(self, fetches, now: float, downloads: bool = True) -> None:
        """Start the due fetches in order, as slots allow; without
        ``downloads`` (offline) only those that need none.  A download
        takes one of the current slots; a landing that needs none
        (:meth:`_local`) only a worker, so it starts past downloads that
        wait for a slot."""
        local = self._local()
        downloading = sum(1 for key in self._inflight if not local(key))
        for f in fetches:
            near = local(f.square)
            if not near and not downloads:
                continue
            if len(self._inflight) >= self.slots.max_slots:
                return
            if not f.due or f.square in self._inflight:
                continue
            if not near and downloading >= self.slots.slots:
                continue
            if not self._take_token(now):
                return
            downloading += not near
            row = self._rows[f.square]
            self._write(INDEX.set_state, row["tile"], row["name"], "upgrading")
            # started: the submit, not the tick's start (#2037: a tick
            # slow before its dispatch read as a 29-163 s landing)
            started = self.clock()
            future = self._pool.submit(self._land, dict(row), f.tier)
            self._inflight[f.square] = _InFlight(future, f, row, started,
                                                 now + f.deadline_s)
            self.last_dispatched.append(f)

    def _land(self, row: dict, tier: int):
        """On a worker: the lander's facts and when they landed.  Its
        requests go first in the server's budget (#2037)."""
        with MACHINE_SLOTS.net_priority():
            facts = self.lander(row, tier)
        return facts, self.clock()

    def _harvest(self, now: float) -> None:
        for key, item in list(self._inflight.items()):
            if not item.future.done():
                continue
            del self._inflight[key]
            try:
                facts, landed_at = item.future.result()
            except Exception as error:      # a failed fetch: counted, retried
                self._failed_landing(key, item, error)
                continue
            self._landed(key, item, facts, landed_at)

    def _landed(self, key: str, item: _InFlight, facts: dict,
                now: float) -> None:
        row = item.row
        late = item.fetch.late or now > item.due_at
        self._write(INDEX.set_state, row["tile"], row["name"], "upgraded",
                        tier_px=facts["tier_px"],
                        full_bytes=facts.get("full_bytes", 0),
                        jpeg_path=facts.get("jpeg_path"),
                        dds_cache_key=facts.get("dds_cache_key"),
                        fetched_at=now)
        if late:
            self._write(INDEX.mark_late, row["tile"], row["name"])
            self.counts["late"] += 1
        was = PLAN.tier_of_width(row["tier_px"])
        row.update(state="upgraded", tier_px=facts["tier_px"])
        if PLAN.tier_of_width(row["tier_px"]) == _FINEST and was != _FINEST:
            self._sharp += 1
        self._seq += 1
        self._touched[key] = self._seq
        self.house.landed()
        seconds = now - item.started
        tier = item.fetch.tier
        if self.spawn.episode is not None:
            self.spawn.episode.note_landed(key, tier, now)
        if facts.get("network", True):      # a download's time, not a link's
            self._fetch_s[tier] = 0.7 * self._fetch_s[tier] + 0.3 * seconds
        self._fail_streak = 0
        self.counts["landed"] += 1
        self.counts["bytes"] += int(facts.get("full_bytes") or 0)
        self.counts["network"] += int(bool(facts.get("network", True)))
        landing = {"square": key, "tier": tier,
                   "crossing": item.fetch.crossing, "late": late,
                   "started": item.started, "landed": now,
                   "slots": self.slots.slots}
        if facts.get("source_s"):           # a source landing's parts
            landing["source_s"] = facts["source_s"]
        self.landings.append(landing)
        self._log(landing)

    def _failed_landing(self, key: str, item: _InFlight, error) -> None:
        row = item.row
        count = self._failures[key] = self._failures.get(key, 0) + 1
        self._fail_streak += 1
        self.counts["failed"] += 1
        state = "failed" if count >= MAX_FAILURES else (
            "upgraded" if PLAN.tier_of_width(row["tier_px"]) > 0 else "low")
        self._write(INDEX.set_state, row["tile"], row["name"], state)
        if count >= MAX_FAILURES:
            self._failed.add(key)
        if self._fail_streak >= OFFLINE_AFTER:
            self._offline_until = self.clock() + OFFLINE_PAUSE_S
            self._fail_streak = 0
        self._log({"square": key, "tier": item.fetch.tier,
                   "error": repr(error)[:200]})

    # -------------------------------------------------------- last used

    def _mark_near(self, now: float) -> None:
        """``last_near_at`` for the rows inside their tier's distance."""
        if now - self._near_at < NEAR_EVERY_S or self.motion is None:
            return
        self._near_at = now
        m = self.motion
        near_by_tile: dict[str, list[str]] = {}
        near = set()
        for key in REACH.keys_within(self._tiles, m.lat, m.lon,
                                     REACH.near_reach()):
            row = self._rows[key]
            if INDEX.distance_m(row, m.lat, m.lon) <= INDEX.tier_distance_m(row):
                near.add(key)
                near_by_tile.setdefault(row["tile"], []).append(row["name"])
        if near_by_tile:                    # written by the house
            self.house.near(now, near_by_tile, near - self._near)
        self._near = near

    # ----------------------------------------------------------- report

    def status(self) -> dict:
        """The fields of ``ImageryFollowStatus``."""
        m = self.motion
        sharp = self._sharp     # counted at each reread and landing (#2037)
        return {
            "state": self.state, "reason": self.reason,
            "xplane": self.state not in ("waiting", "starting"),
            "lat": round(m.lat, 6) if m else 0.0,
            "lon": round(m.lon, 6) if m else 0.0,
            "speed_ms": round(m.groundspeed_ms, 1) if m else 0.0,
            "track_deg": round(m.track_deg, 1) if m else 0.0,
            "queued": self.queued, "in_flight": len(self._inflight),
            "slots": self.slots.slots,
            "buffer_s": (-1.0 if math.isinf(self.buffer_s)
                         else round(self.buffer_s, 1)),
            "sharp": sharp, "textures": len(self._rows),
            "landed": self.counts["landed"], "late": self.counts["late"],
            "failed": self.counts["failed"],
            "bytes_landed": self.counts["bytes"],
            "flight_loads": self.reader.resets,
            "jumps": self.tracker.jumps,
            "reloads": self.counts["reloads"],
            "reload_offer": _pending_offer(),
        }

    def _status(self, now: float, force: bool = False) -> None:
        fields = self.status()
        changed = (fields["state"], fields["reason"], fields["landed"],
                   fields["failed"], fields["slots"], fields["reloads"],
                   fields["reload_offer"])
        if not force and changed == self._last_status and (
                now - self._status_at < STATUS_EVERY_S):
            return
        self._last_status, self._status_at = changed, now
        from .events import ImageryFollowStatus
        self.emit(ImageryFollowStatus(**fields))

    def _log(self, record: dict) -> None:
        """One line of ``logs/imagery_on_demand.log`` (spec §4.4)."""
        write_log(self.log_path, record)


def log_path() -> str:
    """``logs/imagery_on_demand.log`` under the data root."""
    import O4_File_Names as FNAMES
    return os.path.join(FNAMES.data_path("logs"), "imagery_on_demand.log")


def write_log(path, record: dict) -> None:
    """One ``key=value`` line of the on-demand log at ``path`` (none
    when ``path`` is empty); never raises."""
    if not path:
        return
    with contextlib.suppress(OSError):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(time.strftime("%Y-%m-%dT%H:%M:%S ")
                         + " ".join(f"{k}={v}" for k, v in record.items())
                         + "\n")
