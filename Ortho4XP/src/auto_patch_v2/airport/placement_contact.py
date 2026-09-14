"""§16g (1)/(7) THE CONTACT RELATION — the ONE predicate a unit chains on
(spec ``object-placement-spec.md`` §16f (1)(b), §16g (1), §16g (7) (1)).

Lifted out of ``placement_family`` for the 1,000-line law when §16g (7)
added the footprint polygon (owner RULINGS 2026-09-14c item 1, attributed
14g).  Three readings of ONE question — *do these two bodies touch at*
``footprint_touch_m``? — kept together so they cannot drift apart:

* :func:`boxes_touch` — the PART-BOX reading, which is what §16g chained
  on until 14g measured what it costs: a rotated building's lat/lon box
  overlaps a neighbour whose FOOTPRINT is 3.5-20 m away, and that chain
  gave 1,509 HECA bodies a rail deck's datum.  It stays as the cheap
  SUPERSET filter — a part's box contains its ring, so polygon-touch
  implies box-touch — and as the reading for a plan written before the
  ring field.
* :func:`rings_touch` — §16g (7) (1)'s FOOTPRINT POLYGON reading, asked
  only of the pairs the boxes admit.
* :func:`_clusters` — the transitive chaining both readings feed.
"""
from __future__ import annotations

import math as _math
import typing as _t

from . import anchor_rule as _ar
from . import placement_boxes as _pb

__all__ = ["boxes_touch", "rings_touch", "ring_metres",
           "m_per_deg_exact", "FAMILY_MIN_MEMBERS"]

#: §16f (1): two bodies of ONE member are not a family by themselves.
FAMILY_MIN_MEMBERS = 2


#: :func:`boxes_touch` answers a small pair by the plain product — the
#: filtering and sorting cost more than the comparisons below this many.
_PAIR_PRODUCT_MAX = 4096


def m_per_deg_exact(lat: float) -> tuple[float, float]:
    """``(metres per degree of latitude, of longitude)`` at ``lat``,
    computed and NOT memoised.

    ``anchor_rule._m_per_deg`` buckets on ``int(lat * 1e4)``, so whoever
    calls it FIRST inside a bucket fixes the value every later caller
    sees — this lane measured the consequence in round 1 (a ring node at
    exactly 50 m of longitude reads 50.00000000000935 cold and
    49.99999999998842 once the bucket was warmed at 40.00009 N, and
    `test_a_basin_wall_follows_its_ring_...` flips).  §16g (7)'s scaling
    is wanted ONCE per cluster, so the memo buys nothing here and taking
    it would make this law an order-dependence for every reader after
    it.  The memo's own defect is NAMED, not fixed here: it is another
    law's instrument."""
    r = _math.radians(lat)
    return (111_132.954 - 559.822 * _math.cos(2 * r) + 1.175 * _math.cos(4 * r),
            111_412.84 * _math.cos(r) - 93.5 * _math.cos(3 * r))


def ring_metres(ring, ml: float, mo: float):
    """A ``(lat, lon)`` footprint ring in METRES with its own BOX:
    ``(vertices, (x0, y0, x1, y1))``.

    One scaling for the whole airport (a single reference latitude),
    because a contact at 0.5 m cannot care about the 1e-5 m/deg the
    latitude carries across a few kilometres.  The BOX is the reject that
    makes the law affordable: a body is a SET of component rings, so
    ``_polys_touch`` is a ring x ring product, and at HECA the bare
    product cost the pass 104 s against 6.5 (measured).  A ring lies
    inside its own box, so a box pair further apart than the tolerance
    cannot touch."""
    vs = [(a * ml, b * mo) for a, b in ring]
    xs = [v[0] for v in vs]
    ys = [v[1] for v in vs]
    n = len(vs)
    edges = [(vs[i], vs[(i + 1) % n]) for i in range(n)]
    return (vs, (min(xs), min(ys), max(xs), max(ys)), edges)


