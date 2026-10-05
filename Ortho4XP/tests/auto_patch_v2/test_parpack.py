"""THE POOLED PACK PARTITION IS THE SERIAL ONE (issue #362, lane ``parpack``;
``airport/pack_work.py``).

A synthetic pack — a basement building, a neighbour touching it, a bush
field (scatter), a fence (line object), a deck on piers, a thin panel and
a resource placed twice — is partitioned serially and through a work pool
of 2, 3 and N workers.  Bar: the partition, the stored resource readings
and the member loop's ``counts`` / ``skipped`` are EQUAL, and each pooled
block equals its serial derivation on its own.
"""
from __future__ import annotations

import dataclasses as _dc
import os
import pickle
from pathlib import Path
from types import SimpleNamespace as NS

import numpy as np
import pytest

from auto_patch_v2.airport import contact as C
from auto_patch_v2.airport import deck_signature as D
from auto_patch_v2.airport import obj8 as O
from auto_patch_v2.airport import pack_partition as PP
from auto_patch_v2.airport import pack_work as W
from auto_patch_v2.airport import skirt as S
from auto_patch_v2.law import Law
from auto_patch_v2.model.frame import Frame

from test_v2packscatter import _box, _sheet, _write_obj

LAW = Law.for_airport("")
THICK = LAW.tables.structures.basin.min_solid_thickness_m
N = max(2, min(8, os.cpu_count() or 2))


def _placement(root: Path, oid: str, name: str, xy, heading: float = 0.0):
    return O.PlacedObject(id=oid, path=name, resolved=str(root / name), xy=xy,
                          heading_deg=heading, agl_m=0.0, kind="OBJECT", anchor_z=100.0,
                          below_grade=None, plan_bbox=None, solid_min_z=None,
                          solid_min_depth_m=None, hard_deck=None, deck_top_z=None)


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    root = tmp_path_factory.mktemp("parpack") / "pack"
    (root / "Earth nav data").mkdir(parents=True)
    (root / "Earth nav data" / "apt.dat").write_text("I\n1100\n", encoding="utf-8", newline="")
    _write_obj(root / "basement.obj", [_box(0, 0, 30, 20, 10, y0=-3.0),
                                       _box(5, 5, 4, 4, 14, y0=0.0)])
    _write_obj(root / "neighbour.obj", [_box(0, 0, 12, 20, 8)])
    _write_obj(root / "bushes.obj", [_box(3.0 * i, 0.0, 0.5, 0.5, 1.0, y0=-0.2)
                                     for i in range(80)])
    _write_obj(root / "fence.obj", [_sheet(0, 0, 60.0, 1.5)])
    _write_obj(root / "deck.obj", [_box(0, 0, 60, 12, 0.8, y0=7.0)]
               + [_box(x, 5, 1.5, 1.5, 7.0) for x in (2, 20, 38, 56)])
    _write_obj(root / "panel.obj", [[((0, 3, 0), (4, 3, 0), (4, 3, 4))]])
    _write_obj(root / "twice.obj", [_box(0, 0, 3, 3, 3)])
    objs = [_placement(root, "dsf:obj0", "basement.obj", (0.0, 0.0), 10.0),
            _placement(root, "dsf:obj1", "neighbour.obj", (30.02, 0.0), 10.0),
            _placement(root, "dsf:obj2", "bushes.obj", (-200.0, 80.0), 33.0),
            _placement(root, "dsf:obj3", "fence.obj", (0.0, -90.0), 5.0),
            _placement(root, "dsf:obj4", "deck.obj", (100.0, 40.0), 70.0),
            _placement(root, "dsf:obj5", "panel.obj", (-80.0, -40.0)),
            _placement(root, "dsf:obj6", "twice.obj", (300.0, 0.0)),
            _placement(root, "dsf:obj7", "twice.obj", (320.0, 0.0)),
            _placement(root, "dsf:obj8", "missing.obj", (0.0, 300.0))]
    pack = NS(name="pack", apt_dat_path=str(root / "Earth nav data" / "apt.dat"))
    air = NS(icao="ZZZZ", frame=Frame("ZZZZ", (60.0, -135.0), 11), pack=pack)
    return NS(root=root, objs=objs, air=air)


