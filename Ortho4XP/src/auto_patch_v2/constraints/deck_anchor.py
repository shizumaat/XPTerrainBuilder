"""THE DECK END LINE IS AN ANCHOR (spec ``Ortho4XP/docs/specs/
deck-end-anchors-20261103.md``; owner RULINGS 2026-11-03c, the 16:00Z /
16:08Z asks; #1717, #1715, #1712, #1738).

A pack HARD-DECK bridge (``planar/deck_bridge``: an ``ATTR_hard_deck`` or
signature plate the airport's own pavement drives across, 27c) states
where the carried runway or taxiway stands: its end lines.  Until this
module the deck was RELATIONAL only (``constraints/edge_deck``: one zero,
flush at both end lines) and nothing held its level, so the runway rows
fought the cut under it (round 1: runway −1.8 m) or, the ridge trimmed out
of the cut, drifted across the gap (round 2: 0.64 m).  Now each end line
is an ANCHOR, as a CIFP threshold, a tile seam or a runway crossing node
is: one hard ``Pin`` before the solve, and the airside grades smoothly to
it.  A frame with no pack hard deck mints nothing (§2.0): every row is as
before.

ONE DERIVATION (:func:`derive`, called once by ``runway_chord.
with_runway_chord`` and published as ``PlanarMap.deck_anchors``), read off
the map's decks (``PlanarMap.decks``, deck redesign §1) — a deck no trench
runs under included — and taken whole by stage 1's map
(``model/stage_one.from_full``):

* the FAMILY is the deck's (``DeckBridge.family``, its most senior carried
  route, ``planar/deck_route``), one per object — never voted per end line;
* the PINNED VERTEX of an end is where the CARRIED ROUTE leaves the deck —
  a runway deck: the end of the runway's ridge where the cut trimmed it
  (``planar/overlay._ridges_off_cuts``), else its ridge vertex nearest the
  end line; a taxi deck: the seat station nearest where the carried taxi
  centreline crosses the end line, else the one nearest its middle;
* the PROFILE there is read with the bridge window BLIND — the runway's
  re-fit chord (``runway_chord._chords``, its trend fitted without the DEM
  inside the deck rings and the trench outlines) or the carried taxi
  chain's own trend over the same exclusion;
* the deck never tilts (Q1 a): its zero is the mean of ``profile − top``
  over its end lines, each end then at ``zero + top`` — for two ends
  ``z_A = ½(p_A + p_B − r)``, ``z_B = z_A + r``, ``r = top_B − top_A``;
* PRECEDENCE (owner 2026-11-03T16:20Z, Q2 as answered): tile seam > CIFP
  threshold > deck anchor.  A CIFP threshold on the deck or within its
  vertical-curve reach GOVERNS the deck: the zero is set so the deck top
  at the threshold's station is the CIFP value, the other end following
  the authored rise (LPMA: a whole runway end on a hard deck).  A seam pin
  or a crossing node within an anchor's reach, or a deck grade over the
  family cap, mints the anchor under :data:`YIELD_HEAD` (``[design]
  yielding_pin_rulings``): it is held unless in conflict itself, and then
  yields just enough (``DesignReport.pin_yield``) — the seam wins, and the
  object seat follows the built surface.  A vertex a senior pin already
  holds takes no anchor pin.

THE TAXI DECK'S LEVEL IS THE AIRSIDE SOLVE'S (deck redesign §5 (b); owner
2026-11-03T21:16Z Q2: "the bridge ends need to be treated like a building
pad: we need to determine what elevation is feasible from the route graph
... the airside pavement must weld to and grade perfectly to the bridge
deck").  A taxi deck takes NO pre-solve pin: its end lines' stations are
held rigid and flush to one zero (``constraints/edge_deck``) inside the
airside solve, which finds the level its routes make feasible; that level
is published as the anchor (:func:`settle`, after the solve, before the
emit, the census and the object stage — the stations are stage 1 columns,
constants of stage 2 and of the cut under the deck), and the object reseats
to it (``pipeline/rebake_inputs._deck_plate``).  A runway deck keeps its
pre-solve pin on the window-blind chord (owner 18:10Z).  A ROAD deck — one no
apt.dat route crosses (``planar/deck_route``, owner 2026-11-03T23:02Z) — is no
taxi bridge but takes the same reading: where its end lines meet the airside
pavement the surface passing over (its top) stays flush with it, at the level
the solve builds there.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from ..geom import exact
from ..law import Law
from ..law.tables import role_cap, runway_vertical_curve_bound
from ..model.airport import Airport
from ..model.constraints import Pin, Row, Source
from ..model.planar import PlanarMap
from ..model.stage_one import full_map
from ..model.structures import DeckAnchor
from .deck_lines import cut_faces
from .geometry import project_to_chain
from .precedence import view
from .trend import trend_of

__all__ = ["GEN", "RULING", "YIELD_HEAD", "SOLVED_NOTE", "derive", "deck_anchor_pins",
           "deck_holes", "blind", "settle", "sidecar_records"]

GEN = "deck_anchor"
#: the ruling of a held anchor (a ``Pin`` is an equality: no head list)
RULING = "structures.deck end line anchor (RULINGS 2026-11-03c Q1 a)"
#: the head of a yielding anchor (``[design] yielding_pin_rulings``)
YIELD_HEAD = "structures.deck anchor yields to a senior pin"
YIELD_RULING = f"{YIELD_HEAD} (RULINGS 2026-11-03c Q2 a)"
#: the note of a taxi deck's anchor the airside solve levels (module doc)
SOLVED_NOTE = "level from the airside solve (deck redesign §5 (b), owner Q2 2026-11-03)"

_RUNWAY = ("runway", "runway_crossing")
_TAXI_CENTERLINE = "taxi_centerline"
#: the plan tolerance (m) a route's vertex stands "on" an end line within
#: (the runway ridge's reach, the carried chain's search)
_ON_LINE_M = 1.5


def deck_holes(pm: PlanarMap) -> list[tuple[tuple[float, float], ...]]:
    """The bridge WINDOWS: every deck's ring (``PlanarMap.decks``) and every
    floor and void face of each cut naming a deck (deck redesign §2 row 16:
    an OSM bore carries no ``Tunnel.footprint``, so its outline was never
    blind) — the DEM inside them reads the deck or the road under it, never
    the ground the carried route runs on.  A cut's faces are the ones whose
    point stands inside its rim path (``Tunnel.wall_path``), else within
    its half width and rim stand-off of its axis."""
    out = [tuple(tuple(p) for p in db.ring) for db in getattr(pm, "decks", ()) or ()
           if len(db.ring) >= 3]
    cuts = [tn for tn in getattr(pm, "structures", ()) or () if getattr(tn, "deck_bridge", "")]
    for tn in cuts:
        fp = tuple(getattr(tn, "footprint", ()) or ())
        if len(fp) >= 3:
            out.append(fp)
    return out + cut_faces(pm, cuts)


def blind(holes) -> "_t.Callable[[tuple[float, float]], bool]":
    """``inside(xy)``: whether a point is in a bridge window (``deck_holes``)."""
    if not holes:
        return lambda _xy: False
    from shapely.geometry import Point, Polygon
    from shapely.ops import unary_union
    from shapely.prepared import prep
    u = prep(unary_union([Polygon(h).buffer(0.0) for h in holes]))
    return lambda xy: u.covers(Point(xy))


def _ends(pm: PlanarMap, law: Law) -> dict[str, list]:
    """Object id -> its end lines ``(station xys, seat terms, depth, deck)``,
    each once, every piece's A then B in the map's deck order
    (``constraints/deck_lines``)."""
    from .deck_lines import end_lines
    return {oid: [(e.line, e.terms, e.depth, e.deck) for e in es]
            for oid, es in end_lines(pm, law).items()}


def _off_line(xy, stations) -> float:
    """Plan distance from ``xy`` to the end line's polyline."""
    if len(stations) < 2:
        return exact.hypot(xy[0] - stations[0][0], xy[1] - stations[0][1])
    return project_to_chain(xy, list(stations))[0]


