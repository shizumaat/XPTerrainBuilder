"""THE STEEP-GROUND YIELD of the core's levelled road ribbons.

``O4_Vector_Map.include_roads`` levels a banked road by buffering its
centreline ``lane_width`` each side and holding every ring vertex at the
centreline's DEM (``alt_vec_shift``): a laterally level ribbon whose
kerbs are a hard Dirichlet set in the mesh, while the ground one vertex
outside follows the raw DEM.  On ordinary banked ground that is a bench
a few decimetres tall.  Where the road's centreline runs along (or
across) a cliff in the DEM, the ground one lane width off the centreline
stands metres above or below it, and the ribbon becomes a slab standing
off its own ground with a vertical wall on each side; the sparse ring
(one node per OSM vertex) then interpolates straight through the DEM's
zigzag between those nodes.  Owner sim read LPPD 2026-11-18T13:32Z:
stepped vertical slabs and spikes along a coastal bluff whose top
carries a narrow road (ribbon vertices 14.97 m above / 16.46 m below
the DEM at 37.738425,-25.700671 and 37.741289,-25.707300).

THE RULE: a road levels where its bench is a bench.  Where the DEM
within one ``lane_width`` of the centreline -- across either kerb or
along to the next station -- stands more than ``bench_max_m`` off the
centreline, the ribbon YIELDS to its own ground over that span (plus a
``margin_m`` either side, and gaps shorter than ``merge_gap_m`` between
two such spans): the span is dropped from the banked network and the
mesh follows the DEM there.  The band the longitudinal clamp owns
beside a patch (``exempt``) is never yielded.
"""

from __future__ import annotations

import numpy
import O4_Vector_Utils as VECT
from shapely import geometry
from shapely.prepared import prep

#: The tallest bench a levelled ribbon may stand off its own ground
#: within one lane width, in metres.  Above it the ribbon is a wall and
#: the road yields to the DEM.  A rule constant, not a per-airport
#: tuning: 3 m over a 4 m lane is a 75 % cross-fall, which no
#: carriageway sits on without a retaining wall.
ROAD_BENCH_MAX_M = 3.0


def station_relief(stations, alt_vec, lane_width):
    """Per station: the largest |DEM - centreline DEM| within one lane."""
    centre = numpy.asarray(alt_vec(stations), dtype=numpy.float64)
    relief = numpy.zeros(len(stations))
    for side in ("left", "right"):
        kerb = numpy.asarray(
            alt_vec(VECT.shift_way(stations, lane_width, side)),
            dtype=numpy.float64)
        relief = numpy.maximum(relief, numpy.abs(kerb - centre))
    step = numpy.abs(numpy.diff(centre))
    relief[1:] = numpy.maximum(relief[1:], step)
    relief[:-1] = numpy.maximum(relief[:-1], step)
    return relief


def _yield_intervals(s, steep, margin_m, merge_gap_m):
    """Merged ``(a, b)`` arclength intervals around the steep stations."""
    out = []
    for i in numpy.flatnonzero(steep):
        a, b = s[i] - margin_m, s[i] + margin_m
        if out and a - out[-1][1] <= merge_gap_m:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(max(a, 0.0), min(b, s[-1])) for a, b in out]


def _kept_pieces(coords, s_coords, intervals, min_piece_m):
    """The way's own polyline outside ``intervals``, as coordinate arrays."""
    edges = [0.0]
    for a, b in intervals:
        edges += [a, b]
    edges.append(s_coords[-1])
    pieces = []
    for a, b in zip(edges[0::2], edges[1::2]):
        if b - a < min_piece_m:
            continue
        inner = (s_coords > a) & (s_coords < b)
        ends = [[numpy.interp(t, s_coords, coords[:, 0]),
                 numpy.interp(t, s_coords, coords[:, 1])] for t in (a, b)]
        pieces.append(numpy.vstack([ends[0], coords[inner], ends[1]]))
    return pieces


def _append(out_g, out_c, out_i, geom, cls, wid):
    out_g.append(geom)
    out_c.append(cls)
    out_i.append(wid)


def yield_steep_spans(road_network, alt_vec, lane_width, *,
                      way_classes=None, way_ids=None, exempt=None,
                      bench_max_m=ROAD_BENCH_MAX_M, margin_m=None,
                      merge_gap_m=None, min_piece_m=None):
    """Drop the spans of a banked-road network that stand on cliffs.

    Returns ``(network, classes, ids, report)``: the kept
    MultiLineString with its per-geom class and id lists kept parallel
    (a split way repeats its class and id per piece; both lists are
    empty when the caller's were not parallel to the geoms), and a
    report dict (``ways``, ``spans``, ``yielded_m``, ``worst_relief_m``
    and the ``worst`` station, tile-relative ``(x, y)``).  A way with no
    steep station passes through unchanged.
    """
    margin_m = 2.0 * lane_width if margin_m is None else margin_m
    merge_gap_m = 8.0 * lane_width if merge_gap_m is None else merge_gap_m
    min_piece_m = 2.0 * lane_width if min_piece_m is None else min_piece_m
    geoms = list(getattr(road_network, "geoms", ()) or ())
    classes = list(way_classes or ())
    ids = list(way_ids or ())
    parallel = len(classes) == len(geoms) == len(ids)
    band = None
    if exempt is not None and not getattr(exempt, "is_empty", True):
        band = prep(exempt)
    report = {"ways": 0, "spans": 0, "yielded_m": 0.0,
              "worst_relief_m": 0.0, "worst": None}
    out_g, out_c, out_i = [], [], []
    for gi, geom in enumerate(geoms):
        cls = classes[gi] if parallel else None
        wid = ids[gi] if parallel else None
        coords = numpy.asarray(geom.coords, dtype=numpy.float64)
        stations = numpy.asarray(VECT.refine_way(coords, lane_width),
                                 dtype=numpy.float64)
        steep = numpy.zeros(len(stations), dtype=bool)
        if len(stations) >= 2:
            relief = station_relief(stations, alt_vec, lane_width)
            steep = relief > bench_max_m
        if band is not None and steep.any():
            for i in numpy.flatnonzero(steep):
                steep[i] = not band.covers(geometry.Point(stations[i]))
        if not steep.any():
            _append(out_g, out_c, out_i, geom, cls, wid)
            continue
        intervals = _yield_intervals(VECT.way_arclengths(stations), steep,
                                     margin_m, merge_gap_m)
        k = int(numpy.argmax(numpy.where(steep, relief, -1.0)))
        if relief[k] > report["worst_relief_m"]:
            report["worst_relief_m"] = float(relief[k])
            report["worst"] = (float(stations[k][0]), float(stations[k][1]))
        report["ways"] += 1
        report["spans"] += len(intervals)
        report["yielded_m"] += float(sum(b - a for a, b in intervals))
        for piece in _kept_pieces(coords, VECT.way_arclengths(coords),
                                  intervals, min_piece_m):
            _append(out_g, out_c, out_i, geometry.LineString(piece), cls,
                    wid)
    if not parallel:
        out_c, out_i = [], []
    return geometry.MultiLineString(out_g), out_c, out_i, report
