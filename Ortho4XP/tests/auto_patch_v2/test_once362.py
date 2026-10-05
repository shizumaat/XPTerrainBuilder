"""Issue #362 twins: the CLASSIFICATION-FREE pack reads of the planar
build (tunnel corridors, thin plates, door wells, sunken roads, wall
corridors, and the basin pass's per-ring readings) run ONCE per build —
the ribbon-free second pass (#100 (c)) is handed the first pass's reading
(``planar/pack_reads``), and its planar map is the one a fresh read
builds.  Synthetic, offline."""
from __future__ import annotations

import dataclasses as _dc

import pytest

from auto_patch_v2.airport import frame_entry as _fe
from auto_patch_v2.airport.obj8 import ResourceCache
from auto_patch_v2.classify import classify
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline.stage_one_map import ribbon_free
from auto_patch_v2.planar import pack_reads as _pr
from auto_patch_v2.planar.build import build as planar_build

from test_roadmint100 import SOUTH, _SlopeDem, _way, _with

READERS = ("read_corridors", "read_plates", "read_door_wells", "read_sunken_roads",
           "read_wall_corridors")


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _cache(law):
    return ResourceCache(law.tables.structures.basin.min_solid_thickness_m,
                         _fe.quantum(law))


def _counted(monkeypatch):
    calls = {n: 0 for n in READERS}
    for n in READERS:
        real = getattr(_pr, n)

        def spy(*a, _n=n, _real=real, **k):
            calls[_n] += 1
            return _real(*a, **k)
        monkeypatch.setattr(_pr, n, spy)
    return calls


def _untimed(stats):
    """A stats record without its wall clocks (``*_s``)."""
    return {k: v for k, v in _dc.asdict(stats).items() if not k.endswith("_s")}


def _same_map(a, b):
    assert a.faces == b.faces
    assert a.edges == b.edges
    assert a.vertices == b.vertices
    assert a.breaklines == b.breaklines


def test_the_four_reads_run_once_across_both_planar_passes(law, monkeypatch):
    """A late (ribbon) cell makes the build run the planar prefix twice.
    The second pass — on the ribbon-free classification, with the airport
    RE-BOUND as the build re-binds it (the flat-site verdict) — calls no
    reader, and its map equals the one a fresh read (main's second pass)
    builds."""
    airport = _dc.replace(_with(_way(-3, SOUTH, highway="tertiary")), dem=_SlopeDem())
    cl = classify(airport, law)
    cl0 = ribbon_free(cl)
    assert cl0 is not None, "the fixture must carry a ribbon"
    calls = _counted(monkeypatch)
    cache, oo = _cache(law), []
    pm1, st1 = planar_build(airport, cl, law, objects_out=oo, cache=cache)
    assert calls == {n: 1 for n in READERS}
    rebound = _dc.replace(airport, flat_site=airport.flat_site)
    assert rebound is not airport
    pm0, _st0 = planar_build(rebound, cl0, law, cache=cache, objects=oo[0],
                             object_report=st1.basins.objects)
    assert calls == {n: 1 for n in READERS}
    # main's second pass: every read made afresh
    fresh, _f = planar_build(rebound, cl0, law, cache=_cache(law), objects=oo[0],
                             object_report=st1.basins.objects)
    assert calls == {n: 2 for n in READERS}
    _same_map(pm0, fresh)
    # and the first pass is untouched by the second
    again, st_again = planar_build(airport, cl, law, cache=_cache(law))
    _same_map(pm1, again)
    for name in ("tunnel_objects", "door_wells", "sunken_roads"):
        assert _untimed(getattr(st1, name)) == _untimed(getattr(st_again, name))


def test_a_reused_reading_equals_a_fresh_one_and_no_caller_can_write_it(law):
    """Deep equality of the handed-out reading with a fresh call, and the
    stats are each caller's OWN copy: the planar build appends to them
    (``sunken_groups`` -> ``refused``), which must not reach the next pass."""
    airport = _dc.replace(_with(), dem=_SlopeDem())
    cache, objects = _cache(law), []
    first = _pr.pack_reads(airport, objects, cache, law)
    first.road_stats.refused.append("written by the first pass")
    first.tunnel_stats.refused.append("written by the first pass")
    first.corridors.append("not a corridor")
    second = _pr.pack_reads(airport, objects, cache, law)
    fresh = _pr._read(airport, objects, _cache(law), law)
    for name in ("corridors", "plates", "wells", "roads"):
        assert getattr(second, name) == getattr(fresh, name)
    for name in ("tunnel_stats", "plate_stats", "door_stats", "road_stats"):
        assert _untimed(getattr(second, name)) == _untimed(getattr(fresh, name))
    assert second.road_stats.refused == []


