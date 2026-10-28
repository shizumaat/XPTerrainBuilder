"""#1333 twin (owner 2026-10-25, LFLL): the cut under a building is the
building's LOWER LEVEL (RULINGS 2026-10-23b two pads, 27h depth from the
objects; #1179 a pad never fills a mapped cutting).

``classify/pad_cut_corridor`` leaves a COVERED cutting (``covered=yes`` /
``tunnel=building_passage``) in the pad; ``planar/covered_cut`` mints the
held pad's lower level over it at the densest plane of the lower parts'
walled feet, trims what no level takes, and the pad fills never take a
cutting.  Hermetic: a metre frame (lon = x, lat = y)."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.classify.pad_cut_corridor import (
    _is_covered,
    cutting_corridors,
    trim_cut_corridors,
)
from auto_patch_v2.law import Law
from auto_patch_v2.model.registries import Registries
from auto_patch_v2.planar import covered_cut as CC
from shapely.geometry import Point, box
from shapely.ops import unary_union

LAW = Law.for_airport("HECA")
NS = types.SimpleNamespace
RAIL = {"railway": "rail", "cutting": "yes", "covered": "yes", "layer": "-1",
        "tunnel": "building_passage"}


def _part(x0, y0, x1, y1, base_y, h=0.0, feet=()):
    ring = ((y0, x0), (y0, x1), (y1, x1), (y1, x0))      # (lat, lon) = (y, x)
    return NS(lon=0.5 * (x0 + x1), lat=0.5 * (y0 + y1), base_y=base_y, height_m=h,
              rings=(ring,), feet=tuple(feet), line=False)


def _feet(x, y0, y1, y):
    return [(float(v), float(x), float(y)) for v in range(int(y0), int(y1), 10)]


def _airport(parts, ways=(), ground=lambda x, y: 239.0):
    unit = NS(members=[NS(parts=parts)])
    return NS(partition=NS(units=[unit]), osm_ways=list(ways),
              frame=NS(entry=lambda: (lambda lon, lat: (lon, lat))),
              dem=NS(z=ground), pack=None, icao="")


def _way(x, y0, y1, tags=RAIL):
    return NS(points=[(x, y0), (x, y1)], tags=dict(tags))


P = box(0.0, 0.0, 200.0, 300.0)                          # the station's pad
AIR = box(0.0, 300.0, 200.0, 340.0)                       # the apron north of it
#: the station's halls on the pad: walled, their feet at the floor y 0
FRONT = [_part(10.0 + 40.0 * i, 292.0, 40.0 + 40.0 * i, 300.0, 0.0, 10.0,
               [(296.0, 12.0 + 40.0 * i + d, 0.0) for d in (0.0, 9.0, 18.0, 27.0)])
         for i in range(4)]
#: the trench's objects: the track bed (a 5 km object, base -9.1) and the
#: platforms beside it, walled to the trench floor
TRENCH = [_part(90.0, -2000.0, 110.0, 3000.0, -9.1),
          _part(108.0, 20.0, 114.0, 260.0, -9.1, 3.0, _feet(111.0, 20, 260, -9.1)),
          _part(86.0, 20.0, 92.0, 260.0, -9.0, 3.0, _feet(89.0, 20, 260, -9.0))]
#: two covered tracks under the station, 12 m apart
TRACKS = [(94.0, -100.0, 250.0), (106.0, -100.0, 250.0)]


def _cut_ground(x, y):
    return 229.8 if 80.0 <= x <= 120.0 else 239.0


def test_a_covered_cutting_stays_in_the_pad_an_open_one_is_trimmed():
    assert _is_covered(RAIL) and _is_covered({"cutting": "yes", "covered": "yes"})
    assert not _is_covered({"railway": "rail", "cutting": "yes"})
    pad = box(-50, -50, 50, 50)
    ap = NS(osm_ways=[NS(points=[(0.0, -100.0), (0.0, 100.0)], tags=dict(RAIL))])
    assert trim_cut_corridors([pad], ap, LAW)[0].area == pytest.approx(10000.0)
    ap.osm_ways[0].tags = {"railway": "rail", "cutting": "yes"}
    assert trim_cut_corridors([pad], ap, LAW)[0].area < 10000.0
    ap.osm_ways[0].tags = dict(RAIL)
    w = cutting_corridors(ap, LAW, covered=True, widen=1.0).area
    assert w == pytest.approx(3.0 * cutting_corridors(ap, LAW, covered=True).area)
    assert cutting_corridors(ap, LAW, covered=False) is None


def test_the_cut_under_the_station_is_its_lower_level_at_the_objects_bottom():
    ap = _airport(FRONT + TRENCH, [_way(*w) for w in TRACKS], _cut_ground)
    cov = CC.covered_corridors(ap, LAW)
    got = CC.plan_covered(P, AIR, ap, LAW, 0.5, cov, None, [],
                          CC.covered_corridors(ap, LAW, widen=1.0))
    assert got is not None
    H, L, S, rec = got
    assert rec["witness"] == CC.WITNESS and rec["top_y"] == 0
    assert rec["y_lo"] == pytest.approx(-9.1, abs=0.15)      # the walls' floor
    # the corridor and the platforms beside it, never the rest of the pad
    # nor the 5 km track bed beyond it
    assert L.contains(box(91.0, 10.0, 109.0, 240.0))       # the tracks
    assert L.contains(box(108.5, 30.0, 113.5, 250.0))      # a platform beside them
    assert L.area < 0.25 * P.area and L.within(P.buffer(0.01))
    assert L.distance(AIR) >= 3.0 - 1e-6
    assert L.intersection(H).area == pytest.approx(0.0, abs=1e-6)
    assert rec["ground_z"] == pytest.approx(229.8)


def test_no_lower_storey_no_level_and_the_cut_is_trimmed():
    from auto_patch_v2.planar.overlay import Region
    ap = _airport(FRONT, [_way(100.0, -100.0, 250.0)])
    cov = CC.covered_corridors(ap, LAW)
    why: list = []
    assert CC.plan_covered(P, AIR, ap, LAW, 0.5, cov, None, why) is None
    assert why and "no part a storey under" in why[0]
    reg, counts = Registries(), {}
    pad = Region("building", "building8", P, None, None, "airside", "cell")
    out = CC.trim_uncut([pad], ap, LAW, reg, counts)
    assert sum(r.polygon.area for r in out) == pytest.approx(P.area - cov.intersection(P).area)
    assert counts["covered_cut_trimmed"] == 1


def test_a_minted_level_keeps_its_cut_and_the_rest_is_trimmed():
    from auto_patch_v2.planar.overlay import Region
    ap = _airport(FRONT + TRENCH, [_way(100.0, -100.0, 250.0)])
    cov = CC.covered_corridors(ap, LAW)
    L = cov.intersection(box(0, 0, 200, 200))
    reg = Registries()
    reg.landings["building8/p1"] = {"block": "building8", "witness": CC.WITNESS}
    regs = [Region("building", "building8", P.difference(L), None, None, "airside", "cell"),
            Region("building", "building8/p1", L, None, None, "airside", "cell")]
    out = CC.trim_uncut(regs, ap, LAW, reg, {})
    low = [r for r in out if str(r.ref) == "building8/p1"]
    assert len(low) == 1 and low[0].polygon.area == pytest.approx(L.area)
    rest = cov.intersection(P).difference(L)
    assert all(r.polygon.intersection(rest).area < 1e-6 for r in out)


def test_a_covered_cut_level_does_not_extend_over_the_group():
    from auto_patch_v2.planar.low_extent import extend_levels
    from auto_patch_v2.planar.overlay import Region
    ap = _airport(FRONT + TRENCH, [_way(100.0, -100.0, 250.0)])
    reg = Registries()
    reg.landings["building8/p1"] = {"block": "building8", "kind": "low_level",
                                    "witness": CC.WITNESS, "top_y": 0.0, "y_hi": -2.0}
    regs = [Region("building", "building8/p1", box(90, 0, 110, 250), None, None,
                   "airside", "cell")]
    from auto_patch_v2.planar.low_extent import AirRegion
    got = extend_levels(regs, reg, [AirRegion(AIR, "cell")], ap, LAW, 0.5, {})
    assert got == regs


def test_a_pad_fill_never_takes_a_mapped_cutting(monkeypatch):
    """#1179 at the fills' mint (19ap): the plate over the corridor the
    pad lost is no landing there (LFLL: 16 fills at 239.3-239.8 m over the
    229.5 m TGV trench)."""
    from auto_patch_v2.airport import slab_faces as SF
    from auto_patch_v2.geom.base_slab import FaceFacts
    from auto_patch_v2.planar import landing as LD
    from auto_patch_v2.planar.overlay import Region
    monkeypatch.setattr(SF, "witness_faces", lambda _lw: (lambda _m, _c: FaceFacts(0.0, 0.0, 0.0)))
    b = box(50, 0, 160, 100)
    plate = NS(comp=0, base_y=0.15, height_m=0.0, area_m2=b.area,
               rings=(tuple((y, x) for x, y in tuple(b.exterior.coords)[:-1]),),
               feet=(), box=(0, 50, 100, 160), line=False, scatter=False)
    m = NS(id="dsf:obj1", resource="Terminal/side_walk.obj", parts=(plate,),
           deck_kind="", origin=(0.0, 0.0), heading_deg=0.0)
    part = NS(units=(NS(id="unit:0", members=(m,)),))
    def to_xy(lon, lat):
        return (lon, lat)
    cut = NS(points=[(125.0, -50.0), (125.0, 150.0)],
             tags={"railway": "rail", "cutting": "yes"})
    airport = NS(partition=part, frame=NS(entry=lambda: to_xy), osm_ways=[cut])
    pad = Region("building", "b5", box(0, 0, 100, 100), None, None, "groundside", "cell")
    reg = Registries()
    reg.held["b5"] = {"unit": "b5", "k": 0, "blocks": 1}
    got = LD.landing_regions([pad], {}, [box(300, 0, 400, 100)], airport, LAW, 0.0, 15.0,
                             {}, reg=reg)
    corr = cutting_corridors(airport, LAW)
    assert got and all(r.polygon.intersection(corr).area < 1e-6 for r in got)


# ── 2026-10-28r (3): the cut's ENDS grade to the open cut at the rail grade ──

def _ends_airport(ground):
    def ident(a, b):
        return (a, b)
    frame = NS(entry=lambda: ident, transformers=lambda: (ident, lambda x, y: (y, x)))
    cut = NS(points=[(100.0, -300.0), (100.0, 600.0)],
             tags={"railway": "rail", "cutting": "yes"})
    return NS(frame=frame, dem=NS(z=ground), osm_ways=[cut])


def test_each_end_of_the_level_runs_out_to_the_open_cut_at_rail_grade():
    from auto_patch_v2.planar.cut_runout import cut_runouts
    L = box(90.0, 0.0, 110.0, 300.0)                     # the level, to the pad's ends
    H = box(0.0, 0.0, 200.0, 300.0).difference(box(88.0, -1.0, 112.0, 301.0))
    held = {"building8": {"datum_pred": 239.0}}
    ap = _ends_airport(lambda x, y: 229.0)               # the open cut, 1 m under
    counts: dict = {}
    got = cut_runouts({"building8/p1": (L, "building8", -9.0)}, held, ap, LAW,
                      unary_union([H, L]), 0.5, counts)
    tn = LAW.tables.structures.tunnel
    assert len(got) == 2 and counts["cut_runout_ends"]["ends"] == 2
    for rec in got.values():
        assert rec["landing"] == "building8/p1" and rec["block"] == "building8"
        assert (rec["g"], rec["cap"]) == (tn.rail_ramp_grade, tn.rail_ramp_max_grade)
        # 1 m closed, plus the plane band the datum may miss by, at the
        # 1.25 % design grade: ~160 m of ramp, never a step
        assert 140.0 <= rec["run_m"] <= 170.0
        for q in rec["polys"]:
            assert q.intersection(L).area < 1e-6 and q.distance(L) < 0.5
    dirs = sorted(round(r["dir"][1]) for r in got.values())
    assert dirs == [-1, 1]                               # one each way, out of the level


def test_an_end_whose_ground_stands_level_or_above_asks_nothing():
    from auto_patch_v2.planar.cut_runout import cut_runouts
    L = box(90.0, 0.0, 110.0, 300.0)
    held = {"building8": {"datum_pred": 239.0}}
    for z, key in ((231.0, "at_grade"), (233.0, "climbs")):   # the level + its band
        counts: dict = {}
        got = cut_runouts({"building8/p1": (L, "building8", -9.0)}, held,
                          _ends_airport(lambda x, y, z=z: z), LAW, L, 0.5, counts)
        assert got == {} and counts["cut_runout_ends"][key] == 2


def test_the_run_out_rows_hold_the_strip_at_or_under_the_level():
    """The record is a landing run-out: ``constraints/ramp_runout`` reads
    the fields it reads for a viaduct's landing."""
    from auto_patch_v2.planar.cut_runout import cut_runouts
    L = box(90.0, 0.0, 110.0, 300.0)
    got = cut_runouts({"building8/p1": (L, "building8", -9.0)},
                      {"building8": {"datum_pred": 239.0}},
                      _ends_airport(lambda x, y: 229.0), LAW, L, 0.5, {})
    need = {"landing", "block", "y", "lip", "dir", "width_m", "z0_pred", "reach_m",
            "g", "cap", "dem0", "ground", "run_m", "polys"}
    assert got and all(need <= set(r) for r in got.values())


