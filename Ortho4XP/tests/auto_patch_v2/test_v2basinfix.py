"""Lane `v2basinfix` twins — A BASIN IS A FACILITY, NOT A SKIRT (owner
RULINGS 2026-09-10ax (2)).

What happened at LEMD on app 1.0.310 (bisected in this lane: the loss is
v2skirt, `796109cc`, merged `54b8091e`, shipped in 1.0.309 `4c1ca124`):
the T4S pit's OWN members `Ground-FSX-LEMD36`/`LEMD85` read foundation
skirts of 7.01/7.03 m — a pit IS uniform below-zero extent across its
footprint — so `classify/evidence._drop_skirted` dropped the T4S terminal
pad `building16` (94 % covered, relief 4.65 m <= 7.01 m).  With that pad
gone the OSM road bore `-5970` was no longer refused ("the mouth stands
against building pad building16"), its ramp became a `kind == "structure"`
cell on the pit's rim, and `planar/basins` rule 5 refused the basin
itself: "27557 m2 overlaps a tunnel structure".  `basin_facilities` 1 ->
0, the pit went uncut, and `Ground-FSX-LEMD37` was seated onto the uncut
surface — the owner's "lip 2 m above the apron".

The rule: the basin admission (rule 1, 09ak's authored depth against the
object's own datum) runs FIRST — `airport/basin_witness.basin_member_ids`
— and its members are exempt at the ONE derivation site of "skirted"
(`airport/skirt.skirted_placements`, which `_drop_skirted` and
`emit/clusters` both read) and from `airport/rebake_plan`'s per-component
below-grade skip.  A skirt is a foundation under a building that stands
ABOVE the ground; a basin's members are the pit.

Law values are read from the tables inside the tests, never retyped.
"""
from __future__ import annotations

import dataclasses as _dc

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.airport import obj8, skirt
from auto_patch_v2.airport.basin_witness import basin_member_ids, read_objects
from auto_patch_v2.airport.rebake_plan import plan as rebake_plan
from auto_patch_v2.classify import load_rules
from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.classify.roles import classify
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import (Airport, Building, DsfObject, Pavement,
                                         Runway, RunwayEnd, SceneryPack)
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.basins import build_basins

from test_m4b import _box_obj, _rect
from test_v2skirt import HX as SHX, HZ as SHZ, _box

HX, HZ = 30.0, 20.0                      # the fixture pit: 60 x 40 m in plan
SKIRT_M = 2.0                            # the skirted box's foundation depth


class _FlatDem:
    provenance = {"synthetic": "flat 700"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


class _Slope:
    """A plane rising in x — the relief a skirt is allowed to hide."""

    def __init__(self, grade: float) -> None:
        self.grade = grade
        self.provenance = {"synthetic": f"plane {grade:.3%} up-slope in x"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + self.grade * x

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def objs(tmp_path_factory, law):
    d = tmp_path_factory.mktemp("v2basinfix_pack") / "objects"
    d.mkdir()
    (d.parent / "Earth nav data").mkdir()
    (d.parent / "Earth nav data" / "apt.dat").write_text("I\n1000 Version\n")
    dd = law.tables.structures.basin.admission_depth_m
    return {
        "dir": d,
        # THE PIT (the OTHH / T4S shape): four walls from its own datum
        # down to twice the admission depth, and a FLOOR PLATE there.
        "pit": _box_obj(d / "pit.obj", hx=HX, hz=HZ, depth=2.0 * dd),
        # A SKIRTED BOX BUILDING (v2skirt's own fixture, one
        # implementation): walls rising 8 m ABOVE the ground over a
        # uniform foundation slab — 10ag's building, never a pit.
        "skirtbox": _box(d / "skirtbox.obj", skirt_depth=SKIRT_M),
    }


def _cache(law):
    return obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)


def _airport(objs, law, name, dem, hx=HX, hz=HZ):
    """One placement of ``name`` at the frame origin, a building footprint
    over it (the pad candidate) and an apron beside it (the pad gate)."""
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 697.0, "fixture"),
            RunwayEnd("27", (600.0, 522.5), (60.5, -135.5), 0.0, 0.0, 703.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", str(objs["dir"].parent / "Earth nav data" / "apt.dat"),
                       "0", (), ())
    ring = _rect(-hx, -hz, hx, hz)
    blds = (Building("dsf:object0", ring, (), "dsf:object:building", None, None),)
    apron = Pavement("pav1", 1, _rect(-150.0, -140.0, 150.0, -60.0), (), "apron")
    dsf = (DsfObject("dsf:obj0", f"objects/{name}.obj", (0.0, 0.0), 0.0, None, False,
                     None, 0.0, str(objs[name]), "OBJECT"),)
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (apron,), (), {}, (), (),
                   (), (), (), blds, dsf, pack, dem, law.ruleset_key)


def _cells():
    return [Cell(1, "apron", "pav1", _rect(-150, -140, 150, -60), (), None, None,
                 "airside", "apron", {})]


# ── the pit stays a basin with the skirt reader ON ───────────────────────

