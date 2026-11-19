"""The BLEND BAND around a custom patch's pavement (#2173 part 2, owner
2026-11-19T00:18Z: "open areas, like the grass between taxiways, and next
to runways, get the lidar detail, but the paved areas all blend smoothly").

A custom patch meshes each pad / ramp ring as an INTERP_ALT barrier and the
DEM outside it, so the grass already shows the lidar -- but a flat pad edge
meets that lidar with a STEP (KASE after the re-base: open edges |d| p50
0.86 m, p90 2.7 m).  The auto patch used to answer the same step with a
BANK: a closed ``o4_feature=bank_foot`` ring ON the DEM outside the paved
union, the mesh blending every vertex between ring and foot linearly in
plan distance (``O4_Mesh_Utils.bank_annulus_blend_values``, RULINGS
2026-09-09ab).  The emitter of that ring went with v2's bank pass
(RULINGS 2026-10-04c (3)); the mesh half is still live and reads any
patch's ``bank_foot`` ways (``O4_Bank_Annulus``).  This module writes those
ways into the RE-BASED COPY of a custom patch (``O4_Patch_Rebase``), never
the user's file:

* the FOOT is the DAYLIGHT point of the bank law along each pavement edge
  station's outward normal -- the first distance ``t`` where the 1:3 line
  (``[design] bank_slope``) off the edge's height meets the build DEM
  (the deleted emitter's daylight law, the one
  ``auto_patch_v2.classify.ramp_runout._daylight`` also walks), never
  nearer than ``[design] bank_min_width_m``; the band is the union of the
  per-station quads and the paved union grown by the minimum width;
* every foot ring carries ``var_alt_rel=0`` (its height IS the build DEM,
  sampled at its own nodes, every :data:`STEP_M`), so the mesh outside it
  is the DEM unchanged;
* a ring bounding an ENCLOSED stretch of grass (a hole of the band) also
  carries ``o4_void=yes`` (``O4_Patch_Voids.VOID_TAG``): it is a
  constrained ring, but the grass inside it is no patch coverage and keeps
  the lidar.

Pads keep their one height: only ground between a paved edge and its foot
is valued by the blend, and the blend never writes a pavement vertex.
"""

from __future__ import annotations

import math

import numpy

__all__ = ["STEP_M", "MAX_WIDTH_M", "BAND_FEATURE", "band_rings",
           "band_osm"]

#: Station spacing along the paved edge and node spacing on the foot ring
#: (metres): the foot follows the lidar at this resolution (the deleted
#: emitter's ``bank_sample_m``).
STEP_M = 2.0
#: How far the daylight walk looks (metres).  A station that has not
#: daylighted by then stands below (or above) ground that keeps climbing
#: (falling) faster than 1:3 -- the ground's own bank, which keeps the
#: lidar: its foot is at the minimum width.  MEASURED at KASE: with the
#: bank law's 200 m (``O4_Mesh_Utils.BANK_MAX_WIDTH_M``) as the width of a
#: station that never daylights, the quads ran 184 m up the valley wall
#: and the blend laid ground 85 m below the lidar there.
MAX_WIDTH_M = 40.0
#: The tag the mesh's bank annulus reads (``O4_Bank_Annulus``).
BAND_FEATURE = "bank_foot"
#: Gaps between pads narrower than this are closed before the band is
#: built (a seam between two authored pads is not grass).
_CLOSE_M = 0.5
#: A band hole smaller than this many minimum widths across is filled.
_MIN_HOLE_WIDTHS = 2.0
#: Mitered normal length cap (the deleted emitter's ``_MITER_MAX``).
_MITER_MAX = 3.0
#: The foot ring is simplified by this much (metres) before it is
#: re-densified: the quad union is jagged at the station scale.
_SIMPLIFY_M = 0.25
#: The daylight walk's step (metres; ``ramp_runout.DAYLIGHT_STEP_M``).
_WALK_M = 0.5
_M_PER_DEG = 111120.0


def _law():
    """``(slope, min_width_m)`` of the bank law (``[design]``)."""
    from auto_patch_v2.law import tables

    design = tables.load_default().tables.emit.design
    return float(design.bank_slope), float(design.bank_min_width_m)


class _Frame:
    """A local metric frame around ``origin`` (lon, lat)."""

    def __init__(self, origin):
        self.lon0, self.lat0 = float(origin[0]), float(origin[1])
        self.kx = _M_PER_DEG * math.cos(self.lat0 * math.pi / 180)

    def to_m(self, lonlat):
        p = numpy.atleast_2d(numpy.asarray(lonlat, dtype=float))
        return numpy.column_stack([(p[:, 0] - self.lon0) * self.kx,
                                   (p[:, 1] - self.lat0) * _M_PER_DEG])

    def to_deg(self, xy):
        p = numpy.atleast_2d(numpy.asarray(xy, dtype=float))
        return numpy.column_stack([p[:, 0] / self.kx + self.lon0,
                                   p[:, 1] / _M_PER_DEG + self.lat0])


