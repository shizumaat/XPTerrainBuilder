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
           "re_cut_by_terrain", "hull_of", "stands_over_rank", "census_v14", "census_v14_lines",
           "census_v15", "census_v15_lines", "STANDS_OVER_TOL_M",
           "merge_rides", "cut_order", "group_at_zero", "senior_of",
           "FOOTLESS_KEPT"]


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


def stands_over_rank(box: tuple[float, float, float, float],
                     other: tuple[float, float, float, float]
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
    SMALLER is what it stands on."""
    ov = overlap(box, other)
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
    for a_i, i in enumerate(live):
        for j in live[a_i + 1:]:
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


def carrier_for(pids: _t.AbstractSet[int],
                box: tuple[float, float, float, float] | None,
                cands: _t.Sequence[Candidate],
                adj: _t.Mapping[int, _t.AbstractSet[int]],
                part_boxes: _t.Sequence[tuple[float, float, float,
                                              float]] = (),
                ) -> tuple[Candidate | None, str]:
    """§15 (1) (superseding §14 (1)(a) and §13 (1)'s same-placement
    scope): ``(carrier, why)`` for one elevated or footless body.

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
    never its own file."""
    if not cands:
        return None, ""
    if box is not None:
        # ONE relation, read ONE way (CLAUDE.md, the census-wrapper
        # defect): the search ranks on the body's PLAN BOX, which is
        # exactly what the plan publishes per body and what §15 (3)'s
        # census re-reads.  A part-by-part refinement here was measured
        # (LEMD: rides 2,051 -> 1,934, plan stage 3.0 -> 6.0 s) and
        # DROPPED: it moved 6 % of the rides, doubled the stage, and left
        # the instrument reading a different geometry from the law — a
        # carried body would then be "standing over" a body that was
        # never its carrier, and the bar would count the disagreement
        # rather than the defect.
        best_ov = (0.0, 0.0)
        over: Candidate | None = None
        for c in cands:
            ov = stands_over_rank(box, c.box)
            if ov > best_ov:
                best_ov, over = ov, c
        if over is not None:
            return over, (f"stands over {overlap_m2(box, over.box):.0f} m2 "
                          f"of it in plan")
    # the body's neighbours, walked ONCE: a unit's candidate list is
    # long (LEMD's unit:25 offers 111 footed bodies) and re-walking the
    # adjacency per candidate costs more than the whole carrier rule
    neigh: list[int] = [q for p in pids for q in adj.get(p, ())]
    best_n = 0
    best: Candidate | None = None
    for c in cands:
        n = sum(1 for q in neigh if q in c.pids)
        if n > best_n:
            best_n, best = n, c
    if best is not None:
        return best, f"abuts {best_n} part contact(s)"
    if box is not None:
        clat, clon = 0.5 * (box[0] + box[2]), 0.5 * (box[1] + box[3])
        ml, mo = _ar._m_per_deg(clat)

        def _d2(c: Candidate) -> tuple[float, int]:
            la, lo = c.centre
            return (((la - clat) * ml) ** 2 + ((lo - clon) * mo) ** 2, c.member)

        near = min(cands, key=_d2)
        return near, f"nearest footed body of the unit ({_d2(near)[0] ** 0.5:.0f} m)"
    big = max(cands, key=lambda c: (c.feet, -c.member))
    return big, "the unit's largest footed body"


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


# ── §14 (4): THE CENSUS ──────────────────────────────────────────────────

#: §13's interim reading: a footless placement left on its unit's shared
#: DATUM row.  §14 (1) supersedes it, and the bar is 0.
KEPT_FOOTLESS = "footless"
#: §14 (1)'s named residual: a footless placement whose UNIT holds no
#: footed body at all, so nothing in the plan reads the ground under it.
#: It keeps its own authored row — which for the one-member unit this
#: class actually is, is its own position, not a shared datum — and is
#: REPORTED by name rather than guessed at.  Not a bar.
KEPT_NO_CARRIER = "footless_no_carrier"
FOOTLESS_KEPT = (KEPT_FOOTLESS, KEPT_NO_CARRIER)


def census_v14(splits: _t.Sequence[_t.Mapping[str, _t.Any]],
               kept: _t.Sequence[_t.Mapping[str, _t.Any]],
               *, elevated_base_m: float, split_tol_m: float) -> dict:
    """§14 (4), over the PLACEMENT PLAN's own rows
    (``model/placement.Split.to_dict()`` — the shape the app writes and
    the shape ``obj8_split_report`` renders, so the two instruments are
    one code path and cannot disagree):

    ``footless at datum``   a footless file left on its placement's
                            authored row: the shared-datum point, which
                            for LEMD's unit:25 is 430 m and 15.7 m of
                            height away from the building it belongs to.
    ``footless on ground``  a footless file whose intended zero stands
                            above ``elevated_base_m`` — the writer shifted
                            it so its own lowest vertex lands on the
                            terrain (the footbridge deck 0.03 m under the
                            road).  This is §13's own bar restricted to
                            the footless class.
    ``basin bodies split``  a ``basin`` resource written as more than one
                            file: one rigid object draped piece by piece.
    ``spread``              the widest zero-plane range of any ONE
                            placement — ``surface_z - y_zero`` over its
                            bodies.  A placement whose terrain genuinely
                            differs is LAWFULLY split (§9), so this is
                            reported with the placement that carries it,
                            never silently.

    Bars: 0 / 0 / 0 / <= ``split_tol_m``."""
    at_datum: list[str] = []
    no_carrier: list[str] = []
    #: every BASIN body's zero plane, keyed by the emitted RING it
    #: anchors on when the anchor names one (§14 (2)) and by its own
    #: placement otherwise.  The ring is the physical object: LEMD's pit
    #: is authored as THREE resources on one row, and 11v measured its
    #: scatter ACROSS them (593.30 ... 600.29, 7.0 m).  Per-placement
    #: alone the metric cannot see that.
    basin_ring: dict[str, list[float]] = {}
    on_ground: list[tuple[float, str]] = []
    basin_split: list[str] = []
    spread: list[tuple[float, str]] = []
    for s in splits:
        p = s.get("placement", {})
        plat, plon = p.get("lat"), p.get("lon")
        zeros: list[float] = []
        basins = 0
        res = str(p.get("resource", "?"))
        for b in s.get("bodies", ()):
            off = b.get("authored_offset", (0.0, 0.0, 0.0))
            y0 = float(off[1]) if len(off) > 1 else 0.0
            a = b.get("anchor", {})
            if b.get("class") == "basin":
                basins += 1
            sz = b.get("surface_z")
            zero = None if sz is None else float(sz) - float(b.get("y_zero", y0))
            if zero is not None:
                zeros.append(zero)
                if b.get("class") == "basin":
                    why = str(b.get("anchor_reason", ""))
                    key = (why.split("(", 1)[1].split(")", 1)[0]
                           if why.startswith("basin rim (") else res)
                    basin_ring.setdefault(key, []).append(zero)
            if not b.get("elevated"):
                continue
            if plat is not None and abs(float(a.get("lat", 0.0)) - float(plat)) < 1e-9 \
                    and abs(float(a.get("lon", 0.0)) - float(plon)) < 1e-9:
                at_datum.append(str(b.get("new_resource", "?")))
            if y0 > elevated_base_m:
                on_ground.append((y0, str(b.get("new_resource", "?"))))
        if basins > 1:
            basin_split.append(res)
        if len(zeros) > 1:
            spread.append((max(zeros) - min(zeros), res))
    for k in kept:
        r = str(k.get("reason", ""))
        if r == KEPT_FOOTLESS:
            at_datum.append(str(k.get("resource", "?")))
        elif r == KEPT_NO_CARRIER:
            no_carrier.append(str(k.get("resource", "?")))
    spread.sort(reverse=True)
    basin_spread = sorted(((max(v) - min(v), k) for k, v in basin_ring.items()
                           if len(v) > 1), reverse=True)
    on_ground.sort(reverse=True)
    worst = spread[0] if spread else (0.0, "")
    wbasin = basin_spread[0] if basin_spread else (0.0, "")
    return {"footless_at_datum": len(at_datum),
            "footless_at_datum_names": at_datum[:5],
            "footless_on_ground": len(on_ground),
            "footless_on_ground_names": on_ground[:5],
            "basin_bodies_split": len(basin_split),
            "basin_bodies_split_names": basin_split[:5],
            "footless_no_carrier": len(no_carrier),
            "footless_no_carrier_names": no_carrier[:5],
            "spread_m": worst[0], "spread_resource": worst[1],
            "spread_basin_m": wbasin[0], "spread_basin_resource": wbasin[1],
            "spread_over_tol": sum(1 for d, _r in spread if d > split_tol_m),
            "bars_ok": (not at_datum and not on_ground and not basin_split
                        and worst[0] <= split_tol_m)}


# ── §15 (3): THE RESIDUAL THE EYE READS ──────────────────────────────────

#: §15 (3)'s reporting threshold: a body whose zero stands this far above
#: the zero of the body it STANDS OVER is what the owner reads as
#: floating (11ac: "the roof pieces are floating above the buildings").
STANDS_OVER_TOL_M = 0.5


def _v15_rows(splits: _t.Sequence[_t.Mapping[str, _t.Any]]) -> list[dict]:
    """Every body of the plan as ``{res, idx, box, zero, footed, carried}``
    — the one projection both §15 (3) readings are taken from.  A body
    with no ``plan_box`` (a plan written before §15) or no ``surface_z``
    (OFF-SHEET: its anchor stands on no graded face) carries ``None`` and
    is excluded from every comparison, never guessed at (§15 (5))."""
    rows: list[dict] = []
    for s in splits:
        p = s.get("placement", {})
        for b in s.get("bodies", ()):
            box = b.get("plan_box")
            sz = b.get("surface_z")
            rows.append({
                "res": str(b.get("new_resource") or p.get("resource", "?")),
                "idx": p.get("index"),
                # THE UNIT, without a new field: every placement of one
                # unit carries that unit's ANCHOR as its row (§14), so
                # the row's own (lat, lon) IS the unit key — and §15 (1)
                # scopes the carrier search to the unit, so the census
                # has to read the same scope or it counts the scoping
                # rather than the defect.
                "unit": (p.get("lat"), p.get("lon")),
                "box": None if not box else tuple(float(q) for q in box),
                "zero": None if sz is None
                        else float(sz) - float(b.get("y_zero", 0.0)),
                "feet": int(b.get("feet") or 0),
                "carried": bool(b.get("elevated")) or bool(b.get("merged_into")),
            })
    return rows


def census_v15(splits: _t.Sequence[_t.Mapping[str, _t.Any]],
               kept: _t.Sequence[_t.Mapping[str, _t.Any]] = (),
               *, float_tol_m: float = STANDS_OVER_TOL_M) -> dict:
    """§15 (3), over the PLACEMENT PLAN's own rows — the same shape and
    the same code path as :func:`census_v14`.

    A foot census cannot see this class at all: a carried body has NO
    feet, and a body anchored at its own low-side foot reads every foot
    of its own as lawful while standing metres above the walls under it.
    What the eye reads is the difference between the two zeros —

        float = zero - zero_beneath

    — where ``beneath`` is the FOOTED body of another placement with the
    largest plan overlap under this body's footprint (the same
    stands-over relation :func:`carrier_for` picks its carrier by, so the
    instrument and the law read the same geometry).  A body standing over
    nothing is not in the class.

    Bar (§15 (6)): ``stands-over float > 0.5 m`` is ZERO for CARRIED
    bodies — a carried body takes its carrier's zero by construction, so
    any residual is a carrier the law chose wrongly.  A FOOTED body's
    float is REPORTED by name: it reads its own ground, and two footed
    bodies over genuinely different terrain lawfully differ."""
    rows = _v15_rows(splits)
    ground = [r for r in rows if r["feet"] and r["box"] and r["zero"] is not None]
    in_unit: dict[_t.Any, list[dict]] = {}
    for g in ground:
        in_unit.setdefault(g["unit"], []).append(g)
    carried_over: list[tuple[float, str, str]] = []
    footed_over: list[tuple[float, str, str]] = []
    n_stands = 0
    cross = 0
    off_sheet = sum(1 for r in rows if r["zero"] is None or not r["box"])
    for r in rows:
        if r["zero"] is None or not r["box"]:
            continue
        best_ov, under = (0.0, 0.0), None
        for g in in_unit.get(r["unit"], ()):
            if g["idx"] == r["idx"]:
                continue
            ov = stands_over_rank(r["box"], g["box"])
            if ov > best_ov:
                best_ov, under = ov, g
        if under is None:
            # it stands over a body of ANOTHER unit, which §15 (1)'s
            # search cannot reach: reported as its own number, never
            # counted as a float the law could have closed
            cross += any(g["idx"] != r["idx"] and overlap(r["box"], g["box"]) > 0.0
                         for g in ground)
            continue
        n_stands += 1
        f = r["zero"] - under["zero"]
        if f > float_tol_m:
            (carried_over if r["carried"] else footed_over).append(
                (f, r["res"], under["res"]))
    carried_over.sort(reverse=True)
    footed_over.sort(reverse=True)
    return {"stands_over": n_stands,
            "stands_over_float_gt": len(carried_over) + len(footed_over),
            "carried_float_gt": len(carried_over),
            "footed_float_gt": len(footed_over),
            "carried_worst": carried_over[:10],
            "footed_worst": footed_over[:10],
            "off_sheet_bodies": off_sheet,
            "stands_over_other_unit_only": cross,
            "float_tol_m": float_tol_m,
            "bars_ok": not carried_over}


def census_v15_lines(c: _t.Mapping[str, _t.Any]) -> list[str]:
    """:func:`census_v15`'s bar as the lines both tools print."""
    tol = c.get("float_tol_m", STANDS_OVER_TOL_M)
    out = [f"   §15 bodies standing over a body of another placement: "
           f"{c['stands_over']} of its own UNIT — §15 (1)'s own scope "
           f"({c['off_sheet_bodies']} off-sheet body(ies) excluded; "
           f"{c.get('stands_over_other_unit_only', 0)} stand only over a body "
           f"of ANOTHER unit, which the carrier search cannot reach)",
           f"   §15 stands-over float > {tol:g} m: {c['stands_over_float_gt']} "
           f"— CARRIED {c['carried_float_gt']} (bar 0)"
           + ("" if not c["carried_float_gt"] else
              "   *** §15 (1) VIOLATED (bar 0) ***")
           + f", footed {c['footed_float_gt']} (reported, not barred)"]
    for f, res, under in c.get("carried_worst", ()):
        out.append(f"      carried +{f:.2f} m  {res}  over {under}")
    for f, res, under in c.get("footed_worst", ()):
        out.append(f"      footed  +{f:.2f} m  {res}  over {under}")
    return out


