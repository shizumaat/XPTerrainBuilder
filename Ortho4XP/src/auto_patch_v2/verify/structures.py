"""The STRUCTURE readers (M4) over the emitted product — the law family
``wall_in_runway_strip`` (registered in ``families.toml``) and the tunnel
ACCEPTANCE checks the oracle ``tools/tunnel_portal_acceptance.py``
adjudicates (``wall_top_flat``, ``ramp_wall_gap``, the canonical mouth
of RULINGS 2026-08-30, deck clearance), each as a pure function over
:class:`Patch` returning rows in the census row shape.  The acceptance
checks are NOT law families (the v1 register has none — the twin
``test_every_v1_family_has_a_v2_family`` holds the two registers equal)
and are published under their own ``tunnel_*`` keys beside the families.

Populations are the ORACLE's own: ramps are the ``tunnel_ramp`` ROLE,
walls the ``retaining_wall`` role carrying ref ``tunnel_wall`` exactly,
decks the ``bridge_deck:`` refs.
"""
from __future__ import annotations

import math

from ..constraints.geometry import principal_axis
from ..law.tables import zone2_half_width_m
from .frame import Patch, Row, Shape, row

__all__ = ["wall_in_runway_strip", "tunnel_wall_top_flat", "tunnel_ramp_wall_gap",
           "tunnel_mouth_canonical", "tunnel_deck_clearance", "ACCEPTANCE"]

_WALL_REF = "tunnel_wall"


def _ramps(p: Patch) -> list[Shape]:
    return [sh for sh in p.shapes if sh.role == "tunnel_ramp"]


def _walls(p: Patch) -> list[Shape]:
    return [sh for sh in p.shapes if sh.role == "retaining_wall" and sh.ref == _WALL_REF]


def _decks(p: Patch) -> list[Shape]:
    return [sh for sh in p.shapes if sh.ref.startswith("bridge_deck:")]


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _seg_dist(px: float, py: float, a: tuple[float, float], b: tuple[float, float]) -> float:
    vx, vy = b[0] - a[0], b[1] - a[1]
    l2 = vx * vx + vy * vy
    t = 0.0 if l2 < 1e-18 else max(0.0, min(1.0, ((px - a[0]) * vx + (py - a[1]) * vy) / l2))
    return math.hypot(px - (a[0] + t * vx), py - (a[1] + t * vy))


def _inside(px: float, py: float, ring) -> bool:
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / ((yj - yi) or 1e-18) + xi:
            inside = not inside
        j = i
    return inside


# ── the law family ───────────────────────────────────────────────────────

def wall_in_runway_strip(p: Patch) -> list[Row]:
    """Every ``retaining_wall`` vertex inside a runway-family ring's
    strip keep-out (``zones.adjacent_ground`` runway half width for the
    runway's code; RULINGS 2026-08-21d, ``retaining_wall.in_runway_strip
    = false``) is a row."""
    law = p.law
    runways = [sh for sh in p.shapes if sh.role in ("runway", "runway_crossing")]
    walls = [sh for sh in p.shapes if sh.role == "retaining_wall"]
    if not runways or not walls:
        return []
    out: list[Row] = []
    for w in walls:
        for k, (x, y) in enumerate(w.xy):
            for r in runways:
                hw = zone2_half_width_m(law, "runway", r.code_number, r.code_letter)
                if not hw:
                    continue
                if _inside(x, y, r.xy):
                    d = 0.0
                else:
                    n = len(r.xy)
                    d = min(_seg_dist(x, y, r.xy[i], r.xy[(i + 1) % n]) for i in range(n))
                if d <= hw:
                    out.append(row("wall_in_runway_strip", ("retaining_wall", r.role),
                                   "airside", hw - d, None, None, d, (x, y), (x, y),
                                   w.key, r.key, lat=p.ll[w.ids[k]][0], lon=p.ll[w.ids[k]][1]))
                    break
    return out


# ── the acceptance checks ────────────────────────────────────────────────

