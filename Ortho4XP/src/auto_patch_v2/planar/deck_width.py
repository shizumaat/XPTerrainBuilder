"""ONE GENERATED DECK PER TAXIWAY, AS WIDE AS ITS TAXIWAY AND SHOULDERS
(owner RULINGS 2026-11-19s (3) (b), (4) (c); ``docs/specs/airside-first-
bridges-spec.md`` section 1 row 1).

``planar/deck_generated`` reads where the airport's pavement covers a
road's cut (the piece ``P ∩ C``).  Its WIDTH is never that pavement's
(KBNA 1.0.565: "They seem wider than they need to be, I would expect them
to generally match the width of the taxiway + a shoulder"): each apt.dat
taxi route (row 1202) crossing the piece gets ITS OWN deck -- two parallel
taxiways two decks, the gap between them open over one cut (19s (3) (b))
-- a parallelogram whose ENDS run along the road (the cut's crests, the
piece's extent along the route) and whose SIDES run along the route at
``[deck_gen] width_by_class_m`` of the route's width class (ICAO Annex 14
§3.9.3 taxiway width plus §3.10.1 shoulders: the taxiway as drawn) and
``shoulder_share`` of that each side (owner RULINGS 2026-11-19s (8) (a):
1.0.566's decks at the class width read "exactly taxiway width"), centred
on its centreline.
A route of no class takes the airport's most common class.

Nothing here names an airport.  Build-time impact: a few shapely
intersections per generated deck piece.
"""
from __future__ import annotations

import collections
import math
import typing as _t

from shapely.geometry import LineString, Polygon

__all__ = ["cores", "parted", "route_ends", "route_specs", "rings"]

XY = tuple[float, float]
#: two crossing segments this near and this parallel are one route (m, deg)
_SAME_ROUTE_M = 3.0
_SAME_ROUTE_DEG = 20.0


def _class_width_m(law, letter: "str | None", fallback: "str | None" = None) -> float:
    """The taxiway as drawn (m) of a width class letter (``width_by_class_m``)."""
    table = dict(law.tables.structures.deck_gen.width_by_class_m)
    for k in (letter, fallback, "C"):
        if k and str(k).upper() in table:
            return float(table[str(k).upper()])
    return max(float(v) for v in table.values())


def _grow(law) -> float:
    """The deck's width over its taxiway's: a ``shoulder_share`` shoulder
    each side (owner RULINGS 2026-11-19s (8) (a): "the total bridge width
    is closer to twice the width of the taxiway")."""
    return 1.0 + 2.0 * float(law.tables.structures.deck_gen.shoulder_share)


def _crossings(piece: Polygon, airport) -> list[tuple[LineString, _t.Any]]:
    """Every taxi edge's stretch across ``piece`` (longest first)."""
    nodes = getattr(airport, "taxi_nodes", {}) or {}
    out = []
    for e in getattr(airport, "taxi_edges", ()) or ():
        if getattr(e, "is_runway", False) or e.a not in nodes or e.b not in nodes:
            continue
        a, b = nodes[e.a].xy, nodes[e.b].xy
        if a == b:
            continue
        x = LineString([a, b]).intersection(piece)
        for q in getattr(x, "geoms", [x]):
            if q.geom_type == "LineString" and q.length > 1.0:
                out.append((q, e))
    return sorted(out, key=lambda r: -r[0].length)


def _unit(line: LineString) -> XY:
    (x0, y0), (x1, y1) = line.coords[0], line.coords[-1]
    n = math.hypot(x1 - x0, y1 - y0)
    return ((x1 - x0) / n, (y1 - y0) / n) if n > 1e-9 else (0.0, 0.0)


def _routes(piece: Polygon, airport) -> list[tuple[LineString, list]]:
    """The crossings grouped into routes: ``(its longest stretch, its
    edges)`` -- one per taxiway NAME (a curve's segments, a split edge),
    an unnamed edge joining the route it continues (as near and as
    parallel as :data:`_SAME_ROUTE_M` / :data:`_SAME_ROUTE_DEG`)."""
    cos_t = math.cos(math.radians(_SAME_ROUTE_DEG))
    groups: list[tuple[LineString, list]] = []
    for q, e in _crossings(piece, airport):
        d, name = _unit(q), str(getattr(e, "name", "") or "")
        for main, edges in groups:
            m = _unit(main)
            same = any(str(getattr(x, "name", "") or "") == name for x in edges) if name \
                else (abs(d[0] * m[0] + d[1] * m[1]) >= cos_t
                      and q.distance(main) <= _SAME_ROUTE_M)
            if same:
                edges.append(e)
                break
        else:
            groups.append((q, [e]))
    return groups


