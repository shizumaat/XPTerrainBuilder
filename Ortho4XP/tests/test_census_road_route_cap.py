"""THE CENSUS PRICES A ROAD PAIR ALONG ITS ROUTE AT THE ROAD'S OWN CAPS
(§37 (7), owner RULINGS 2026-09-13av; issue #609, RULINGS 2026-10-13a (1)).

``constraints/roads.road_within_shape`` reads a road pair with
``road_pair_reading(cap_l, cap_t, ...)``, ``cap_l`` the ROLE's longitudinal
cap.  The census imports the same reading (``check_grade._road_pair_reading_v2``)
and MUST feed it the same caps.  MEASURED (lane crossfall609, SPJC round-5
pad roads): it fed the CHAIN's pair cap instead — already tightened to the
2 % cross-section cap for a chord-transverse pair and to the pad's 1 % for a
pair with a pad-rim endpoint — so the along-route half of a lawful ramp was
priced at 1-2 %: 202 of SPJC's 298 new ``road_cross_section`` rows and ~200
of its 236 new ``within_shape`` rows stood on pairs the solve's own rows held.
"""
from __future__ import annotations

import sys

_LAT0, _LON0 = -12.03, -77.11


def _cg():
    if "tools" not in sys.path:
        sys.path.insert(0, "tools")
    import check_grade as CG
    return CG


def _ll(x, y):
    return (_LAT0 + y / 110600.0, _LON0 + x / 108900.0)


def _road(CG, z_of, with_pad: bool):
    """A 40 m x 6 m service-road ring along x (stations every 5 m on both
    kerbs) at ``z_of(x, y)``; its route frame (route 0, s = x, t = y - 3);
    with ``with_pad`` a building pad sharing the road's x = 0 kerb nodes."""
    xs = [5.0 * k for k in range(9)]
    pts = [(x, 0.0) for x in xs] + [(x, 6.0) for x in reversed(xs)]
    nids = [f"r{i}" for i in range(len(pts))]
    nodes = {n: _ll(x, y) for n, (x, y) in zip(nids, pts)}
    frame = {n: (0, x, y - 3.0) for n, (x, y) in zip(nids, pts)}
    elevs = [z_of(x, y) for x, y in pts]
    road = CG.Way(wid="road", role="service_road", ref="small_roads:-1",
                  aeroway="apron", nids=nids + [nids[0]], elevs=elevs + [elevs[0]],
                  tags={"role": "service_road", "shapeID": "1",
                        CG.LATERAL_CAP_T_TAG: "0.015"})
    ways = [road]
    if with_pad:
        # the pad's east edge IS the road's west kerb end (x = 0): the two
        # rim nodes are shared, the pad level with them
        rim = [nids[0], nids[-1]]
        west = [("p0", (-20.0, 0.0)), ("p1", (-20.0, 6.0))]
        for n, xy in west:
            nodes[n] = _ll(*xy)
        z0 = z_of(0.0, 0.0)
        pn = [rim[0], "p0", "p1", rim[1], rim[0]]
        ways.append(CG.Way(wid="pad", role="building", ref="building1",
                           aeroway="apron", nids=pn, elevs=[z0] * len(pn),
                           tags={"role": "building", "shapeID": "2"}))
    return ways, nodes, frame


def _rows(CG, z_of, with_pad=False):
    ways, nodes, frame = _road(CG, z_of, with_pad)
    xs: list = []
    out = CG._check_within_shape(ways, nodes, CG._ll_to_m_factory(nodes), 0.015,
                                 road_frame_by_nid=frame, transverse_road_out=xs)
    return [v for v in out if v.way_a.wid == "road"], [v for v in xs if v.way_a.wid == "road"]


def test_a_lawful_ramp_reads_no_row_along_or_across_its_route():
    """8 % along the route, level across: under the road's 10 % / 2 % no
    pair of the ring is over its law — not the diagonals either."""
    CG = _cg()
    within, xsec = _rows(CG, lambda x, y: 0.08 * x)
    assert xsec == [], [(v.grade_pct, v.cap_pct) for v in xsec][:5]
    assert within == [], [(v.grade_pct, v.cap_pct) for v in within][:5]


def test_a_ramp_leaving_a_pad_reads_no_row_at_the_road_law():
    """13a (1): the road climbs from the pad's rim at up to 10 %.  A pair
    with a pad-rim endpoint is a ROAD pair priced at the road's own caps,
    never at the pad's 1 %."""
    CG = _cg()
    within, xsec = _rows(CG, lambda x, y: 0.08 * x, with_pad=True)
    assert xsec == [] and within == [], (
        [(v.grade_pct, v.cap_pct, v.distance_m) for v in xsec + within][:5])


def test_a_real_cross_fall_is_still_a_row():
    """The control: 8 % ACROSS the road is a cross-section row."""
    CG = _cg()
    _within, xsec = _rows(CG, lambda x, y: 0.08 * y)
    assert xsec, "a road tilted 8 % across must read road_cross_section rows"