def _run(world, workers: int):
    cache = O.ResourceCache(THICK)
    with W.open_pool(LAW, cache, workers=workers, out=lambda s: None) as pool:
        part = PP.partition_pack(world.air, world.objs, cache, LAW, pool=pool)
        return part, cache, pool.tasks_done


def _digest(part, cache) -> bytes:
    """Everything the partition cache stores of this reading, by VALUE."""
    g = part.geom
    return pickle.dumps(
        (repr(part.units), part.skipped, sorted(part.counts.items()), part.contacts,
         part.abutments, sorted(part.member_object.items()),
         tuple((k, o.id) for k, o in part.deferred), repr(g.members.recipes), g.member_ref,
         g.anchor_of_member, sorted(g.anchor_ix.items()),
         [np.asarray(getattr(g.index, f.name)).tobytes() for f in _dc.fields(g.index)],
         repr(sorted(cache.derived_state()["skirt"].items())),
         [(k, list(v)) for k, v in cache.derived_state()["range"].items()],
         [(k, v.tobytes()) for k, v in cache.derived_state()["bounds"].items()]))


@pytest.fixture(scope="module")
def serial(world):
    part, cache, done = _run(world, 1)
    assert done == 0
    return part, cache


def test_the_synthetic_pack_exercises_every_class(serial):
    part, _cache = serial
    c = part.counts
    assert c["members"] >= 5 and c["parts"] > 80
    assert c["scatter_members"] == 1 and c["line_objects"] == 1
    assert c["skirted_members"] >= 1 and c["multi_anchor"] == 1
    assert c["no_solid_admitted"] == 1
    assert dict(part.skipped)["missing.obj"] == "unreadable OBJ8"


@pytest.mark.parametrize("n", sorted({2, 3, N}))
def test_pooled_partition_equals_serial(world, serial, n):
    part, cache, done = _run(world, n)
    assert done > 0                                   # the pool really answered
    assert _digest(part, cache) == _digest(*serial)
    assert list(cache.derived_state()["skirt"]) == list(serial[1].derived_state()["skirt"])
    assert not cache.pre                              # nothing read ahead is kept


def test_default_is_serial_under_pytest(world, serial):
    cache = O.ResourceCache(THICK)
    part = PP.partition_pack(world.air, world.objs, cache, LAW)
    assert _digest(part, cache) == _digest(*serial)


def test_a_pool_that_dies_leaves_the_serial_partition(world, serial, monkeypatch):
    cache = O.ResourceCache(THICK)
    said = []
    with W.open_pool(LAW, cache, workers=2, out=said.append) as pool:
        monkeypatch.setattr(pool, "_setup", _die_setup)
        part = PP.partition_pack(world.air, world.objs, cache, LAW, pool=pool)
    assert said and not pool.parallel
    assert _digest(part, cache) == _digest(*serial)


def _die_setup(*_a):
    os._exit(7)


# ── each pooled block against its own serial derivation ──────────────────

def test_resource_readings_read_ahead_equal_the_serial_readings(world):
    paths = [o.resolved for o in world.objs]
    here = O.ResourceCache(THICK)
    want = {}
    for p in paths:
        if here.geometry(p) is None:
            continue
        want[p] = (repr(D.elevated_deck(here, p, LAW)),
                   repr(here.base_profile(p, LAW)), repr(S.reading(here, p, LAW)))
    cache = O.ResourceCache(THICK)
    with W.open_pool(LAW, cache, workers=2, out=lambda s: None) as pool:
        assert W.read_resources_ahead(pool, cache, paths) == len(set(paths))
    kinds = {k for k, _p in cache.pre}
    assert kinds == {"deck", "base", "skirt"}
    assert ("skirt", paths[2]) not in cache.pre       # never asked of scatter
    held = dict(cache.pre)
    got = {p: (repr(D.elevated_deck(cache, p, LAW)), repr(cache.base_profile(p, LAW)),
               repr(S.reading(cache, p, LAW))) for p in want}
    assert got == want
    # every reading taken was the pool's, and taking it consumed it
    assert all(k not in cache.pre for k in held if k[1] in want)
    assert cache.base[paths[0]] is held[("base", paths[0])]
    assert cache.skirt[paths[0]] is held[("skirt", paths[0])]
    assert W.read_resources_ahead(None, cache, paths) == 0