def _common_class(airport) -> "str | None":
    got = collections.Counter(str(e.width_class).upper() for e in
                              getattr(airport, "taxi_edges", ()) or ()
                              if getattr(e, "width_class", None))
    return got.most_common(1)[0][0] if got else None


def _reach(b: float, sign: float, a0: float, a1: float, u: XY, w: XY, pave_at, reach: float
           ) -> float:
    """End ``b`` of a deck moved ``sign`` along its route until the airport's
    pavement lies just past it across most of its width (a deck over a
    pack's hole spans the hole, pavement to pavement: spec 2123 #2183 item
    4), at most ``reach`` metres; ``b`` where pavement already meets it."""
    (ux, uy), (wx, wy) = u, w
    lw = math.hypot(wx, wy)
    probes = [a0 + (a1 - a0) * k / 6.0 for k in range(1, 6)]
    e = 0.0
    while e <= reach:
        bb = b + sign * (e + 0.5) / lw
        hit = sum(1 for a in probes if pave_at((a * ux + bb * wx, a * uy + bb * wy)))
        if 2 * hit > len(probes):
            return b + sign * e / lw
        e += 0.5
    return b


def route_specs(piece: Polygon, road_dir: "XY | None", airport, law, pave_at=None,
                cover=None, avoid=None) -> list[tuple[XY, list]]:
    """``(road direction, deck spec)`` per taxi route across ``piece``
    (module doc; the spec ``[w, det, a0, a1, b0, b1, note, a_c, hc]``: the
    ring ``a u + b w``, its centreline ``a_c`` and its taxiway's half
    width ``hc``); ``[]`` where no route crosses it at an angle to the road
    (the caller keeps the piece).  ``pave_at(xy)``: whether the airport's pavement
    stands there -- each end then reaches it (:func:`_reach`).  ``cover``:
    the cover each covered road needs past the piece, ``avoid`` where the
    pack stands (:func:`_spans_cover`)."""
    if road_dir is None or piece.is_empty:
        return []
    ux, uy = road_dir
    cos_t = math.cos(math.radians(_SAME_ROUTE_DEG))
    common = _common_class(airport)
    got: list[list] = []          # [w, det, a0, a1, b0, b1, note]
    for main, edges in _routes(piece, airport):
        wx, wy = _unit(main)
        if abs(wx * ux + wy * uy) >= cos_t:
            continue                     # a route along the road crosses no cut
        det = ux * wy - uy * wx
        b0, b1 = _span((ux, uy), (wx, wy), piece.exterior.coords)[1]
        mx, my = main.interpolate(0.5, normalized=True).coords[0]
        a_c = (mx * wy - my * wx) / det
        letters = sorted({str(e.width_class).upper() for e in edges if e.width_class})
        letter = letters[-1] if letters else None
        core = _class_width_m(law, letter, common)
        width = core * _grow(law)
        ha, hc = 0.5 * width / abs(det), 0.5 * core / abs(det)
        if pave_at is not None:
            # the taxiway's own pavement meets each end (its shoulders may
            # stand over the ground)
            reach = float(law.tables.structures.deck_gen.end_reach_m)
            b0 = _reach(b0, -1.0, a_c - hc, a_c + hc, (ux, uy), (wx, wy), pave_at, reach)
            b1 = _reach(b1, 1.0, a_c - hc, a_c + hc, (ux, uy), (wx, wy), pave_at, reach)
        names = sorted({str(e.name) for e in edges if getattr(e, "name", "")})
        lo_a, hi_a, why = a_c - ha, a_c + ha, (f"{width:g} m wide (taxiway + a half-width "
                                               "shoulder each side, RULINGS 2026-11-19s (8) (a))")
        if pave_at is not None:
            runs = _end_runs(b0, b1, a_c, hc, (ux, uy), (wx, wy), det, pave_at, law, width)
            lo_a, hi_a, why = _pavement_width(runs, a_c, hc, ha, det, width)
        d = [(wx, wy), det, lo_a, hi_a, b0, b1,
             f"taxiway {'/'.join(names) or '?'} class "
             f"{letter or (common or '?') + ' (the airport common)'}: deck {why}", a_c, hc]
        grown = _spans_cover((ux, uy), d, cover, avoid)
        if grown:
            d[6] += f"; spans its roads' whole cover ({grown:.1f} m more)"
        got.append(d)
    return [((ux, uy), d) for d in _merged((ux, uy), got)]


