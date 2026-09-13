"""A BRIDGE STATES THE CROSSING (spec §34 (5); Fable 2026-09-13i;
RULINGS 2026-09-13i item 1, 2026-09-13q item 3) — lane ``v2rampwalk``.

Its own module because ``planar/structures.py`` and
``planar/structure_approach.py`` both stand at their 1,000-line budget.

NOT CALLED BY THE BUILD (lane ``v2rampwalk``, 2026-09-13).  The seeding
half below is implemented and MEASURED on one LEMD build (ledger
``f4cf494dab92``): taxiway F-6, way −1230, deck half-width 7.6 m read off
its own taxi cell, both service roads bored and 31h-merged into one ramp
with mouths at the two abutments.  Arming it ALONE regresses the cockpit
block — LEMD CRITICAL VISUAL 3 → 10, seven of the ten rows at
40.46100, −3.54455 — because the portal RIM takes ``DEM(mouth)`` = 570.0
(the road's ground, down in the cutting) against a taxi surface solving
~573.5 above it, so the abutment reads as a 3.52 m cliff and mints four
``strip_seam_tear`` rows that were zero.  §34 (5)'s other half — "the
aeroway is a terrain deck at the taxi surface, level across the cutting
under taxi law" — has NO DEM source (the DEM carries no bridge): the
abutment rim would have to take the TAXI CELL's own solved value, a new
relational law that is an owner/Fable ruling, not this lane's.  The
module and its twins (``tests/auto_patch_v2/test_v2rampwalk.py``) stand
so the next round starts from the measurement, not from scratch.
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString

from ..law import Law
from ..model.airport import Airport, OsmWay
from ..model.frame import XY
from shapely.geometry import Point
from shapely.strtree import STRtree

from .structure_approach import carriageway_width_m, is_bridge, is_tunnel_way, unit

_MITRE = dict(join_style="mitre", mitre_limit=2.0)

__all__ = ["underpass_bores", "approach_along", "is_aeroway_bridge", "UNDERPASS_TAG"]


def is_aeroway_bridge(tags: _t.Mapping[str, str]) -> bool:
    """An ``aeroway=*`` way tagged ``bridge`` (not ``no``).

    ``airport/deck_signature.is_bridge_way`` — the predicate every deck
    pass uses — requires ``highway`` or ``railway``, so an AEROWAY bridge
    is invisible to all of it: LEMD's taxiway F-6 (way −1230,
    ``aeroway=taxiway bridge=yes layer=1``) and KCLT's taxiway U (−1560)
    mint no deck and seed nothing, which is exactly the gap §34 (5)
    closes.  The predicate stays LOCAL: widening the shared one would mint
    a terrain deck at ROAD level from every aeroway bridge across every
    corridor, where the taxi surface over an underpass is the pavement
    cell's own (``pavement_deck_intervals``, 2026-09-06f) under taxi
    law — which is what "level across the cutting under taxi law" means.
    """
    b = tags.get("bridge")
    return bool(tags.get("aeroway")) and bool(b) and b != "no"

#: The tag a synthesised UNDERPASS bore carries, so the reports and the
#: approach walk can tell it from a mapped ``tunnel=yes`` way.
UNDERPASS_TAG = "o4_underpass"


def underpass_bores(airport: Airport, law: Law, cells, polys
                    ) -> tuple[list[OsmWay], dict[int, LineString], list[str]]:
    """A BRIDGE STATES THE CROSSING (spec §34 (5); Fable 2026-09-13i,
    RULINGS 2026-09-13i item 1 and 2026-09-13q item 3).

    An ``aeroway=*`` way tagged ``bridge=yes`` with ``layer >=
    [tunnel] underpass_min_layer`` is a taxiway ON A STRUCTURE: whatever
    passes under it is in a CUTTING, and OSM says so by the bridge alone —
    the roads beneath carry no ``tunnel`` tag anywhere in either measured
    case (LEMD F-6, way −1230 over service roads −5820/−5821, a 7.5 m DEM
    cutting the taxi surface bathtubs 2.66 m at 5.3 % across; KCLT taxiway
    U, way −1560 over untagged tertiary roads, headroom 2.3–2.5 m).  With
    no bore seeded the terrain simply drapes the cutting and the taxiway
    follows it down.

    So the crossing is stated: the road's own centreline CLIPPED to the
    aeroway's deck ribbon becomes a bore (``tunnel=yes``), and everything
    downstream is the tunnel model already built — the mouths where the
    road leaves the ribbon (§29's on-field gate applies to them like any
    other), the ramps out of them along the road (§34 (1)/(2)), the rims,
    and the aeroway itself as the DECK across the corridor (it is already
    a ``bridge`` way, so ``deck_intervals`` mints it; where a taxi-family
    cell spans the corridor ``pavement_deck_intervals`` keeps that cell's
    own taxi law, 2026-09-06f — "level across the cutting under taxi law").

    The ribbon's half-width is the PAVEMENT the aeroway traces
    (``pavement_half_widths``, 2026-09-06b (2)) — a taxiway bridge carries
    no ``width`` tag and its lanes fallback (7 m) is a third of a real
    taxiway — falling back to the carriageway width where no pavement
    traces it.  Returns the synthetic ways, each one's PARENT road line
    (the ramp's route), and the notes for the structures line."""
    tn = law.tables.structures.tunnel
    out: list[OsmWay] = []
    parents: dict[int, LineString] = {}
    notes: list[str] = []
    decks = []
    for w in airport.osm_ways:
        tags = getattr(w, "tags", None) or {}
        if not is_aeroway_bridge(tags) or len(w.points) < 2:
            continue
        try:
            layer = int(float(str(tags.get("layer", "0")).strip()))
        except ValueError:
            layer = 0
        if layer < tn.underpass_min_layer:
            continue
        decks.append(w)
    if not decks:
        return out, parents, notes
    roads = [w for w in airport.osm_ways
             if (getattr(w, "tags", None) or {}).get("highway") and len(w.points) >= 2
             and not is_tunnel_way(w.tags, tn.admitted_values) and not is_bridge(w)]
    for w in decks:
        ln = LineString(w.points)
        half = carriageway_width_m(w.tags, law) / 2.0
        step = max(law.tables.emit.identity.min_distinct_spacing_m, 1.0)
        ss = [min(s, ln.length) for s in _frange(0.0, ln.length, step)]
        axis_fn = (lambda s, _ln=ln: (_ln.interpolate(min(s, _ln.length)).x,
                                      _ln.interpolate(min(s, _ln.length)).y))
        half = max(half, _deck_half_width(axis_fn, ss, cells, polys, half))
        ribbon = ln.buffer(half, **_MITRE)
        n = 0
        for r in roads:
            piece = LineString(r.points).intersection(ribbon)
            for g in getattr(piece, "geoms", [piece]):
                if g.geom_type != "LineString" or g.length < tn.underpass_min_span_m:
                    continue
                pts = tuple((float(x), float(y)) for x, y in g.coords)
                sw = OsmWay(r.id, r.kind, pts, False,
                            {**dict(r.tags), "tunnel": tn.admitted_values[0],
                             UNDERPASS_TAG: str(w.id)})
                out.append(sw)
                parents[id(sw)] = LineString(r.points)
                n += 1
        notes.append(f"underpass {w.tags.get('aeroway')} {w.id} (layer {w.tags.get('layer')}, "
                     f"deck half-width {half:.1f} m): {n} road(s) bored")
    return out, parents, notes


def _frange(a: float, b: float, step: float) -> list[float]:
    out, s = [], a
    while s < b - 1e-9:
        out.append(s)
        s += step
    out.append(b)
    return out


def approach_along(parent: LineString, mouth: XY, inward: XY,
                   reach_m: float) -> list[XY]:
    """THE RAMP'S ROUTE OUT OF AN UNDERPASS MOUTH (spec §34 (1)/(5)): the
    PARENT road's own centreline, walked outward from the mouth (a mouth
    the bore's clip made stands mid-way along the road, at no mapped node,
    so ``approach``'s node index finds nothing there and falls back to a
    straight extension).  Extended straight past the road's end, exactly
    as ``approach`` does."""
    s0 = parent.project(__import__("shapely").geometry.Point(mouth))
    out_dir = (-inward[0], -inward[1])
    cs = list(parent.coords)
    fwd = None
    if len(cs) >= 2:
        a = parent.interpolate(min(parent.length, s0 + 1.0))
        d = unit(mouth, (a.x, a.y))
        fwd = (d[0] * out_dir[0] + d[1] * out_dir[1]) >= 0.0
    path: list[XY] = [tuple(mouth)]
    if fwd is None:
        return path
    rng = [s for s in _stations(parent, s0, fwd) ]
    for s in rng:
        p = parent.interpolate(s)
        q = (p.x, p.y)
        if math.hypot(q[0] - path[-1][0], q[1] - path[-1][1]) < 1e-6:
            continue
        path.append(q)
        if LineString(path).length >= reach_m:
            return path
    ln = LineString(path) if len(path) >= 2 else None
    if ln is None:
        path.append((mouth[0] + out_dir[0] * (reach_m + 1.0),
                     mouth[1] + out_dir[1] * (reach_m + 1.0)))
        return path
    if ln.length < reach_m:
        a = unit(path[-2], path[-1])
        path.append((path[-1][0] + a[0] * (reach_m - ln.length + 1.0),
                     path[-1][1] + a[1] * (reach_m - ln.length + 1.0)))
    return path


def _stations(parent: LineString, s0: float, fwd: bool) -> list[float]:
    """The parent's own vertex stations beyond ``s0``, in walk order."""
    ss = []
    acc = 0.0
    cs = list(parent.coords)
    for i in range(1, len(cs)):
        acc += math.hypot(cs[i][0] - cs[i - 1][0], cs[i][1] - cs[i - 1][1])
        ss.append(acc)
    ss = [0.0] + ss
    return [s for s in ss if s > s0 + 1e-6] if fwd else \
           [s for s in reversed(ss) if s < s0 - 1e-6]


def _deck_half_width(axis_fn, ss, cells, polys, half_default: float) -> float:
    """THE DECK'S HALF-WIDTH ACROSS THE ROAD (spec §34 (5)): the MEDIAN
    half-width of the governed pavement cell the aeroway's axis stands in,
    measured perpendicular to the axis at each station.

    A taxiway bridge way carries no ``width`` tag, so the carriageway
    fallback reads 2 lanes × 3.5 m = 7 m — a third of a real taxiway, and
    a 7 m bore puts both its mouths under the deck.  The taxi cell the
    aeroway runs in IS the deck (measured LEMD F-6: ``junction/pav157``),
    and its own edges across the axis are the width the road passes under.
    ``pavement_half_widths`` cannot answer this: its
    ``ramp_pavement_max_offset_m`` test asks whether a pavement TRACES a
    road, and a junction blob's across-axis centre is metres off the
    taxiway centreline it contains."""
    if not polys:
        return half_default
    tree = STRtree(polys)
    reach = 200.0
    vals: list[float] = []
    for i, s in enumerate(ss):
        p = axis_fn(s)
        a = axis_fn(max(0.0, s - 1.0))
        b = axis_fn(s + 1.0)
        u = unit(a, b)
        nv = (-u[1], u[0])
        pt = Point(p)
        best = None
        for j in tree.query(pt, predicate="intersects"):
            c = cells[int(j)]
            if c.kind == "structure" or not polys[int(j)].contains(pt):
                continue
            poly = polys[int(j)]
            hs = []
            for sgn in (1.0, -1.0):
                ray = LineString([p, (p[0] + nv[0] * sgn * reach,
                                      p[1] + nv[1] * sgn * reach)])
                x = ray.intersection(poly.boundary)
                if x.is_empty:
                    hs = []
                    break
                pts = [g for g in getattr(x, "geoms", [x]) if g.geom_type == "Point"]
                if not pts:
                    hs = []
                    break
                hs.append(min(math.hypot(g.x - p[0], g.y - p[1]) for g in pts))
            if len(hs) == 2:
                h = (hs[0] + hs[1]) / 2.0
                if best is None or h < best:
                    best = h
        if best is not None:
            vals.append(best)
    if not vals:
        return half_default
    vals.sort()
    return vals[len(vals) // 2]