def test_part_readings_derived_ahead_equal_the_placing(world, serial):
    cache = O.ResourceCache(THICK)
    members, lines, scat = [], set(), set()
    for mi, o in enumerate(world.objs[:6]):
        comps = list(enumerate(cache.components(o.resolved)))
        members.append((o, cache.geometry(o.resolved), comps))
    lines.add(3)
    scat.add(2)
    params = (1.0, 4, 5.0, 12)
    want = C.placed_parts(members, params[0], params[1], lines, params[2], params[3], scat)
    assert W.part_attrs_ahead(None, members, lines, scat, *params) is None
    with W.open_pool(LAW, cache, workers=3, out=lambda s: None) as pool:
        attrs = W.part_attrs_ahead(pool, members, lines, scat, *params)
    assert [len(a) for a in attrs] == [len(m[2]) for m in members]
    got = C.placed_parts(members, params[0], params[1], lines, params[2], params[3], scat,
                         attrs=attrs)
    assert len(got) == len(want)
    for a, b in zip(got, want):
        assert (a.pid, a.member, a.comp, a.base_y, a.area_m2, a.centroid, a.line,
                a.scatter) == (b.pid, b.member, b.comp, b.base_y, b.area_m2,
                               b.centroid, b.line, b.scatter)
        assert a.feet.tobytes() == b.feet.tobytes()
        assert a.solid_h == b.solid_h or (a.solid_h != a.solid_h and b.solid_h != b.solid_h)
        assert len(a.rings) == len(b.rings)
        assert all(np.asarray(x).tobytes() == np.asarray(y).tobytes()
                   for x, y in zip(a.rings, b.rings))
        assert a.pts.tobytes() == b.pts.tobytes() and a.tris.tobytes() == b.tris.tobytes()
    assert any(p.line and len(p.feet) for p in got)             # the fence, with feet
    assert all(p.rings == () and len(p.feet) <= 1 for p in got if p.scatter)