def _run_at(b: float, a_c: float, hc: float, u: XY, w: XY, det: float, pave_at,
            step: float, most: float) -> "tuple[float, float] | None":
    """The run of the airport's pavement across the route at ``b`` holding
    the taxiway (``a_c`` +- ``hc``), as ``(a0, a1)``; ``None`` with none;
    ``(-inf, inf)`` where it runs on past ``most`` metres either way (broad
    pavement: an apron)."""
    (ux, uy), (wx, wy) = u, w

    def paved(a: float) -> bool:
        return bool(pave_at((a * ux + b * wx, a * uy + b * wy)))
    da = step / max(abs(det), 1e-9)
    start = next((a for a in (a_c + k * da for k in range(int(hc / da) + 1)
                              for k in (k, -k)) if paved(a)), None) if hc > 0.0 else None
    if start is None:
        return None
    lim = most / max(abs(det), 1e-9)
    lo = hi = start
    while paved(lo - da):
        lo -= da
        if start - lo > lim:
            return -math.inf, math.inf
    while paved(hi + da):
        hi += da
        if hi - start > lim:
            return -math.inf, math.inf
    return lo, hi


def _end_runs(b0: float, b1: float, a_c: float, hc: float, u: XY, w: XY, det: float,
              pave_at, law, width: float) -> list:
    """The pavement run just past each end of a route deck (:func:`_run_at`
    ``[deck_gen] end_width_probe_m`` past ``b0`` and ``b1``), read out to
    ``end_width_broad`` x the deck's ``width``."""
    g = law.tables.structures.deck_gen
    probe, most = float(g.end_width_probe_m), float(g.end_width_broad) * width
    lw = math.hypot(*w)
    return [_run_at(b, a_c, hc, u, w, det, pave_at, 0.5, most)
            for b in (b0 - probe / lw, b1 + probe / lw)]


def _pavement_width(runs, a_c: float, hc: float, ha: float, det: float, width: float
                    ) -> tuple[float, float, str]:
    """``(a0, a1, note)``: THE DECK IS AS WIDE AS THE PAVEMENT IT MEETS
    (owner RULINGS 2026-11-20a (2): "bridge width, should match the width of
    the pack pavement it touches on either side of the cut as long as it's
    larger than the taxiway x2 rule, if the two sides are different, use the
    narrower one, we don't want to expand to match a whole apron"): of the
    two end runs the NARROWER, never under ``width`` (19s (8) (a), the
    taxiway twice) about the centreline; an end with no pavement run or a
    broad one (an apron) never widens it."""
    m = abs(det)
    widths = [None if r is None else (math.inf if math.isinf(r[0]) else (r[1] - r[0]) * m)
              for r in runs]
    names = " / ".join("none" if x is None else ("broad" if math.isinf(x) else f"{x:.1f} m")
                       for x in widths)
    narrow = None if None in widths else min(zip(widths, runs, strict=True),
                                             key=lambda q: q[0])
    if narrow is None or math.isinf(narrow[0]) or narrow[0] <= width + 1e-6:
        return (a_c - ha, a_c + ha,
                f"{width:g} m wide (taxiway twice, RULINGS 2026-11-19s (8) (a); the pavement "
                f"at its ends A / B: {names}, RULINGS 2026-11-20a (2))")
    a0, a1 = min(narrow[1][0], a_c - hc), max(narrow[1][1], a_c + hc)
    if a1 - a0 < 2.0 * ha:
        grow = 0.5 * (2.0 * ha - (a1 - a0))
        a0, a1 = a0 - grow, a1 + grow
    return (a0, a1, f"{(a1 - a0) * m:.1f} m wide: the narrower pavement at its ends A / B "
            f"{names} (RULINGS 2026-11-20a (2))")


def rings(specs: _t.Sequence[tuple[XY, list]]) -> list[tuple[Polygon, str]]:
    """``(deck ring, note)`` of each route deck spec."""
    return [(_ring(u, d), d[6]) for u, d in specs]


def cores(specs: _t.Sequence[tuple[XY, list]]) -> list[Polygon]:
    """Each route deck spec's ring over its taxiway alone (no shoulders)."""
    return [_core(u, d) for u, d in specs]


