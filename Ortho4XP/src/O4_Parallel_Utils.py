import os
import subprocess
import sys
import threading
import time
import O4_UI_Utils as UI


# ---------------------------------------------------------------------------
# Machine-aware slot resolution ("0 = Auto" in the slot settings,
# docs/specs/parallel-tile-builds.md §2).  Each knob gets the formula its
# bottleneck warrants: tile builds bind on MEMORY as much as cores, DDS
# conversion is CPU-bound, downloads are network-bound (cores irrelevant).
#
# Owner ruling 2026-07-17: MACHINE resources (processor, memory pressure
# short of the mesh cliff) are the operating system's to arbitrate — six
# hand-launched Ortho4XP copies plus X-Plane always time-sliced fine.
# Per-tile pools therefore run at FULL machine width regardless of how
# many tiles build concurrently.  Deliberate throttles remain only where
# the operating system cannot help: REMOTE SERVER goodwill (the
# orchestrator's OpenStreetMap/imagery request caps, the bathymetry cell
# fetch below) and the multi-gigabyte mesh working-set cliff (the
# orchestrator's memory admission gate).
# ---------------------------------------------------------------------------
def machine_core_count() -> int:
    """Logical processor count (4 when the platform will not say)."""
    return os.cpu_count() or 4


def machine_memory_gigabytes() -> float:
    """Total physical memory in gigabytes (8.0 when undeterminable).

    Standard-library only: ``os.sysconf`` on macOS/Linux, the Windows
    ``GlobalMemoryStatusEx`` call through ``ctypes`` elsewhere.
    """
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        page_count = os.sysconf("SC_PHYS_PAGES")
        if page_size > 0 and page_count > 0:
            return page_size * page_count / (1024.0 ** 3)
    except (ValueError, OSError, AttributeError):
        pass
    try:
        import ctypes

        class _MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_uint32),
                ("dwMemoryLoad", ctypes.c_uint32),
                ("ullTotalPhys", ctypes.c_uint64),
                ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64),
                ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64),
                ("ullAvailVirtual", ctypes.c_uint64),
                ("ullAvailExtendedVirtual", ctypes.c_uint64),
            ]

        status = _MemoryStatus()
        status.dwLength = ctypes.sizeof(_MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status.ullTotalPhys / (1024.0 ** 3)
    except Exception:
        pass
    return 8.0


# Fraction of AVAILABLE memory one run may PROJECT onto the steps it has
# admitted concurrently (owner ruling 2026-07-30, "cap memory usage to
# 80 % of available memory"; docs/specs/apron-string-and-scheduling-spec
# §A.2).  The orchestrator samples the ceiling ONCE per run — see
# o4_engine.parallel.step_memory_budget_gigabytes for why re-sampling it
# live would be a feedback loop rather than a gate.
MEMORY_CEILING_FRACTION = 0.8

# The available-memory probe shells out on macOS; a short cache keeps a
# dispatch loop from spawning one ``vm_stat`` per admission decision
# while still letting a long-lived front end see the machine change.
_AVAILABLE_MEMORY_CACHE_SECONDS = 2.0
_available_memory_cache = [0.0, 0.0]   # [sampled_at, gigabytes]
_available_memory_lock = threading.Lock()


def _probe_available_memory_gigabytes():
    """Free-plus-reclaimable physical memory, or ``None`` if unknowable.

    Standard library only (this module is imported by core pipeline
    code).  Linux reads ``MemAvailable``, macOS totals ``vm_stat``'s
    free + inactive + speculative + purgeable pages (the pages the
    kernel hands out without swapping), Windows reads
    ``GlobalMemoryStatusEx().ullAvailPhys``.
    """
    try:
        with open("/proc/meminfo", "r") as handle:
            for line in handle:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / (1024.0 ** 2)
    except (OSError, ValueError, IndexError):
        pass
    try:
        if "dar" in sys.platform:
            page_size = os.sysconf("SC_PAGE_SIZE")
            # close_fds=False is load-bearing, not tidiness: it is what
            # makes CPython take posix_spawn() instead of fork()+exec().
            # This function may be called from a process that has
            # imported the pipeline, and once GDAL has warped anything
            # its bundled PROJ registers a pthread_atfork handler that
            # segfaults in the forked child before exec runs (the
            # 2026-07-16 crash class — see
            # O4_UI_Utils.external_tool_keyword_arguments).  Python file
            # descriptors are non-inheritable by default (PEP 446), so
            # not sweeping them is safe.
            output = subprocess.run(
                ["/usr/bin/vm_stat"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, timeout=5.0, check=True,
                close_fds=False).stdout
            counts = {}
            for line in output.splitlines():
                if ":" not in line:
                    continue
                name, _, value = line.partition(":")
                digits = value.strip().rstrip(".")
                if digits.isdigit():
                    counts[name.strip().lower()] = int(digits)
            pages = sum(
                counts.get(key, 0)
                for key in ("pages free", "pages inactive",
                            "pages speculative", "pages purgeable")
            )
            if pages > 0:
                return pages * page_size / (1024.0 ** 3)
    except Exception:
        pass
    try:
        import ctypes

        class _AvailableStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_uint32),
                ("dwMemoryLoad", ctypes.c_uint32),
                ("ullTotalPhys", ctypes.c_uint64),
                ("ullAvailPhys", ctypes.c_uint64),
                ("ullTotalPageFile", ctypes.c_uint64),
                ("ullAvailPageFile", ctypes.c_uint64),
                ("ullTotalVirtual", ctypes.c_uint64),
                ("ullAvailVirtual", ctypes.c_uint64),
                ("ullAvailExtendedVirtual", ctypes.c_uint64),
            ]

        status = _AvailableStatus()
        status.dwLength = ctypes.sizeof(_AvailableStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status.ullAvailPhys / (1024.0 ** 3)
    except Exception:
        pass
    return None


def machine_available_memory_gigabytes() -> float:
    """Physical memory the machine can hand out right now, in gigabytes.

    Falls back to TOTAL physical memory when the platform will not say —
    the conservative direction is debatable either way, so the fallback
    keeps the old total-memory behaviour rather than inventing a number.
    """
    now = time.time()
    with _available_memory_lock:
        sampled_at, value = _available_memory_cache
        if value > 0.0 and now - sampled_at < _AVAILABLE_MEMORY_CACHE_SECONDS:
            return value
    probed = _probe_available_memory_gigabytes()
    if not probed or probed <= 0.0:
        probed = machine_memory_gigabytes()
    with _available_memory_lock:
        _available_memory_cache[0] = now
        _available_memory_cache[1] = float(probed)
    return float(probed)


# Set by the parallel-build scheduler in every worker child's
# environment (and refreshed by the "siblings" broadcast as tiles
# finish): how many sibling tiles are building at once.  Since the
# 2026-07-17 lean-on-the-operating-system ruling, only NETWORK fetchers
# that hit small remote hosts consult it (the bathymetry cell fetch) —
# processor-bound pools run at full width regardless.
PARALLEL_SIBLINGS_ENVIRONMENT_KEY = "O4_PARALLEL_BUILD_SIBLINGS"


def parallel_sibling_count() -> int:
    """How many tiles are building concurrently (1 outside a parallel run)."""
    try:
        return max(1, int(os.environ.get(
            PARALLEL_SIBLINGS_ENVIRONMENT_KEY, "1")))
    except ValueError:
        return 1


# Rough resident cost of ONE worker child that has imported the pipeline
# and is running a step (gigabytes).  This is the pool-SIZE sanity bound
# only: per-step peak footprints are the orchestrator's business (its
# projection against MEMORY_CEILING_FRACTION of available memory,
# o4_engine.parallel), and this divisor exists solely so Auto never
# spawns interpreters the orchestrator's ceiling could not admit.
BUILD_SLOT_MEMORY_GIGABYTES = 2.0


def effective_build_slots(configured) -> int:
    """Concurrent tile builds for a ``max_build_slots`` value (0 = Auto).

    Auto is the LOGICAL CORE COUNT, floored at one and bounded by how
    many worker interpreters the memory ceiling could ever admit
    (``MEMORY_CEILING_FRACTION`` of available memory divided by
    :data:`BUILD_SLOT_MEMORY_GIGABYTES`).

    Sizing revised 2026-07-30 (docs/specs/apron-string-and-scheduling-
    spec.md §A.2, owner: "I could run as many tiles as I have cores
    concurrently if they have all their data downloaded") from
    ``min(12, cores // 2, memory // 6)``.  Both retired divisors were
    proxies for constraints that are now gated explicitly and per step:
    REMOTE pressure by the orchestrator's osm/imagery class caps, MEMORY
    by its projected-footprint admission gate.  Leaving the proxies in
    place as well would cap compute below the cores the owner asked for
    — the 2026-07-30 defect report (18 cores at 46 % utilisation) was
    exactly that double-counting one revision earlier.  An EXPLICIT
    setting is honoured verbatim, above or below Auto.
    """
    configured = int(configured or 0)
    if configured > 0:
        return configured
    by_cores = machine_core_count()
    by_memory = int(
        machine_available_memory_gigabytes()
        * MEMORY_CEILING_FRACTION
        // BUILD_SLOT_MEMORY_GIGABYTES
    )
    return max(1, min(by_cores, by_memory))


def effective_convert_slots(configured) -> int:
    """Parallel DDS conversions for a ``max_convert_slots`` value (0 = Auto).

    Conversion is CPU-bound: Auto uses every core but two (floor two,
    cap sixteen) — at FULL width even when several tiles build
    concurrently (2026-07-17 ruling: the operating system time-slices
    competing pools fine, and the last running tile inherits the whole
    machine with no hand-off machinery).
    """
    configured = int(configured or 0)
    if configured > 0:
        return configured
    return max(2, min(16, machine_core_count() - 2))


def effective_download_slots(configured) -> int:
    """Parallel orthophoto constructions for ``max_download_slots``
    (0 = Auto).

    Downloads are network-bound, so the core count is irrelevant: Auto
    is two (each orthophoto already runs sixteen request threads),
    whether or not sibling tiles build concurrently — commercial
    imagery hosts handle a handful of parallel streams comfortably, and
    the orchestrator's imagery class cap already bounds how many tiles
    download at once.  Users on external drives may prefer an explicit
    one — the historic default — per the long-standing warning in the
    setting's hint.
    """
    configured = int(configured or 0)
    if configured > 0:
        return configured
    return 2

################################################################################
class parallel_worker(threading.Thread):
    def __init__(self, task, queue, progress=None, success=[1]):
        threading.Thread.__init__(self)
        self._task = task
        self._queue = queue
        self._progress = progress
        self._success = success

    def run(self):
        while True:
            args = self._queue.get()
            if isinstance(args, str) and args == "quit":
                try:
                    UI.progress_bar(self._progress["bar"], 100)
                except:
                    pass
                return 1
            try:
                self._success[0] = self._task(*args) and self._success[0]
            except Exception:
                # A worker crash must fail the step loudly: swallowing it
                # here made Step 2.5 report "normal exit" with zero masks
                # built (custom-extent NameError, 2026-07-16).
                import traceback
                UI.lvprint(0, "ERROR: a worker task crashed:\n"
                           + traceback.format_exc())
                self._success[0] = 0
            if self._progress:
                self._progress["done"] += 1
                UI.progress_bar(
                    self._progress["bar"],
                    int(
                        100
                        * self._progress["done"]
                        / (self._progress["done"] + self._queue.qsize())
                    ),
                )
            if UI.red_flag:
                return 0

################################################################################
def parallel_execute(task, queue, nbr_workers, progress=None):
    workers = []
    success = [1]
    for _ in range(nbr_workers):
        queue.put("quit")
        worker = parallel_worker(task, queue, progress, success)
        worker.start()
        workers.append(worker)
    for worker in workers:
        worker.join()
    if UI.red_flag:
        return 0
    return success[0]


################################################################################
def parallel_launch(task, queue, nbr_workers, progress=None):
    workers = []
    for _ in range(nbr_workers):
        worker = parallel_worker(task, queue, progress)
        worker.start()
        workers.append(worker)
    return workers

################################################################################
def parallel_join(workers):
    for worker in workers:
        worker.join()