def _runway_vertex(vw, chains, rw: str, stations, others, inside, spacing: float
                   ) -> "int | None":
    """Where the runway leaves the deck: the end of a ridge piece nearest
    the end line (the cut trimmed the ridge there), else the ridge vertex
    nearest it — inside the deck's window or within reach of its line, and
    nearer this end line than the object's ``others`` (an uncut ridge's
    station stands up to half the station ``spacing`` off the line)."""
    pieces = chains.get(rw, [])

    def ours(q: int) -> bool:
        # in the window or beside the line, and in the third of the deck
        # nearest this end line (the cut runs to just short of the end lines)
        d = _off_line(vw.xy[q], stations)
        return (inside(vw.xy[q]) or d <= max(2.0 * _ON_LINE_M, 0.5 * spacing)) and all(
            d <= 0.5 * _off_line(vw.xy[q], o) for o in others)
    for pool in ([v for ch in pieces for v in (ch[0], ch[-1])], [v for ch in pieces for v in ch]):
        near = [q for q in pool if ours(q)]
        if near:
            return min(near, key=lambda q: _off_line(vw.xy[q], stations))
    return None


def _mid(stations) -> tuple[float, float]:
    n = len(stations)
    return (sum(q[0] for q in stations) / n, sum(q[1] for q in stations) / n)


