"""THE MACHINE MEMORY LEDGER — one memory budget every engine process on
this machine shares: the app's builds, the harness's builds and command-line
runs (incident 2026-11-17 ~22:46Z; owner 22:50Z: use what the machine has,
scale back for an app build or X-Plane).

Before it, each engine SESSION sized its budget from the same free memory
(``O4_Machine_Slots`` opens one slot directory per session; the parallel
scheduler re-sizes its run budget from the machine): four harness builds
and an app build each read ~90 GB free, each admitted steps against it,
and the steps then GREW into the same memory until a 128 GB Mac ran out.
A free-memory reading cannot see what an admitted step is about to take.

The ledger is that missing knowledge.  A fixed per-user directory
(:func:`ledger_dir`) holds one RECORD per reservation: a JSON file naming
the session, its role, what it is for, how many gigabytes it reserved and
the process whose memory it covers, held by an OS lock for exactly as long
as the reservation lives — the system drops the lock when the holder exits,
however it exits, and the next reader removes the dead record.

A reservation's OUTSTANDING part is what it reserved less what the covered
process tree has grown since (one ``ps`` reading; a nested process holding
its own record counts there, never twice).  Admission (:func:`admits`)::

    free − Σ outstanding − X-Plane's expected growth − the app's room
         ≥ need + headroom

* **X-Plane** (a process of :data:`XPLANE_NAMES`) is reserved
  ``xplane_expected_gb`` less what it already holds, plus
  ``xplane_margin_gb`` (:data:`BUDGET`): a flight loading scenery grows.
* **the app first**: a ``lane`` or ``cli`` session also leaves room for the
  app's next step — the app session's largest live reservation, or what a
  waiting app step needs (its WANT mark, written by :func:`note_wait`).
* **pressure**: at the kernel's ``warn`` level lane and command-line
  sessions start nothing new; at ``critical`` no session does.  Running
  steps are never stopped; they finish and give their memory back.
* **progress**: a caller holding nothing (``idle``) still starts one step
  when no other session holds a reservation and the pressure is not
  critical — a lane only when no X-Plane and no pressure warning either.

Every wait names who holds memory (:func:`note_wait`: "X-Plane 24 GB, app
build 30 GB, lane lessa5 18 GB").

Standard library only (with :mod:`O4_Parallel_Utils`' memory probes); it
never raises into a build: a ledger that cannot be written reserves nothing.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field

import O4_Parallel_Utils as _PU

if sys.platform == "win32":                # module level: a freezer sees it
    import msvcrt as _oslock
else:
    import fcntl as _oslock

__all__ = ["BUDGET", "ENV_DIR", "ENV_LABEL", "ENV_ROLE", "ENV_SESSION",
           "ENV_STEP_RESERVED", "XPLANE_NAMES", "Reservation", "Snapshot",
           "Verdict", "admission", "admits", "claim", "held_tiles", "hold_tile",
           "holders_text", "ledger_dir", "note_wait", "pressure_refuses",
           "process_table",
           "reserve", "role", "session_id", "snapshot"]

#: the ledger directory (default: :func:`ledger_dir`'s per-user path)
ENV_DIR = "O4_MACHINE_LEDGER_DIR"
#: the session a process belongs to, inherited by its children
ENV_SESSION = "O4_MEMORY_SESSION"
#: ``app`` | ``lane`` | ``cli``, and the words the logs name the session by
ENV_ROLE = "O4_MEMORY_ROLE"
ENV_LABEL = "O4_MEMORY_LABEL"
#: set in a parallel run's worker: its parent reserves each step it runs
ENV_STEP_RESERVED = "O4_MEMORY_STEP_RESERVED"

ROLES = ("app", "lane", "cli")
_LABELS = {"app": "app build", "lane": "lane build",
           "cli": "command-line build"}

#: X-Plane's process names (macOS / Linux; ``ps`` reads the executable)
XPLANE_NAMES = frozenset({"X-Plane", "X-Plane-x86_64", "X-Plane-arm64"})

#: THE LEDGER LAW (gigabytes / seconds).
#: ``xplane_expected_gb`` — what a running X-Plane is expected to hold once a
#: flight's scenery is loaded.  An ESTIMATE (X-Plane 12 with orthophoto
#: scenery on the owner's 128 GB Mac); no recorded figure yet — refine it
#: when one is.  ``xplane_margin_gb`` — kept above that for its spikes.
#: ``want_ttl_s`` — how long a waiting app step's WANT mark stands after its
#: last refusal (the scheduler re-asks every 2 s).  ``fresh_s`` — an
#: unlocked record younger than this is being written or removed, not dead.
#: ``snapshot_s`` — how long one reading of the ledger serves a process's
#: gates; ``table_s`` — how long one process listing does (an old listing
#: shows less growth, the safe side for a reading; a reservation's base
#: read from it is at most that old).
BUDGET = {
    "xplane_expected_gb": 32.0,
    "xplane_margin_gb": 4.0,
    "want_ttl_s": 10.0,
    "fresh_s": 5.0,
    "snapshot_s": 1.0,
    "table_s": 3.0,
}

_KIB_PER_GIB = 1024.0 * 1024.0
#: Windows locks a byte range readers then cannot read: lock one past EOF
_WIN_LOCK_OFFSET = 1 << 30


def ledger_dir() -> str:
    """The machine-wide ledger: ``$O4_MACHINE_LEDGER_DIR`` or
    ``~/.ortho4xp/machine_memory`` (one per user; every session finds it)."""
    path = os.environ.get(ENV_DIR, "").strip()
    return path or os.path.join(os.path.expanduser("~"), ".ortho4xp",
                                "machine_memory")


def session_id() -> str:
    """This process's session (inherited; minted and published if absent)."""
    sid = os.environ.get(ENV_SESSION, "")
    if not sid:
        sid = "s%d-%d" % (os.getpid(), int(time.time() * 1000))
        os.environ[ENV_SESSION] = sid
    return sid


