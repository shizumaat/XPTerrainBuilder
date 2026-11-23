"""THE MACHINE WORKER BUDGET — one slot pool for every heavy process of an
engine session (issue #1225).

Tiles build in separate worker processes, each tile's auto-patch starts one
process per airport, and each airport's work pool starts more: nine tiles
at once put 40+ airport processes and their pools on a 128 GB machine and
exhausted it.  Nothing tied the count to the memory the machine has, or to
the other tiles of the run.

This module is that tie.  An engine session owns ONE pool of ``capacity``
slots, a directory of slot files every process of the session finds through
:data:`ENV_DIR` (inherited down the whole process tree).  A process holds a
slot by holding an OS lock on one slot file — released by the system when
the holder exits, however it exits, so a killed build never leaks a slot.

* an airport build takes ONE slot before it starts (:func:`take`, which
  waits for a free one: an airport beyond the budget queues);
* a work pool takes a slot per worker it starts (:func:`try_take`, which
  never waits: a pool gets what is free, and with fewer than two runs its
  stage serially in the process that already holds a slot);
* a tile's heavy step (vector, mesh/Triangle4XP, masks, DSF + imagery,
  overlays) holds ONE slot for its own process (:func:`step`), lent back
  while the process only waits on airport workers it starts
  (:func:`lend`); a DDS conversion pool takes a slot per extra worker.

A worker PROCESS is started only after its slot is granted: nothing waits
resident for a slot (#1225, second report: every airport of a tile was
spawned up front and queued for a slot at ~2 GB each).

``capacity`` (:func:`capacity`) is ``min(cores - reserved, memory slots)``:
the memory the machine could hand out when the session started, less the
headroom of :data:`BUDGET`, at :data:`BUDGET`'s per-worker estimate,
sampled ONCE per session.  What is LIVE is the memory gate
(:func:`memory_admits`, :func:`machine_verdict`): before a new slot is
granted it asks the MACHINE MEMORY LEDGER (``O4_Machine_Memory``), which
every engine session of the machine shares — free memory less what other
builds' admitted work has still to grow into, X-Plane and the app's room —
and each grant reserves its memory there (``worker_gb`` a slot, or the
step's own estimate) until it is released.  Below the headroom nothing new
starts until it recovers — unless the session holds no slot at all and the
ledger's progress rule lets it run one.  A process that finds no session
(a command-line tile, the harness) opens its own with the same rule.

:func:`lower_priority` runs the engine below the user's applications, and
its builds below its own command process (owner 2026-11-20T18:40Z: "an
active dialog should take precedence over any builds which should be in the
background"): the command process at nice 5, every build worker's tree at
nice 10 (Windows: below-normal for both).  Workers run at
NORMAL QoS — no macOS utility clamp, which confined them to the efficiency
cores (owner RULINGS 2026-10-22k): nice only yields time to the user's apps,
it still runs on the performance cores; the slot budget and the memory gate
are what keep the machine from freezing.

NAMED CLASSES (#1236) are a second kind of pool in the same session
directory: ``class-<name>/slot-k`` for ``k < limit``, the same OS locks,
no memory gate.  A class is a budget the session's processes share — a
server's: :func:`net_class` names one per host, and the imagery threads,
the async imagery fetcher and the elevation downloads of EVERY tile of
the session hold one slot of it per request in flight
(:func:`try_take_class`, :func:`take_class`, :func:`hold_class`).  Ten
tiles on one imagery server are then one limit on that server, not ten.
A class wait is bounded (:data:`CLASS_WAIT_S`): past it the caller goes
on without a slot, so a wedged holder costs a request over the budget,
never a hung build.

PRIORITY (#2037): requests made inside :func:`net_priority` (the imagery
follow job: the squares the camera flies toward) go FIRST in every
class.  A priority request that finds no free slot leaves a demand mark
in the class (``want/<pid>-<thread>``, its mtime refreshed at each
refused attempt and live for :data:`DEMAND_TTL_S`); while any process's
mark is live, no other request takes a slot of that class, so the next
slot freed goes to the camera.  The class's limit is unchanged: the
server sees the same load, ordered.

Standard library only (with :mod:`O4_Parallel_Utils`' memory probes): the
airport pool, the tile driver and the orchestrator all import it.
"""
from __future__ import annotations

