"""RULINGS 2026-09-09q (1): a structure the terrain adapted to (a wall
corridor / basin / tunnel member) excludes THAT MEMBER from the re-seat,
never its ANCHOR FAMILY.

The measured failure: Aerosoft anchors the whole LEMD terminal pack at
two origin points, so the 28 wall-corridor members' ids — expanded to
their anchor family by the deleted ``[rebake] structure_family_excluded``
— took 300 placements out of the re-seat and left them at their authored
y over 32 m of relief (worst +36.4 m sunk, −31.8 m floating).

Twins here, sharing ``test_m6a_rebake``'s synthetic pack:

1. a family of THREE at one anchor spelling, one member a corridor wall:
   the wall stays out, the other two seat (and stay ONE unit);
2. the law key is gone — nothing may re-introduce the expansion;
3. the excluded member is still excluded when named by PATH (the basin
   records' spelling), and still only itself.
"""
from __future__ import annotations

import pytest

from auto_patch_v2.airport import obj8
from auto_patch_v2.airport.rebake_plan import plan as _plan
from auto_patch_v2.law import Law
from auto_patch_v2.planar.basins import read_objects

from test_m6a_rebake import _airport, _box_obj, law, pack   # noqa: F401


@pytest.fixture(scope="module")
def family(pack, law):                                      # noqa: F811
    """Three resources at ONE anchor spelling (0, 0), heading apart —
    ``family_key`` is the anchor position, so all three share it."""
    d = pack / "objects"
    for name in ("wall", "sib1", "sib2"):
        _box_obj(d / f"{name}.obj", 7.0, 5.0, 2.0)
    a = _airport(pack, law, [
        ("wall", (0.0, 0.0), 0.0, 0.0),
        ("sib1", (0.0, 0.0), 90.0, 0.0),
        ("sib2", (0.0, 0.0), 180.0, 0.0),
    ])
    objs, _ = read_objects(a, law)
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    for o in objs:
        if o.resolved:
            cache.geometry(o.resolved)
    return a, objs, cache


def _plan_excluding(family, law, exclude):                  # noqa: F811
    a, objs, cache = family
    return _plan(a, objs, cache, law, exclude=exclude)


def _wall_id(family):
    _a, objs, _c = family
    return next(o.id for o in objs if o.path.endswith("wall.obj"))


def test_the_family_is_one_unit_when_nothing_is_excluded(family, law):  # noqa: F811
    pl = _plan_excluding(family, law, ())
    assert pl.counts["terrain_adapted"] == 0
    assert pl.counts["units"] == 1 and pl.counts["members"] == 3


def test_a_corridor_wall_excludes_only_itself(family, law):  # noqa: F811
    """The ruling: the wall stays out; its two anchor siblings seat."""
    pl = _plan_excluding(family, law, (_wall_id(family),))
    assert pl.counts["terrain_adapted"] == 1
    seated = {m.resource for u in pl.units for m in u.members}
    assert seated == {"objects/sib1.obj", "objects/sib2.obj"}
    assert "objects/wall.obj" in dict(pl.skipped)
    # ...and the survivors are still ONE body at the shared anchor (09d)
    assert pl.counts["units"] == 1 and pl.counts["members"] == 2


def test_the_exclusion_also_takes_the_resource_PATH_spelling(family, law):  # noqa: F811
    pl = _plan_excluding(family, law, ("objects/wall.obj",))
    assert pl.counts["terrain_adapted"] == 1
    assert {m.resource for u in pl.units for m in u.members} == {
        "objects/sib1.obj", "objects/sib2.obj"}


def test_the_family_expansion_key_is_deleted():
    """No caller may switch the expansion back on (RULINGS 09q (1))."""
    rb = Law.for_airport("ZZZZ").tables.structures.rebake
    assert not hasattr(rb, "structure_family_excluded")


# ── RULINGS 2026-09-09s: the plate family withdrawn; per-component ground
#    seating (round 2) ─────────────────────────────────────────────────────

import statistics                                             # noqa: E402

from auto_patch_v2.emit import rebake as R                    # noqa: E402
from test_m6b_deck import _boxes_obj                          # noqa: E402

ORIGIN = (60.5, -135.5)


