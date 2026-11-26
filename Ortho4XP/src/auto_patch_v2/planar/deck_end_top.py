"""A PACK DECK'S TOP AT AN END LINE IS ITS DRIVEN SURFACE THERE, NEVER ITS
HIGHEST VERTEX (#2238 / #2241; owner 2026-11-21 "if the object's roof is a
hard deck it must be seated flush with the taxiway"; RULINGS 2026-10-30a (1)
"flush at both end lines").

``planar/deck_bridge`` read each end line's top as the HIGHEST hard-deck
vertex within reach of its stations.  An ``ATTR_hard_deck`` block often
carries more than the driven slab: parapets and kerbs standing over it, the
roof's underside under it, a slab that falls along the end line.  The
highest vertex is then a parapet's top or the slab's high corner, and the
deck is seated that much UNDER the taxiway that welds to it.  MEASURED on
the 1.0.572 tile as X-Plane draws it (``tools/drawn_site.py``): a tunnel
roof (slab top y 5.00, parapets to y 6.54) sat 1.44-1.54 m under the
taxiway at both end lines; a deck whose slab falls 1.0 m along its end
lines (y 6.99 -> 7.98) sat 0.11-0.59 m under it.

THE READING: at every station of the end line, the HIGHEST near-horizontal
hard-deck face over it (``[bridge] deck_plate_normal_y_min``; a face the
station stands up to ``edge_m`` outside of is read on its plane -- the
stations lie on the ring), i.e. the surface a wheel rolls on there; the
end line's top is the MEDIAN over its stations, so a parapet a corner
station stands on is outvoted.  A station over no such face is not read;
an end line with none keeps the caller's reading.  Pure shape; nothing here
names a pack, a resource or an airport.
"""
from __future__ import annotations

import typing as _t

import numpy as np

from ..airport.bridge_witness import placed_faces, up_faces
from ..geom.lowest_face import every_z_at

__all__ = ["EDGE_M", "slab_faces", "station_tops", "driven_top"]

XY = tuple[float, float]
#: a station up to this far outside a slab face reads it on its plane (the
#: stations lie on the ring) -- ``airport/bridge_witness.driven_surface``'s read
EDGE_M = 0.5


def slab_faces(cache: _t.Any, decks: _t.Sequence[_t.Any], normal_min: float) -> np.ndarray:
    """Every deck placement's near-horizontal hard-deck face
    (``ObjGeometry.hard_deck``) as ``(n, 3, 3)`` frame x, y, authored y."""
    parts = []
    for d in decks:
        g = cache.geometry(d.resolved) if getattr(d, "resolved", None) else None
        tri = g.hard_deck if g is not None else ()
        if len(tri):
            parts.append(placed_faces(g.vertices, tri, d.xy, d.heading_deg))
    if not parts:
        return np.zeros((0, 3, 3))
    return up_faces(np.concatenate(parts), normal_min)


def station_tops(faces: np.ndarray, seats: _t.Sequence[XY], edge_m: float) -> list[float]:
    """The highest slab face's y over each station, ``nan`` over none."""
    if not len(seats):
        return []
    zs = every_z_at(faces, [p[0] for p in seats], [p[1] for p in seats], edge_m=edge_m)
    return [float(np.max(z)) if len(z) else float("nan") for z in zs]


def driven_top(faces: np.ndarray, seats: _t.Sequence[XY], edge_m: float,
               fallback: float) -> float:
    """The end line's top (module doc): the median of :func:`station_tops`
    over the stations that read one; ``fallback`` where none does."""
    got = [t for t in station_tops(faces, seats, edge_m) if t == t]
    return float(np.median(got)) if got else float(fallback)
