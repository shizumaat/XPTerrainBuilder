"""A WALL IN A RUNWAY BAND ENDS THE BAND (owner sim read #2111, KBNA
2026-11-16T16:56:54Z: "a blast shield ... like a retaining wall or fence,
marks where terrain transition should occur, so the runway safety area
should grade to include the blast shield without a dip between it and the
runway end.  The terrain drops steeply to the road"; law: RULINGS
2026-11-16d — a wall marking the line between two levels is a retaining
wall — and 16i (3), with a fence or wall a step is allowed there).

A pack LINE object the solidity reader calls a solid or retaining wall
(``airport/line_solidity.kind_of``: SOLID_WALL / RETAINING_WALL; a blast
fence reads SOLID_WALL from its geometry and texture, never its name),
standing in a runway's graded band off its pavement, is the band's END
there: the band keeps the ground between its pavement and the wall, and
the ground BEHIND the wall (the side away from the pavement, swept
:data:`REACH_M` back) leaves the band — beyond zone 2 the DEM is
untouched, so the drop to the road below stands at the wall.

ONE derivation site: ``planar/zones.zone_regions`` cuts every runway band
with :func:`wall_cuts` beside its other single-site trims (27t plates, the
#1633 wall set-backs), so every reader downstream sees one trimmed band.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, Point
from shapely.ops import unary_union

__all__ = ["band_wall_lines", "wall_cuts", "REACH_M", "INSIDE_SHARE"]

#: how far behind a wall its cut reaches (m): past any runway band's zone 2
REACH_M = 500.0
#: a wall ends a band only when at least this share of its length lies in it
INSIDE_SHARE = 0.5
#: a wall closer than this to the band's own pavement is a kerb, not an end
_OFF_PAVEMENT_M = 1.0


def band_wall_lines(airport, rules) -> tuple[LineString, ...]:
    """Every solid / retaining LINE object of ``airport`` (frame xy) that is
    no unit's own fence (``EdgeLine.unit``, #2068's yards read those)."""
    from ..airport.line_solidity import RETAINING_WALL, SOLID_WALL, kind_of
    out = []
    for el in tuple(getattr(airport, "edge_lines", ()) or ()):
        if getattr(el, "unit", None) is not None or len(el.points) < 2:
            continue
        if kind_of(el, rules.service) not in (SOLID_WALL, RETAINING_WALL):
            continue
        ln = LineString(list(el.points) + ([el.points[0]] if el.closed else []))
        if ln.length > 0.0:
            out.append(ln)
    return tuple(out)


def _offset_mid(ln: LineString, side: float) -> Point:
    """The point 1 m off the middle of ``ln`` on its left (``side`` +1) or
    right (-1)."""
    s = ln.length / 2.0
    a, b = ln.interpolate(max(0.0, s - 0.5)), ln.interpolate(min(ln.length, s + 0.5))
    dx, dy = b.x - a.x, b.y - a.y
    n = (dx * dx + dy * dy) ** 0.5 or 1.0
    m = ln.interpolate(s)
    return Point(m.x - side * dy / n, m.y + side * dx / n)


def wall_cuts(walls: _t.Sequence[LineString], pavement, band) -> list:
    """Per wall of ``walls`` standing in ``band`` (at least
    :data:`INSIDE_SHARE` of its length) and off ``pavement``: the ground
    behind it, swept :data:`REACH_M` away from the pavement (module doc)."""
    if band is None or band.is_empty or pavement is None or pavement.is_empty:
        return []
    out = []
    for ln in walls:
        if ln.distance(pavement) <= _OFF_PAVEMENT_M or not ln.intersects(band):
            continue
        if ln.intersection(band).length < INSIDE_SHARE * ln.length:
            continue
        left = pavement.distance(_offset_mid(ln, 1.0))
        right = pavement.distance(_offset_mid(ln, -1.0))
        # the side FARTHER from the pavement is behind the wall
        far = REACH_M if left > right else -REACH_M
        cut = ln.buffer(far, single_sided=True, cap_style="flat")
        if not cut.is_empty:
            out.append(cut)
    return [unary_union(out)] if out else []