def role() -> str:
    """``app``, ``lane`` or ``cli`` (the default)."""
    value = os.environ.get(ENV_ROLE, "")
    return value if value in ROLES else "cli"


def _label() -> str:
    return os.environ.get(ENV_LABEL, "") or _LABELS[role()]


def claim(new_role: str, label: str = "") -> None:
    """Name this process tree's role (and label) unless an ancestor already
    did — the app's engine claims ``app``, the harness ``lane``.  A label
    already in the environment stands."""
    if new_role not in ROLES:
        raise ValueError(new_role)
    if os.environ.get(ENV_ROLE) not in ROLES:
        os.environ[ENV_ROLE] = new_role
        if label:
            os.environ.setdefault(ENV_LABEL, label)
    session_id()


# -- the machine's processes ------------------------------------------------

_TABLE: list = []                          # [(monotonic, table)]
_TABLE_LOCK = threading.Lock()


def process_table() -> list:
    """``[(pid, ppid, rss KiB, executable)]`` of every process, read now,
    or ``[]`` (Windows, or ``ps`` failed).  Each reading also serves the
    ledger's own gates for ``table_s``."""
    table = _read_process_table()
    with _TABLE_LOCK:
        _TABLE[:] = [(time.monotonic(), table)]
    return table


def _read_process_table() -> list:
    if sys.platform == "win32":
        return []
    try:
        import O4_UI_Utils as UI
        command = ["ps", "-A", "-o", "pid=,ppid=,rss=,comm="]
        output = subprocess.run(
            command,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            encoding="utf-8", errors="replace", timeout=10.0, check=False,
            **UI.external_tool_keyword_arguments(command)).stdout
    except Exception:
        return []
    rows = []
    for line in output.splitlines():
        fields = line.split(None, 3)
        if len(fields) >= 3 and all(f.isdigit() for f in fields[:3]):
            rows.append((int(fields[0]), int(fields[1]), int(fields[2]),
                         fields[3].strip() if len(fields) > 3 else ""))
    return rows


