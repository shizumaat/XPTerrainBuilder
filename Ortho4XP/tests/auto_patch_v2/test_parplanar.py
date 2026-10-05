"""THE POOLED PACK READERS ARE THE SERIAL ONES (issue #362, lane
``parplanar``; ``airport/reader_work.py``, ``airport/dem_shared.py``,
``planar/pack_reads.py``).

A synthetic pack — a tunnel wall object over a mapped bore, a level kerb-wall
corridor and a closed bay — is read by ``planar/pack_reads`` on one core and
with the wall corridors and the tunnel corridors + thin plates in work-pool
workers BESIDE the door wells and the sunken roads.  Bar: every record, every
stats field but the clocks, the fallback-rung count and the planar map are
EQUAL; a pool that dies, a reader that trips and inputs that do not pickle
all leave the serial reading.
"""
from __future__ import annotations

import dataclasses as _dc
import os
import pickle

import numpy as np
import pytest
from pyproj import Transformer

from auto_patch_v2.airport import dem_shared as DS
from auto_patch_v2.airport import frame_entry as _fe
from auto_patch_v2.airport import pool as P
from auto_patch_v2.airport import reader_work as RW
from auto_patch_v2.airport import wall_corridors as WC
from auto_patch_v2.airport.dem_production import ProductionDem, _BakedTile
from auto_patch_v2.airport.obj8 import ResourceCache
from auto_patch_v2.classify.roles import Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar import pack_reads as PR
from auto_patch_v2.planar.basins import read_objects
from auto_patch_v2.planar.build import build as planar_build

from test_tunnel_objects import _airport, _bore, _wall_obj
from test_v2wallcorridor import _cells, _corridor_obj

N = max(2, min(8, os.cpu_count() or 2))


@pytest.fixture(scope="module")
def law():
    # Law C (the kerb-wall corridors) is a per-airport affordance: OTHH's
    return Law.for_airport("OTHH")


def _cache(law):
    return ResourceCache(law.tables.structures.basin.min_solid_thickness_m, _fe.quantum(law))


@pytest.fixture(scope="module")
def world(tmp_path_factory, law):
    d = tmp_path_factory.mktemp("parplanar") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n", encoding="utf-8",
                                                         newline="")
    objs = {"dir": d, "wall": _wall_obj(d / "wall.obj", end_a=True),
            "level": _corridor_obj(d / "level.obj"),
            "bay": _corridor_obj(d / "bay.obj", end_wall=True, half_len=5.0)}
    airport = _airport(objs, law, [("wall", (0.0, 0.0), 180.0, -3.0, "OBJECT_AGL"),
                                   ("level", (900.0, 400.0), 0.0, None, "OBJECT"),
                                   ("level", (900.0, 0.0), 0.0, None, "OBJECT"),
                                   ("bay", (1300.0, 0.0), 0.0, None, "OBJECT")],
                       _bore(y_in=-40.0))
    objects, _rep = read_objects(airport, law, _cache(law))
    return airport, objects


@pytest.fixture(autouse=True)
def _small_packs_pool_too(monkeypatch):
    """The fixture pack is three objects: lift the size rule (twinned below)."""
    monkeypatch.setattr(RW, "MIN_OBJECTS", 0)


def _untimed(stats) -> dict:
    return {k: v for k, v in _dc.asdict(stats).items() if not k.endswith("_s")}


def _reading(world, law, workers: int) -> dict:
    """The five readings as ``planar/build`` asks for them, under a pinned
    budget (the suite's own pin is restored)."""
    airport, objects = world
    cache = _cache(law)
    P.configure(workers)
    _fe.reset_rung_counts()
    try:
        pr = PR.pack_reads(airport, objects, cache, law, walls=True)
        walls, wstats = PR.wall_corridor_reads(airport, objects, cache, law)
    finally:
        P.configure(1)
    return {"corridors": pr.corridors, "plates": pr.plates, "wells": pr.wells,
            "roads": pr.roads, "walls": walls,
            "stats": [_untimed(s) for s in (pr.tunnel_stats, pr.plate_stats, pr.door_stats,
                                            pr.road_stats, wstats)],
            "rungs": _fe.rung_counts(), "grade": (cache.grade.calls, cache.grade.unions,
                                                  cache.grade.vertices),
            "pool": PR.pool_report(cache)}


def _same(a: dict, b: dict) -> None:
    for k in ("corridors", "plates", "wells", "roads", "walls", "stats", "rungs", "grade"):
        assert a[k] == b[k], k


@pytest.fixture(scope="module")
def serial(world, law):
    return _reading(world, law, 1)


def test_the_synthetic_pack_exercises_the_pooled_readers(serial):
    assert len(serial["corridors"]) == 1 and len(serial["walls"]) >= 5
    assert serial["pool"] is None                 # one core: no pool, no account