def _carried(vw, taxi, ends) -> "tuple | None":
    """The taxi centreline the deck CARRIES: the chain passing nearest every
    end line's middle (the least of its greatest distance), within the
    deck's span — ``None`` where none crosses it."""
    mids = [_mid(e[0]) for e in ends]
    span = max((exact.dist(a, b) for a in mids for b in mids), default=0.0)
    best = None
    for ch in taxi:
        if len(ch) < 2:
            continue
        pts = [vw.xy[q] for q in ch]
        d = max(project_to_chain(m, pts)[0] for m in mids)
        if d <= max(span, 4.0 * _ON_LINE_M) and (best is None or d < best[0]):
            best = (d, ch)
    return None if best is None else best[1]


def _taxi_vertex(vw, ch, stations, seats) -> int:
    """The pinned vertex of a taxi end line is a SEAT STATION (round 3 §3):
    the one nearest where the carried chain crosses the end line, else the
    one nearest the line's middle — never a junction vertex beside the line
    (KIAH ``obj24551`` end B pinned ``v12883``, off every station)."""
    mx, my = _crossing(vw, ch, stations) or _mid(stations)
    return min(seats, key=lambda v: exact.hypot(vw.xy[v][0] - mx, vw.xy[v][1] - my))


def _crossing(vw, ch, stations) -> "tuple[float, float] | None":
    """Where the carried chain ``ch`` crosses the end line (its stations'
    polyline, run on a station spacing past each end), ``None`` for no
    crossing."""
    if not ch or len(ch) < 2 or len(stations) < 2:
        return None
    from shapely.geometry import LineString
    pts = [tuple(p) for p in stations]
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    n = exact.hypot(x1 - x0, y1 - y0) or 1.0
    run = n / max(1, len(pts) - 1)
    ux, uy = (x1 - x0) / n * run, (y1 - y0) / n * run
    line = LineString([(x0 - ux, y0 - uy), *pts, (x1 + ux, y1 + uy)])
    x = line.intersection(LineString([vw.xy[q] for q in ch]))
    if x.is_empty:
        return None
    c = x.centroid
    return (c.x, c.y)


def _chain_profile(pm: PlanarMap, vw, ch, xy, inside, window: float) -> "float | None":
    """The taxi chain's own DEM trend at its foot of ``xy``, the bridge
    window blind."""
    pts = [vw.xy[q] for q in ch]
    st = [0.0]
    for a, b in zip(pts, pts[1:], strict=False):
        st.append(st[-1] + exact.hypot(b[0] - a[0], b[1] - a[1]))
    tr = trend_of(((s, float(pm.vertices[q].dem_z)) for s, q in zip(st, ch, strict=True)
                   if pm.vertices[q].dem_z is not None and not inside(vw.xy[q])), window)
    return None if tr is None else tr.at(project_to_chain(xy, pts)[3])


def _ground(pm: PlanarMap, seats) -> "float | None":
    """The fallback profile: the DEM at the end line's seats (the abutment)."""
    zs = [float(pm.vertices[v].dem_z) for v in seats if pm.vertices[v].dem_z is not None]
    return sum(zs) / len(zs) if zs else None


def _profiled(pm: PlanarMap, vw, chains, ch, inside, window: float, spacing: float, chords,
              others, stations, terms, depth, deck) -> "tuple | None":
    """``(seats, depth, runway, vertex, profile, middle, line)`` of one end
    line (``ch``: the carried taxi chain; ``others``: the object's other end
    lines' stations).  The runway is the DECK's (its family and route,
    ``planar/deck_route``), never a vote of the cells at the seats."""
    seats = [v for v, _w in terms]
    if not seats or not stations:
        return None
    rw = deck.route_ref if deck.family == "runway" else ""
    v = _runway_vertex(vw, chains, rw, stations, others, inside, spacing) if rw else None
    mid = _mid(stations)
    c = (chords or {}).get(rw) if rw and v is not None else None
    if v is None:
        v = _taxi_vertex(vw, ch, stations, seats)
    p = c.z(c.station(*vw.xy[v])) if c is not None else (
        _chain_profile(pm, vw, ch, mid, inside, window) if ch is not None else None)
    p = _ground(pm, seats) if p is None else p
    return None if p is None else (seats, float(depth), rw, v, float(p), mid, tuple(stations))


