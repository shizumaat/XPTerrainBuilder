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

A COVERED CUTTING (#1333): a cutting way mapped ``covered=yes`` or
``tunnel=building_passage`` runs UNDER the building the pad carries (LFLL's
TGV tracks under the station; the passage is no bore, §26, and belongs to
the building's pad).  Its corridor is NOT trimmed here: the planar stage
reads the building's own lower storey along it and mints the pad's LOWER
LEVEL over it (``planar/covered_cut``, RULINGS 2026-10-23b's two pads at
the objects' bottom, 27h), and trims what no level takes
(``covered_cut.trim_uncut``), so a pad still never fills a cut.
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


def _is_covered(tags: _t.Mapping[str, str]) -> bool:
    """A cutting UNDER A BUILDING: ``covered=yes`` or
    ``tunnel=building_passage`` (module docstring, #1333)."""
    return (str(tags.get("covered", "")).strip().lower() == "yes"
            or str(tags.get("tunnel", "")).strip().lower() == "building_passage")


def cutting_corridors(airport, law, covered: "bool | None" = None, widen: float = 0.0):
    """The union of every mapped cutting way's carriageway, or ``None``;
    ``covered`` True / False keeps only the covered / the open ones;
    ``widen`` adds that many carriageway widths either side."""
    tn = law.tables.structures.tunnel
    admitted = tuple(tn.admitted_values)
    strips = []
    for w in getattr(airport, "osm_ways", ()) or ():
        tags = getattr(w, "tags", None) or {}
        if len(w.points) < 2 or not _is_cutting(tags, admitted):
            continue
        if covered is not None and _is_covered(tags) != covered:
            continue
        half = (0.5 + float(widen)) * mapped_width_m(tags, tn.lane_width_m, tn.default_lanes)
        strips.append(LineString(w.points).buffer(half, cap_style="flat"))
    return unary_union(strips) if strips else None


def trim_cut_corridors(parts: list, airport, law) -> list:
    """Every pad part minus the mapped OPEN cutting corridors (geometry
    only; the caller splits the parts and mints the refs).  A covered
    cutting stays in the pad for the planar stage (module docstring)."""
    CUT_TRIMMED.clear()
    corr = cutting_corridors(airport, law, covered=False) if law is not None else None
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
