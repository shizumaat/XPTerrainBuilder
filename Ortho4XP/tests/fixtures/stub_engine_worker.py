#!/usr/bin/env python3
"""A stand-in worker child for the parallel-tile-build scheduler tests.

Pure standard library.  Speaks the JSON-lines engine protocol
(``src/o4_engine/jsonl.py`` docstring) well enough for
``o4_engine.parallel.ParallelBuildRun`` to drive it as a real worker
subprocess, but runs NO pipeline: it emits a scripted event stream whose
shape is chosen by the tile COORDINATES the parent hands it, so a test
controls the script purely through the tiles it builds.

Protocol, briefly:

* On start we print one ``{"event": "EngineHello", ...}`` line to stdout
  and flush (the parent's handshake gate), then read commands, one JSON
  object per stdin line.
* ``build`` (``tiles=[[lat, lon]]``): reply ``{"reply": id, "ok": true}``
  then emit a per-tile scripted stream ending in the child-run-level
  ``RunDone`` the parent expects (and suppresses).
* ``cancel``: set a flag the active build polls.
* End-of-file on stdin: exit 0 (the parent closed our stdin to retire us).

Tile-coordinate scripts (switch on ``lat``):

* ``lat == 60`` — a cancellable sleeper: emit progress, then sleep ~0.6 s
  polling stdin (via the reader thread's cancel flag).  If cancelled,
  emit ``TileState`` label ``"stopped"`` + ``RunDone``; otherwise finish
  the happy path.
* ``lat == 61`` — a failing tile: ``BuildDone`` ``ok=false`` +
  ``TileState`` state ``"error"`` then ``RunDone``.
* ``lat == 62`` — a crashing worker: emit one progress line then
  ``os._exit(1)`` mid-build (no ``RunDone`` — the parent synthesizes the
  failure from the unexpected exit).
* ``lat == 65`` — a sleeper that DIES on cancel: on the cancel flag it
  ``os._exit(0)``s with no terminal event (the SIGTERM-escalated real
  child), so the parent must label the tile stopped itself.
* ``lat == 66`` — a WEDGED worker: sleeps ``STUB_WORKER_WEDGE_SECONDS``
  (default 30) and never polls the cancel flag at all — a step stuck in
  an operation with no cancellation checkpoint.  Only the parent's
  SIGTERM escalation can end it; the parent must both bound the wait
  and label the tile stopped.
* ``lat == 63`` — an AUTO-PATCH tile: its ``vector`` step fetches
  briefly, emits ``AutoPatchBegin``, then BURNS PROCESSOR for
  ``STUB_WORKER_SOLVE_SECONDS`` (default 0.6) before reporting the
  airport done — the hybrid vector step of
  docs/specs/vector-step-class-split-spec.md, so a test can prove the
  solve phase runs uncapped while the fetch phase stays capped (markers
  ``solvestart_``/``solveend_``).  Every other step is the happy path.
* ``lat == 64`` — an IMAGERY tile: its ``imagery`` step downloads
  briefly, emits ``ImageryDownloadsDone``, then BURNS PROCESSOR for
  ``STUB_WORKER_CONVERT_SECONDS`` (default 0.6) as the DDS conversion
  tail — the hybrid imagery step of
  docs/specs/apron-string-and-scheduling-spec.md §A.2, so a test can
  prove the tail runs uncapped while the download phase stays capped
  (markers ``downloadend_``, ``convertstart_``/``convertend_``).  Every
  other step is the happy path.
* anything else — the happy path: two ``StepProgress`` lines, then
  ``TileState`` done + ``BuildDone`` ok + ``RunDone``.

``STUB_WORKER_PHASE_BARRIER=N`` makes the solve / conversion phases wait
for N workers to reach them before their start marker is written, so a
concurrency twin measures admission width and not this machine's process
spawn stagger (see ``_await_phase_barrier``).

``STUB_WORKER_CONSOLE_LINE`` is written to stderr at start as UTF-8
bytes — a real worker's pinned console — so a test can read what the
parent makes of it.

If ``STUB_WORKER_MARK_DIR`` is set, ``start_<lat>_<lon>`` and
``end_<lat>_<lon>`` marker files (each containing ``time.time()``) are
written at build start / end so a test can PROVE two tiles overlapped in
wall-clock time.

Every emitted event is one JSON object per line on stdout, flushed;
nothing else touches stdout (any chatter goes to stderr).
"""

