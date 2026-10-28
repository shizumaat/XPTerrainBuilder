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
author drew, never a box).  Two readers use it, both owner-ruled:

* ``planar/covered_bores`` — a ``covered=yes`` way with a trench object
  at an end is a bore (Q255 a, amends 2026-09-11aq A);
* ``planar/structures`` — the graded zones keep off the outline (Q256 b:
  "graded terrain should come right up to it on 3 sides with only the
  road grading down to it's low edge on the front side").

The depth stays the survey's or the bore law's (20e: the pack portal sets
the mouth only where the ground does not already carry the cutting).
Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
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
from .object_cut import _plan_segments

__all__ = ["TrenchObject", "read_trench_objects", "trench_keepouts", "covered_candidates"]


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


def trench_keepouts(trenches: _t.Sequence[TrenchObject], bores, tol_m: float,
                    cover: _t.Sequence = ()) -> tuple[list, list[str]]:
    """THE ZONES KEEP OFF A TRENCH OBJECT AT A BORE END (RULINGS 2026-10-28s
    (6), Q256 b): ``(the outline's polygons, one note per object)`` for each
    trench object whose outline stands within ``tol_m`` of an end of a bore
    of ``bores`` (built, refused or survey-decided alike: the pack drew the
    trench whatever the engine cuts).  The polygons join the structure
    pass's keepouts — the one region the graded zones stop at — so the
    terrain meets the object on its sides and the road alone grades to its
    front edge.

    ``cover`` is the classification's cell polygons (pavement, pads, roads):
    a keepout is GROUND the zones would have graded, never a cell, so the
    outline is trimmed by them at this one site.  MEASURED EDDF (replay of
    the registered l1028 capture): untrimmed, ``Tunnel_4.obj``'s outline
    took the taxiway ``pav76`` it passes under out of the arrangement — 64
    ``airside_no_step`` and 22 ``taxi_box`` rows on the taxiway east of
    the runway 25R threshold (ADJUDICATED 4824 -> 4923)."""
    ends = [Point(p) for b in bores for p in (b.points[0], b.points[-1])]
    cut = shapely.union_all(np.array(list(cover), dtype=object)) if len(cover) else None
    polys: list = []
    notes: list[str] = []
    for t in trenches:
        if not any(t.outline.distance(e) <= tol_m for e in ends):
            continue
        ground = t.outline if cut is None else t.outline.difference(cut)
        parts = [g for g in shapely.get_parts(ground)
                 if g.geom_type == "Polygon" and not g.is_empty]
        polys.extend(parts)
        notes.append(f"{t.object_id} {os.path.basename(t.resource)}: the zones keep off its "
                     f"outline ({sum(g.area for g in parts):.0f} m2; RULINGS 2026-10-28s (6))")
    return polys, notes