def _paved(frame, nodes, pads, ramps):
    """``(polygons, z_at)``: each pad / ramp plan in the frame, and the
    patch height at frame points (the nearest pad's altitude; a ramp
    linear from its high end edge to its low end edge)."""
    from shapely import STRtree, geometry, points

    polys, heights = [], []
    for _, refs, alt in pads:
        polys.append(geometry.Polygon(frame.to_m([nodes[r] for r in refs])))
        heights.append((float(alt),))
    for _, refs, high, low in ramps:
        pts = frame.to_m([nodes[r] for r in refs[:4]])
        polys.append(geometry.Polygon(pts))
        heights.append((float(high), float(low), (pts[3] + pts[0]) / 2,
                        (pts[1] + pts[2]) / 2))
    polys = [p if p.is_valid else p.buffer(0) for p in polys]
    tree = STRtree(polys)

    def z_at(xy):
        out = numpy.empty(len(xy))
        for k, j in enumerate(tree.nearest(points(xy)).tolist()):
            h = heights[j]
            if len(h) == 1:
                out[k] = h[0]
                continue
            axis = h[3] - h[2]
            f = float(numpy.dot(xy[k] - h[2], axis)
                      / max(float(numpy.dot(axis, axis)), 1e-12))
            out[k] = h[0] + (h[1] - h[0]) * min(1.0, max(0.0, f))
        return out
    return polys, z_at


def _outward_normals(pts):
    """The MITERED outward normal per vertex of a closed chain oriented so
    the pavement lies to the LEFT (a CCW exterior, a CW hole): the RIGHT
    normal points away from it in both cases."""
    seg = numpy.roll(pts, -1, axis=0) - pts
    length = numpy.hypot(seg[:, 0], seg[:, 1])
    length = numpy.where(length > 0, length, 1.0)
    right = numpy.column_stack([seg[:, 1], -seg[:, 0]]) / length[:, None]
    both = numpy.roll(right, 1, axis=0) + right
    size = numpy.hypot(both[:, 0], both[:, 1])
    flat = size <= 1e-9
    miter = numpy.minimum(_MITER_MAX, 2.0 / numpy.where(flat, 1.0, size))
    out = both / numpy.where(flat, 1.0, size)[:, None] * miter[:, None]
    out[flat] = right[flat]
    return out


def _stations(ring):
    """The ring's stations every :data:`STEP_M`, closing point dropped."""
    from auto_patch_v2.planar.chords import densify

    return numpy.asarray(densify(list(ring.coords)[:-1], STEP_M,
                                 closed=True)[:-1], dtype=float)


def _daylight(z0, pts, unit, dem_m, slope, min_w):
    """THE DAYLIGHT DISTANCE per station (the bank law of the deleted
    emitter, RULINGS 2026-09-09g): the first ``t`` (every :data:`_WALK_M`
    from ``min_w``) where the 1:3 line off the edge meets the ground,
    ``|z0 - DEM(p + u t)| <= slope * t``; ``min_w`` where the ground over
    the first ``min_w`` already falls (fill) / rises (cut) at ``slope`` or
    steeper, or that never daylights inside :data:`MAX_WIDTH_M` -- THE
    GROUND'S OWN BANK, kept as lidar."""
    d = numpy.full(len(z0), min_w)
    z_edge = dem_m(pts)
    sgn = numpy.where(z0 >= z_edge, 1.0, -1.0)
    own = sgn * (z_edge - dem_m(pts + unit * min_w)) >= slope * min_w
    d[own] = min_w
    live = numpy.flatnonzero(~own)
    t = min_w
    while live.size and t <= MAX_WIDTH_M + 1e-9:
        z = dem_m(pts[live] + unit[live] * t)
        hit = numpy.abs(z0[live] - z) <= slope * t
        d[live[hit]] = t
        live = live[~hit]
        t += _WALK_M
    return d


def _to_pavement(pts, unit, d, paved):
    """``d`` capped at the first crossing of the paved union's boundary
    along the ray (the deleted emitter's ``_ray_limit``: two paved edges
    facing across a gap SHARE the band)."""
    import shapely

    start = pts + unit * 0.05
    rays = shapely.linestrings(numpy.stack([start, pts + unit * d[:, None]],
                                           axis=1))
    edge = paved.boundary
    out = d.copy()
    for k in numpy.flatnonzero(shapely.intersects(rays, edge)):
        hit = shapely.get_coordinates(shapely.intersection(rays[k], edge))
        if len(hit):
            out[k] = min(out[k], 0.05 + float(numpy.min(numpy.hypot(
                hit[:, 0] - start[k, 0], hit[:, 1] - start[k, 1]))))
    return out