# ── 2026-10-28r (1) (2), round 3: the level is the cut's alone ──

def _plan(ap, air=AIR):
    cov = CC.covered_corridors(ap, LAW)
    reach = CC.covered_corridors(ap, LAW, widen=1.0)
    got = CC.plan_covered(P, air, ap, LAW, 0.5, cov, None, [], reach)
    assert got is not None
    return cov, reach, got


def test_the_level_never_takes_the_pads_far_side():
    """LFLL closing build: the trench split the station pad, and the part
    beyond it -- the forecourt, no airside within reach -- was grown into
    the level (``low_level._with_orphans``, 29,736 m2 sunk 9 m).  A covered
    cut's level is the corridor and the lower parts' footprints in reach."""
    hall = _part(150.0, 100.0, 190.0, 200.0, 0.0, 10.0)        # the far side's hall
    ap = _airport(FRONT + TRENCH + [hall], [_way(x, -100.0, 400.0) for x, _a, _b in TRACKS],
                  _cut_ground)
    _cov, reach, (H, L, _S, _rec) = _plan(ap, air=box(0.0, 300.0, 80.0, 340.0))
    from auto_patch_v2.law.tables import design as design_law
    near = float(design_law(LAW).pad_frontage_m)
    assert L.difference(reach.buffer(near)).area < 1.0
    assert box(150.0, 100.0, 190.0, 200.0).within(H.buffer(1e-6))


