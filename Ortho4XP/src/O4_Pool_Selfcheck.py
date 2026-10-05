"""THE WORK POOL'S SELF-CHECK — ``<engine> --pool-selfcheck`` (issue #362;
owner RULINGS 2026-10-05d (2): the pool is proven in the FROZEN engine on
macOS, Windows and Linux before the parallel branch lands).

The frozen CYXY fixture has no pack, so no work pool ever starts there.
This entry makes the binary it runs in drive the pool directly, through the
engine's own modules and nothing else, and says what happened:

* ``spawn``   — a :class:`WorkPool` whose workers are this executable
  re-entered (``multiprocessing.freeze_support`` in the entry file): every
  task answered by a worker, at least two distinct worker processes;
* ``arrays`` / ``object`` / ``dem`` — ``SharedArrays`` + ``attach``,
  ``share_object`` + ``shared_object`` and the shared DEM
  (``dem_shared.share`` / ``revive``) read in the workers;
* ``pack``    — a REAL stage: ``pack_partition.partition_pack`` over a small
  synthetic pack through ``pack_work.open_pool`` (the workers load the law
  tables and parse ``.obj`` files themselves);
* ``worker``  — what a worker process IS: a frozen worker is diverted by
  ``freeze_support`` before the entry file's body runs, so it has to be
  shown — not assumed — that it can print the house characters (``Δ``,
  ``→``: an exception, not mojibake, on a cp1252 console), that its
  stdout carries this process's pinned text layer, and that its ``pyproj``
  reads the PROJ data this process's does;
* ``nested``  — the tile driver's airport pool (a spawned
  ``ProcessPoolExecutor`` with ``auto_patch.driver._init_worker`` and a
  ``Manager`` queue, as ``driver.py`` builds it) whose children each open
  work pools of their own, with ``set_share`` applied;
* ``teardown`` — every process this run started is gone and every
  shared-memory block is unlinked.

Every section is computed twice — by workers and on one core — and the two
digests must be equal; ``--workers 1`` pins the whole run to one core, and
its digest is the one a pooled run of the same binary must print.  The
verdict a release job reads is ``scripts/check_frozen_tile.py --pass pool``
(it runs both arms, compares them and re-checks the teardown from outside
after the process has exited).  Twin: ``tests/test_pool_selfcheck.py``.
"""
from __future__ import annotations

import concurrent.futures as _cf
import hashlib
import json
import multiprocessing as _mp
import os
import pickle
import sys
import time
from types import SimpleNamespace as _NS

__all__ = ["main", "run", "alive", "block_exists", "OK_LINE", "FAILED_LINE"]

#: the last stdout line of a run, by verdict
OK_LINE = "POOL SELFCHECK OK"
FAILED_LINE = "POOL SELFCHECK FAILED"
#: sibling airport builds the nested arm declares (the airport pool's size)
SIBLINGS = 2
#: seconds the nested airport pool may take, and the teardown may linger
NESTED_S = 240.0
LINGER_S = 15.0
_TASKS = 48
#: what every worker prints: characters cp1252 does not carry (#171, #125)
CONSOLE_PROBE = "pool-selfcheck worker console: Δ ε ≥ → Suárez"


# ── what the workers run (module level: a spawned worker imports them) ────

def _setup(base: int) -> dict:
    return {"base": base}


def _square(state: dict, t: int) -> tuple:
    time.sleep(0.1)       # one worker cannot take them all while the rest boot
    return t * t + state["base"], os.getpid()


def reading() -> dict:
    """What THIS process is, for the ``worker`` section: its stdout's text
    layer, whether it can print :data:`CONSOLE_PROBE`, and the PROJ data
    directory its ``pyproj`` reads."""
    said = ""
    try:
        print(CONSOLE_PROBE, flush=True)
    except Exception as e:
        said = f"{type(e).__name__}: {e}"
    try:
        import pyproj
        data = os.path.normcase(os.path.realpath(pyproj.datadir.get_data_dir()))
        pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32608", always_xy=True
                                    ).transform(-135.0, 60.0)
    except Exception as e:
        data = f"{type(e).__name__}: {e}"
    return {"pid": os.getpid(), "print_error": said, "proj_data": data,
            "stdout": [getattr(sys.stdout, "encoding", None),
                       getattr(sys.stdout, "errors", None)]}


def _worker_reading(_state, _t) -> tuple:
    return reading(), os.getpid()


