"""Lane `wells551` twins — A THING STANDING ON THE GROUND IS NOT A PIT
(issue #551; design spec §47 (8); owner OTHH read of 1.0.387: "No
tunnel/basin at these locations … all at the jetways").

OTHH's jetway objects carry a 4.3 m service room under the rotunda —
floor plate, stairs, machinery — whose ceiling is the apron.  Rule 1 read
the room's floor as a pit floor (a deep plate under a shell that tops out
at grade) and cut 35 pits.  The witness that separates it from the ten
real pits is the OBJECT'S OWN PROPORTION: a pit is deeper than it is tall
(Drainage 0.06 m over a 3.8–4.2 m floor, Dewatering 5.35 over 13.14),
a thing standing on the ground is taller than its foundation is deep
(every jetway 9.0 m over 4.3).  No new law number: height against depth.

* an open pit (nothing above its rim) is cut;
* the same pit with a building standing on it (one object, taller than
  the pit is deep) is refused, named `standing`;
* a pit under ANOTHER object's canopy stays a pit — the witness is read
  per object, never across placements.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.basin_witness import basin_member_ids, read_objects
from auto_patch_v2.classify.roles import Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import (Airport, Building, DsfObject, Pavement,
                                         Runway, RunwayEnd, SceneryPack)
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.basins import build_basins

from test_m4b import _box_obj, _rect, _two_box_obj
from test_v2basinfix import _FlatDem, _cells

HX, HZ = 30.0, 20.0


def _tower_on_pit(path, hx, hz, depth, height):
    """A box pit with a BUILDING standing on it as a SEPARATE welded
    component (the jetway's shape: the room's ceiling is the apron, the
    rotunda above is another solid) — one object, taller than deep.  A
    building WELDED to the pit's rim is already rule 1's `through_grade`
    (one component through the ground); this is the case it misses."""
    return _two_box_obj(path,
                        dict(hx=hx, hz=hz, depth=depth),
                        dict(hx=hx, hz=hz, depth=-0.05, top=height, lid=True))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def objs(tmp_path_factory, law):
    d = tmp_path_factory.mktemp("wells551_pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text(
        "I\n1000 Version\n", encoding="utf-8", newline="")
    dd = law.tables.structures.basin.admission_depth_m
    return {
        "dir": d,
        "pit": _box_obj(d / "pit.obj", hx=HX, hz=HZ, depth=2.0 * dd),
        # a building 9 m tall standing over a pit 5 m deep (the jetway's
        # proportion: 9.0 over 4.3)
        "tower": _tower_on_pit(d / "tower.obj", HX, HZ, 2.0 * dd, 9.0),
        # a thin canopy 8 m up over the whole pit footprint — ANOTHER object
        "canopy": _box_obj(d / "canopy.obj", hx=HX + 2, hz=HZ + 2, depth=-7.0,
                           top=8.0, floor=True, lid=True),
    }


def _airport(objs, law, names, dem):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 697.0, "fixture"),
            RunwayEnd("27", (600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 703.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", str(objs["dir"].parent / "Earth nav data" / "apt.dat"),
                       "0", (), ())
    blds = (Building("dsf:object0", _rect(-HX, -HZ, HX, HZ), (), "dsf:object:building",
                     None, None),)
    apron = Pavement("pav1", 1, _rect(-150.0, -140.0, 150.0, -60.0), (), "apron")
    dsf = tuple(DsfObject(f"dsf:obj{i}", f"objects/{n}.obj", (0.0, 0.0), 0.0, None, False,
                          None, 0.0, str(objs[n]), "OBJECT") for i, n in enumerate(names))
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (apron,), (), {}, (), (),
                   (), (), (), blds, dsf, pack, dem, law.ruleset_key)


def _read(objs, law, names):
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    a = _airport(objs, law, names, _FlatDem())
    objects, rep = read_objects(a, law, cache)
    _cl, basins, stats = build_basins(a, Classification(tuple(_cells()), (), {}, ()),
                                      law, (), objects, cache=cache, report=rep)
    # the classify-time membership (10ax (2)) reads the same witnesses
    members = basin_member_ids(a, law, cache)
    return objects, rep, list(basins), stats, members


def test_an_open_pit_is_cut(objs, law):
    objects, rep, basins, stats, members = _read(objs, law, ["pit"])
    assert rep.standing == {} and len(basins) == 1
    assert members == frozenset({"dsf:obj0"})


def test_a_building_standing_on_its_own_basement_is_not_a_pit(objs, law):
    """§47 (8): the object's solid top stands 9 m above the ground, its
    deepest plate 5 m below it — a thing standing on the ground; every
    witness of the placement is refused and named with both numbers."""
    objects, rep, basins, stats, members = _read(objs, law, ["tower"])
    assert basins == []
    assert list(rep.standing) == ["objects/tower.obj"]
    n, top, depth = rep.standing["objects/tower.obj"]
    assert n == 1 and top == pytest.approx(9.0, abs=0.3) and depth == pytest.approx(-5.0, abs=0.3)
    assert members == frozenset()
    assert any("standing on the ground" in r for r in stats.refused), stats.refused


def test_a_pit_under_another_objects_canopy_stays_a_pit(objs, law):
    """The witness is read per OBJECT: a canopy of another placement over
    the pit is cover (reported, 04i rule 4's own-cover test unchanged),
    never the pit's own height."""
    objects, rep, basins, stats, members = _read(objs, law, ["pit", "canopy"])
    assert rep.standing == {}
    assert len(basins) == 1 and basins[0].covered_fraction > 0.5
    assert "dsf:obj0" in members