def tunnel_wall_top_flat(p: Patch) -> list[Row]:
    """§F1 / 2026-09-01c: two wall vertices closer than the band span in
    plan are ACROSS the band and carry one value; a pair differing by
    more than the materiality floor is a row (the oracle reports the
    worst delta; ``span`` is the oracle's ``wall_band_span_m`` = 2 m)."""
    span = 2.0
    # the reader's envelope is the rate readers' quantum
    # (``emit.instrument.coarse_noise_m``): the oracle REPORTS the worst
    # delta with no bar; a crest that follows the ground across two
    # stations differs by the ground's own slope over the span
    tol = p.law.tables.emit.instrument.coarse_noise_m
    out: list[Row] = []
    for w in _walls(p):
        pts = list({(w.xy[k], w.z[k], w.ids[k]) for k in range(len(w.ids))})
        for i in range(len(pts)):
            (a, za, ia) = pts[i]
            for j in range(i + 1, len(pts)):
                (b, zb, ib) = pts[j]
                if abs(a[0] - b[0]) > span or abs(a[1] - b[1]) > span or _dist(a, b) > span:
                    continue
                dz = abs(za - zb)
                if dz > tol + 1e-9:
                    out.append(row("tunnel_wall_top_flat", ("retaining_wall",) * 2, "airside",
                                   dz, None, None, _dist(a, b), a, b, w.key, w.key,
                                   lat=p.ll[ia][0], lon=p.ll[ia][1]))
    return out


def tunnel_ramp_wall_gap(p: Patch) -> list[Row]:
    """2026-08-28c item 1 / 2026-09-01c: the ramp is NOT welded to the
    wall — a vertex id shared between a ``tunnel_ramp`` ring and a
    ``tunnel_wall`` ring is a row."""
    out: list[Row] = []
    walls = _walls(p)
    wall_ids = {v: w for w in walls for v in w.ids}
    for r in _ramps(p):
        for k, v in enumerate(r.ids):
            w = wall_ids.get(v)
            if w is not None:
                out.append(row("tunnel_ramp_wall_gap", ("tunnel_ramp", "retaining_wall"),
                               "mixed", 0.0, None, None, 0.0, r.xy[k], r.xy[k], r.key, w.key,
                               lat=p.ll[v][0], lon=p.ll[v][1]))
    return out


def _ends(r: Shape) -> list[tuple[tuple[float, float], float]]:
    """The two ends of a ramp piece along its long axis: ``(centre,
    mean z)`` each."""
    n = len(r.xy)
    pa = principal_axis(list(r.xy))
    if pa is None:
        return [((r.xy[0][0], r.xy[0][1]), r.z[0])]
    a, b, _w = pa
    L = _dist(a, b) or 1.0
    ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
    st = [((x - a[0]) * ux + (y - a[1]) * uy) for x, y in r.xy]
    lo, hi = min(st), max(st)
    out = []
    for target in (lo, hi):
        ks = [k for k in range(n) if abs(st[k] - target) <= 2.0]
        out.append(((sum(r.xy[k][0] for k in ks) / len(ks), sum(r.xy[k][1] for k in ks) / len(ks)),
                    sum(r.z[k] for k in ks) / len(ks)))
    return out


