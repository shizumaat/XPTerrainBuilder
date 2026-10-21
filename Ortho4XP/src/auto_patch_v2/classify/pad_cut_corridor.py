"""A PAD NEVER FILLS A MAPPED CUTTING (issue #1179).

A building pad is laid flat at one level over its whole outline.  A road
or railway the map tags ``cutting=*`` runs BELOW the ground beside it, so
a pad whose outline spans that way fills the cut up to pad level — at
LFLL the station cluster pad (315,116 m2) laid 239.75 m over the TGV
trench the DEM reads at 228–236 m, the cut "filled in just at the
airport while it is correctly lower on either side".

The rule, at the pad's ONE derivation site (``classify/evidence._pads``,
before the refs are minted, so every pad consumer inherits it): every pad
part loses the plan corridor of each mapped cutting way — the way's own
carriageway (``airport/road_ways.mapped_width_m`` at the ``[tunnel]``
lane law, the reading the bores use).  A bridge is the crossing, never
the cut; an admitted ``tunnel`` bore runs under the ground the pad stands
on and stays covered.  The corridor left open is no pad: the ground
there is read as any unpadded ground.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString
from shapely.ops import unary_union

from ..airport.deck_signature import is_bridge_way, is_tunnel_way
from ..airport.road_ways import mapped_width_m

__all__ = ["cutting_corridors", "trim_cut_corridors", "CUT_TRIMMED"]

#: the last run's count of pad parts the corridor cut (diagnostics)
CUT_TRIMMED: dict[str, float] = {}


def _is_cutting(tags: _t.Mapping[str, str], admitted) -> bool:
    c = str(tags.get("cutting", "")).strip().lower()
    if not c or c == "no":
        return False
    if not ("highway" in tags or "railway" in tags):
        return False
    return not is_bridge_way(tags) and not is_tunnel_way(tags, admitted)


def cutting_corridors(airport, law):
    """The union of every mapped cutting way's carriageway, or ``None``."""
    tn = law.tables.structures.tunnel
    admitted = tuple(tn.admitted_values)
    strips = []
    for w in getattr(airport, "osm_ways", ()) or ():
        tags = getattr(w, "tags", None) or {}
        if len(w.points) < 2 or not _is_cutting(tags, admitted):
            continue
        half = 0.5 * mapped_width_m(tags, tn.lane_width_m, tn.default_lanes)
        strips.append(LineString(w.points).buffer(half, cap_style="flat"))
    return unary_union(strips) if strips else None


def trim_cut_corridors(parts: list, airport, law) -> list:
    """Every pad part minus the mapped cutting corridors (geometry only;
    the caller splits the parts and mints the refs)."""
    CUT_TRIMMED.clear()
    corr = cutting_corridors(airport, law) if law is not None else None
    if corr is None or corr.is_empty:
        return parts
    out, n, area = [], 0, 0.0
    for p in parts:
        if p.intersects(corr):
            q = p.difference(corr)
            if not q.is_valid:
                q = q.buffer(0.0)
            n += 1
            area += p.area - q.area
            if q.is_empty:
                continue
            p = q
        out.append(p)
    CUT_TRIMMED.update(parts=n, area_m2=round(area, 1))
    return out
