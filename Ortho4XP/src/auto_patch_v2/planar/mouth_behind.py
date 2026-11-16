"""A TAXIWAY BEHIND A PINNED ENTRANCE MOUTH BOUNDS ITS CAP (#2099 F2 P1b /
P1c, RULINGS 2026-11-06c (3)).

Clause 1 (``structure_mouth._pinned``) slides a pinned mouth when a
taxiway face stands in its ring: the taxiway at the opening is never cut.
A taxiway the ring meets ONLY BEHIND the mouth line (over the bore, past
the entrance face) is not at the opening: sliding the mouth out of it
leaves an earth wedge between the face and the road (measured CYYZ: a
2.0 m slide, the road 4.9 m over its floor 1 m off the bore end).  Such a
face stays a stop, and the mouth's CAP — the ring's stand-off behind the
mouth line — is held short of it (:func:`cap_bound`); the ring's void and
the knife's footprint never take it (:func:`clear_of`).  A cap that cannot
stand ``wall_gap_m`` behind the mouth line leaves clause 1's yield
standing."""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from ..law import Law

__all__ = ["Behind", "behind_faces", "cap_bound", "clear_of"]

_REACH_M = 1000.0      # the half-planes' extent: far past any ring


class Behind(_t.NamedTuple):
    """The taxiway faces a pinned entrance ring meets only behind its mouth
    line: ``d`` their least distance from it (inside the ring's lateral
    span), ``faces`` / ``refs`` themselves."""
    d: float
    faces: tuple
    refs: tuple


def _frame(mouth, inward, ring: Polygon):
    """(behind half-plane strip, mouth line) for the ring's lateral span."""
    ix, iy = inward
    nx, ny = -iy, ix
    w = max(abs((x - mouth[0]) * nx + (y - mouth[1]) * ny) for x, y in ring.exterior.coords)
    a = (mouth[0] - nx * w, mouth[1] - ny * w)
    b = (mouth[0] + nx * w, mouth[1] + ny * w)
    strip = Polygon([a, b, (b[0] + ix * _REACH_M, b[1] + iy * _REACH_M),
                     (a[0] + ix * _REACH_M, a[1] + iy * _REACH_M)])
    return strip, LineString([a, b])


def behind_faces(mouth, inward, ring, hits) -> "Behind | None":
    """``hits`` — (polygon, ref) taxiway faces the pinned ring stands in.
    A :class:`Behind` when EVERY one meets the ring only behind the mouth
    line (the side ``inward`` points to); ``None`` when one stands at the
    opening (clause 1's yield) or nothing is read."""
    if not hits or ring is None or ring.is_empty:
        return None
    hull = ring if ring.geom_type == "Polygon" else ring.convex_hull
    strip, line = _frame(mouth, inward, hull)
    front = ring.difference(strip)
    if any(p.intersects(front) for p, _r in hits):
        return None
    ds = []
    for p, _r in hits:
        near = p.intersection(strip)
        ds.append(line.distance(near if not near.is_empty else p))
    return Behind(min(ds), tuple(p for p, _r in hits), tuple(r for _p, r in hits))


def cap_bound(behind: Behind, law: Law, gap: float) -> "float | None":
    """The cap's stand-off behind the mouth line that keeps the ring off the
    taxiway: ``d`` less the input grid and the identity spacing; ``None``
    (the yield stands) when that is under ``gap`` (``wall_gap_m``)."""
    ident = law.tables.emit.identity
    cap = behind.d - ident.input_quantum_m - ident.min_distinct_spacing_m
    return cap if cap >= gap else None


def clear_of(geom, faces):
    """``geom`` less the taxiway ``faces`` (P1c: the ring's void and the
    knife's footprint never take the taxiway behind the mouth)."""
    if geom is None or not faces:
        return geom
    return geom.difference(unary_union(list(faces)))