@pytest.mark.parametrize("n", sorted({2, 3, N}))
def test_pooled_readers_equal_serial(world, law, serial, n, capsys):
    got = _reading(world, law, n)
    _same(got, serial)
    assert (f"[pool] workers {min(n, 5, RW.MAX_WORKERS)}: 5 task(s) answered by workers"
            in capsys.readouterr().out)        # four wall families + the tunnels
    assert got["pool"]["readers"] == ["tunnels", "walls"]
    assert got["pool"]["workers"] == min(n, 5, RW.MAX_WORKERS) and not got["pool"]["fell_back"]


def test_a_small_pack_is_read_on_one_core(world, law, serial, monkeypatch):
    """Under ``MIN_OBJECTS`` no pool is opened whatever the budget — a cost
    rule, so the reading is the serial one by construction."""
    monkeypatch.undo()
    assert RW.MIN_OBJECTS > len(world[1])
    monkeypatch.setattr(RW, "WorkPool", None)      # opening one would raise
    got = _reading(world, law, N)
    _same(got, serial)
    assert got["pool"] is None


def test_the_pooled_readers_are_not_read_twice(world, law, monkeypatch):
    """With a pool the build's own process calls neither pooled reader, and
    ``wall_corridor_reads`` is handed the worker's reading."""
    calls = []
    for mod, name in ((PR, "read_corridors"), (PR, "read_plates"), (PR, "read_wall_corridors")):
        monkeypatch.setattr(mod, name, lambda *a, _n=name, **k: calls.append(_n))
    _reading(world, law, 2)
    assert calls == []


def test_the_planar_map_is_the_serial_one(world, law):
    airport, _objects = world
    cl = Classification(tuple(_cells()), (), {}, ())
    maps = []
    for workers in (1, 2):
        P.configure(workers)
        try:
            pm, st = planar_build(airport, cl, law, cache=_cache(law))
        finally:
            P.configure(1)
        maps.append((pm.faces, pm.edges, pm.vertices, pm.breaklines, pm.structures,
                     _untimed(st.tunnel_objects), _untimed(st.wall_corridors),
                     st.union_fallback_rungs))
    assert maps[0] == maps[1]
    assert maps[0][4], "the fixture must build structures"


# ── the order argument: a family reads nothing of another's ──────────────

def test_a_familys_reading_is_its_own_and_the_ids_come_from_the_assembly(world, law, serial):
    """``read_family`` over the families in ANY order, each with a fresh
    reader and a fresh parse, assembled in the intake's sorted order, is the
    one-loop reading — and the ``@k`` of a resource placed at two anchors
    follows the sorted family order, whichever family was read first."""
    airport, objects = world
    placements, fams = WC.wall_families(objects, _cache(law), law)
    assert [fk for fk, _ks in fams] == sorted(fk for fk, _ks in fams) and len(fams) == 4
    got = {}
    for fk, ks in reversed(fams):
        rd = WC.wall_reader(airport, _cache(law), law)
        got[fk] = WC.read_family(rd, fk, [objects[k] for k in ks])
    for _st, pairs in got.values():              # no id before the assembly
        assert all(r.id in ("", "/a", "/b") for _res, _name, recs in pairs for r in recs)
    walls, wstats = WC.assemble(placements, [got[fk] for fk, _ks in fams])
    assert walls == serial["walls"] and _untimed(wstats) == serial["stats"][4]
    # the two ``level`` anchors: (900, 0) sorts before (900, 400)
    by_k = {r.id.split("@")[1][0]: r for r in walls if "level.obj" in r.id}
    assert by_k["0"].anchor_xy == (900.0, 0.0) and by_k["1"].anchor_xy == (900.0, 400.0)
    assert all(r.sibling.startswith(r.id.rsplit("/", 1)[0] + "/") for r in walls if r.sibling)


# ── what does not answer leaves the serial reading ───────────────────────

def _die_setup(*_a):
    os._exit(3)


def test_a_pool_that_dies_leaves_the_serial_reading(world, law, serial, monkeypatch, capsys):
    monkeypatch.setattr(RW, "setup", _die_setup)
    got = _reading(world, law, 2)
    _same(got, serial)
    assert got["pool"]["fell_back"] and got["pool"]["readers"] == []
    assert "[pool] FELL BACK" in capsys.readouterr().out


def _walls_trip(state, task):
    """A worker whose LAST wall family reaches for a field it was not handed."""
    if task[0] == RW.WALLS and task[1][0] > 1000.0:
        try:
            len(state.airport.partition)
        except RW.StrippedField as e:
            return ("serial", str(e))
    return RW.read(state, task)


def test_a_reader_that_trips_is_read_here(world, law, serial, monkeypatch, capsys):
    monkeypatch.setattr(RW, "read", _walls_trip)
    got = _reading(world, law, 2)
    _same(got, serial)
    assert got["pool"]["readers"] == ["tunnels"]
    assert "'walls' is read on one core: airport.partition" in capsys.readouterr().out


