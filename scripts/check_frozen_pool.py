#!/usr/bin/env python3
"""THE FROZEN POOL PASS — ``check_frozen_tile.py <binary> --pass pool``
(issue #362; owner RULINGS 2026-10-05d (2)).

The work pool inside one airport's build (``auto_patch_v2/airport/pool.py``)
is spawn + shared memory + a pool nested under the tile driver's airport
pool.  The frozen CYXY fixture has no pack, so the tile and airport passes
never start one.  This pass makes the bundle under test run its own
``--pool-selfcheck`` entry (``Ortho4XP/src/O4_Pool_Selfcheck.py``) TWICE —
pooled, and pinned to one core — and holds it to:

(a) workers spawned from the frozen executable and answered: >= 2 workers,
    tasks answered > 0, never ``FELL BACK``, never ``serial``;
(b) shared memory read in the workers (``SharedArrays``/``attach``,
    ``share_object``, the shared DEM) — and a real stage, the pack
    partition, through ``pack_work.open_pool``;
(c) the nested case: two airport-pool children (``driver._init_worker``),
    each with work pools of its own and the ``set_share`` budget;
(d) the pooled digest equals the one-core arm's;
(e) after the process has EXITED: no process it started is alive, no
    process of the bundle's image survives, no shared-memory block it
    created exists;
(f) THE PARENT HARD-KILLED MID-MAP, twice.  Inside the pooled arm the
    bundle kills a child of its own that owns a pool over shared blocks
    (the ``kill`` section: the tile driver terminating one airport while
    the engine lives on).  And from here the WHOLE bundle is killed —
    ``--pool-selfcheck --victim --chain``: an engine, its Manager, one
    airport-pool child and that child's workers holding the shared DEM —
    as a cancel, an app quit or an out-of-memory kill does it.  Both
    times, within a bounded wait: every process gone, none of the bundle's
    image left, every block unopenable by name.

This file is the pass's body and its verdict (:func:`verdict` is pure, and
is what ``Ortho4XP/tests/test_pool_selfcheck.py`` twins); the tool a job
runs is ``check_frozen_tile.py``.  Standard library only: the liveness and
block probes are the self-check module's own, loaded by file, never
re-spelled.  Nothing is written outside the pass's temp directory and the
log directory: the child's data root is a private empty folder.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

#: the five pooled sections of one core run, in the order they print
SECTIONS = ("spawn", "worker", "arrays", "object", "dem", "pack")
#: stderr text that fails the pass wherever it appears
POISON = ("FELL BACK", "leaked shared_memory", "Traceback (most recent call last)",
          "BrokenProcessPool", "UnicodeEncodeError")
#: seconds a finished run's processes may take to disappear
LINGER_S = 20.0


def _selfcheck_module(repo_root):
    """``O4_Pool_Selfcheck`` loaded BY FILE (its top level is standard
    library only) — for ``alive`` / ``block_exists`` / the verdict lines."""
    path = os.path.join(repo_root, "Ortho4XP", "src", "O4_Pool_Selfcheck.py")
    spec = importlib.util.spec_from_file_location("_o4_pool_selfcheck", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def selfcheck_argv(binary, engine_python=None):
    """``[<binary>, --pool-selfcheck]``, the interpreter in front of a
    SOURCE entry (the same rule as ``check_frozen_tile._engine_argv``)."""
    if binary.lower().endswith(".py"):
        return [engine_python or sys.executable, binary, "--pool-selfcheck"]
    return [binary, "--pool-selfcheck"]


def _pools_ok(pools, where, failures, want=SECTIONS):
    for name in want:
        row = (pools or {}).get(name)
        if not row:
            failures.append("%s: no account of the %s pool" % (where, name))
            continue
        if row.get("fell_back"):
            failures.append("%s: the %s pool FELL BACK (%s)"
                            % (where, name, row.get("reason")))
        elif row.get("workers", 0) < 2 or not row.get("parallel"):
            failures.append("%s: the %s pool ran SERIAL (workers %s, %s)"
                            % (where, name, row.get("workers"),
                               row.get("reason") or "not parallel"))
        elif not row.get("tasks"):
            failures.append("%s: the %s pool's workers answered 0 tasks"
                            % (where, name))


def verdict(pooled, serial, text="", frozen=True):
    """Every reason this pair of runs is not a proof; ``[]`` is a pass.

    ``pooled`` / ``serial`` are the two arms' ``--out`` records (``None``
    for an arm that wrote none), ``text`` everything either arm printed.
    """
    failures = []
    for marker in POISON:
        if marker in text:
            failures.append("the bundle printed %r" % marker)
    if not pooled:
        return failures + ["the pooled arm wrote no record (it crashed, hung "
                           "or does not know --pool-selfcheck)"]
    failures += ["pooled arm: %s" % f for f in pooled.get("failures", [])]
    if frozen and not pooled.get("frozen"):
        failures.append("the pooled arm did not run frozen (sys.frozen false)")
    if pooled.get("workers", 0) < 2:
        failures.append("the pooled arm ran with %s worker(s)"
                        % pooled.get("workers"))
    _pools_ok(pooled.get("pools"), "pooled arm", failures)
    if len(pooled.get("pids") or []) < 2:
        failures.append("fewer than two worker processes answered")
    nested = pooled.get("nested") or []
    if len(nested) != 2:
        failures.append("nested: %d of 2 airport-pool children answered"
                        % len(nested))
    for row in nested:
        where = "nested child %s" % row.get("pid")
        _pools_ok(row.get("pools"), where, failures)
        if len(row.get("pids") or []) < 2:
            failures.append("%s: fewer than two workers of its own" % where)
        if row.get("digest") != pooled.get("digest"):
            failures.append("%s: digest %s != %s" % (
                where, row.get("digest"), pooled.get("digest")))
        want = max(1, int(row.get("cpu") or 1) // 2)
        if row.get("budget") != want or row.get("daemon"):
            failures.append("%s: budget %s, want %s (set_share), daemon %s"
                            % (where, row.get("budget"), want, row.get("daemon")))
    kill = pooled.get("kill") or {}
    if len(kill.get("pids") or []) < 2 or len(kill.get("blocks") or []) < 2:
        failures.append("kill: the bundle did not hard-kill a pool over shared "
                        "blocks (%s)" % (kill or "no kill section"))
    elif kill.get("orphans") or kill.get("leaked_blocks"):
        failures.append("kill: after the bundle hard-killed a pool's parent: "
                        "orphans %s, blocks still openable %s"
                        % (kill.get("orphans"), kill.get("leaked_blocks")))
    if pooled.get("orphans") or pooled.get("leaked_blocks"):
        failures.append("the bundle's own teardown read: orphans %s, leaked "
                        "blocks %s" % (pooled.get("orphans"),
                                       pooled.get("leaked_blocks")))
    if not serial:
        failures.append("the one-core arm wrote no record")
    else:
        failures += ["one-core arm: %s" % f for f in serial.get("failures", [])]
        if serial.get("workers") != 1:
            failures.append("the one-core arm ran with %s workers"
                            % serial.get("workers"))
        if serial.get("digest") != pooled.get("digest"):
            failures.append("EQUALITY: pooled digest %s != one-core digest %s "
                            "(sections %s vs %s)" % (
                                pooled.get("digest"), serial.get("digest"),
                                pooled.get("sections"), serial.get("sections")))
    return failures


def _image_processes(binary):
    """``[(pid, command)]`` of every running process of ``binary``'s image
    (nothing for a SOURCE entry: an interpreter is not attributable)."""
    if binary.lower().endswith(".py"):
        return []
    try:
        if sys.platform == "win32":
            out = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH", "/FI",
                 "IMAGENAME eq %s" % os.path.basename(binary)],
                capture_output=True, text=True, timeout=30).stdout
            rows = [line.split('","') for line in out.splitlines() if '","' in line]
            return [(int(r[1]), r[0].strip('"')) for r in rows if r[1].isdigit()]
        out = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True,
                             text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    found = []
    for line in out.splitlines():
        pid, _sep, command = line.strip().partition(" ")
        if command.strip().startswith(binary) and pid.isdigit():
            found.append((int(pid), command.strip()[:120]))
    return found


def _launch(binary, work, data_root):
    """``(environment, cwd)`` every arm's process starts with."""
    environment = dict(os.environ)
    environment["ORTHO4XP_DATA_ROOT"] = data_root
    environment["PYTHONHASHSEED"] = "0"
    if not binary.lower().endswith(".py"):       # see check_frozen_tile._drive
        environment["PROJ_LIB"] = os.path.join(work, "nonexistent-proj")
        environment["PROJ_DATA"] = environment["PROJ_LIB"]
    # a SOURCE entry finds ``./src`` from its own directory (the entry file
    # only anchors itself for --engine-jsonl); a bundle runs anywhere
    cwd = (os.path.dirname(os.path.abspath(binary))
           if binary.lower().endswith(".py") else work)
    return environment, cwd