def _table() -> list:
    """:func:`process_table`, one reading serving ``table_s``: a ``ps``
    from a loaded machine's Python costs up to a second (measured 0.77 s
    at load average 95), and a pool takes slots at every stage."""
    with _TABLE_LOCK:
        if _TABLE and time.monotonic() - _TABLE[0][0] < BUDGET["table_s"]:
            return _TABLE[0][1]
    return process_table()


def _xplane_gigabytes(table) -> "float | None":
    """X-Plane's resident memory, or ``None`` when it is not running."""
    sizes = [kib for _, _, kib, exe in table
             if os.path.basename(exe) in XPLANE_NAMES]
    return sum(sizes) / _KIB_PER_GIB if sizes else None


def _tree_gigabytes(root: int, table, stop: set) -> "float | None":
    """``root``'s share of resident memory with its descendants', not
    descending past ``stop`` (other records' roots, whose descendants
    their own records cover); ``None`` when ``root`` is not running.

    Every process counts for exactly one record.  A root counts its own
    memory only when no other root is above it: a NESTED root (an airport
    build that reserved its pool's workers, inside the slot its parent
    reserved for it) is the outer record's process — the outer record
    counts it, the nested one only its workers.  Until 2026-11-18 the
    outer record lost sight of the process its slot was for once the pool
    reserved, and its 3 GB stayed outstanding while the build used it."""
    rss = {pid: kib for pid, _, kib, _ in table}
    if root not in rss:
        return None
    parent = {pid: ppid for pid, ppid, _, _ in table}
    children: dict = {}
    for pid, ppid, _, _ in table:
        children.setdefault(ppid, []).append(pid)
    total = 0 if _root_above(root, parent, stop) else rss[root]
    stack, seen = list(children.get(root, ())), {root}
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        total += rss.get(pid, 0)
        if pid not in stop:
            stack.extend(children.get(pid, ()))
    return total / _KIB_PER_GIB


def _root_above(pid: int, parent: dict, roots: set) -> bool:
    """Is a process of ``roots`` an ancestor of ``pid``?"""
    seen = {pid}
    pid = parent.get(pid)
    while pid is not None and pid not in seen and pid > 1:
        if pid in roots:
            return True
        seen.add(pid)
        pid = parent.get(pid)
    return False


# -- records ----------------------------------------------------------------

def _lock_fd(fd) -> bool:
    try:
        if sys.platform == "win32":
            os.lseek(fd, _WIN_LOCK_OFFSET, os.SEEK_SET)
            _oslock.locking(fd, _oslock.LK_NBLCK, 1)
        else:
            _oslock.flock(fd, _oslock.LOCK_EX | _oslock.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock_fd(fd) -> None:
    try:
        if sys.platform == "win32":
            os.lseek(fd, _WIN_LOCK_OFFSET, os.SEEK_SET)
            _oslock.locking(fd, _oslock.LK_UNLCK, 1)
    except OSError:
        pass
    try:
        os.close(fd)                       # closing releases a flock
    except OSError:
        pass


def _remove(path: str) -> None:
    with contextlib.suppress(OSError):    # already gone: another reader's
        os.remove(path)


_SEQ = [0]
_SEQ_LOCK = threading.Lock()


def _record_path(kind: str) -> str:
    with _SEQ_LOCK:
        _SEQ[0] += 1
        n = _SEQ[0]
    # the clock too: a recycled pid must never re-open a dead record's
    # name while a reader is removing it
    return os.path.join(ledger_dir(), "%s-%d-%d-%x.json" % (
        kind, os.getpid(), n, time.time_ns() & 0xFFFFFFFF))


class Reservation:
    """One live record; :meth:`release` (or the context exit, or the
    process's exit) removes it.  ``gigabytes`` is 0 when nothing was
    written (nothing to reserve, or the ledger could not be written)."""

    def __init__(self, path: str = "", fd=None, gigabytes: float = 0.0):
        self.path, self._fd = path, fd
        self.gigabytes = float(gigabytes) if fd is not None else 0.0

    def release(self) -> None:
        fd, self._fd = self._fd, None
        if fd is None:
            return
        if sys.platform != "win32":
            _remove(self.path)             # gone before the lock drops
        _unlock_fd(fd)
        if sys.platform == "win32":
            _remove(self.path)             # an open file cannot be removed
        _forget_snapshot()

    def settle(self, gigabytes: float) -> None:
        """Lower the reservation to ``gigabytes`` once what it covers has
        been measured (a pool's workers at their working size): a
        reservation only ever shrinks here, and in place — the record's
        lock is its life, so it is rewritten under the same descriptor,
        padded to its old length so no reader sees it cut short."""
        gigabytes = max(0.0, float(gigabytes))
        if self._fd is None or gigabytes >= self.gigabytes - 0.05:
            return
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                old = handle.read()
            body = json.loads(old)
            body["gb"] = round(gigabytes, 3)
            new = json.dumps(body)
            os.lseek(self._fd, 0, os.SEEK_SET)
            os.write(self._fd, new.ljust(len(old)).encode("utf-8"))
        except (OSError, ValueError):
            return
        self.gigabytes = gigabytes
        _forget_snapshot()

    def __enter__(self) -> "Reservation":
        return self

    def __exit__(self, *exc) -> None:
        self.release()

    def __del__(self) -> None:
        try:
            self.release()
        except Exception:
            pass


def _write_record(kind: str, body: dict) -> Reservation:
    """A new locked record holding ``body`` (an empty one on failure)."""
    try:
        os.makedirs(ledger_dir(), exist_ok=True)
        path = _record_path(kind)
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o600)
    except OSError:
        return Reservation()
    if not _lock_fd(fd):
        os.close(fd)
        return Reservation()
    try:
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, json.dumps(body).encode("utf-8"))
    except OSError:
        _remove(path)
        _unlock_fd(fd)
        return Reservation()
    _forget_snapshot()
    return Reservation(path, fd, float(body.get("gb", 0.0)))