def _rungy(state, task):
    row = RW.read(state, task)
    return (row[0], row[1], {"twin.site": (1, 2)})


def test_a_workers_fallback_rungs_are_charged_here(world, law, monkeypatch):
    monkeypatch.setattr(RW, "read", _rungy)
    try:
        assert _reading(world, law, 2)["rungs"] == {"twin.site": (5, 10)}   # five tasks
    finally:
        _fe.reset_rung_counts()


def test_inputs_that_do_not_pickle_stay_on_one_core(world, law, serial, capsys):
    airport, objects = world
    said = []
    closure = _dc.replace(airport, dem=type("D", (), {"z": lambda self, x, y: 0.0})())
    assert RW.begin(closure, objects, _cache(law), law, workers=2, out=said.append) is None
    assert len(said) == 1 and "do not cross to a worker" in said[0]
    assert RW.begin(airport, objects, _cache(law), law, workers=1, out=said.append) is None
    assert len(said) == 1                          # a budget of 1 says nothing


def test_a_stripped_field_trips_on_any_use_and_pickles():
    s = pickle.loads(pickle.dumps(RW.Stripped("groups")))
    for use in (lambda: s.members, lambda: len(s), lambda: bool(s), lambda: list(s),
                lambda: s[0], lambda: 1 in s):
        with pytest.raises(RW.StrippedField, match="airport.groups"):
            use()


# ── the DEM a worker samples ─────────────────────────────────────────────

def _production_dem(frame, tiles: dict) -> ProductionDem:
    dem = ProductionDem.__new__(ProductionDem)       # no corpus: the sampler alone
    dem.frame, dem.icao, dem._tiles = frame, "ZZZZ", tiles
    dem._inv = Transformer.from_crs(frame.crs, "EPSG:4326", always_xy=True)
    return dem


def test_the_shared_dem_samples_bit_for_bit_and_never_composes():
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    rng = np.random.default_rng(362)
    tiles = {(60, -136): _BakedTile(60, -136, rng.normal(700.0, 30.0, (301, 401)), 0.0, 1.0, 0.0, 1.0),
             (60, -135): None}
    dem = _production_dem(frame, tiles)
    shared, token = DS.share(dem)
    try:
        warm = DS.revive(pickle.loads(pickle.dumps(token)))
        xs, ys = rng.uniform(-9000, 9000, 500), rng.uniform(-9000, 9000, 500)
        assert warm.z_many(xs, ys).tobytes() == dem.z_many(xs, ys).tobytes()
        assert warm.z(12.5, -40.25) == dem.z(12.5, -40.25)
        assert not warm.tile(60, -136).alt.flags.writeable
        # a tile the build knew to be absent reads NaN, as it does there
        east = 40000.0
        assert np.isnan(warm.z(east, 0.0)) and np.isnan(dem.z(east, 0.0))
        # a tile the build had not composed is the build's to compose
        with pytest.raises(DS.ColdTile):
            warm.z(0.0, 80000.0)
    finally:
        shared.close()


def test_a_twin_dem_crosses_as_itself(world):
    airport, _objects = world
    shared, token = DS.share(airport.dem)
    assert shared is None and DS.revive(token) is airport.dem


# ── the instruments (``tools/planar_read_arm.py``, ``v2_solve_replay --workers``) ──

def _tool(name: str):
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_parplanar_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, path.read_text(encoding="utf-8")


def test_the_read_arm_hashes_the_two_arms_equal_and_a_change_differently(world, law):
    arm, _src = _tool("planar_read_arm")
    airport, objects = world
    recs = []
    for workers in (1, 2):
        P.configure(workers)
        try:
            recs.append(arm.reading(airport, objects, _cache(law), law))
        finally:
            P.configure(1)
    assert recs[0]["timing"]["pool"] is None and recs[1]["timing"]["pool"]["readers"]
    assert recs[0]["all"] == recs[1]["all"]
    assert recs[0]["counts"]["corridors"] == 1 and recs[0]["counts"]["walls"] >= 3
    # the hash reads the readings: one object fewer is another record
    less = arm.reading(airport, objects[1:], _cache(law), law)
    assert less["all"] != recs[0]["all"] and less["tunnels"] != recs[0]["tunnels"]
    # clocks are not identity; a set hashes the same in any order
    assert arm.sha({"b", "a"}) == arm.sha({"a", "b"})
    assert arm.sha(PR.WallCorridorStats(read_s=1.0)) == arm.sha(PR.WallCorridorStats(read_s=2.0))


def test_the_replay_pins_the_pool_budget():
    replay, src = _tool("v2_solve_replay")
    try:
        assert replay.pool_budget(3) == 3 and P.budget() == 3
        assert replay.pool_budget() == 3               # a read alone pins nothing
    finally:
        P.configure(1)
    assert '"--workers"' in src and "pool_budget(a.workers)" in src