def test_the_stage_profiler_digest_reads_the_two_arms_equal(world, serial):
    """``tools/pack_stage_profile.py --workers`` is the instrument the
    OTHH / HECA identity is read on: its digest agrees on the two arms and
    moves when the partition does."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    import pack_stage_profile as T
    part, cache, _done = _run(world, 2)
    want = T.stage_digest(serial[0], (), serial[1])
    assert T.stage_digest(part, (), cache) == want
    assert set(want) == {"partition", "connectors", "clusters", "readings"}
    assert "objects" in T.stage_digest(part, (), cache, [], None)
    moved = _dc.replace(part, counts={**part.counts, "parts": part.counts["parts"] + 1})
    assert T.stage_digest(moved, (), cache)["partition"] != want["partition"]
    ap = T.main.__code__.co_consts
    assert "--workers" in ap


# ── step 3: the per-placement readings ───────────────────────────────────

def _dem(x: float, y: float) -> float:
    return 100.0 + 0.002 * x - 0.001 * y            # a gentle tilt, no NaN


def _read(world, ahead=None):
    bl = LAW.tables.structures.basin
    root = world.root
    _write_obj(root / "pit.obj", [_box(0, 0, 40, 30, 6.0, y0=-6.0)])
    _write_obj(root / "deckflag.obj", [_box(0, 0, 30, 8, 0.6, y0=5.0)],
               hard="ATTR_hard_deck")
    _write_obj(root / "buried.obj", [_box(0, 0, 6, 6, 2.0, y0=-9.0)])
    names = ["pit.obj", "basement.obj", "deckflag.obj", "buried.obj", "bushes.obj",
             "pit.obj", "neighbour.obj", "nowhere.obj", "lib/stock/thing.obj", "pit.obj"]
    rows = [(f"dsf:obj{k}", nm, (40.0 * k, -25.0 * k), 17.0 * k,
             0.5 if k % 3 == 0 else None, "OBJECT_AGL" if k % 3 == 0 else "OBJECT")
            for k, nm in enumerate(names)]
    index = {nm: str(root / nm) for nm in names if nm != "nowhere.obj"}
    index["lib/stock/thing.obj"] = str(root / "twice.obj")
    cache = O.ResourceCache(THICK)
    objs, rep = O.read_placed_objects(
        rows, None, index, _dem, bl.admission_depth_m, bl.min_solid_thickness_m,
        bl.contact_band_m, cache, shell_reaches_grade=bl.shell_reaches_grade,
        floor_plate_normal_y_min=bl.floor_plate_normal_y_min,
        rim_reaches_grade=bl.rim_reaches_grade,
        rim_protrusion_max_fraction=bl.rim_protrusion_max_fraction,
        authored_depth_min_m=bl.authored_depth_min_m,
        ahead=None if ahead is None else (lambda jobs, rl: ahead(cache, jobs, rl)))
    return objs, rep, cache


def test_the_placement_reading_through_a_pool_is_the_serial_reading(world):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    import pack_stage_profile as T
    want_objs, want_rep, want_cache = _read(world)
    assert any(w.below.area > 0 for o in want_objs for w in o.witnesses)
    assert want_rep.below_grade_objects >= 3 and want_rep.hard_deck_objects == 1
    assert want_rep.unresolved == 1 and want_rep.stock_placements == 1
    assert want_rep.buried_components >= 1 and want_rep.buried_named
    for n in sorted({2, 3, N}):
        asked = []

        def ahead(cache, jobs, rl, _n=n):
            asked.append(len(jobs))
            with W.open_pool(LAW, cache, workers=_n, out=lambda s: None) as pool:
                got = W.placements_ahead(pool, jobs, rl)
                assert pool.tasks_done > 0
                return got
        objs, rep, cache = _read(world, ahead)
        # only the placements with a component or a hard deck to read cross
        assert asked and 0 < asked[0] < len(want_objs)
        assert T.value_of(objs) == T.value_of(want_objs)   # every polygon by WKB
        assert rep == want_rep
        assert list(rep.buried_named) == list(want_rep.buried_named)
        assert list(cache.derived_state()["range"].items()) \
            == list(want_cache.derived_state()["range"].items())
    # no pool: the same call answers None and the reader reads here
    objs, rep, _c = _read(world, lambda cache, jobs, rl: W.placements_ahead(None, jobs, rl))
    assert T.value_of(objs) == T.value_of(want_objs) and rep == want_rep


# ── item 4: the narrow contact pass — verdicts ahead, the loop replayed ──

def _contact_world():
    """A lattice of boxes that touch, nearly touch and overlap, in a few
    members, so the pass skips joined pairs, flushes mid-way and doubts."""
    rng = np.random.default_rng(362)
    members = []
    for mi in range(40):
        comps = []
        for k in range(6):
            x, z = float(rng.integers(0, 12)) * 2.0, float(rng.integers(0, 12)) * 2.0
            gap = float(rng.choice([0.0, 0.004, 0.03, 0.4]))
            comps.append(_box(x + gap, z, 2.0, 2.0, 3.0 + k, y0=float(rng.integers(0, 2))))
        members.append(comps)
    return members


def _narrow_inputs(tmp_path):
    members = []
    for mi, comps in enumerate(_contact_world()):
        path = _write_obj(tmp_path / f"m{mi}.obj", comps)
        cache = O.ResourceCache(THICK)
        o = _placement(tmp_path, f"dsf:obj{mi}", f"m{mi}.obj", (0.0, 0.0))
        members.append((o, cache.geometry(path), list(enumerate(cache.components(path)))))
    parts = C.placed_parts(members)
    bp = C._broad_pairs(parts, 0.01)
    pend = [(int(a), int(b)) for a, b in bp.tolist()]
    return parts, pend


@pytest.mark.parametrize("budget,chunk", [(10**9, 50_000), (10**9, 200), (40, 200), (10**9, 1)])
def test_the_replay_of_recorded_verdicts_is_the_narrow_pass(tmp_path, budget, chunk):
    parts, pend = _narrow_inputs(tmp_path)
    assert len(pend) > 300
    uf0 = C._UnionFind(len(parts))
    want, want_un = C._narrow_pass(parts, pend, 0.01, budget, chunk, uf0)
    assert want and len(want) < len(pend)             # some touch, some are skipped
    nrows, flags = C.narrow_outcomes(parts, pend, 0.01, budget, chunk)
    # order-free: any blocking of the pairs records the same verdicts
    cut = len(pend) // 3
    a = C.narrow_outcomes(parts, pend[:cut], 0.01, budget, 7)
    b = C.narrow_outcomes(parts, pend[cut:], 0.01, budget, 10**9)
    assert np.array_equal(np.concatenate([a[0], b[0]]), nrows)
    assert np.array_equal(np.concatenate([a[1], b[1]]), flags)
    uf1 = C._UnionFind(len(parts))
    got, got_un = C._narrow_replay(parts, pend, nrows, flags, chunk, uf1)
    assert got == want and got_un == want_un
    assert [uf1.find(i) for i in range(len(parts))] == [uf0.find(i) for i in range(len(parts))]
    assert vars(uf1) == vars(uf0) or all(
        np.array_equal(np.asarray(x), np.asarray(y))
        for x, y in zip(vars(uf1).values(), vars(uf0).values()))
    if budget == 40:
        assert want_un > 0 and (flags & C.DOUBT).any()


@pytest.mark.parametrize("n", sorted({2, N}))
def test_the_pooled_narrow_pass_reads_the_parts_from_shared_memory(tmp_path, monkeypatch, n):
    from auto_patch_v2.airport import pool as P
    parts, pend = _narrow_inputs(tmp_path)
    monkeypatch.setattr(C, "NARROW_POOL_MIN_PAIRS", 1)
    want = C.narrow_outcomes(parts, pend, 0.01, 10**9, 500)
    with P.WorkPool(workers=n, out=lambda s: None) as pool:
        got = C.narrow_ahead(pool, parts, pend, 0.01, 10**9, 500)
        assert pool.tasks_done >= 1
    assert np.array_equal(got[0], want[0]) and np.array_equal(got[1], want[1])
    assert C.narrow_ahead(None, parts, pend, 0.01, 10**9, 500) is None
    # the whole partition, pooled against serial
    def run(pool):
        return C.partition([(o, g, c) for o, g, c in _members(tmp_path)], 0.01, 1.0,
                           10**9, 0.5, 300, pool=pool)
    serial = run(None)
    with P.WorkPool(workers=n, out=lambda s: None) as pool:
        pooled = run(pool)
        assert pool.tasks_done >= 1
    assert pooled.contacts == serial.contacts and pooled.abutments == serial.abutments
    assert (pooled.pairs_tested, pooled.pairs_unproved, pooled.pools, pooled.structures) \
        == (serial.pairs_tested, serial.pairs_unproved, serial.pools, serial.structures)


def _members(tmp_path):
    out = []
    for mi in range(40):
        path = str(tmp_path / f"m{mi}.obj")
        cache = O.ResourceCache(THICK)
        out.append((_placement(tmp_path, f"dsf:obj{mi}", f"m{mi}.obj", (0.0, 0.0)),
                    cache.geometry(path), list(enumerate(cache.components(path)))))
    return out


def test_shared_arrays_are_read_only_views_and_are_released():
    from auto_patch_v2.airport import pool as P
    src = {"a": np.arange(12, dtype=np.int64).reshape(4, 3), "e": np.zeros((0, 3))}
    with P.SharedArrays(src) as sh:
        got = P.attach(sh.spec)
        assert np.array_equal(got["a"], src["a"]) and got["e"].shape == (0, 3)
        assert not got["a"].flags.writeable
        assert P.attach(sh.spec) is got               # attached once
        name = sh.spec["a"][0]
    P._ATTACHED[:] = [None, [], {}]
    from multiprocessing import shared_memory
    with pytest.raises(FileNotFoundError):
        shared_memory.SharedMemory(name=name)


def test_the_pack_stage_raises_no_runtime_warning(world, serial):
    """issue #395 — THE GUARD: engine stderr carries no numpy / shapely
    ``RuntimeWarning``, so a real error stands out.  The synthetic pack is
    read and partitioned with ``RuntimeWarning`` promoted to an ERROR; a
    call site that starts leaking one fails here by name."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        part, cache, _done = _run(world, 1)
        for o in world.objs[:7]:
            cache.base_profile(o.resolved, LAW)
    assert _digest(part, cache) == _digest(*serial)
