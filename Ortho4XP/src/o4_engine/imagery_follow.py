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
* PAUSE: no new fetch starts while a build runs (``busy()``) or while a
  Library command that changes tiles holds :func:`paused` — the converter
  and a build would race on ``textures/``; fetches in flight finish;
* no network: :data:`OFFLINE_AFTER` failures in a row pause fetching for
  :data:`OFFLINE_PAUSE_S` ("Offline: imagery stays low-res"); a texture
  that fails :data:`MAX_FAILURES` times is ``failed`` until next session;
* X-Plane not running or its Web API off: the job idles and says so;
* a Web API id reset after a drop (a flight load) and a camera jump are
  counted (``flight_loads``, ``jumps``): the witnesses spec §4.5 (P5)
  acts on.

``last_near_at`` is written for the rows the camera is within their
tier's distance of, while the sim is not paused (spec §5.3).  The job
reports through ``ImageryFollowStatus`` events.
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
import O4_Imagery_OnDemand_Index as INDEX
import O4_Imagery_Tier_Plan as PLAN
import O4_XPlane_WebAPI as WEBAPI
from O4_Imagery_Follow_Motion import MotionTracker

__all__ = ["MAX_FAILURES", "OFFLINE_AFTER", "OFFLINE_PAUSE_S", "FollowJob",
           "paused"]

#: A texture that fails this many times is ``failed`` for the session.
MAX_FAILURES = 3
#: Failures in a row (any textures) that read as "no network".
OFFLINE_AFTER = 3
#: Seconds fetching pauses after that (the fetcher's own AIMD pause runs
#: inside each fetch; this is the job's).
OFFLINE_PAUSE_S = 60.0
#: Seconds between status events when nothing changed.
STATUS_EVERY_S = 2.0
#: Seconds between rereads of the index rows (landings update them live).
ROWS_EVERY_S = 30.0
#: Seconds between ``last_near_at`` writes (the index throttles per row).
NEAR_EVERY_S = 10.0
#: Default seconds one landing takes per tier before any is measured
#: (the P3a replay's model at 85 requests/s and a 2 s full convert).
DEFAULT_FETCH_S = {1: 0.3, 2: 1.9, 3: 5.0}

_PAUSES = 0
_PAUSES_GUARD = threading.Lock()


@contextlib.contextmanager
def paused(_reason: str = ""):
    """While held, no follow job starts a new fetch (a Library command that
    deletes or replaces tiles holds it)."""
    global _PAUSES
    with _PAUSES_GUARD:
        _PAUSES += 1
    try:
        yield
    finally:
        with _PAUSES_GUARD:
            _PAUSES -= 1


def pause_count() -> int:
    """How many holders of :func:`paused` there are now."""
    return _PAUSES


def _placeholder_root() -> str:
    import O4_File_Names as FNAMES
    import O4_Imagery_Placeholder as PLACEHOLDER
    return os.path.join(FNAMES.data_path(PLACEHOLDER.STORE_DIR),
                        "placeholders")


def _key(row: dict) -> str:
    return f"{row['tile']}/{row['name']}"


def _tier_of_px(px) -> int:
    """The tier index of a file ``px`` wide (unknown widths read as 0)."""
    try:
        return PLAN.TIER_WIDTH.index(int(px))
    except (TypeError, ValueError):
        return 0


class _InFlight(_t.NamedTuple):
    future: _futures.Future
    fetch: PLAN.Fetch
    row: dict
    started: float
    due_at: float           # absolute time of the crossing it serves


