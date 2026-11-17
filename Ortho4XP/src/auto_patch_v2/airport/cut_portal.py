"""A PORTAL IN A CUT: a pack frame whose walls stand from a mapped road's
floor up to the ground over its bore (#2120 R2 Part P; spec
``sim-review/2120-R2.md`` §3; owner RULINGS 2026-11-16d / 16l / 16n /
16s / 16t).

Some packs author a covered road's portals as ONE frame each: walls from
the road floor up to a roof at the level of the ground the bore runs
under, the frame's zero at the road.  Every other portal reader asks for
geometry UNDER the zero (``portal_objects`` a roof the ground covers,
``trench_objects`` a trench below grade, ``covered_ground._mouth_walls``
a solid reaching the mouth depth under the zero) -- such a frame has none,
so it was read as a building: a pad minted over its plan and its zero
seated by its feet on whatever ground lay under it, the roof standing
~20 m over the cover.  MEASURED KATL (Orbx 2026-11, I-285 under runway
10/28): four frames, walls y 0..20.0 with a 0.5 m parapet to 20.5, a roof
at y 20.0 of 3,783-12,559 m2; the lidar reads the motorway floor 282-293
under them and the bank 297.5-301.3 beside the cut.

THE WITNESS (airport-level inputs only, so the pre-classification shade
and the planar reader read the same frames): a placement is a PORTAL IN A
CUT when

1. its plan's hull crosses a mapped bore's axis (``deck_signature.
   is_tunnel_way`` under ``[tunnel] admitted_values``);
2. its static solid stands at least ``[tunnel] mouth_depth_m`` tall, ON
   its zero: nothing under it (or floating over it) by
   ``[tunnel.object] shell_floor_min_m`` -- the walls stand on the road; a
   frame with geometry under its zero is the trench / shell / portal
   readers' (``trench_objects``, ``tunnel_objects``, ``portal_objects``);
3. the DEM under that axis inside the hull -- all of it -- stands at least
   the mouth depth under the highest DEM within ``[tunnel]
   covered_rim_search_m`` of it: the frame stands IN the cut the airport's
   ground shows (with a DEM that cannot see it there is no cut to stand
   in, and nothing is admitted);
4. it is ROOFED over the bore: the near-horizontal faces at the top of
   its tallest component (``[tunnel.object] plate_normal_y_min``, within
   ``plate_bin_m``, ``plate_min_area_m2`` of them) stand over at least half
   the axis inside its hull -- the cover deck a portal carries, the plate
   its seat puts on the cover (``airport/cut_portal_seat``);
5. less than half its plan lies over the airport's paved surfaces (a hard
   structure an aircraft uses is never a portal: ``Airport.pavements`` and
   the runways, the apt.dat surfaces the airport loaded); and
6. it is no deck: neither an ``ATTR_hard_deck`` frame nor a geometry deck
   the signature accepted (``PlacedObject.deck_kind`` "flag"/"signature").

MEASURED (census over every registered capture, lane lkatlP): tests 1, 2's
height, 5 and 6 alone admit 138 frames at 20 airports -- terminals,
car parks, streetlights over rail bores; the axis read whole (3) leaves 14,
standing on the zero 6 (KATL's four, an EFHK infrastructure block, KDEN's
train-trench walls), and the roof over the bore (4: KATL 89-100 % of the
axis, the other two 0 %) KATL's four.

Its DEPTH is the cut's (the cover level less the floor under the axis)
capped by its own solid's height: the step the mouth wall declares.

Nothing here names a pack, a resource or an airport; every number is a
``structures.toml`` key.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from . import frame_entry as _fe
from . import obj8 as _obj8
from .deck_signature import is_tunnel_way
from .dem import dem_z_many

__all__ = ["CutPortal", "attach_cut_portals", "plan_union", "log_lines"]

#: sampling step along a bore axis inside a frame's hull (metres): the
#: DEM's own metre posting -- the floor is the lowest of these
_STEP_M = 1.0
#: the spacing of the across-axis cover readings along a crossing, and of
#: the samples across (metres): the cover is a level, not a crest
_SECTION_M = 10.0
_ACROSS_M = 2.0
#: the prefilter reads the plan box's crossing this many times coarser and
#: keeps every box whose relief reaches HALF the mouth depth: a loose
#: necessary condition, so no frame the full reading admits is lost
_COARSE = 4
#: the decks the witness refuses (``obj8.PlacedObject.deck_kind``)
_DECK_KINDS = ("flag", "signature")


@_dc.dataclass(frozen=True)
class CutPortal:
    """One pack frame read as a portal in a cut, in the airport frame."""

    object_id: str
    resource: str
    #: the placed plan of its static solids (frame metres)
    plan: _t.Any
    #: the top of its TALLEST static component (the headwall / roof the
    #: cover meets); the solid above it (a parapet) stands proud of it
    top_y: float
    #: the static solid's bottom and top over its zero
    bottom_y: float
    solid_top_y: float
    #: the mapped bores whose axes cross its hull (way ids)
    bores: tuple[int, ...]
    #: the lowest DEM under those axes inside the hull, and the highest DEM
    #: within ``covered_rim_search_m`` of them (the cover's level)
    floor_z: float
    cover_z: float

    @property
    def depth_m(self) -> float:
        """The cut's depth here, capped by the frame's own solid."""
        return min(self.cover_z - self.floor_z, self.top_y - self.bottom_y)


def _bore_lines(airport, law) -> list[tuple[int, LineString]]:
    tn = law.tables.structures.tunnel
    return [(w.id, LineString(w.points)) for w in getattr(airport, "osm_ways", ()) or ()
            if len(w.points) >= 2 and is_tunnel_way(w.tags, tn.admitted_values)]


def _paved(airport):
    """The airport's paved surfaces as one polygon (apt.dat 110 rows and the
    runways' own rectangles); empty when it has none."""
    polys = []
    for p in getattr(airport, "pavements", ()) or ():
        try:
            g = Polygon(p.outer, [h for h in p.holes if len(h) >= 3])
        except (ValueError, TypeError):
            continue
        polys.append(g if g.is_valid else g.buffer(0))
    for r in getattr(airport, "runways", ()) or ():
        a, b = r.ends[0].xy, r.ends[1].xy
        polys.append(LineString([a, b]).buffer(0.5 * float(r.width_m), cap_style="flat"))
    polys = [g for g in polys if not g.is_empty]
    return unary_union(polys) if polys else Polygon()