def derive(pm: PlanarMap, law: Law, airport: Airport, chords: "dict | None" = None
           ) -> tuple[DeckAnchor, ...]:
    """Every end line of every pack deck (``PlanarMap.decks``), anchored
    (module doc).  ``chords``: runway id -> the window-blind re-fit chord
    (``runway_chord._chords`` with its knots); without one a runway end
    reads the DEM at its seats.  Stage 1's map takes the full map's
    anchors (:func:`_from_full`)."""
    by_obj = _ends(pm, law)
    if not by_obj:
        return ()
    full = full_map()
    if full is not None and full is not pm:
        return _from_full(pm, by_obj, full)
    from .runway_profile import ridge_chains, threshold_pins
    vw = view(pm, law)
    chains = ridge_chains(vw)
    taxi = [vw.chains[b] for b, bl in pm.breaklines.items() if bl.kind == _TAXI_CENTERLINE]
    inside = blind(deck_holes(pm))
    window = float(law.tables.emit.design.runway_profile_window_m)
    spacing = float(law.tables.emit.chords.station_spacing_m)
    thresholds = threshold_pins(pm, law, airport)
    senior = {v: "threshold" for v in thresholds}
    yielding = {v: ("seam", float(pm.vertices[v].dem_z)) for v in pm.seam_vertices
                if pm.vertices[v].dem_z is not None}
    yielding.update({r.v: ("crossing", float(r.z))
                     for r in _crossing_pins(pm, law, airport)})
    senior.update({v: k for v, (k, _z) in yielding.items()})
    rws = {rw.id: rw for rw in airport.runways}
    out: list[DeckAnchor] = []
    for oid in sorted(by_obj):
        ends = by_obj[oid]
        cut = {tuple(e[0]): e[3].cut for e in ends}
        family = "runway" if any(e[3].family == "runway" for e in ends) else \
            ("taxi" if any(e[3].family == "taxi" for e in ends) else ends[0][3].family)
        ch = _carried(vw, taxi, ends)
        rows = [r for r in (_profiled(pm, vw, chains, ch, inside, window, spacing, chords,
                                      [o[0] for o in ends if o is not e], *e)
                            for e in ends) if r is not None]
        if not rows:
            continue
        rw = rws.get(next((r[2] for r in rows if r[2]), ""))
        zero = sum(r[4] - r[1] for r in rows) / len(rows)
        gov = _threshold_zero(vw, law, rows, zero, thresholds, inside, rw)
        d0 = rows[0][1]
        for k, (seats, depth, rwid, v, p, _mid, line) in enumerate(rows):
            z = (gov[0] if gov else zero) + depth
            a = DeckAnchor(oid, "AB"[k] if k < 2 else str(k), v, tuple(seats),
                           round(z, 6), round(depth, 6), round(depth - d0, 6),
                           family, rwid, round(p, 6), note=gov[1] if gov else "",
                           cut=cut.get(line, "none"), line=line)
            out.append(_solved_level(_judge(a, rows, vw, law, rws.get(rwid), senior,
                                            yielding)))
    return tuple(_one_per_vertex(out))


def _solved(a: DeckAnchor) -> bool:
    """Whether ``a``'s level is the solve's (module doc): every deck but a
    runway's."""
    return a.family != "runway"


def _solved_level(a: DeckAnchor) -> DeckAnchor:
    """A held TAXI (or road) anchor is no pin (module doc, §5 (b)): its level
    is the airside solve's, published by :func:`settle`."""
    if not _solved(a) or not a.pinned:
        return a
    return _dc.replace(a, pinned=False,
                       note=SOLVED_NOTE + (f"; {a.note}" if a.note else ""))


