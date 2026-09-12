"""THE CARRIER (spec ``object-placement-spec.md`` §13 / §14; owner
RULINGS 2026-09-11s / 11v).

A FOOTLESS body has no ground to meet.  Written alone it is shifted onto
the ground (LEMD's footbridge deck, 0.03 m under the road it crosses);
kept whole it drapes at the shared DATUM point, 15.7 m under its own
building.  Neither is the authoring, and neither is a reading of the
terrain — there is no terrain under a deck.

So a footless body takes SOMEBODY ELSE'S reading: its CARRIER's.  The
carrier is the footed body it stands on, abuts, or is nearest to, and the
footless body is written as a body file AT THE CARRIER'S ANCHOR WITH THE
CARRIER'S ``y_zero`` — one zero plane for the two of them, which is what
"the deck stays at the kerb" means when the kerb is the only thing either
of them can read.  The carrier search is over the UNIT (the members of
one shared-datum row), because that is the scope the pack authored them
in: 171 of LEMD's resources share ``OBJECT 293 -3.564788 40.492764`` and
one flat plane.

This module holds the three §14 rules that are not about one body's own
geometry — the carrier search, the plan-overlap binding, and §9's
coarsening the two of them feed — so that ``placement_plan`` stays the
orchestration and stays under the 1,000-line law.

NO LAW CONSTANT LIVES HERE.  ``elevated_base_m`` and ``split_tol_m`` are
passed in by the caller from ``[rebake]`` / ``[placement]``.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from . import anchor_rule as _ar

__all__ = ["is_elevated", "coarsen", "bind_plan_overlaps", "Candidate",
           "carrier_for", "unit_edges", "box_of", "overlap", "overlap_m2",
           "re_cut_by_terrain", "hull_of", "stands_over_rank", "foot_boxes",
           "fill_of", "parts_overlap", "ground_at_box", "ground_under",
           "ground_samples", "box_area_m2",
           "census_v16", "census_v16_lines", "census_population",
           "census_population_lines", "census_v14", "census_v14_lines",
           "census_v15", "census_v15_lines", "STANDS_OVER_TOL_M",
           "merge_rides", "cut_order", "group_at_zero", "senior_of",
           "FOOTLESS_KEPT", "KEPT_FOOTLESS", "KEPT_NO_CARRIER", "OWN_GROUND",
           "THICKNESS_SKIP", "LAWFUL_SKIPS", "_v15_rows"]

# THE INSTRUMENTS LIVE NEXT DOOR (``placement_census``) and are re-exported
# here: every caller — both tools and the twins — reads them as this
# module's, and the 1,000-line law is what moved them, not a second home
# for the reading.  One implementation, one import surface.


# ── plan boxes ───────────────────────────────────────────────────────────

def hull_of(boxes: _t.Iterable[tuple[float, float, float, float]]
            ) -> tuple[float, float, float, float] | None:
    """The bounding box of ``boxes``, or ``None`` when there are none."""
    bs = list(boxes)
    if not bs:
        return None
    return (min(b[0] for b in bs), min(b[1] for b in bs),
            max(b[2] for b in bs), max(b[3] for b in bs))


def box_of(feet: _t.Sequence[tuple[float, float, float]],
           parts: _t.Sequence[_t.Any]) -> tuple[float, float, float, float]:
    """A body's PLAN box ``(lat0, lon0, lat1, lon1)`` — from its own feet
    when it has them (a SEGMENT's box is its segment's, not its parent
    line's), else from its parts' boxes."""
    if feet:
        las = [f[0] for f in feet]
        los = [f[1] for f in feet]
        return (min(las), min(los), max(las), max(los))
    return (min(p.box[0] for p in parts), min(p.box[1] for p in parts),
            max(p.box[2] for p in parts), max(p.box[3] for p in parts))


def overlap(a: tuple[float, float, float, float],
            b: tuple[float, float, float, float]) -> float:
    """The plan overlap AREA of two boxes in square degrees (a monotone
    stand-in for square metres inside one placement)."""
    dla = min(a[2], b[2]) - max(a[0], b[0])
    dlo = min(a[3], b[3]) - max(a[1], b[1])
    return dla * dlo if dla > 0.0 and dlo > 0.0 else 0.0


def box_area_m2(b: tuple[float, float, float, float]) -> float:
    """One plan box's area in square metres."""
    ml, mo = _ar._m_per_deg(0.5 * (b[0] + b[2]))
    return max(0.0, (b[2] - b[0]) * ml) * max(0.0, (b[3] - b[1]) * mo)


def fill_of(box: tuple[float, float, float, float] | None,
            part_boxes: _t.Sequence[tuple[float, float, float, float]]) -> float:
    """§16 (3): the FOOTPRINT FILL of a body — the area its PART boxes
    cover over the area of its own plan box, capped at 1.

    This is what separates a SOLID from a line: a wall ring or a building
    fills 0.3-1.0 of its box, while a 2 km fence segment, a grass strip
    and a taxi sign fill a few thousandths of theirs.  Overlapping parts
    are counted twice, which can only push a candidate ABOVE the bar —
    the test is a floor, so the error is on the side of admitting a
    genuine solid, never of admitting a line."""
    if not box or not part_boxes:
        return 0.0
    area = box_area_m2(box)
    if area <= 0.0:
        return 1.0                      # a degenerate box is its own fill
    return min(1.0, sum(box_area_m2(b) for b in part_boxes) / area)


#: §16 (3): how many PART boxes stand for a body's footprint in the
#: stands-over relation — its largest, by area.  The law and the census
#: read the SAME bounded set (the plan publishes it per body), because a
#: relation measured on one geometry by the law and another by the
#: instrument counts the disagreement rather than the defect; and a plan
#: carrying every part box of every body (LEMD: 29,402 parts) doubles its
#: own size for a refinement the tail of the list never changes.
FOOT_BOXES_MAX = 8


def foot_boxes(part_boxes: _t.Sequence[tuple[float, float, float, float]],
               cap: int = FOOT_BOXES_MAX
               ) -> tuple[tuple[float, float, float, float], ...]:
    """The ``cap`` largest of ``part_boxes`` (:data:`FOOT_BOXES_MAX`), in
    the order given — a body's footprint, bounded."""
    bs = list(part_boxes)
    if len(bs) <= cap:
        return tuple(bs)
    keep = sorted(range(len(bs)), key=lambda i: -box_area_m2(bs[i]))[:cap]
    return tuple(bs[i] for i in sorted(keep))


def parts_overlap(a: _t.Sequence[tuple[float, float, float, float]],
                  b: _t.Sequence[tuple[float, float, float, float]]) -> float:
    """§16 (3): STANDS-OVER IS PARTS-HULL OVERLAP, not box overlap — the
    overlap of the two bodies' PART boxes, summed pairwise (square
    degrees, the same monotone unit :func:`overlap` speaks).

    A body's hull box is a crude proxy for its footprint: LEMD's
    ``LEMDzaun__b5``, a fence segment, has a box that CONTAINS the garage
    roof and a footprint that touches none of it (11ai (C)).  Pairwise
    summation double-counts parts that overlap each other, which can only
    raise a candidate that genuinely stands under the body."""
    return sum(overlap(p, q) for p in a for q in b)


def ground_at_box(surface: _t.Callable[[float, float], "float | None"],
                  box: tuple[float, float, float, float] | None) -> float | None:
    """§16 (2)/(3): THE GROUND UNDER A BODY'S OWN GEOMETRY — the design
    surface at the centre of the body's plan box, else at whichever of
    its corners reads.  ONE point, read the same way by the law (which
    refuses a carrier standing far from it) and by the census (which
    prints ``zero - ground_under_geometry``); a second rule here would be
    the census-wrapper defect."""
    if not box or surface is None:
        return None
    pts = [(0.5 * (box[0] + box[2]), 0.5 * (box[1] + box[3])),
           (box[0], box[1]), (box[0], box[3]), (box[2], box[1]), (box[2], box[3])]
    for la, lo in pts:
        z = surface(la, lo)
        if z is not None:
            return float(z)
    return None


def ground_samples(surface: _t.Callable[[float, float], "float | None"],
                   boxes: _t.Sequence[tuple[float, float, float, float]] = (),
                   box: tuple[float, float, float, float] | None = None
                   ) -> list[float]:
    """§16 (2): the design surface UNDER A BODY'S OWN GEOMETRY, sampled at
    the centre of each of its FOOTPRINT boxes (``foot_boxes``) — else, for
    a body that publishes none, at the centre and corners of its plan box.

    A body's box centre is not its geometry: an L-shaped terminal's centre
    stands in the yard between its wings, and a re-cut roof's centre can
    fall on the taxiway 8 m below it.  The parts are where the body
    actually is.  ONE sampler, read the same way by the law (which refuses
    a carrier standing far from this ground) and by the census."""
    if surface is None:
        return []
    pts: list[tuple[float, float]] = [(0.5 * (b[0] + b[2]), 0.5 * (b[1] + b[3]))
                                      for b in boxes]
    if not pts and box:
        pts = [(0.5 * (box[0] + box[2]), 0.5 * (box[1] + box[3])),
               (box[0], box[1]), (box[0], box[3]), (box[2], box[1]), (box[2], box[3])]
    out = []
    for la, lo in pts:
        z = surface(la, lo)
        if z is not None:
            out.append(float(z))
    return out


def ground_under(surface: _t.Callable[[float, float], "float | None"],
                 boxes: _t.Sequence[tuple[float, float, float, float]] = (),
                 box: tuple[float, float, float, float] | None = None
                 ) -> float | None:
    """THE ground under a body: the MEDIAN of :func:`ground_samples` (a
    median, because one part hanging over a ditch is not the ground the
    body stands on).  ``None`` where nothing reads."""
    zs = sorted(ground_samples(surface, boxes, box))
    return None if not zs else zs[len(zs) // 2]


#: §16a (2): how many of a body's own FEET the mis-anchoring test reads.
#: A terminal publishes 132 of them and the answer is a MEDIAN; the
#: sampling resolution costs nothing the reading needs (LEMD publishes
#: 82k feet over the airport, and reading every one of them put 0.6 s in
#: the plan stage for a number that did not move).
GROUND_OFF_FEET_MAX = 32


def anchor_ground_off(anchor: _ar.Anchor,
                      feet: _t.Sequence[tuple[float, float, float]],
                      surface: _t.Callable[[float, float], "float | None"]
                      ) -> float | None:
    """§16a (2): IS THIS BODY MIS-ANCHORED — how far its own zero stands
    from the ground under its OWN FEET.

    The ground under a foot is not the surface there: the foot stands at
    its own authored height ``y`` above the body's zero plane, so what
    the ground under it SAYS the body's zero is, is
    ``surface(foot) - y_foot``.  (§7's float per foot is exactly this
    minus the body's zero.)  Reading the raw surface instead makes every
    building on a slope look mis-anchored — measured at LEMD: 313 of the
    airport's footed bodies refused as carriers, and the roofs over them
    then rode whatever came next, 49 of them more than 0.5 m off the
    walls they stand on.

    The MEDIAN over the feet, because one foot hanging over a ditch is
    not the body's anchoring.  ``None`` where nothing reads: no reading
    is no evidence that the body is wrong."""
    if anchor.surface_z is None or not feet:
        return None
    zero = float(anchor.surface_z) - float(anchor.y_zero)
    step = max(1, len(feet) // GROUND_OFF_FEET_MAX)
    zs = []
    for f in feet[::step]:
        z = surface(f[0], f[1])
        if z is not None:
            zs.append(float(z) - float(f[2]))
    if not zs:
        return None
    zs.sort()
    return abs(zs[len(zs) // 2] - zero)


def stands_over_rank(box: tuple[float, float, float, float],
                     other: tuple[float, float, float, float],
                     boxes: _t.Sequence[tuple[float, float, float, float]] = (),
                     other_boxes: _t.Sequence[tuple[float, float, float, float]] = (),
                     ) -> tuple[float, float]:
    """The ranking key for "does this body stand over that one" — the
    plan OVERLAP first, the tighter box second.

    The second half is not decoration.  A body wholly inside several
    large boxes ties on overlap at its own area, and LEMD has plenty of
    them: a 4.5 km grass line segment's station box and a taxi-sign
    body's box both contain the whole T4S roof, so the winner was
    whichever the enumeration reached first — and the law and the census
    enumerate in different orders, which made 11 bodies "float" on
    nothing but that.  Of two bodies that both cover this one, the
    SMALLER is what it stands on.

    §16 (3): where both bodies' PART boxes are given the overlap is
    measured between those (:func:`parts_overlap`) — the hull boxes then
    serve only as the cheap reject, because two hulls that miss cannot
    have a part pair that meets."""
    ov = overlap(box, other)
    if ov <= 0.0:
        return (0.0, 0.0)
    if boxes and other_boxes:
        ov = parts_overlap(boxes, other_boxes)
        if ov <= 0.0:
            return (0.0, 0.0)
    return (ov, -abs((other[2] - other[0]) * (other[3] - other[1])))


def overlap_m2(a: tuple[float, float, float, float],
               b: tuple[float, float, float, float]) -> float:
    """:func:`overlap` in SQUARE METRES — square degrees are a monotone
    stand-in for the comparison, but the REPORT says how much of one
    body stands over the other, and that is read in metres."""
    ov = overlap(a, b)
    if ov <= 0.0:
        return 0.0
    ml, mo = _ar._m_per_deg(0.5 * (a[0] + a[2]))
    return ov * ml * mo


# ── §13 (1): is this body's file standing on the ground at all? ──────────

def is_elevated(base_y_min: float, anchor: _ar.Anchor,
                elevated_base_m: float) -> bool:
    """§13 (1): is this body ELEVATED — is its file's intended zero
    something other than the ground?

    Two readings of ONE sentence ("a body is a candidate for its own file
    only if its lowest vertex is a ground contact of the object"), and a
    body fails it either way:

    * its LOWEST AUTHORED VERTEX stands above ``elevated_base_m`` — a
      roof, a deck, a tower part welded to nothing below it;
    * or the anchor the generic rule chose for it carries a ``y_zero``
      above ``elevated_base_m``.  This is the same sentence read on the
      anchor the FILE actually takes: a body welded out of a ground floor
      AND a roof has a low vertex, but ``anchor_for``'s median zero plane
      can land on the roof (measured at LEMD: ``Munoza-rada`` b1,
      ``y_zero`` +32.73, its feet censused 34 m off — the owner's 11r
      read).  Either way the file would be written so that a vertex tens
      of metres up lands on the terrain.

    Below the zero plane is LAWFUL and never elevated: basins, skirts and
    foundations are authored down, and 10ba/10ag put them there on
    purpose.  ``elevated_base_m <= 0`` disarms the law (round-one
    reading)."""
    if elevated_base_m <= 0.0:
        return False
    return bool(base_y_min > elevated_base_m or anchor.y_zero > elevated_base_m)


# ── §9 (1) + §13 (1): the coarsening ─────────────────────────────────────

def coarsen(bodies: _t.Sequence[tuple[int, _ar.Anchor, int]], tol_m: float,
            elevated: _t.AbstractSet[int] = frozenset(),
            boxes: _t.Sequence[tuple[float, float, float, float]] | None = None,
            *, attach_elevated: bool = True) -> list[list[int]]:
    """BODY COARSENING (owner RULINGS 2026-09-11e (1); spec §9).

    ``bodies`` are ``(body index, its anchor, its ground-contact vertex
    count)``; the answer is the groups of indices that become ONE file.
    Two bodies of the same placement are one file when their INTENDED-ZERO
    TERRAIN HEIGHTS — the design surface at each body's anchor minus its
    ``y_zero``, i.e. each body's own zero plane in world height — agree
    within ``tol_m``: a split exists only where the terrain DIFFERS under
    the object.  The group is anchored by its SENIOR body (the most
    ground-contact vertices; ties by body order), and the walk is
    senior-first so that "agree" is always measured against the anchor the
    group will actually take — never a chain of pairwise steps that lets a
    group span many times the tolerance.

    A body whose surface reads NOWHERE has no zero plane to compare: all
    of a placement's off-surface bodies are ONE group (no reading is no
    evidence that the terrain differs).  ``tol_m <= 0`` restores round
    one's reading: one file per body.

    ``elevated`` are the bodies standing wholly above
    ``[rebake] elevated_base_m``.  §13 (1): an elevated body is NEVER a
    file of its own, whatever the coarsening says, and it joins its
    CARRIER — the ground body of the same placement with the largest PLAN
    OVERLAP (``boxes``, one per body), else the nearest ground body in
    plan.  Where EVERY body is elevated there is no carrier HERE and the
    caller (:func:`placement_plan.build_splits`) takes the placement to
    the UNIT's carrier search (§14 (1)) before it ever gets here; the
    one-group answer below is the degenerate case a twin still asks for.
    """
    ground = [i for i in range(len(bodies)) if i not in elevated]
    if not ground:
        # §14 (1): no ground body in the placement — the UNIT carries it
        if attach_elevated:
            return [list(range(len(bodies)))] if bodies else []
        return []
    order = sorted(ground, key=lambda i: (-bodies[i][2], bodies[i][0]))
    groups: list[list[int]] = []
    zeros: list[float | None] = []
    for i in order:
        _bi, a, _n = bodies[i]
        z = None if a.surface_z is None else float(a.surface_z) - float(a.y_zero)
        placed = False
        if tol_m > 0.0:
            for gi, g0 in enumerate(zeros):
                if (z is None) == (g0 is None) and (
                        z is None or abs(z - g0) <= tol_m):
                    groups[gi].append(i)
                    placed = True
                    break
        elif z is None:
            # no tolerance at all: only the off-surface bodies still merge
            for gi, g0 in enumerate(zeros):
                if g0 is None:
                    groups[gi].append(i)
                    placed = True
                    break
        if not placed:
            groups.append([i])
            zeros.append(z)
    if not attach_elevated:
        # §15 (1): the elevated bodies are the UNIT's business, not this
        # placement's — the caller runs the stands-over search over every
        # resource of the unit and attaches them itself
        return [sorted(g) for g in sorted(groups, key=min)]
    group_of = {i: gi for gi, g in enumerate(groups) for i in g}
    for i in sorted(elevated):
        a = bodies[i][1]
        ml, mo = _ar._m_per_deg(a.lat)

        # §13 (1): the CARRIER — largest plan overlap, else nearest
        def _rank(j: int, _a: _ar.Anchor = a, _i: int = i) -> tuple[float, float, int]:
            ov = (overlap(boxes[_i], boxes[j]) if boxes is not None
                  and _i < len(boxes) and j < len(boxes) else 0.0)
            b = bodies[j][1]
            d2 = ((b.lat - _a.lat) * ml) ** 2 + ((b.lon - _a.lon) * mo) ** 2
            return (-ov, d2, j)

        carrier = min(ground, key=_rank)
        groups[group_of[carrier]].append(i)
    return [sorted(g) for g in sorted(groups, key=min)]


# ── §14 (3): PLAN OVERLAP BINDS ──────────────────────────────────────────

def bind_plan_overlaps(groups: _t.Sequence[_t.Sequence[int]],
                       boxes: _t.Sequence[_t.Sequence[tuple[float, float,
                                                            float, float]]],
                       classes: _t.Sequence[str],
                       *, bind_basin: bool = True) -> list[list[int]]:
    """§14 (3): bodies of ONE resource that OVERLAP IN PLAN are one body
    whatever the contact graph says — a floor under walls, a ledge inside
    a wall, a parapet over its own trench.  The split only ever separates
    bodies that are APART in plan and whose terrain differs by more than
    ``split_tol_m`` (which is what :func:`coarsen` already decided).

    This is what closed LEMD's 7.0 m zero-plane scatter: the basin's
    floor plate, its walls and its parapet carry no ε-contact edge
    between them (they are authored as separate welded components a
    fraction of a metre apart), so 10i's contact graph made them three
    bodies standing over terrain that genuinely differs — the floor is
    7 m under the rim — and the coarsening dutifully gave each its own
    file and its own drape.  They are ONE RIGID OBJECT, and the plan
    overlap says so.

    A LINE SEGMENT is never bound: the segments of one fence are apart in
    plan BY CONSTRUCTION (11f (2) cut them so each could read its own
    terrain), and a zig-zag fence's axis-aligned segment boxes overlap
    where the fence itself does not.  Binding them would undo the cut.

    ``boxes`` is one body's PART boxes, not one box per body: a body's
    own hull box is a crude proxy for its footprint, and binding on it
    read two L-shaped wings of a terminal 100 m apart as overlapping.
    Measured at LEMD: the hull reading bound 87 groups and put 1,538 more
    feet ABOVE their ground (``other`` feet over 3 m 49 -> 203); the part
    reading binds what actually stands over what.
    """
    n = len(boxes)
    parent = list(range(n))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    if bind_basin:
        # §14 (2): A BASIN RESOURCE IS NEVER SPLIT.  Its floor plate, its
        # walls and its parapet are one rigid object over terrain that
        # DIFFERS by the pit's own depth — the one case where "the
        # terrain differs under the object" is not evidence of two
        # bodies, because the pit was cut to the object (10ba).  They
        # overlap in plan too, so this only forecloses the reading where
        # a wall ring's box misses its floor's.
        basin = [i for i in range(n) if classes[i] == _ar.BASIN]
        for i in basin[1:]:
            union(basin[0], i)
    # the body HULL is a cheap reject for the part-by-part scan below:
    # two bodies whose hulls miss cannot have a part pair that overlaps,
    # and a placement like LEMD's 113-body perimeter grass would
    # otherwise run the part product 6,300 times (+1.6 s on the airport)
    hull = [(min(b[0] for b in bs), min(b[1] for b in bs),
             max(b[2] for b in bs), max(b[3] for b in bs)) if bs else None
            for bs in boxes]
    live = [i for i in range(n)
            if classes[i] != _ar.LINE_SEGMENT and hull[i] is not None]
    # ONE SWEEP, not the full product (11ak (4)): the scan is ordered by
    # the hull's south edge, so once a candidate STARTS north of this
    # body's north edge neither it nor anything after it can overlap.
    # The partition is unchanged (union-find does not care in what order
    # it is told); what changes is that OTHH's stage stops asking the
    # question 77 million times.
    live.sort(key=lambda i: hull[i][0])
    for a_i, i in enumerate(live):
        north = hull[i][2]
        for j in live[a_i + 1:]:
            if hull[j][0] > north:
                break
            if find(i) == find(j) or overlap(hull[i], hull[j]) <= 0.0:
                continue
            if any(overlap(a, b) > 0.0 for a in boxes[i] for b in boxes[j]):
                union(i, j)
    # union the GROUPS the bound bodies fall in
    gparent = list(range(len(groups)))

    def gfind(a: int) -> int:
        while gparent[a] != a:
            gparent[a] = gparent[gparent[a]]
            a = gparent[a]
        return a

    root_group: dict[int, int] = {}
    for gi, g in enumerate(groups):
        for i in g:
            r = find(i)
            if r in root_group:
                ra, rb = gfind(root_group[r]), gfind(gi)
                if ra != rb:
                    gparent[ra] = rb
            else:
                root_group[r] = gi
    out: dict[int, list[int]] = {}
    for gi, g in enumerate(groups):
        out.setdefault(gfind(gi), []).extend(g)
    return [sorted(v) for _k, v in sorted(out.items(), key=lambda kv: min(kv[1]))]


def senior_of(raw: _t.Sequence[_t.Any], grp: _t.Sequence[int]) -> int:
    """The body whose ANCHOR a group takes (11e (1)): the one with the
    most ground-contact feet among the group's GROUND bodies (§13 (3):
    an elevated member's vertices are not feet), ties to the earliest —
    except that a BASIN body's anchor always wins its group (§14 (2):
    floor, walls and parapet share the rim's one zero)."""
    cands = [i for i in grp if not raw[i][4]] or list(grp)
    basins = [i for i in cands if raw[i][1] == _ar.BASIN]
    return max(basins or cands, key=lambda i: (len(raw[i][3]), -i))


# ── §15 (2): THE BINDING RE-CUT ──────────────────────────────────────────

def re_cut_by_terrain(groups: _t.Sequence[_t.Sequence[int]],
                      bodies: _t.Sequence[tuple[int, _ar.Anchor, int]],
                      tol_m: float, classes: _t.Sequence[str]
                      ) -> tuple[list[list[int]], int]:
    """§15 (2): ``(groups, re-cut count)``.

    :func:`bind_plan_overlaps` welds bodies that overlap in plan whatever
    their terrain does.  That is right for a floor under its walls and
    wrong for a 1,384 x 590 m chain of overlaps: LEMD's
    ``Terminal4_green-LEMD03__b0`` came out as ONE rigid body whose feet
    span 5.80 m of surface, and its low-side anchor then lifted the
    garage roof 8.68 m over the garage's own walls (owner 11ac (3), 11ae
    (3)).

    So the bond gets a TERRAIN CHECK: a bound group whose members'
    intended zeros (``surface_z - y_zero``, each member's own zero plane
    in world height) span more than ``tol_m`` is re-cut into TERRAIN
    GROUPS by §9's rule — :func:`coarsen`, restricted to that group —
    and the plan-overlap bond holds only within one of them.  A rigid
    body is never wider than the terrain it can stand on.

    A BASIN group is exempt and never re-cut: §14 (2) is the one case
    where the terrain differing under the object is not evidence of two
    bodies — the pit was cut TO the object (10ba), and its floor plate
    stands the pit's own depth below its rim by authoring."""
    if tol_m <= 0.0:
        return [list(g) for g in groups], 0
    out: list[list[int]] = []
    n_recut = 0
    for g in groups:
        zs = [None if bodies[i][1].surface_z is None
              else float(bodies[i][1].surface_z) - float(bodies[i][1].y_zero)
              for i in g]
        read = [z for z in zs if z is not None]
        if (len(g) < 2 or not read or max(read) - min(read) <= tol_m
                or any(classes[i] == _ar.BASIN for i in g)):
            out.append(list(g))
            continue
        n_recut += 1
        sub = coarsen([bodies[i] for i in g], tol_m)
        out.extend(sorted(g[j] for j in s) for s in sub)
    return [sorted(v) for v in sorted(out, key=min)], n_recut


# ── §14 (1) / §15 (1): THE CARRIER, over the UNIT ────────────────────────

@_dc.dataclass(frozen=True)
class Candidate:
    """One FOOTED body of a unit, as a carrier candidate: the file it
    lands in, the anchor that file takes, the part ids it holds (the
    contact / abutment graph speaks in those) and its plan box."""

    member: int
    resource: str
    anchor: _ar.Anchor
    pids: frozenset[int]
    feet: int
    box: tuple[float, float, float, float]
    #: was this body actually WRITTEN at its anchor (a split), or is it a
    #: kept-whole placement still sitting on its authored row?
    written: bool = True
    #: the candidate's PART boxes — what it actually covers in plan.  A
    #: body's own hull box is a crude proxy for its footprint (§14 (3)
    #: measured it: the hull read two L-shaped wings of a terminal 100 m
    #: apart as overlapping), and a coarsened group's hull can be a
    #: kilometre wide, which would make every roof of the unit "stand
    #: over" it.  The hull is kept as the cheap reject.
    part_boxes: tuple[tuple[float, float, float, float], ...] = ()
    #: which GROUP of that member's bodies this candidate IS (-1 for a
    #: candidate standing in for a whole placement) — §15 (1)'s search
    #: runs over the UNIT, so its answer has to name the group an
    #: elevated body of the SAME member JOINS, as against a file of
    #: another member it would RIDE
    group: int = -1
    #: §16 (3): the body's §6 CLASS and its FOOTPRINT FILL — a line
    #: segment never carries, and neither does a body filling less than
    #: ``[placement] carrier_fill_min`` of its own plan box
    body_class: str = ""
    fill: float = 1.0
    #: §16a (2): HOW FAR THIS CANDIDATE'S OWN ZERO STANDS FROM THE GROUND
    #: UNDER ITS OWN FEET.  §16 (3) refused a carrier by the ground under
    #: the CARRIED body, which is the reading §16a deletes: walls on
    #: sloping ground anchor at their low-side foot, and a roof judged
    #: against the ground under itself then lands metres off them (LEMD
    #: carried ``stands-over float > 0.5 m`` 1 -> 58).  What disqualifies
    #: a carrier is that IT is mis-anchored — it would carry its own
    #: error — and that is read on its own feet, ONCE per candidate
    #: rather than once per (body, candidate) search.  ``None`` off-sheet.
    ground_off: float | None = None

    @property
    def centre(self) -> tuple[float, float]:
        return (0.5 * (self.box[0] + self.box[2]), 0.5 * (self.box[1] + self.box[3]))


def unit_edges(pairs: _t.Iterable[tuple[int, int]],
               pids: _t.AbstractSet[int]) -> dict[int, set[int]]:
    """The unit's CONTACT + ABUTMENT graph as an adjacency map, restricted
    to the part ids of that unit.  Both relations are read the same way:
    10i's ε-contact says two parts touch, 10ay's abutment says two parts
    of one anchor plane overlap in plan a hair apart — and "the footed
    body it abuts" in §14 (1) is either of them.  What is counted is
    EDGES, which is the only measure of "largest contact" the plan
    carries (no plan record holds a contact AREA)."""
    adj: dict[int, set[int]] = {}
    for a, b in pairs:
        if a in pids and b in pids and a != b:
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)
    return adj


def carriers_for(pids: _t.AbstractSet[int],
                 box: tuple[float, float, float, float] | None,
                 cands: _t.Sequence[Candidate],
                 adj: _t.Mapping[int, _t.AbstractSet[int]],
                 part_boxes: _t.Sequence[tuple[float, float, float,
                                               float]] = (),
                 *, fill_min: float = 0.0, tol_m: float = 0.0,
                 refusals: dict[str, int] | None = None,
                 ) -> list[tuple[Candidate, str]]:
    """§15 (1) + §16a (1): EVERY carrier this body stands over, ranked.

    The list is the plan-overlap ranking of §15 (1)(a) — every candidate
    the law accepts whose footprint the body stands over, best first —
    and §16a (1) cuts the carried body against it: one piece per carrier
    group, each riding that group's zero.  Where the body stands over NO
    candidate the list holds the single answer of the fallback rules
    ((b) largest contact, else (c) nearest, else (d) largest), and where
    even those find nothing it is empty.

    :func:`carrier_for` is this function's first element, and is what
    §15 (1)'s single-carrier reading means.

    THE CARRIER IS WHAT THE BODY STANDS OVER, over the whole UNIT, every
    resource alike: (a) the footed body with the largest PLAN OVERLAP
    beneath the body's plan footprint; else (b) the footed body it ABUTS
    with the largest contact (the most edges of the unit's contact /
    abutment graph); else (c) the NEAREST footed body in plan; else (d)
    the unit's LARGEST footed body.  ``(None, "")`` when the unit holds
    no footed body at all — the caller reports that class by name and
    never guesses a height.

    The order is the owner's 11ae attribution read back as law.  Contact
    first carried LEMD's T3 roof ``tej2`` onto ``P2PK`` — a neighbour it
    touches — instead of onto ``LEMD41``, the building it stands over
    (+1.15 m); distance inside its own placement carried the
    ``LEMD38`` hangar roof onto walls 250 m away (+6.11 m).  What the eye
    reads is the body under the body, and no same-resource preference
    survives: this pack names its roofs as their own resources
    (``TEJ*``/``tej*``, *tejado*), so the walls a roof rides are almost
    never its own file.

    §16 (3): A CARRIER IS A SOLID.  A candidate that is a LINE SEGMENT,
    or whose footprint fills less than ``fill_min`` of its own plan box
    (a grass strip, a sign, a fence), never carries — its box says
    nothing about where the ground under the carried body is.

    §16a (2): AND THE GROUND CHECK IS ON THE CARRIER.  A candidate whose
    own zero stands more than ``tol_m`` from the ground under ITS OWN
    FEET (:attr:`Candidate.ground_off`, read once where the candidate is
    made) is REFUSED and the search continues — it is itself
    mis-anchored and would carry its error.  The ground under the CARRIED
    body is never compared: walls on sloping ground anchor at their
    low-side foot, so a roof judged against the ground under itself is
    judged against a surface its carrier never stood on.
    ``refusals`` collects the counts by reason."""
    # PER SEARCH, not per candidate: what the report asks is how many
    # bodies had a candidate refused, not how many (body, candidate)
    # pairs a unit of 111 candidates makes
    local: dict[str, int] = {}

    def _bump(k: str) -> None:
        local[k] = local.get(k, 0) + 1

    def _out(r: list[tuple[Candidate, str]]) -> list[tuple[Candidate, str]]:
        if refusals is not None:
            for k in local:
                refusals[k] = refusals.get(k, 0) + 1
        return r

    solid = []
    for c in cands:
        if c.body_class == _ar.LINE_SEGMENT:
            _bump("line")
            continue
        if fill_min > 0.0 and c.fill < fill_min:
            _bump("fill")
            continue
        solid.append(c)
    if not solid:
        return _out([])

    def _ok(c: Candidate) -> bool:
        """§16a (2): the candidate's OWN zero against the ground under
        its OWN feet."""
        if c.ground_off is None or tol_m <= 0.0:
            return True
        if c.ground_off <= tol_m:
            return True
        _bump("zero_off_ground")
        return False

    if box is not None:
        # ONE relation, read ONE way (CLAUDE.md, the census-wrapper
        # defect): the search and §15 (3)'s census rank the same
        # geometry — the body's plan box as the cheap reject and, where
        # the plan publishes them, its footprint boxes (§16 (3)).
        ranked = []
        for c in solid:
            ov = stands_over_rank(box, c.box, part_boxes, c.part_boxes)
            if ov > (0.0, 0.0):
                ranked.append((ov, c))
        ranked.sort(key=lambda q: (q[0][0], q[0][1], -q[1].member), reverse=True)
        over = [(c, f"stands over {overlap_m2(box, c.box):.0f} m2 of it in plan")
                for _ov, c in ranked if _ok(c)]
        if over:
            return _out(over)
    # the body's neighbours, walked ONCE: a unit's candidate list is
    # long (LEMD's unit:25 offers 111 footed bodies) and re-walking the
    # adjacency per candidate costs more than the whole carrier rule
    neigh: list[int] = [q for p in pids for q in adj.get(p, ())]
    touch = []
    for c in solid:
        n = sum(1 for q in neigh if q in c.pids)
        if n:
            touch.append((n, c))
    touch.sort(key=lambda q: (q[0], -q[1].member), reverse=True)
    for n, c in touch:
        if _ok(c):
            return _out([(c, f"abuts {n} part contact(s)")])
    if box is not None:
        clat, clon = 0.5 * (box[0] + box[2]), 0.5 * (box[1] + box[3])
        ml, mo = _ar._m_per_deg(clat)

        def _d2(c: Candidate) -> tuple[float, int]:
            la, lo = c.centre
            return (((la - clat) * ml) ** 2 + ((lo - clon) * mo) ** 2, c.member)

        for c in sorted(solid, key=_d2):
            if _ok(c):
                return _out([(c, f"nearest footed body of the unit "
                              f"({_d2(c)[0] ** 0.5:.0f} m)")])
        return _out([])
    for c in sorted(solid, key=lambda c: (-c.feet, c.member)):
        if _ok(c):
            return _out([(c, "the unit's largest footed body")])
    return _out([])


def carrier_for(pids: _t.AbstractSet[int],
                box: tuple[float, float, float, float] | None,
                cands: _t.Sequence[Candidate],
                adj: _t.Mapping[int, _t.AbstractSet[int]],
                part_boxes: _t.Sequence[tuple[float, float, float,
                                              float]] = (),
                **kw: _t.Any) -> tuple[Candidate | None, str]:
    """§15 (1)'s single answer: the FIRST of :func:`carriers_for`, or
    ``(None, "")`` when the unit offers the law no carrier at all."""
    out = carriers_for(pids, box, cands, adj, part_boxes, **kw)
    return out[0] if out else (None, "")


def group_at_zero(groups: _t.Sequence[_t.Sequence[int]],
                  raw: _t.Sequence[_t.Any], zero: float | None, tol_m: float,
                  senior_of: _t.Callable[[_t.Any, _t.Sequence[int]], int]) -> int:
    """The index of the member's own group standing at ``zero`` (within
    ``tol_m``), or ``-1``.

    §15 (1) says which terrain reading an elevated body takes; §9 still
    says which FILE it is written in, and two zeros that agree within the
    coarsening tolerance are one file by that rule.  So a roof whose
    carrier is another resource, but whose carrier's zero is the zero one
    of its own placement's groups already stands at, rides its own file:
    the same height, one file fewer, and no reading changed."""
    if zero is None or tol_m <= 0.0:
        return -1
    best, best_d = -1, tol_m
    for gi, g in enumerate(groups):
        a = raw[senior_of(raw, g)][2]
        if a.surface_z is None:
            continue
        d = abs((float(a.surface_z) - float(a.y_zero)) - zero)
        if d <= best_d:
            best, best_d = gi, d
    return best


def merge_rides(rides: _t.Mapping[tuple[int, int], tuple[list[int], str]],
                 by_key: _t.Mapping[tuple[int, int], Candidate],
                 tol_m: float) -> list[tuple[list[int], Candidate, str]]:
    """§9's own rule read on the CARRIED set: two elevated bodies of one
    member whose CARRIERS' zero planes agree within ``split_tol_m`` are
    ONE file — a split exists only where the terrain differs under the
    object, and a carrier is only ever a reading of that terrain.  The
    file takes the SENIOR carrier (the most feet), senior-first, so
    "agree" is always measured against the anchor the file will actually
    take.

    Without this a pack that names its roofs as their own resources
    (LEMD's ``TEJ*``) writes one file per roof panel per carrier group:
    the unit-wide search is per BODY, and a terminal's roof stands over
    a dozen wall groups whose zeros are the same flat apron."""
    items = []
    for k, (g, w) in rides.items():
        c = by_key[k]
        z = (None if c.anchor.surface_z is None
             else float(c.anchor.surface_z) - float(c.anchor.y_zero))
        items.append([z, list(g), c, w])
    groups: list[list] = []
    for it in sorted(items, key=lambda q: (-q[2].feet, q[2].member, q[2].group)):
        for gr in groups:
            if tol_m > 0.0 and (it[0] is None) == (gr[0] is None) and (
                    it[0] is None or abs(it[0] - gr[0]) <= tol_m):
                gr[1].extend(it[1])
                break
        else:
            groups.append(it)
    return [(sorted(g), c, w) for _z, g, c, w in groups]


def cut_order(deps: _t.Mapping[int, _t.AbstractSet[int]]) -> list[int]:
    """The order the unit's members are CUT in: a carrier before anything
    it carries, so that "was the carrier itself written at its anchor?"
    is answered by measurement and not by assumption (a carrier kept
    whole keeps its AUTHORED row, and the two files then stand at
    different heights — reported, never silent).  A cycle — two members
    each carrying the other's roof — is broken at its first member; the
    only thing that then goes unread is that one flag."""
    order: list[int] = []
    done: set[int] = set()
    rest = list(deps)
    while rest:
        free = [q for q in rest if deps[q] <= done] or [rest[0]]
        for q in free:
            order.append(q)
            done.add(q)
            rest.remove(q)
    return order


# ── the instruments (``placement_census``) ───────────────────────────────

from .placement_census import (                          # noqa: E402
    CARRIED_GROUND_TOL_M, FOOTLESS_KEPT, GEOM_GROUND_TOL_M, KEPT_FOOTLESS,
    KEPT_NO_CARRIER, LAWFUL_SKIPS, OWN_GROUND, STANDS_OVER_TOL_M,
    THICKNESS_SKIP, _v15_rows, census_population, census_population_lines,
    census_v14, census_v14_lines, census_v15, census_v15_lines, census_v16,
    census_v16_lines)
