"""A BORE END THAT IS NO PORTAL (issue #1028, owner Q32: "either there isn't
really a tunnel there, or it's steeper, or the shape is wrong").

A mapped tunnel way's end is a mouth only where the road comes up out of the
ground.  It is NOT one where the road goes on UNDERGROUND: another tunnel way
leaves the end's node (its end, or an interior node: a switch, #1738) within
the approach turn cap, either straight away
(a second OSM feed's copy of the same tunnel, which splits
``structure_approach.chains`` because four ways meet at the node) or after
an open stretch of road shorter than the shortest lawful ramp
(``mouth_depth_m / ramp_max_grade``), which cannot come up to grade and go
back down again.  Measured at EDDF: rail ``-27364`` continuing as
``-10179`` at 1°, service ``-25266`` as its other feed's ``-33590`` at 0°,
and KCLT ``-6954`` running into ``-8739`` 19 m on.  Each built a full ramp
along the tunnel ahead.

Nor is it one where the road goes on ELEVATED (#2116): a mapped bridge way
leaves the bore's end node — the "tunnel" is a passage through a building
at deck level, and the road never was in the ground.  Measured at KDEN: the
arrivals and commercial lanes run from layer-1 bridges through layer -1 /
-2 ways under the terminal and out onto layer-1 bridges again; the bore
-16126+-21557+-3702 opened a 0.67 m mouth at its junction with bridge
-3706 and cut a tunnel ramp under that road's deck posts.

:func:`tunnel_ends` indexes the tunnel ways' ends once per pass;
:func:`continues_underground` names why an end is no portal (or ``None``);
:func:`bridge_ends` / :func:`continues_on_deck` the elevated case.

ONE BORE UNDER A MULTI-BRIDGE DECK (owner RULINGS 2026-11-19a): two tunnel
ways joined by an open way shorter than the shortest lawful ramp, both of
whose ends stand at a hard-deck bridge whose frame holds a trench object
(``planar/deck_bridge``; the caller passes those decks only -- KBNA's open
stretch between its taxiway-L decks stays open sky, #1718), are one road
in one cut under the deck's bridges -- it cannot come up to grade
between them.  :func:`deck_gap_ways` hands that open way to the bore set as
a tunnel, so ``structure_approach.chains`` reads the three as one bore with
its mouths at the far ends.  MEASURED KRDU CTR_TML: unclassified -254
(under one taxiway bridge) and -255 (under the next) joined by -233, 10 m,
each refused "goes on underground as the other way 10 m out".
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import LineString

from ..law import Law
from ..model.airport import OsmWay
from ..model.frame import XY
from .structure_approach import _key, is_bridge, is_tunnel, unit

__all__ = ["tunnel_ends", "continues_underground", "walked_m", "bridge_ends",
           "continues_on_deck", "deck_gap_ways"]


def tunnel_ends(osm: _t.Sequence[OsmWay], admitted: _t.Sequence[str]
                ) -> dict[tuple[int, int], list[tuple[OsmWay, XY, XY]]]:
    """Every tunnel way's continuations by node key: ``(way, node, next
    point)`` -- its two ends, and each INTERIOR node in both directions
    (RULINGS 2026-11-03b (6), #1738: a branch piece drawn ending on the
    through piece's interior node, a switch, goes on underground there;
    MEASURED ENGM: six such switch ends built 7.5 m rail ramps over the
    tunnel)."""
    out: dict[tuple[int, int], list[tuple[OsmWay, XY, XY]]] = {}
    for w in osm:
        pts = w.points
        if len(pts) < 2 or not is_tunnel(w, admitted):
            continue
        out.setdefault(_key(pts[0]), []).append((w, pts[0], pts[1]))
        out.setdefault(_key(pts[-1]), []).append((w, pts[-1], pts[-2]))
        for i in range(1, len(pts) - 1):
            k = _key(pts[i])
            out.setdefault(k, []).append((w, pts[i], pts[i + 1]))
            out[k].append((w, pts[i], pts[i - 1]))
    return out


def _walked(path: _t.Sequence[XY], inward: XY, reach_m: float
            ) -> tuple[float, XY, XY] | None:
    """``(metres walked on mapped ways, the node the walk ended at, its
    heading)`` when ``structure_approach.approach`` ended its walk early
    (it then appends ONE straight extension to ``reach_m + 1``), else
    ``None``: the road runs on for the whole reach."""
    if len(path) < 2 or abs(LineString(path).length - (reach_m + 1.0)) > 1e-6:
        return None
    walked = LineString(path[:-1]).length if len(path) >= 3 else 0.0
    last = path[-2]
    heading = unit(path[-3], path[-2]) if len(path) >= 3 else (-inward[0], -inward[1])
    return walked, last, heading


def walked_m(path: _t.Sequence[XY], inward: XY, reach_m: float) -> float:
    """How far ``structure_approach.approach`` walked mapped ways before its
    straight extension (``inf``: the road runs on for the whole reach)."""
    got = _walked(path, inward, reach_m)
    return math.inf if got is None else got[0]


def continues_underground(bore, inward: XY, path: _t.Sequence[XY], ends, law: Law,
                          reach_m: float) -> str | None:
    """Why the bore end whose approach is ``path`` is NO PORTAL (module
    doc), or ``None``.  ``ends`` is :func:`tunnel_ends`."""
    tn = law.tables.structures.tunnel
    got = _walked(path, inward, reach_m)
    if got is None:
        return None
    walked, last, heading = got
    cap = tn.rail_ramp_max_grade if any("railway" in (w.tags or {}) for w in bore.ways) \
        else tn.ramp_max_grade
    if walked >= tn.mouth_depth_m / cap:
        return None
    own = {id(w) for w in bore.ways}
    cos_max = math.cos(math.radians(tn.approach_turn_max_deg))
    for w, a, b in ends.get(_key(last), ()):
        if id(w) in own:
            continue
        d = unit(a, b)
        if d[0] * heading[0] + d[1] * heading[1] >= cos_max:
            ids = "+".join(str(x.id) for x in bore.ways)
            return (f"bore {ids}: its end is no portal — the road goes on underground as "
                    f"tunnel way {w.id} {walked:.0f} m out (under the shortest lawful ramp "
                    f"{tn.mouth_depth_m / tn.ramp_max_grade:.0f} m; #1028)")
    return None


def bridge_ends(osm: _t.Sequence[OsmWay], admitted: _t.Sequence[str]
                ) -> dict[tuple[int, int], list[OsmWay]]:
    """The mapped bridge ways (``structure_approach.is_bridge``, no tunnel)
    of a highway or railway, by the node key of each of their two ends."""
    out: dict[tuple[int, int], list[OsmWay]] = {}
    for w in osm:
        t = w.tags or {}
        if len(w.points) < 2 or ("highway" not in t and "railway" not in t) \
                or is_tunnel(w, admitted) or not is_bridge(w):
            continue
        for p in (w.points[0], w.points[-1]):
            out.setdefault(_key(p), []).append(w)
    return out


def continues_on_deck(bore, end: XY, ends) -> str | None:
    """Why the bore end at ``end`` is NO PORTAL because the road goes on
    ELEVATED (module doc): a mapped bridge way (:func:`bridge_ends`) leaves
    that node.  ``None`` otherwise."""
    own = {id(w) for w in bore.ways}
    for w in ends.get(_key(end), ()):
        if id(w) in own:
            continue
        ids = "+".join(str(x.id) for x in bore.ways)
        return (f"bore {ids}: its end is no portal — the road goes on elevated as bridge "
                f"way {w.id} (layer {(w.tags or {}).get('layer', '0')}): a passage at deck "
                "level, no cut (#2116)")
    return None


def deck_gap_ways(osm: _t.Sequence[OsmWay], tunnel_ways: _t.Sequence[OsmWay],
                  deck_polys: _t.Sequence, law: Law) -> tuple[list[OsmWay], list[str]]:
    """``(the open ways joining two tunnel ways under hard decks, as tunnel
    copies; one note each)`` (module doc).  ``deck_polys``: the hard-deck
    bridges' rings (shapely polygons)."""
    if not deck_polys or not tunnel_ways:
        return [], []
    from shapely.geometry import Point
    tn = law.tables.structures.tunnel
    tol = float(tn.object.bore_end_tolerance_m)
    shortest = float(tn.mouth_depth_m) / float(tn.ramp_max_grade)
    ends = tunnel_ends(tunnel_ways, tn.admitted_values)
    bored = {w.id for w in tunnel_ways}
    out: list[OsmWay] = []
    notes: list[str] = []
    for w in osm:
        t = w.tags or {}
        if (w.id in bored or len(w.points) < 2 or "highway" not in t or is_bridge(w)
                or LineString(w.points).length >= shortest):
            continue
        a, b = w.points[0], w.points[-1]
        ta, tb = ends.get(_key(a), ()), ends.get(_key(b), ())
        if not ta or not tb or {id(x[0]) for x in ta} & {id(x[0]) for x in tb}:
            continue
        if not all(any(p.distance(Point(e)) <= tol for p in deck_polys) for e in (a, b)):
            continue
        out.append(_dc.replace(w, tags={**t, "tunnel": "yes", "o4_deck_gap": "yes"}))
        notes.append(f"open way {w.id} ({LineString(w.points).length:.0f} m) joins tunnel ways "
                     f"{ta[0][0].id} and {tb[0][0].id} under hard decks: one bore (RULINGS "
                     f"2026-11-19a)")
    return out, notes
