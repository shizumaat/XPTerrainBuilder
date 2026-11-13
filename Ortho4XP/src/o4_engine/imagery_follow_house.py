"""The follow job's slow index work, off its tick (#2037).

The follow job (``imagery_follow.FollowJob``) ticks once a second: it
harvests the landings, plans and dispatches.  Three pieces of its work
read or write the whole index and took seconds each on the tick's own
thread:

* the reread of every row (215,209 rows on 2026-11-13: 1.5-2.7 s; one
  ``sqlite3`` step per row, and each step releases and re-takes the GIL:
  beside two busy Python threads 5,000 rows took 15 s, the whole index
  would take ~650 s);
* the storage measure of the in-session sweep (``storage_budget.
  session_budget``: a ``stat`` of every kept placeholder, ~1.2 s) and the
  sweep itself (``imagery_downgrade.sweep``);
* the ``last_near_at`` writes (one UPDATE per row near the camera).

While a World drape run shared the engine process its threads held the
GIL, and each of those hand-offs waited its turn: at CYEG on 2026-11-13
landed squares were counted 44-176 s after they landed, their slots idle
that long.  :class:`FollowHouse` does that work on its own thread and
connection, the reread one step per TILE (``INDEX.all_rows``: 8.6 s
beside the same two threads, 0.6 s idle) and the storage floor measured
at most every :data:`FLOOR_EVERY_S`; the tick only takes the newest
snapshot of the rows
(:meth:`FollowHouse.take_rows`) and hands over the near rows and the
landings.  Not started (the tests drive the tick by hand),
:meth:`FollowHouse.step` runs inline from the tick, as before.

The sweep downgrades files: while it runs the house holds
:attr:`FollowHouse.dispatch_guard`, which the tick takes (never waiting)
around its dispatch, so no square is set ``upgrading`` between the
sweep's choice of rows and their downgrade.
"""
from __future__ import annotations

import math
import threading
import time
import typing as _t

import O4_Imagery_Follow_Reach as REACH
import O4_Imagery_OnDemand_Index as INDEX
import O4_Imagery_Tier_Plan as PLAN

__all__ = ["FLOOR_EVERY_S", "ROWS_EVERY_S", "SWEEP_EVERY_S", "FollowHouse"]

#: Seconds between rereads of the index rows (landings update them live).
ROWS_EVERY_S = 30.0
#: Seconds between storage-cap checks while landing (spec §6.2: during a
#: session a sweep starts only over 110 % of the cap).
SWEEP_EVERY_S = 60.0
#: Seconds a measured storage floor (a ``stat`` of every placeholder) is
#: reused by the sweep's 110 % check.
FLOOR_EVERY_S = 600.0
#: Seconds the house thread sleeps between looks at its work.
PERIOD_S = 0.25


class _Snapshot(_t.NamedTuple):
    """The rows read (``{key: row}``), their tiles (``REACH.by_tile``),
    the job's landing count when the read began (``seq``: a row the job
    changed after that is the job's, not the snapshot's) and the rows at
    the finest tier (``sharp``, the status line's)."""
    rows: dict
    tiles: dict
    seq: int
    sharp: int


def _read_rows(conn) -> dict:
    """``{"tile/name": row}`` of every index row with a centre and a
    size (what the planner can place)."""
    return {f"{r['tile']}/{r['name']}": r for r in INDEX.all_rows(conn)
            if r.get("centre_lat") is not None and r.get("load_size_m")}