def _section_points(crossings: list, reach: float, coarse: int = 1
                    ) -> tuple[np.ndarray, np.ndarray, int]:
    """``(xs, ys, m)``: the points along ``crossings`` (the bore axes inside
    a hull) every ``_STEP_M`` -- the first ``m`` -- then the points across
    them within ``reach``, every ``_SECTION_M`` along; every spacing times
    ``coarse`` (the prefilter's reading)."""
    d = np.arange(-reach, reach + 1e-9, _ACROSS_M * coarse)
    along_x, along_y, across_x, across_y = [], [], [], []
    for seg in crossings:
        n = max(2, int(np.ceil(seg.length / (_STEP_M * coarse))) + 1)
        pts = shapely.get_coordinates(shapely.line_interpolate_point(
            seg, np.linspace(0.0, seg.length, n)))
        xs, ys = pts[:, 0], pts[:, 1]
        (x0, y0), (x1, y1) = seg.coords[0], seg.coords[-1]
        span = float(np.hypot(x1 - x0, y1 - y0)) or 1.0
        ux, uy = (x1 - x0) / span, (y1 - y0) / span
        along_x.append(xs)
        along_y.append(ys)
        k = np.arange(0, n, max(1, int(round(_SECTION_M / _STEP_M))))
        across_x.append((xs[k, None] - uy * d[None, :]).ravel())
        across_y.append((ys[k, None] + ux * d[None, :]).ravel())
    m = sum(len(q) for q in along_x)
    if not along_x:                   # a bore only touching the hull: no crossing
        return np.empty(0), np.empty(0), 0
    return np.concatenate(along_x + across_x), np.concatenate(along_y + across_y), m


