"""THE TERRAIN EDGE at emit time (owner RULINGS 2026-09-10b/10c; spec §19
(3) and §19.3 C7 / C12).

The adjacent-ground rings are clipped at the physical edge in the planar
stage (``planar/terrain_edge.py``); this module is what the EMIT stage
does with the edge segments the clip left on the map:

  * §19 (3) BEYOND THE EDGE: NOTHING — no bank is emitted from an edge
    segment.  :func:`no_bank_region` is the §18 water-line mechanism
    generalised: the region OUTWARD of every edge segment is cut out of
    the banked region at the SINGLE derivation site in ``emit/bank.py``,
    so no annulus and no foot node lands beyond the edge and the mesh
    drapes the DEM's own slope from the ring outward.
  * §19.3 C12: the edge segments are published as ``terrain_edge`` open
    ways over the boundary vertices they already run through — no new
    node, no new geometry (the ``crown_spine`` precedent) — so the owner
    can read the edge in the KML beside the shapes it ended.
"""
from __future__ import annotations

import dataclasses as _dc

from ..law.model import Law
from ..law.tables import snap_margin_m
from ..model.planar import PlanarMap
from .surface import GradedSurface, SurfaceBreakline

__all__ = ["EDGE_KIND", "edge_lines", "no_bank_region", "with_terrain_edges"]

#: The breakline kind carrying an edge segment run (``o4_feature=terrain_edge``).
EDGE_KIND = "terrain_edge"


def edge_lines(planar: PlanarMap):
    """The map's terrain-edge segments as shapely lines (empty when the
    airport has no edge — every region ended on its own)."""
    from shapely.geometry import LineString
    out = []
    for coords in getattr(planar, "terrain_edges", ()) or ():
        pts = [(float(x), float(y)) for x, y in coords]
        if len(pts) >= 2:
            out.append(LineString(pts))
    return out


def _outward_slab(ln, keep_in, reach: float, eps: float, near: float):
    """THE GROUND OUTWARD OF ONE EDGE RUN, from ``keep_in`` out to
    ``reach``.

    NOT an offset polygon and not a single-sided buffer: an offset that
    large on an edge whose own curvature radius is smaller FOLDS, and the
    fold is silently cancelled — measured at CYXY, a 66.9 m edge offset
    205 m self-intersects 170 m out and returns 5,804 m² of a 13,720 m²
    slab, leaving the bank beyond the edge alive as a 9.5 m mound 125 m
    down the plateau.

    The region is instead the band within ``reach`` of the run MINUS
    ``keep_in``, keeping only what still touches the run (within ``near``,
    the width of what was kept): inboard of an edge ``keep_in`` IS the
    design surface and its collar, so cutting it away leaves the outward
    side, and an inboard scrap beyond it is separated from the run by it
    and dropped."""
    from shapely.ops import unary_union
    band = ln.buffer(reach).difference(keep_in)
    if band.is_empty:
        return None
    keep = [g for g in getattr(band, "geoms", [band])
            if g.geom_type == "Polygon" and g.distance(ln) <= near + eps]
    return unary_union(keep) if keep else None


def no_bank_region(planar: PlanarMap, law: Law, cov):
    """THE GROUND BEYOND THE EDGE, as one geometry to cut out of the
    banked region (``emit/bank.with_bank``), or ``None``.

    Per edge segment run: the half-slab of ``bank_max_width_m +
    bank_min_width_m`` on the side the design coverage is NOT on — the
    whole reach a bank could otherwise have taken — minus THE COVERAGE
    AND ITS MINIMUM-WIDTH COLLAR, which no cut may eat into.

    THE COLLAR IS WHY (owner RULINGS 2026-09-10g, the CYXY texture
    tearing).  Round 1 cut the slab back to ``cov`` itself, so the banked
    region's boundary came to rest ON the design coverage's own ring for
    the whole edge run.  ``bank._push_off`` then walks that run point by
    point: a vertex merely NEAR the coverage is pushed back out to
    ``bank_min_width_m``, while a vertex exactly ON it is left where it is
    (its nearest point of the coverage is itself — there is no direction
    to push along).  The foot ring emitted from that run therefore
    alternates between 0.01 m and 5.01 m from the strip's ring and CROSSES
    it: a zero-area needle between two constrained rings, which
    Triangle4XP fills to its recursion limit.  Measured on the CYXY
    plateau slope below the 32L end: 59,634 mesh vertices piled on 216
    distinct plan positions inside one 50 m cell, 119,264 triangles where
    the control mesh has 172, 18.4 M vertex pairs closer in plan than
    ``identity.min_distinct_spacing_m`` at different heights — the
    overlapping nodes the owner read as texture tearing.

    Cutting from the collar outward instead leaves that boundary at
    exactly ``bank_min_width_m`` from the coverage, where ``_push_off``
    has nothing to do and no two constrained rings can meet.  The bank at
    an edge is then the minimum-width collar the law already gives every
    ring, and NOTHING beyond it: the 200 m daylight reach that built the
    plateau wall is gone either way.  Recorded as a deviation from spec
    §19 (3)'s literal "no bank is emitted from an edge segment" — a
    5 m collar is emitted — because the alternative (dropping the run and
    emitting the foot open) breaks the CLOSED FOOT RING law, which
    ``emit/bank``'s own docstring records as measured: an open chain
    enters ``include_patches`` as a dummy way and the bank reverts to the
    raw DEM (§10.5, the 306 % transect)."""
    from shapely.ops import unary_union
    lines = edge_lines(planar)
    if not lines or cov is None or cov.is_empty:
        return None
    d = law.tables.emit.design
    reach = float(d.bank_max_width_m) + float(d.bank_min_width_m)
    min_w = float(d.bank_min_width_m)
    eps = snap_margin_m(law)
    keep_in = cov.buffer(min_w, join_style="mitre", mitre_limit=3.0)
    slabs = [s for s in (_outward_slab(ln, keep_in, reach, eps, min_w)
                         for ln in lines) if s is not None]
    if not slabs:
        return None
    geom = unary_union(slabs).difference(keep_in)
    return None if geom.is_empty else geom


def with_terrain_edges(surface: GradedSurface, planar: PlanarMap,
                       law: Law) -> GradedSurface:
    """The surface with one OPEN breakline per edge segment run, over the
    boundary vertices the run already passes through (§19.3 C12).  No new
    vertex is created: the way is a record of where the ground ends."""
    lines = edge_lines(planar)
    if not lines:
        return surface
    from shapely.strtree import STRtree
    from shapely import points as _points
    tol = snap_margin_m(law)
    have = {v.id for v in surface.vertices}
    ids = [v for v in planar.vertices if v in have]
    if not ids:
        return surface
    xs = [planar.vertices[v].xy[0] for v in ids]
    ys = [planar.vertices[v].xy[1] for v in ids]
    tree = STRtree(_points(xs, ys))
    next_bl = max((b.id for b in surface.breaklines), default=-1) + 1
    new: list[SurfaceBreakline] = []
    for k, ln in enumerate(lines):
        near = tree.query(ln.buffer(tol))
        chain = []
        for j in near:
            v = ids[int(j)]
            chain.append((ln.project(_points(xs[int(j)], ys[int(j)])), v))
        chain.sort()
        run = tuple(v for _s, v in chain)
        if len(run) < 2:
            continue
        new.append(SurfaceBreakline(next_bl, EDGE_KIND, f"terrain_edge:{k}", run))
        next_bl += 1
    if not new:
        return surface
    return _dc.replace(surface, breaklines=surface.breaklines + tuple(new))
