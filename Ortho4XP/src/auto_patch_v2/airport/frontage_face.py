"""THE LANDSIDE FACE OF A TERMINAL AND ITS CLUES (RULINGS 2026-11-25g,
25h (Q1, Q3); spec ``docs/specs/terminal-frontage-split-level-20261125.md``
§1.4).  Read by ``airport/unit_storey.unit_levels`` (one record per
terminal-sized unit); nothing else reads it yet (step 1: a record).

THE FACE.  The part of the unit's closed plan outline (exterior rings: a
courtyard is no landside face) with no airside
pavement within ``[design] pad_frontage_m`` and, where the map's groundside
is given, groundside pavement within ``[road_contact] contact_reach_m``;
pieces shorter than that reach are dropped.

THE CLUES (owner 25h Q1: the groundside "could be more than one level,
typically there's other clues like retaining walls, connections to other
buildings"; Q3: pavement, fences and walls are evidence of a steeper step).
Published for step 2, which reads how many levels the groundside drops and
where the steeper steps sit; step 1 reads only the face span (the far test):

- ``face_span``: the lowest base and highest top (authored y) of the unit's
  solid parts along the face -- the height of the groundside face;
- ``retaining_walls``: the airport's retaining walls within reach of it;
- ``fences``: pack line parts (fences, walls) within reach: unit, base, height;
- ``upper_roads``: OSM highways within reach mapped ``bridge`` or
  ``layer`` >= 1 (an upper kerb road, §1.4);
- ``neighbours``: other units within reach (garages, linked buildings),
  with their grounded base range and the DEM median under their plan there."""
from __future__ import annotations

import dataclasses as _dc
import statistics as _st
import typing as _t

from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import linemerge, unary_union

__all__ = ["UnitPlans", "face_clues", "landside_face"]


@_dc.dataclass(frozen=True)
class UnitPlans:
    """Every unit's solid footprints ``[(part, polygon)]``, line-part
    footprints and plan box (frame metres), read once per airport."""

    solid: tuple
    lines: tuple
    boxes: tuple

    def near(self, zone) -> list[int]:
        x0, y0, x1, y1 = zone.bounds
        return [i for i, b in enumerate(self.boxes) if b is not None
                and not (b[0] > x1 or b[2] < x0 or b[1] > y1 or b[3] < y0)]


def _lines(g) -> list:
    if g is None or g.is_empty:
        return []
    if isinstance(g, LineString):
        return [g]
    return [x for x in getattr(g, "geoms", ()) if isinstance(x, LineString)]


def landside_face(plan, air, ground, near_m: float, reach_m: float) -> MultiLineString:
    """THE FACE (module docstring), empty where no run qualifies.
    ``ground`` ``None`` skips the groundside test."""
    closed = plan.buffer(near_m).buffer(-near_m)
    closed = plan if closed.is_empty else closed
    out = unary_union([Polygon(q.exterior).exterior for q in getattr(closed, "geoms", [closed])
                       if isinstance(q, Polygon)])
    if air is not None and not air.is_empty:
        out = out.difference(air.buffer(near_m))
    if ground is not None:
        out = LineString() if ground.is_empty else out.intersection(ground.buffer(reach_m))
    pieces = _lines(out)
    merged = _lines(linemerge(pieces)) if pieces else []
    return MultiLineString([x for x in merged if x.length >= reach_m])


def _layer(tags) -> int:
    try:
        return int(str((tags or {}).get("layer", "0")).split(";")[0])
    except ValueError:
        return 0


def _upper_road(w, zone) -> bool:
    t = w.tags or {}
    return (bool(t.get("highway")) and (t.get("bridge", "no") not in ("", "no")
                                        or _layer(t) >= 1)
            and len(w.points) >= 2 and LineString(w.points).intersects(zone))


def face_clues(ui: int, plan, face, airport, plans: UnitPlans, reach_m: float,
               near_m: float, dem_samples: _t.Callable) -> dict:
    """THE CLUES of unit ``ui`` along ``face`` (module docstring)."""
    line = face if not face.is_empty else plan.boundary
    zone, along = line.buffer(reach_m), line.buffer(near_m)
    span = [(p.base_y, p.base_y + float(getattr(p, "height_m", 0.0) or 0.0))
            for p, g in plans.solid[ui] if g.intersects(along)]
    walls = sorted(str(getattr(w, "resource", "") or "")
                   for w in (getattr(airport, "retaining_walls", ()) or ())
                   if getattr(w, "poly", None) is not None and w.poly.intersects(zone))
    roads = sorted(int(w.id) for w in (getattr(airport, "osm_ways", ()) or ())
                   if _upper_road(w, zone))
    fences, neigh = [], []
    dem = getattr(airport, "dem", None)
    for uj in plans.near(zone):
        fences.extend([uj, round(float(p.base_y), 2),
                       round(float(getattr(p, "height_m", 0.0) or 0.0), 2)]
                      for p, g in plans.lines[uj] if g.intersects(zone))
        hit = [g for _p, g in plans.solid[uj] if g.intersects(zone)] if uj != ui else []
        if not hit:
            continue
        ys = [p.base_y for p, _g in plans.solid[uj] if getattr(p, "feet", ())]
        zs = dem_samples(dem, unary_union(hit))
        u = airport.partition.units[uj]
        neigh.append({"unit": uj, "id": str(getattr(u, "id", uj)),
                      "plan_m2": round(unary_union([g for _p, g in plans.solid[uj]]).area, 1),
                      "base_y": [round(min(ys), 2), round(max(ys), 2)] if ys else None,
                      "ground": round(_st.median(zs), 2) if zs else None})
    return {"face_span": ([round(min(a for a, _b in span), 2),
                           round(max(b for _a, b in span), 2)] if span else None),
            "retaining_walls": walls, "fences": fences, "upper_roads": roads,
            "neighbours": neigh}