def test_a_pit_reads_as_a_skirt_by_resource_but_is_never_a_skirted_placement(objs, law):
    """The interventional pair, both sides in one test: the RESOURCE
    reader still calls the pit's below-zero geometry uniform (that is the
    fact that broke LEMD — a pit and a foundation are the same shape), and
    the PLACEMENT is nevertheless not skirted, because the basin admission
    ran first and claimed it."""
    cache = _cache(law)
    r = skirt.reading(cache, str(objs["pit"]), law)
    assert r.skirt and r.depth_m is not None                 # the fact
    assert r.perimeter_fraction >= law.tables.structures.skirt.perimeter_fraction
    a = _airport(objs, law, "pit", _FlatDem())
    assert basin_member_ids(a, law, cache) == {"dsf:obj0"}   # admitted FIRST
    depths, _c = skirt.skirted_placements(a, law, cache)
    assert depths == {}                                      # the exemption


def test_the_pad_over_a_pit_is_not_dropped_and_the_basin_is_admitted(objs, law):
    """The LEMD chain, end to end on the fixture: the pad above the pit
    stands (so whatever the pad guards — at LEMD, a road bore's mouth —
    keeps its refusal), and the basin itself is admitted with its floor at
    the plate."""
    bl = law.tables.structures.basin
    cache = _cache(law)
    a = _airport(objs, law, "pit", _FlatDem())
    cl = classify(a, law, load_rules(), cache=cache)
    assert cl.stats.get("pads_skirted") == 0
    assert [c.ref for c in cl.cells if c.role == "building"] != []
    objects, rep = read_objects(a, law, cache)
    _cl, basins, _stats = build_basins(a, Classification(tuple(_cells()), (), {}, ()),
                                       law, (), objects, cache=cache, report=rep)
    assert len(basins) == 1
    assert basins[0].floor_z == pytest.approx(700.0 - 2.0 * bl.admission_depth_m, abs=0.3)


def test_a_skirted_box_building_is_not_a_basin(objs, law):
    """The other side of the rule: a building on a uniform foundation —
    walls rising above the ground, no floor plate under it — is NOT a
    basin member, stays skirted, and still drops its pad under 10ag."""
    cache = _cache(law)
    a = _airport(objs, law, "skirtbox", _Slope(0.5 * SKIRT_M / (2.0 * SHX)),
                 hx=SHX, hz=SHZ)
    assert basin_member_ids(a, law, cache) == frozenset()
    depths, _c = skirt.skirted_placements(a, law, cache)
    assert set(depths) == {"dsf:obj0"}
    cl = classify(a, law, load_rules(), cache=_cache(law))
    assert cl.stats.get("pads_skirted") == 1
    assert [c.ref for c in cl.cells if c.role == "building"] == []
    # and no basin: nothing witnesses a floor
    objects, rep = read_objects(a, law, cache)
    _cl, basins, _stats = build_basins(a, Classification(tuple(_cells()), (), {}, ()),
                                       law, (), objects, cache=cache, report=rep)
    assert basins == ()


# ── the below-grade skip (10ax (2), second site) ─────────────────────────

def test_a_basin_member_is_never_skipped_below_grade(objs, law):
    """09w (1)'s skip removes a placement whose every genuine component
    stands under its ground — which is every member of a pit.  A basin's
    members are exempt: the basin's own exclusion / plate seat governs
    them, and the family is not stranded at its authored y while the
    terrain moves under it."""
    cache = _cache(law)
    a = _airport(objs, law, "pit", _FlatDem())
    objects, _rep = read_objects(a, law, cache)
    region = Polygon(_rect(-HX - 5.0, -HZ - 5.0, HX + 5.0, HZ + 5.0))
    plan_in = rebake_plan(a, objects, cache, law,
                          below_grade=[(region, ("objects/pit.obj",))])
    assert plan_in.counts["below_grade"] == 0
    assert not any("below-grade solids" in why for _r, why in plan_in.skipped)
    # the interventional arm: the SAME plan with no basin region — the
    # member is below grade and the skip takes it
    plan_out = rebake_plan(a, objects, cache, law)
    assert plan_out.counts["below_grade"] == 1
    assert any("below-grade solids" in why for _r, why in plan_out.skipped)


# ── the read is shared, not repeated ─────────────────────────────────────

def test_the_pack_is_read_once_for_both_stages(objs, law):
    """The admission asked at classify time must cost the planar pass
    nothing: one reading, memoised on the shared cache (v2skirt's
    pattern)."""
    cache = _cache(law)
    a = _airport(objs, law, "pit", _FlatDem())
    first, _rep = read_objects(a, law, cache)
    again, _rep2 = read_objects(a, law, cache)
    assert again is first
    assert basin_member_ids(a, law, cache) == {"dsf:obj0"}


def test_an_airport_without_a_dem_admits_no_basin_member(objs, law):
    """Rule 1 judges a floor against the LOCAL GROUND: with no terrain to
    judge against there is no basin, and the skirt reader is unchanged."""
    cache = _cache(law)
    a = _dc.replace(_airport(objs, law, "pit", _FlatDem()), dem=None)
    assert basin_member_ids(a, law, cache) == frozenset()