import json
import os
import queue
import sys
import threading
import time

MARK_DIR = os.environ.get("STUB_WORKER_MARK_DIR")

# Small inter-event pauses so concurrent tiles overlap measurably in
# wall-clock time (the two-slot overlap test asserts on marker files).
_STEP_PAUSE = 0.06
_TERMINAL_PAUSE = 0.08
_SLEEPER_SECONDS = 0.6
_SLEEPER_POLL = 0.02

_SOLVE_SECONDS = float(os.environ.get("STUB_WORKER_SOLVE_SECONDS", "0.6"))
# The fetch part of an auto-patch tile's vector step: long enough that
# the osm class cap is observable in the marker intervals.
_FETCH_SECONDS = float(os.environ.get("STUB_WORKER_FETCH_SECONDS", "0.15"))
# The DDS conversion tail of an imagery tile, and the download phase that
# precedes it (same roles as _SOLVE_SECONDS / _FETCH_SECONDS above).
_CONVERT_SECONDS = float(
    os.environ.get("STUB_WORKER_CONVERT_SECONDS", "0.6"))
_DOWNLOAD_SECONDS = float(
    os.environ.get("STUB_WORKER_DOWNLOAD_SECONDS", "0.15"))

# How long the wedged tile (lat 66) sleeps without ever polling cancel:
# far past any test's deadline, so only the parent's escalation ends it.
_WEDGE_SECONDS = float(os.environ.get("STUB_WORKER_WEDGE_SECONDS", "30"))

# ── the phase barrier (#142, and the #76 class before it) ─────────────
# A concurrency twin measures ADMISSION width by sampling the overlap of
# per-tile phase intervals.  That reading is only exact while the phases
# START together: the workers are separate PROCESSES, so anything that
# staggers their arrival at the measured phase by more than the phase
# lasts drops the sampled peak below the width being proved, with the
# scheduler behaving perfectly.  #142 read 5 of 6 that way on
# windows-latest, #76 read 5 of 6 on macOS; #76 was mitigated by
# LENGTHENING the phase, which buys margin against the stagger without
# bounding it.  (What produces the stagger on those runners is NOT
# established -- interpreter spawn skew up to 2 s did not reproduce it on
# a 4-core Linux box.  The barrier does not need to know: it removes the
# dependence on alignment rather than the cause of the misalignment.)
# With ``STUB_WORKER_PHASE_BARRIER=N`` set, every worker entering the
# measured phase announces its arrival in the mark dir and waits for N
# arrivals before the phase's start marker is written, so the stagger is
# absorbed BEFORE the measurement window opens.  A worker the scheduler
# never admits never arrives, so an admission width BELOW N still fails
# the twin -- this moves the machine out of the measurement, it does not
# weaken the assertion.
_PHASE_BARRIER_PARTY = int(os.environ.get("STUB_WORKER_PHASE_BARRIER", "0"))
_PHASE_BARRIER_SECONDS = float(
    os.environ.get("STUB_WORKER_PHASE_BARRIER_SECONDS", "20.0"))
_PHASE_BARRIER_POLL = 0.01
_PHASE_BARRIER_PREFIX = "phasearrival"

_cancel_flag = threading.Event()
_build_queue: "queue.Queue" = queue.Queue()
_eof = threading.Event()


def _emit(obj):
    """Write one protocol line to stdout and flush."""
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _chatter(*parts):
    """Non-protocol text goes to stderr only (the parent tees it)."""
    print(*parts, file=sys.stderr, flush=True)


def _write_marker(kind, lat, lon, step=None, only_if_absent=False):
    if not MARK_DIR:
        return
    name = "%s_%d_%d" % (kind, lat, lon)
    if step:
        name += "_" + step
    path = os.path.join(MARK_DIR, name)
    if only_if_absent and os.path.exists(path):
        return
    try:
        # Atomic write (temp + rename): a reader must never observe a
        # created-but-empty file, whatever the read/write interleaving.
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8", newline="") as handle:
            handle.write(repr(time.time()))
        os.replace(temporary, path)
    except OSError as error:
        _chatter("stub worker could not write marker", path, error)


