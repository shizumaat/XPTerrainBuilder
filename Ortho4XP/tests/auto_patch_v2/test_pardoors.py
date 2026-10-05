"""THE POOLED DOOR WELLS AND SUNKEN ROADS ARE THE SERIAL ONES — readings AND
at-grade charges (issue #362, lane ``pardoors``; ``airport/door_wells.py``,
``airport/sunken_roads.py``, ``airport/grade_ledger.py``,
``airport/reader_work.py``).

A synthetic pack — one door-well building placed at two anchors, a roofed
and a wide well, a roofed sunken road with an open one under its deck, a
level one — is read by ``planar/pack_reads`` on one core and with every reader in
work-pool workers.  Bar: every record and every stats field but the clocks
are EQUAL, and so is what the readers leave on the build's cache for the
passes after them: ``cache.grade`` (calls, unions, vertices, resources), the
three at-grade memos (keys, their order, every polygon) and the fallback
rungs.  A pool that dies, a family that trips, a read that cannot be
replayed and an armed vertex budget all leave the serial reading and the
serial charges.
"""
from __future__ import annotations

import dataclasses as _dc
import os
import random

import pytest

from auto_patch_v2.airport import door_wells as DW
from auto_patch_v2.airport import frame_entry as _fe
from auto_patch_v2.airport import grade_ledger as GL
from auto_patch_v2.airport import obj8_grade as G
from auto_patch_v2.airport import pool as P
from auto_patch_v2.airport import reader_work as RW
from auto_patch_v2.airport import sunken_roads as SR
from auto_patch_v2.airport.obj8 import ResourceCache, above_grade_footprint, at_grade_geometry
from auto_patch_v2.law import Law
from auto_patch_v2.planar import pack_reads as PR
from auto_patch_v2.planar.basins import read_objects

from test_tunnel_objects import _airport
from test_v2doorramp import _door_obj, _road_obj, _roofed_well_obj, _wide_well_obj

N = max(2, min(8, os.cpu_count() or 2))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _cache(law):
    return ResourceCache(law.tables.structures.basin.min_solid_thickness_m, _fe.quantum(law))


@pytest.fixture(scope="module")
def world(tmp_path_factory, law):
    d = tmp_path_factory.mktemp("pardoors") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n", encoding="utf-8",
                                                         newline="")
    objs = {"dir": d, "door": _door_obj(d / "door.obj"),
            "roofed": _roofed_well_obj(d / "roofed.obj"), "wide": _wide_well_obj(d / "wide.obj"),
            "road": _road_obj(d / "road.obj"),
            "road_level": _road_obj(d / "road_level.obj", level=True),
            "road_open": _road_obj(d / "road_open.obj", roof=False)}
    airport = _airport(objs, law, [
        # one resource at two anchors: two door families, ``@0`` and ``@1``
        ("door", (400.0, 0.0), 0.0, 0.0, "OBJECT"), ("door", (0.0, 0.0), 90.0, 0.0, "OBJECT"),
        ("roofed", (800.0, 0.0), 0.0, 0.0, "OBJECT"), ("wide", (1200.0, 0.0), 0.0, 0.0, "OBJECT"),
        # two road families over one another: each asks for the other's cover
        ("road", (0.0, 2000.0), 0.0, 0.0, "OBJECT"),
        ("road_open", (5.0, 2000.0), 0.0, 0.0, "OBJECT"),
        ("road_level", (2000.0, 2000.0), 0.0, 0.0, "OBJECT")])
    objects, _rep = read_objects(airport, law, _cache(law))
    return airport, objects


@pytest.fixture(autouse=True)
def _small_packs_pool_too(monkeypatch):
    monkeypatch.setattr(RW, "MIN_OBJECTS", 0)


def _untimed(stats) -> dict:
    return {k: v for k, v in _dc.asdict(stats).items() if not k.endswith("_s")}


def _memo(memo: dict) -> list:
    """A memo as data: its keys IN ORDER and every value's geometry."""
    def val(v):
        if isinstance(v, tuple):
            return tuple(val(x) for x in v)
        return "LATER" if v is G.LATER else getattr(v, "wkb_hex", v)
    return [(k, val(v)) for k, v in memo.items()]


def _reading(world, law, workers: int, cache=None) -> dict:
    airport, objects = world
    cache = _cache(law) if cache is None else cache
    P.configure(workers)
    _fe.reset_rung_counts()
    try:
        pr = PR.pack_reads(airport, objects, cache, law, walls=True)
    finally:
        P.configure(1)
    g = cache.grade
    return {"wells": pr.wells, "roads": pr.roads,
            "stats": [_untimed(pr.door_stats), _untimed(pr.road_stats)],
            "rungs": _fe.rung_counts(),
            "grade": (g.calls, g.unions, g.vertices, sorted(g.resources), g.over_budget),
            "memos": [_memo(cache.grade_memo), _memo(cache.cover_memo), _memo(cache.clip_memo)],
            "pool": PR.pool_report(cache), "cache": cache}


KEYS = ("wells", "roads", "stats", "rungs", "grade", "memos")


def _same(a: dict, b: dict) -> None:
    for k in KEYS:
        assert a[k] == b[k], k


