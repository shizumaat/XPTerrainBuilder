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


# ── ROUND 2: THE FLOOR IS THE OBJECT'S DEPTH BELOW THE RIM (10ba) ────────
#
# The rim follows the pavement (10an/10ar) and the FLOOR follows the rim:
# every floor-ring vertex stands ``body_depth_m`` under its nearest rim
# vertex, replacing the absolute pin at ``DEM(anchor) + agl + plate_y``.
# At LEMD that pin left the floor at 588.95 under a rim on the apron at
# 597.3–597.9 — an 8.3–9.0 m cut for a 7.05 m object, and LEMD37's
# authored wall crest (−1.88) 3.1–3.8 m under the rim instead of 10aq's
# 1.9 m.  Spec §22.1c.

import numpy as _np                                                # noqa: E402

from auto_patch_v2.constraints import generate as _generate        # noqa: E402
from auto_patch_v2.constraints.structures import (                 # noqa: E402
    BASIN_FLOOR_RULING)
from auto_patch_v2.constraints.structures import basins as _basin_rows  # noqa: E402
from auto_patch_v2.model.constraints import Linear as _Linear, Pin as _Pin  # noqa: E402
from auto_patch_v2.model.structures import Basin as _Basin         # noqa: E402
from auto_patch_v2.planar.build import build as _build             # noqa: E402
from auto_patch_v2.solve import Status as _Status, solve_design as _solve  # noqa: E402
from auto_patch_v2.solve.design import hard_rulings as _hard_rulings  # noqa: E402

from test_v2pit2 import (FLOOR as _F_RING, RIM as _RIM, _apron_plane,  # noqa: E402
                         _cells as _pit_cells, _contacts, _face)

#: the T4S object: 7.05 m of body under its own rim (the sidecar's
#: ``body_depth_m`` / ``-solid_minimum_y_m``)
T4S_DEPTH_M = 7.05
#: the floor the ABSOLUTE pin would have used — 3 m under the apron at the
#: anchor, which is what the excavated production DEM reads at LEMD
DEM_PIT_DROP_M = 3.0


class _ApronSlope:
    """A 1 % plane falling east — the apron the rim sits in.  ``pit_drop``
    sinks the DEM inside the rim (LEMD's production DEM already contains
    Aerosoft's basement), which is exactly the reading the absolute floor
    pin took as its datum."""

    def __init__(self, pit_drop: float = 0.0) -> None:
        self.pit_drop = pit_drop
        self.provenance = {"synthetic": f"1 % plane, pit drop {pit_drop:.1f} m"}

    def z(self, x: float, y: float) -> float:
        z = 700.0 + 0.01 * x
        if self.pit_drop and -44.0 <= x <= 44.0 and 136.0 <= y <= 204.0:
            return z - self.pit_drop
        return z

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


class _FlatApron(_ApronSlope):
    """OTHH's site: a flat DEM under flat aprons, where the rim IS R_est."""

    provenance = {"synthetic": "flat 700"}

    def z(self, x: float, y: float) -> float:
        return 700.0