def _await_phase_barrier(phase, lat, lon):
    """Hold until ``_PHASE_BARRIER_PARTY`` workers have reached ``phase``.

    Returns True when the party assembled, False when it did not (the
    deadline expired, i.e. the scheduler never ran that many at once) --
    either way the worker proceeds, so a short party is reported by the
    twin's own concurrency assertion rather than by a hang here.  Arrival
    is a file in the shared mark dir because the workers are processes
    with no other channel between them; a barrier of 0 or 1, or no mark
    dir, is a no-op, so every twin that does not opt in is unaffected."""
    if _PHASE_BARRIER_PARTY < 2 or not MARK_DIR:
        return True
    _write_marker("%s_%s" % (_PHASE_BARRIER_PREFIX, phase), lat, lon)
    prefix = "%s_%s_" % (_PHASE_BARRIER_PREFIX, phase)
    deadline = time.time() + _PHASE_BARRIER_SECONDS
    while True:
        try:
            arrived = sum(1 for name in os.listdir(MARK_DIR)
                          if name.startswith(prefix)
                          and not name.endswith(".tmp"))
        except OSError:
            return True
        if arrived >= _PHASE_BARRIER_PARTY:
            return True
        if time.time() >= deadline:
            _chatter("stub worker phase barrier", phase, "timed out with",
                     arrived, "of", _PHASE_BARRIER_PARTY, "arrived")
            return False
        time.sleep(_PHASE_BARRIER_POLL)


def _step(lat, lon, key, percent, indeterminate=False):
    _emit({
        "event": "StepProgress",
        "lat": lat, "lon": lon,
        "step_key": key, "label": key,
        "percent": percent, "indeterminate": indeterminate,
    })


def _tile_state(lat, lon, state, label="", percent=0.0):
    _emit({
        "event": "TileState",
        "lat": lat, "lon": lon,
        "state": state, "label": label, "percent": percent,
    })


def _build_done(lat, lon, ok, error=""):
    _emit({
        "event": "BuildDone",
        "lat": lat, "lon": lon, "ok": ok, "error": error,
    })


def _run_done():
    # The parent suppresses the child's RunDone (it is child-run-level) and
    # uses it only as the "this tile's run finished" signal.
    _emit({"event": "RunDone", "done_count": 0, "error_count": 0,
           "cancelled": False})


def _reader():
    """Background stdin reader: routes builds to a queue, sets the cancel
    flag, and signals end-of-file."""
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            continue
        command = message.get("cmd")
        if command == "cancel":
            _cancel_flag.set()
        elif command == "build":
            _build_queue.put(message)
        # Any other command (shutdown, etc.) is ignored by this stub.
    _eof.set()
    _build_queue.put(None)   # unblock the main loop


def _run_one_build(message):
    tiles = message.get("tiles") or [[0, 0]]
    lat, lon = int(tiles[0][0]), int(tiles[0][1])
    # The phase-aware orchestrator (spec 3.8) sends one step per build
    # command; whole-build commands (no "steps") keep the legacy shape.
    steps = message.get("steps") or []
    step_key = steps[0] if steps else "vector"
    _emit({"reply": message.get("id"), "ok": True})
    # A child is a fresh process after a per-tile cancel, but reuse across
    # tiles is allowed for the non-cancel path — clear any stale flag.
    _cancel_flag.clear()
    # Tile-level markers: "start" is the FIRST command's instant (never
    # overwritten), "end" the latest command's end (last step wins).
    _write_marker("start", lat, lon, only_if_absent=True)
    if steps:
        _write_marker("stepstart", lat, lon, step=step_key)

    if lat == 60:
        _sleeper_tile(lat, lon, step_key)
    elif lat == 61:
        _failing_tile(lat, lon, step_key)
    elif lat == 62:
        _crashing_tile(lat, lon, step_key)
    elif lat == 65:
        _dying_on_cancel_tile(lat, lon, step_key)
    elif lat == 66:
        _wedged_tile(lat, lon, step_key)
    elif lat == 63 and step_key == "vector":
        _auto_patch_tile(lat, lon, step_key)
    elif lat == 64 and step_key == "imagery":
        _imagery_tile(lat, lon, step_key)
    else:
        _happy_tile(lat, lon, step_key)

    # Markers BEFORE RunDone: the tests read them the instant the parent
    # reports the run finished, so they must be durable before the
    # terminal event leaves this process (emitting RunDone first raced
    # the reader against the marker write — observed as an
    # intermittently EMPTY end_<lat>_<lon> file).
    if steps:
        _write_marker("stepend", lat, lon, step=step_key)
    _write_marker("end", lat, lon)
    _run_done()


