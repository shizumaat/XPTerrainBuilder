"""Unit tests for the runway-crossing slab bracket (the KBNA 02L/20R+13/31
wedge fix) and the airside mid-edge STEP gate.

The bug: ``_single_poly_station_slab`` snapped the crossing slab bracket
OUTWARD to the nearest kept profile station.  With a sparse profile (physical
ends + a tight crossing-anchor cluster) the overlap projects just outside the
cluster, so the bracket snapped all the way to the physical ends — the slab
ballooned across the ENTIRE runway and the crossing junction inherited both
runways' full profile range (KBNA: an 8.6 m / 731 % step between a 174 m
crossing vertex and the 165 m runway edge 1.18 m away).  The fix clamps the
slab to the overlap's own extent, snapping to a station only within a tight
tolerance.
"""
from __future__ import annotations

import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from shapely.geometry import Polygon


def _runway_candidate(ref, ax, ay, bx, by, width, fractions, elevs):
    """Build a single-poly runway candidate ``(poly, alts, geometry)`` with a
    given sparse profile, matching ``_build_single_poly_runway_ring``'s output
    shape but constructed directly so the test controls the station list."""
    length = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / length, (by - ay) / length
    px, py = -uy * width / 2.0, ux * width / 2.0
    stations = list(zip(fractions, elevs))
    ring, alts = [], []
    for f, e in stations:
        x = ax + f * (bx - ax)
        y = ay + f * (by - ay)
        ring.append((x + px, y + py))
        alts.append(round(e, 2))
    for f, e in reversed(stations):
        x = ax + f * (bx - ax)
        y = ay + f * (by - ay)
        ring.append((x - px, y - py))
        alts.append(round(e, 2))
    poly = Polygon(ring)
    geometry = {
        "axis_a": (ax, ay), "axis_b": (bx, by),
        "length_m": length, "width_m": width,
        "unit": (ux, uy), "perp": (px, py),
        "stations": stations,
        "fractions": list(fractions), "elevs": list(elevs),
    }
    return poly, alts + [alts[0]], geometry


# A long runway A along +x with a SPARSE profile: physical ends at 180 / 168
# and a tight 174 m crossing-anchor cluster near mid-runway.  A perpendicular
# runway C crosses it at (1000, 0), also 174 m there.
_A = _runway_candidate("A/B", 0.0, 0.0, 2000.0, 0.0, 60.0,
                       [0.0, 0.49, 0.51, 1.0], [180.0, 174.0, 174.0, 168.0])
_C = _runway_candidate("C/D", 1000.0, -800.0, 1000.0, 800.0, 50.0,
                       [0.0, 0.48, 0.52, 1.0], [160.0, 174.0, 174.0, 190.0])


def test_midedge_gate_contact_tolerance_and_pair_filter():
    """check_grade's mid-edge step logic (reused by the verify gate) catches a
    wedge whose steep edge runs 1.5 m from the neighbour only at the gate's
    2 m contact tolerance, and the airside pair filter can exclude a pair."""
    import check_grade as CG

    # A short high edge (way V) 1.5 m from a long low edge (way E).
    wv = CG.Way(wid="-1", role="runway_crossing", ref="X", aeroway="runway",
                nids=["1", "2", "3"], elevs=[174.0, 174.0, 174.0], tags={})
    we = CG.Way(wid="-2", role="runway", ref="Y", aeroway="runway",
                nids=["4", "5", "6"], elevs=[165.0, 165.0, 165.0], tags={})
    wv.tags = {"role": "runway_crossing"}
    we.tags = {"role": "runway"}
    ways = [wv, we]
    verts = [CG.Vertex(way_idx=0, nid="1", x=10.0, y=1.5, elev=174.0)]
    edges = [CG.Edge(way_idx=1, a=(0.0, 0.0), b=(20.0, 0.0), ea=165.0,
                     eb=165.0)]

    # 1 m contact tol: 1.5 m gap → missed.
    miss = CG._check_vertex_to_edge_step(verts, edges, ways,
                                         edge_search_m=5.0, edge_step_m=2.5,
                                         contact_tol_m=1.0)
    assert miss == []
    # 2 m contact tol: 1.5 m gap → caught, ~9 m step.
    hit = CG._check_vertex_to_edge_step(verts, edges, ways,
                                        edge_search_m=5.0, edge_step_m=2.5,
                                        contact_tol_m=2.0)
    assert len(hit) == 1 and hit[0].step_m > 8.0
    # pair filter can exclude it.
    filt = CG._check_vertex_to_edge_step(
        verts, edges, ways, edge_search_m=5.0, edge_step_m=2.5,
        contact_tol_m=2.0, pair_ok=lambda a, b: False)
    assert filt == []