def _cut_levels(dem, groups: list, reach: float, coarse: int = 1) -> list:
    """Per group of crossings, ``(floor, axis top, cover)`` -- the lowest
    and the highest DEM along them and the highest within ``reach`` across
    them -- or ``None``; ONE DEM call for every group."""
    parts = [_section_points(segs, reach, coarse) for segs in groups]
    if not parts:
        return []
    z = dem_z_many(dem, np.concatenate([p[0] for p in parts]),
                   np.concatenate([p[1] for p in parts]))
    out, k = [], 0
    for xs, _ys, m in parts:
        low, high = z[k:k + m], z[k + m:k + len(xs)]
        k += len(xs)
        ok = np.isfinite(low).any() and np.isfinite(high).any()
        out.append((float(np.nanmin(low)), float(np.nanmax(low)), float(np.nanmax(high)))
                   if ok else None)
    return out


def _crossings(hull, lines) -> list:
    """The pieces of ``lines`` inside ``hull``."""
    out = []
    for ln in lines:
        x = ln.intersection(hull)
        for g in getattr(x, "geoms", [x]):
            if g.geom_type == "LineString" and g.length > 0.0:
                out.append(g)
    return out


def _authored_hull(g, genuine) -> np.ndarray | None:
    """The authored plan hull ``(x, z)`` of the genuine solids, or ``None``."""
    from scipy.spatial import ConvexHull, QhullError
    xz = g.vertices[np.concatenate([c.tris.ravel() for c in genuine])][:, [0, 2]]
    try:
        return xz[ConvexHull(xz).vertices]
    except (QhullError, ValueError):
        return None


def _placed_hull(o, xz: np.ndarray):
    """The authored hull ``xz`` placed by ``o`` (frame metres) -- the cheap
    first reading of where the frame stands."""
    a, b, d, e, xo, yo = _obj8.placement_affine(o.xy, o.heading_deg)
    return Polygon(np.column_stack([a * xz[:, 0] + b * xz[:, 1] + xo,
                                    d * xz[:, 0] + e * xz[:, 1] + yo]))


def _roofed(o, g, genuine, segs, law) -> bool:
    """Test (4): the near-horizontal faces at the top of ``o``'s tallest
    component stand over at least half the axis ``segs`` inside its hull."""
    from .obj8_clip import _bulk_polys
    from .object_cut import _face_normals_y, _plan_area
    ob = law.tables.structures.tunnel.object
    tall = max(genuine, key=lambda c: (c.max_y - c.min_y, c.max_y))
    tris = np.concatenate([c.tris for c in genuine])
    v = g.vertices
    top = (_face_normals_y(v, tris) >= ob.plate_normal_y_min) & (
        np.abs(v[tris][:, :, 1].max(axis=1) - tall.max_y) <= ob.plate_bin_m)
    if not top.any() or float(_plan_area(v, tris)[top].sum()) < ob.plate_min_area_m2:
        return False
    roof = _fe.enter([_fe.union(_bulk_polys(v, tris[top]), "cut_portal._roofed")],
                     _obj8.placement_affine(o.xy, o.heading_deg), _fe.quantum(law))[0]
    total = sum(s.length for s in segs)
    return roof is not None and total > 0.0 and \
        2.0 * sum(s.intersection(roof).length for s in segs) >= total


def _near_cuts(objects, bores, dem, depth_min: float, reach: float) -> dict[int, list[int]]:
    """``object index -> bore indices`` of every placement whose plan box
    crosses a bore where the DEM reads a cut the mouth depth deep (the box's
    crossing read leniently -- its lowest point against the highest ground,
    a NECESSARY condition of test (3) on the hull inside it), before any of
    its geometry is touched.  Decks (test 6) never enter."""
    boxes = [getattr(o, "plan_bbox", None) for o in objects]
    keep = [i for i, (o, b) in enumerate(zip(objects, boxes, strict=True))
            if b is not None and o.resolved is not None and getattr(o, "hard_deck", None) is None
            and getattr(o, "deck_kind", "") not in _DECK_KINDS]
    if not keep:
        return {}
    tree = STRtree([ln for _i, ln in bores])
    pairs = tree.query(np.array([boxes[i] for i in keep], dtype=object), predicate="intersects")
    near: dict[int, list[int]] = {}
    for a, j in zip(pairs[0].tolist(), pairs[1].tolist(), strict=True):
        near.setdefault(keep[a], []).append(j)
    idx = sorted(near)
    levels = _cut_levels(dem, [_crossings(boxes[i], [bores[j][1] for j in near[i]])
                               for i in idx], reach, _COARSE)
    return {i: near[i] for i, lv in zip(idx, levels, strict=True)
            if lv is not None and lv[2] - lv[0] >= 0.5 * depth_min}