def settle(pm: PlanarMap, z) -> PlanarMap:
    """``pm`` with every taxi or road deck's anchors at the level the solve
    built (module doc): the object's one zero is the mean over its stations
    of ``z − top``, each end at ``zero + top``.  The anchor stays unpinned:
    it publishes a level, it never held one (the census reads its stations
    off the one zero, ``verify/deck_flush``).  A map with no such deck, or
    no solved surface, is returned as is."""
    anchors = tuple(getattr(pm, "deck_anchors", ()) or ())
    if z is None or len(z) == 0 or not any(_solved(a) for a in anchors):
        return pm
    acc: dict[str, dict[int, float]] = {}
    for a in anchors:
        if _solved(a):
            for s in a.stations:
                acc.setdefault(a.object_id, {}).setdefault(s, float(z[s]) - float(a.top_y))
    zero = {oid: sum(d.values()) / len(d) for oid, d in acc.items() if d}
    out = [a if not _solved(a) or a.object_id not in zero else _dc.replace(
        a, z_m=round(zero[a.object_id] + float(a.top_y), 6)) for a in anchors]
    return _dc.replace(pm, deck_anchors=tuple(out))


def _from_full(pm: PlanarMap, by_obj: dict, full: PlanarMap) -> tuple[DeckAnchor, ...]:
    """STAGE 1'S ANCHORS ARE THE FULL MAP'S (deck redesign §1, one
    derivation for both maps; ``model/stage_one.from_full``): each end
    line of this map takes the full map's anchor of the same line — its
    level, family, runway, yield and note — on this map's seat stations; its
    pinned vertex is this map's vertex at the full map's pinned point, else
    the station nearest that point."""
    at = {tuple(vx.xy): v for v, vx in pm.vertices.items()}
    seats = {(oid, tuple(e[0])): [v for v, _w in e[1]] for oid, es in by_obj.items() for e in es}
    out: list[DeckAnchor] = []
    for a in getattr(full, "deck_anchors", ()) or ():
        st = seats.get((a.object_id, tuple(a.line)))
        if not st:
            continue
        xy = tuple(full.vertices[a.v].xy)
        v = at.get(xy)
        if v is None:
            v = min(st, key=lambda q: exact.dist(pm.vertices[q].xy, xy))
        out.append(_dc.replace(a, v=v, stations=tuple(st)))
    return tuple(_one_per_vertex(out))


def _threshold_zero(vw, law: Law, rows, zero: float, thresholds: dict, inside, rw
                    ) -> "tuple[float, str] | None":
    """``(zero, note)`` where a CIFP threshold GOVERNS the deck (module doc):
    one in the deck's window sets the deck top at its station along the
    deck to the CIFP value; one within the vertical-curve reach of an end
    line puts that end ON the runway's profile (the chord through the
    threshold), the other end following the authored rise.  The nearest
    such threshold; ``None`` for none."""
    if not thresholds or rw is None:
        return None
    rate = runway_vertical_curve_bound(law, 1.0, rw.code_number, rw.code_letter) or 0.0
    (xa, ya), (xb, yb) = rows[0][5], rows[-1][5]
    L2 = exact.sq(xb - xa) + exact.sq(yb - ya)
    best = None
    for t, cifp in thresholds.items():
        if rw.id not in _runways_at(vw, t):
            continue
        k = min(range(len(rows)), key=lambda i: vw.dist(t, rows[i][3]))
        d = vw.dist(t, rows[k][3])
        if inside(vw.xy[t]):
            x, y = vw.xy[t]
            f = 0.0 if L2 <= 0.0 else min(1.0, max(0.0, ((x - xa) * (xb - xa)
                                                        + (y - ya) * (yb - ya)) / L2))
            z0, why = float(cifp) - (rows[0][1] + f * (rows[-1][1] - rows[0][1])), "on the deck"
        else:
            z0 = rows[k][4] - rows[k][1]
            reach = math.sqrt(2.0 * abs(z0 - zero) / rate) if rate > 0.0 else 0.0
            if d > reach:
                continue
            why = f"{d:.1f} m from end {'AB'[k] if k < 2 else k}, inside its {reach:.1f} m reach"
        if best is None or d < best[0]:
            best = (d, z0, f"the CIFP threshold v{t} governs the deck ({why}; "
                           f"deck moved {z0 - zero:+.2f} m)")
    return None if best is None else (best[1], best[2])


def _runways_at(vw, v: int) -> set[str]:
    """The runways whose family faces ring ``v``."""
    pm = vw.pm
    return {r for f in pm.vertices[v].incident_faces if pm.faces[f].role in _RUNWAY
            for r in str(pm.faces[f].ref).split("+")}