def _service(x0, y0, x1, y1):
    return NS(points=[(x0, y0), (x1, y1)], tags={"highway": "service", "lanes": "1"})


def test_a_road_along_the_trench_keeps_its_ground():
    """24a: a road beside the level meets the pad at its edge -- the level
    keeps a riser's width off its carriageway (one on it, one 0.4 m from
    it); a road crossing the tracks is the building's deck (28r (2)) and is
    never trimmed from the level."""
    from shapely.geometry import LineString
    beside, near = _service(113.0, 100.0, 113.0, 140.0), _service(116.15, 180.0, 116.15, 230.0)
    cross = _service(60.0, 60.0, 140.0, 60.0)
    ap = _airport(FRONT + TRENCH, [_way(*w) for w in TRACKS] + [beside, near, cross],
                  _cut_ground)
    cov, _reach, (_H, L, _S, rec) = _plan(ap)
    w = max(float(LAW.tables.emit.identity.min_distinct_spacing_m), 1.0)
    for r in (beside, near):
        c = LineString(r.points).buffer(1.75, cap_style="flat")
        assert L.distance(c.difference(cov)) >= w - 1e-6
    assert rec["off_roads"] == 2 and rec["off_roads_m2"] > 0.0
    assert L.contains(box(87.0, 58.0, 113.0, 62.0))       # the crossing stays the level
    assert L.contains(box(95.0, 110.0, 105.0, 190.0))     # the cut stays one level