def _slope_sampler(z0: float, per_m: float):
    """Ground rising ``per_m`` metres per metre EAST of the frame origin —
    LINEAR, so a part's median over symmetric feet is its centre value."""
    from auto_patch_v2.emit import clusters as C
    _m_lat, m_lon = C.metres_per_degree(ORIGIN[0])

    def f(lat, lon):
        return (z0 + (lon - ORIGIN[1]) * m_lon * per_m, False)
    return f


def _planned(pack, law, placements):                          # noqa: F811
    a = _airport(pack, law, placements)
    objs, _ = read_objects(a, law)
    cache = obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    for o in objs:
        if o.resolved:
            cache.geometry(o.resolved)
    return _plan(a, objs, cache, law)


@pytest.fixture(scope="module")
def scatter(pack, law):                                       # noqa: F811
    """ONE resource carrying three buildings 500 m apart (a scatter file:
    `LEMD_OBJ-grass_FSX-LEMDgrass.obj` spans 10,493 m), and one carrying a
    building with a canopy floating 0.1 m over its roof."""
    d = pack / "objects"
    _boxes_obj(d / "scatter.obj", [(200.0, 0.0, 10.0, 10.0, 0.0, 5.0),
                                   (700.0, 0.0, 10.0, 10.0, 0.0, 5.0),
                                   (1200.0, 0.0, 10.0, 10.0, 0.0, 5.0)])
    _boxes_obj(d / "canopy.obj", [(200.0, 0.0, 10.0, 10.0, 0.0, 5.0),
                                  (200.0, 0.0, 12.0, 12.0, 5.1, 5.6)])
    return d


def test_a_scatter_files_buildings_each_land_on_their_own_ground(scatter, pack, law):  # noqa: F811
    """RULINGS 2026-09-09s (2): three buildings in ONE file over 10 m of
    relief — no rigid delta seats them.  Each connected component is its
    own contact structure and reads the mesh under ITS OWN FEET, so each
    lands on its own ground (the residual at every foot is nil)."""
    pl = _planned(pack, law, [("scatter", (0.0, 0.0), 0.0, 0.0)])
    m = pl.units[0].members[0]
    assert len(m.parts) == 3 and all(p.feet for p in m.parts)
    assert pl.counts["contacts"] == 0                 # 500 m apart: three structures
    res = R.seat(pl, _slope_sampler(700.0, 0.01), law)   # +10 m over the 1,000 m span
    seat = res.units[0].members[0]
    assert seat.delta_m is None                        # one file, three deltas (06g)
    ds = sorted(d for _c, _k, d in seat.part_deltas)
    assert ds == pytest.approx([2.0, 7.0, 12.0], abs=1e-3)   # mm from the 8-dp plan
    assert res.counts()["clusters"] == 3 and res.counts()["clusters_baked"] == 3
    # ...and every building's FEET land on the mesh under them (the bar the
    # scout measures: the WORST foot).  A 20 m box on a 1 % slope leaves
    # ±0.10 m at its corners by construction — the median is nil
    smp = _slope_sampler(700.0, 0.01)
    for (_c, _k, delta), p in zip(sorted(seat.part_deltas), sorted(m.parts, key=lambda q: q.lon)):
        rs = [700.0 + delta + y - smp(la, lo)[0] for la, lo, y in p.feet]
        assert max(abs(r) for r in rs) < 0.11
        assert statistics.median(rs) == pytest.approx(0.0, abs=1e-3)


def test_a_floating_canopy_follows_the_walls(scatter, pack, law):   # noqa: F811
    """The other half of 09s (2): a component with no GROUND feet is never
    seated on the ground under itself — the canopy 0.1 m over the roof is
    ELEVATED (v1 I-8), inherits the walls' cluster and takes their delta."""
    pl = _planned(pack, law, [("canopy", (0.0, 0.0), 0.0, 0.0)])
    m = pl.units[0].members[0]
    assert len(m.parts) == 2 and pl.counts["contacts"] == 1
    walls = next(p for p in m.parts if p.base_y == pytest.approx(0.0))
    lid = next(p for p in m.parts if p.base_y == pytest.approx(5.1))
    assert walls.feet and not lid.feet                 # only the walls carry feet
    res = R.seat(pl, _slope_sampler(700.0, 0.01), law)
    seat = res.units[0].members[0]
    assert seat.delta_m == pytest.approx(2.0, abs=1e-3)   # ONE delta for the file
    assert len({d for _c, _k, d in seat.part_deltas}) == 1


