"""Which mesh triangles are cliff faces, and how a texture lies on them (#2096).

An orthophoto is projected straight down, so on a face of slope ``a`` one
image pixel is drawn ``1 / cos(a)`` times longer along the fall line: twice
as long at 60 degrees, three times at 70.  This module reads the tile's own
mesh (we know every triangle) and lays out a FACE-SPACE texture on the steep
ones, so a tiling texture drawn there is not stretched:

* **alpha** -- every node gets an opacity from the steepest land triangle
  around it, ramping (smoothstep) from 0 at ``slope_lo`` to 1 at
  ``slope_hi`` degrees.  The overlay is the land triangles with a node
  above 0, so the cliff texture fades into the orthophoto across the first
  ring of triangles at the cliff's top and bottom: the soft blend band.
* **charts** -- the overlay is cut into charts, each with ONE projection.
  Steep triangles (``>= face_min``) grow into charts of similar normal
  (within ``chart_angle`` of the seed's) projected along the chart's mean
  normal, so a triangle is stretched at most ``1 / cos(chart_angle)``
  (1.15 at 30 degrees).  The gentle triangles of the blend band take their
  region's plan chart: top-down, like the orthophoto, which is not
  stretched there.
* **regions** -- connected overlay triangles: one texture each,
  colour-matched to the orthophoto around it (``O4_Cliff_Texture``).  A
  region whose steep area is under ``min_area_m2`` stays orthophoto, and at
  most ``max_regions`` (the largest) are kept.

Pure numpy; positions are metres in a plane tangent at the tile centre.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians

import numpy

__all__ = ["CliffParams", "CliffLayout", "find_cliff_layout",
           "local_metres", "node_steepest", "slope_ramp", "triangle_slopes"]

EARTH_RADIUS_M = 6378137.0


@dataclass(frozen=True)
class CliffParams:
    """The knobs of the layout (degrees, metres)."""
    slope_lo: float = 52.0       # node alpha 0 at or below this slope
    slope_hi: float = 62.0       # ... and 1 at or above this one
    face_min: float = 45.0       # a triangle this steep takes a face chart
    chart_angle: float = 30.0    # max normal spread inside one face chart
    repeat_m: float = 480.0      # metres of face per texture repeat
    min_area_m2: float = 2000.0  # a smaller region stays orthophoto
    max_regions: int = 96        # textures per tile, largest regions first


@dataclass
class CliffLayout:
    """The overlay of one tile.

    ``tris[i]`` (a mesh triangle id) is drawn in chart ``chart[i]``; chart
    ``c`` belongs to region ``chart_region[c]`` and measures its texture
    coordinates along the unit axes ``chart_axes[c]``.  ``alpha`` is per
    mesh node.  ``region_area[r]`` is region ``r``'s steep 3-D area (m2),
    ``region_tris[r]`` its triangles; ``dropped_regions`` counts the
    regions left to the orthophoto (too small, or past the cap).
    """
    tris: numpy.ndarray
    chart: numpy.ndarray
    chart_region: list
    chart_axes: list
    alpha: numpy.ndarray
    region_area: list
    region_tris: list
    dropped_regions: int = 0

    def plan_charts(self):
        """Per region its plan (top-down) chart: the first of its charts."""
        first = {}
        for c, r in enumerate(self.chart_region):
            first.setdefault(r, c)
        return [first[r] for r in range(len(self.region_tris))]

    def chart_uv(self, chart_id, xyz, repeat_m):
        """Texture coordinates (in repeats) of points ``xyz`` (n, 3):
        column 0 (``s``) along the contour, column 1 (``t``) up the face;
        ``repeat_m`` is metres per repeat, one number or one per column."""
        u, v = self.chart_axes[chart_id]
        return numpy.stack((xyz @ u, xyz @ v), 1) / repeat_m


def local_metres(lon, lat, z, lat0, lon0):
    """(n, 3) metres east, north, up of points of the tile at
    ``(lat0, lon0)``: one tangent plane at the tile centre (under 1 % of
    scale error across a tile -- a texture scale, never a position)."""
    k = radians(1) * EARTH_RADIUS_M
    x = (numpy.asarray(lon, dtype=float) - lon0) * k * cos(radians(lat0 + 0.5))
    y = (numpy.asarray(lat, dtype=float) - lat0) * k
    return numpy.stack((x, y, numpy.asarray(z, dtype=float)), 1)


def triangle_slopes(xyz, tri_idx):
    """Slope (degrees), upward unit normal and 3-D area of each triangle."""
    a = xyz[tri_idx[:, 1]] - xyz[tri_idx[:, 0]]
    b = xyz[tri_idx[:, 2]] - xyz[tri_idx[:, 0]]
    n = numpy.cross(a, b)
    norm = numpy.linalg.norm(n, axis=1)
    n = n / numpy.maximum(norm, 1e-9)[:, None]
    n[n[:, 2] < 0] *= -1
    slope = numpy.degrees(numpy.arccos(numpy.clip(n[:, 2], 0.0, 1.0)))
    return slope, n, 0.5 * norm


def _edge_neighbours(tri_idx, subset):
    """``{tri: [tris of subset sharing an edge with it]}``."""
    sub = numpy.asarray(subset)
    t = tri_idx[sub]
    edges = numpy.concatenate((t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]))
    edges.sort(axis=1)
    owner = numpy.tile(sub, 3)
    order = numpy.lexsort((edges[:, 1], edges[:, 0]))
    e, o = edges[order], owner[order]
    nbrs = {int(i): [] for i in sub}
    for k in numpy.nonzero(numpy.all(e[1:] == e[:-1], axis=1))[0]:
        p, q = int(o[k]), int(o[k + 1])
        nbrs[p].append(q)
        nbrs[q].append(p)
    return nbrs


def node_steepest(tri_idx, slope, land, nbr_nodes):
    """(n,) slope (degrees) of the steepest land triangle at each node."""
    steepest = numpy.zeros(nbr_nodes)
    ids = numpy.nonzero(land)[0]
    for c in range(3):
        numpy.maximum.at(steepest, tri_idx[ids, c], slope[ids])
    return steepest


def slope_ramp(slope, lo, hi):
    """Smoothstep of ``slope`` (degrees): 0 at or below ``lo``, 1 at or
    above ``hi``."""
    x = numpy.clip((slope - lo) / numpy.maximum(1e-6, numpy.subtract(hi, lo)),
                   0.0, 1.0)
    return x * x * (3 - 2 * x)


def _node_alpha(tri_idx, slope, land, nbr_nodes, params, extra=None):
    alpha = slope_ramp(node_steepest(tri_idx, slope, land, nbr_nodes),
                       params.slope_lo, params.slope_hi)
    return alpha if extra is None else numpy.maximum(alpha, extra)


def _components(tris, nbrs):
    seen, comps = set(), []
    for start in tris:
        start = int(start)
        if start in seen:
            continue
        seen.add(start)
        stack, comp = [start], []
        while stack:
            p = stack.pop()
            comp.append(p)
            for q in nbrs[p]:
                if q not in seen:
                    seen.add(q)
                    stack.append(q)
        comps.append(comp)
    return comps


def _face_axes(normal):
    """Unit ``(u, v)`` spanning the plane normal to ``normal``: ``u``
    horizontal along the face, ``v`` up the face."""
    u = numpy.cross((0.0, 0.0, 1.0), normal)
    if numpy.linalg.norm(u) < 1e-6:
        u = numpy.array((1.0, 0.0, 0.0))
    u = u / numpy.linalg.norm(u)
    v = numpy.cross(normal, u)
    return u, v / numpy.linalg.norm(v)


def _grow_charts(comp, slope, normal, area, nbrs, params):
    """Face charts of one region's steep triangles: ``[(tris, normal)]``."""
    steep = sorted((t for t in comp if slope[t] >= params.face_min),
                   key=lambda t: -slope[t])
    steep_set = set(steep)
    limit = cos(radians(params.chart_angle))
    owner, charts = set(), []
    for seed in steep:
        if seed in owner:
            continue
        n0 = normal[seed]
        owner.add(seed)
        members, stack = [seed], [seed]
        while stack:
            p = stack.pop()
            for q in nbrs[p]:
                if q in steep_set and q not in owner and normal[q] @ n0 >= limit:
                    owner.add(q)
                    members.append(q)
                    stack.append(q)
        mean = (normal[members] * area[members, None]).sum(0)
        charts.append((members, mean / numpy.linalg.norm(mean)))
    return charts