class FollowHouse:
    """The index work of one follow job.  ``index_path``: its index;
    ``conn``: the job's connection (inline work only); ``seq()``: the
    job's landing count; ``cap_bytes``: the sharp imagery cap (0 or
    ``None``: no sweep); ``abort()``: the job is stopping."""

    def __init__(self, index_path, conn, *, seq: _t.Callable[[], int],
                 cap_bytes: "int | None", clock=time.time,
                 log: _t.Callable[[dict], None] = lambda record: None,
                 abort: _t.Callable[[], bool] = lambda: False,
                 rows_every_s: float = ROWS_EVERY_S,
                 sweep_every_s: float = SWEEP_EVERY_S):
        self.index_path, self.conn = index_path, conn
        self.seq, self.cap_bytes, self.clock = seq, cap_bytes, clock
        self.log, self.abort = log, abort
        self.rows_every_s, self.sweep_every_s = rows_every_s, sweep_every_s
        self.dispatch_guard = threading.Lock()
        self.camera = None                  # the job's motion, for the sweep
        self.downgraded = 0
        self._guard = threading.Lock()
        self._snapshot: "_Snapshot | None" = None
        self._rows_at = -math.inf
        self._rows_wanted = False
        self._sweep_at = -math.inf
        self._budget = None                 # (measured at, Budget)
        self._landed = 0
        self._near: list = []               # (now, {tile: names}, fresh)
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: "threading.Thread | None" = None

    # ------------------------------------------------------ from the tick

    def read_now(self) -> _Snapshot:
        """The rows read at once on the job's connection (its open, a
        flight plan's tiles just rescanned)."""
        snap = self._read(self.conn)
        with self._guard:
            self._snapshot, self._rows_at = None, self.clock()
            self._rows_wanted = False
        return snap

    def want_rows(self) -> None:
        """Reread the rows soon (a rescan finished, a sweep downgraded)."""
        with self._guard:
            self._rows_wanted = True
        self._wake.set()

    def landed(self) -> None:
        """One landing since the last sweep."""
        with self._guard:
            self._landed += 1

    def near(self, now: float, names_by_tile: dict, fresh) -> None:
        """``last_near_at`` = ``now`` for ``names_by_tile``; ``fresh``:
        the keys just approached (their ``near_count``)."""
        with self._guard:
            self._near.append((now, names_by_tile, set(fresh)))
        self._wake.set()

    def take_rows(self) -> "_Snapshot | None":
        """The newest snapshot not yet taken, or ``None``."""
        with self._guard:
            snap, self._snapshot = self._snapshot, None
        return snap

    # --------------------------------------------------------- the work

    def step(self, now: float, conn=None) -> None:
        """Whatever is due: the near writes, the sweep, the reread."""
        conn = conn if conn is not None else self.conn
        self._write_near(conn)
        if self._sweep_due(now):
            self._sweep(conn, now)
        with self._guard:
            due = self._rows_wanted or now - self._rows_at >= self.rows_every_s
        if due:
            snap = self._read(conn)
            with self._guard:
                self._snapshot, self._rows_at = snap, now
                self._rows_wanted = False

    def _read(self, conn) -> _Snapshot:
        seq = self.seq()
        rows = _read_rows(conn)
        finest = len(PLAN.TIER_WIDTH) - 1
        sharp = sum(1 for r in rows.values()
                    if PLAN.tier_of_width(r["tier_px"]) == finest)
        return _Snapshot(rows, REACH.by_tile(rows), seq, sharp)

    def _write_near(self, conn) -> None:
        with self._guard:
            batches, self._near = self._near, []
        for now, names_by_tile, fresh in batches:
            for tile, names in names_by_tile.items():
                INDEX.mark_near(conn, tile, names, now, approaching=[
                    n for n in names if f"{tile}/{n}" in fresh])

    def _sweep_due(self, now: float) -> bool:
        with self._guard:
            return bool(self._landed and self.cap_bytes
                        and now - self._sweep_at >= self.sweep_every_s)

    def _sweep(self, conn, now: float) -> None:
        """The 110 % trigger (spec §6.2): ``imagery_downgrade.sweep`` in
        session mode, sparing the squares near the camera; the measure
        first, the downgrades under :attr:`dispatch_guard`."""
        from .imagery_downgrade import sweep
        from .storage_budget import session_budget
        with self._guard:
            self._sweep_at, self._landed = now, 0
        if self._budget is None or now - self._budget[0] >= FLOOR_EVERY_S:
            self._budget = (now, session_budget(conn, self.cap_bytes))
        budget = self._budget[1]
        with self.dispatch_guard:
            result = sweep(conn, budget, camera=self.camera, in_session=True,
                           now=now, abort=self.abort)
        if result.get("downgraded"):
            self.downgraded += result["downgraded"]
            self.want_rows()

    # ------------------------------------------------------- the thread

    def start(self) -> "FollowHouse":
        """Do the work on its own thread and connection from now on."""
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="o4-imagery-follow-house")
        self._thread.start()
        return self

    @property
    def threaded(self) -> bool:
        """Does the work run on the house's own thread?"""
        return self._thread is not None

    def stop(self, timeout: float = 10.0) -> None:
        """Stop the thread (its current step finishes, bounded)."""
        self._stop.set()
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def _run(self) -> None:
        conn = INDEX.open_index(self.index_path)
        try:
            while not self._stop.is_set():
                try:
                    self.step(self.clock(), conn)
                except Exception as error:      # logged; the job goes on
                    self.log({"house_error": repr(error)[:300]})
                self._wake.wait(PERIOD_S)
                self._wake.clear()
            self._write_near(conn)              # the last near rows kept
        finally:
            conn.close()
