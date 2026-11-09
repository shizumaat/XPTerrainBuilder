"""THE BUILD'S MEMORY GUARD — what one airport build and its pool workers
hold resident, and the NAMED STOP when that is more than the machine can
spare (issue #1980).

Why it exists.  On 2026-11-09 one pack worker of EIDW's partition grew
past 20 GB inside a single GEOS call (a roof-test trim over 12,824 points,
``obj8_grade._near_points``), and the build sat at "resource readings
405/405" for 14 minutes while a 128 GB machine filled its swap and warned
its owner it was out of memory.  The mechanism is fixed where it lived;
this module makes the CLASS impossible: a pool wait reads the build's
memory every :data:`CHECK_S` and stops the stage with
:class:`MemoryCeilingError` — a ``MemoryError``, catalogued as
``airport_memory_ceiling`` by ``O4_Tile_Failures`` — before the machine
runs out, instead of waiting out the pool's stall or falling back to one
core (which would re-run the same reading in the build's own process).

THE CEILINGS (any one stops the stage):

* one WORKER above :data:`WORKER_CEILING_GB` — a worker holds ONE resource
  at a time (``pack_work.PackWorker``); four times the pool's own
  ``WORKER_ALLOWANCE_GB`` is no parse, it is a runaway;
* the BUILD (its process and its workers) above :data:`BUILD_RAM_SHARE` of
  this build's share of physical memory (``pool.share``: the airport
  builds running beside it);
* the MACHINE with less than :data:`SYSTEM_FREE_FLOOR` of its memory free
  (``kern.memorystatus_level`` on macOS, ``MemAvailable`` on Linux,
  ``GlobalMemoryStatusEx`` on Windows) — the owner's "refuse or stop when
  the system is under memory pressure", whoever is using it.

The numbers are module constants, not law: like the pool's own memory law
they never enter a digest, and they change no geometry — a build under
every ceiling is byte-identical with or without this module.

:func:`describe` is the build's memory as one short phrase, which the
progress heartbeat (``engine_v2.V2Progress`` in the v1 driver package) appends to its
"still working" line, so the app shows what a step holds while it runs.
"""
from __future__ import annotations

import dataclasses as _dc
import os
import subprocess
import sys
import typing as _t
import weakref

__all__ = ["MemoryCeilingError", "Reading", "WORKER_CEILING_GB", "BUILD_RAM_SHARE",
           "SYSTEM_FREE_FLOOR", "CHECK_S",
           "breach", "check", "register", "describe"]

#: one worker's resident ceiling, GiB (4 x ``pool.WORKER_ALLOWANCE_GB``)
WORKER_CEILING_GB = 8.0
#: the build's ceiling as a share of ITS share of physical memory
BUILD_RAM_SHARE = 0.6
#: the machine's free-memory floor, as a fraction of its physical memory
SYSTEM_FREE_FLOOR = 0.05
#: seconds between two readings inside one pool wait
CHECK_S = 2.0

_KIB_PER_GIB = 1024.0 * 1024.0
#: the pools whose workers count as this build's (:func:`register`)
_POOLS: "weakref.WeakSet" = weakref.WeakSet()


class MemoryCeilingError(MemoryError):
    """A build step stopped because its memory, or the machine's, passed a
    ceiling (module doc).  ``reading`` is the :class:`Reading` that tripped
    it; ``failure_code`` names the catalogue entry."""

    failure_code = "airport_memory_ceiling"

    def __init__(self, message: str, reading: "Reading | None" = None) -> None:
        super().__init__(message)
        self.reading = reading


@_dc.dataclass(frozen=True)
class Reading:
    """One reading: the build process's resident GiB, each worker's, and
    the machine's free fraction (``None`` where it cannot be read)."""

    parent_gb: float
    workers_gb: tuple[float, ...] = ()
    free_fraction: float | None = None

    @property
    def total_gb(self) -> float:
        return self.parent_gb + sum(self.workers_gb)

    def text(self) -> str:
        """``memory 12.4 GB (4 workers, largest 6.1 GB), system 41 % free``."""
        s = f"memory {self.total_gb:.1f} GB"
        if self.workers_gb:
            s += (f" ({len(self.workers_gb)} worker{'s' if len(self.workers_gb) > 1 else ''}, "
                  f"largest {max(self.workers_gb):.1f} GB)")
        if self.free_fraction is not None:
            s += f", system {100.0 * self.free_fraction:.0f} % free"
        return s


# ── the readers (one per platform, each never raises) ────────────────────

def _resident_kib(pids: _t.Iterable[int]) -> dict[int, int]:
    """``{pid: resident KiB}`` of the processes of ``pids`` that could be
    read — ``ps`` on POSIX, ``K32GetProcessMemoryInfo`` on Windows; a pid
    that is gone is simply absent."""
    pids = sorted({int(p) for p in pids})
    if not pids:
        return {}
    if sys.platform == "win32":
        return _resident_kib_windows(pids)
    try:
        import O4_UI_Utils as _ui
        out = subprocess.run(["ps", "-o", "pid=,rss=", "-p", ",".join(map(str, pids))],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=10,
                             **_ui.external_tool_keyword_arguments()).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    got: dict[int, int] = {}
    for ln in out.splitlines():
        f = ln.split()
        if len(f) == 2 and f[0].isdigit() and f[1].isdigit():
            got[int(f[0])] = int(f[1])
    return got