def test_a_different_input_is_read_afresh(law, monkeypatch):
    """The reading is reused only while EVERY input is the same object —
    another object list, law or DEM is another reading."""
    airport = _dc.replace(_with(), dem=_SlopeDem())
    calls = _counted(monkeypatch)
    cache, objects = _cache(law), []
    _pr.wall_corridor_reads(airport, objects, cache, law)
    _pr.wall_corridor_reads(_dc.replace(airport), objects, cache, law)
    assert calls["read_wall_corridors"] == 1
    # ONE memo: another object list drops the wall reading with the rest
    _pr.pack_reads(airport, [], cache, law)
    _pr.wall_corridor_reads(airport, objects, cache, law)
    assert calls["read_wall_corridors"] == 2
    calls["read_door_wells"] = 0
    _pr.pack_reads(airport, objects, cache, law)
    _pr.pack_reads(_dc.replace(airport), objects, cache, law)
    assert calls["read_door_wells"] == 1
    _pr.pack_reads(airport, [], cache, law)
    assert calls["read_door_wells"] == 2
    _pr.pack_reads(_dc.replace(airport, dem=_SlopeDem()), objects, cache, law)
    assert calls["read_door_wells"] == 3
    _pr.pack_reads(airport, objects, cache, Law.for_airport("SYNT"))
    assert calls["read_door_wells"] == 4


def test_the_second_pass_prints_no_reader_progress(law):
    """The heartbeat stays truthful: a reused reading ticks no reader's
    label (``model/pulse``)."""
    from auto_patch_v2.model import pulse
    airport = _dc.replace(_with(), dem=_SlopeDem())
    cache, objects = _cache(law), []
    _pr.pack_reads(airport, objects, cache, law)
    pulse.tick("the caller's own step")
    _pr.pack_reads(airport, objects, cache, law)
    assert pulse.describe() == "the caller's own step"
    pulse.clear()


def test_the_wall_reading_is_each_callers_own(law):
    """The wall corridors come back as the caller's own list and its own
    copy of the stats, like the four."""
    airport = _dc.replace(_with(), dem=_SlopeDem())
    cache, objects = _cache(law), []
    walls, stats = _pr.wall_corridor_reads(airport, objects, cache, law)
    walls.append("not a corridor")
    stats.refused.append("written by the first pass")
    walls2, stats2 = _pr.wall_corridor_reads(airport, objects, cache, law)
    assert walls2 == [] and stats2.refused == []


# ── the basin pass's ring readings ───────────────────────────────────────

@pytest.fixture(scope="module")
def pit(tmp_path_factory):
    from auto_patch_v2.planar.basins import read_objects
    from test_m4b import _airport, _box_obj
    from test_v2basin import _FlatDem
    zlaw = Law.for_airport("ZZZZ")
    d = tmp_path_factory.mktemp("once362_pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text(
        "I\n1000 Version\n", encoding="utf-8", newline="")
    dd = zlaw.tables.structures.basin.admission_depth_m
    objs = {"dir": d, "pit": _box_obj(d / "pit.obj", hx=30.0, hz=20.0, depth=2.0 * dd)}
    airport = _dc.replace(_airport(objs, zlaw, [("pit", (0.0, 0.0), 0.0, 0.0)]),
                          dem=_FlatDem())
    cache = _cache(zlaw)
    objects, rep = read_objects(airport, zlaw, cache)
    return zlaw, airport, cache, objects, rep


def _basin_pass(pit, cells, reads, monkeypatch=None):
    """One basin pass; with ``monkeypatch``, the count of the pack readers
    it reached (the at-grade geometry, the cover, the ramp decks)."""
    from auto_patch_v2.classify.roles import Classification
    from auto_patch_v2.planar import basins as _b
    zlaw, airport, cache, objects, rep = pit
    n = {"grade": 0, "cover": 0, "ramps": 0}
    if monkeypatch is not None:
        for key, owner, name in (("grade", _b.obj8, "at_grade_geometry"),
                                 ("cover", _b.obj8, "above_grade_footprint"),
                                 ("ramps", _b._basin_witness, "ramp_decks")):
            real = getattr(owner, name)

            def spy(*a, _k=key, _real=real, **k):
                n[_k] += 1
                return _real(*a, **k)
            monkeypatch.setattr(owner, name, spy)
    cl = Classification(tuple(cells), (), {}, ())
    out = _b.build_basins(airport, cl, zlaw, (), objects, cache, report=rep, reads=reads)
    return out, n


