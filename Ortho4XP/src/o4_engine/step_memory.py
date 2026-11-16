"""What one tile step is projected to hold, and what it was measured holding
(issue #2083).

The parallel scheduler admits a step only while the projected peaks of the
steps it has running fit its memory budget.  Until #2083 the vector step
(OSM parse plus the auto-patch solve) was projected at a flat 3 GB, one
HECA measurement from 2026-07-30; a 14-tile run in 1.0.519 measured 6-14 GB
per tile in that step (KMCI 14.1, KDEN 8.0, the LFPx tile 7.0, OTHH 6.9,
HECA 6.6, KIAH 6.3, LFPG 5.9, KHOU 4.7) and filled a 128 GB Mac's swap.

Two answers live here:

* :func:`projected_gigabytes` — a step's projection: the tile's own
  recorded peak for that step (``tile_time_model.step_peaks``) times
  :data:`RECORDED_PEAK_MARGIN` when one exists; otherwise the default
  (:data:`VECTOR_AIRPORT_DEFAULT_GB` for a vector step that may solve
  airports).  A mesh step never projects below its elevation-level size,
  which a changed setting can raise past an old record.
* :func:`tree_resident_gigabytes` — the resident memory of each worker
  process TOGETHER WITH its descendants (the auto-patch solve's airport
  processes and their pools run as grandchildren), one ``ps`` call for
  all of them.  The scheduler samples it while steps run and records each
  step's peak into the tile's build record.

Standard library only; every function here is advisory and never raises.
"""
from __future__ import annotations

import subprocess
import sys

__all__ = ["RECORDED_PEAK_MARGIN", "VECTOR_AIRPORT_DEFAULT_GB",
           "VECTOR_NO_AIRPORT_GB", "LIVE_CHECKED_STEPS",
           "charged_gigabytes", "projected_gigabytes",
           "tree_resident_gigabytes"]

#: a recorded peak is the maximum of 2-second samples, not the true peak:
#: a spike between two samples is missed, so the projection carries a margin
RECORDED_PEAK_MARGIN = 1.15
#: a vector step with airports to solve (or not known to have none) and no
#: recorded peak: the 1.0.519 run's median per-tile peak (6.8 GB) rounded
#: up — the 3 GB of 2026-07-30 admitted 2-5x more solves than fit
VECTOR_AIRPORT_DEFAULT_GB = 8.0
#: a vector step its history says solves no airport: the OSM parse alone,
#: the pre-#2083 flat figure
VECTOR_NO_AIRPORT_GB = 3.0
#: the heavy steps the scheduler also checks against LIVE free memory
#: before it starts one (``O4_Machine_Slots.memory_admits``)
LIVE_CHECKED_STEPS = frozenset({"vector", "mesh"})
#: steps whose heavy inner work takes machine memory ITSELF, one worker at a
#: time against live free memory: the vector step's airport builds and
#: their pools (``slot_gated_pool.run`` -> ``O4_Machine_Slots.try_take``).
#: The scheduler charges such a step at most :data:`VECTOR_AIRPORT_DEFAULT_GB`
#: — its recorded peak is the whole process tree with up to seven airports
#: at once, shared library pages counted once per process (+43-080 in
#: 1.0.539: 62.9 GB charged while the machine stayed 86 % free), and
#: charging it in full held every other tile's step (#2101 follow-up).
_SELF_GATED_STEPS = frozenset({"vector"})

_KIB_PER_GIB = 1024.0 * 1024.0


def projected_gigabytes(step_key, recorded, default, airports_planned=None):
    """Projected peak (GB) of ``step_key`` for one tile.

    ``recorded`` is the tile's ``{step: peak GB}`` history, ``default`` the
    table/elevation-level estimate the scheduler had before #2083, and
    ``airports_planned`` the airports the tile's history says its vector
    step solves (``None`` = unknown).
    """
    peak = (recorded or {}).get(step_key)
    if isinstance(peak, (int, float)) and peak > 0:
        measured = float(peak) * RECORDED_PEAK_MARGIN
        if step_key == "mesh":
            return max(measured, float(default))
        return measured
    if step_key == "vector":
        if airports_planned is not None and not airports_planned:
            return VECTOR_NO_AIRPORT_GB
        return max(VECTOR_AIRPORT_DEFAULT_GB, float(default))
    return float(default)


def charged_gigabytes(step_key, projected):
    """What a step holds against the run's memory budget (and needs free
    to start): its projection, capped for a self-gated step, whose inner
    work is admitted worker by worker against live memory instead."""
    if step_key in _SELF_GATED_STEPS:
        return min(float(projected), VECTOR_AIRPORT_DEFAULT_GB)
    return float(projected)


def _process_table():
    """``[(pid, ppid, rss KiB)]`` of every process, or ``[]``."""
    if sys.platform == "win32":
        return []
    try:
        # close_fds=False keeps CPython on posix_spawn: the scheduler's
        # process may have GDAL/PROJ loaded, whose atfork handler crashes
        # a forked child (O4_Parallel_Utils, the 2026-07-16 crash class).
        output = subprocess.run(
            ["ps", "-A", "-o", "pid=,ppid=,rss="],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            encoding="utf-8", errors="replace",
            timeout=10.0, check=False, close_fds=False).stdout
    except Exception:
        return []
    rows = []
    for line in output.splitlines():
        fields = line.split()
        if len(fields) == 3 and all(f.isdigit() for f in fields):
            rows.append((int(fields[0]), int(fields[1]), int(fields[2])))
    return rows


def tree_resident_gigabytes(root_pids, table=None):
    """``{root pid: GB}``: each root's resident memory plus all of its
    descendants'.  ``table`` (``[(pid, ppid, rss KiB)]``) is read from
    ``ps`` when not given; a root that is gone is absent from the answer,
    and on a platform without ``ps`` the answer is ``{}``."""
    rows = _process_table() if table is None else table
    if not rows:
        return {}
    rss = {pid: kib for pid, _, kib in rows}
    children: dict = {}
    for pid, ppid, _ in rows:
        children.setdefault(ppid, []).append(pid)
    answer = {}
    for root in root_pids:
        if root not in rss:
            continue
        total, stack, seen = 0, [root], set()
        while stack:
            pid = stack.pop()
            if pid in seen:
                continue
            seen.add(pid)
            total += rss.get(pid, 0)
            stack.extend(children.get(pid, ()))
        answer[root] = total / _KIB_PER_GIB
    return answer
