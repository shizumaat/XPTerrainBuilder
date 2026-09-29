"""Issue #97 M3 — THE ROAD RING IS STATIONED AT THE PROFILE SPACING.

Road faces are minted in ``classify/roles.py`` as a mitred buffer of the
truck chains, so their ring vertices stood only at the chain's bends —
HECA ``route19``: 55 m between stations while the road profile
(``emit.road_profile.station_m``) samples every 20 m, and the zone band cut
back from the road (``planar/zones``) chorded across the same 55 m, up to
0.8 m off the road it faces (scout road97, sw0929b_HECA).  The ring is now
stationed at the profile spacing on its FREE edges; an edge on the
pavement / pad / runway union it was cut from keeps its endpoints, so no
vertex is minted into the airside ring.
"""
from __future__ import annotations

import math

from shapely.geometry import Point, Polygon, box

from auto_patch_v2.classify import classify
from auto_patch_v2.classify.roles import station_road_ring

from test_classify import _synthetic, law  # noqa: F401  (fixture)


def _segments(poly):
    for ring in (poly.exterior, *poly.interiors):
        cs = list(ring.coords)
        yield from zip(cs, cs[1:])


def _len(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def test_a_165_m_road_is_stationed_at_20_m():
    road = box(0.0, 0.0, 165.0, 6.0)
    out = station_road_ring(road, 20.0)
    lens = [_len(a, b) for a, b in _segments(out)]
    assert max(lens) <= 20.0 + 1e-9, max(lens)
    # 165 m splits into ceil(165/20) = 9 equal stations of 18.33 m per side
    assert sum(1 for L in lens if L > 10.0) == 18
    assert abs(out.area - road.area) < 1e-6          # geometry unchanged


def test_an_edge_on_the_pavement_it_was_cut_from_keeps_its_endpoints():
    road = box(0.0, 0.0, 165.0, 6.0)
    apron = box(0.0, -50.0, 165.0, 0.0)              # shares y = 0
    out = station_road_ring(road, 20.0, apron)
    long = [(a, b) for a, b in _segments(out) if _len(a, b) > 20.0]
    assert len(long) == 1 and all(abs(p[1]) < 1e-9 for p in long[0]), long
    assert max(_len(a, b) for a, b in _segments(out)
               if (a, b) != long[0]) <= 20.0 + 1e-9


def test_classify_stations_every_free_road_edge(law):
    station = float(law.tables.emit.road_profile.station_m)
    cl = classify(_synthetic(gate=True), law)
    roads = [c for c in cl.cells if c.role == "service_road"]
    assert roads
    others = [Polygon(c.ring, c.holes) for c in cl.cells
              if c.role != "service_road"]
    knife = (law.tables.structures.building_pad.groundside_cutback_m
             + law.tables.emit.identity.min_distinct_spacing_m * 2)
    for c in roads:
        for a, b in _segments(Polygon(c.ring, c.holes)):
            if _len(a, b) <= station + 1e-6:
                continue
            mid = Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            # a long edge is only lawful on the cell it was cut from
            assert any(o.exterior.distance(mid) <= knife for o in others), (
                c.ref, a, b, _len(a, b))
