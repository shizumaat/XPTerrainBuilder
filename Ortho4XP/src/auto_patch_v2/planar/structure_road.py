"""§34 (13) (4) / §34 (11) (a) THE ROAD BETWEEN TWO MOUTHS (Fable
2026-09-15; RULINGS 2026-09-15h/15u/15y; owner 15e item 5).

Its own module, beside ``structure_approach`` and ``structure_underpass``,
because ``planar/structures.py`` stands at its 1,000-line budget — and
because this is the ONE road-family face the structures stage mints, so
it wants a name of its own.

THE LAW IT ANSWERS, AND THE ONE IT REFUSES.  Owner 15e item 5: "the
ground is getting pulled down between there and 40.4940268, −3.5826498.
We may need to provide a smooth sloping road grade for the road here:
40.494628,−3.5832911 to 40.4943869,−3.5823239".  r1 identified that road
— OSM way −5944, ``highway=service lanes=2``, 297.9 m, 0.14 m from the
owner's own first point — and named the two gates that keep it out of the
layout (``classify.evidence._osm_roads`` intersects road centrelines with
``pavement_union``; ``classify.roles`` mints faces from ``truck_chains``
alone).  r2's 24-reader consumer census (owner RULINGS 2026-08-30l)
REFUSED the obvious repair: admitting mapped roads generally reads 207
faces / 944,872 m² at LEMD — 7.8 % of the coverage — to fix one road, and
returns HAZARD on five readers, the worst being that a face minted over a
``tunnel=yes`` way has no structure record, so ``airport/road_ramp.
deck_refs`` cannot exclude it and §37 (6) grades it to the surface OVER
THE BORE.

So 15y re-founds §34 (11) (a) on its own words — THE ROAD BETWEEN TWO
MOUTHS — and puts it HERE, at the planar stage, where the mouths are
known.  Every HAZARD the census named dies of the scope: the population
is a handful of ways that END at portals, a structure way is refused
outright, and the faces are nowhere near a runway strip.

THE PREDICATE, AND WHY IT IS NOT THE ONE THE BRIEF GUESSED.  The first
reading tried was "two mouths of one bore facing each other".  MEASURED at
the owner's site, they do not: ``tunnel:-15327@0`` and ``tunnel:-5980@0``
are 88.5 m apart and their ramps climb AWAY from one another (dot of each
outward direction with the line between them: −0.916 and −0.906) — they
are the two near portals of a DUAL CARRIAGEWAY whose far ends merge at
``tunnel:-15327+-5980@0``, and the ground between them is the plateau the
bores pass under, not a road.  What IS the road between two mouths is the
way whose OWN TWO ENDS are mouths: −5944 runs from ``tunnel:-5931@1``'s
mouth (sharing its node exactly, 0.00 m) to 47.3 m short of
``tunnel:-5980@0``.  So the predicate is:

* a mapped ``highway=*`` way, itself NEITHER ``tunnel`` NOR ``bridge``
  (a structure states that ground, and this is the census's HAZARD);
* each of its two ends within ``[tunnel] mouth_pair_m`` of a structure
  mouth, and the two mouths DIFFERENT (a way that leaves and re-enters
  one portal is not a road between two mouths);
* at least one of those ends joined to the bore by a shared NODE
  (``NODE_TOL``, the canonical identity join — memory
  ``canonical-identity-join``: 11-dp lat/lon carries node ids, never a
  proximity join).  The other end may be near rather than on, because a
  merged dual carriageway reports its mouth at the PAIR'S CENTRE (the
  same 12 m offset §34 (5) (a) measured at F-6), and demanding two node
  joins reads **0** ways at LEMD where demanding one reads **4**.

MEASURED POPULATION at LEMD: **4 ways, 616.5 m** — −5944 (the owner's),
−12917, −4044 and −3830 — against 27 at the same ``mouth_pair_m`` without
the node join, and 207 faces for the general admission r2 refused.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from ..classify.roles import Cell
from ..law import Law
from ..law.tables import role_side
from ..model.airport import Airport
from .structure_approach import carriageway_width_m, is_bridge, is_tunnel_way

__all__ = ["MOUTH_ROAD_REF", "mouth_pair_roads"]

#: The ref a mouth-pair road face carries — its OWN namespace, never the
#: 1206 corridors' ``route{i}`` (consumer census row 17: sharing it would
#: leave the census unable to tell the two populations apart).
MOUTH_ROAD_REF = "mouth_road"

#: Two OSM coordinates closer than this are ONE node (``structures.
#: NODE_TOL``, the canonical identity join).
NODE_TOL = 0.05

_MITRE = dict(join_style="mitre", mitre_limit=2.0)


def mouth_pair_roads(airport: Airport, classification, law: Law,
                     tunnels: _t.Sequence) -> tuple:
    """``(classification with the mouth-pair road cells, notes)``.

    The face is the way's own centreline buffered by its carriageway
    width (``structure_approach.carriageway_width_m``, the same reading
    every other road width in the structures stage uses), minus every
    existing cell so it never overlaps pavement, a pad or a corridor —
    the 1206 corridor mint's own construction."""
    tn = law.tables.structures.tunnel
    pair_m = float(getattr(tn, "mouth_pair_m", 0.0) or 0.0)
    notes: list[str] = []
    if pair_m <= 0.0:
        return classification, notes
    mouths = [(t.id, t.axis[0], frozenset(t.ways))
              for t in tunnels if getattr(t, "axis", None)]
    if not mouths:
        return classification, notes
    bore_ends: dict[int, tuple] = {}
    for w in airport.osm_ways:
        tags = getattr(w, "tags", None) or {}
        if tags.get("highway") is None or len(w.points) < 2:
            continue
        if is_tunnel_way(tags, tn.admitted_values):
            bore_ends[w.id] = (w.points[0], w.points[-1])
    cells = list(classification.cells)
    taken = unary_union([Polygon(c.ring, c.holes) for c in cells]) if cells else None
    out: list[Cell] = []
    refused_structure = 0
    for w in airport.osm_ways:
        tags = getattr(w, "tags", None) or {}
        if tags.get("highway") is None or len(w.points) < 2:
            continue
        if is_tunnel_way(tags, tn.admitted_values) or is_bridge(w):
            refused_structure += 1
            continue
        ends = (w.points[0], w.points[-1])
        got = [_mouth_at(e, mouths, bore_ends, pair_m) for e in ends]
        if got[0] is None or got[1] is None or got[0][0] == got[1][0]:
            continue
        if not (got[0][2] or got[1][2]):
            continue                    # neither end is a true node join
        half = carriageway_width_m(tags, law) / 2.0
        face = LineString(w.points).buffer(half, cap_style="flat", **_MITRE)
        if taken is not None and not taken.is_empty:
            face = face.difference(taken)
        for k, part in enumerate(_parts(face)):
            if part.area < law.tables.emit.identity.min_distinct_spacing_m:
                continue
            ref = f"{MOUTH_ROAD_REF}:{w.id}" + (f"#{k}" if k else "")
            out.append(Cell(0, "service_road", ref,
                            tuple(part.exterior.coords)[:-1],
                            tuple(tuple(h.coords)[:-1] for h in part.interiors),
                            None, None, role_side(law, "service_road"),
                            "service_road",
                            {"mouth_road": 1.0, "area_m2": part.area,
                             "way": float(w.id)}))
        notes.append(
            f"mouth road {w.id} ({tags.get('highway')}, width "
            f"{2 * half:.1f} m, {LineString(w.points).length:.0f} m): "
            f"{got[0][0]} @ {got[0][1]:.1f} m"
            f"{' (node)' if got[0][2] else ''} -> {got[1][0]} @ "
            f"{got[1][1]:.1f} m{' (node)' if got[1][2] else ''}")
    if not out:
        return classification, notes
    merged = list(cells) + out
    merged = [_dc.replace(c, id=i) for i, c in enumerate(merged)]
    notes.append(f"mouth roads {len(notes)} way(s) -> {len(out)} face(s), "
                 f"{sum(Polygon(c.ring, c.holes).area for c in out):.0f} m2 "
                 f"(mouth_pair_m {pair_m:g}; {refused_structure} structure "
                 f"way(s) refused)")
    return _dc.replace(classification, cells=tuple(merged)), notes


def _mouth_at(p, mouths, bore_ends, pair_m):
    """``(tunnel id, distance, joined by a shared NODE)`` of the mouth this
    road END continues, or ``None``.  A NODE join outranks a nearer mouth:
    the way that literally continues the bore is the one the law means."""
    best = None
    for tid, m, ways in mouths:
        d = math.hypot(p[0] - m[0], p[1] - m[1])
        if d > pair_m:
            continue
        node = any(bid in ways and any(math.hypot(p[0] - q[0], p[1] - q[1]) <= NODE_TOL
                                       for q in ends)
                   for bid, ends in bore_ends.items())
        rank = (1 if node else 0, -d)
        if best is None or rank > (1 if best[2] else 0, -best[1]):
            best = (tid, d, node)
    return best


def _parts(geom) -> list[Polygon]:
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    return [g for g in getattr(geom, "geoms", ()) if g.geom_type == "Polygon"]