def _mouth_end(r: Shape, others: list[Shape] = (), walls: list[Shape] = ()
               ) -> tuple[tuple[float, float], float]:
    """The ramp's mouth end: the end the wall's END CAP stands across —
    the end whose centre is nearest a wall edge (the cap at the gap; the
    open top end sees only the side bands, half a corridor away).  Not
    the lower end: where the ground beyond a mouth lies below the bore
    floor the ramp DESCENDS outward (the ±cap cone) and its low end is
    the top.  With no walls, the lower end; a piece flat at the datum
    (the covered stretch before a deck) takes the end no other ramp
    piece continues from."""
    ends = _ends(r)
    if len(ends) < 2:
        return ends[0]
    (pa, za), (pb, zb) = ends
    if walls:
        def near(pt):
            best = 1e9
            for w in walls:
                n = len(w.xy)
                for k in range(n):
                    best = min(best, _seg_dist(pt[0], pt[1], w.xy[k], w.xy[(k + 1) % n]))
            return best
        da, db = near(pa), near(pb)
        if abs(da - db) > 0.5:
            return (pa, za) if da < db else (pb, zb)
    if abs(za - zb) > 0.02:
        return (pa, za) if za < zb else (pb, zb)
    da = min((min(_dist(pa, q) for q in o.xy) for o in others), default=1e9)
    db = min((min(_dist(pb, q) for q in o.xy) for o in others), default=1e9)
    return (pa, za) if da >= db else (pb, zb)


