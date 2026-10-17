"""THE RIDGE REACHES THE RUNWAY'S OWN PAVEMENT EDGE (issue #878).

The ``runway_profile`` ridge (``overlay._runway_ridges``) runs end to end
across the apt.dat overruns.  A pack that draws its runway a few
centimetres to a few decimetres LONGER than the apt.dat rectangle leaves a
rim cell of the SAME runway (same role, same ref) beyond the ridge's end.
When that rim is narrower than the weld tolerance the weld cannot fold it
onto the rectangle (``weld._weld_one`` refuses a junior the projection
would collapse), so it survives as a face of its own whose far end edge
runs corner to corner with no vertex on the axis.  The crown stands at the
ridge's end node and the rim's far edge at the shoulder level, so the
solve leaves a cliff across the rim's width.  MEASURED (issue #878,
KLGB 08L end, 33.82275,-118.16354): a 0.37 m rim on the 0.5 m lattice,
crown 17.67 against the edge chord 17.47 — ``runway_step`` 0.20 m over
0.50 m, a verify DEFECT that refused the airport.

THE RULE.  Two pavement boundaries within ``identity.weld_spacing_m`` of
each other ARE one boundary (RULINGS 2026-09-04u).  So a ridge end whose
runway pavement continues, along the axis, by no more than that tolerance
past it is carried to where that pavement ends: the point the noding then
makes a vertex of the rim's far edge, at the crown.  The original end
stays a station of the ridge (the threshold pin is the station nearest the
threshold), and pavement reaching FURTHER than the tolerance is left as it
was — that is a surface of its own, never a sliver this rule may reach
into.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from .zones import RUNWAY_FAMILY

__all__ = ["reach_pavement_edge"]


def reach_pavement_edge(ridges: _t.Sequence[tuple[str, LineString]],
                        cells: _t.Sequence, tol: float, gap: float = 0.0
                        ) -> tuple[list[tuple[str, LineString]], int]:
    """``ridges`` with each end carried along its own axis to the edge of
    the runway's own pavement (the union of the runway-family ``cells``
    whose ref is the ridge's) when that edge lies within ``tol`` beyond it;
    ``(ridges, ends extended)``.  ``gap`` is the seam two of those cells
    may leave between them and still read as one pavement (the lattice's
    half cell: the snap closes it) — KLGB's rim starts 1.4 mm past the
    rectangle it borders."""
    if tol <= 0.0 or not ridges:
        return list(ridges), 0
    body: dict[str, list[Polygon]] = {}
    for c in cells:
        if c.role in RUNWAY_FAMILY and len(c.ring) >= 3:
            body.setdefault(c.ref, []).append(
                Polygon(c.ring, [h for h in c.holes if len(h) >= 3]))
    out: list[tuple[str, LineString]] = []
    extended = 0
    for ref, line in ridges:
        polys = body.get(ref)
        coords = list(line.coords)
        if not polys or len(coords) < 2:
            out.append((ref, line))
            continue
        pave = unary_union([p if p.is_valid else p.buffer(0) for p in polys])
        head = _reach(coords[0], coords[1], pave, tol, gap)
        tail = _reach(coords[-1], coords[-2], pave, tol, gap)
        if head is not None:
            coords.insert(0, head)
            extended += 1
        if tail is not None:
            coords.append(tail)
            extended += 1
        out.append((ref, LineString(coords) if (head or tail) else line))
    return out, extended


def _reach(end: tuple, inner: tuple, pave, tol: float, gap: float
           ) -> tuple | None:
    """The point where the pavement ``pave`` ends along the axis from
    ``inner`` through ``end`` — its pieces on the probe chained across
    seams up to ``gap`` — when it lies strictly beyond ``end`` and within
    ``tol`` of it; else ``None``."""
    (ex, ey), (ix, iy) = end[:2], inner[:2]
    L = ((ex - ix) ** 2 + (ey - iy) ** 2) ** 0.5
    if L <= 0.0 or pave.distance(Point(ex, ey)) > gap:
        return None
    ux, uy = (ex - ix) / L, (ey - iy) / L
    probe = LineString([(ex, ey), (ex + ux * tol, ey + uy * tol)])
    inside = probe.intersection(pave)
    spans = []
    for g in getattr(inside, "geoms", [inside]):
        if g.is_empty or g.geom_type != "LineString":
            continue
        d = sorted(((c[0] - ex) * ux + (c[1] - ey) * uy) for c in g.coords)
        spans.append((d[0], d[-1]))
    run = 0.0
    for a, b in sorted(spans):
        if a > run + gap + 1e-9:
            break                             # a seam wider than the snap closes
        run = max(run, b)
    if run <= 1e-6 or run >= tol - 1e-9:
        return None                           # no rim, or pavement reaching on
    return (ex + ux * run, ey + uy * run)