def parted(specs: list[tuple[XY, list]], law, avoid=None) -> list[tuple[XY, list]]:
    """``specs`` with every two decks standing at least ``[deck_gen]
    parallel_gap_m`` apart (owner RULINGS 2026-11-19s (3) (b): "two parallel
    taxiways have to have a minimum gap between them which always leave a
    gap between two bridges"): both give up their shoulders a metre at a
    time, about their own centrelines, never below their taxiway's width.
    MEASURED KRDU at twice the class width: two taxiways over one curving
    road 64 m apart, their 76 m decks overlapping 422 m2.  So does a deck
    whose shoulders reach onto a part of ``avoid`` (the pack's decks and
    frames, the structure pass's corridors) its taxiway does not stand on
    (KRDU ``o4gen_c18ee4b1``: a shoulder over a tunnel ramp 7.9 m under it)."""
    gap = float(law.tables.structures.deck_gen.parallel_gap_m)
    parts = [q for q in getattr(avoid, "geoms", [avoid]) if q.geom_type == "Polygon"] \
        if avoid is not None and not avoid.is_empty else []
    for u, d in specs:
        # what the taxiway itself stands on (its own road's corridor) is its
        far = [q for q in parts if not q.intersects(_core(u, d))]
        while any(_ring(u, d).intersection(q).area > 1.0 for q in far) and _narrow(u, d):
            pass
    for _ in range(_PART_STEPS):
        moved = False
        for i in range(len(specs)):
            for j in range(i + 1, len(specs)):
                ri, rj = _ring(*specs[i]), _ring(*specs[j])
                if ri.distance(rj) >= gap - 1e-6:
                    continue
                moved = _narrow(*specs[i]) | _narrow(*specs[j]) or moved
        if not moved:
            break
    return specs


#: the most metres a deck gives up each side to part from its neighbours
_PART_STEPS = 60


def _narrow(u: XY, d: list) -> bool:
    """``d`` a metre narrower each side about its centreline (``d[7]``), never
    under its taxiway's half width (``d[8]``); whether it moved."""
    step = 1.0 / max(abs(d[1]), 1e-9)
    a_c, hc = d[7], d[8]
    a0, a1 = max(d[2], min(a_c - hc, d[2] + step)), min(d[3], max(a_c + hc, d[3] - step))
    if a0 == d[2] and a1 == d[3]:
        return False
    d[2], d[3] = a0, a1
    if "narrowed to part" not in d[6]:
        d[6] += "; narrowed to part from a neighbouring deck or structure (parallel_gap_m, " \
                "RULINGS 2026-11-19s (3) (b))"
    return True


def _spans_cover(u: XY, d: list, cover, avoid=None) -> float:
    """THE DECK SPANS ITS CROSSING (lane lcarve2): ``d``'s ring grown, in
    place, over every part of ``cover`` it touches -- the carriageway and
    its shoulders of each road the pavement covers, where it runs on under
    pavement past the piece (an apron or a pack junction the road leaves
    the deck under: KRDU 1.0.565 ``-255`` met the apron's no-bridge level
    at the deck's side, 5 m short of its clearance).  The deck is the
    airside pavement there (stage 1 solves its ring paved), so growing it
    never moves airside.  Growth that would reach further onto ``avoid``
    (the pack's own decks and frames: the pack always wins, B1 (c)) is
    undone.  Returns how far it grew (m, the larger of the two directions)."""
    if cover is None or cover.is_empty:
        return 0.0
    a0, a1, b0, b1 = d[2], d[3], d[4], d[5]
    on_pack = _ring(u, d).intersection(avoid).area if avoid is not None else 0.0
    parts = [q for q in getattr(cover, "geoms", [cover]) if q.geom_type == "Polygon"
             and q.area > 0.5]
    for _ in range(4):
        ring = _ring(u, d).buffer(_TOUCH_M)
        hit = [q for q in parts if q.intersects(ring)]
        if not hit:
            break
        parts = [q for q in parts if not q.intersects(ring)]
        for q in hit:
            (qa0, qa1), (qb0, qb1) = _span(u, d[0], q.exterior.coords)
            d[2], d[3] = min(d[2], qa0), max(d[3], qa1)
            d[4], d[5] = min(d[4], qb0), max(d[5], qb1)
    if avoid is not None and _ring(u, d).intersection(avoid).area > on_pack + 1.0:
        d[2], d[3], d[4], d[5] = a0, a1, b0, b1
        return 0.0
    lw = math.hypot(*d[0])
    da = max(a0 - d[2], d[3] - a1) * abs(d[1]) / max(lw, 1e-9)
    db = max(b0 - d[4], d[5] - b1) * abs(d[1])
    return max(da, db, 0.0)


