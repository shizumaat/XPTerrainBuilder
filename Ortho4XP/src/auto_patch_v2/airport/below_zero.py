"""THE OBJECT'S BELOW-ZERO GEOMETRY (RULINGS 2026-09-10af): is the part
of a placement that stands under its own zero a NARROW CUT (a door or a
corridor rendered a road's width into the ground) or a FOUNDATION SKIRT
(the whole bottom of the building, uniform across its footprint, so the
author can seat it on a slope with nothing floating)?

Owner, verbatim (10af): "it would be a relatively small, approximately
road width extension to render the door or corridor walls below the
surface; whereas if the entire building is uniform across its bottom,
then it's just foundations".

THE READING, for one placement (or the two placements a wall-corridor
pair spans), in the airport frame:

* the FOOTPRINT — the union of the plan extents (authored plan bounding
  boxes, placed) of every GENUINE component; the polygon of that union
  holding the site is the building the site belongs to;
* the BELOW-ZERO geometry — the plan segments/polygons of every triangle
  whose lowest vertex stands ``min_depth_m`` or more under the object's
  OWN zero (never against the terrain: the seated frame, 10u/10ad),
  widened by a wall's plan thickness so a vertical face (zero plan area)
  has extent;
* the PERIMETER FRACTION — the share of the footprint polygon's exterior
  lined by that below-zero geometry.  A uniform skirt reads ≈ 1.0; a
  single door cut a small fraction;
* the WIDTHS transverse to a given axis — the below-zero geometry's plan
  extent across the corridor's axis against the footprint's own.

A measurement module: nothing here decides anything.  Law C's clause (d)
(``wall_corridors``) and the skirt-seat rule (10ag) read it.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from ..model.frame import XY, rotated_rectangle
from . import obj8 as _obj8

__all__ = ["BelowZero", "read_below_zero"]

#: A triangle's plan segment shorter than this is a point.
_MIN_SEG_M = 0.02


@_dc.dataclass(frozen=True)
class BelowZero:
    """One placement's below-zero reading (module doc)."""

    footprint: Polygon
    below: _t.Any            # a shapely geometry, or None
    #: the SITE polygon's own exterior (the piece of the placement the
    #: corridor stands in) and the share of it the below-zero geometry lines
    perimeter_m: float
    below_perimeter_m: float
    fraction: float
    #: the WHOLE placement's exterior (every polygon of the union of its
    #: components' plan extents) and the share of THAT lined below zero —
    #: the 10af reading: a foundation skirt lines its building's whole
    #: perimeter (≈ 1.0), a door or corridor cut a small fraction.  The
    #: site polygon alone reads 1.0 for a STANDALONE kerb wall (OTHH's
    #: underpass: the kerbs are their own piece of the terminal pack).
    total_perimeter_m: float = 0.0
    total_below_perimeter_m: float = 0.0
    fraction_total: float = 0.0

    @property
    def site_area_m2(self) -> float:
        return float(self.footprint.area)

    @property
    def site_thickness_m(self) -> float:
        """The site polygon's plan rectangle's SHORT side: a free-standing
        kerb wall is a sliver (a wall's thickness); a building is metres
        across.  A skirt's perimeter fraction reads 1.0 for BOTH — the
        thickness says which of them is a building (RULINGS 2026-09-10af
        round 6)."""
        rect = rotated_rectangle(self.footprint)
        if rect.geom_type != "Polygon":
            return 0.0
        c = list(rect.exterior.coords)[:4]
        if len(c) < 4:
            return 0.0
        return float(min(math.dist(c[i], c[(i + 1) % 4]) for i in range(4)))

    def widths(self, u: XY) -> tuple[float, float]:
        """``(below-zero extent, footprint extent)`` across ``u`` (a unit
        vector along the corridor's axis): the cut's width transverse to
        the corridor against the building's own."""
        n = (-u[1], u[0])
        return (_extent(self.below, n), _extent(self.footprint, n))


def _extent(geom, n: XY) -> float:
    if geom is None or geom.is_empty:
        return 0.0
    xy = shapely.get_coordinates(geom)
    if xy.shape[0] == 0:
        return 0.0
    t = xy[:, 0] * n[0] + xy[:, 1] * n[1]
    return float(t.max() - t.min())


def _plan_parts(v: np.ndarray, tris: np.ndarray, mat: _t.Sequence[float]) -> list:
    """Each triangle's PLAN geometry in the frame: its polygon, or (a
    vertical face: no plan area) the segment it draws on the ground."""
    a, b, d, e, xoff, yoff = mat
    pts = v[tris][:, :, [0, 2]]
    xs = a * pts[:, :, 0] + b * pts[:, :, 1] + xoff
    ys = d * pts[:, :, 0] + e * pts[:, :, 1] + yoff
    polys = shapely.polygons(np.stack([xs, ys], axis=2))
    ok = shapely.is_valid(polys) & (shapely.area(polys) > 1e-9)
    parts = [p for p, k in zip(polys, ok.tolist()) if k]
    for k in np.nonzero(~ok)[0].tolist():
        P = [(float(xs[k, i]), float(ys[k, i])) for i in range(3)]
        far = max(((math.dist(P[i], P[j]), i, j)
                   for i in range(3) for j in range(i + 1, 3)), key=lambda t: t[0])
        if far[0] >= _MIN_SEG_M:
            parts.append(LineString([P[far[1]], P[far[2]]]))
    return parts