def _seg_gap2(p, q, r, t) -> float:
    """Squared distance between segments ``pq`` and ``rt`` (metres)."""
    ux, uy = q[0] - p[0], q[1] - p[1]
    vx, vy = t[0] - r[0], t[1] - r[1]
    wx, wy = p[0] - r[0], p[1] - r[1]
    a = ux * ux + uy * uy
    b = ux * vx + uy * vy
    c = vx * vx + vy * vy
    d = ux * wx + uy * wy
    e = vx * wx + vy * wy
    den = a * c - b * b
    if den > 1e-18:
        sN = max(0.0, min(1.0, (b * e - c * d) / den))
    else:
        sN = 0.0
    tN = (b * sN + e) / c if c > 1e-18 else 0.0
    if tN < 0.0:
        tN = 0.0
        sN = max(0.0, min(1.0, -d / a)) if a > 1e-18 else 0.0
    elif tN > 1.0:
        tN = 1.0
        sN = max(0.0, min(1.0, (b - d) / a)) if a > 1e-18 else 0.0
    dx = wx + sN * ux - tN * vx
    dy = wy + sN * uy - tN * vy
    return dx * dx + dy * dy


def _inside(ring, x: float, y: float) -> bool:
    n = len(ring)
    hit = False
    j = n - 1
    for i in range(n):
        ai, aj = ring[i], ring[j]
        if (ai[1] > y) != (aj[1] > y):
            xx = ai[0] + (y - ai[1]) * (aj[0] - ai[0]) / (aj[1] - ai[1])
            if x < xx:
                hit = not hit
        j = i
    return hit


def _box_apart(a, b, eps_m: float) -> bool:
    return (a[0] - b[2] > eps_m or b[0] - a[2] > eps_m
            or a[1] - b[3] > eps_m or b[1] - a[3] > eps_m)


def rings_touch(ra, rb, eps_m: float) -> bool:
    """§16g (7) (1): do these two FOOTPRINT POLYGONS touch or come within
    ``eps_m``?  Each ring is ``(vertices, edges)`` in metres — the edges
    precomputed by :func:`ring_metres`, because this loop runs millions
    of times and the modulo indexing was a measurable share of it.

    Edge-to-edge distance plus a containment test, which is the whole
    relation for two simple rings: either an edge pair is within the
    tolerance, or one ring lies wholly inside the other.  Asked only of
    the pairs :func:`boxes_touch` already admitted, so the ring counts are
    small (``contact.FOOTPRINT_RING_MAX`` is 16) and the loop is bounded
    at 256 segment pairs."""
    if not ra or not rb:
        return True                    # no ring: the box reading stands
    e2 = eps_m * eps_m
    va, ea = ra
    vb, eb = rb
    gap = _seg_gap2
    for p, q in ea:
        for r, t in eb:
            if gap(p, q, r, t) <= e2:
                return True
    return (_inside(vb, va[0][0], va[0][1])
            or _inside(va, vb[0][0], vb[0][1]))