#: a cover part this near a deck's ring runs on from it (m)
_TOUCH_M = 0.5


def _span(u: XY, w: XY, pts) -> tuple[tuple[float, float], tuple[float, float]]:
    """The ``(a, b)`` ranges of ``pts`` in the basis ``p = a u + b w``."""
    (ux, uy), (wx, wy) = u, w
    det = ux * wy - uy * wx
    ab = [((x * wy - y * wx) / det, (ux * y - uy * x) / det) for x, y in pts]
    return ((min(a for a, _b in ab), max(a for a, _b in ab)),
            (min(b for _a, b in ab), max(b for _a, b in ab)))


def _ring(u: XY, d: list) -> Polygon:
    (ux, uy), (wx, wy) = u, d[0]
    return Polygon([(a * ux + b * wx, a * uy + b * wy)
                    for a, b in ((d[2], d[4]), (d[3], d[4]), (d[3], d[5]), (d[2], d[5]))])


def _core(u: XY, d: list) -> Polygon:
    """``d``'s ring over its taxiway alone (no shoulders)."""
    return _ring(u, [d[0], d[1], d[7] - d[8], d[7] + d[8], d[4], d[5]])


def _merged(u: XY, got: list[list]) -> list[list]:
    """Route decks whose taxiways overlap (a lead-in beside its taxiway, two
    routes meeting over the road) are ONE deck: the senior's (the longer
    crossing, first) widened over the other's plan, its taxiway over both."""
    out: list[list] = []
    for d in got:
        core = _core(u, d)
        for k in out:
            if _core(u, k).intersection(core).area > 1.0:
                (a0, a1), _b = _span(u, k[0], _ring(u, d).exterior.coords)
                (c0, c1), _b = _span(u, k[0], core.exterior.coords)
                k[2], k[3] = min(k[2], a0), max(k[3], a1)
                lo, hi = min(k[7] - k[8], c0), max(k[7] + k[8], c1)
                k[7], k[8] = 0.5 * (lo + hi), 0.5 * (hi - lo)
                k[6] += f"; widened over a second route ({d[6].split(':')[0]})"
                break
        else:
            out.append(d)
    return out


def route_ends(ring: Polygon, road_dir: "XY | None", at_role, pave, step: float, to_ll
               ) -> "tuple[list, list] | None":
    """A route deck's END LINES read off its own ends -- its two edges along
    the road -- where ``airside_deck_seat.facing_contacts`` reads none (a
    deck the class width leaves inside a wider pavement meets pavement on
    its sides too, one contact all round): per end edge, the longest run of
    stations every ``step`` metres whose ground one step outside is the
    airport's pavement (``at_role(xy)``, ``pave(role)``), as ``(lat, lon)``
    (``to_ll``); ``None`` where an end meets no pavement run."""
    pts = list(ring.exterior.coords)[:-1]
    if road_dir is None or len(pts) != 4 or step <= 0.0:
        return None
    ux, uy = road_dir

    def along(e) -> float:
        dx, dy = e[1][0] - e[0][0], e[1][1] - e[0][1]
        n = math.hypot(dx, dy)
        return abs(dx * ux + dy * uy) / n if n > 1e-9 else 0.0
    edges = sorted(((pts[i], pts[(i + 1) % 4]) for i in range(4)), key=lambda e: -along(e))[:2]
    c = ring.centroid
    out = []
    for a, b in edges:
        L = math.dist(a, b)
        nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
        if nx * ((a[0] + b[0]) / 2 - c.x) + ny * ((a[1] + b[1]) / 2 - c.y) < 0.0:
            nx, ny = -nx, -ny
        runs, cur = [], []
        for k in range(max(2, int(L / step) + 1)):
            f = k / max(1, int(L / step))
            p = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            if pave(at_role((p[0] + nx * step, p[1] + ny * step))):
                cur.append(tuple(to_ll(*p)))
            elif cur:
                runs.append(cur)
                cur = []
        runs.append(cur)
        best = max(runs, key=len)
        if len(best) < 2:
            return None
        out.append(best)
    return out[0], out[1]