def _body(gigabytes: float, **extra) -> dict:
    return dict({"session": session_id(), "role": role(), "label": _label(),
                 "gb": float(gigabytes), "since": time.time()}, **extra)


def reserve(gigabytes: float, what: str, pid: "int | None" = None,
            table=None) -> Reservation:
    """Reserve ``gigabytes`` for ``what`` on the machine ledger: the memory
    process ``pid`` (default: this one) and its tree grow into from now.
    Held until released, or until the holding process exits."""
    gigabytes = max(0.0, float(gigabytes))
    if gigabytes <= 0.0:
        return Reservation()
    pid = os.getpid() if pid is None else int(pid)
    table = _table() if table is None else table
    stop = {int(r.get("pid", 0)) for r in _live_records("r")} - {pid}
    base = _tree_gigabytes(pid, table, stop)
    held = _write_record("r", _body(gigabytes, what=str(what), pid=pid,
                                    base_gb=base or 0.0))
    if held.gigabytes > 0.0 and not os.environ.get(_ENV_ANNOUNCED):
        os.environ[_ENV_ANNOUNCED] = "1"   # once per process tree
        _say("Machine memory ledger %s: %s reserves %s GB for %s; holding "
             "now: %s." % (ledger_dir(), _label(), _gb(gigabytes), what,
                           holders_text(snapshot())))
    return held


def hold_tile(lat: int, lon: int) -> Reservation:
    """THE BUILD HOLD (owner 2026-11-18T13:06Z: "cleanup unneeded files,
    but not mid-build"): a locked ledger record naming the tile this
    process is building, held until released or until the process exits
    however it exits.  Every cleanup reads :func:`held_tiles` and leaves a
    held tile's files alone, whichever session holds it."""
    return _write_record("t", _body(0.0, tile=[int(lat), int(lon)],
                                    pid=os.getpid()))


def held_tiles() -> set:
    """The ``(lat, lon)`` tiles a live build holds, on the whole machine
    (:func:`hold_tile`); dead holders' records are dropped."""
    out = set()
    for body in _live_records("t"):
        with contextlib.suppress(TypeError, ValueError, IndexError, KeyError):
            out.add((int(body["tile"][0]), int(body["tile"][1])))
    return out