def _arm(binary, workers, work, log_dir, tag, deadline, engine_python, data_root):
    """Run one arm under ``deadline``.  ``(record | None, text, seconds,
    note)`` — ``note`` says how it ended when not by itself."""
    out_json = os.path.join(log_dir, "pool-selfcheck-%s.json" % tag)
    log = os.path.join(log_dir, "pool-selfcheck-%s.log" % tag)
    if os.path.exists(out_json):
        os.remove(out_json)
    argv = selfcheck_argv(binary, engine_python) + [
        "--work", work, "--out", out_json]
    if workers is not None:
        argv += ["--workers", str(workers)]
    environment, cwd = _launch(binary, work, data_root)
    print("   %s arm: %s" % (tag, " ".join(argv)))
    started, note = time.time(), ""
    with open(log, "wb") as sink:
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=sink,
                                 stderr=subprocess.STDOUT, cwd=cwd, env=environment)
        try:
            rc = child.wait(timeout=deadline)
            if rc != 0:
                note = "exit %s" % rc
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=30)
            note = "DEADLINE: still running after %d s (killed)" % deadline
    with open(log, "r", encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    record = None
    if os.path.isfile(out_json):
        with open(out_json, "r", encoding="utf-8") as handle:
            record = json.load(handle)
    return record, text, time.time() - started, note


def kill_verdict(record, alive, strays, leaked, wait_s):
    """Every reason the outside kill arm is not a proof (pure)."""
    if not record:
        return ["KILL ARM: the victim wrote no record (it crashed, hung or "
                "does not know --victim)"]
    failures = []
    if (record.get("pool") or {}).get("fell_back") or len(record.get("pids") or []) < 2 \
            or len(record.get("blocks") or []) < 2 or not record.get("manager"):
        failures.append("KILL ARM: what was killed was not an engine over an "
                        "airport child with a pool and shared blocks (%s)"
                        % {k: record.get(k) for k in ("pool", "pids", "blocks", "manager")})
    if alive:
        failures.append("KILL ARM ORPHAN: process(es) still alive %.0f s after "
                        "their engine was hard-killed: %s" % (wait_s, alive))
    if strays:
        failures.append("KILL ARM ORPHAN: process(es) of the bundle's image "
                        "still running: %s" % strays)
    if leaked:
        failures.append("KILL ARM LEAK: shared-memory block(s) still openable "
                        "by name: %s" % leaked)
    return failures


def _kill_arm(binary, probe, work, log_dir, deadline, engine_python, data_root,
              before, workers):
    """Start the bundle as ``--victim --chain``, hard-kill it mid-map and
    read what is left.  ``(failures, the line to print)``."""
    out_json = os.path.join(log_dir, "pool-selfcheck-victim.json")
    log = os.path.join(log_dir, "pool-selfcheck-victim.log")
    if os.path.exists(out_json):
        os.remove(out_json)
    argv = selfcheck_argv(binary, engine_python) + [
        "--victim", "--chain", "--out", out_json, "--workers", str(workers or 3)]
    environment, cwd = _launch(binary, work, data_root)
    print("   kill arm: %s" % " ".join(argv))
    record = None
    with open(log, "wb") as sink:
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=sink,
                                 stderr=subprocess.STDOUT, cwd=cwd, env=environment)
        end = time.time() + deadline
        while not os.path.isfile(out_json) and child.poll() is None and time.time() < end:
            time.sleep(0.1)
        if os.path.isfile(out_json):
            time.sleep(1.0)                    # the victim's second map is in flight
            with open(out_json, "r", encoding="utf-8") as handle:
                record = json.load(handle)
        busy = [p for p in (record or {}).get("pids", []) if probe.alive(p)]
        child.kill()                           # SIGKILL / TerminateProcess
        child.wait(timeout=30)
    killed = time.time()
    record = dict(record or {}, pids=busy) if record else None
    pids = set(busy) | {child.pid} | {(record or {}).get(k) for k in
                                      ("pid", "top", "manager", "tracker")}
    pids.discard(None)
    blocks = sorted((record or {}).get("blocks") or [])
    # the image a worker really is (an AppImage's AppRun is a launcher)
    image = binary if binary.lower().endswith(".py") else \
        (record or {}).get("executable") or binary
    while True:
        alive = sorted(p for p in pids if probe.alive(p))
        strays = [row for row in _image_processes(image) if row[0] not in before]
        leaked = [b for b in blocks if probe.block_exists(b)]
        if not (alive or strays or leaked) or time.time() > killed + probe.KILL_S:
            break
        time.sleep(0.25)
    waited = time.time() - killed
    failures = kill_verdict(record, alive, strays, leaked, probe.KILL_S)
    probe.put_down(alive + [row[0] for row in strays], leaked)
    return failures, (
        "   kill arm: engine pid %s hard-killed mid-map (Manager, 1 airport "
        "child, %d worker(s), %d shared block(s)) — after %.1f s: %d alive, "
        "%d of the image, %d block(s) openable"
        % (child.pid, len(busy), len(blocks), waited, len(alive), len(strays),
           len(leaked)))