def boxes_touch(ba: _t.Sequence[tuple[float, float, float, float]],
                bb: _t.Sequence[tuple[float, float, float, float]],
                ha: tuple[float, float, float, float],
                hb: tuple[float, float, float, float],
                eps_m: float) -> bool:
    """Does ANY box of ``ba`` come within ``eps_m`` of any box of ``bb``?
    The one contact predicate §16f (1)(b) and §16g (1)/(6) are stated in
    — read by :func:`_clusters`'s ``_bind`` and by §16g (6)'s contact
    graph, so the unit partition and the connector topology can never be
    two different relations.

    THE PLAIN PRODUCT IS THE WRONG SHAPE FOR A CLUTTER BODY (RULINGS
    2026-09-14b measured the pairing at 27.2 s of OTHH's ``plan_clusters``
    over 24.2 M pairs; OTHH's fattest body carries **1,885 boxes**, so one
    unlucky pair is 3.5 M comparisons).  Two exact reductions, in order:
    the boxes of each side that cannot reach the OTHER SIDE'S HULL are
    dropped first (a box that touches some ``y`` is necessarily within
    ``eps_m`` of ``hb``), and what survives is walked as a LATITUDE SWEEP
    — both sides sorted by their south edge once, a moving window of the
    ``bb`` boxes whose latitude span can still reach the current ``ba``
    box — instead of the full product.  The answer is the product's, to
    the bit: the same predicate on the same pairs, with the pairs that
    cannot satisfy it never asked."""
    if not ba or not bb:
        return False
    if len(ba) * len(bb) <= _PAIR_PRODUCT_MAX:
        return any(_pb.box_gap_m(x, y) <= eps_m for x in ba for y in bb)
    xs = [x for x in ba if _pb.box_gap_m(x, hb) <= eps_m]
    if not xs:
        return False
    ys = [y for y in bb if _pb.box_gap_m(y, ha) <= eps_m]
    if not ys:
        return False
    if len(xs) * len(ys) <= _PAIR_PRODUCT_MAX:
        return any(_pb.box_gap_m(x, y) <= eps_m for x in xs for y in ys)
    slack = eps_m / 111_132.0
    xs.sort(key=lambda b: b[0])
    ys.sort(key=lambda b: b[0])
    n = len(ys)
    lo = 0
    live: list = []
    for x in xs:
        south, north = x[0] - slack, x[2] + slack
        while lo < n and ys[lo][0] <= north:
            live.append(ys[lo])
            lo += 1
        if live and live[0][2] < south:
            live = [y for y in live if y[2] >= south]
        for y in live:
            if y[0] <= north and _pb.box_gap_m(x, y) <= eps_m:
                return True
    return False


def _polys_touch(ra, rb, eps_m: float) -> bool:
    """§16g (7) (1) over two BODIES, each a set of component rings: they
    touch when any ring of one reaches any ring of the other.  A body
    with no ring at all falls back to the box verdict its caller already
    has."""
    if not ra or not rb:
        return True
    for vx, bx, ex in ra:
        for vy, by, ey in rb:
            if (not _box_apart(bx, by, eps_m)
                    and rings_touch((vx, ex), (vy, ey), eps_m)):
                return True
    return False