def census_v14_lines(c: _t.Mapping[str, _t.Any], *, elevated_base_m: float,
                     split_tol_m: float) -> list[str]:
    """:func:`census_v14`'s four bars as the lines both tools print."""
    def _bar(n: int) -> str:
        return "" if not n else "   *** §14 VIOLATED (bar 0) ***"
    out = [f"   §14 footless at datum: {c['footless_at_datum']} (bar 0)"
           + _bar(c["footless_at_datum"]),
           f"   §14 footless on ground: {c['footless_on_ground']} "
           f"(bar 0, [rebake] elevated_base_m {elevated_base_m:g} m)"
           + _bar(c["footless_on_ground"]),
           f"   §14 basin bodies split: {c['basin_bodies_split']} (bar 0)"
           + _bar(c["basin_bodies_split"]),
           f"   §14 spread (widest zero-plane range of one placement): "
           f"{c['spread_m']:.2f} m (bar <= {split_tol_m:g} m) "
           f"{c['spread_resource']}; {c['spread_over_tol']} placement(s) over "
           f"— a placement whose terrain genuinely differs is LAWFULLY "
           f"split (§9), so read the rigid classes beside it:",
           f"   §14 spread of a BASIN RING (11v: 7.0 m over LEMD36+37+SWbaume): "
           f"{c['spread_basin_m']:.2f} m (bar <= {split_tol_m:g} m) "
           f"{c['spread_basin_resource']}",
           f"   §14 footless with no footed body in their unit (their own "
           f"authored row, reported not barred): {c['footless_no_carrier']}"]
    for name in c.get("footless_at_datum_names", ()):
        out.append(f"      at datum: {name}")
    for y, name in c.get("footless_on_ground_names", ()):
        out.append(f"      on ground: +{y:.2f} m  {name}")
    for name in c.get("basin_bodies_split_names", ()):
        out.append(f"      basin split: {name}")
    return out
