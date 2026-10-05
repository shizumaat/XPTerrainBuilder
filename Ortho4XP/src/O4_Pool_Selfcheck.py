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
  work pools of their own — PINNED to this run's worker count, so a pool
  inside an airport-pool child is proven whatever the machine's memory —
  and each child's share and budget read back: the share is the airport
  pool's size, and the budget is what ``budget_bound`` derives from it
  (``min(cores // share, the memory bound)``: 1, bound ``memory``, on a
  4-core / 16 GB runner — :func:`budget_for`);
* ``kill``    — THE PARENT IS HARD-KILLED MID-MAP: a child of this run
  (:func:`victim`) opens a pool whose workers hold the shared DEM and a
  shared array, and is killed while they work.  Within :data:`KILL_S` every
  worker must be gone and every block unopenable by name — while THIS
  process lives on, so the resource tracker they all share cleans nothing
  (the case of ``driver._teardown_pool`` terminating an airport child).
  ``--victim --chain`` is the same victim one level down, under an airport
  pool and its Manager, for a caller that kills the whole process from
  outside (``scripts/check_frozen_pool.py``: an engine cancel, an app quit);
* ``teardown`` — every process this run started is gone, every
  shared-memory block is unlinked, and this process has none still OPEN
  (``pool.attached``: on one core it reads its own blocks, and a Windows
  block lives until its last handle closes).

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
import signal
import sys
import time
from types import SimpleNamespace as _NS

__all__ = ["main", "run", "victim", "alive", "block_exists", "put_down", "budget_for",
           "OK_LINE", "FAILED_LINE", "KILL_S"]

#: the last stdout line of a run, by verdict
OK_LINE = "POOL SELFCHECK OK"
FAILED_LINE = "POOL SELFCHECK FAILED"
#: sibling airport builds the nested arm declares (the airport pool's size)
SIBLINGS = 2
#: seconds the nested airport pool may take, and the teardown may linger
NESTED_S = 240.0
LINGER_S = 15.0
#: seconds a hard-killed parent's workers and blocks may outlive it
KILL_S = 20.0
#: seconds one task of the victim's map holds its worker, the victim's map
#: lasts when nobody kills it, and its record may take to appear
HOLD_S = 0.25
VICTIM_S = 60.0
VICTIM_READY_S = 120.0
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


def _victim_setup(token: tuple) -> dict:
    """A victim worker's state: the shared DEM, held for the worker's life
    as a pack reader holds it (``reader_work.setup``)."""
    from auto_patch_v2.airport.dem_shared import revive
    return {"dem": revive(token)}


def _hold(state: dict, task: tuple) -> int:
    """One task of the map the victim is killed in: read the shared array
    and the shared DEM, then keep the worker busy."""
    from auto_patch_v2.airport.pool import attach
    spec, xs, ys = task
    float(attach(spec)["grid"][0, 0])
    state["dem"].z_many(xs, ys)
    time.sleep(HOLD_S)
    return os.getpid()


def _nested(task: tuple) -> dict:
    """ONE airport-pool child: what the pool budget reads here, then the
    whole core run in work pools of its own."""
    from auto_patch_v2.airport import pool as _pool
    workers, work = task
    got = _core(workers, work, say=lambda _s: None)
    budget, bound = _pool.budget_bound()
    got.update(budget=budget, bound=bound, share=_pool.share(), cpu=os.cpu_count() or 1,
               ram_gb=_pool.physical_ram_gb(), reserve_gb=_pool.PARENT_RESERVE_GB,
               allowance_gb=_pool.WORKER_ALLOWANCE_GB, pid=os.getpid(),
               daemon=bool(_mp.current_process().daemon))
    return got


def budget_for(row: dict) -> tuple:
    """``(workers, bound)`` the pool's law gives a process that shares the
    machine as ``row`` says (``share``, ``cpu``, ``ram_gb``, ``reserve_gb``,
    ``allowance_gb``) — ``pool.budget_bound``'s rule, re-derived from the
    recorded facts so the check does not ask the function it is checking.
    Standard library only (``scripts/check_frozen_pool.py`` calls it)."""
    share = max(1, int(row.get("share") or 1))
    by_cores = max(1, int(row.get("cpu") or 1) // share)
    if row.get("ram_gb") is not None:
        by_memory = max(1, int((row["ram_gb"] / share - row["reserve_gb"])
                               // row["allowance_gb"]))
        if by_memory < by_cores:
            return by_memory, "memory"
    return by_cores, "share" if share > 1 else "cores"


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
    from auto_patch_v2.airport import frame_entry as _fe
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
    # the build's own cache (``pipeline/build.pack_stage``): the §51 (6) quantum
    cache = O.ResourceCache(law.tables.structures.basin.min_solid_thickness_m,
                            _fe.quantum(law))
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


def _dem(rng) -> tuple:
    """``(a one-tile DEM, xs, ys)``: what the ``dem`` section and the
    victim's workers sample."""
    from auto_patch_v2.airport.dem_production import _BakedTile
    from auto_patch_v2.airport.dem_shared import WarmDem
    from auto_patch_v2.model.frame import Frame
    dem = WarmDem(Frame("ZZZZ", (60.5, -134.5), 11), "ZZZZ", {(60, -135): _BakedTile(
        60, -135, 100.0 + 50.0 * rng.random((301, 301)), 0.0, 1.0, 0.0, 1.0)})
    return dem, rng.uniform(-3000, 3000, 500), rng.uniform(-3000, 3000, 500)


def _core(workers: int, work: str, say=print) -> dict:
    """Every section through pools of ``workers`` (1 = on one core).
    ``{"digest", "sections", "pids", "blocks", "pools", "failures"}``."""
    import numpy as np
    from auto_patch_v2.airport import pool as P
    from auto_patch_v2.airport import dem_shared as DS

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
            # a worker with NO stdout (a windowed bundle's child) prints
            # nothing and raises nothing: only a stream that exists is held
            # to this process's pinned text layer
            if r["stdout"][0] and here["stdout"][0] and r["stdout"] != here["stdout"]:
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
    dem, xs, ys = _dem(rng)
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
    # on one core THIS process attached to its own blocks: every one must be
    # closed by now (a Windows block lives until its last handle closes)
    if P.attached():
        failures.append(f"teardown: this process still has shared block(s) open "
                        f"after their owner closed them: {P.attached()}")
    return {"digest": _sha(json.dumps(sections, sort_keys=True).encode()),
            "sections": sections, "worker": theirs[0], "here": here, "pids": sorted(pids), "blocks": blocks,
            "pools": pools, "failures": failures}


def _nested_arm(workers: int, work: str) -> list:
    """The tile driver's airport pool, built as ``driver.py`` builds it,
    each child running :func:`_core`.  One result per child."""
    from auto_patch import driver as _driver
    ctx = _mp.get_context("spawn")
    mgr = _driver._start_manager(ctx)
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


# ── the parent, hard-killed mid-map ──────────────────────────────────────

def _victim_body(workers: int, out: str, above: dict | None = None) -> None:
    """THE PROCESS THE KILL ARM KILLS: a pool whose workers hold the shared
    DEM (their state) and a shared array (their task).  Once every worker
    has answered it writes ``{pid, pids, blocks, tracker, …above}`` to
    ``out`` and maps for :data:`VICTIM_S` more — the kill lands in there.
    Left alone it closes everything and returns."""
    import numpy as np
    from multiprocessing import resource_tracker as _rt
    from auto_patch_v2.airport import pool as P
    from auto_patch_v2.airport import dem_shared as DS
    P.configure(None)
    rng = np.random.default_rng(362)
    dem, xs, ys = _dem(rng)
    shared_dem, token = DS.share(dem)
    with P.SharedArrays({"grid": rng.random((257, 129))}) as sa, \
            P.WorkPool(_victim_setup, (token,), workers=workers) as pool:
        try:
            task = (sa.spec, xs, ys)
            answered = pool.try_map(_hold, [task] * (4 * workers), what="victim")
            record = {"pid": os.getpid(), "pids": pool.pids(), "executable": sys.executable,
                      "answered": sorted(set(answered or [])), "pool": pool.report(),
                      "blocks": [v[0] for spec in (sa.spec, shared_dem.spec)
                                 for v in spec.values()],
                      "tracker": getattr(_rt._resource_tracker, "_pid", None)}
            record.update(above or {})
            with open(out + ".part", "w", encoding="utf-8", newline="") as handle:
                json.dump(record, handle)
            os.replace(out + ".part", out)
            pool.try_map(_hold, [task] * (workers * int(VICTIM_S / HOLD_S)), what="victim")
        finally:
            shared_dem.close()


def victim(workers: int, out: str, chain: bool = False) -> None:
    """:func:`_victim_body` in this process — or, with ``chain``, in the
    one child of an airport pool built as ``driver.py`` builds it (its
    Manager beside it), so that killing THIS process is killing an engine
    mid-build."""
    if not chain:
        return _victim_body(workers, out)
    from multiprocessing import resource_tracker as _rt
    from auto_patch import driver as _driver
    ctx = _mp.get_context("spawn")
    mgr = _driver._start_manager(ctx)
    try:
        ex = _cf.ProcessPoolExecutor(
            max_workers=1, mp_context=ctx, initializer=_driver._init_worker,
            initargs=(None, mgr.Queue(), 1))
        above = {"top": os.getpid(), "manager": mgr._process.pid,
                 "tracker": getattr(_rt._resource_tracker, "_pid", None)}
        fut = ex.submit(_victim_body, workers, out, above)
        done, pending = _cf.wait([fut], timeout=VICTIM_READY_S + VICTIM_S)
        _driver._teardown_pool(ex, [], {}, pending, deadline_s=10.0)
    finally:
        mgr.shutdown()


def put_down(pids, blocks) -> None:
    """Best effort: kill ``pids`` and unlink ``blocks`` — what a FAILED
    kill arm found, so the check does not itself leave orphans behind."""
    from multiprocessing import shared_memory
    for pid in pids:
        try:
            os.kill(int(pid), getattr(signal, "SIGKILL", signal.SIGTERM))
        except OSError:
            pass
    for name in blocks:
        try:
            try:
                blk = shared_memory.SharedMemory(name=name, track=False)
            except TypeError:              # an interpreter before 3.13
                blk = shared_memory.SharedMemory(name=name)
            blk.close()
            blk.unlink()
        except OSError:
            pass


def _kill_arm(workers: int, work: str, say) -> tuple:
    """``(the section's record, its failures)``: start :func:`victim` as a
    child of THIS process, hard-kill it mid-map, and read what is left."""
    out = os.path.join(work, "victim.json")
    if os.path.exists(out):
        os.remove(out)
    proc = _mp.get_context("spawn").Process(target=victim, args=(workers, out))
    proc.start()
    end = time.monotonic() + VICTIM_READY_S
    while not os.path.exists(out) and proc.is_alive() and time.monotonic() < end:
        time.sleep(0.1)
    if not os.path.exists(out):
        proc.kill()
        proc.join(10.0)
        return {}, ["kill: the victim wrote no record (it died or never started)"]
    with open(out, encoding="utf-8") as handle:
        record = json.load(handle)
    time.sleep(4 * HOLD_S)                 # the second map is in flight
    busy = [p for p in record["pids"] if alive(p)]
    proc.kill()
    proc.join(10.0)
    t0 = time.monotonic()
    orphans, leaked = _linger(record["pids"], record["blocks"], KILL_S)
    record.update(busy=len(busy), orphans=orphans, leaked_blocks=leaked,
                  gone_s=round(time.monotonic() - t0, 2))
    failures = []
    if record["pool"]["fell_back"] or len(busy) < 2 or len(record["blocks"]) < 2:
        failures.append(f"kill: the victim was not a pool over shared blocks when "
                        f"it was killed ({record['pool']}, {len(busy)} worker(s) "
                        f"alive, {len(record['blocks'])} block(s))")
    if orphans:
        failures.append(f"kill: worker(s) outlived their hard-killed parent by "
                        f"{KILL_S:.0f} s: {orphans}")
    if leaked:
        failures.append(f"kill: shared-memory block(s) still openable {KILL_S:.0f} s "
                        f"after their owner was hard-killed: {leaked}")
    put_down(orphans, leaked)
    say(f"kill: parent {record['pid']} hard-killed mid-map with {len(busy)} worker(s) "
        f"and {len(record['blocks'])} shared block(s): after {record['gone_s']:.1f} s "
        f"{len(orphans)} worker(s) alive, {len(leaked)} block(s) openable")
    return record, failures


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


def _linger(pids, blocks, wait_s: float = LINGER_S) -> tuple:
    """``(pids still alive, blocks still openable)`` once both are empty or
    ``wait_s`` has passed."""
    end = time.monotonic() + wait_s
    while True:
        left, there = [p for p in pids if alive(p)], [b for b in blocks if block_exists(b)]
        if not (left or there) or time.monotonic() > end:
            return left, there
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
        want = budget_for(r)
        ram = "?" if r["ram_gb"] is None else f"{r['ram_gb']:.0f}"
        say(f"nested: airport-pool child {r['pid']} share {r['share']}, budget "
            f"{r['budget']} (bound: {r['bound']}; cores {r['cpu']}, {ram} GB), "
            f"{len(r['pids'])} worker(s) of its own in pools pinned to {workers}, "
            f"digest {r['digest'][:12]}")
        failures += [f"nested {r['pid']}: {f}" for f in r["failures"]]
        if r["digest"] != record["digest"]:
            failures.append(f"nested {r['pid']}: digest {r['digest'][:12]} != "
                            f"{record['digest'][:12]}")
        if workers > 1 and (r["share"] != SIBLINGS or r["daemon"]):
            failures.append(f"nested {r['pid']}: share {r['share']} (want {SIBLINGS}), "
                            f"daemon {r['daemon']} — set_share did not apply")
        if workers > 1 and (r["budget"], r["bound"]) != want:
            failures.append(f"nested {r['pid']}: budget {r['budget']} (bound "
                            f"{r['bound']}), want {want[0]} (bound {want[1]}) for "
                            f"share {r['share']}, cores {r['cpu']}, {ram} GB")
    if len(nested) != SIBLINGS and not any(f.startswith("nested:") for f in failures):
        failures.append(f"nested: {len(nested)} of {SIBLINGS} children answered")
    killed: dict = {}
    if workers > 1:                        # one core has no worker to orphan
        killed, said = _kill_arm(workers, work, say)
        failures += said
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
            "nested": [{k: r[k] for k in ("pid", "budget", "bound", "share", "cpu",
                                          "ram_gb", "reserve_gb", "allowance_gb",
                                          "daemon", "digest", "pids", "pools")}
                       for r in nested],
            "orphans": orphans, "leaked_blocks": leaked, "kill": killed,
            "wall_s": round(time.perf_counter() - t0, 3)}


def main(argv: list[str]) -> int:
    """``--pool-selfcheck [--workers N] [--work DIR] [--out FILE]``: exit 0
    when the work pool answers in this interpreter (module doc).
    ``--workers`` defaults to ``max(2, min(4, cores))``.  ``--victim
    [--chain] --out FILE`` is :func:`victim` instead: the process a caller
    kills."""
    def value(flag: str, default: str) -> str:
        return argv[argv.index(flag) + 1] if flag in argv else default
    import tempfile
    # PINNED, never the derived budget: a small machine's budget of 1 must
    # not turn the pooled arm into a serial one (the pass fails on < 2)
    workers = int(value("--workers", str(max(2, min(4, os.cpu_count() or 2)))))
    if "--victim" in argv:
        victim(max(2, workers), value("--out", ""), chain="--chain" in argv)
        return 0
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
        with open(value("--out", ""), "w", encoding="utf-8", newline="") as handle:
            json.dump(record, handle, indent=1, sort_keys=True)
    if record["ok"]:
        print(f"{OK_LINE}: workers {record['workers']}, {len(record['pids'])} "
              f"process(es), digest {record['digest']}, {record['wall_s']:.1f} s")
    else:
        print(FAILED_LINE)
    return 0 if record["ok"] else 1
