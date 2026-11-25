"""THE LANE JOB GATE — a lane or command-line HEAVY JOB (a capture, a
replay, a rebake replay, a census over captures, a mesh-only tile) takes
its memory on the machine memory ledger before it starts (owner
2026-11-25T18:11Z, after eight lanes' replays and captures — 71 Python
processes, 217 GB — met macOS Jetsam's low-swap kills).

Tile builds already shared the machine (``O4_Machine_Slots`` /
``O4_Machine_Memory``); the lane tools did not: each loaded a capture
(~9-10 GB a process) against the same free memory as every other.  This
module is the same machinery for a whole job — never a second one:

* :func:`admit` waits until ``O4_Machine_Slots.machine_verdict`` admits
  the job's estimate (free memory less every build's outstanding
  reservations, X-Plane's and the app's room, keeping
  ``headroom_gigabytes`` free; nothing new starts under memory pressure),
  printing ONE line a minute (needed GB, free GB, who holds memory), then
  RESERVES it on the ledger for the job's life.  The reservation is an OS
  lock: a crash or kill releases it with the process.
* :func:`estimate_gigabytes` — the job's MEASURED peak (``ru_maxrss`` of
  its last run, recorded at exit in :func:`peaks_path`) times
  ``step_memory.RECORDED_PEAK_MARGIN``; with no record, :data:`DEFAULT_GB`.
* :func:`admissible_workers` — how many workers of a pool the machine
  admits now: pools are sized by headroom, never by cores alone.

SCALE BACK (owner 2026-11-25T18:12Z: "use all available resources, but
… scale back if other apps start"): no fixed floor — an idle machine
admits every job at once; a job that started runs to its end, its pools
shed workers under pressure (``auto_patch_v2.airport.pool_slots``) and
every process runs at the dev nice (``o4_dev_nice.pth``) so the owner's
apps win the processors.  A session that set
``O4_Machine_Slots.ENV_UNGATED`` (the test suite) is admitted at once.

Standard library only; recording a peak never raises into a job.
"""
from __future__ import annotations

import atexit
import contextlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import O4_Machine_Memory as _MEM
import O4_Machine_Slots as _SLOTS
from o4_engine import step_memory as _STEP_MEMORY

__all__ = ["DEFAULT_GB", "admissible_workers", "admit", "admit_process", "claim_lane",
           "estimate_gigabytes", "peaks_path"]

#: a job's memory before its first recorded peak (gigabytes), by kind.
#: ``capture`` / ``replay``: one ``v2_solve_replay`` process measured at
#: 9-10 GB resident in the 2026-11-25 incident (71 processes, 217 GB) —
#: the upper figure.  ``airport`` (one in-process solve, the harness's
#: patch build) and ``rebake``: the vector step with airports
#: (``o4_engine.step_memory.VECTOR_AIRPORT_DEFAULT_GB``, the 1.0.519
#: run's median per-tile peak rounded up).  ``census``: one heavy worker
#: (``O4_Machine_Slots.BUDGET['worker_gb']``; a census loads one ~1 GB
#: pickle or one patch at a time).  Every kind is replaced by its own
#: measured peak after one run.
DEFAULT_GB = {
    "capture": 10.0,
    "replay": 10.0,
    "airport": _STEP_MEMORY.VECTOR_AIRPORT_DEFAULT_GB,
    "rebake": _STEP_MEMORY.VECTOR_AIRPORT_DEFAULT_GB,
    "census": _SLOTS.BUDGET["worker_gb"],
}

#: seconds between admission attempts, and between wait lines
POLL_S = 5.0
SAY_EVERY_S = 60.0

ENV_PEAKS = "O4_JOB_PEAKS_PATH"


def peaks_path() -> str:
    """Where measured job peaks live: ``$O4_JOB_PEAKS_PATH`` or
    ``~/.ortho4xp/job_peaks.json`` (one per user, beside the ledger)."""
    return os.environ.get(ENV_PEAKS, "").strip() or os.path.join(
        os.path.expanduser("~"), ".ortho4xp", "job_peaks.json")


def _key(kind: str, subject: str) -> str:
    return "%s %s" % (kind, subject.upper()) if subject else kind


