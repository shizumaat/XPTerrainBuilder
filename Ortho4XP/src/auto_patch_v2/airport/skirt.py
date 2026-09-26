"""THE FOUNDATION-SKIRT READER (owner RULINGS 2026-09-10af / 10ag; spec
``design-surface-spec.md`` §22).

The owner's discriminator, verbatim in 10af: "if the entire building is
uniform across its bottom, then it's just foundations and we can take
advantage of that to allow the building to sit on a sloping surface
without having any portion of the building floating and no ramps
needed", against "a relatively small, approximately road width extension
to render the door or corridor walls below the surface".

So a FOUNDATION SKIRT is a property of the object's BELOW-ZERO geometry
alone, read per RESOURCE in the AUTHORED frame and independent of where
the placement stands: a uniform below-zero extent of depth ``s`` across
the footprint — the share of the footprint's PERIMETER that carries
below-zero geometry is at least ``[skirt] perimeter_fraction``, and those
pieces agree in depth within ``depth_tolerance_m``.  A corridor or a door
well meets the perimeter only at its ends and reads a small fraction, so
it is never a skirt here; that clause is Law C's narrow-cut test (10af
(ii)), which imports THIS reader rather than growing a second one.

Two consumers, both in §22:

* ``classify/evidence._pads`` — a pad whose area is covered by skirted
  placements and whose DEM relief is within their skirt drops: a skirted
  building needs no pad, the ground under it keeps its design surface;
* ``airport/rebake_plan`` -> ``emit/clusters`` — a body every one of
  whose members is skirted seats at its LOW-side foot, never 10i's
  median (the median would float the low side by half the relief).

Nothing here reads the DEM except :func:`ring_relief_m`, which is the
one implementation of "the relief across a ring" (``planar/structures``
delegates to it).  Every number is a law argument; none lives here.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
import shapely
from shapely.geometry import MultiPoint, Polygon
from shapely.ops import unary_union

from ..model.frame import XY
from . import bulk_geos as _bulk
from . import frame_entry as _fe
from . import obj8 as _obj8
from .obj8_clip import _bulk_polys, _clip_component

__all__ = ["SkirtReading", "reading", "skirt_depth", "is_skirt",
           "below_zero_perimeter_fraction", "footprint", "placement_footprint",
           "ring_relief_m", "skirted_placements"]


@_dc.dataclass(frozen=True)
class SkirtReading:
    """One resource's below-zero reading (see the module doc).

    ``depth_m`` is the skirt's depth ``s`` — the SHALLOWEST below-zero
    extent among the pieces that reach the footprint's perimeter, which
    is what a relief must stay inside for nothing to float — or ``None``
    when the object carries no skirt.  ``reason`` names the refusal."""

    skirt: bool
    depth_m: float | None
    perimeter_fraction: float
    depth_min_m: float
    depth_max_m: float
    footprint_perimeter_m: float
    below_zero: bool
    reason: str


_NO_GEOMETRY = SkirtReading(False, None, 0.0, 0.0, 0.0, 0.0, False,
                            "no geometry")


def _plan_union(v, tris_list: _t.Sequence) -> Polygon | None:
    """The plan union of triangles, or ``None``."""
    polys: list = []
    for tris in tris_list:
        polys.extend(_bulk_polys(v, tris))
    if not polys:
        return None
    u = unary_union(polys)
    if not u.is_valid:
        u = shapely.make_valid(u)
    if u.is_empty:
        return None
    return u


def footprint(cache: _obj8.ResourceCache, path: str):
    """The resource's PLAN footprint in the authored frame: the union of
    every genuine component's triangles projected to ``(x, z)``.  A shell
    of vertical walls projects to zero area, so the floor and roof plates
    carry it; with no area at all the convex hull of the solid plan
    points stands in (a hollow shell of vertical faces only)."""
    geom = cache.geometry(path)
    if geom is None or geom.solid.shape[0] == 0:
        return None
    comps = cache.genuine(path) or cache.components(path)
    u = _plan_union(geom.vertices, [c.tris for c in comps])
    if u is not None and u.area > 0.0:
        return u
    pts = geom.vertices[geom.solid.reshape(-1)][:, [0, 2]]
    hull = MultiPoint([tuple(p) for p in pts.tolist()]).convex_hull
    return hull if hull.geom_type == "Polygon" and hull.area > 0.0 else None


def component_footprint(cache: _obj8.ResourceCache, path: str,
                        comps: _t.Sequence[int]):
    """:func:`footprint` restricted to the NAMED components (indices into
    ``cache.components(path)``, which is what ``Part.comp`` is) — ONE
    BODY's own plan extent in the authored frame, or ``None``.

    A body's PAD needs the body's footprint, not the resource's: Aerosoft
    LEMD authors 150 separate canopy modules into one ``.obj``, so
    :func:`footprint` there is the whole old terminal.  Measured round 5
    (owner RULINGS 2026-09-11p (1)): the alternatives both fail — the
    FEET's convex hull of a colonnade is a 0.18 m ribbon (nine column
    bases on a line: 9.7 m² over a 52.8 m span, folded by
    ``building_pad.min_area_m2`` and unemittable in a 0.5 m identity
    grid), and the union of the parts' AXIS-ALIGNED plan boxes
    over-covers a diagonal canopy by 6x (2,358 m² for the same module)
    and puts its representative point outside the boundary gate.  The
    components' own triangles are the body's real footprint."""
    geom = cache.geometry(path)
    if geom is None or geom.solid.shape[0] == 0:
        return None
    all_comps = cache.components(path)
    tris = [all_comps[i].tris for i in comps if 0 <= i < len(all_comps)]
    if not tris:
        return None
    u = _plan_union(geom.vertices, tris)
    if u is not None and u.area > 0.0:
        return u
    # a hollow shell of vertical faces only — :func:`footprint`'s own
    # fallback, restricted to these components
    import numpy as _np
    pts = geom.vertices[_np.concatenate(tris).reshape(-1)][:, [0, 2]]
    hull = MultiPoint([tuple(p) for p in pts.tolist()]).convex_hull
    return hull if hull.geom_type == "Polygon" and hull.area > 0.0 else None


def _exteriors(geom) -> list:
    return [g.exterior for g in shapely.get_parts(geom)
            if g.geom_type == "Polygon"] or (
        [geom.exterior] if geom.geom_type == "Polygon" else [])


def _rim_hits(below: _t.Sequence, exteriors: _t.Sequence, tol: float) -> list[bool]:
    """Per below-zero piece, whether it comes within ``tol`` of any
    footprint exterior (it REACHES the perimeter)."""
    # §B.3 (#28): one prepared ``dwithin`` per exterior over every piece
    # (``bulk_geos.within_distance`` is exactly ``e.distance(g) <= tol``)
    hit = np.zeros(len(below), dtype=bool)
    for e in exteriors:
        hit |= _bulk.within_distance(e, below, tol)
    return hit.tolist()


def reading(cache: _obj8.ResourceCache, path: str, law) -> SkirtReading:
    """The resource's skirt reading, memoised on ``cache`` (the pack is
    parsed once for classify, the planar pass and the re-seat plan)."""
    memo = cache.skirt
    got = memo.get(path)
    if got is not None:
        return got
    got = _read(cache, path, law)
    memo[path] = got
    return got


def _read(cache: _obj8.ResourceCache, path: str, law) -> SkirtReading:
    sk = law.tables.structures.skirt
    geom = cache.geometry(path)
    if geom is None or geom.solid.shape[0] == 0:
        return _NO_GEOMETRY
    # the O(n) pre-screen (``y_range``): a resource with nothing under its
    # authored zero can carry no skirt and is never componented for one
    min_y = cache.y_range(path)[0]
    if not (min_y < -1e-9):
        return _dc.replace(_NO_GEOMETRY, reason="no below-zero geometry")
    fp = footprint(cache, path)
    if fp is None:
        return _dc.replace(_NO_GEOMETRY, below_zero=True, reason="no footprint")
    per = sum(e.length for e in _exteriors(fp))
    if per <= 0.0:
        return _dc.replace(_NO_GEOMETRY, below_zero=True, reason="no footprint perimeter")
    v = geom.vertices
    tol = sk.edge_tolerance_m
    below: list = []
    depths: list[float] = []
    for comp in cache.genuine(path):
        if comp.min_y >= -1e-9:
            continue
        g = _clip_component(v, comp, 0.0, True)
        if g is None or g.is_empty or g.area <= 0.0:
            continue
        below.append(g)
        depths.append(-float(comp.min_y))
    if not below:
        return _dc.replace(_NO_GEOMETRY, below_zero=True, footprint_perimeter_m=per,
                           reason="below-zero vertices carry no genuine solid")
    bu = unary_union(below)
    if not bu.is_valid:
        bu = shapely.make_valid(bu)
    band = bu.buffer(tol)
    on_rim = sum(e.intersection(band).length for e in _exteriors(fp))
    frac = min(1.0, on_rim / per)
    # the depths of the pieces that actually REACH the perimeter: a deep
    # lift pit inside a skirted building is not the skirt's depth
    rim_depths = [d for g, d, hit in zip(below, depths, _rim_hits(below, _exteriors(fp), tol))
                  if hit]
    if not rim_depths:
        rim_depths = depths
    d_min, d_max = min(rim_depths), max(rim_depths)
    out = _dc.replace(_NO_GEOMETRY, perimeter_fraction=frac, depth_min_m=d_min,
                      depth_max_m=d_max, footprint_perimeter_m=per, below_zero=True)
    if frac < sk.perimeter_fraction:
        return _dc.replace(out, reason=(
            f"below-zero perimeter fraction {frac:.2f} < {sk.perimeter_fraction} "
            "(a narrow cut, not a skirt)"))
    if d_max - d_min > sk.depth_tolerance_m:
        return _dc.replace(out, reason=(
            f"below-zero depth {d_min:.2f}-{d_max:.2f} m spreads more than "
            f"{sk.depth_tolerance_m} m — not one uniform extent"))
    if d_min < sk.min_depth_m:
        return _dc.replace(out, reason=(
            f"skirt depth {d_min:.2f} m < {sk.min_depth_m} m — a lip, not a foundation"))
    return _dc.replace(out, skirt=True, depth_m=d_min, reason="skirt")


def skirt_depth(cache: _obj8.ResourceCache, path: str, law) -> float | None:
    """``s`` — the skirt's depth, or ``None`` when the resource has none."""
    return reading(cache, path, law).depth_m


