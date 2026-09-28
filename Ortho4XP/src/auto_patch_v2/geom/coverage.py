"""THE PATCH COVERAGE — one polygon, the union of every planar face.

MOVED here from ``emit/bank`` (#59): ``airport/road_profile`` (the road
clamp's band) and ``emit`` (the bank, the road join) both read it, and a
producer may not import ``emit``.  ``geom`` is the leaf every layer may
read, so the ONE implementation lives here; ``emit.bank`` re-exports it.
The map is read structurally (``faces`` / ``vertices`` /
``ring_vertices``) — ``geom`` imports nothing of v2.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union

__all__ = ["coverage_polygon"]


class _PlanarLike(_t.Protocol):
    """What the union reads of ``model.planar.PlanarMap``."""

    faces: _t.Mapping[_t.Any, _t.Any]
    vertices: _t.Mapping[_t.Any, _t.Any]

    def ring_vertices(self, ring: _t.Any) -> _t.Iterable[_t.Any]: ...


def coverage_polygon(planar: _PlanarLike) -> _t.Any:
    """THE PATCH COVERAGE as ONE polygon in the frame: the union of EVERY
    planar face (the structure voids included — their rim is emitted as a
    constrained ring, so the ground inside them is patch geometry and takes
    no bank).  ``None`` when the map has no face."""
    polys = []
    for f in planar.faces.values():
        ring = [planar.vertices[v].xy for v in planar.ring_vertices(f.ring)]
        if len(ring) < 3:
            continue
        holes = [[planar.vertices[v].xy for v in planar.ring_vertices(h)]
                 for h in f.holes]
        p = Polygon(ring, [h for h in holes if len(h) >= 3])
        if not p.is_valid:
            p = p.buffer(0)
        if not p.is_empty:
            polys.append(p)
    if not polys:
        return None
    cov = unary_union(polys)
    return None if cov.is_empty else cov