#: set once a process (or an ancestor) has announced the ledger in its log
_ENV_ANNOUNCED = "O4_MEMORY_LEDGER_ANNOUNCED"


def _say(line: str) -> None:
    try:
        print(line, flush=True)
    except Exception:
        pass


def _probe_live(path: str) -> "bool | None":
    """True: a holder has the record; False: nobody does; None: gone."""
    try:
        fd = os.open(path, os.O_RDWR)
    except OSError:
        return None
    try:
        return not _lock_fd(fd)
    finally:
        _unlock_fd(fd)


def _live_records(kind: str) -> list:
    """The bodies of every live ``kind`` record; dead ones are removed."""
    folder = ledger_dir()
    try:
        names = [n for n in os.listdir(folder)
                 if n.startswith(kind + "-") and n.endswith(".json")]
    except OSError:
        return []
    now, out = time.time(), []
    for name in names:
        path = os.path.join(folder, name)
        live = _probe_live(path)
        if live:
            body = _read_body(path)
            if body is not None:
                out.append(body)
        elif live is False and _age(path, now) > BUDGET["fresh_s"]:
            _remove(path)
    return out


def _read_body(path: str) -> "dict | None":
    try:
        with open(path, "r", encoding="utf-8") as handle:
            body = json.load(handle)
        return body if isinstance(body, dict) else None
    except (OSError, ValueError):
        return None


def _age(path: str, now: float) -> float:
    try:
        return now - os.stat(path).st_mtime
    except OSError:
        return 0.0


_ADMIT_POLL_S = 0.02
_ADMITTING = threading.local()


@contextlib.contextmanager
def admission():
    """One admission at a time on the whole machine: the block that reads
    the ledger and writes its reservation holds ``admit.lock`` (an OS lock,
    dropped if the holder dies), so two builds that read the same free
    memory in the same instant never both take it.  The ledger is re-read
    inside (the process table is not: it only measures growth).  Nested
    blocks in one thread are one admission; a ledger that cannot be
    opened admits without it."""
    if getattr(_ADMITTING, "depth", 0):
        _ADMITTING.depth += 1
        try:
            yield
        finally:
            _ADMITTING.depth -= 1
        return
    fd = _open_admit_lock()
    _ADMITTING.depth = 1
    try:
        _forget_snapshot()
        yield
    finally:
        _ADMITTING.depth = 0
        if fd is not None:
            _unlock_fd(fd)


def _open_admit_lock():
    """The held ``admit.lock`` descriptor (waits for it), or ``None``."""
    try:
        os.makedirs(ledger_dir(), exist_ok=True)
        fd = os.open(os.path.join(ledger_dir(), "admit.lock"),
                     os.O_RDWR | os.O_CREAT, 0o600)
    except OSError:
        return None
    deadline = time.monotonic() + 30.0     # a wedged holder never hangs us
    while not _lock_fd(fd):
        if time.monotonic() > deadline:
            os.close(fd)
            return None
        time.sleep(_ADMIT_POLL_S)
    return fd


# -- the reading ------------------------------------------------------------

@dataclass
class Snapshot:
    """One reading of the machine: free memory, every session's live
    outstanding reservations, X-Plane, the pressure and the app's room."""

    free_gb: float
    outstanding_gb: float = 0.0
    sessions: dict = field(default_factory=dict)   # session -> holder row
    xplane_gb: "float | None" = None
    pressure: str = "normal"
    wants: list = field(default_factory=list)      # live app WANT marks


def _groups(records: list, table) -> list:
    """``[(rows, outstanding GB, grown GB)]``, one per session and covered
    process."""
    groups: dict = {}
    for body in records:
        key = (body.get("session", "?"), int(body.get("pid", 0)))
        groups.setdefault(key, []).append(body)
    roots = {pid for _, pid in groups}
    out = []
    for (_, pid), rows in groups.items():
        reserved = sum(float(r.get("gb", 0.0)) for r in rows)
        now = _tree_gigabytes(pid, table, roots - {pid})
        base = min(float(r.get("base_gb", 0.0)) for r in rows)
        grown = max(0.0, now - base) if now is not None else 0.0
        out.append((rows, max(0.0, reserved - grown), grown))
    return out