def test_a_road_over_the_level_is_cut_out_of_it_and_its_riser():
    """28r (2): a road over the cut is the building's deck for the whole
    level and its riser -- its ribbon cell ends at the strip's outer edge
    (LFLL ``-6364``/``-11343``: a level vertex at 239.37 m on the crossing's
    node)."""
    from auto_patch_v2.model.planar import STRIP_SUFFIX
    from auto_patch_v2.planar.overlay import Region
    from auto_patch_v2.planar.ribbons import _cut_out
    ap = _airport(FRONT + TRENCH, [_way(*w) for w in TRACKS], _cut_ground)
    _cov, _reach, (H, L, S, _rec) = _plan(ap)
    reg = Registries()
    reg.landings["building8/p1"] = {"block": "building8", "witness": CC.WITNESS}
    pads = [Region("building", "building8", H, None, None, "groundside", "cell"),
            Region("building", "building8/p1", L, None, None, "groundside", "cell"),
            Region("building", "building8/p1" + STRIP_SUFFIX, S, None, None,
                   "groundside", "cell")]
    cut = CC.covered_cut_taken(ap, LAW, pads, reg)
    cell = Region("small_roads", "small_roads:-1", box(60.0, 57.0, 140.0, 63.0), None, None,
                  "groundside", "ribbon")
    got = _cut_out([cell], cut, 0.5)
    w = max(float(LAW.tables.emit.identity.min_distinct_spacing_m), 1.0)
    assert len(got) == 2
    for r in got:
        for x, y in r.polygon.exterior.coords:
            assert L.distance(Point(x, y)) >= w - 0.5 - 1e-6   # the grid's half cell