def _read_peaks() -> dict:
    try:
        with open(peaks_path(), encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def estimate_gigabytes(kind: str, subject: str = "") -> float:
    """The job's expected memory: its own recorded peak (else the kind's
    largest recorded peak) times the recorded-peak margin, or
    :data:`DEFAULT_GB`."""
    peaks = _read_peaks()
    peak = peaks.get(_key(kind, subject))
    if not isinstance(peak, (int, float)) or peak <= 0:
        same = [v for k, v in peaks.items() if k.split(" ")[0] == kind
                and isinstance(v, (int, float)) and v > 0]
        peak = max(same) if same else None
    if peak:
        return round(float(peak) * _STEP_MEMORY.RECORDED_PEAK_MARGIN, 2)
    return float(DEFAULT_GB.get(kind, _SLOTS.BUDGET["worker_gb"]))


def _peak_gigabytes() -> float:
    """This process's peak resident memory (``ru_maxrss``: bytes on macOS,
    KiB elsewhere), 0 where the platform has no ``resource``."""
    try:
        import resource
    except ImportError:
        return 0.0
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    scale = 1024.0 ** 3 if sys.platform == "darwin" else 1024.0 ** 2
    return rss / scale


def _record_peak(kind: str, subject: str, gigabytes: float) -> None:
    """Store ``gigabytes`` as the job's measured peak (atomic replace;
    a lost race loses one record, never the file)."""
    if gigabytes <= 0.0 or os.environ.get(_SLOTS.ENV_UNGATED):
        return                             # a test process is no job's peak
    with contextlib.suppress(OSError, ValueError):
        peaks = _read_peaks()
        peaks[_key(kind, subject)] = round(gigabytes, 2)
        path = Path(peaks_path())
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".job_peaks")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(peaks, handle, indent=1, sort_keys=True)
        os.replace(tmp, path)


def claim_lane(root: "str | os.PathLike | None" = None) -> None:
    """Name this process tree a LANE on the ledger (unless an ancestor
    named it: the app's engine is ``app``), labelled by its worktree —
    ``.claude/worktrees/<name>/…`` — or its checkout's folder."""
    here = Path(root or os.getcwd()).resolve()
    parts = here.parts
    name = (parts[parts.index("worktrees") + 1]
            if "worktrees" in parts[:-1] else here.parent.name)
    _MEM.claim("lane", "lane %s" % name)


@contextlib.contextmanager
def admit(kind: str, subject: str = "", *, need_gb: "float | None" = None,
          give_up=None, emit=print, poll_s: float = POLL_S,
          say_every_s: float = SAY_EVERY_S, clock=time.monotonic,
          sleep=time.sleep):
    """Wait until the machine admits this job, hold its memory on the
    ledger while the block runs, record its peak after (module doc).
    Yields the gigabytes reserved.  ``give_up()`` true ends a wait with
    ``SystemExit``."""
    claim_lane(Path(__file__).resolve().parents[1])
    need = estimate_gigabytes(kind, subject) if need_gb is None else float(need_gb)
    what = ("%s %s" % (kind, subject)).strip()
    began = clock()
    said = None
    while True:
        with _MEM.admission():             # read and reserve as one
            verdict = _SLOTS.machine_verdict(need, idle=True)
            if verdict.ok:
                held = _reserve(need, what)
                break
        now = clock()
        if said is None or now - said >= say_every_s:
            said = now
            _say(emit, "Machine gate: %s waits %.0f s for memory — %s."
                 % (what, now - began, verdict.text))
        if give_up is not None and give_up():
            raise SystemExit("Machine gate: %s gave up waiting for memory" % what)
        sleep(poll_s)
    if said is not None:
        _say(emit, "Machine gate: %s starts after %.0f s waiting."
             % (what, clock() - began))
    try:
        yield need
    finally:
        held.release()
        _record_peak(kind, subject, _peak_gigabytes())


def admit_process(kind: str, subject: str = "", **kw) -> float:
    """:func:`admit` for the rest of this process (a tool's ``main`` after
    its arguments are read): released, and the peak recorded, at exit.
    Returns the gigabytes reserved."""
    gate = admit(kind, subject, **kw)
    need = gate.__enter__()
    atexit.register(gate.__exit__, None, None, None)
    return need


def _reserve(need: float, what: str) -> "_MEM.Reservation":
    if os.environ.get(_SLOTS.ENV_UNGATED):
        return _MEM.Reservation()
    return _MEM.reserve(need, what)


def _say(emit, line: str) -> None:
    with contextlib.suppress(Exception):
        emit(line, flush=True) if emit is print else emit(line)


def admissible_workers(per_worker_gb: float, want: int) -> int:
    """Workers of ``per_worker_gb`` the machine admits now, at most
    ``want`` and at least one (the caller's own process runs one)."""
    want = max(1, int(want))
    if os.environ.get(_SLOTS.ENV_UNGATED):
        return want
    verdict = _SLOTS.machine_verdict(per_worker_gb)
    if not verdict.ok:
        return 1
    return max(1, min(want, 1 + int(verdict.spare_gb // max(per_worker_gb, 1e-9))))