def _pit_airport(law, dem, depth=T4S_DEPTH_M, rim_est=700.0):
    from auto_patch_v2.classify.roles import Classification as _Cl
    from auto_patch_v2.model.airport import (Airport as _Ap, Runway as _Rw,
                                             RunwayEnd as _Re, SceneryPack as _Sp)
    from auto_patch_v2.model.frame import Frame as _Fr
    cells = _pit_cells("basin_wall:0", "basin_floor:0")
    frame = _Fr("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (_Re("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            _Re("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 706.0, "fixture"))
    pack = _Sp("fixture", "apt.dat", "0", (), ())
    airport = _Ap("ZZZZ", "Synthetic", frame, 700.0, (_Rw("09/27", 45.0, 1, ends, 3, "D"),),
                  (), (), {}, (), (), (), (), (), (), (), pack, dem, law.ruleset_key)
    pm, _st = _build(airport, _Cl(tuple(cells), (), {}, ()), law)
    floor_z = rim_est - depth
    b = _Basin("basin:0", ("obj:fixture",), floor_z, "basin_floor:0", "basin_wall:0",
               tuple(_F_RING), wall_path=tuple(_RIM), rim_estimate_m=rim_est,
               solid_min_z=floor_z, solid_min_y_m=-depth, area_m2=4800.0)
    return airport, _dc.replace(pm, basins=(b,))


def _pit_solved(law, dem, **kw):
    airport, pm = _pit_airport(law, dem, **kw)
    cs, _counts, _walls = _generate(pm, law, airport)
    sol, rep = _solve(pm, cs, law)
    assert sol.status in (_Status.OPTIMAL, _Status.FEASIBLE), sol.status
    return airport, pm, _np.asarray(sol.z, float), rep


def _floor_to_rim(pm, law, airport):
    """Floor vertex -> the rim vertex its relative row names."""
    rows = _basin_rows(pm, law, airport)
    floor_vs = set(pm.ring_vertices(_face(pm, "basin_floor:0").ring))
    assert not any(isinstance(r, _Pin) and r.v in floor_vs for r in rows), \
        "10ba: a floor vertex carries no absolute datum any more"
    rel = [r for r in rows if isinstance(r, _Linear) and r.follows
           and set(r.follows) <= floor_vs]
    out = {v: next(u for u, c in r.terms if c < 0) for r in rel for v in r.follows}
    assert set(out) == floor_vs, "every floor vertex follows a rim vertex"
    return out


def test_the_floor_row_is_one_equality_that_names_the_rim_it_follows(law):
    """ONE ``Linear`` EQUALITY (``lo == hi``) per floor vertex, priced at
    the design solve's LAW weight, with ``follows`` naming the FLOOR: the
    floor follows, the rim is never pulled down into the pit.

    NOT two opposing one-sided rows in ``[design] hard_rulings``, which
    this lane measured first: both halves are AT their bound at the
    solution, so the augmented-Lagrangian polish escalates them against
    each other (LEMD: 1305/128088 hard rows active, max violation
    0.3019 m, HARD SET NOT SETTLED, adjudicated 580 -> 1259)."""
    assert BASIN_FLOOR_RULING not in _hard_rulings(law)
    airport, pm = _pit_airport(law, _ApronSlope())
    rows = _basin_rows(pm, law, airport)
    rel = [r for r in rows if isinstance(r, _Linear)]
    assert rel, "the relative floor rows exist"
    floor_vs = set(pm.ring_vertices(_face(pm, "basin_floor:0").ring))
    for r in rel:
        assert r.source.ruling.startswith(BASIN_FLOOR_RULING)
        assert set(r.follows) <= floor_vs
        assert r.lo == r.hi == pytest.approx(-T4S_DEPTH_M)


def test_a_pit_in_a_sloped_apron_hangs_its_floor_under_the_rim(law):
    """(1) A 1 % apron: the rim comes out ON the apron's own plane (10an)
    and every floor vertex stands the object's 7.05 m under the rim it
    follows — the floor is a TILTED plate under a tilted rim, not a level
    declared somewhere else."""
    airport, pm, z, _rep = _pit_solved(law, _ApronSlope())
    plane = _apron_plane(pm, z)
    contacts = _contacts(pm)
    assert contacts
    assert max(abs(float(z[v]) - plane(v)) for v in contacts) <= 0.05
    rim_of = _floor_to_rim(pm, law, airport)
    worst = max(abs(float(z[v]) - (float(z[u]) - T4S_DEPTH_M))
                for v, u in rim_of.items())
    assert worst <= 0.05, f"the floor stands {worst:.3f} m off rim - 7.05"
    # and the rim really is not flat here: the law has something to follow
    assert max(float(z[u]) for u in set(rim_of.values())) \
        - min(float(z[u]) for u in set(rim_of.values())) > 0.3


def test_the_dem_under_the_anchor_is_not_the_floors_datum(law):
    """(2) The LEMD frame: the production DEM inside the rim already
    carries the basement, so the ABSOLUTE pin's datum sat 3 m under the
    apron.  Under 10ba the floor is unchanged by that reading — the two
    arms differ by less than the materiality floor, and neither floor is
    3 m lower."""
    airport_a, pm_a, z_a, _ra = _pit_solved(law, _ApronSlope())
    airport_b, pm_b, z_b, _rb = _pit_solved(law, _ApronSlope(DEM_PIT_DROP_M))
    rim_a, rim_b = _floor_to_rim(pm_a, law, airport_a), _floor_to_rim(pm_b, law, airport_b)
    assert set(rim_a) == set(rim_b), "the same fixture geometry, one DEM apart"
    worst = max(abs(float(z_b[v]) - (float(z_b[u]) - T4S_DEPTH_M))
                for v, u in rim_b.items())
    assert worst <= 0.05, f"the excavated DEM moved the floor {worst:.3f} m"
    # the DROP is invariant to the DEM inside the rim; the floor's LEVEL
    # still moves with the rim, because the rim follows the pavement and
    # the apron body's own datum reads those samples (10ar's residual)
    drop_a = {v: float(z_a[v]) - float(z_a[u]) for v, u in rim_a.items()}
    drop_b = {v: float(z_b[v]) - float(z_b[u]) for v, u in rim_b.items()}
    drift = max(abs(drop_a[v] - drop_b[v]) for v in drop_a)
    assert drift <= 0.05, f"the DEM at the anchor moved the drop {drift:.3f} m"
    # and the floor is NOT the old absolute datum: the pin would have taken
    # the excavated DEM under the anchor, 3 m lower
    old_datum = 700.0 - DEM_PIT_DROP_M - T4S_DEPTH_M
    lift = min(float(z_b[v]) for v in rim_b) - old_datum
    assert lift > 1.5, f"the floor is only {lift:.2f} m off the excavated datum"


def test_a_flat_rim_reproduces_the_absolute_pin(law):
    """(3) OTHH's site is unchanged BY CONSTRUCTION: its pits' rims sit in
    flat aprons on a flat DEM, so ``rim - body_depth`` IS the absolute
    floor the pin declared, to the materiality floor."""
    airport, pm, z, _rep = _pit_solved(law, _FlatApron())
    declared = pm.basins[0].floor_z
    rim_of = _floor_to_rim(pm, law, airport)
    for v, u in rim_of.items():
        assert float(z[v]) == pytest.approx(float(z[u]) - T4S_DEPTH_M, abs=0.05)
        assert float(z[v]) == pytest.approx(declared, abs=0.05)