def _judge(a: DeckAnchor, rows, vw, law: Law, rw, senior: dict, yielding: dict
           ) -> DeckAnchor:
    """``a`` judged (module doc): a senior pin on its vertex takes it; a seam
    or crossing pin on the deck's span or farther off its level than the
    family's cap can climb, or a deck grade over that cap, makes it yield
    (Q2 as answered)."""
    if a.v in senior:
        return _dc.replace(a, pinned=False, note=f"a {senior[a.v]} pin holds v{a.v}")
    code = (rw.code_number, rw.code_letter) if rw is not None else (None, None)
    role = "runway" if a.family == "runway" else _role_of(vw.pm, law, a.stations)
    cap = role_cap(law, role, *code) if role else None
    others = [r for r in rows if r[3] != a.v]
    span = max((vw.dist(a.v, r[3]) for r in others), default=0.0)
    rise = max((abs(a.top_y - r[1]) for r in others), default=0.0)
    if cap is not None and span > 0.0 and rise / span > float(cap.longitudinal) + 1e-9:
        return _dc.replace(a, yielding=True,
                           note=f"deck grade {rise / span:.4f} over the cap {cap.longitudinal}")
    # THE SEAM AND THE CROSSING ARE SENIOR (Q2 as answered): one standing on
    # the deck, or one the family's own grade cannot reach from the anchor's
    # level, makes the anchor yield
    lon = float(cap.longitudinal) if cap is not None else math.inf
    hit = [(vw.dist(a.v, q), q, kind, zq) for q, (kind, zq) in yielding.items()]
    hit = [h for h in hit if h[0] < span or abs(a.z_m - h[3]) > lon * h[0]]
    if not hit:
        return a
    d, q, kind, zq = min(hit)
    return _dc.replace(a, yielding=True, note=(a.note + "; " if a.note else "") +
                       f"a {kind} pin v{q} {d:.1f} m away at {zq:.2f} m")


def _role_of(pm: PlanarMap, law: Law, seats) -> "str | None":
    """The capped role most of an end line's seats stand on (a taxi deck's
    cap), ``None`` for none."""
    votes: dict[str, int] = {}
    for v in seats:
        for f in pm.vertices[v].incident_faces:
            r = pm.faces[f].role
            if role_cap(law, r) is not None:
                votes[r] = votes.get(r, 0) + 1
    return max(sorted(votes), key=lambda r: votes[r]) if votes else None


def _one_per_vertex(anchors: list[DeckAnchor]) -> list[DeckAnchor]:
    """Two end lines never pin one vertex: the second keeps its record, unpinned."""
    seen: set[int] = set()
    out = []
    for a in anchors:
        if a.pinned and a.v in seen:
            a = _dc.replace(a, pinned=False, note=f"v{a.v} already anchors another end line")
        seen.add(a.v)
        out.append(a)
    return out


def _crossing_pins(pm: PlanarMap, law: Law, airport: Airport) -> list:
    from .runway_chord import runway_crossing_pins
    return runway_crossing_pins(pm, law, airport)


def deck_anchor_pins(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """One hard ``Pin`` per anchored end line (module doc)."""
    return [Pin(a.v, float(a.z_m), Source(GEN, YIELD_RULING if a.yielding else RULING,
                                          (a.object_id, f"end:{a.end}", a.family)))
            for a in getattr(planar, "deck_anchors", ()) or () if a.pinned]


def sidecar_records(planar: PlanarMap) -> list[dict]:
    """The sidecar ``deck_anchors`` (EVIDENCE, and the ``deck_end_flush``
    census's input): per end line its object, end, pinned vertex, level,
    profile, top, family, yield, cut, its deck's witness, and its seat
    stations as ``[lat, lon]``
    (the vertex keys, the emitted node identity)."""
    def ll(v: int) -> list[float]:
        return [float(planar.vertices[v].key[0]), float(planar.vertices[v].key[1])]
    witness = {}
    for db in getattr(planar, "decks", ()) or ():
        witness.setdefault(db.object_id, db.witness)
    return [{"object": a.object_id, "end": a.end, "v": a.v, "at": ll(a.v),
             "z_m": round(a.z_m, 3), "profile_z_m": round(a.profile_z_m, 3),
             "top_y": round(a.top_y, 3), "rise_m": round(a.rise_m, 3), "family": a.family,
             "ref": a.ref, "yielding": a.yielding, "pinned": a.pinned, "note": a.note,
             "cut": a.cut, "witness": witness.get(a.object_id, ""),
             "stations": [ll(v) for v in a.stations]}
            for a in getattr(planar, "deck_anchors", ()) or ()]