def _sessions(groups: list) -> dict:
    """``{session: {role, label, gb, largest_gb}}`` — what each session
    holds (the larger of its reservations and their growth)."""
    sessions: dict = {}
    for rows, _outstanding, grown in groups:
        head = rows[0]
        row = sessions.setdefault(head.get("session", "?"), {
            "role": head.get("role", "cli"), "label": head.get("label", "?"),
            "gb": 0.0, "largest_gb": 0.0})
        sizes = [float(r.get("gb", 0.0)) for r in rows]
        row["gb"] += max(sum(sizes), grown)
        row["largest_gb"] = max([row["largest_gb"]] + sizes)
    return sessions


_CACHE: dict = {}
_CACHE_LOCK = threading.Lock()


def _forget_snapshot() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()


def snapshot() -> Snapshot:
    """The machine now.  Free memory and the pressure are read every time
    (``O4_Parallel_Utils`` caches its probe); the ledger and the process
    table serve ``snapshot_s`` (a reservation made or released here
    re-reads them)."""
    key = ledger_dir()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
    if not hit or time.monotonic() - hit[0] >= BUDGET["snapshot_s"]:
        table = _table()
        groups = _groups(_live_records("r"), table)
        hit = (time.monotonic(), dict(
            outstanding_gb=sum(g[1] for g in groups),
            sessions=_sessions(groups), xplane_gb=_xplane_gigabytes(table),
            wants=[w for w in _live_records("want") if _want_live(w)]))
        with _CACHE_LOCK:
            _CACHE[key] = hit
    return Snapshot(free_gb=_PU.machine_available_memory_gigabytes(),
                    pressure=_PU.machine_memory_pressure(), **hit[1])


def _want_live(body: dict) -> bool:
    return time.time() - float(body.get("since", 0.0)) <= BUDGET["want_ttl_s"]


@dataclass(frozen=True)
class Verdict:
    """An admission answer.  ``spare_gb``: what is left above the headroom
    after the need (negative: refused for room); ``contended``: refused
    with another build, X-Plane, the app's room or the pressure part of
    the reason (or although free memory alone would have held it) — a wait
    the machine's own builds and the owner end, not other programs."""

    ok: bool
    spare_gb: float = 0.0
    contended: bool = False                        # see the class doc
    text: str = ""


def _xplane_reserve(snap: Snapshot) -> float:
    if snap.xplane_gb is None:
        return 0.0
    return (max(0.0, BUDGET["xplane_expected_gb"] - snap.xplane_gb)
            + BUDGET["xplane_margin_gb"])


def _app_room(snap: Snapshot) -> float:
    """The room a lane or command-line caller leaves for the app: its
    largest live step, or what a waiting app step needs."""
    if role() == "app":
        return 0.0
    mine = session_id()
    room = [row["largest_gb"] for sid, row in snap.sessions.items()
            if row["role"] == "app" and sid != mine]
    room += [float(w.get("gb", 0.0)) for w in snap.wants
             if w.get("session") != mine]
    return max(room or [0.0])


def _gb(gigabytes: float) -> str:
    return ("%.1f" if gigabytes < 10.0 else "%.0f") % max(0.0, gigabytes)


def holders_text(snap: Snapshot) -> str:
    """Who holds memory: "X-Plane 24 GB, app build 30 GB, lane x 18 GB"."""
    parts = []
    if snap.xplane_gb is not None:
        parts.append("X-Plane %s GB" % _gb(snap.xplane_gb))
    rank = {name: k for k, name in enumerate(ROLES)}
    mine = session_id()
    for sid, row in sorted(snap.sessions.items(), key=lambda kv: (
            rank.get(kv[1]["role"], 9), kv[1]["label"], kv[0])):
        parts.append("%s %s GB%s" % (row["label"], _gb(row["gb"]),
                                     " (this one)" if sid == mine else ""))
    if any(w.get("session") != mine for w in snap.wants):
        parts.append("an app step waiting")
    return ", ".join(parts) or "no build holds memory"


