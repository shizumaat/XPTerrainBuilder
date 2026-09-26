"""§27 AN AIRSIDE EDGE MAKES A LOT AIRSIDE — the airside-edge law
(owner RULINGS 2026-09-12c, extended by 2026-09-12f; Fable 2026-09-12e).

Owner 12c: "shapeID 81 at 40.461514, -3.5732897 cannot be groundside
because it shares a long edge with an apron.  Something can only be
groundside if it has no connection to airside other than a service
road."  Owner 12f: roads flip too, and the exemption is a MOUTH.

THE ONE DERIVATION SITE (08-30l).  ``roles.classify`` calls
``airside_edge_flip`` ONCE, after every groundside verdict is in (the
`lot` / `strip` source branch, the 11ac demotion, the 04u open default,
the corridor roads outside the pavement union), so the rule is spelled
here and nowhere else and ``side`` stays a pure function of ``role``
(``law.tables.role_side``): no downstream consumer changes.

It lives apart from ``roles.py`` only because that file is at its
1000-line ceiling (``tests/auto_patch_v2/test_model.py``).
"""
from __future__ import annotations

import math

import numpy as _np
from shapely.geometry import LineString, Polygon
from shapely.ops import nearest_points, unary_union
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import role_side
from .rules import Rules

__all__ = ["airside_edge_flip"]


#: §27 (owner RULINGS 2026-09-12c, Fable 12e): a face this thin — area
#: over perimeter, the radius of its inscribed circle — is an EMIT
#: ARTEFACT (a weld sliver, a ring shaved off a page), not a surface
#: anyone parks on or drives; it never flips, whatever it touches.
#: Measured at LEMD: 34 such slivers (`dsf:pol255#2` and friends,
#: 20-200 m2 on a 200-800 m perimeter) share 100+ m with airside pavement
#: each.
_LOT_SLIVER_RADIUS_M = 1.0

#: §27 (5) (owner RULINGS 2026-09-12f): a contact is END-ON — a MOUTH —
#: only when it runs across the strip rather than along it.  Within this
#: many degrees of the strip axis' NORMAL is transverse.
_MOUTH_TRANSVERSE_DEG = 45.0

#: §27 (1) + (5) + (6): the groundside roles the airside-edge rule judges.
#: The owner's 12c sentence is UNIVERSAL — "something can only be
#: groundside if it has no connection to airside other than a service
#: road" — so every groundside PAVEMENT role is judged: the LOT class,
#: the FREE ROADS (12f (a), the free-road ruling 2026-07-27) and the OPEN
#: PAGE (12i).  04u's "open pavement is never apron BY DEFAULT" holds
#: where no airside edge exists; a >= `airside_edge_min_m` lateral airside
#: edge IS evidence, and a default yields to evidence.  The groundside
#: STRUCTURE ramps (`tunnel_ramp`, `door_ramp`, `garage_ramp`,
#: `wall_corridor_ramp`) are NOT pavement anyone drives an aircraft on and
#: are never candidates.
_AIRSIDE_EDGE_CANDIDATES = ("parking_lot", "service_road", "service_junction",
                            "groundside_pavement")

#: The FREE ROADS: the only faces that offer a MOUTH (§27 (5)).
_ROAD_ROLES = ("service_road", "service_junction")


def _strip_axis_width(poly: Polygon,
                      cache: dict | None = None) -> tuple[tuple[float, float], float]:
    """``(unit axis, width)`` of ``poly`` read as a STRIP: the long side
    direction and the short side length of its minimum rotated
    rectangle.  Degenerate rings give ``((1, 0), 0.0)``."""
    if cache is not None and id(poly) in cache:
        return cache[id(poly)]
    if poly.is_empty or poly.area <= 0.0:
        return (1.0, 0.0), 0.0
    try:
        with _np.errstate(divide="ignore", invalid="ignore"):
            # GEOS' oriented_envelope trips numpy's error state on an
            # axis-aligned box: a warning, never a wrong answer.
            rect = poly.minimum_rotated_rectangle
        xs = list(getattr(rect, "exterior", rect).coords)
    except Exception:                                    # pragma: no cover
        return (1.0, 0.0), 0.0
    if len(xs) < 5:
        return (1.0, 0.0), 0.0
    e1 = (xs[1][0] - xs[0][0], xs[1][1] - xs[0][1])
    e2 = (xs[2][0] - xs[1][0], xs[2][1] - xs[1][1])
    l1 = math.hypot(*e1)
    l2 = math.hypot(*e2)
    lng, shrt = (e1, l2) if l1 >= l2 else (e2, l1)
    n = math.hypot(*lng) or 1.0
    out = ((lng[0] / n, lng[1] / n), float(shrt))
    if cache is not None:
        cache[id(poly)] = out
    return out