import atexit
import contextlib
import hashlib
import os
import shutil
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit

import O4_Machine_Memory as _MEM
import O4_Parallel_Utils as _PU

if sys.platform == "win32":                # module level: a freezer sees it
    import msvcrt as _oslock
else:
    import fcntl as _oslock

__all__ = ["BUDGET", "CLASS_WAIT_S", "DEMAND_TTL_S", "ENV_DIR", "ENV_CAPACITY",
           "ENV_UNGATED", "Held", "capacity", "headroom_gigabytes", "carry_net_priority",
           "ensure_session", "has_net_priority", "hold_class", "lend", "lend_step",
           "release_os_lock", "retake_step", "try_os_lock",
           "background_priority", "lower_priority", "machine_verdict",
           "COMMAND_NICE", "ENV_BUILD_WORKER", "NICE",
           "memory_admits", "net_class", "note_memory_wait",
           "hold_net_for_flight", "net_priority", "session_capacity",
           "step", "take_class", "try_take", "try_take_class", "take"]

#: the session's slot directory and its capacity, inherited by every child
ENV_DIR = "O4_MACHINE_SLOTS_DIR"
ENV_CAPACITY = "O4_MACHINE_SLOTS"
#: set only by a session that proves MECHANICS, not the machine (the pool
#: self-check, the tests): its explicit capacity is not shrunk by the live
#: memory gate.  A real build never sets it.
ENV_UNGATED = "O4_MACHINE_SLOTS_UNGATED"

#: THE BUDGET LAW (gigabytes / fractions).  Kept here, not in an auto-patch
#: law table: those are hashed into the partition cache key, and how many
#: workers a machine affords must never enter a digest.
#:
#: ``worker_gb`` — what one heavy process (an airport build, or one worker
#: of its pool) is budgeted.  Provenance: a live auto-patch solve held
#: 2.55 GB resident (HECA, ``o4_engine.parallel.STEP_MEMORY_ESTIMATES_GB``),
#: pool workers 1.25-2.0 GB at OTHH (``airport.pool.WORKER_ALLOWANCE_GB``);
#: idle airport workers were seen at ~2 GB on the owner's machine (#1225).
#: Rounded UP to 3.0.  No per-airport peak is recorded anywhere yet; refine
#: this when one is.
#: ``headroom_fraction`` / ``headroom_min_gb`` — what is kept free for the
#: operating system, the app and the user's other work: the larger of
#: 15 % of physical memory and 8 GB (owner, #1225).
#: ``reserved_cores`` — cores never given to the build (owner, #1225:
#: "cores - 2"), so the window server and input always have one.
BUDGET = {
    "worker_gb": 3.0,
    "headroom_fraction": 0.15,
    "headroom_min_gb": 8.0,
    "reserved_cores": 2,
}

#: the nice value :func:`lower_priority` sets (POSIX) for a build worker's
#: tree, the one it sets for the engine's command process (the app's pipe:
#: its commands and dialog answers, above its builds and below the user's
#: applications), the variable that marks a process tree already lowered,
#: and the one a build worker is spawned with (``o4_engine.parallel``)
NICE = 10
COMMAND_NICE = 5
ENV_PRIORITY = "O4_ENGINE_PRIORITY_LOWERED"
ENV_BUILD_WORKER = "O4_ENGINE_BUILD_WORKER"

#: seconds between attempts of a :func:`take` that is waiting
POLL_S = 0.5