def _clusters(cands: _t.Sequence[_t.Any], eps_m: float,
              min_members: int = FAMILY_MIN_MEMBERS,
              counts: "dict | None" = None
              ) -> "tuple[list[list[int]], dict[int, set[int]]]":
    """§16f (1)(b): the unit's footed bodies grouped into CONNECTED PLAN
    CLUSTERS — two bodies are in contact where any pair of their PART
    boxes overlaps or comes within ``eps_m``.

    READ AT THE BODY, NOT AT THE WHOLE MEMBER (measured, round 1): a
    member-level reading joins a member to a family on ONE touching box
    and then drags every body of it onto the family's plane — KCLT's
    `Charlotte_Airport_002_ALB__b7` stands 500 m out on the apron and
    came out 216.89 m under its own ground, and the file count went
    477 -> 708.  §16f (2)'s own sentence is the body's: "a member whose
    FOOTPRINT stands apart ... is NOT in the family and is cut to its own
    ground".  The family is then the set of MEMBERS represented in the
    cluster, which is what the census prints.

    The PART boxes, not the body hull, for §14 (3)'s own reason: a hull
    read two L-shaped wings of a terminal 100 m apart as overlapping.

    A LINE SEGMENT and a BASIN never join a family — the one is apart in
    plan by construction (§11f (2) cut it so it could read its own
    terrain) and the other's zero is its RIM (§14 (2))."""
    live = [i for i, c in enumerate(cands)
            if c.body_class not in (_ar.LINE_SEGMENT, _ar.BASIN)
            and (c.part_boxes or c.box)]
    adj: dict[int, set[int]] = {}
    if len(live) < 2:
        return [], adj
    boxes = {i: (list(cands[i].part_boxes) or [cands[i].box]) for i in live}
    hull = {i: _pb.hull_of(boxes[i]) for i in live}
    live = [i for i in live if hull[i] is not None]
    # §16g (7) (1) (owner RULINGS 2026-09-14c item 1): THE FOOTPRINT
    # POLYGON is what chains, and the boxes are only its cheap superset.
    # A candidate that publishes no ring (a plan written before the
    # field, or a degenerate hull) keeps the box reading and is COUNTED
    # so a stale frame is never mistaken for a law-true read.
    ml, mo = m_per_deg_exact(hull[live[0]][0] if live else 0.0)
    rings: dict[int, list] = {}
    no_ring = 0
    for i in live:
        rr = getattr(cands[i], "rings", None)
        if rr:
            rings[i] = [ring_metres(r, ml, mo) for r in rr if len(r) >= 3]
        if not rings.get(i):
            no_ring += 1
    if counts is not None:
        counts["unit_chain_bodies"] = counts.get("unit_chain_bodies", 0) + len(live)
        counts["unit_chain_no_polygon"] = \
            counts.get("unit_chain_no_polygon", 0) + no_ring
    parent = {i: i for i in live}

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    # the body HULL is the cheap reject, then the part-by-part scan —
    # ordered by the hull's south edge so the sweep stops (§14 (3)'s own
    # shape; OTHH's clutter members are thousands of boxes each)
    order = sorted(live, key=lambda i: hull[i][0])
    # THE SWEEP CARRIES THE TOLERANCE.  At §16f's millimetres the slack
    # rounds away; at §16g's ``footprint_touch_m`` (0.5 m) it does not,
    # and without it the sweep BREAKS on the very pair the law binds — a
    # pier 0.3 m north of its deck starts past the deck's north edge
    # (measured, the §16g twin).
    _slack = eps_m / 111_132.0

    def _bind(a: int, b: int) -> None:
        if find(a) == find(b) or _pb.box_gap_m(hull[a], hull[b]) > eps_m:
            return
        if (boxes_touch(boxes[a], boxes[b], hull[a], hull[b], eps_m)
                and _polys_touch(rings.get(a), rings.get(b), eps_m)):
            parent[find(a)] = find(b)
            # §16f (4): the CONTACT EDGES are kept — a member on no
            # pad joins the pad group it TOUCHES, and that needs the
            # graph, not just its components
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)

    # THE GRID WAS TRIED AND REFUTED (§16g (1), lane v2clusterpad round 2).
    # The plan-wide reading is slow — OTHH's ``plan_units`` reads 485.7 s —
    # and the sweep below looked like the cause, so the hulls were bucketed
    # into a plan grid (each grown by ``eps_m``, so a pair within the
    # tolerance necessarily shares a cell).  MEASURED at OTHH: grid 557.5 s
    # against the sweep's 485.7 s for IDENTICAL clusters (185 either way) —
    # the cost is not the pairing.  THE ATTRIBUTION THAT FOLLOWED IT WAS
    # WRONG (scout `v2partcost`, RULINGS 2026-09-14b): it blamed
    # ``bodies_of_plan`` and the PART-BOX product inside ``_bind``, and a
    # cProfile of the whole ``plan_clusters`` on the registered OTHH
    # capture reads ``bodies_of_plan`` at **0.43 s** and this pairing
    # sweep (``_clusters`` + ``_bind`` + ``box_gap_m``, 24.2 M pairs) at
    # **27.2 s** of 324 — the other 295 s were ``union_area_m2``'s
    # per-slab re-scan, fixed there.  The grid stays DELETED.
    for ai, a in enumerate(order):
        north = hull[a][2] + _slack
        for b in order[ai + 1:]:
            if hull[b][0] > north:
                break
            _bind(a, b)
    out: dict[int, list[int]] = {}
    for i in live:
        out.setdefault(find(i), []).append(i)
    # a cluster is a FAMILY only where it spans more than one MEMBER:
    # one member's own bodies are already one object to §14 (3) / §16c
    return ([sorted(v) for _k, v in sorted(out.items(),
                                           key=lambda kv: min(kv[1]))
             if (len(v) >= 2 if min_members <= 1
                 else len({cands[i].member for i in v}) >= min_members)], adj)