def _chord_dir(geom) -> tuple[float, float] | None:
    """Unit direction of a contact: the longest chord of its vertices —
    the cap's own line for an end-on contact, the run for a lateral one."""
    pts: list[tuple[float, float]] = []
    for g in getattr(geom, "geoms", [geom]):
        pts.extend(getattr(g, "coords", []))
    if len(pts) < 2:
        return None
    best = None
    bd = -1.0
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            d = (pts[i][0] - pts[j][0]) ** 2 + (pts[i][1] - pts[j][1]) ** 2
            if d > bd:
                bd, best = d, (pts[i], pts[j])
    if best is None or bd <= 0.0:
        return None
    (ax, ay), (bx, by) = best
    n = math.hypot(bx - ax, by - ay) or 1.0
    return ((bx - ax) / n, (by - ay) / n)


class _Roads:
    """The free-road CENTRELINES (the 1206 truck chains) a §27 contact
    may be the mouth of, with the station geometry that reads a neck."""

    __slots__ = ("lines", "tree", "weld_m", "max_w", "run_m")

    def __init__(self, lines, weld_m: float, max_w: float, run_m: float):
        self.lines = [ln for ln in lines if ln is not None and not ln.is_empty
                      and ln.length > 0.0]
        self.tree = STRtree(self.lines) if self.lines else None
        self.weld_m = float(weld_m)
        self.max_w = float(max_w)
        self.run_m = float(run_m)


def _cross_section(face: Polygon, line: LineString, s: float,
                   half: float) -> float:
    """Length of ``face`` cut across ``line`` at station ``s`` — the piece
    of the normal segment (half-length ``half``) that holds the station."""
    p = line.interpolate(s)
    q = line.interpolate(min(line.length, s + 0.5))
    r = line.interpolate(max(0.0, s - 0.5))
    dx, dy = q.x - r.x, q.y - r.y
    n = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / n * half, dx / n * half
    xs = LineString([(p.x - nx, p.y - ny), (p.x + nx, p.y + ny)]
                    ).intersection(face)
    piece = 0.0
    for g in getattr(xs, "geoms", [xs]):
        if g.geom_type == "LineString" and g.distance(p) < 0.6:
            piece = max(piece, g.length)
    return piece


def _centreline_mouth(face: Polygon, contact, factor: float,
                      roads: _Roads) -> bool:
    """§27 (5), the CENTRELINE mouth (issue #2, CYXY-1): a contact is also
    a mouth when a free-road centreline ENTERS ``face`` through it — the
    road whose own strip was differenced into the lot page by design
    (``roles._cut_lines``: a free route part inside a strip/lot does not
    cut again), so neither face in contact is a born road.

    The chain passes within ``weld_m`` of the contact and runs on into the
    face; the face's cross-section across the chain, read at stations
    ``weld_m .. service.min_run_m`` in, has a median at most
    ``service.free_max_width_m`` (a road NECK, not a lot the road merely
    crosses); the contact is transverse to the chain (within
    ``_MOUTH_TRANSVERSE_DEG`` of its normal, the face rule); and the
    contact's extent along the chain's NORMAL is at most ``factor`` necks.
    Measured at CYXY `dsf:pol123` / route50: 8.9 m <= 1.5 x 7.1 m."""
    if roads is None or roads.tree is None:
        return False
    weld = roads.weld_m
    for j in roads.tree.query(contact.buffer(weld), predicate="intersects"):
        line = roads.lines[int(j)]
        s0 = line.project(nearest_points(line, contact)[0])
        best: tuple[int, list[float]] | None = None
        for sign in (1, -1):
            widths: list[float] = []
            d = max(weld, 1.0)
            while d <= roads.run_m + 1e-9:
                s = s0 + sign * d
                if s < 0.0 or s > line.length:
                    break
                if face.distance(line.interpolate(s)) > 0.1:
                    break
                widths.append(_cross_section(face, line, s, roads.max_w))
                d += 1.0
            if len(widths) >= 2 and (best is None or len(widths) > len(best[1])):
                best = (sign, widths)
        if best is None:
            continue
        sign, widths = best
        neck = float(_np.median(widths))
        if neck <= 0.0 or neck > roads.max_w:
            continue
        a = line.interpolate(s0)
        b = line.interpolate(min(line.length, max(0.0, s0 + sign * roads.run_m)))
        ax, ay = b.x - a.x, b.y - a.y
        n = math.hypot(ax, ay)
        if n <= 0.0:
            continue
        axis = (ax / n, ay / n)
        cd = _chord_dir(contact)
        if cd is not None and abs(cd[0] * axis[0] + cd[1] * axis[1]) >= \
                math.cos(math.radians(90.0 - _MOUTH_TRANSVERSE_DEG)):
            continue
        nrm = (-axis[1], axis[0])
        proj = [x * nrm[0] + y * nrm[1]
                for g in getattr(contact, "geoms", [contact])
                for x, y in getattr(g, "coords", [])]
        if proj and max(proj) - min(proj) <= factor * neck:
            return True
    return False