@pytest.fixture(scope="module")
def serial(world, law):
    return _reading(world, law, 1)


def test_the_synthetic_pack_exercises_both_readers_and_their_charges(serial):
    assert [w.id for w in serial["wells"]] == ["door:door.obj@0", "door:door.obj@1"]
    assert [w.anchor_xy for w in serial["wells"]] == [(0.0, 0.0), (400.0, 0.0)]  # sorted families
    # the open road stands under the roofed one's deck: both are roofed
    assert len(serial["roads"]) == 2 and serial["stats"][1]["plates"] >= 3
    assert len(serial["stats"][0]["refused"]) >= 2 and serial["stats"][1]["refused"]
    calls, unions, vertices, resources, _over = serial["grade"]
    assert calls > unions > 0 and vertices > 0 and len(resources) >= 4
    assert all(serial["memos"]) and serial["pool"] is None


@pytest.mark.parametrize("n", sorted({2, 3, N}))
def test_pooled_readers_and_charges_equal_serial(world, law, serial, n):
    got = _reading(world, law, n)
    _same(got, serial)
    assert {"doors", "roads"} <= set(got["pool"]["readers"]) and not got["pool"]["fell_back"]


def test_a_later_pass_is_answered_and_charged_as_after_one_core(world, law, serial):
    """What the basin pass does next — a LINEWORK read of a placement the
    doors read polygons-only, a cover read both readers made, a new one —
    costs and charges the same on a pooled build's cache."""
    airport, objects = world
    after = []
    for r in (serial, _reading(world, law, 2)):
        cache = r["cache"]
        band = law.tables.structures.basin.contact_band_m
        out = []
        for o in objects:
            lu, pu = at_grade_geometry(o, cache, airport.dem.z, band)
            cv = above_grade_footprint(o, cache, airport.dem.z, band)
            out.append(tuple(getattr(x, "wkb_hex", None) for x in (lu, pu, cv)))
        g = cache.grade
        after.append((out, g.calls, g.unions, g.vertices, sorted(g.resources),
                      _memo(cache.grade_memo), _memo(cache.cover_memo), _memo(cache.clip_memo)))
    assert after[0] == after[1]
    assert after[0][2] > serial["grade"][1]            # the pass made unions of its own


@pytest.mark.parametrize("seed", (1, 2, 3))
def test_any_completion_order_is_the_serial_reading(world, law, serial, monkeypatch, seed):
    """The tasks handed out in a random order (the weights only order the
    submission): the answers are taken in the intake's order all the same."""
    rng = random.Random(seed)
    begin = P.WorkPool.begin

    def shuffled(self, fn, tasks, *, weights=None, **kw):
        return begin(self, fn, tasks, weights=[rng.random() for _ in tasks], **kw)
    monkeypatch.setattr(P.WorkPool, "begin", shuffled)
    _same(_reading(world, law, 3), serial)


def test_a_family_reads_nothing_of_another_and_the_ids_come_from_the_assembly(world, law, serial):
    """Each family read in REVERSE order through a fresh reader on a fresh
    parse, assembled in the intake's order, is the one-loop reading."""
    airport, objects = world
    stats = DW.DoorStats()
    cache = _cache(law)
    wits = DW.sill_witnesses(objects, cache, airport.dem.z, law, stats)
    fams = DW.door_families(objects, wits)
    assert len(fams) == 4 and [fk for fk, _f, _m in fams] == sorted(fk for fk, _f, _m in fams)
    rd = DW.door_reader(airport, cache, law, {cid for _o, _w, cid in wits})
    got = {fk: DW.read_family(rd, fam, members) for fk, fam, members in reversed(fams)}
    assert all(w.id == "" for _st, wells in got.values() for _r, _n, w in wells)
    wells, stats = DW.assemble(stats, [got[fk] for fk, _f, _m in fams])
    assert wells == serial["wells"] and _untimed(stats) == serial["stats"][0]
    placements, rfams = SR.road_families(objects, _cache(law), law)
    assert len(rfams) >= 3
    rgot = {}
    for fk, ks in reversed(rfams):
        c = _cache(law)
        rgot[fk] = SR.read_family(SR.road_reader(airport, objects, c, law), [objects[k] for k in ks])
    roads, rstats = SR.assemble(placements, [rgot[fk] for fk, _ks in rfams])
    assert roads == serial["roads"] and _untimed(rstats) == serial["stats"][1]


# ── what does not answer leaves the serial reading AND the serial charges ──

def _die_setup(*_a):
    os._exit(3)


def test_a_pool_that_dies_leaves_the_serial_reading(world, law, serial, monkeypatch, capsys):
    monkeypatch.setattr(RW, "setup", _die_setup)
    got = _reading(world, law, 2)
    _same(got, serial)
    assert got["pool"]["fell_back"] and got["pool"]["readers"] == []
    assert "[pool] FELL BACK" in capsys.readouterr().out


def _doors_trip(state, task):
    """A worker whose door family at the SECOND anchor trips."""
    if task[0] == RW.DOORS and state.objects[task[2][0]].xy[0] > 300.0:
        return ("serial", "twin: a cold tile", None)
    return RW.read(state, task)


