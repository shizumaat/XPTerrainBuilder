"""FRONTAGE STEP 3, ROADS RAMP TO THE FRONTAGE (spec
``docs/specs/terminal-frontage-split-level-20261125.md`` §3.2; RULINGS
2026-11-25g (3)): a mapped road entering a two-floor block from its
groundside is on the block's groundside level to the pad's edge
(``planar/frontage_roads``), and a road meeting the frontage -- its band,
or the level's face at the pad's edge -- ramps from the groundside floor
``G = z_D + rise`` at the design grade, up to a frontage a storey up, down
to one a storey down, its ceiling following; its contact rows on the
building's wall leave; airside and the band itself are untouched.
Synthetic."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.constraints import frontage_ramp as fr
from auto_patch_v2.constraints.road_ramp import CONTACT_RULING, GEN, RULING, RULING_CEILING
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Band, ConstraintSet, Linear, Source
from auto_patch_v2.model.registries import LANDSIDE_KERB
from auto_patch_v2.planar.frontage_roads import frontage_roads
from shapely.geometry import box
from shapely.ops import unary_union

LAW = Law.for_airport("SYNT")
G_RAMP = float(LAW.tables.emit.road_contact.ramp_grade)
VIS = float(LAW.tables.emit.cockpit.visual_m)
NS = types.SimpleNamespace


def _map(ground: float, contact_only: bool = False):
    """A road along x: band vertex 1 (x 1, on the kerb), road vertices 2
    (x 5), 3 (x 20), 4 (x 60); wall vertex 9 (the building's edge, x 0) and
    a lot vertex 5 off the road; the datum column 7 inside the building.
    ``contact_only``: vertex 2 is a contact's end vertex, no target."""
    xy = {1: (1.0, 0.0), 2: (5.0, 0.0), 3: (20.0, 0.0), 4: (60.0, 0.0),
          5: (1.0, 30.0), 7: (-30.0, 0.0), 9: (0.0, 0.0)}
    faces = {0: NS(id=0, ref="small_roads:-1", role="service_road", ring=(1, 2, 3, 4),
                   holes=())}
    edges = {i: NS(a=a, b=b) for i, (a, b) in enumerate(((1, 2), (2, 3), (3, 4), (1, 5),
                                                         (9, 1), (9, 2)))}
    rr = {3: ground, 4: ground} if contact_only else {2: ground, 3: ground, 4: ground}
    return NS(faces=faces, edges=edges, ring_vertices=lambda ring: ring,
              vertices={v: NS(xy=p, dem_z=ground) for v, p in xy.items()},
              road_ramp_z=rr, road_contact_edge={2: (9, 7, 0.0, 5.0)},
              registries=NS(held={}, landings={}))


def _rows(ground: float, contact_only: bool = False) -> ConstraintSet:
    lin, bands = [], []
    for v in ((3, 4) if contact_only else (2, 3, 4)):
        lin.append(Linear(((v, 1.0),), ground, ground,
                          Source(GEN, RULING, (f"vertex:{v}", "small_roads:-1"))))
        bands.append(Band(v, None, ground + VIS,
                          Source(GEN, RULING_CEILING, (f"vertex:{v}", "small_roads:-1"))))
    contact = Source(GEN, CONTACT_RULING, ("vertex:2", "small_roads:-1"))
    lin.append(Linear(((2, 1.0), (9, -1.0)), None, 0.4, contact, follows=(2,)))
    lin.append(Linear(((2, 1.0), (9, -1.0)), -0.4, None, contact, follows=(2,)))
    return ConstraintSet(linears=tuple(lin), bands=tuple(bands))


@pytest.fixture
def band(monkeypatch):
    import auto_patch_v2.constraints.kerb_frontage as kf
    import auto_patch_v2.model.platform as mp

    def arm(rise: float, kerb: bool = True):
        got = ({1: ("b", rise)} if kerb else {}, {9, 7})
        monkeypatch.setattr(kf, "kerb_vertices", lambda pm, law: got)
        monkeypatch.setattr(mp, "datum_vertices", lambda pm, law, fills=False: {"b": 7})
    return arm


def _targets(cs):
    return {fr._vertex(r.source): r.hi for r in cs.linears if r.source.ruling == RULING}


def test_the_road_ramps_down_from_a_frontage_a_storey_up(band):
    band(4.1)
    pm = _map(49.5)
    assert fr.band_seeds(pm, LAW) == {2: ("b", 4.1, 4.0), 3: ("b", 4.1, 19.0),
                                      4: ("b", 4.1, 59.0)}
    cs, rep = fr.frontage_ramp_rewrite(pm, LAW, _rows(49.5), {7: 47.0})
    G = 51.1
    t = _targets(cs)
    assert t[2] == pytest.approx(G - G_RAMP * 4.0) and t[3] == pytest.approx(G - G_RAMP * 19.0)
    assert t[4] == 49.5                           # the ramp met its ground before here
    ceil = {r.v: r.hi for r in cs.bands}
    assert ceil[2] == pytest.approx(t[2] + VIS) and ceil[4] == pytest.approx(49.5 + VIS)
    # the contact on the building's wall leaves with the vertex the band governs
    assert not [r for r in cs.linears if r.source.ruling == CONTACT_RULING]
    assert rep["raised"] == 2 and rep["contacts_withdrawn"] == 2 and rep["lowered"] == 0


def test_the_road_ramps_up_from_a_frontage_a_storey_down(band):
    band(-5.7)
    pm = _map(14.5)
    cs, rep = fr.frontage_ramp_rewrite(pm, LAW, _rows(14.5), {7: 18.77})
    G = 13.07
    t = _targets(cs)
    assert t[2] == pytest.approx(G + G_RAMP * 4.0) and t[3] == pytest.approx(G + G_RAMP * 19.0)
    assert t[4] == 14.5                           # the climb met its ground before here
    assert {r.v: r.hi for r in cs.bands}[2] == pytest.approx(t[2] + VIS)
    assert rep["lowered"] == 2 and rep["raised"] == 0


def test_a_contact_end_vertex_takes_the_bands_ramp(band):
    """The end group a §37 (10) contact governs has no §37 (6) target; on
    the building's wall the contact leaves and the band's ramp is its
    target and ceiling."""
    band(-5.7)
    pm = _map(16.5, contact_only=True)
    cs, rep = fr.frontage_ramp_rewrite(pm, LAW, _rows(16.5, contact_only=True), {7: 18.77})
    t = _targets(cs)
    assert t[2] == pytest.approx(13.07 + G_RAMP * 4.0) and rep["targeted"] == 1
    assert {r.v: r.hi for r in cs.bands}[2] == pytest.approx(t[2] + VIS)
    assert not [r for r in cs.linears if r.source.ruling == CONTACT_RULING]


def test_a_road_at_the_levels_face_is_a_contact(band):
    """No band vertex on the road: its end stands within the stand-off of
    the frontage level's face (the landing at the record's rise), and
    ramps from there."""
    band(-5.7, kerb=False)
    pm = _map(16.5)
    pm.faces[1] = NS(id=1, ref="b/p1", role="building", ring=(9,), holes=())
    pm.registries = NS(held={"b": {LANDSIDE_KERB: ({"y": -5.7},)}},
                       landings={"b/p1": {"block": "b", "y": -5.7, "deck": None}})
    pm.road_ramp_z[1] = 16.5                     # the road's end, 1 m off the face
    seeds = fr.band_seeds(pm, LAW)
    assert seeds[1] == ("b", -5.7, 1.0) and seeds[2] == ("b", -5.7, 5.0)
    cs, _rep = fr.frontage_ramp_rewrite(pm, LAW, _rows(16.5), {7: 18.77})
    t = _targets(cs)
    assert t[2] == pytest.approx(13.07 + G_RAMP * 5.0)


def test_no_datum_level_leaves_the_road_as_it_was(band):
    band(4.1)
    before = _rows(49.5)
    cs, rep = fr.frontage_ramp_rewrite(_map(49.5), LAW, before, {})
    assert cs == before and rep["unlevelled"] == 3


def test_no_frontage_no_seeds(band):
    band(4.1, kerb=False)
    cs, rep = fr.frontage_ramp_rewrite(_map(49.5), LAW, _rows(49.5), {7: 47.0})
    assert rep["seeded"] == 0 and cs == _rows(49.5)


def _way(*pts):
    return NS(tags={"highway": "service"}, points=list(pts))


def test_a_road_entering_the_block_is_on_its_level_to_the_edge():
    """Pad 100 x 60, the airside along its west edge, the level in its east
    part.  East road: from the level out through the east edge -- on the
    level.  West road: from the level ending inside the block -- the
    block's.
    A road crossing the block north-south well off the airside -- on the
    level; one crossing beside the airside -- the block's."""
    P, air, L = box(0.0, 0.0, 100.0, 60.0), box(-50.0, 0.0, 0.0, 60.0), box(60.0, 10.0, 90.0, 50.0)
    ways = [_way((75.0, 30.0), (130.0, 30.0)), _way((75.0, 20.0), (45.0, 20.0)),
            _way((30.0, -10.0), (30.0, 70.0)), _way((2.0, -10.0), (2.0, 70.0))]
    got = frontage_roads(L, P, air, NS(osm_ways=ways), LAW, 3.0, 1.0)
    xs = sorted(round(q.bounds[0]) for q in got)
    assert len(got) == 2, [q.bounds for q in got]
    east, cross = sorted(got, key=lambda q: -q.bounds[0])
    assert east.bounds[2] == pytest.approx(100.0) and east.bounds[0] == pytest.approx(90.0)
    assert cross.bounds[1] == pytest.approx(0.0) and cross.bounds[3] == pytest.approx(60.0)
    assert xs[0] > 20.0


def test_no_road_no_piece():
    P, air, L = box(0.0, 0.0, 100.0, 60.0), box(-50.0, 0.0, 0.0, 60.0), box(60.0, 10.0, 90.0, 50.0)
    assert frontage_roads(L, P, air, NS(osm_ways=[]), LAW, 3.0, 1.0) == []


def _part(x0, y0, x1, y1, base_y, feet=False):
    ring = ((y0, x0), (y0, x1), (y1, x1), (y1, x0))      # (lat, lon) = (y, x)
    return NS(lon=0.5 * (x0 + x1), lat=0.5 * (y0 + y1), base_y=base_y, rings=(ring,),
              feet=((y0, x0, base_y),) if feet else (), line=False, scatter=False)


def test_the_airside_floor_ends_at_the_road_through_the_storey():
    """RULINGS 2026-11-26c: the #2279 terminal (``test_kerb_frontage2279.
    _landside``) with a mapped road across its storey 30 m in from the
    apron.  The body past the road (cut off the airside by it) and the road
    itself are the landside's; the airside floor is the body short of the
    road -- never the road's corridor, nor a bay past it."""
    from auto_patch_v2.classify.airside_edge import airside_edge_flip
    from auto_patch_v2.classify.rules import load_rules
    from auto_patch_v2.classify.storey_edge import knife_storeys, storey_band
    floor = _part(100.0, -20.0, 140.0, -2.0, 0.0, feet=True)
    upper = [_part(20.0, 0.0, 60.0, 60.0, 4.1), _part(200.0, 0.0, 250.0, 60.0, 4.1),
             _part(60.0, 0.0, 200.0, 40.0, 4.1)]
    road = NS(tags={"highway": "service"}, points=[(0.0, 30.0), (270.0, 30.0)])
    ap = NS(partition=NS(units=[NS(members=[NS(parts=[floor, *upper])])]),
            frame=NS(entry=lambda: (lambda lon, lat: (lon, lat))),
            dem=NS(z=lambda x, y: 46.0 + 4.6 * (y > 0)), osm_ways=[road])
    final = [["apron", "apron0", box(-50.0, -100.0, 320.0, 0.0), None, {}, "apron"],
             ["parking_lot", "lot0", box(0.0, 0.0, 270.0, 100.0), None, {}, "parking_lot"]]
    band = storey_band(ap, LAW, [], final)
    half = 0.5 * (band.roads.bounds[3] - band.roads.bounds[1])
    cuts: dict = {}
    airside_edge_flip(final, [], LAW, load_rules(),
                      storey=band, storey_cuts=cuts, to_xy=lambda lon, lat: (lon, lat))
    assert knife_storeys(final, cuts, LAW, 1.0, band) == 1
    under = unary_union([f[2] for f in final[2:] if f[0] == "apron"])
    assert under.area == pytest.approx(230.0 * (30.0 - half), rel=1e-3)
    assert under.intersection(band.roads).area < 1.0


def test_a_pad_wholly_past_the_wall_is_the_upper_level(monkeypatch):
    """RULINGS 2026-11-26c: the unit's main block stands over the airside
    floor; a canopy pad of the same unit wholly past it, touching the
    storey lot, becomes the main block's upper landing at the storey's
    rise; a pad keeping a pad's worth on the floor is left to ``plan_up``."""
    import dataclasses

    import auto_patch_v2.planar.low_level as ll
    from auto_patch_v2.planar.past_wall import past_the_wall

    @dataclasses.dataclass(frozen=True)
    class Reg:
        ref: str
        polygon: object
    monkeypatch.setattr(ll, "unit_share", lambda P, airport, to_xy: (0, []))
    floor = box(0.0, 0.0, 100.0, 40.0)
    groups = {"main": [Reg("main", box(0.0, 0.0, 100.0, 40.0))],
              "canopy": [Reg("canopy", box(20.0, 50.0, 40.0, 70.0))],
              "half": [Reg("half", box(60.0, 10.0, 80.0, 60.0))]}
    lot = box(0.0, 40.0, 100.0, 100.0).difference(box(20.0, 50.0, 40.0, 70.0))
    reg = NS(landings={})
    ap = NS(frame=NS(entry=lambda: (lambda lon, lat: (lon, lat))))
    done: dict = {}
    air = box(0.0, -50.0, 100.0, 0.0)
    got = past_the_wall(groups, done, [(lot, 4.1)], floor, ap, LAW, 0.25, reg, "up",
                        lambda P: air, lambda ref, P: None)
    assert got == {"canopy"}
    assert [r.ref for r in done["canopy"]] == ["canopy/p1"]
    assert done["canopy"][0].polygon.area == pytest.approx(400.0)
    assert reg.landings["canopy/p1"]["block"] == "main" and reg.landings["canopy/p1"]["y"] == 4.1


def test_a_hard_deck_needs_something_passing_under_it():
    """Owner 2026-11-27 (PHLI front kerb): a deck piece is a bridge only
    where a mapped way crosses under it -- a run of at least half its narrow
    width; a way clipping its corner, or none, is no witness."""
    from auto_patch_v2.planar.deck_under import passes_under
    piece = box(0.0, 0.0, 40.0, 100.0)                  # narrow width 40 m
    across = NS(id=1, tags={"highway": "primary"}, points=[(-10.0, 50.0), (50.0, 50.0)])
    corner = NS(id=2, tags={"highway": "service"}, points=[(-5.0, 3.0), (3.0, -5.0)])
    river = NS(id=3, tags={"waterway": "stream"}, points=[(20.0, -10.0), (20.0, 110.0)])
    apron = NS(id=4, tags={"aeroway": "taxiway"}, points=[(-10.0, 60.0), (50.0, 60.0)])
    assert passes_under(piece, NS(osm_ways=[across, corner])) == [(1, 40.0)]
    assert passes_under(piece, NS(osm_ways=[river])) == [(3, 100.0)]
    assert passes_under(piece, NS(osm_ways=[corner, apron])) == []