def _placed_plan(o: _obj8.PlacedObject, cache: _obj8.ResourceCache,
                 wall_thickness_m: float) -> list[Polygon]:
    """THE PLACEMENT'S PLAN GEOMETRY — every GENUINE component's own plan
    outline (its triangles projected; a vertical face widened to a wall's
    plan thickness), placed and unioned.  Bounding boxes were measured
    first and REFUSED (RULINGS 2026-09-10af, round 6): a pack's component
    boxes overlap, so the union collapses a whole cargo area into ONE
    polygon and every candidate in it reads the same perimeter."""
    g = cache.geometry(o.resolved)
    if g is None:
        return []
    mat = _obj8.placement_affine(o.xy, o.heading_deg)
    parts = []
    for c in cache.components(o.resolved):
        if c.max_y - c.min_y < cache.thickness_m:
            continue
        parts.extend(_plan_parts(g.vertices, c.tris, mat))
    if not parts:
        return []
    u = unary_union([p if p.geom_type == "Polygon" else p.buffer(wall_thickness_m)
                     for p in parts])
    if u.is_empty:
        return []
    return [u] if u.geom_type == "Polygon" else [q for q in u.geoms
                                                 if q.geom_type == "Polygon"]


def _below_parts(o: _obj8.PlacedObject, cache: _obj8.ResourceCache, min_depth_m: float
                 ) -> list:
    """The plan geometry of every triangle standing ``min_depth_m`` or
    more under the object's own zero (segments for vertical faces,
    polygons for the rest)."""
    g = cache.geometry(o.resolved)
    if g is None:
        return []
    mat = _obj8.placement_affine(o.xy, o.heading_deg)
    v = g.vertices
    parts = []
    for c in cache.components(o.resolved):
        if c.max_y - c.min_y < cache.thickness_m or c.min_y > -min_depth_m:
            continue
        low = v[c.tris][:, :, 1].min(axis=1) <= -min_depth_m
        if low.any():
            parts.extend(_plan_parts(v, c.tris[low], mat))
    return parts


def read_below_zero(objects: _t.Sequence[_obj8.PlacedObject], cache: _obj8.ResourceCache,
                    min_depth_m: float, site: XY, wall_thickness_m: float,
                    store: dict | None = None) -> BelowZero | None:
    """The below-zero reading (module doc) of the placements ``objects``
    at ``site`` — the footprint polygon holding the site, the below-zero
    plan geometry inside it, and the share of that polygon's perimeter
    the below-zero geometry lines.  ``store`` (a caller-owned dict)
    memoises the per-placement walk — a corridor pass reads the same
    terminal once per candidate otherwise.  ``None`` when nothing is
    readable."""
    boxes: list[Polygon] = []   # the placements' plan polygons
    parts: list = []
    for o in objects:
        if o.resolved is None or _obj8.is_stock_library_resource(o.path):
            continue
        hit = None if store is None else store.get(o.id)
        if hit is None:
            hit = (_placed_plan(o, cache, wall_thickness_m),
                   _below_parts(o, cache, min_depth_m))
            if store is not None:
                store[o.id] = hit
        boxes.extend(hit[0])
        parts.extend(hit[1])
    if not boxes:
        return None
    polys = boxes if len(objects) < 2 else None
    if polys is None:
        u = unary_union(boxes)
        polys = ([u] if u.geom_type == "Polygon"
                 else [p for p in u.geoms if p.geom_type == "Polygon"])
    if not polys:
        return None
    p = Point(site)
    foot = min(polys, key=lambda q: q.distance(p))
    ring = LineString(foot.exterior.coords)
    perim = float(ring.length)
    below = below_all = None
    if parts:
        u2 = unary_union([g.buffer(wall_thickness_m) if g.geom_type != "Polygon"
                          else g for g in parts])
        if not u2.is_empty:
            below_all = u2
            clip = u2.intersection(foot.buffer(wall_thickness_m))
            below = None if clip.is_empty else clip
    rings = [LineString(q.exterior.coords) for q in polys]
    total = float(sum(r.length for r in rings))
    lined = 0.0
    lined_total = 0.0
    if below_all is not None:
        wide = below_all.buffer(wall_thickness_m)
        hit = ring.intersection(wide)
        lined = float(hit.length) if not hit.is_empty else 0.0
        for r in rings:
            h = r.intersection(wide)
            if not h.is_empty:
                lined_total += float(h.length)
    return BelowZero(foot, below, perim, lined,
                     0.0 if perim <= 0.0 else min(1.0, lined / perim),
                     total, lined_total,
                     0.0 if total <= 0.0 else min(1.0, lined_total / total))