def _feet(paved, z_at, dem_m, slope, min_w):
    """``(band region, widths)``: the per-station quads from the paved
    edge to its daylight foot along the mitered normal, unioned with the
    paved union grown by ``min_w``."""
    from shapely import geometry, ops

    quads, widths = [], []
    for poly in getattr(paved, "geoms", [paved]):
        poly = geometry.polygon.orient(poly, sign=1.0)
        for ring in [poly.exterior, *poly.interiors]:
            pts = _stations(ring)
            if len(pts) < 3:
                continue
            nrm = _outward_normals(pts)
            size = numpy.maximum(numpy.hypot(nrm[:, 0], nrm[:, 1]), 1e-12)
            unit = nrm / size[:, None]
            # The walk runs along the unit normal; the foot sits on the
            # mitered normal at that perpendicular offset.
            d = _to_pavement(pts, unit, _daylight(
                z_at(pts), pts, unit, dem_m, slope, min_w), paved)
            widths.append(d)
            feet = pts + nrm * d[:, None]
            for i in range(len(pts)):
                j = (i + 1) % len(pts)
                quad = geometry.Polygon([pts[i], pts[j], feet[j], feet[i]])
                quads.append(quad if quad.is_valid else quad.buffer(0))
    band = ops.unary_union([paved.buffer(min_w), *quads])
    return band, (numpy.concatenate(widths) if widths else numpy.zeros(0))


def band_rings(nodes, pads, ramps, sample, box=None):
    """``(rings, stats)``: the foot rings of the blend band around the
    patch's paved union, each ``(lonlat Nx2 closed, is_hole)``, and
    ``stats`` (``widths``: the daylight width per paved-edge station, m;
    ``frame``: the metric frame).  ``sample`` is the build DEM
    ``f(lonlat Nx2) -> z``; ``box`` an optional ``(lon0, lat0, lon1,
    lat1)`` the band is clipped to (the tile)."""
    from shapely import geometry, ops

    pts = numpy.array([nodes[r] for _, refs, *_ in pads + ramps
                       for r in refs])
    if not len(pts):
        return [], {"widths": numpy.zeros(0)}
    frame = _Frame(pts.mean(axis=0))
    slope, min_w = _law()
    polys, z_at = _paved(frame, nodes, pads, ramps)
    paved = ops.unary_union(polys).buffer(
        _CLOSE_M, join_style=2).buffer(-_CLOSE_M, join_style=2)
    band, widths = _feet(paved, z_at,
                         lambda xy: sample(frame.to_deg(xy)), slope, min_w)
    if box is not None:
        band = band.intersection(geometry.Polygon(frame.to_m(
            [(box[0], box[1]), (box[2], box[1]), (box[2], box[3]),
             (box[0], box[3])])))
    band = band.simplify(_SIMPLIFY_M)
    min_hole = (_MIN_HOLE_WIDTHS * min_w) ** 2
    rings = []
    for poly in getattr(band, "geoms", [band]):
        if poly.is_empty or poly.geom_type != "Polygon":
            continue
        rings.append((poly.exterior, False))
        rings.extend((hole, True) for hole in poly.interiors
                     if geometry.Polygon(hole).area >= min_hole)
    out = []
    for ring, hole in rings:
        xy = _stations(ring)
        if len(xy) >= 3:
            out.append((frame.to_deg(numpy.vstack([xy, xy[:1]])), hole))
    return out, {"widths": widths, "frame": frame, "z_at": z_at,
                 "paved": paved, "band": band}


def band_osm(text, rings):
    """``text`` (a patch's OSM) with one closed way per ring before
    ``</osm>``: ``o4_feature=bank_foot``, ``var_alt_rel=0`` and, on a hole,
    the void tag; node and way ids below every id the text uses."""
    import re

    from O4_Patch_Voids import VOID_TAG

    ids = [int(v) for v in re.findall(r"\bid=['\"](-?\d+)['\"]", text)]
    nid = min([0, *ids]) - 1
    lines, ways = [], []
    for ring, hole in rings:
        refs = []
        for lon, lat in ring[:-1]:
            lines.append("  <node id='%d' lat='%.9f' lon='%.9f' />\n"
                         % (nid, lat, lon))
            refs.append(nid)
            nid -= 1
        tags = [("o4_feature", BAND_FEATURE), ("var_alt_rel", "0")]
        if hole:
            tags.append(VOID_TAG)
        ways.append((refs + refs[:1], tags))
    for refs, tags in ways:
        lines.append("  <way id='%d'>\n" % nid)
        nid -= 1
        lines.extend("    <nd ref='%d' />\n" % r for r in refs)
        lines.extend("    <tag k='%s' v='%s' />\n" % kv for kv in tags)
        lines.append("  </way>\n")
    cut = text.rfind("</osm>")
    if cut < 0:
        raise ValueError("no </osm> in the patch")
    return text[:cut] + "".join(lines) + text[cut:]