class FollowJob:
    """One follow session.  ``reader`` is an ``O4_XPlane_WebAPI``
    ``PositionReader``; ``lander(row, tier)`` lands one file and returns
    the index facts (``imagery_follow_land.TierLander``); ``index_path``
    the index file; ``busy()`` is true while a build runs; ``emit``
    receives each ``ImageryFollowStatus``."""

    def __init__(self, emit, *, reader, lander, index_path=None,
                 busy=lambda: False, lead_s: float = PLAN.DEFAULT_LEAD_S,
                 period_s: float = 1.0, max_slots: int = SLOTS.MAX_SLOTS,
                 lands_per_s: float = 4.0, clock=time.time, log_path=None,
                 slots: SLOTS.FetchSlots | None = None, rebuild_tiles=()):
        self.emit = emit
        self.reader, self.lander = reader, lander
        self.index_path = index_path
        self.rebuild_tiles = [tuple(t) for t in rebuild_tiles or ()]
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
        self._rows_at = -math.inf
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
                       "network": 0}
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
        """The loop: :meth:`open`, then :meth:`tick` every ``period_s``."""
        try:
            self.open()
            while not self._stop.is_set():
                t0 = time.monotonic()
                self.tick()
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
        self._reload_rows(self.clock())

    def close(self) -> None:
        """Let the fetches in flight finish (bounded), record them, and
        say "stopped"."""
        pending = [f.future for f in self._inflight.values()]
        if pending:
            _futures.wait(pending, timeout=10.0)
        self._harvest(self.clock())
        self._pool.shutdown(wait=False, cancel_futures=True)
        if self.state != "error":
            self.state, self.reason = "stopped", ""
        self._status(self.clock(), force=True)
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # --------------------------------------------------------------- tick

    def tick(self) -> None:
        """One cycle: read, plan, harvest, dispatch, report."""
        now = self.clock()
        self._harvest(now)
        rec = self.reader.read()
        if rec is None:
            self.state = "waiting"
            self.reason = "X-Plane is not running or its Web API is off"
            self._status(now)
            return
        lat, lon = WEBAPI.camera_position(rec)
        self.motion = self.tracker.add(now, lat, lon,
                                       float(rec.get("elev_m") or 0.0))
        if now - self._rows_at >= ROWS_EVERY_S:
            self._reload_rows(now)
        fetches = self.last_plan = self._plan()
        self.last_dispatched = []
        self._update_slots(fetches, now)
        if not rec.get("paused"):
            self._mark_near(now)
        why = self._why_paused(now)
        if why:
            self.state, self.reason = "paused", why
        else:
            self.state, self.reason = "following", ""
            self._dispatch(fetches, now)
        self._status(now)

    def _why_paused(self, now: float) -> str:
        if self.busy() or pause_count():
            return "A build is running; imagery waits for it"
        if now < self._offline_until:
            return "Offline: imagery stays low-res"
        return ""

    # ------------------------------------------------------------- plan

    def _reload_rows(self, now: float) -> None:
        self._rows = {_key(r): r for r in INDEX.rows(self._conn)
                      if r.get("centre_lat") is not None
                      and r.get("load_size_m")}
        self._rows_at = now

    def _plan(self) -> list[PLAN.Fetch]:
        squares, on_disk = [], {}
        for key, row in self._rows.items():
            if key in self._failed or row["state"] == "failed":
                continue
            squares.append(PLAN.Square(key, row["centre_lat"],
                                       row["centre_lon"], row["load_size_m"]))
            on_disk[key] = _tier_of_px(row["tier_px"])
        if self.motion is None:
            return []
        return PLAN.plan(self.motion, squares, on_disk, lead_s=self.lead_s,
                         fetch_s=self._fetch_s)

    def _update_slots(self, fetches, now: float) -> None:
        """The buffer: in-flight work first (its remaining seconds), then
        the queue in planner order, at the current slots."""
        deadlines, costs = [], []
        for item in self._inflight.values():
            deadlines.append(item.due_at - now)
            costs.append(max(0.0, self._fetch_s[item.fetch.tier]
                             - (now - item.started)))
        queue = [f for f in fetches if not f.late
                 and f.square not in self._inflight]
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

    def _dispatch(self, fetches, now: float) -> None:
        for f in fetches:
            if len(self._inflight) >= self.slots.slots:
                return
            if not f.due or f.square in self._inflight:
                continue
            if not self._take_token(now):
                return
            row = self._rows[f.square]
            INDEX.set_state(self._conn, row["tile"], row["name"], "upgrading")
            future = self._pool.submit(self._land, dict(row), f.tier)
            self._inflight[f.square] = _InFlight(future, f, row, now,
                                                 now + f.deadline_s)
            self.last_dispatched.append(f)

    def _land(self, row: dict, tier: int):
        """On a worker: the lander's facts and when they landed."""
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
        INDEX.set_state(self._conn, row["tile"], row["name"], "upgraded",
                        tier_px=facts["tier_px"],
                        full_bytes=facts.get("full_bytes", 0),
                        jpeg_path=facts.get("jpeg_path"),
                        dds_cache_key=facts.get("dds_cache_key"),
                        fetched_at=now)
        if late:
            INDEX.mark_late(self._conn, row["tile"], row["name"])
            self.counts["late"] += 1
        row.update(state="upgraded", tier_px=facts["tier_px"])
        seconds = now - item.started
        tier = item.fetch.tier
        self._fetch_s[tier] = 0.7 * self._fetch_s[tier] + 0.3 * seconds
        self._fail_streak = 0
        self.counts["landed"] += 1
        self.counts["bytes"] += int(facts.get("full_bytes") or 0)
        self.counts["network"] += int(bool(facts.get("network", True)))
        landing = {"square": key, "tier": tier,
                   "crossing": item.fetch.crossing, "late": late,
                   "started": item.started, "landed": now,
                   "slots": self.slots.slots}
        self.landings.append(landing)
        self._log(landing)

    def _failed_landing(self, key: str, item: _InFlight, error) -> None:
        row = item.row
        count = self._failures[key] = self._failures.get(key, 0) + 1
        self._fail_streak += 1
        self.counts["failed"] += 1
        state = "failed" if count >= MAX_FAILURES else (
            "upgraded" if _tier_of_px(row["tier_px"]) > 0 else "low")
        INDEX.set_state(self._conn, row["tile"], row["name"], state)
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
        cos_lat = math.cos(math.radians(m.lat))
        near_by_tile: dict[str, list[str]] = {}
        near = set()
        for key, row in self._rows.items():
            reach = PLAN.CROSSING_S[_tier_of_px(row["tier_px"])] * row[
                "load_size_m"]
            east = (row["centre_lon"] - m.lon) * 111_320.0 * cos_lat
            north = (row["centre_lat"] - m.lat) * 111_320.0
            if math.hypot(east, north) <= reach:
                near.add(key)
                near_by_tile.setdefault(row["tile"], []).append(row["name"])
        for tile, names in near_by_tile.items():
            fresh = [n for n in names if f"{tile}/{n}" not in self._near]
            INDEX.mark_near(self._conn, tile, names, now, approaching=fresh)
        self._near = near

    # ----------------------------------------------------------- report

    def status(self) -> dict:
        """The fields of ``ImageryFollowStatus``."""
        m = self.motion
        sharp = sum(1 for r in self._rows.values()
                    if _tier_of_px(r["tier_px"]) == len(PLAN.TIER_WIDTH) - 1)
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
        }

    def _status(self, now: float, force: bool = False) -> None:
        fields = self.status()
        changed = (fields["state"], fields["reason"], fields["landed"],
                   fields["failed"], fields["slots"])
        if not force and changed == self._last_status and (
                now - self._status_at < STATUS_EVERY_S):
            return
        self._last_status, self._status_at = changed, now
        from .events import ImageryFollowStatus
        self.emit(ImageryFollowStatus(**fields))

    def _log(self, record: dict) -> None:
        """One line of ``logs/imagery_on_demand.log`` (spec §4.4)."""
        if not self.log_path:
            return
        with contextlib.suppress(OSError):
            os.makedirs(os.path.dirname(self.log_path) or ".", exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8",
                      newline="\n") as handle:
                handle.write(time.strftime("%Y-%m-%dT%H:%M:%S ")
                             + " ".join(f"{k}={v}" for k, v in record.items())
                             + "\n")