def tunnel_mouth_canonical(p: Patch) -> list[Row]:
    """THE CANONICAL MOUTH (RULINGS 2026-08-30): per tunnel id (the ramp
    ref's ``tunnel_ramp:<id>``), ONE ramp piece reaches the mouth line
    (the lowest piece), ONE wall band answers it on BOTH sides and
    across the mouth (a wall vertex within ``wall_gap_m + wall_band_width_m
    + 1`` of the mouth edge's centre on the far side — the END CAP), and
    the mouth wall stands ``bore_datum_m`` above the mouth node
    (2026-09-03b).  Each miss is a row naming the tunnel."""
    tn = p.law.tables.structures.tunnel
    tol = p.law.tables.emit.materiality.elevation_m
    reach = tn.wall_gap_m + tn.wall_band_width_m + 1.0
    walls = _walls(p)
    out: list[Row] = []
    # sites: ramp pieces within the oracle's ``mouth_cluster_m`` (25 m)
    # of each other are one place a bore surfaces
    ramps_all = _ramps(p)
    parent = list(range(len(ramps_all)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(ramps_all)):
        for j in range(i + 1, len(ramps_all)):
            if min(_dist(a, b) for a in ramps_all[i].xy for b in ramps_all[j].xy) <= 25.0:
                parent[find(i)] = find(j)
    by_id: dict[str, list[Shape]] = {}
    for i, r in enumerate(ramps_all):
        by_id.setdefault(f"site{find(i)}", []).append(r)
    for tid, ramps in by_id.items():
        # the mouth piece: the one whose cap-side end is nearest a wall
        cand = [(r, _mouth_end(r, [o for o in ramps if o is not r], walls)) for r in ramps]
        low, (mouth, zmouth) = min(cand, key=lambda c: min(
            (_seg_dist(c[1][0][0], c[1][0][1], w.xy[k], w.xy[(k + 1) % len(w.xy)])
             for w in walls for k in range(len(w.xy))), default=1e9))
        # the END CAP: a wall EDGE within reach of the mouth line's centre
        # (the cap's vertices stand at the corners, its edge crosses the
        # centre); the wall pieces at the mouth are those with an edge
        # within the corridor's width of it
        near: list[tuple[Shape, int]] = []
        cap: list[tuple[Shape, int]] = []
        for w in walls:
            n = len(w.xy)
            for k in range(n):
                d = _seg_dist(mouth[0], mouth[1], w.xy[k], w.xy[(k + 1) % n])
                if d <= 2.0 * reach + 30.0:
                    near.append((w, k))
                    near.append((w, (k + 1) % n))
                if d <= reach + 1.0:
                    cap.append((w, k))
                    cap.append((w, (k + 1) % n))
        pieces = {w.key for w, _k in near}
        if not cap:
            out.append(row("tunnel_mouth_canonical", ("tunnel_ramp", "retaining_wall"), "mixed",
                           0.0, None, None, None, mouth, mouth, low.key, None,
                           out_of_scope=f"{tid}: no end cap across the mouth"))
            continue
        # the MOUTH WALL NODE stands bore_datum_m above the mouth node
        # (09-03b): the cap edge's value at the point nearest the mouth
        # line's centre, interpolated along that edge (the crest follows
        # the DEM ACROSS the cap — SPJC's cap spans 0.5 m of relief)
        want = zmouth + tn.bore_datum_m
        best = None
        for w, k in cap:
            n = len(w.xy)
            a, b = w.xy[k], w.xy[(k + 1) % n]
            d = _seg_dist(mouth[0], mouth[1], a, b)
            if best is None or d < best[0]:
                vx, vy = b[0] - a[0], b[1] - a[1]
                l2 = vx * vx + vy * vy
                t = 0.0 if l2 < 1e-18 else max(0.0, min(1.0, ((mouth[0] - a[0]) * vx
                                                              + (mouth[1] - a[1]) * vy) / l2))
                best = (d, w.z[k] * (1 - t) + w.z[(k + 1) % n] * t)
        worst = abs(best[1] - want) if best else 0.0
        # the instrument envelope: the rate readers' quantum (the mouth
        # centre is a cluster mean; the cap crest is interpolated)
        if worst > p.law.tables.emit.instrument.coarse_noise_m:
            out.append(row("tunnel_mouth_canonical", ("tunnel_ramp", "retaining_wall"), "mixed",
                           worst, None, None, None, mouth, mouth, low.key, cap[0][0].key,
                           out_of_scope=f"{tid}: mouth wall {best[1]:.2f} vs ramp mouth "
                                        f"{zmouth:.2f} + {tn.bore_datum_m}"))
        if len(pieces) > 1:
            out.append(row("tunnel_mouth_canonical", ("retaining_wall",) * 2, "airside",
                           float(len(pieces)), None, None, None, mouth, mouth, low.key, None,
                           out_of_scope=f"{tid}: {len(pieces)} wall pieces at the mouth"))
        at_mouth = [r for r in ramps
                    if _dist(_mouth_end(r, [o for o in ramps if o is not r], walls)[0],
                             mouth) <= 25.0]
        if len(at_mouth) > 1:
            out.append(row("tunnel_mouth_canonical", ("tunnel_ramp",) * 2, "groundside",
                           float(len(at_mouth)), None, None, None, mouth, mouth, low.key, None,
                           out_of_scope=f"{tid}: {len(at_mouth)} ramp pieces at the mouth"))
    return out


def tunnel_deck_clearance(p: Patch) -> list[Row]:
    """2026-08-30c §4 / 08-30f: a deck stands ``bridge.clearance_m`` above
    the ramp abutting it — the lowest deck vertex vs the highest ramp
    vertex within the gap + 2 m of the deck ring."""
    br = p.law.tables.structures.bridge
    gap = p.law.tables.structures.tunnel.wall_gap_m
    tol = p.law.tables.emit.materiality.elevation_m
    out: list[Row] = []
    ramps = _ramps(p)
    for d in _decks(p):
        n = len(d.xy)
        zs = []
        for r in ramps:
            for k in range(len(r.ids)):
                x, y = r.xy[k]
                if min(_seg_dist(x, y, d.xy[i], d.xy[(i + 1) % n]) for i in range(n)) <= gap + 2.0:
                    zs.append(r.z[k])
        if not zs:
            continue
        clear = min(d.z) - max(zs)
        if clear < br.clearance_m - tol:
            out.append(row("tunnel_deck_clearance", ("service_road", "tunnel_ramp"), "groundside",
                           br.clearance_m - clear, None, None, None, d.xy[0], d.xy[0], d.key, None,
                           out_of_scope=f"{d.ref}: clearance {clear:.2f} < {br.clearance_m}"))
    return out


#: The acceptance readers, keyed as the census publishes them.
ACCEPTANCE = {
    "tunnel_wall_top_flat": tunnel_wall_top_flat,
    "tunnel_ramp_wall_gap": tunnel_ramp_wall_gap,
    "tunnel_mouth_canonical": tunnel_mouth_canonical,
    "tunnel_deck_clearance": tunnel_deck_clearance,
}