def _layout_region(comp, slope, normal, area, nbrs, params, out):
    """Append one region's charts and triangles to ``out``."""
    region = len(out["region_tris"])
    out["region_tris"].append(numpy.asarray(comp))
    plan = len(out["axes"])
    out["chart_region"].append(region)
    out["axes"].append((numpy.array((1.0, 0.0, 0.0)),
                        numpy.array((0.0, 1.0, 0.0))))
    assigned = set()
    for members, mean in _grow_charts(comp, slope, normal, area, nbrs, params):
        out["chart_region"].append(region)
        out["tris"].extend(members)
        out["chart"].extend([len(out["axes"])] * len(members))
        out["axes"].append(_face_axes(mean))
        assigned.update(members)
    rest = [t for t in comp if t not in assigned]
    out["tris"].extend(rest)
    out["chart"].extend([plan] * len(rest))


def find_cliff_layout(xyz, tri_idx, land, params=None, extra_alpha=None):
    """The cliff overlay of a mesh: ``xyz`` (n, 3) node metres, ``tri_idx``
    (m, 3) node ids, ``land`` (m,) bool, ``params`` a :class:`CliffParams`
    (its defaults when None).  An empty layout when nothing is steep
    enough.  ``extra_alpha`` (n,) raises node alpha (by maximum) where the
    overlay is carried past the slope ramp (``O4_Cliff_Shade``); it adds no
    steep area of its own."""
    params = params or CliffParams()
    tri_idx = numpy.asarray(tri_idx).reshape(-1, 3)
    land = numpy.asarray(land, dtype=bool)
    slope, normal, area = triangle_slopes(xyz, tri_idx)
    alpha = _node_alpha(tri_idx, slope, land, len(xyz), params,
                        extra_alpha)
    overlay = numpy.nonzero(land & (alpha[tri_idx].max(1) > 0))[0]
    out = {"tris": [], "chart": [], "chart_region": [], "axes": [],
           "region_tris": []}
    comps, areas, kept = [], [], []
    if len(overlay):
        nbrs = _edge_neighbours(tri_idx, overlay)
        comps = _components(overlay, nbrs)
        areas = [float(area[c][slope[c] >= params.slope_lo].sum())
                 for c in comps]
        kept = sorted((i for i in range(len(comps))
                       if areas[i] >= params.min_area_m2),
                      key=lambda i: -areas[i])[: params.max_regions]
        for i in kept:
            _layout_region(comps[i], slope, normal, area, nbrs, params, out)
    tris = numpy.asarray(out["tris"], dtype=int)
    kept_alpha = numpy.zeros_like(alpha)
    if len(tris):
        nodes = numpy.unique(tri_idx[tris])
        kept_alpha[nodes] = alpha[nodes]
    return CliffLayout(tris, numpy.asarray(out["chart"], dtype=int),
                       out["chart_region"], out["axes"], kept_alpha,
                       [areas[i] for i in kept], out["region_tris"],
                       len(comps) - len(kept))