def is_skirt(cache: _obj8.ResourceCache, path: str, law) -> bool:
    """Whether the resource's below-zero geometry is a FOUNDATION SKIRT
    (10af): uniform across the footprint, not a road-width cut."""
    return reading(cache, path, law).skirt


def below_zero_perimeter_fraction(cache: _obj8.ResourceCache, path: str, law) -> float:
    """The share of the footprint's perimeter carrying below-zero
    geometry — Law C's narrow-cut clause (ii) reads this directly."""
    return reading(cache, path, law).perimeter_fraction


def placement_footprint(cache: _obj8.ResourceCache, path: str, law,
                        xy: XY, heading_deg: float):
    """The resource's plan footprint carried into the AIRPORT FRAME at a
    placement (``obj8.placement_affine``), or ``None``."""
    fp = footprint(cache, path)
    if fp is None:
        return None
    # §51 (4) row 14 — ENTRY
    return _fe.enter([fp], _obj8.placement_affine(xy, heading_deg),
                     _fe.quantum(law))[0]


def skirted_placements(airport, law, cache: _obj8.ResourceCache | None = None
                       ) -> tuple[dict[str, float], _obj8.ResourceCache]:
    """``{placement id: skirt depth s}`` over the airport's resolved
    ``.obj`` placements, and the cache the readings are memoised on (the
    caller passes its own so the pack is parsed once).

    A BASIN MEMBER IS NEVER SKIRTED (owner RULINGS 2026-09-10ax (2)).
    The basin admission runs FIRST (``airport/basin_witness.py``) and its
    members are exempt HERE — at the one derivation site of "skirted", so
    both consumers inherit it: ``classify/evidence._drop_skirted`` keeps
    the pad standing over a pit, and ``emit/clusters`` keeps 10i's seat
    for it.  A skirt is a foundation under a building that stands ABOVE
    the ground; a basin's members ARE the pit, and their below-zero
    geometry is uniform across the footprint for exactly that reason.
    Measured at LEMD: ``Ground-FSX-LEMD36``/``LEMD85`` read skirts of
    7.01/7.03 m and dropped the T4S terminal pad ``building16``, which
    cost the pit its cut — ``basin_witness``' module doc has the chain."""
    sk = law.tables.structures.skirt
    cache = cache or _obj8.ResourceCache(law.tables.structures.basin.min_solid_thickness_m,
                                        _fe.quantum(law))
    out: dict[str, float] = {}
    if not (sk.drops_pad or sk.seat_low_side):
        return out, cache
    from .basin_witness import basin_member_ids
    basins = basin_member_ids(airport, law, cache)
    for o in getattr(airport, "dsf_objects", ()):
        resolved = getattr(o, "resolved_path", None)
        if not resolved or not str(o.path).lower().endswith(".obj"):
            continue
        if o.id in basins:
            continue                      # a facility, not a foundation
        r = reading(cache, resolved, law)
        if r.skirt and r.depth_m is not None:
            out[o.id] = r.depth_m
    return out, cache


def ring_relief_m(dem_z: _t.Callable[[float, float], float],
                  ring: _t.Sequence[XY]) -> float:
    """The DEM relief across a ring (max − min over its vertices).  ONE
    implementation: ``planar/structures._pad_relief_m`` delegates here.
    ``inf`` when the DEM samples nothing (never silently 0)."""
    zs = [float(dem_z(float(x), float(y))) for x, y in ring]
    zs = [z for z in zs if not math.isnan(z)]
    return (max(zs) - min(zs)) if zs else math.inf
