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
from auto_patch_v2.classify.pad_cut_corridor import (cutting_corridors, _is_covered,
                                                     trim_cut_corridors)
from auto_patch_v2.law import Law
from auto_patch_v2.model.registries import Registries
from auto_patch_v2.planar import covered_cut as CC
from shapely.geometry import box

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
    assert rec["y_lo"] == pytest.approx(-9.1, abs=0.15)      # the walls' floor, never -9.1 - a storey
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
    to_xy = (lambda lon, lat: (lon, lat))
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