def _read_arrays(_state, spec) -> tuple:
    from auto_patch_v2.airport.pool import attach
    got = attach(spec)
    return (sorted((k, hashlib.sha256(v.tobytes()).hexdigest(), bool(v.flags.writeable))
                   for k, v in got.items()), os.getpid())


def _read_object(_state, spec) -> tuple:
    from auto_patch_v2.airport.pool import shared_object
    return _sha(pickle.dumps(shared_object(spec), protocol=4)), os.getpid()


def _read_dem(_state, task) -> tuple:
    from auto_patch_v2.airport.dem_shared import revive
    token, xs, ys = task
    return _sha(revive(token).z_many(xs, ys).tobytes()), os.getpid()


def _nested(task: tuple) -> dict:
    """ONE airport-pool child: what the pool budget reads here, then the
    whole core run in work pools of its own."""
    from auto_patch_v2.airport import pool as _pool
    workers, work = task
    got = _core(workers, work, say=lambda _s: None)
    got.update(budget=_pool.budget(), cpu=os.cpu_count() or 1, pid=os.getpid(),
               daemon=bool(_mp.current_process().daemon))
    return got


# ── the sections ─────────────────────────────────────────────────────────

def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _box(x, z, w, d, h, y0=0.0) -> list:
    x1, z1, y1 = x + w, z + d, y0 + h
    v = [(x, y0, z), (x1, y0, z), (x1, y0, z1), (x, y0, z1),
         (x, y1, z), (x1, y1, z), (x1, y1, z1), (x, y1, z1)]
    faces = [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
             (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]
    return [(v[a], v[b], v[c]) for a, b, c in faces]


def write_pack(root: str) -> None:
    """The synthetic pack: a basement building, a neighbour touching it, a
    bush field, a deck on piers and twelve small sheds."""
    def obj(name: str, comps: list) -> None:
        verts = [p for comp in comps for tri in comp for p in tri]
        rows = ["A", "800", "OBJ", "", f"POINT_COUNTS {len(verts)} 0 0 {len(verts)}"]
        rows += [f"VT {a:.4f} {b:.4f} {c:.4f} 0 1 0 0 0" for a, b, c in verts]
        rows += [f"IDX {i}" for i in range(len(verts))] + [f"TRIS 0 {len(verts)}"]
        with open(os.path.join(root, name), "w", encoding="utf-8", newline="") as f:
            f.write("\n".join(rows) + "\n")
    os.makedirs(os.path.join(root, "Earth nav data"), exist_ok=True)
    with open(os.path.join(root, "Earth nav data", "apt.dat"), "w",
              encoding="utf-8", newline="") as f:
        f.write("I\n1100\n")
    obj("basement.obj", [_box(0, 0, 30, 20, 10, y0=-3.0), _box(5, 5, 4, 4, 14)])
    obj("neighbour.obj", [_box(0, 0, 12, 20, 8)])
    obj("bushes.obj", [_box(3.0 * i, 0.0, 0.5, 0.5, 1.0, y0=-0.2) for i in range(80)])
    obj("deck.obj", [_box(0, 0, 60, 12, 0.8, y0=7.0)]
        + [_box(x, 5, 1.5, 1.5, 7.0) for x in (2, 20, 38, 56)])
    for k in range(12):
        obj(f"shed{k:02d}.obj", [_box(0, 0, 4 + k, 5, 3 + 0.25 * k)])


def _pack(workers: int, root: str, say) -> tuple:
    """``(digest, the pool's report)`` of the pack
    partition of :func:`write_pack`'s pack."""
    import dataclasses as _dc
    import numpy as np
    from auto_patch_v2.airport import obj8 as O
    from auto_patch_v2.airport import pack_partition as PP
    from auto_patch_v2.airport import pack_work as W
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.frame import Frame

    def placed(k: int, name: str, xy, heading: float = 0.0):
        return O.PlacedObject(
            id=f"dsf:obj{k}", path=name, resolved=os.path.join(root, name), xy=xy,
            heading_deg=heading, agl_m=0.0, kind="OBJECT", anchor_z=100.0,
            below_grade=None, plan_bbox=None, solid_min_z=None,
            solid_min_depth_m=None, hard_deck=None, deck_top_z=None)
    law = Law.for_airport("")
    names = [("basement.obj", (0.0, 0.0), 10.0), ("neighbour.obj", (30.02, 0.0), 10.0),
             ("bushes.obj", (-200.0, 80.0), 33.0), ("deck.obj", (100.0, 40.0), 70.0)]
    names += [(f"shed{k:02d}.obj", (300.0 + 40.0 * k, -60.0), 7.0 * k) for k in range(12)]
    objs = [placed(k, *row) for k, row in enumerate(names)]
    pack = _NS(name="pack", apt_dat_path=os.path.join(root, "Earth nav data", "apt.dat"))
    air = _NS(icao="ZZZZ", frame=Frame("ZZZZ", (60.0, -135.0), 11), pack=pack)
    cache = O.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    with W.open_pool(law, cache, workers=workers, out=say) as pool:
        part = PP.partition_pack(air, objs, cache, law, pool=pool)
        say(pool.line())
        report = pool.report()
    g = part.geom
    digest = _sha(pickle.dumps(
        (repr(part.units).replace(repr(root)[1:-1], "<pack>").replace(root, "<pack>"), sorted(part.counts.items()),
         part.contacts, part.abutments, sorted(part.member_object.items()),
         g.member_ref, g.anchor_of_member, sorted(g.anchor_ix.items()),
         [np.asarray(getattr(g.index, f.name)).tobytes() for f in _dc.fields(g.index)]),
        protocol=4))
    return digest, report


def _core(workers: int, work: str, say=print) -> dict:
    """Every section through pools of ``workers`` (1 = on one core).
    ``{"digest", "sections", "pids", "blocks", "pools", "failures"}``."""
    import numpy as np
    from auto_patch_v2.airport import pool as P
    from auto_patch_v2.airport import dem_shared as DS
    from auto_patch_v2.airport.dem_production import _BakedTile
    from auto_patch_v2.model.frame import Frame

    sections: dict = {}
    pids: set = set()
    blocks: list = []
    pools: dict = {}
    failures: list = []

    def answers(name: str, pool, got: list, want_tasks: int) -> list:
        pids.update(pid for _v, pid in got if pid != os.getpid())
        pools[name] = pool.report()
        say(f"{name}: {pool.line()}")
        if workers > 1 and (pool.fell_back or pool.tasks_done != want_tasks):
            failures.append(f"{name}: {pool.line()}")
        return [v for v, _pid in got]

    with P.WorkPool(_setup, (7,), workers=workers, out=say) as pool:
        got = pool.map(_square, list(range(_TASKS)), {"base": 7}, what="selfcheck")
        sections["spawn"] = _sha(repr(answers("spawn", pool, got, _TASKS)).encode())
        together = len({pid for _v, pid in got})
        if workers > 1 and together < 2:
            failures.append(f"spawn: {together} worker process answered all "
                            f"{_TASKS} tasks of one pool")
        here = reading()
        got = pool.map(_worker_reading, list(range(2 * max(2, workers))), None)
        theirs = answers("worker", pool, got, _TASKS + len(got))
        for r in theirs if workers > 1 else []:
            if r["print_error"]:
                failures.append(f"worker {r['pid']}: cannot print the house "
                                f"characters ({r['print_error']}; stdout {r['stdout']})")
            if r["stdout"] != here["stdout"]:
                failures.append(f"worker {r['pid']}: its console is not pinned "
                                f"(stdout {r['stdout']}, this process {here['stdout']})")
            if r["proj_data"] != here["proj_data"]:
                failures.append(f"worker {r['pid']}: pyproj reads {r['proj_data']}, "
                                f"this process reads {here['proj_data']}")
        say(f"worker: stdout {theirs[0]['stdout']} (here {here['stdout']}), pyproj data "
            f"{theirs[0]['proj_data']}")

    rng = np.random.default_rng(362)
    arrays = {"grid": rng.random((257, 129)), "ids": np.arange(4096, dtype=np.int32)}
    thing = {"rows": [(k, float(k) / 7.0, f"row{k}") for k in range(2000)], "k": (1, 2)}
    frame = Frame("ZZZZ", (60.5, -134.5), 11)
    dem = DS.WarmDem(frame, "ZZZZ", {(60, -135): _BakedTile(
        60, -135, 100.0 + 50.0 * rng.random((301, 301)), 0.0, 1.0, 0.0, 1.0)})
    xs, ys = rng.uniform(-3000, 3000, 500), rng.uniform(-3000, 3000, 500)
    with P.WorkPool(workers=workers, out=say) as pool, P.SharedArrays(arrays) as sa, \
            P.share_object(thing) as so:
        shared_dem, token = DS.share(dem)
        try:
            blocks += [v[0] for spec in (sa.spec, so.spec, shared_dem.spec)
                       for v in spec.values()]
            n = max(2, workers) * 2
            got = pool.map(_read_arrays, [sa.spec] * n, None)
            rows = answers("arrays", pool, got, n)
            sections["arrays"] = _sha(repr(rows[0]).encode())
            if len({repr(r) for r in rows}) != 1 or any(w for _k, _h, w in rows[0]):
                failures.append("arrays: the workers did not all read the same "
                                "read-only arrays")
            got = pool.map(_read_object, [so.spec] * n, None)
            rows = answers("object", pool, got, 2 * n)
            sections["object"] = rows[0] if len(set(rows)) == 1 else "DIFFER"
            got = pool.map(_read_dem, [(token, xs, ys)] * n, None)
            rows = answers("dem", pool, got, 3 * n)
            sections["dem"] = rows[0] if len(set(rows)) == 1 else "DIFFER"
            if rows[0] != _sha(dem.z_many(xs, ys).tobytes()):
                failures.append("dem: a worker's shared DEM sampled differently")
        finally:
            shared_dem.close()

    sections["pack"], pools["pack"] = _pack(workers, os.path.join(work, "pack"),
                                            lambda s: say(f"pack: {s}"))
    if workers > 1 and (pools["pack"]["fell_back"] or not pools["pack"]["tasks"]):
        failures.append(f"pack: the pack stage did not pool ({pools['pack']})")
    return {"digest": _sha(json.dumps(sections, sort_keys=True).encode()),
            "sections": sections, "worker": theirs[0], "here": here, "pids": sorted(pids), "blocks": blocks,
            "pools": pools, "failures": failures}


def _nested_arm(workers: int, work: str) -> list:
    """The tile driver's airport pool, built as ``driver.py`` builds it,
    each child running :func:`_core`.  One result per child."""
    from auto_patch import driver as _driver
    ctx = _mp.get_context("spawn")
    mgr = ctx.Manager()
    try:
        ex = _cf.ProcessPoolExecutor(
            max_workers=SIBLINGS, mp_context=ctx, initializer=_driver._init_worker,
            initargs=(None, mgr.Queue(), SIBLINGS))
        futs = {ex.submit(_nested, (workers, work)): str(k) for k in range(SIBLINGS)}
        done, pending = _cf.wait(futs, timeout=NESTED_S)
        results = [f.result() for f in done]
        _driver._teardown_pool(ex, results, futs, pending, deadline_s=10.0)
        if pending:
            raise TimeoutError(f"{len(pending)} airport-pool child(ren) did not "
                               f"answer in {NESTED_S:.0f} s")
        return results
    finally:
        mgr.shutdown()


# ── the teardown, read from outside the pools ────────────────────────────

def alive(pid: int) -> bool:
    """Is process ``pid`` still running?"""
    if sys.platform == "win32":
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = ctypes.c_void_p
        k32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        k32.CloseHandle.argtypes = (ctypes.c_void_p,)
        handle = k32.OpenProcess(0x00100000, False, int(pid))     # SYNCHRONIZE
        if not handle:
            return False
        try:
            return k32.WaitForSingleObject(handle, 0) == 0x102      # WAIT_TIMEOUT
        finally:
            k32.CloseHandle(handle)
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def block_exists(name: str) -> bool:
    """Does shared-memory block ``name`` still exist?"""
    from multiprocessing import shared_memory
    try:
        try:
            blk = shared_memory.SharedMemory(name=name, track=False)
        except TypeError:                  # an interpreter before 3.13
            blk = shared_memory.SharedMemory(name=name)
    except (FileNotFoundError, OSError):
        return False
    blk.close()
    return True


def _linger(pids, blocks) -> tuple:
    end = time.monotonic() + LINGER_S
    while True:
        left = [p for p in pids if alive(p)]
        if not left or time.monotonic() > end:
            return left, [b for b in blocks if block_exists(b)]
        time.sleep(0.25)


def run(workers: int, work: str, say=print) -> dict:
    """The whole self-check; the returned record is what ``--out`` writes."""
    from auto_patch_v2.airport import pool as P
    t0 = time.perf_counter()
    P.configure(workers if workers == 1 else None)
    write_pack(os.path.join(work, "pack"))
    record = _core(workers, work, say)
    failures = list(record["failures"])
    serial = record if workers == 1 else _core(1, work, lambda _s: None)
    if serial["digest"] != record["digest"]:
        failures.append(f"equality: pooled {record['sections']} != one core "
                        f"{serial['sections']}")
    nested, pids, blocks = [], set(record["pids"]), list(record["blocks"])
    try:
        nested = _nested_arm(workers, work)
    except Exception as e:
        failures.append(f"nested: {type(e).__name__}: {e}")
    for r in nested:
        pids.update([r["pid"], *r["pids"]])
        blocks += r["blocks"]
        want = max(1, r["cpu"] // SIBLINGS)
        say(f"nested: airport-pool child {r['pid']} budget {r['budget']} "
            f"(cores {r['cpu']} // {SIBLINGS} siblings), {len(r['pids'])} worker(s) "
            f"of its own, digest {r['digest'][:12]}")
        failures += [f"nested {r['pid']}: {f}" for f in r["failures"]]
        if r["digest"] != record["digest"]:
            failures.append(f"nested {r['pid']}: digest {r['digest'][:12]} != "
                            f"{record['digest'][:12]}")
        if workers > 1 and (r["budget"] != want or r["daemon"]):
            failures.append(f"nested {r['pid']}: budget {r['budget']} (want {want}), "
                            f"daemon {r['daemon']} — set_share did not apply")
    if len(nested) != SIBLINGS and not any(f.startswith("nested:") for f in failures):
        failures.append(f"nested: {len(nested)} of {SIBLINGS} children answered")
    orphans, leaked = _linger(sorted(pids), blocks)
    if orphans:
        failures.append(f"teardown: process(es) still alive: {orphans}")
    if leaked:
        failures.append(f"teardown: shared-memory block(s) not unlinked: {leaked}")
    return {"ok": not failures, "failures": failures, "workers": workers,
            "cpu": os.cpu_count() or 1, "frozen": bool(getattr(sys, "frozen", False)),
            "python": sys.version.split()[0], "platform": sys.platform,
            "executable": sys.executable, "pid": os.getpid(),
            "digest": record["digest"], "sections": record["sections"],
            "pools": record["pools"], "pids": sorted(pids), "blocks": blocks,
            "worker": record["worker"], "here": record["here"],
            "nested": [{k: r[k] for k in ("pid", "budget", "cpu", "daemon", "digest",
                                          "pids", "pools")} for r in nested],
            "orphans": orphans, "leaked_blocks": leaked,
            "wall_s": round(time.perf_counter() - t0, 3)}


def main(argv: list[str]) -> int:
    """``--pool-selfcheck [--workers N] [--work DIR] [--out FILE]``: exit 0
    when the work pool answers in this interpreter (module doc).
    ``--workers`` defaults to ``max(2, min(4, cores))``."""
    def value(flag: str, default: str) -> str:
        return argv[argv.index(flag) + 1] if flag in argv else default
    import tempfile
    workers = int(value("--workers", str(max(2, min(4, os.cpu_count() or 2)))))
    made = None if "--work" in argv else tempfile.mkdtemp(prefix="o4_pool_selfcheck_")
    work = value("--work", made or "")
    lines: list[str] = []

    def say(line: str) -> None:
        lines.append(line)
        print(line, flush=True)
    try:
        record = run(workers, work, say)
    except Exception as e:                 # the check itself broke: say why
        import traceback
        traceback.print_exc()
        record = {"ok": False, "failures": [f"{type(e).__name__}: {e}"],
                  "workers": workers}
    finally:
        if made:
            import shutil
            shutil.rmtree(made, ignore_errors=True)
    record["lines"] = lines
    for f in record["failures"]:
        print(f"FAILED {f}", flush=True)
    if "--out" in argv:
        with open(value("--out", ""), "w", encoding="utf-8") as handle:
            json.dump(record, handle, indent=1, sort_keys=True)
    if record["ok"]:
        print(f"{OK_LINE}: workers {record['workers']}, {len(record['pids'])} "
              f"process(es), digest {record['digest']}, {record['wall_s']:.1f} s")
    else:
        print(FAILED_LINE)
    return 0 if record["ok"] else 1