def test_a_rings_pack_readings_are_made_once_and_equal_a_fresh_pass(pit, monkeypatch):
    """The second pass over the same ring and members — on ANOTHER
    classification — reaches no pack reader, and its cells, basins and
    notes are those of a pass that reads everything afresh."""
    from test_m4b import _cells
    zlaw, airport, cache, objects, _rep = pit
    reads = _pr.ring_reads(airport, objects, cache, zlaw)
    (_cl1, basins1, _s1), n1 = _basin_pass(pit, _cells(), reads, monkeypatch)
    assert len(basins1) == 1 and n1["grade"] and n1["cover"] and n1["ramps"]
    n1 = dict(n1)                           # the spies nest: keep this pass's count
    fewer = _cells()[:3]                    # the second pass's own cells
    (cl2, basins2, s2), n2 = _basin_pass(pit, fewer, reads, monkeypatch)
    assert n2 == {"grade": 0, "cover": 0, "ramps": 0}, \
        "the reused pass must reach no pack reader"
    (cl3, basins3, s3), n3 = _basin_pass(pit, fewer, None, monkeypatch)
    assert n3 == n1, "without the store every reading is made again"
    assert cl2 == cl3 and basins2 == basins3
    assert s2.refused == s3.refused and s2.rim_yields == s3.rim_yields


def test_a_ring_with_other_members_is_read_afresh(pit, monkeypatch):
    """The readings are keyed on the ring AND its members: a pass whose
    claimed set removes the member (no ring at all) reuses nothing, and
    the store scoped to another object list is another store."""
    from test_m4b import _cells
    zlaw, airport, cache, objects, rep = pit
    reads = _pr.ring_reads(airport, objects, cache, zlaw)
    assert _pr.ring_reads(airport, objects, cache, zlaw) is reads
    (_c, basins, _s), _n = _basin_pass(pit, _cells(), reads)
    assert len(basins) == 1 and all(k[0] in {"rim_open", "cover", "own_cover", "rim_wall",
                                             "ramps"} for k in reads)
    held = dict(reads)
    for k in list(reads):                   # a planted wrong answer per key
        if k[0] == "cover":
            reads[k] = 0.999
    (_c2, basins2, _s2), _n2 = _basin_pass(pit, _cells(), reads)
    assert basins2[0].covered_fraction == 0.999, "the key IS the ring: the store answers"
    reads.clear()
    reads.update(held)
    assert _pr.ring_reads(airport, list(objects), cache, zlaw) is not reads


def test_the_windowed_rim_index_answers_as_the_whole_objects_index_does():
    """prof362 row D: ``_rim_open`` asked of an index over the parts near
    the ring equals the same question asked of the whole object's index —
    parts at, just inside and just beyond the reach, far parts, an empty
    member, and a member with nothing near at all."""
    import random
    from shapely.geometry import LineString, MultiLineString, Polygon
    from auto_patch_v2.planar.basins import _rim_index, _rim_open
    rnd = random.Random(362)
    ring = Polygon([(0, 0), (40, 0), (40, 25), (0, 25)])
    reach, step = 2.0, 1.5
    for trial in range(40):
        members = []
        for _m in range(rnd.randint(1, 4)):
            lines = []
            for _k in range(rnd.randint(0, 30)):
                # hug one side at a distance drawn around the reach
                d = rnd.choice([reach, reach - 1e-9, reach + 1e-9,
                                rnd.uniform(0.0, 2.0 * reach), rnd.uniform(50.0, 900.0)])
                x0 = rnd.uniform(-5.0, 40.0)
                lines.append(LineString([(x0, -d), (x0 + rnd.uniform(0.5, 6.0), -d)]))
            members.append(MultiLineString(lines))
        whole = _rim_open(ring, (_rim_index(g) for g in members), step, reach)
        near = _rim_open(ring, (_rim_index(g, ring.bounds, reach) for g in members),
                         step, reach)
        assert near == whole, trial
    far = MultiLineString([LineString([(500, 500), (510, 500)])])
    assert _rim_index(far, ring.bounds, reach) is None and _rim_index(far) is not None