def _pressure_refuses(snap: Snapshot) -> bool:
    if snap.pressure == "critical":
        return True
    return snap.pressure == "warn" and role() != "app"


def pressure_refuses(snap: "Snapshot | None" = None) -> bool:
    """:func:`admits`' pressure rule alone: does the kernel's pressure now
    stop this session's role starting work?"""
    return _pressure_refuses(snapshot() if snap is None else snap)


def _idle_may_run(snap: Snapshot) -> bool:
    """The progress rule: an idle caller runs one step when no other
    session holds memory and nothing the owner runs stands in the way."""
    mine = session_id()
    if any(sid != mine for sid in snap.sessions) or snap.pressure == "critical":
        return False
    if role() == "app":
        return True
    return snap.xplane_gb is None and snap.pressure == "normal" and not any(
        w.get("session") != mine for w in snap.wants)


def admits(need_gb: float, headroom_gb: float, *, idle: bool = False,
           snap: "Snapshot | None" = None) -> Verdict:
    """May this process start ``need_gb`` more now, keeping ``headroom_gb``
    free (the module doc's rule)?  ``idle``: the caller holds nothing."""
    snap = snapshot() if snap is None else snap
    alone = snap.free_gb - float(need_gb) - float(headroom_gb)
    room = _app_room(snap)
    spare = alone - snap.outstanding_gb - _xplane_reserve(snap) - room
    ok = spare >= 0.0 and not _pressure_refuses(snap)
    if not ok and idle:
        ok = _idle_may_run(snap)
    mine = session_id()
    others = (room > 0.0 or snap.xplane_gb is not None
              or _pressure_refuses(snap)
              or any(sid != mine for sid in snap.sessions))
    # The reason, as it is (owner 2026-11-18: "listing the memory need
    # which is far lower than the available memory"): what builds have
    # booked and not yet grown into is what stands between the free
    # memory and the need; the pressure only when it is what refuses.
    text = ("needs %s GB, %s GB free, %s GB kept free, %s GB booked by"
            " builds and not yet in use; holding: %s%s"
            % (_gb(need_gb), _gb(snap.free_gb), _gb(headroom_gb),
               _gb(snap.outstanding_gb), holders_text(snap),
               "; memory pressure %s" % snap.pressure
               if _pressure_refuses(snap) else ""))
    return Verdict(ok=ok, spare_gb=spare,
                   contended=not ok and (alone >= 0.0 or others), text=text)


_WANT: list = []                           # this process's WANT mark
_SAID: dict = {}
_SAY_EVERY_S = 60.0


def note_wait(what: str, verdict: Verdict, need_gb: float = 0.0,
              emit=print) -> None:
    """A refused caller waits: an app caller's WANT mark is refreshed (the
    lanes leave it room), and the wait is logged with who holds memory —
    once per ``what`` a minute, or when the holders change."""
    if role() == "app" and need_gb > 0.0:
        _refresh_want(float(need_gb))
    holders = re.sub(r"[0-9.]+ GB", "GB", verdict.text.split("holding:")[-1])
    now = time.monotonic()
    last = _SAID.get(str(what))
    if last and last[1] == holders and now - last[0] < _SAY_EVERY_S:
        return
    _SAID[str(what)] = (now, holders)
    try:
        emit("Waiting for memory before %s: %s." % (what, verdict.text))
    except Exception:
        pass


def _refresh_want(gigabytes: float) -> None:
    """Keep this process's WANT mark at the largest need of the last
    ``want_ttl_s``, re-stamped at most once a second."""
    with _CACHE_LOCK:
        held = _WANT[0] if _WANT else None
    if held is not None:
        age = time.time() - held.since
        if age < 1.0 and held.gigabytes >= gigabytes:
            return
        if age < BUDGET["want_ttl_s"]:
            gigabytes = max(gigabytes, held.gigabytes)
    mark = _write_record("want", _body(gigabytes))
    mark.since = time.time()
    with _CACHE_LOCK:
        old = list(_WANT)
        _WANT[:] = [mark] if mark.gigabytes > 0.0 else []
    for stale in old:
        stale.release()