def _happy_tile(lat, lon, step_key="vector"):
    _step(lat, lon, step_key, 0.0)
    time.sleep(_STEP_PAUSE)
    _step(lat, lon, step_key, 50.0)
    time.sleep(_STEP_PAUSE)
    _tile_state(lat, lon, "done", percent=100.0)
    time.sleep(_TERMINAL_PAUSE)
    _build_done(lat, lon, True)
    time.sleep(_TERMINAL_PAUSE)


def _sleeper_tile(lat, lon, step_key="vector"):
    _step(lat, lon, step_key, 0.0)
    time.sleep(_STEP_PAUSE)
    _step(lat, lon, step_key, 30.0)
    deadline = time.time() + _SLEEPER_SECONDS
    while time.time() < deadline:
        if _cancel_flag.is_set():
            _tile_state(lat, lon, "queued", label="stopped")
            time.sleep(_TERMINAL_PAUSE)
            return
        time.sleep(_SLEEPER_POLL)
    # Never cancelled: finish the happy way.
    _tile_state(lat, lon, "done", percent=100.0)
    time.sleep(_TERMINAL_PAUSE)
    _build_done(lat, lon, True)
    time.sleep(_TERMINAL_PAUSE)


def _dying_on_cancel_tile(lat, lon, step_key="vector"):
    """A sleeper whose cancel ends the PROCESS, not the step: on the
    cancel flag it exits 0 with no ``TileState``/``RunDone`` — what a
    real child does when the escalation's SIGTERM reaches its transport
    (``jsonl._stop_session_and_exit_process`` → ``os._exit(0)``) while
    the step never polled its red flag.  Never cancelled: happy path."""
    _step(lat, lon, step_key, 0.0)
    time.sleep(_STEP_PAUSE)
    _step(lat, lon, step_key, 30.0)
    deadline = time.time() + _SLEEPER_SECONDS
    while time.time() < deadline:
        if _cancel_flag.is_set():
            sys.stdout.flush()
            os._exit(0)
        time.sleep(_SLEEPER_POLL)
    _tile_state(lat, lon, "done", percent=100.0)
    time.sleep(_TERMINAL_PAUSE)
    _build_done(lat, lon, True)
    time.sleep(_TERMINAL_PAUSE)


def _wedged_tile(lat, lon, step_key="vector"):
    """A step that never reaches a cancellation checkpoint: it sleeps
    the whole wedge without looking at the cancel flag, so a cooperative
    ``cancel`` does nothing and only the parent's SIGTERM escalation
    (which this plain process dies to) ends it."""
    _step(lat, lon, step_key, 0.0)
    time.sleep(_STEP_PAUSE)
    _step(lat, lon, step_key, 30.0)
    time.sleep(_WEDGE_SECONDS)
    _tile_state(lat, lon, "done", percent=100.0)
    time.sleep(_TERMINAL_PAUSE)
    _build_done(lat, lon, True)
    time.sleep(_TERMINAL_PAUSE)


def _failing_tile(lat, lon, step_key="vector"):
    _step(lat, lon, step_key, 0.0)
    time.sleep(_STEP_PAUSE)
    _step(lat, lon, step_key, 50.0, indeterminate=True)
    time.sleep(_STEP_PAUSE)
    _build_done(lat, lon, False, error="a build step failed")
    time.sleep(_TERMINAL_PAUSE)
    _tile_state(lat, lon, "error", label="failed")
    time.sleep(_TERMINAL_PAUSE)