def test_tripped_doors_are_read_here_before_the_roads_are_settled(world, law, serial,
                                                                  monkeypatch, capsys):
    monkeypatch.setattr(RW, "read", _doors_trip)
    got = _reading(world, law, 2)
    _same(got, serial)
    assert "doors" not in got["pool"]["readers"] and "roads" in got["pool"]["readers"]
    assert "'doors' is read on one core: twin: a cold tile" in capsys.readouterr().out


def _roads_trip(state, task):
    if task[0] == RW.ROADS:
        return ("serial", "twin: a cold tile", None)
    return RW.read(state, task)


def test_tripped_roads_are_read_here_after_the_doors(world, law, serial, monkeypatch):
    monkeypatch.setattr(RW, "read", _roads_trip)
    got = _reading(world, law, 2)
    _same(got, serial)
    assert "roads" not in got["pool"]["readers"] and "doors" in got["pool"]["readers"]


def test_a_read_that_cannot_be_replayed_is_read_here(world, law, serial, monkeypatch, capsys):
    """No worker's entries reach the build: nothing is written by the
    refused replay, and both readers are read on one core."""
    monkeypatch.setattr(GL, "made", lambda ledgers: ({}, {}))
    got = _reading(world, law, 2)
    _same(got, serial)
    assert got["pool"]["readers"] == ["tunnels", "walls"]
    said = capsys.readouterr().out
    assert "'doors' is read on one core: no worker returned" in said
    assert "'roads' is read on one core: no worker returned" in said
    assert "pack readers: tunnels, walls" in got["pool"]["line"]


def test_an_armed_vertex_budget_keeps_the_at_grade_readers_on_one_core(world, law):
    """The budget REFUSES a read past it on one core; no worker knows where
    the build's count stands, so an armed cache is not handed out."""
    got = []
    for workers in (1, 2):
        cache = _cache(law)
        cache.grade.vertex_budget = 100
        got.append(_reading(world, law, workers, cache))
    _same(got[1], got[0])
    assert got[0]["grade"][4] and got[1]["pool"]["readers"] == ["tunnels", "walls"]


# ── the ledger alone ─────────────────────────────────────────────────────

def test_a_linework_read_is_not_replayable(world, law):
    airport, objects = world
    cache = _cache(law)
    mark = GL.begin(cache)
    at_grade_geometry(objects[0], cache, airport.dem.z, law.tables.structures.basin.contact_band_m)
    with pytest.raises(GL.Unreplayable, match="linework"):
        GL.end(cache, mark)


def test_a_ledger_carries_its_requests_its_entries_and_their_rungs(world, law, monkeypatch):
    """One worker's two tasks: the second HITS the first's entry, and the
    replay of the second ALONE finds the entry among every ledger's; an
    entry's fallback rungs travel with the entry, not with the task."""
    airport, objects = world
    band = law.tables.structures.basin.contact_band_m
    worker = _cache(law)
    union = _fe.union

    def rungy(parts, site=None):
        if site == "obj8_grade.polys":
            _fe._count(site, 0)
        return union(parts, site)
    monkeypatch.setattr(_fe, "union", rungy)
    leds, totals = [], []
    for _task in range(2):
        _fe.reset_rung_counts()
        mark = GL.begin(worker)
        above_grade_footprint(objects[0], worker, airport.dem.z, band)
        leds.append(GL.end(worker, mark))
        totals.append(_fe.rung_counts())
    monkeypatch.undo()
    assert [len(x.touches) for x in leds] == [1, 1]
    assert [len(x.memos) for x in leds] == [1, 0] and leds[0].clips and not leds[1].clips
    assert leds[0].rungs == totals[0] == {"obj8_grade.polys": (1, 0)}
    assert leds[0].own_rungs(totals[0]) == {} and totals[1] == {}
    build = _cache(law)
    _fe.reset_rung_counts()
    try:
        with pytest.raises(GL.Unreplayable):
            GL.replay(build, leds[1:], GL.made(leds[1:]))
        assert not build.cover_memo and build.grade.calls == 0     # nothing written
        GL.replay(build, leds[1:], GL.made(leds))
        assert _fe.rung_counts() == {"obj8_grade.polys": (1, 0)}
        GL.replay(build, leds[:1], GL.made(leds))                  # now a hit: a call
        assert _fe.rung_counts() == {"obj8_grade.polys": (1, 0)}
    finally:
        _fe.reset_rung_counts()
    one = _cache(law)
    for _task in range(2):
        above_grade_footprint(objects[0], one, airport.dem.z, band)
    assert (build.grade.calls, build.grade.unions, build.grade.vertices) == \
        (one.grade.calls, one.grade.unions, one.grade.vertices) == (2, 1, one.grade.vertices)
    assert _memo(build.cover_memo) == _memo(one.cover_memo)
    assert _memo(build.clip_memo) == _memo(one.clip_memo)
    # ``once``: one read asks a placement once, however many tasks asked
    again = _cache(law)
    GL.replay(again, leds, GL.made(leds), once=True)
    assert (again.grade.calls, again.grade.unions) == (1, 1)