def run_pool(binary, repo_root, log_dir, deadline=300, keep=False,
             engine_python=None, workers=None):
    """THE POOL PASS (module doc).  Returns the process exit status."""
    probe = _selfcheck_module(repo_root)
    os.makedirs(log_dir, exist_ok=True)
    root = tempfile.mkdtemp(prefix="o4_frozen_pool_")
    frozen = not binary.lower().endswith(".py")
    before = {pid for pid, _c in _image_processes(binary)}
    try:
        work, data_root = os.path.join(root, "work"), os.path.join(root, "data")
        os.makedirs(work)
        os.makedirs(data_root)
        pooled, text_p, wall_p, note_p = _arm(
            binary, workers, work, log_dir, "pooled", deadline, engine_python, data_root)
        serial, text_s, wall_s, note_s = _arm(
            binary, 1, work, log_dir, "onecore", deadline, engine_python, data_root)
        for line in text_p.splitlines():
            if "[pool]" in line or line.startswith(("nested:", "worker:", "kill:",
                                                    "POOL SELFCHECK", "FAILED")):
                print("   | " + line)
        failures = verdict(pooled, serial, text_p + text_s, frozen=frozen)
        failures += ["%s arm: %s" % (tag, note)
                     for tag, note in (("pooled", note_p), ("one-core", note_s)) if note]
        if "serial (budget 1)" not in text_s and serial:
            failures.append("the one-core arm did not say `serial (budget 1)`")
        # ---- (e) from OUTSIDE, after both processes have exited ----------
        pids, blocks = set(), set()
        for record in (pooled, serial):
            if record:
                pids.update([record.get("pid")] + list(record.get("pids") or []))
                blocks.update(record.get("blocks") or [])
        pids.discard(None)
        # the image a worker really is (an AppImage's AppRun is a launcher)
        image = (pooled or {}).get("executable") if frozen else binary
        image = image or binary
        end = time.time() + LINGER_S
        while True:
            alive = sorted(p for p in pids if probe.alive(p))
            strays = [row for row in _image_processes(image) if row[0] not in before]
            if not (alive or strays) or time.time() > end:
                break
            time.sleep(0.5)
        leaked = sorted(b for b in blocks if probe.block_exists(b))
        if alive:
            failures.append("ORPHAN: process(es) the run started are still "
                            "alive after it exited: %s" % alive)
        if strays:
            failures.append("ORPHAN: process(es) of the bundle's image are "
                            "still running: %s" % strays)
        if leaked:
            failures.append("LEAK: shared-memory block(s) still exist after "
                            "exit: %s" % leaked)
        # ---- (f) the whole bundle, hard-killed mid-map --------------------
        said, kill_line = _kill_arm(binary, probe, work, log_dir, deadline,
                                    engine_python, data_root, before, workers)
        failures += said
        print(kill_line)
        if pooled:
            print("   workers %s on %s core(s), python %s, %s, frozen=%s"
                  % (pooled.get("workers"), pooled.get("cpu"), pooled.get("python"),
                     pooled.get("platform"), pooled.get("frozen")))
            print("   processes started %d, shared blocks %d — after exit: "
                  "%d alive, %d of the image, %d block(s) left"
                  % (len(pids), len(blocks), len(alive), len(strays), len(leaked)))
            print("   digest pooled   %s" % pooled.get("digest"))
            print("   digest one-core %s" % (serial or {}).get("digest"))
        print("   wall: pooled %.1f s, one-core %.1f s" % (wall_p, wall_s))
        if failures:
            print("", file=sys.stderr)
            print("ERROR: the frozen bundle's WORK POOL is not proven",
                  file=sys.stderr)
            for item in failures:
                print("  - %s" % item, file=sys.stderr)
            for tag, text in (("pooled", text_p), ("one-core", text_s)):
                print("--- %s arm output (tail) ---" % tag, file=sys.stderr)
                print("\n".join(text.splitlines()[-40:]), file=sys.stderr)
            print("full logs: %s" % log_dir, file=sys.stderr)
            return 1
        print("POOL PASS OK: %s workers spawned from %s, shared memory read, "
              "nested under the airport pool, pooled == one-core, clean "
              "teardown, nothing outlives a hard-killed parent"
              % (pooled.get("workers"), os.path.basename(binary)))
        return 0
    finally:
        if keep:
            print("   (kept: %s)" % root)
        else:
            shutil.rmtree(root, ignore_errors=True)
