"""A PACK TRENCH OBJECT AT A MOUTH (owner 2026-10-28, RULINGS 2026-10-28s
(5)/(6), Q255 a / Q256 b; issue #1028, spec ``eddf-tunnel-mouths-spec.md``
E2/E3).

A pack may model a road trench by its WALLS and FLOOR alone: a walled
object whose solids hang at least ``[tunnel.object] shell_floor_min_m``
under its zero and stand no more than ``[bridge] clearance_minimum_m``
above it (no roof, no building over the road), placed with a mapped road's
end — a tunnel way's, or a ``covered=yes`` way's — within
``[tunnel.object] bore_end_tolerance_m`` of its plan.  MEASURED EDDF:
``Tunnel_1.obj`` (walls 85 x 488 m, floor plate 6.0 m under its zero) at
the taxiway bridge west of runway 18's threshold, ``Tunnel_3.obj`` /
``Tunnel_4.obj`` (walls to -6.0 m) at the taxiway bridges east of the
runway 25R threshold; every other tunnel reader refused them ("no floor
plate", "an open ramp", "datum relief") or never screened them.

The object's OUTLINE is the union of its solids' plan (the notch the
author drew, never a box).  Its reader is ``planar/covered_bores``: a
``covered=yes`` way with a trench object at an end is a bore (Q255 a,
amends 2026-09-11aq A).  Q256 b's "graded terrain should come right up to
it on 3 sides with only the road grading down to it's low edge on the
front side" — the zones keeping off the outline — is HELD: measured on
EDDF it regressed the taxiway the object passes under (spec E3).

The depth stays the survey's or the bore law's (20e: the pack portal sets
the mouth only where the ground does not already carry the cutting).
Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import typing as _t

import numpy as np
import shapely
from shapely.geometry import Point
from shapely.strtree import STRtree

from ..model.frame import XY
from . import frame_entry as _fe
from . import obj8 as _obj8
from .obj8_clip import _bulk_polys
from .object_cut import _face_normals_y, _plan_area, _plan_segments

__all__ = ["TrenchObject", "read_trench_objects", "covered_candidates", "mouth_portals"]


@_dc.dataclass(frozen=True)
class TrenchObject:
    """One pack trench object at a mapped road end, in the airport frame."""

    object_id: str
    resource: str
    #: the solids' plan union (frame metres)
    outline: object
    #: how far its solids hang under its zero (metres)
    depth_m: float
    #: the mapped road ends within tolerance of it: ``(xy, way id)``
    ends: tuple[tuple[XY, int], ...]


def covered_candidates(osm_ways) -> list:
    """The ways 2026-10-28s (5) may admit as bores: a road or railway mapped
    ``covered=yes`` carrying no ``tunnel`` value (a ``tunnel`` value is read
    by 11aq A alone: ``building_passage`` and its class stay no bore)."""
    return [w for w in osm_ways
            if (w.tags or {}).get("covered") == "yes" and "tunnel" not in (w.tags or {})
            and ("highway" in (w.tags or {}) or "railway" in (w.tags or {}))
            and len(w.points) >= 2]


def _outline(g: _obj8.ObjGeometry, q: float):
    """The authored plan union of every solid triangle: the plates' plan
    polygons and the walls' plan segments (a vertical face has no area)."""
    v, t = g.vertices, g.solid
    if t is None or not len(t):
        return None
    parts = list(_bulk_polys(v, t))
    parts += [s.buffer(max(q, 0.05)) for s in _plan_segments(v, t)]
    if not parts:
        return None
    u = shapely.union_all(np.array(parts, dtype=object))
    return u if not u.is_empty else None