def _auto_patch_tile(lat, lon, step_key="vector"):
    """The hybrid vector step: a remote FETCH, then the auto-patch solve.

    The solve burns processor deliberately (a sleeping "solve" would
    prove nothing about the concurrency the class split is meant to
    unlock — a ``ps`` sample must be able to SEE these workers running).
    """
    airport = "S%d%d" % (abs(lat) % 10, abs(lon) % 100)
    _step(lat, lon, step_key, 0.0)
    time.sleep(_FETCH_SECONDS)               # the remote fetch
    _write_marker("fetchend", lat, lon)
    _emit({"event": "AutoPatchBegin", "airports": [airport],
           "lat": lat, "lon": lon})
    # The fetch token is released by AutoPatchBegin above, so a worker
    # waiting here holds nothing the others need.
    _await_phase_barrier("solve", lat, lon)
    _write_marker("solvestart", lat, lon)
    _burn_processor(_SOLVE_SECONDS)          # the solve: real processor
    _write_marker("solveend", lat, lon)
    _emit({"event": "AutoPatchProgress", "airport": airport,
           "done": 1, "total": 1, "label": "Done", "status": "done",
           "lat": lat, "lon": lon})
    time.sleep(_STEP_PAUSE)                  # the vector tail
    _tile_state(lat, lon, "done", percent=100.0)
    time.sleep(_TERMINAL_PAUSE)
    _build_done(lat, lon, True)
    time.sleep(_TERMINAL_PAUSE)


def _burn_processor(seconds):
    """Occupy a core for ``seconds`` — a sleeping phase would prove
    nothing about concurrency a ``ps`` sample is supposed to SEE."""
    deadline = time.time() + seconds
    spin = 0
    while time.time() < deadline:
        spin = (spin + 1) % 1000003
        for _ in range(2000):
            spin = (spin * 31 + 7) % 1000003


def _imagery_tile(lat, lon, step_key="imagery"):
    """The hybrid imagery step: a remote DOWNLOAD phase, then the local
    DDS conversion tail (which burns processor, like the solve does)."""
    _step(lat, lon, step_key, 0.0)
    time.sleep(_DOWNLOAD_SECONDS)            # the remote downloads
    _write_marker("downloadend", lat, lon)
    _emit({"event": "ImageryDownloadsDone", "lat": lat, "lon": lon,
           "downloaded": 4, "failed": 0})
    # As in the solve above: the download token is released by
    # ImageryDownloadsDone, so the late tiles can still get theirs.
    _await_phase_barrier("convert", lat, lon)
    _write_marker("convertstart", lat, lon)
    _burn_processor(_CONVERT_SECONDS)
    _write_marker("convertend", lat, lon)
    _tile_state(lat, lon, "done", percent=100.0)
    time.sleep(_TERMINAL_PAUSE)
    _build_done(lat, lon, True)
    time.sleep(_TERMINAL_PAUSE)


def _crashing_tile(lat, lon, step_key="vector"):
    _step(lat, lon, step_key, 0.0)
    time.sleep(_STEP_PAUSE)
    _chatter("stub worker crashing on purpose for", lat, lon)
    os._exit(1)


def main():
    console_line = os.environ.get("STUB_WORKER_CONSOLE_LINE")
    if console_line:
        # What a real worker's console is: UTF-8 BYTES, whatever the
        # locale (O4_Console_Encoding pins it at the entry) — issue #125.
        sys.stderr.buffer.write(console_line.encode("utf-8") + b"\n")
        sys.stderr.buffer.flush()
    _emit({
        "event": "EngineHello",
        "ortho4xp_version": "stub-worker",
        "protocol": "1.1",
        "capabilities": ["build", "cancel", "cancel_tile"],
    })
    threading.Thread(target=_reader, daemon=True).start()
    while True:
        message = _build_queue.get()
        if message is None:      # stdin closed
            break
        _run_one_build(message)
    sys.exit(0)


if __name__ == "__main__":
    main()