def test_the_run_out_stands_two_risers_off_a_pad_and_its_z0_is_the_levels():
    """28r (3) with #1183: the run-out starts one plane band over the level
    (the block's contact reach is the datum pin's, never the level's lip:
    LFLL's 10.97 m ran both strips to the 400 m cap), and stands two risers
    off the pads beside it (the census pairs pavement within one)."""
    from auto_patch_v2.airport.airside_group_seat import PLANE_BAND_M
    from auto_patch_v2.planar.cut_runout import cut_runouts
    L = box(90.0, 0.0, 110.0, 300.0)
    flank = unary_union([box(60.0, -200.0, 94.0, 0.0), box(106.0, -200.0, 140.0, 0.0)])
    held = {"building8": {"datum_pred": 239.0, "samples_reach": [11.0]}}
    got = cut_runouts({"building8/p1": (L, "building8", -9.0)}, held,
                      _ends_airport(lambda x, y: 229.0), LAW, unary_union([L, flank]),
                      0.5, {})
    riser = max(float(LAW.tables.emit.identity.min_distinct_spacing_m), 1.0)
    assert got
    for rec in got.values():
        assert rec["z0_pred"] == pytest.approx(230.0)
        assert rec["reach_m"] == pytest.approx(PLANE_BAND_M)
        assert rec["run_m"] <= 170.0                     # never the 400 m cap
        for q in rec["polys"]:
            assert q.distance(flank) >= 2.0 * riser - 1e-6