def read_trench_objects(objects: _t.Sequence[_obj8.PlacedObject],
                        cache: _obj8.ResourceCache, law, road_ways,
                        taken: _t.AbstractSet[str] = frozenset()
                        ) -> tuple[list[TrenchObject], list[str]]:
    """Every pack trench object at a mapped road end (module doc), and one
    note per object read."""
    ob = law.tables.structures.tunnel.object
    tol = float(ob.bore_end_tolerance_m)
    top_max = float(law.tables.structures.bridge.clearance_minimum_m)
    ends = [(p, w.id) for w in road_ways for p in (w.points[0], w.points[-1])]
    if not ends:
        return [], []
    tree = STRtree([Point(p) for p, _w in ends])
    outlines: dict[str, object] = {}
    out: list[TrenchObject] = []
    notes: list[str] = []
    for o in objects:
        if (o.resolved is None or o.id in taken or not hasattr(o.plan_bbox, "buffer")
                or _obj8.is_stock_library_resource(o.path)):
            continue
        near = [int(j) for j in tree.query(o.plan_bbox.buffer(tol), predicate="intersects")]
        if not near:
            continue
        vmin, vmax = cache.y_range(o.resolved)[:2]
        if vmin > -float(ob.shell_floor_min_m) or vmax > top_max:
            continue
        if o.path not in outlines:
            g = cache.geometry(o.resolved)
            outlines[o.path] = None if g is None else _outline(g, _fe.quantum(law))
        a = outlines[o.path]
        if a is None:
            continue
        placed = _fe.enter([a], _obj8.placement_affine(o.xy, o.heading_deg),
                           _fe.quantum(law))[0]
        if placed is None:
            continue
        at = tuple((ends[j][0], ends[j][1]) for j in near
                   if placed.distance(Point(ends[j][0])) <= tol)
        if not at:
            continue
        out.append(TrenchObject(o.id, o.path, placed, -vmin, at))
        notes.append(f"{o.id} {os.path.basename(o.path)}: a trench object (walls "
                     f"{-vmin:.2f} m under its zero, top {vmax:.2f} m) at road end(s) "
                     f"{sorted({w for _p, w in at})}, outline {placed.area:.0f} m2")
    out.sort(key=lambda t: t.object_id)
    return out, sorted(notes)


def _face_at(o: _obj8.PlacedObject, g: _obj8.ObjGeometry, xy: XY, r: float, law
             ) -> "tuple[float, float, object] | None":
    """The ENTRANCE FACE of ``o`` at the bore end ``xy``: ``(bottom y, top y,
    top plan)`` of its solids whose plan triangle comes within ``r`` of
    ``xy`` — the bottom the lowest of them under the object's zero, the top
    the level of the largest near-horizontal plate bin among them (the
    face's own top, never a parapet rail), its plan placed in the airport
    frame — or ``None`` where no solid stands there."""
    from shapely.geometry import Polygon
    ob = law.tables.structures.tunnel.object
    v, t = g.vertices, g.solid
    if t is None or not len(t):
        return None
    a, b, d, e, xo, yo = _obj8.placement_affine(o.xy, o.heading_deg)
    px, py = a * v[:, 0] + b * v[:, 2] + xo, d * v[:, 0] + e * v[:, 2] + yo
    near = np.hypot(px[t] - xy[0], py[t] - xy[1]).min(axis=1) <= r + np.ptp(
        np.stack([px[t], py[t]], axis=-1), axis=1).max(axis=1)
    disc = Point(xy).buffer(r)
    ks = [k for k in np.flatnonzero(near)
          if Polygon(np.c_[px[t[k]], py[t[k]]]).buffer(1e-3).intersects(disc)]
    if not ks:
        return None
    ks_a = np.asarray(ks)
    bottom = float(v[t[ks_a], 1].min())
    plate = _face_normals_y(v, t[ks_a]) >= ob.plate_normal_y_min
    if not plate.any():
        return bottom, float(v[t[ks_a], 1].max()), None
    tops = v[t[ks_a[plate]], 1].max(axis=1)
    bins: dict[int, float] = {}
    for k, ar in zip(np.floor(tops / ob.plate_bin_m).astype(int).tolist(),
                     _plan_area(v, t[ks_a[plate]]).tolist(), strict=True):
        bins[k] = bins.get(k, 0.0) + ar
    best = max(bins, key=lambda k: bins[k])
    sel = np.floor(tops / ob.plate_bin_m).astype(int) == best
    plan = shapely.union_all(np.array([Polygon(np.c_[px[q], py[q]]).buffer(1e-3)
                                       for q in t[ks_a[plate][sel]]], dtype=object))
    return bottom, float(tops[sel].max()), plan


def _cover_over(plan, dem_z) -> "float | None":
    """The surveyed ground over a face's top: the highest DEM sample over its
    plan (its vertices and an inner point; ``portal_objects`` reads a roof's
    cover the same way)."""
    if plan is None or plan.is_empty:
        return None
    pts = [plan.representative_point().coords[0]]
    for q in getattr(plan, "geoms", [plan]):
        pts.extend(q.exterior.coords)
    zs = [float(dem_z(x, y)) for x, y in pts]
    zs = [z for z in zs if not math.isnan(z)]
    return max(zs) if zs else None