def _resident_kib_windows(pids: list[int]) -> dict[int, int]:
    try:
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = ([("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)]
                        + [(n, ctypes.c_size_t) for n in (
                            "PeakWorkingSetSize", "WorkingSetSize",
                            "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
                            "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                            "PagefileUsage", "PeakPagefileUsage")])

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.K32GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        got: dict[int, int] = {}
        for pid in pids:
            h = k32.OpenProcess(0x1000, False, pid)    # QUERY_LIMITED_INFORMATION
            if not h:
                continue
            try:
                c = Counters()
                c.cb = ctypes.sizeof(Counters)
                if k32.K32GetProcessMemoryInfo(h, ctypes.byref(c), c.cb):
                    got[pid] = int(c.WorkingSetSize // 1024)
            finally:
                k32.CloseHandle(h)
        return got
    except Exception:
        return {}


def _system_free_fraction() -> float | None:
    """The fraction of the machine's memory free for use, or ``None``."""
    try:
        if sys.platform == "darwin":
            import ctypes
            libc = ctypes.CDLL(None)
            v = ctypes.c_int(0)
            n = ctypes.c_size_t(ctypes.sizeof(v))
            if libc.sysctlbyname(b"kern.memorystatus_level", ctypes.byref(v),
                                 ctypes.byref(n), None, 0) != 0:
                return None
            return max(0.0, min(1.0, v.value / 100.0))
        if sys.platform == "win32":
            from .pool import _MemoryStatusEx
            import ctypes
            st = _MemoryStatusEx()
            st.dwLength = ctypes.sizeof(st)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                return None
            return st.ullAvailPhys / st.ullTotalPhys if st.ullTotalPhys else None
        info: dict[str, int] = {}
        with open("/proc/meminfo", encoding="ascii") as f:
            for ln in f:
                k, _, rest = ln.partition(":")
                if k in ("MemTotal", "MemAvailable"):
                    info[k] = int(rest.split()[0])
        if info.get("MemTotal") and "MemAvailable" in info:
            return info["MemAvailable"] / info["MemTotal"]
    except Exception:
        return None
    return None


# ── the reading and the verdict ───────────────────────────────────────────

def _read(worker_pids: _t.Iterable[int] = ()) -> Reading:
    """This process and ``worker_pids``, and the machine's free fraction."""
    me = os.getpid()
    kib = _resident_kib([me, *worker_pids])
    return Reading(kib.get(me, 0) / _KIB_PER_GIB,
                   tuple(kib[p] / _KIB_PER_GIB for p in sorted(kib) if p != me),
                   _system_free_fraction())


def breach(r: Reading, ram_gb: float | None, share: int = 1) -> str:
    """Which ceiling ``r`` passes (module doc), as a sentence — ``""`` when
    none.  ``ram_gb`` ``None`` (unreadable) leaves the build ceiling out."""
    if r.workers_gb and max(r.workers_gb) > WORKER_CEILING_GB:
        return (f"one worker holds {max(r.workers_gb):.1f} GB "
                f"(ceiling {WORKER_CEILING_GB:.0f} GB a worker)")
    if ram_gb:
        cap = BUILD_RAM_SHARE * ram_gb / max(1, int(share))
        if r.total_gb > cap:
            return (f"the build holds {r.total_gb:.1f} GB (ceiling {cap:.1f} GB: "
                    f"{100 * BUILD_RAM_SHARE:.0f} % of its share of {ram_gb:.0f} GB)")
    if r.free_fraction is not None and r.free_fraction < SYSTEM_FREE_FLOOR:
        return (f"the computer has {100.0 * r.free_fraction:.0f} % of its memory free "
                f"(floor {100 * SYSTEM_FREE_FLOOR:.0f} %)")
    return ""


def check(what: str, worker_pids: _t.Iterable[int], ram_gb: float | None,
          share: int = 1, reader: _t.Callable[..., Reading] = _read) -> Reading:
    """Read the build's memory; raise :class:`MemoryCeilingError` naming
    ``what`` (the stage's activity) when a ceiling is passed."""
    r = reader(worker_pids)
    why = breach(r, ram_gb, share)
    if why:
        raise MemoryCeilingError(f"{what or 'build'}: stopped before the computer runs "
                                 f"out of memory — {why}; {r.text()}", r)
    return r


# ── the heartbeat's phrase ────────────────────────────────────────────────

def register(pool: _t.Any) -> None:
    """Count ``pool``'s workers (its ``pids()``) as this build's."""
    _POOLS.add(pool)


def describe() -> str:
    """The build's memory as a phrase (:meth:`Reading.text`), or ``""``
    where it cannot be read.  Never raises."""
    try:
        pids = [p for pool in list(_POOLS) for p in pool.pids()]
        r = _read(pids)
        return r.text() if r.parent_gb > 0 else ""
    except Exception:
        return ""