def capacity(cores: int, total_gb: float, available_gb: float,
             budget: dict = BUDGET) -> int:
    """Slots a machine of ``cores`` logical cores, ``total_gb`` physical and
    ``available_gb`` free-or-reclaimable memory affords — never below 1
    (a machine without the room still builds, one process at a time)."""
    by_memory = int((available_gb - _headroom(total_gb, budget))
                    // budget["worker_gb"])
    by_cores = int(cores) - int(budget.get("reserved_cores", 0))
    return max(1, min(by_cores, by_memory))


def _headroom(total_gb: float, budget: dict = BUDGET) -> float:
    return max(budget["headroom_fraction"] * total_gb, budget["headroom_min_gb"])


def headroom_gigabytes(budget: dict = BUDGET) -> float:
    """Gigabytes every gate keeps free for the operating system, the app
    and the user's other work: the larger of ``headroom_fraction`` of this
    machine's physical memory and ``headroom_min_gb`` (owner, #1225)."""
    return _headroom(_PU.machine_memory_gigabytes(), budget)


def memory_admits(budget: dict = BUDGET, need_gb: "float | None" = None) -> bool:
    """THE LIVE GATE: may one more heavy process of ``need_gb`` (default:
    one worker's estimate) start now?  :func:`machine_verdict`'s answer."""
    return machine_verdict(need_gb, budget=budget).ok


def machine_verdict(need_gb: "float | None" = None, *, idle: bool = False,
                    budget: dict = BUDGET) -> "_MEM.Verdict":
    """The machine memory ledger's answer (``O4_Machine_Memory.admits``)
    for ``need_gb`` more, keeping this machine's headroom: free memory
    (``O4_Parallel_Utils`` caches it two seconds) less every build's
    outstanding reservations, X-Plane's and the app's room.  ``idle``: the
    caller holds nothing (the ledger's progress rule).  Always yes in a
    session that set :data:`ENV_UNGATED`.  The tile scheduler asks it with
    a step's own projected peak before it starts a step (#2083)."""
    if os.environ.get(ENV_UNGATED):
        return _MEM.Verdict(ok=True)
    need = budget["worker_gb"] if need_gb is None else float(need_gb)
    return _MEM.admits(need, headroom_gigabytes(budget), idle=idle)


def _measured_capacity() -> int:
    return capacity(_PU.machine_core_count(), _PU.machine_memory_gigabytes(),
                    _PU.machine_available_memory_gigabytes())


_SESSION_OPEN = threading.Lock()


def ensure_session() -> tuple[str, int]:
    """``(slot directory, capacity)`` of this process's session — the one
    inherited through :data:`ENV_DIR`, or a new one published in
    ``os.environ`` so every child started from here shares it.  An explicit
    :data:`ENV_CAPACITY` without a directory pins the capacity."""
    path = os.environ.get(ENV_DIR, "")
    if path and os.path.isdir(path):
        return path, _capacity_from_env()
    # One opener at a time: threads that open the first session together
    # (two tiles' fetch pools) would each mint a directory, and each
    # directory is a separate cap.
    with _SESSION_OPEN:
        path = os.environ.get(ENV_DIR, "")
        if path and os.path.isdir(path):
            return path, _capacity_from_env()
        try:
            cap = max(1, int(os.environ.get(ENV_CAPACITY, "")))
        except ValueError:
            cap = _measured_capacity()
        path = tempfile.mkdtemp(prefix="o4-slots-")
        atexit.register(shutil.rmtree, path, True)
        _MEM.session_id()              # the ledger's session: this one
        os.environ[ENV_CAPACITY] = str(cap)
        os.environ[ENV_DIR] = path
        return path, cap


def _capacity_from_env() -> int:
    try:
        return max(1, int(os.environ.get(ENV_CAPACITY, "")))
    except ValueError:
        return 1


def session_capacity() -> int:
    """The session's capacity (:func:`ensure_session` opens one if needed)."""
    return ensure_session()[1]


class Held:
    """Slots this process holds, and the memory they reserved on the
    machine ledger (``gb`` a slot); :meth:`release` (or the context exit,
    or the process's exit) gives both back."""

    def __init__(self, fds: list, gb: float = 0.0,
                 reservation: "_MEM.Reservation | None" = None) -> None:
        self._fds = list(fds)
        self.gb = float(gb)
        self._reservation = reservation

    @property
    def count(self) -> int:
        return len(self._fds)

    def settle(self, per_gb: float) -> None:
        """Lower the reservation to ``per_gb`` a slot once the processes it
        covers were measured at their working size (never raises it): the
        flat ``worker_gb`` is a guess made before a worker exists, and a
        pool of 16 kept 48 GB booked while its workers held a third of it
        (owner 2026-11-18, "waiting for memory" with 60 GB free)."""
        if self._reservation is None or not self._fds:
            return
        per = max(0.0, float(per_gb))
        if per < self.gb:
            self._reservation.settle(per * len(self._fds))
            self.gb = per

    def release(self) -> None:
        fds, self._fds = self._fds, []
        reservation, self._reservation = self._reservation, None
        for fd in fds:
            _unlock(fd)
        if reservation is not None:
            reservation.release()

    def __enter__(self) -> "Held":
        return self

    def __exit__(self, *exc) -> None:
        self.release()

    def __del__(self) -> None:
        try:
            self.release()
        except Exception:
            pass


def _lock(path: str):
    """:func:`try_os_lock`, with an unopenable file read as "held"."""
    try:
        return try_os_lock(path)
    except OSError:
        return None


def try_os_lock(path: str):
    """An open descriptor holding ``path``'s OS lock, or ``None`` when
    another process (or another descriptor of this one) holds it.  The
    system drops the lock when the holder exits, however it exits.  An
    ``OSError`` means the file cannot be opened at all (a read-only or
    missing folder): no wait would ever end that."""
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if sys.platform == "win32":
            _oslock.locking(fd, _oslock.LK_NBLCK, 1)
        else:
            _oslock.flock(fd, _oslock.LOCK_EX | _oslock.LOCK_NB)
    except OSError:
        os.close(fd)
        return None
    return fd


def _unlock(fd) -> None:
    try:
        if sys.platform == "win32":
            os.lseek(fd, 0, os.SEEK_SET)
            _oslock.locking(fd, _oslock.LK_UNLCK, 1)
    except OSError:
        pass
    try:
        os.close(fd)                       # closing releases a flock
    except OSError:
        pass


#: gives back a lock :func:`try_os_lock` took
release_os_lock = _unlock


def try_take(n: int, gb: "float | None" = None, what: str = "") -> Held:
    """Up to ``n`` free slots, at once and never waiting (possibly none),
    each reserving ``gb`` (default ``worker_gb``; 0: no memory gate, the
    caller's parent reserved it) on the machine ledger.

    As many are granted as the ledger has room for (:func:`machine_verdict`);
    with no room nothing is granted — except one slot when the whole
    session holds none and the ledger's progress rule lets it run."""
    path, cap = ensure_session()
    if n <= 0:
        return Held([])
    per = BUDGET["worker_gb"] if gb is None else max(0.0, float(gb))
    if per <= 0.0 or os.environ.get(ENV_UNGATED):
        return _take_free(path, cap, n, per, what)
    with _MEM.admission():                 # read and reserve as one
        return _take_free(path, cap, n, per, what)


def _take_free(path: str, cap: int, n: int, per: float, what: str) -> Held:
    """:func:`try_take`'s body: the free slots the ledger has room for."""
    want = _memory_fit(n, per)
    pressed = want == 0
    if pressed:
        want = cap                         # pressed: count the free ones
    fds: list = []
    start = os.getpid() % cap              # spread the scans
    for k in range(cap):
        if len(fds) >= want:
            break
        fd = _lock(os.path.join(path, "slot-%d" % ((start + k) % cap)))
        if fd is not None:
            fds.append(fd)
    if pressed:
        idle = len(fds) == cap             # the session holds none
        keep = 1 if idle and machine_verdict(per, idle=True).ok else 0
        for fd in fds[keep:]:
            _unlock(fd)
        fds = fds[:keep]
    return _held(fds, per, what)


def _memory_fit(n: int, per: float) -> int:
    """How many of ``n`` slots of ``per`` GB the machine ledger has room
    for now (``n`` when ``per`` is 0 or the session is ungated)."""
    if per <= 0.0 or os.environ.get(ENV_UNGATED):
        return n
    verdict = machine_verdict(per)
    if not verdict.ok:
        return 0
    return max(1, min(n, 1 + int(verdict.spare_gb // per)))


def _held(fds: list, per: float, what: str) -> Held:
    """``fds`` as a :class:`Held` with their ledger reservation."""
    if not fds or per <= 0.0 or os.environ.get(ENV_UNGATED):
        return Held(fds, per)
    label = what or "%d worker%s" % (len(fds), "s" if len(fds) > 1 else "")
    return Held(fds, per, _MEM.reserve(per * len(fds), label))


def take(n: int = 1, *, poll_s: float = POLL_S, on_wait=None,
         give_up=None, gb: "float | None" = None, what: str = "") -> Held:
    """``min(n, capacity)`` slots of ``gb`` each (:func:`try_take`), waiting
    until they are free — the queue of every heavy process beyond the
    budget.  A partial take is given back before the next attempt (two
    waiters never hold half each).  ``on_wait()`` is called once, when the
    first attempt finds no room; a wait for memory is also logged with who
    holds it (``O4_Machine_Memory.note_wait``); ``give_up()`` true (a
    cancel) ends the wait with nothing held."""
    want = max(1, min(int(n), session_capacity()))
    said = False
    while True:
        held = try_take(want, gb, what)
        if held.count >= want:
            return held
        held.release()
        if give_up is not None and give_up():
            return Held([])
        if not said and on_wait is not None:
            said = True
            on_wait()
        note_memory_wait(want, gb, what)
        time.sleep(poll_s)


def note_memory_wait(n: int, gb: "float | None", what: str) -> None:
    """Log (and, for the app, mark) a wait the machine ledger causes."""
    per = BUDGET["worker_gb"] if gb is None else max(0.0, float(gb))
    if per <= 0.0 or os.environ.get(ENV_UNGATED):
        return
    verdict = machine_verdict(per * n)
    if not verdict.ok:
        _MEM.note_wait(what or "a build process", verdict, per * n)


#: the slot this process's current heavy step holds (:func:`step`)
_STEP: list = []


@contextlib.contextmanager
def step(*, on_wait=None, give_up=None, gb: "float | None" = None,
         what: str = ""):
    """Hold ONE slot for this process's heavy step (nested: the outer one
    covers it), reserving ``gb`` (default ``worker_gb``; 0 when a parallel
    run's parent reserved the step) on the machine ledger.  The process
    waits here, light, until the slot and the memory are free."""
    if _STEP:
        yield _STEP[0]
        return
    held = take(1, on_wait=on_wait, give_up=give_up, gb=gb,
                what=what or "this step")
    _STEP.append(held)
    try:
        yield held
    finally:
        _STEP.clear()
        held.release()


@contextlib.contextmanager
def lend():
    """Give this process's step slot back while it only WAITS on worker
    processes it starts (each takes its own), and take it again after —
    a tile holding its slot while its airports queue for one would
    deadlock a full session."""
    held = lend_step()
    try:
        yield
    finally:
        retake_step(held)


def lend_step() -> "Held | None":
    """Give this process's step slot back; the :class:`Held` to pass to
    :func:`retake_step`, or ``None`` when no slot is held."""
    held = _STEP[0] if _STEP else None
    if held is None or not held.count:
        return None
    held.release()
    return held


def retake_step(held: "Held | None", *, give_up=None) -> None:
    """Take the slot :func:`lend_step` gave back, waiting for a free one.
    ``give_up()`` true ends the wait: the step goes on holding none."""
    if held is None:
        return
    again = take(1, gb=held.gb, what="this step", give_up=give_up)
    held._fds, again._fds = again._fds, []         # the step owns it again
    held._reservation, again._reservation = again._reservation, None


#: the longest a :func:`take_class` waits before it goes on without a slot
CLASS_WAIT_S = 600.0

#: seconds between attempts of a :func:`take_class` that is waiting
CLASS_POLL_S = 0.05


def net_class(url_or_host: str) -> str:
    """The class of one server: ``net:<host>`` of a URL (or of a bare
    host), lower-cased, the port kept — two providers on one host share
    it."""
    text = str(url_or_host or "")
    if "//" in text:
        text = urlsplit(text).netloc.rpartition("@")[2]
    return "net:" + (text.strip().lower() or "unknown")


def _class_dir(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    path = os.path.join(ensure_session()[0],
                        "class-%s-%s" % (safe[:64], digest))
    os.makedirs(path, exist_ok=True)
    return path


#: seconds a priority request's demand mark stands after its last refused
#: attempt (it refreshes it every poll while it waits)
DEMAND_TTL_S = 0.5
#: a mark this old is a dead process's: removed by the next reader
_DEMAND_STALE_S = 60.0

#: seconds one :func:`hold_net_for_flight` stands (a dead follow job's
#: hold lapses by itself)
FLIGHT_HOLD_TTL_S = 3.0
_FLIGHT_HOLD = "flight-net-hold"

_PRIORITY = threading.local()


@contextlib.contextmanager
def net_priority():
    """Every class request made on this thread inside the block goes
    first (see the module: PRIORITY)."""
    before = getattr(_PRIORITY, "on", False)
    _PRIORITY.on = True
    try:
        yield
    finally:
        _PRIORITY.on = before


def has_net_priority() -> bool:
    """Is this thread inside :func:`net_priority`?"""
    return bool(getattr(_PRIORITY, "on", False))


def carry_net_priority(task):
    """``task`` run under :func:`net_priority` when THIS thread is in it
    (a worker thread started here does not inherit the flag); else
    ``task`` itself."""
    if not has_net_priority():
        return task

    def run(*args, **kwargs):
        with net_priority():
            return task(*args, **kwargs)
    return run


def hold_net_for_flight() -> None:
    """For :data:`FLIGHT_HOLD_TTL_S`, no request outside
    :func:`net_priority` takes a slot of any ``net:`` class, on any server
    (#2256: a flight's departure core goes before background builds).  The
    follow job renews it each tick while the core is open."""
    mark = os.path.join(ensure_session()[0], _FLIGHT_HOLD)
    try:
        with open(mark, "a", encoding="utf-8", newline=""):
            pass
        os.utime(mark)
    except OSError:
        pass


def _flight_hold_live() -> bool:
    try:
        age = time.time() - os.stat(
            os.path.join(ensure_session()[0], _FLIGHT_HOLD)).st_mtime
    except OSError:
        return False
    return age < FLIGHT_HOLD_TTL_S


def _demand_dir(path: str) -> str:
    return os.path.join(path, "want")


def _note_demand(path: str) -> None:
    """This thread's priority request waits on the class at ``path``."""
    folder = _demand_dir(path)
    mark = os.path.join(folder, "%d-%d" % (os.getpid(), threading.get_ident()))
    try:
        os.makedirs(folder, exist_ok=True)
        with open(mark, "a", encoding="utf-8", newline=""):
            pass
        os.utime(mark)
    except OSError:
        pass


def _demand_live(path: str) -> bool:
    """Does a priority request (any process) wait on the class at
    ``path`` now?  Dead processes' old marks are removed."""
    now = time.time()
    live = False
    try:
        entries = list(os.scandir(_demand_dir(path)))
    except OSError:
        return False
    for entry in entries:
        try:
            age = now - entry.stat().st_mtime
        except OSError:
            continue
        if age < DEMAND_TTL_S:
            live = True
        elif age > _DEMAND_STALE_S:
            with contextlib.suppress(OSError):
                os.remove(entry.path)
    return live


def try_take_class(name: str, n: int = 1, limit: int = 1,
                   priority: "bool | None" = None) -> Held:
    """Up to ``n`` free slots of the class ``name`` of ``limit`` slots, at
    once and never waiting (possibly none).  Every process of the session
    that names the class shares its ``limit`` slots.  ``priority`` (default:
    :func:`has_net_priority`) goes first: without it nothing is taken
    while a priority request waits; with it, a refusal marks the wait."""
    limit = max(1, int(limit))
    if n <= 0:
        return Held([])
    if priority is None:
        priority = has_net_priority()
    path = _class_dir(name)
    if not priority and (_demand_live(path) or (
            name.startswith("net:") and _flight_hold_live())):
        return Held([])
    fds: list = []
    start = (os.getpid() + threading.get_ident()) % limit
    for k in range(limit):
        if len(fds) >= n:
            break
        fd = _lock(os.path.join(path, "slot-%d" % ((start + k) % limit)))
        if fd is not None:
            fds.append(fd)
    if priority and len(fds) < n:
        _note_demand(path)
    return Held(fds)


def take_class(name: str, n: int = 1, limit: int = 1, *,
               timeout_s: float = CLASS_WAIT_S, poll_s: float = CLASS_POLL_S,
               give_up=None) -> Held:
    """``min(n, limit)`` slots of the class ``name``, waiting until they
    are free — at most ``timeout_s``, after which NOTHING is held and the
    caller goes on without (the bounded wait: a holder that never lets go
    costs one request over the budget, never a hung build).  A partial
    take is given back before the next attempt.  ``give_up()`` true (a
    Stop) ends the wait with nothing held."""
    want = max(1, min(int(n), max(1, int(limit))))
    deadline = time.monotonic() + max(0.0, float(timeout_s))
    while True:
        held = try_take_class(name, want, limit)
        if held.count >= want:
            return held
        held.release()
        if give_up is not None and give_up():
            return Held([])
        if time.monotonic() >= deadline:
            return Held([])
        time.sleep(poll_s)


@contextlib.contextmanager
def hold_class(name: str, limit: int, n: int = 1, **wait):
    """Hold ``n`` slots of the class ``name`` (:func:`take_class`, its
    keywords) for the block; yields the :class:`Held` (``count`` 0 when
    the bounded wait ran out or was given up)."""
    held = take_class(name, n, limit, **wait)
    try:
        yield held
    finally:
        held.release()


def lower_priority() -> None:
    """Run this process — and every child it starts afterwards, which
    inherits it — below the user's applications: a build worker
    (:data:`ENV_BUILD_WORKER` set) at nice :data:`NICE`, the engine's
    command process at :data:`COMMAND_NICE`, so the app's commands and
    dialog answers go before its builds; ``BELOW_NORMAL_PRIORITY_CLASS``
    for both on Windows.  Never raises a process's priority (a dev venv's
    nice 15 stands).  Once per process tree, and once more in a build
    worker; never raises."""
    worker = bool(os.environ.get(ENV_BUILD_WORKER))
    marked = os.environ.get(ENV_PRIORITY)
    if marked and (marked == "worker" or not worker):
        return
    os.environ[ENV_PRIORITY] = "worker" if worker else "1"
    nice = NICE if worker else COMMAND_NICE
    try:
        if sys.platform == "win32":
            import ctypes
            k32 = ctypes.windll.kernel32
            k32.SetPriorityClass(k32.GetCurrentProcess(), 0x4000)
        elif os.getpriority(os.PRIO_PROCESS, 0) < nice:
            os.setpriority(os.PRIO_PROCESS, 0, nice)
    except Exception:
        pass


def background_priority() -> None:
    """Run THIS process in the system's background band: its CPU and its
    disk reads yield to everything else (macOS ``PRIO_DARWIN_BG``, which
    also throttles I/O; Windows background mode; elsewhere nice 19).
    For work nobody waits on, beside a build (owner 2026-11-12T19:08Z:
    Measure "at background priority while builds run").  Never raises."""
    try:
        if sys.platform == "win32":
            import ctypes
            k32 = ctypes.windll.kernel32
            k32.SetPriorityClass(k32.GetCurrentProcess(), 0x00100000)
        elif hasattr(os, "PRIO_DARWIN_BG"):
            os.setpriority(os.PRIO_DARWIN_PROCESS, 0, os.PRIO_DARWIN_BG)
        else:
            os.setpriority(os.PRIO_PROCESS, 0, 19)
    except Exception:
        pass