def _is_mouth(face: Polygon, other: Polygon, contact, factor: float,
              face_is_road: bool, other_is_road: bool,
              cache: dict | None = None, roads: _Roads | None = None) -> bool:
    """§27 (5): is this contact a FREE ROAD's END CAP — its mouth?

    The owner's exemption is a road meeting the shape END-ON: "a
    groundside shape stays groundside only when every airside contact it
    has is a free road meeting it end-on at the road's mouth".  So the
    STRIP is the ROAD of the pair — by its ORIGINAL role, since a road
    that flipped to apron still offers its mouth to the shape beyond it —
    and where NEITHER face is a road there is no mouth at all: a lot
    meeting an apron is a lateral contact however short.  A mouth is at
    most ``factor`` strip-widths long AND transverse to the road's axis.
    A contact a free-road CENTRELINE enters the face through is a mouth
    too (``_centreline_mouth``, issue #2): the road's strip may live
    inside the lot page, where no face is a born road.
    """
    if face_is_road and other_is_road:
        ax_f, w_f = _strip_axis_width(face, cache)
        ax_o, w_o = _strip_axis_width(other, cache)
        axis, width = (ax_f, w_f) if w_f <= w_o else (ax_o, w_o)
    elif face_is_road:
        axis, width = _strip_axis_width(face, cache)
    elif other_is_road:
        axis, width = _strip_axis_width(other, cache)
    else:
        return _centreline_mouth(face, contact, factor, roads)
    if width > 0.0 and contact.length <= factor * width:
        d = _chord_dir(contact)
        if d is None:
            return True                              # a point touch is no edge
        cos = abs(d[0] * axis[0] + d[1] * axis[1])
        if cos < math.cos(math.radians(90.0 - _MOUTH_TRANSVERSE_DEG)):
            return True
    return _centreline_mouth(face, contact, factor, roads)


def _lateral_airside_m(face: Polygon, face_is_road: bool, tree: STRtree,
                       air: list[tuple[Polygon, bool]], weld_m: float,
                       factor: float, cache: dict | None = None,
                       roads: _Roads | None = None) -> float:
    """Metres of ``face``'s boundary running LATERALLY along airside
    pavement, measured WELD-TOLERANT at ``emit.identity.weld_spacing_m``.

    The classification cells are PRE-WELD: two cells the planar pass will
    weld into one shared edge are up to ``weld_m`` apart here, so exact
    boundary coincidence under-reads the edge the owner sees in the
    emitted patch by ~30 % (LEMD `pav137` / shapeID 81: 95.0 m exact,
    140.2 m welded).  So each airside boundary is buffered by the weld
    spacing and the face's boundary is measured INSIDE that band.  MOUTH
    contacts (§27 (5)) are dropped; the remainder is UNIONED, so two
    airside faces claiming the same run of boundary count it once.
    """
    lateral = []
    for j in tree.query(face.buffer(weld_m), predicate="intersects"):
        other, other_is_road = air[int(j)]
        contact = face.boundary.intersection(other.boundary.buffer(weld_m))
        if contact.is_empty or contact.length <= 0.0:
            continue
        if _is_mouth(face, other, contact, factor, face_is_road,
                     other_is_road, cache, roads):
            continue
        lateral.append(contact)
    if not lateral:
        return 0.0
    return float(unary_union(lateral).length)


