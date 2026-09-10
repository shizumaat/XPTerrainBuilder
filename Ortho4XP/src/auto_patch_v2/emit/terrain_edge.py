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


def _outward_slab(ln, cov, reach: float, eps: float):
    """THE GROUND OUTWARD OF ONE EDGE RUN, out to ``reach``.

    NOT an offset polygon and not a single-sided buffer: an offset that
    large on an edge whose own curvature radius is smaller FOLDS, and the
    fold is silently cancelled — measured at CYXY, a 66.9 m edge offset
    205 m self-intersects 170 m out and returns 5,804 m² of a 13,720 m²
    slab, leaving the bank beyond the edge alive as a 9.5 m mound 125 m
    down the plateau.

    The region is instead the band within ``reach`` of the run MINUS the
    design coverage, keeping only what still touches the run: inboard of
    an edge the coverage IS the design surface, so cutting it away leaves
    the outward side, and an inboard scrap beyond the coverage is
    separated from the run by the coverage and dropped."""
    from shapely.ops import unary_union
    band = ln.buffer(reach).difference(cov)
    if band.is_empty:
        return None
    keep = [g for g in getattr(band, "geoms", [band])
            if g.geom_type == "Polygon" and g.distance(ln) <= eps]
    return unary_union(keep) if keep else None


def no_bank_region(planar: PlanarMap, law: Law, cov):
    """THE GROUND BEYOND THE EDGE, as one geometry to cut out of the
    banked region (``emit/bank.with_bank``), or ``None``.

    Per edge segment run: the half-slab of ``bank_max_width_m +
    bank_min_width_m`` on the side the design coverage is NOT on — the
    whole reach a bank could otherwise have taken — minus the coverage
    itself, which no cut may ever eat into."""
    from shapely.ops import unary_union
    lines = edge_lines(planar)
    if not lines or cov is None or cov.is_empty:
        return None
    d = law.tables.emit.design
    reach = float(d.bank_max_width_m) + float(d.bank_min_width_m)
    eps = snap_margin_m(law)
    slabs = [s for s in (_outward_slab(ln, cov, reach, eps) for ln in lines)
             if s is not None]
    if not slabs:
        return None
    geom = unary_union(slabs).difference(cov)
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
