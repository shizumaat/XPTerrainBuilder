"""THE THIN-PLATE WALL CLASS (spec ``design-surface-spec.md`` §33 (2);
owner RULINGS 2026-09-13d item 5 "remember to use object based wall
objects provided by the scenery package when present as a guide for
where the tunnel mouth is and what size it is"; Fable 2026-09-13i).

``airport/tunnel_objects`` reads a pack's tunnel WALLS — two bands with a
skirt, a crest plate, a trench between their inner faces.  LEMD's pack
does not model its bridges and tunnel walls that way: it models them as
THIN PLATES, a single slab of solids 1.0-1.5 m tall lying over the road
(``Bridges/Bridge3.obj`` 354 x 25 m spanning the whole of bore ``-5931``
with 1.03 m of solids; ``Bridge2.obj`` 168 x 90 m over the bridge ways at
1.31 m; ``Bridge1.obj`` 1.50 m).  Every one of them is refused by the wall
pre-screen's ``least_skirt`` = min(``skirt_min_depth_m`` 3.0,
``edge_wall_min_skirt_m`` 1.5) — and, until §33 (1), SILENTLY.  So the OSM
corridor stood alone and item 5's mouth came out 7.0 m wide (``lanes x
lane_width_m``) against the object's 25.1 m, 1.08 m off its centre and
83 m INSIDE the object's end.

THE CLASS.  A pack object whose GENUINE solids span at least
``[tunnel.object] thin_plate_min_m`` and whose plan hull lies over a
mapped bore (``tunnel=yes``) or deck (``bridge=yes``) for
``hull_min_length_m`` of that way is an AUTHORED CORRIDOR.  Its plan
RECTANGLE gives the corridor's axis (the long side), its width (the short
side) and its PORTAL POSITIONS (the short sides' midpoints — the object's
ends).  The depth stays ``tunnel.bore_datum_m`` for a bore.

THE DECK PLATE reads its top from the object only where the placement
carries an ABSOLUTE seat (``OBJECT_MSL``).  A plain ``OBJECT`` is DRAPED
on the solved surface, so its authored top is an OFFSET over whatever the
ground under it ends up being — no datum at all (measured LEMD
``Bridge2.obj``: authored y 0.000..1.310 over ``anchor_z`` 608.36, the DEM
at the placement; the apron its deck must meet stands at 606.5).  Such a
placement is recorded with that verdict and the deck's ENDS govern
(§33 (4)).

This module READS; ``planar/structure_approach.apply_plates`` applies the
reading to the OSM mouths (the ``source_precedence = ["object", "osm"]``
per-mouth precedence of 05n-3, at the mouth the plate governs).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import time
import typing as _t

import numpy as np
from shapely import affinity as _affinity
from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

from ..law import Law
from ..model.airport import Airport
from ..model.frame import XY
from . import obj8 as _obj8
from .deck_signature import is_bridge_way, is_tunnel_way

__all__ = ["WallPlate", "PlateStats", "read_plates", "authored_axis_ends", "ID_PREFIX"]

ID_PREFIX = "wall-plate"


@_dc.dataclass(frozen=True)
class WallPlate:
    """One thin-plate wall object in the AIRPORT frame.  ``ends`` are the
    plan rectangle's short-side MIDPOINTS — the object's two portals, in
    axis order; ``width_m`` the short side; ``top_z`` the ABSOLUTE
    authored top where the placement carries one (``OBJECT_MSL``), else
    ``None`` (a draped placement states no datum)."""

    id: str
    resource: str
    object_id: str
    plan: Polygon
    ends: tuple[XY, XY]
    length_m: float
    width_m: float
    span_m: float
    top_y_m: float
    top_z: float | None
    #: the mapped ways this plate governs, and the metres of each under it
    bore_ways: tuple[tuple[int, float], ...] = ()
    bridge_ways: tuple[tuple[int, float], ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def kind(self) -> str:
        return "bore" if self.bore_ways else "deck"


@_dc.dataclass
class PlateStats:
    """What the plate reader saw, admitted and refused — every screened
    resource by name with its verdict (§33 (1))."""

    screened: int = 0
    plates: int = 0
    bore_plates: int = 0
    deck_plates: int = 0
    refused: list[str] = _dc.field(default_factory=list)
    read_s: float = 0.0


def _plan_hull(geom: _obj8.ObjGeometry, genuine: _t.Sequence[_obj8.Component]
               ) -> tuple[Polygon | None, float, float]:
    """``(plan hull of the genuine solids, min y, max y)`` in the AUTHORED
    frame (x east, z south)."""
    if not genuine:
        return None, float("nan"), float("nan")
    tris = np.concatenate([c.tris for c in genuine])
    pts = geom.vertices[np.unique(tris.reshape(-1))]
    hull = Polygon([(float(x), float(z))
                    for x, z in zip(pts[:, 0], pts[:, 2])]).convex_hull
    if hull.geom_type != "Polygon" or hull.area <= 0.0:
        return None, float("nan"), float("nan")
    return hull, min(c.min_y for c in genuine), max(c.max_y for c in genuine)


def authored_axis_ends(o: _obj8.PlacedObject, x0: float, x1: float, z0: float, z1: float
                       ) -> tuple[float, float, XY, XY] | None:
    """``(length, width, end0, end1)`` — the corridor the OBJECT states,
    read in its OWN authored frame (§33 (2) "its plan ring gives the
    corridor's axis, width and portal positions (the object's ends)"):
    the authored box's long side is the axis, its short side the WIDTH,
    and the short sides' midpoints — transformed by the placement — are
    the portals.

    NOT the plan hull's minimum rotated rectangle: that minimises AREA,
    so a tapered plate's rectangle turns off the object's own axis and
    reads narrow (measured LEMD Bridge3: 354.2 x 20.2 m against the
    object's own 354.2 x 25.1 m, and an axis 1 degree off its centre)."""
    dx, dz = x1 - x0, z1 - z0
    if dx <= 0.0 or dz <= 0.0:
        return None
    mx, mz = (x0 + x1) / 2.0, (z0 + z1) / 2.0
    if dz >= dx:
        length, width = dz, dx
        a, b = (mx, z0), (mx, z1)
    else:
        length, width = dx, dz
        a, b = (x0, mz), (x1, mz)
    e0 = _obj8._to_frame(o.xy, o.heading_deg, a[0], a[1])
    e1 = _obj8._to_frame(o.xy, o.heading_deg, b[0], b[1])
    return (float(length), float(width),
            (float(e0[0]), float(e0[1])), (float(e1[0]), float(e1[1])))


def _under(plan: Polygon, ways, lines, tree, axis: LineString | None = None
           ) -> list[tuple[int, float]]:
    """``(way id, metres of it under the plan)`` for every way the plan
    covers at all, longest first (the tree keeps this O(hits)).  With
    ``axis`` the metre count is the covered stretch's run ALONG THE
    CORRIDOR — its projection onto the plate's own axis — which is what a
    bore under a corridor has and a road merely CROSSING a slab has not
    (measured LEMD ``STRT4.obj``, a 750 x 89 m ground slab: seven bores
    cross its 89 m width for ~86 m each, none of them along it)."""
    out: list[tuple[int, float]] = []
    for j in (tree.query(plan, predicate="intersects") if tree is not None else ()):
        w, inter = ways[int(j)], lines[int(j)].intersection(plan)
        if inter.is_empty or inter.length <= 0.0:
            continue
        run = float(inter.length)
        if axis is not None:
            ss = [axis.project(Point(q)) for g in _lines(inter) for q in g.coords]
            run = (max(ss) - min(ss)) if ss else 0.0
        out.append((int(w.id), run))
    out.sort(key=lambda t: -t[1])
    return out


def _lines(geom):
    import shapely
    return [g for g in shapely.get_parts(geom) if g.geom_type == "LineString"]


def read_plates(airport: Airport, objects: _t.Sequence[_obj8.PlacedObject],
                cache: _obj8.ResourceCache, law: Law,
                taken: _t.AbstractSet[str] = frozenset()
                ) -> tuple[list[WallPlate], PlateStats]:
    """Every THIN-PLATE wall object the pack states (§33 (2)), in the
    airport frame.  ``taken`` are the resources ``read_corridors``
    already admitted as full wall corridors — an object is read ONCE, by
    the senior reader."""
    t0 = time.perf_counter()
    stats = PlateStats()
    ob = law.tables.structures.tunnel.object
    least_skirt = min(ob.skirt_min_depth_m, ob.edge_wall_min_skirt_m)
    admitted_values = law.tables.structures.tunnel.admitted_values
    msl = {o.id: o.y_offset_m for o in airport.dsf_objects if o.kind == "OBJECT_MSL"}
    bores = [w for w in airport.osm_ways
             if is_tunnel_way(w.tags, admitted_values) and len(w.points) >= 2]
    decks = [w for w in airport.osm_ways if is_bridge_way(w.tags) and len(w.points) >= 2]
    if not bores and not decks:
        stats.read_s = time.perf_counter() - t0
        return [], stats
    b_lines = [LineString(w.points) for w in bores]
    d_lines = [LineString(w.points) for w in decks]
    b_tree = STRtree(b_lines) if b_lines else None
    d_tree = STRtree(d_lines) if d_lines else None
    all_tree = STRtree(b_lines + d_lines) if (b_lines or d_lines) else None
    out: list[WallPlate] = []
    k_by_res: dict[str, int] = {}
    for o in objects:
        if o.resolved is None or _obj8.is_stock_library_resource(o.path) \
                or o.path in taken or o.witnesses:
            continue
        vmin, vmax, x0, x1, z0, z1 = cache.y_range(o.resolved)
        # THE CLASS IS THE GAP THE WALL PRE-SCREEN LEAVES: solids spanning
        # at least thin_plate_min_m and LESS than least_skirt — a plate is
        # what `read_corridors` refuses for having no skirt, and nothing
        # else.  Without the ceiling the class swallows every building on
        # the field (measured LEMD: 112 "plates", among them a 1,035 x
        # 557 m cargo terminal spanning 37 m).
        if not (ob.thin_plate_min_m <= vmax - vmin < least_skirt):
            continue
        if max(x1 - x0, z1 - z0) < ob.hull_min_length_m:
            continue                       # a stub — the wall reader named it
        # the placement's plan BOUNDING BOX must hold a mapped way at all
        # before its geometry is built (the 06f cheap gate's shape)
        if x0 == math.inf or x1 == -math.inf:
            continue
        box = Polygon([_obj8._to_frame(o.xy, o.heading_deg, x, z)
                       for x in (x0, x1) for z in (z0, z1)]).convex_hull
        if all_tree is None or not len(all_tree.query(box, predicate="intersects")):
            continue
        name = os.path.basename(o.path)
        geom = cache.geometry(o.resolved)
        if geom is None:
            continue
        hull, y0, y1 = _plan_hull(geom, cache.genuine(o.resolved))
        if hull is None:
            continue
        plan = _affinity.affine_transform(
            hull, _obj8.placement_affine(o.xy, o.heading_deg))
        b_under = _under(plan, bores, b_lines, b_tree)
        d_under = _under(plan, decks, d_lines, d_tree)
        if not b_under and not d_under:
            continue                       # over nothing mapped: not a corridor
        stats.screened += 1
        ra = authored_axis_ends(o, x0, x1, z0, z1)
        if ra is None:
            stats.refused.append(f"{o.id} {name}: the authored box is degenerate")
            continue
        length, width, e0, e1 = ra
        # A BORE PLATE'S bore runs ALONG the corridor: its covered stretch
        # projects onto the plate's own axis for hull_min_length_m AND for
        # more than the plate is WIDE — a way that merely crosses a wide
        # slab is not in a corridor under it (§33 (2): "its plan ring gives
        # the corridor's AXIS").  A DECK way crosses by definition.
        axis = LineString([e0, e1])
        b_along = _under(plan, bores, b_lines, b_tree, axis)
        b_ok = [t for t in b_along
                if t[1] >= ob.hull_min_length_m and t[1] >= width]
        d_ok = [t for t in d_under if t[1] >= ob.hull_min_length_m]
        if not b_ok and not d_ok:
            bb = (b_along or [(0, 0.0)])[0]
            dd = (d_under or [(0, 0.0)])[0]
            stats.refused.append(
                f"{o.id} {name}: a {length:.0f} x {width:.0f} m plate spanning "
                f"{vmax - vmin:.2f} m over a mapped way, but the longest bore run ALONG its "
                f"axis is {bb[1]:.1f} m (way {bb[0]}; needs hull_min_length_m "
                f"{ob.hull_min_length_m} and more than its own width {width:.0f} m) and the "
                f"longest deck run under it {dd[1]:.1f} m (way {dd[0]}) — the plate crosses or "
                f"clips them, it does not carry a corridor (§33 (2))")
            continue
        notes = [f"thin plate (§33 (2)): solids span {vmax - vmin:.2f} m "
                 f"(>= thin_plate_min_m {ob.thin_plate_min_m}), plan rectangle "
                 f"{length:.1f} x {width:.1f} m"]
        top_z: float | None = None
        if o.kind == "OBJECT_MSL":
            top_z = float(msl.get(o.id, o.anchor_z)) + float(y1)
            notes.append(f"absolute seat (OBJECT_MSL): authored top {top_z:.2f}")
        else:
            notes.append(
                f"DRAPED placement: the authored top {y1:+.3f} m is an OFFSET over the solved "
                f"ground (anchor {o.anchor_z:.2f} is the DEM there), not a datum — the deck's "
                f"ENDS govern (§33 (4))")
        k = k_by_res.get(o.path, 0)
        k_by_res[o.path] = k + 1
        out.append(WallPlate(f"{ID_PREFIX}:{name}@{k}", o.path, o.id, plan, (e0, e1),
                             length, width, float(vmax - vmin), float(y1), top_z,
                             tuple(b_ok), tuple(d_ok), tuple(notes)))
    out.sort(key=lambda p: p.id)
    stats.plates = len(out)
    stats.bore_plates = sum(1 for p in out if p.bore_ways)
    stats.deck_plates = sum(1 for p in out if not p.bore_ways)
    stats.read_s = time.perf_counter() - t0
    return out, stats