def _ground_max(dem_z, xy: XY, r: float) -> float:
    """The highest ground within ``r`` of ``xy`` (a 1 m-spaced sample)."""
    n = int(math.ceil(r))
    zs = [float(dem_z(xy[0] + i, xy[1] + j)) for i in range(-n, n + 1)
          for j in range(-n, n + 1) if i * i + j * j <= r * r]
    zs = [z for z in zs if not math.isnan(z)]
    return max(zs) if zs else math.inf


def mouth_portals(trenches: _t.Sequence[TrenchObject], objects: _t.Sequence[_obj8.PlacedObject],
                  cache: _obj8.ResourceCache, law, tunnel_ways, dem_z) -> list:
    """#1747 (owner ruling 2026-11-03 "yes"; RULINGS 2026-11-03e (15), Q-A
    2026-11-05 "the floor at the PORTAL"; Q256 b, 2026-10-28s (6)): a trench
    object standing at a MAPPED TUNNEL's end is that bore's ENTRANCE: the
    road at the mouth grades to the object's bottom AT THE PORTAL.  One pin
    (``portal_objects.Portal``) per such end, read off the object's FACE
    there (:func:`_face_at`, within TWICE ``[tunnel.object]
    bore_end_tolerance_m`` of the end — ``read_portals``' reach for a face,
    which may stand the tolerance off the end either side: LOWS's west face
    stands 8 m out of its mapped end).

    THE FACE IS SEATED WITH ITS TOP ON THE GROUND OVER IT, ITS BOTTOM ON THE
    FLOOR: ``floor_z`` = the surveyed ground over the face's top
    (:func:`_cover_over`) less the face's height (top − bottom), and
    ``bottom_y`` the face's bottom under the object's zero, so the object
    stage seats that face at the floor (``Tunnel.portal_seat``).  MEASURED
    LOWS (1.0.465): the floor was read at the pack's own zero — 4.0 m over
    the ground at the face (its zero is the DEM at the anchor 650 m away) —
    giving a 0.5 m "ramp" 12-24 m long (a pit), while the object stage set
    the face's bottom on the apron, 5 m proud: neither seated the mouth.

    An end with no solid within that reach is no entrance, nor is one
    whose solids there stand more than ``[placement] split_tol_m`` over the
    highest ground in that reach at the pack's zero (a building on the
    bore), and an edge-wall bridge is never one."""
    from .hanging_objects import edge_wall_reading
    from .portal_objects import Portal
    tol = float(law.tables.structures.tunnel.object.bore_end_tolerance_m)
    split_tol = float(law.tables.structures.placement.split_tol_m)
    bores = {int(w.id) for w in tunnel_ways}
    by_id = {o.id: o for o in objects}
    out = []
    for t in trenches:
        o = by_id.get(t.object_id)
        g = None if o is None else cache.geometry(o.resolved)
        if g is None or edge_wall_reading(o, g, law) is not None:
            # an EDGE-WALL BRIDGE pins by its back's crossing, never by an
            # end's distance (``read_portals``; owner RULINGS 2026-10-28d)
            continue
        zero = float(o.anchor_z + o.agl_m)
        for xy, wid in t.ends:
            if int(wid) not in bores:
                continue
            face = _face_at(o, g, xy, 2.0 * tol, law)
            ground = float(dem_z(xy[0], xy[1]))
            if face is None or np.isnan(ground):
                continue
            bottom, top, plan = face
            if zero + bottom > _ground_max(dem_z, xy, 2.0 * tol) + split_tol:
                # its solids there stand OVER the ground: a building on the
                # bore, never the mouth's road (LOWS's north house plates
                # stood 8.5 m over bore -328's end)
                continue
            cover = _cover_over(plan, dem_z)
            floor = (zero + bottom) if cover is None else cover - (top - bottom)
            out.append(Portal(o.id, o.path, (float(xy[0]), float(xy[1])), int(wid),
                              ground - floor, 0.0, (float(xy[0]), float(xy[1])),
                              floor_z=float(floor), bottom_y=float(bottom)))
    return out