def _candidates(objects, cache, bores, near, depth_min: float, on_zero: float) -> list:
    """``(object, genuine, geometry, crossed way ids, crossings)`` of every
    placement of ``near`` (:func:`_near_cuts`) the witness's tests (1) and
    (2) admit."""
    out, hulls = [], {}
    for i in sorted(near):
        o = objects[i]
        genuine = cache.genuine(o.resolved)
        bottom = min(c.min_y for c in genuine) if genuine else 0.0
        if (not genuine or abs(bottom) >= on_zero
                or max(c.max_y for c in genuine) - bottom < depth_min):
            continue
        g = cache.geometry(o.resolved)
        if o.resolved not in hulls:
            hulls[o.resolved] = None if g is None else _authored_hull(g, genuine)
        if hulls[o.resolved] is None:
            continue
        hull = _placed_hull(o, hulls[o.resolved])
        crossed = [bores[j] for j in near[i] if bores[j][1].intersects(hull)]
        segs = _crossings(hull, [ln for _w, ln in crossed])
        if segs:
            out.append((o, genuine, g, tuple(sorted({w for w, _ln in crossed})), segs))
    return out


def _cut_portals(airport, objects: _t.Sequence[_obj8.PlacedObject],
                cache: _obj8.ResourceCache, law) -> tuple[CutPortal, ...]:
    """Every placement of ``objects`` the witness reads as a portal in a cut
    (module doc), in ``objects`` order; ``()`` with no bore, DEM or cache."""
    from .portal_objects import _solids_plan
    dem = getattr(airport, "dem", None)
    if law is None or cache is None or dem is None or not objects:
        return ()
    bores = _bore_lines(airport, law)
    if not bores:
        return ()
    tn = law.tables.structures.tunnel
    depth_min = float(tn.mouth_depth_m)
    reach = float(tn.covered_rim_search_m)
    near = _near_cuts(objects, bores, dem, depth_min, reach)
    cands = _candidates(objects, cache, bores, near, depth_min,
                        float(tn.object.shell_floor_min_m))
    levels = _cut_levels(dem, [c[4] for c in cands], reach)
    paved = None
    out = []
    for (o, genuine, g, ids, segs), lv in zip(cands, levels, strict=True):
        if lv is None or lv[2] - lv[1] < depth_min or not _roofed(o, g, genuine, segs, law):
            continue
        plan = _solids_plan(o, g, genuine, law)
        if plan is None or plan.is_empty:
            continue
        paved = _paved(airport) if paved is None else paved
        if not paved.is_empty and 2.0 * plan.intersection(paved).area >= plan.area:
            continue
        tall = max(genuine, key=lambda c: (c.max_y - c.min_y, c.max_y))
        out.append(CutPortal(str(o.id), str(o.path), plan, float(tall.max_y),
                             min(float(c.min_y) for c in genuine),
                             max(float(c.max_y) for c in genuine), ids, lv[0], lv[2]))
    return tuple(out)


def attach_cut_portals(airport, objects, cache, law):
    """``airport`` with :attr:`Airport.cut_portals` read -- called ONCE at
    the pack stage, before the entrance shade (``pipeline/build``, the
    replay); every reader takes them from there."""
    if getattr(airport, "frame", None) is None:
        return airport
    return _dc.replace(airport, cut_portals=_cut_portals(airport, objects, cache, law))


def plan_union(portals: _t.Sequence[CutPortal]):
    """The union of the portals' plans (the shade's share), or ``None``."""
    polys = [p.plan for p in portals if p.plan is not None and not p.plan.is_empty]
    return unary_union(polys) if polys else None


def log_lines(icao: str, portals: _t.Sequence[CutPortal]) -> list[str]:
    """One line per portal read (the build log)."""
    return [f"[{icao}] portal in a cut {p.object_id} ({p.resource.rsplit('/', 1)[-1]}): "
            f"bores {list(p.bores)}, floor {p.floor_z:.2f}, cover {p.cover_z:.2f}, "
            f"top y {p.top_y:+.2f} (solid {p.bottom_y:+.2f}..{p.solid_top_y:+.2f}), "
            f"depth {p.depth_m:.2f} m, plan {p.plan.area:,.0f} m2" for p in portals]