def test_a_plate_seats_its_own_object_never_its_anchor_family(family, law):  # noqa: F811
    """RULINGS 2026-09-09s (1): 05n-4's family expansion is withdrawn.  The
    wall object carries the plate; its two anchor siblings are planned as
    ordinary members and seat by their own clusters."""
    a, objs, cache = family
    wall = next(o for o in objs if o.path.endswith("wall.obj"))
    pl = _plan(a, objs, cache, law,
               tunnel_objects={wall.id: (1.0, ((0.0, 0.0), (2.0, 0.0)))})
    assert pl.counts["plate_members"] == 1 and pl.counts["plate_objects"] == 1
    by = {m.resource: m for u in pl.units for m in u.members}
    assert by["objects/wall.obj"].plate_y == pytest.approx(1.0)
    assert by["objects/sib1.obj"].plate_y is None and by["objects/sib2.obj"].plate_y is None
    res = R.seat(pl, lambda la, lo: (704.0, False), law)
    u = res.units[0]
    seats = {m.resource: m for m in u.members}
    # the plate: ground 704 − (base 704 + plate 1.0) = −1.0, that object only
    assert u.datum == R.DATUM_PLATE and seats["objects/wall.obj"].delta_m == pytest.approx(-1.0)
    assert seats["objects/wall.obj"].founding
    # the siblings: their own cluster, seated by their FEET (base_y −2 under
    # a mesh of 704 → the y = 0 plane wants 706, delta +2) — never the plate's
    for n in ("sib1", "sib2"):
        assert seats[f"objects/{n}.obj"].datum == R.DATUM_CLUSTER
        assert seats[f"objects/{n}.obj"].delta_m == pytest.approx(2.0)


def test_a_facility_cluster_still_stays(law):                 # noqa: F811
    """05p / 05q are untouched by 09s: a member standing more than
    `contact_band_m` under the mesh, outside its structure's at-grade
    coalition, keeps its authored y."""
    band = law.tables.structures.basin.contact_band_m

    def member(name, lat):
        p = R.Part(int(lat * 1000), 0, lat, 0.0, 0.0, 100.0,
                   (lat - 1e-5, -1e-5, lat + 1e-5, 1e-5), ((lat, 0.0, 0.0),))
        return R.Member(name, f"objects/{name}.obj", name, name, 0.0, (p,))
    ms = [member(f"Terminal_{i}", 0.001 * (i + 1)) for i in range(3)]
    road = member("TerminalRoads_03_004", 0.004)
    pl = R.RebakePlan("ZZZZ", "p", "/p",
                      (R.Unit("unit:21", (0.0, 0.0), 0.0, (*ms, road)),), (), {},
                      ((1, 2), (2, 3), (3, 4)))
    table = {0.0: 710.0, 0.001: 710.0, 0.002: 710.0, 0.003: 710.0,
             0.004: 710.0 + band + 1.5}
    res = R.seat(pl, lambda la, lo: (table[round(la, 6)], False), law)
    by = {m.resource: m for m in res.units[0].members}
    assert by["objects/TerminalRoads_03_004.obj"].facility
    assert res.counts()["clusters_facility"] == 1


def test_a_plan_without_feet_reads_as_it_did_before_09s(law):   # noqa: F811
    """The fallback: a part with no recorded feet (a version-5 plan, a
    hand-built one) is GROUND by `base_y ≤ elevated_base_m` and reads ONE
    foot at its centroid carrying `base_y` — the pre-09s reading."""
    p = R.Part(0, 0, 0.001, 0.0, 0.0, 100.0, (0.0, -1e-5, 0.002, 1e-5))
    m = R.Member("m", "objects/m.obj", "m", "m", 0.0, (p,))
    pl = R.RebakePlan("ZZZZ", "p", "/p", (R.Unit("u", (0.0, 0.0), 0.0, (m,)),), (), {}, ())
    res = R.seat(pl, lambda la, lo: (710.0 if la else 700.0, False), law)
    assert res.units[0].members[0].delta_m == pytest.approx(10.0)
    assert res.clusters[0].ground_m == pytest.approx(710.0)