def airside_edge_flip(final: list[list], cells, law: Law,
                       rules: Rules, roads=()) -> tuple[int, int]:
    """§27 AN AIRSIDE EDGE MAKES A LOT AIRSIDE (owner RULINGS 2026-09-12c:
    "shapeID 81 ... cannot be groundside because it shares a long edge
    with an apron. Something can only be groundside if it has no
    connection to airside other than a service road"), as extended by
    2026-09-12f: ROADS FLIP TOO AND THE EXEMPTION IS A MOUTH.

    THE ONE DERIVATION SITE (08-30l).  Every groundside verdict — the
    `lot` / `strip` source branch, the 11ac demotion, the 04u open
    default — passes through this pass, so the rule is spelled once and
    `side` stays a pure function of `role` (`law.tables.role_side`): no
    consumer changes.

    A `parking_lot` / `service_road` / `service_junction` face whose
    boundary runs at least ``rules.lot.airside_edge_min_m`` LATERALLY
    along airside pavement (`side = airside` in `precedence.toml`, less
    `building`) becomes `apron` — and a STRIP-CLASS face (one born
    `service_road` / `service_junction`) needs that contact to be at
    least ``rules.lot.road_airside_edge_frac`` OF ITS PERIMETER as well
    (§37 (2), owner RULINGS 2026-09-13q item 7).  What keeps a shape groundside is no
    longer the NEIGHBOUR'S ROLE but the SHAPE OF THE CONTACT: a free road
    meeting it END-ON at the road's mouth (``_is_mouth``).  Slivers never
    flip.  Flips PROPAGATE — a lot beside a road that became apron is
    beside apron — so the pass iterates to a FIXPOINT; it terminates
    because a role only ever moves groundside -> apron.

    Returns ``(faces flipped, iterations)``.

    v1 carried the first half as the AIRSIDE-ADJACENCY VETO
    (`auto_patch/junction_repair.py:2752-2789`, owner 2026-07-27); the v2
    port dropped it, and `roles.py`'s lot branch has minted `parking_lot`
    unconditionally ever since.

    ``roads`` are the free-road CENTRELINES (``ev.truck_chains``' lines):
    a contact one of them enters a face through is a mouth
    (``_centreline_mouth``, issue #2 CYXY-1).
    """
    min_m = float(rules.lot.airside_edge_min_m)
    frac = float(rules.lot.road_airside_edge_frac)
    factor = float(rules.lot.mouth_width_factor)
    weld_m = float(law.tables.emit.identity.weld_spacing_m)
    road_ctx = _Roads(roads, weld_m, rules.service.free_max_width_m,
                      rules.service.min_run_m)
    #: a face OFFERS A MOUTH by the role it was BORN with: a road that
    #: became apron in an earlier round still meets its neighbour end-on
    was_road = [f[0] in _ROAD_ROLES for f in final]
    fixed = [(Polygon(c.ring, c.holes), False) for c in cells
             if c.role != "building" and c.side == "airside"]
    flipped = 0
    rounds = 0
    cache: dict = {}
    while True:
        rounds += 1
        air = [(f[2], was_road[i]) for i, f in enumerate(final)
               if f[0] != "building" and role_side(law, f[0]) == "airside"]
        air = [t for t in air + fixed if not t[0].is_empty]
        if not air:
            return flipped, rounds
        tree = STRtree([t[0] for t in air])
        moved = 0
        for i, f in enumerate(final):
            role, ref, face, _letter, evid = f[0], f[1], f[2], f[3], f[4]
            if role not in _AIRSIDE_EDGE_CANDIDATES:
                continue
            per = face.length
            if per <= 0.0 or face.area / per < _LOT_SLIVER_RADIUS_M:
                continue
            shared = _lateral_airside_m(face, was_road[i], tree, air, weld_m,
                                        factor, cache, road_ctx)
            if shared < min_m:
                continue
            # §37 (2) A ROAD FLIPS BY SHARE, A LOT BY EDGE (owner RULINGS
            # 2026-09-13q KCLT item 7, over 13j item 7).  A STRIP-class
            # face — one born a road, a road BY EVIDENCE — is a LINE
            # through the airport, and a line that grazes an apron for a
            # few metres of a kilometre-long perimeter has not become
            # apron; the owner's 12c sentence is about a shape that SITS
            # against airside pavement.  So a road needs a SHARE of its
            # perimeter, not merely an edge.  Measured at KCLT: shapeID
            # 791 (`dsf:pol82`, 8.4 m wide, 575 m of road centreline, no
            # taxi centreline) flipped on 25.8 m of 1,203 m — 2.1 % — and
            # then stood +12.33 m off its ground under the apron's 1.5 %.
            # LEMD's 61 apron-side lanes run ALONGSIDE their apron (edges
            # to 828 m) and keep their flip.  A LOT is unchanged.
            if was_road[i] and shared < frac * per:
                continue
            final[i] = ["apron", ref, face, None,
                        dict(evid, kind="apron", airside_edge_m=shared,
                             airside_edge_flip=1.0,
                             airside_edge_round=float(rounds),
                             airside_edge_was=role), "apron"]
            moved += 1
        flipped += moved
        if moved == 0:
            return flipped, rounds
