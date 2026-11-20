"""THE SPAN UNDER A PACK BRIDGE IS THE ROAD'S OPEN CUT (owner RULINGS
2026-11-20o, ELLX #2194; extends 2026-10-26k / Q155).

Owner 2026-11-20T19:16Z, "Yes": over a pack bridge's deck footprint the
runway graded strip yields to the mapped road cut beneath; the deck is the
surface there and the road follows the lidar.

A mapped bore both of whose mouths one pack ENTRANCE object pins
(``Tunnel.portal`` with ``portal_floor``: ``trench_objects.mouth_portals``)
is a road passing under that object -- a bridge the pack drew over its own
cut, never a bored tunnel under covered ground.  The stretch between the two
mouths' caps, the corridor's own width either side of it, is
:func:`pinned_spans`' keep-out: the zone bands stop at it as they stop at
a corridor (``planar.zones``), so the ground under the deck is the survey's.
MEASURED ELLX: the runway 06/24 zone-2 strip held the motorway under the
pack bridge 3.0-3.6 m (median) over the lidar road.

Nothing here names an airport, a pack or a resource.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, Polygon

__all__ = ["pinned_spans"]


def pinned_spans(tunnels: _t.Iterable[_t.Any]) -> list[Polygon]:
    """The covered stretch of every bore one pack object pins at both
    mouths (module doc), as polygons in the airport frame."""
    by: dict[tuple, list] = {}
    for t in tunnels:
        if (getattr(t, "portal", "") and getattr(t, "portal_floor", False)
                and getattr(t, "cap_centre", None)):
            by.setdefault((str(t.portal), tuple(sorted(t.ways))), []).append(t)
    out: list[Polygon] = []
    for _key, ts in sorted(by.items()):
        if len(ts) != 2:
            continue
        a, b = ts
        line = LineString([tuple(a.cap_centre), tuple(b.cap_centre)])
        if line.length <= 0.0:
            continue
        half = max(float(a.half_width_m), float(b.half_width_m))
        g = line.buffer(half, cap_style="flat")
        if not g.is_empty:
            out.append(g)
    return out
