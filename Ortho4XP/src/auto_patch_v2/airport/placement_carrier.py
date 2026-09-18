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
           "box_gap_m", "CandidateIndex", "CANDIDATE_CELL_M",
           "carrier_for", "unit_edges", "box_of", "overlap", "overlap_m2",
           "re_cut_by_terrain", "hull_of", "stands_over_rank", "foot_boxes",
           "fill_of", "parts_overlap", "ground_at_box", "ground_under", "contact_ground",
           "foot_box_index", "CONTACT_PTS_MAX",
           "ground_samples", "box_area_m2",
           "census_v16", "census_v16_lines", "census_v16b",
           "census_v16b_lines", "census_population",
           "census_population_lines", "census_v14", "census_v14_lines",
           "census_v15", "census_v15_lines", "STANDS_OVER_TOL_M",
           "merge_rides", "cut_order", "group_at_zero", "senior_of",
           "FOOTLESS_KEPT", "KEPT_FOOTLESS", "KEPT_NO_CARRIER", "OWN_GROUND",
           "THICKNESS_SKIP", "LAWFUL_SKIPS", "_v15_rows",
           "census_bridges", "census_bridges_lines",   # §16e (3)
           "census_families", "census_families_lines"]   # §16f

# THE INSTRUMENTS LIVE NEXT DOOR (``placement_census``) and are re-exported
# here: every caller — both tools and the twins — reads them as this
# module's, and the 1,000-line law is what moved them, not a second home
# for the reading.  One implementation, one import surface.


# ── the plan boxes and the ground under them (``placement_boxes``) ──────
# The geometry every rule here measures on — plan boxes, footprints,
# overlaps, and the design surface under a body — lives next door for the
# 1,000-line law; it is re-exported because every caller and every twin
# reads it as this module's.
from .placement_boxes import (                           # noqa: E402
    FOOT_BOXES_MAX, GROUND_OFF_FEET_MAX, anchor_ground_off, box_area_m2,
    box_gap_m, box_of, fill_of, foot_boxes, ground_at_box, ground_samples,
    CONTACT_PTS_MAX, contact_ground, foot_box_index, ground_under,
    hull_of, overlap,
    overlap_m2, parts_overlap,
    stands_over_rank)

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
    # §16e: A DATUM BODY IS NEVER ELEVATED.  Both readings above ask
    # whether the file's zero is the GROUND, and a crest plate's
    # ``y_zero`` is +5 … +10 m BY CONSTRUCTION: read as elevated, every
    # OTHH tunnel wall was handed to a carrier or to "its own ground" and
    # the datum was thrown away at the last step.
    if anchor.datum:
        return False
    return bool(base_y_min > elevated_base_m or anchor.y_zero > elevated_base_m)


# ── §9 (1) + §13 (1): the coarsening ─────────────────────────────────────

def coarsen(bodies: _t.Sequence[tuple[int, _ar.Anchor, int]], tol_m: float,
            elevated: _t.AbstractSet[int] = frozenset(),
            boxes: _t.Sequence[tuple[float, float, float, float]] | None = None,
            *, attach_elevated: bool = True, reach_m: float = 0.0,
            grounds: _t.Sequence["float | None"] | None = None
            ) -> list[list[int]]:
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

    §16b (1) AMENDS THIS: agreement is necessary and not sufficient.  Two
    bodies join one file only when they are ALSO CONTIGUOUS IN PLAN —
    within ``reach_m`` (``[placement] coarsen_reach_m``) of a box already
    in the group.  LEMD's ``Taxisigns-SENRG`` is 80 signs over
    835 x 2,319 m of airfield: by zero alone they made files that took
    their height from a sign a kilometre and a half away (+4.58 m at the
    owner's gate 5, 11ap item 2).  ``reach_m <= 0`` or no ``boxes``
    restores the pre-11ap reading.

    And §9's coarsening acts WITHIN A TERRAIN GROUP, never across one
    (§16b (1)): where ``grounds`` gives each body the design surface
    under its OWN written geometry, two bodies join only when that
    ground also agrees within ``tol_m``.  Without it the terrain cut is
    undone by the very next pass — two pieces cut apart because the
    ground under them differs have DIFFERENT authored y, so their zeros
    can agree to the centimetre and the coarsening puts them back in one
    file (measured: LEMD's wide-body count did not move until this).

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
    near = (reach_m > 0.0 and boxes is not None)

    def _contiguous(gi: int, i: int) -> bool:
        """§16b (1): is body ``i`` within ``reach_m`` of the group?"""
        if not near or i >= len(boxes) or boxes[i] is None:
            return True
        return any(j < len(boxes) and boxes[j] is not None
                   and box_gap_m(boxes[i], boxes[j]) <= reach_m
                   for j in groups[gi])

    def _same_terrain(gi: int, i: int) -> bool:
        """§16b (1): does body ``i`` stand on the group's own terrain?"""
        if grounds is None or tol_m <= 0.0 or i >= len(grounds) \
                or grounds[i] is None:
            return True
        return all(j >= len(grounds) or grounds[j] is None
                   or abs(float(grounds[i]) - float(grounds[j])) <= tol_m
                   for j in groups[gi])

    for i in order:
        _bi, a, _n = bodies[i]
        z = None if a.surface_z is None else float(a.surface_z) - float(a.y_zero)
        placed = False
        if tol_m > 0.0:
            for gi, g0 in enumerate(zeros):
                if (z is None) == (g0 is None) and (
                        z is None or abs(z - g0) <= tol_m) \
                        and _contiguous(gi, i) and _same_terrain(gi, i):
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

def _key_apart(bind_keys: _t.Sequence[str], i: int, j: int) -> bool:
    """§14a (1): are these two bodies held APART by their bind keys?

    A key is a body's own reason to be its own file whatever the plan
    overlap says: the pieces of a basin body cut by the ring's ARCS carry
    their arc's rim point as their key, and binding them back together
    would undo the cut that makes the wall follow the apron.  An empty
    key never holds anything apart, so every pre-§14a caller reads
    exactly as before."""
    if not bind_keys or i >= len(bind_keys) or j >= len(bind_keys):
        return False
    a, b = bind_keys[i], bind_keys[j]
    return bool(a) and bool(b) and a != b


def bind_plan_overlaps(groups: _t.Sequence[_t.Sequence[int]],
                       boxes: _t.Sequence[_t.Sequence[tuple[float, float,
                                                            float, float]]],
                       classes: _t.Sequence[str],
                       *, bind_basin: bool = True,
                       bind_keys: _t.Sequence[str] = ()) -> list[list[int]]:
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
            if not _key_apart(bind_keys, basin[0], i):
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
            if (find(i) == find(j) or _key_apart(bind_keys, i, j)
                    or overlap(hull[i], hull[j]) <= 0.0):
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
                      tol_m: float, classes: _t.Sequence[str],
                      grounds: _t.Sequence["float | None"] | None = None,
                      boxes: _t.Sequence[tuple[float, float, float,
                                               float]] | None = None,
                      reach_m: float = 0.0
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

    §16b (1): the check is on the GROUND as well as on the zeros.  The
    plan-overlap bond is a union-find over boxes and knows nothing about
    terrain, so it welds back together exactly the pieces the
    own-geometry cut has just divided — two neighbouring slices of one
    garage slab overlap in plan by construction.  A bond whose members'
    OWN GROUND spans more than ``tol_m`` is re-cut by the same rule, and
    the sub-grouping is told the grounds too.

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
        gr = ([] if grounds is None else
              [float(grounds[i]) for i in g
               if i < len(grounds) and grounds[i] is not None])
        wide = bool(gr) and max(gr) - min(gr) > tol_m
        if (len(g) < 2 or (not read and not wide)
                or ((not read or max(read) - min(read) <= tol_m) and not wide)
                or any(classes[i] == _ar.BASIN for i in g)):
            out.append(list(g))
            continue
        n_recut += 1
        sub = coarsen([bodies[i] for i in g], tol_m,
                      boxes=None if boxes is None else [boxes[i] for i in g],
                      reach_m=reach_m,
                      grounds=None if grounds is None
                      else [grounds[i] for i in g])
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
    #: REPORTED ONLY since 2026-09-12j (the fill gate is deleted)
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
    #: §16c (4): the candidate's TOP in the AUTHORED frame — the highest
    #: authored ``y`` of its components (``placement_cut.top_y``).  THE
    #: CARRIER IS WHAT THE BODY RESTS ON: among the candidates a body
    #: plan-overlaps, the one whose top lies nearest BELOW the body's own
    #: base plane, largest overlap breaking ties only.  Before this a
    #: 129,113 m2 floor slab 17 m below a roof beat the 158 m2 wall the
    #: roof rests on (LEMD's T2 roofs 0.57-0.70 m low, RULINGS 2026-09-12d).
    #: ``None`` where the file could not be read.
    top_y: float | None = None
    #: §16c (4): one authored TOP per entry of ``part_boxes`` — so the
    #: rest-on test reads the candidate's top UNDER THE OVERLAP rather
    #: than the top of a coarsened group a hundred metres away.
    part_tops: tuple[float, ...] = ()

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


#: §16b: the plan cell the candidate INDEX buckets a unit's carriers in.
#: A sampling resolution, not a law: it only decides which candidates a
#: search LOOKS at, and every candidate whose box covers the query box is
#: looked at either way.
CANDIDATE_CELL_M = 100.0


class CandidateIndex:
    """A unit's carrier candidates, bucketed by plan cell (§16b, speed).

    §16b (1)'s cut multiplies the bodies of an airport (LEMD 1,374 ->
    4,600) and §16b (2) asks the carrier question once per PIECE, so the
    naive search — every candidate ranked against every body — went from
    1.3 M pairs to 11 M and the plan stage from 5.6 s to 17.7 s.  The
    relation itself is unchanged: a candidate is looked at when its plan
    box shares a cell with the query's, and one too big to bucket is
    looked at always.  The law and the census read the same ranking; this
    only decides what is offered to it."""

    __slots__ = ("cells", "big", "ml", "mo", "all", "cell_m")

    def __init__(self, cands: _t.Sequence["Candidate"], lat: float,
                 cell_m: float = CANDIDATE_CELL_M, big_cells: int = 64):
        self.ml, self.mo = _ar._m_per_deg(lat)
        self.all = list(cands)
        self.cells: dict[tuple[int, int], list["Candidate"]] = {}
        self.big: list["Candidate"] = []
        for c in cands:
            ks = self._keys(c.box, cell_m)
            if ks is None or len(ks) > big_cells:
                self.big.append(c)
                continue
            for k in ks:
                self.cells.setdefault(k, []).append(c)
        self.cell_m = cell_m

    def _keys(self, box, cell_m: float):
        if not box:
            return None
        a = int(box[0] * self.ml // cell_m)
        b = int(box[2] * self.ml // cell_m)
        c = int(box[1] * self.mo // cell_m)
        d = int(box[3] * self.mo // cell_m)
        if (b - a + 1) * (d - c + 1) > 4096:
            return None
        return [(i, j) for i in range(a, b + 1) for j in range(c, d + 1)]

    def near(self, box) -> list["Candidate"]:
        """The candidates whose plan box may meet ``box``."""
        ks = self._keys(box, self.cell_m)
        if ks is None:
            return self.all
        out: list["Candidate"] = list(self.big)
        seen = {id(c) for c in out}
        for k in ks:
            for c in self.cells.get(k, ()):  # noqa: SIM118
                if id(c) not in seen:
                    seen.add(id(c))
                    out.append(c)
        return out


def carriers_for(pids: _t.AbstractSet[int],
                 box: tuple[float, float, float, float] | None,
                 cands: _t.Sequence[Candidate],
                 adj: _t.Mapping[int, _t.AbstractSet[int]],
                 part_boxes: _t.Sequence[tuple[float, float, float,
                                               float]] = (),
                 *, tol_m: float = 0.0,
                 refusals: dict[str, int] | None = None,
                 carried_ground: _t.Callable[[], "float | None"] | None = None,
                 solid_cands: _t.Sequence[Candidate] | None = None,
                 index: "CandidateIndex | None" = None,
                 base_y: "float | None" = None,
                 reach_m: float = 0.0,
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

    §16 (3) as amended (RULINGS 2026-09-12j): A CARRIER IS A SOLID — by
    CLASS.  A LINE SEGMENT never carries: a fence's axis-aligned plan box
    says nothing about where the ground under the carried body is.  The
    FOOTPRINT FILL fraction that stood beside it is DELETED: it struck
    the wall RINGS the roofs actually rest on (LEMD's `LEMD54` /
    `LEMD59` fill 0.005-0.031) before §16c (4) could rank them.

    §16a (2): AND THE GROUND CHECK IS ON THE CARRIER.  A candidate whose
    own zero stands more than ``tol_m`` from the ground under ITS OWN
    FEET (:attr:`Candidate.ground_off`, read once where the candidate is
    made) is REFUSED and the search continues — it is itself
    mis-anchored and would carry its error.  The ground under the CARRIED
    body is never compared: walls on sloping ground anchor at their
    low-side foot, so a roof judged against the ground under itself is
    judged against a surface its carrier never stood on.
    §16c (8) (RULINGS 2026-09-12q): AND THE REFUSAL YIELDS TO WHAT THE
    BODY RESTS ON — a candidate whose TOP under the overlap meets the
    body's base within ``tol_m`` is accepted however far its own zero
    stands from its feet, because it is the thing the body sits on
    (``_rests_on``).
    §16b (3): AND THE FALLBACK CARRIER IS BOUNDED.  The candidates above
    are ranked by the body STANDING OVER them, which is itself evidence
    about the ground under it.  The fallbacks — (b) contact, (c) nearest,
    (d) largest — carry no such evidence: they are "some footed body of
    the unit", and at LEMD they put T4's bamboo roof and its landside
    road deck on the PARKING GARAGE across the road (zeros 611.23 /
    612.19) with 615.6-616.2 m of ground under them, 4 m below the piers
    that hold them up (11ap item 4).  So a fallback candidate is accepted
    only when its zero stands within ``tol_m`` of the ground under the
    CARRIED PIECE (``carried_ground``, read once and only if a fallback
    is actually reached).  This is the carried-side test §16a struck for
    the WHOLE body, restored on the PIECE §16b (1) cuts; §16a (2)'s
    carrier-side test stays exactly as it is.

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

    # THE SOLID SET IS THE UNIT'S, NOT THE SEARCH'S (§16b, speed): the
    # class and fill tests do not depend on the body asking, and running
    # them per search cost 16 M calls on a cut airport.  The caller
    # passes the unit's own filtered list and the refusal counts it
    # already booked.
    if solid_cands is not None:
        solid = list(solid_cands)
    else:
        solid = []
        for c in cands:
            if c.body_class == _ar.LINE_SEGMENT:
                _bump("line")
                continue
            solid.append(c)
    if not solid:
        return _out([])

    def _ok(c: Candidate) -> bool:
        """§16a (2): the candidate's OWN zero against the ground under
        its OWN feet.

        A BASIN body is EXEMPT (RULINGS 2026-09-11al): its zero is the
        RIM by §14 (2) — the pit was cut to the object — and its floor
        feet are authored metres BELOW that zero by construction, so the
        test reads every pit as mis-anchored for a reason that is the
        basin law working (13 of LEMD's 21 refused carriers, the worst
        6.17 m).  Nothing can close them: the basin cut is exempt for
        §14 (2)'s own reason.  A basin may carry — the T4S tower cluster
        rides its rim.  §16f needs NO exemption here: (4)'s pad-plane
        bound keeps every family body within ``bind_ground_m`` of its own
        ground, so the ordinary test passes it (round 1, unbounded, was
        read as mis-anchored — files 477 -> 609)."""
        if c.body_class == _ar.BASIN:
            return True
        if getattr(c.anchor, "unit_seat", False):
            # §16g (2) (owner RULINGS 2026-09-13bo): ONE ZERO PER UNIT —
            # "no per-member cut, no carrier search, NO GROUND TEST
            # BETWEEN MEMBERS".  A unit member standing off its own
            # ground is the law WORKING (``unit_members_off_the_plane``
            # reports it), not a body that would carry its own error, and
            # a rider of a unit member belongs on the unit's plane.
            # MEASURED (lane v2leafseat, HECA dry replay): without this,
            # §16g (10) (4)'s amended leaf seat re-seated 24 bodies — the
            # T3 district's principal carriers — and 2,398 of their
            # riders lost every carrier, files 3,743 -> 6,165 and §15
            # footed float 608 -> 3,176.  With it: files 3,423, footless
            # own-ground 346 -> 134, §15 carried float 96 -> 67, carried
            # over a refused body 329 -> 102.  THE §16f COMMENT BELOW
            # STILL HOLDS for §16f (4)'s bounded family seat; §16g's is
            # unbounded by design, which is why it needs this.
            return True
        if c.ground_off is None or tol_m <= 0.0:
            return True
        if c.ground_off <= tol_m:
            return True
        _bump("zero_off_ground")
        return False

    seen_ground: list["float | None"] = []

    def _near_carried(c: Candidate) -> bool:
        """§16b (3): the FALLBACK test — this candidate's zero against
        the ground under the CARRIED piece.  Read once per search, and
        only when a fallback is reached (the stands-over path never asks
        it: standing over the body IS the evidence)."""
        if carried_ground is None or tol_m <= 0.0:
            return True
        if c.anchor.surface_z is None:
            return True
        if not seen_ground:
            seen_ground.append(carried_ground())
        g = seen_ground[0]
        if g is None:
            return True             # no reading is no evidence
        cz = float(c.anchor.surface_z) - float(c.anchor.y_zero)
        if abs(cz - float(g)) <= tol_m:
            return True
        _bump("far_from_carried_ground")
        return False

    if box is not None:
        # ONE relation, read ONE way (CLAUDE.md, the census-wrapper
        # defect): the search and §15 (3)'s census rank the same
        # geometry — the body's plan box as the cheap reject and, where
        # the plan publishes them, its footprint boxes (§16 (3)).
        ranked = []
        for c in (index.near(box) if index is not None else solid):
            ov = stands_over_rank(box, c.box, part_boxes, c.part_boxes)
            if ov > (0.0, 0.0):
                ranked.append((ov, c))
        # §16c (4): THE CARRIER IS WHAT THE BODY RESTS ON.  Among the
        # candidates the body plan-overlaps, the one whose TOP lies
        # NEAREST the body's own base plane — in ABSOLUTE distance,
        # above or below (12n) — wins; the overlap breaks ties only.  Largest-overlap alone put LEMD's T2 roofs on
        # ``LEMD38``'s 129,113 m2 floor pieces 17 m below them rather
        # than on the 158 m2 walls they rest on, 0.57-0.70 m low
        # (RULINGS 2026-09-12d); the one roof that happened to be bound
        # to its wall read 0.01 m.  Both y's are AUTHORED and the unit
        # shares one datum, so the difference is the rendered one.
        if base_y is not None and any(c.top_y is not None
                                      for _o, c in ranked):
            def _top_under(c: Candidate) -> "float | None":
                if c.part_tops and len(c.part_tops) == len(c.part_boxes):
                    hits = [tv for tb, tv in zip(c.part_boxes, c.part_tops)
                            if not (tb[2] < box[0] or tb[0] > box[2]
                                    or tb[3] < box[1] or tb[1] > box[3])]
                    if hits:
                        return max(hits)
                return c.top_y

            def _rests_on(c: Candidate) -> bool:
                """§16c (8): THE REST-ON CARRIER IS NOT REFUSED FOR ITS
                OWN GROUND (owner RULINGS 2026-09-12q).

                §16a (2) refuses a candidate whose own zero stands off
                the ground under its own feet, because it would carry
                its error.  But where the candidate's TOP under the
                overlap MEETS this body's base within ``tol_m``, the
                candidate is what the body physically rests on: LEMD's
                T3 roof ``tej2`` rests on ``P2PK__b0`` (|Δ| 1.45 m
                against 14.64 m for the runner-up) and the refusal —
                ``P2PK``'s own feet 0.42 m off — sent the roof to a
                body 14 m away.  Handing a roof to something it does
                not touch is a worse error than inheriting its wall's
                mis-anchoring, and the wall's residual is reported in
                its own right (§16a (2)'s refusal set).  The refusal
                stands for every other candidate."""
                if tol_m <= 0.0:
                    return False
                top = _top_under(c)
                if top is None or c.ground_off is None:
                    return False
                return abs(float(base_y) - float(top)) <= tol_m

            def _admit(c: Candidate) -> bool:
                if _ok(c):
                    return True
                if _rests_on(c):
                    _bump("zero_off_ground_yielded_rest_on")
                    return True
                return False

            def _rest_key(q):
                ov, c = q
                top = _top_under(c)
                if top is None:
                    return (1, 0.0, -ov[0], -ov[1], c.member)
                # §16c (4) as amended 2026-09-12n: NEAREST IN ABSOLUTE
                # DISTANCE, above or below.  A roof let INTO a parapet
                # rests on walls whose top stands ABOVE its base, and
                # "nearest below" sent LEMD's T2 roofs to bodies 6 m off
                # while the wall rings they sit in ranked last.
                return (0, round(abs(float(base_y) - float(top)), 3),
                        -ov[0], -ov[1], c.member)
            ranked.sort(key=_rest_key)
            over = [(c, f"rests on it (its top "
                        f"{float(base_y) - float(_top_under(c) or 0.0):+.2f} m "
                        f"from this body's base; stands over "
                        f"{overlap_m2(box, c.box):.0f} m2 in plan)"
                     if _top_under(c) is not None else
                     f"stands over {overlap_m2(box, c.box):.0f} m2 of it in plan")
                    for _ov, c in ranked if _admit(c)]
        else:
            ranked.sort(key=lambda q: (q[0][0], q[0][1], -q[1].member),
                        reverse=True)
            over = [(c, f"stands over {overlap_m2(box, c.box):.0f} m2 of it in plan")
                    for _ov, c in ranked if _ok(c)]
        if over:
            return _out(over)
    # the body's neighbours, walked ONCE: a unit's candidate list is
    # long (LEMD's unit:25 offers 111 footed bodies) and re-walking the
    # adjacency per candidate costs more than the whole carrier rule
    # ...and counted by INTERSECTION, not by scanning the neighbour list
    # once per candidate: §16d (4) asks this per ATOM, and the product of
    # a unit's neighbours by its candidates was 7.4 M steps and 8 s of
    # the LEMD plan stage.  The number is the same — the multiplicity of
    # each neighbour pid, summed over the candidate's own pids.
    neigh: dict[int, int] = {}
    for p in pids:
        for q in adj.get(p, ()):
            neigh[q] = neigh.get(q, 0) + 1
    _nk = neigh.keys()
    touch = []
    for c in solid:
        hit = _nk & c.pids
        if hit:
            touch.append((sum(neigh[q] for q in hit), c))
    touch.sort(key=lambda q: (q[0], -q[1].member), reverse=True)
    for n, c in touch:
        if _ok(c) and _near_carried(c):
            return _out([(c, f"abuts {n} part contact(s)")])
    if box is not None:
        clat, clon = 0.5 * (box[0] + box[2]), 0.5 * (box[1] + box[3])
        ml, mo = _ar._m_per_deg(clat)

        def _d2(c: Candidate) -> tuple[float, int]:
            la, lo = c.centre
            return (((la - clat) * ml) ** 2 + ((lo - clon) * mo) ** 2, c.member)

        for c in sorted(solid, key=_d2):
            # §16d (2) (owner RULINGS 2026-09-13h): THE NEAREST-FOOTED
            # FALLBACK IS CAPPED at ``coarsen_reach_m``.  Uncapped it
            # bound 35 of LEMD's bodies to a footed body somewhere else
            # on the airport — 19 of them over 100 m away, one 3,323 m —
            # and a zero read a kilometre off is not this body's ground
            # by any reading.  Beyond the cap the body takes its OWN
            # ground (§16 (3)), which is what the caller does with an
            # empty list.
            d = _d2(c)[0] ** 0.5
            if reach_m > 0.0 and d > reach_m:
                if refusals is not None:
                    refusals["nearest_beyond_reach"] = \
                        refusals.get("nearest_beyond_reach", 0) + 1
                break
            if _ok(c) and _near_carried(c):
                return _out([(c, f"nearest footed body of the unit "
                              f"({d:.0f} m)")])
        return _out([])
    for c in sorted(solid, key=lambda c: (-c.feet, c.member)):
        if _ok(c) and _near_carried(c):
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


def merge_rides(rides: _t.Mapping[tuple[int, int], tuple[list[int], str]],
                 by_key: _t.Mapping[tuple[int, int], Candidate],
                 tol_m: float,
                 boxes: _t.Sequence[tuple[float, float, float, float]] | None
                 = None, reach_m: float = 0.0,
                 grounds: _t.Sequence["float | None"] | None = None
                 ) -> list[tuple[list[int], Candidate, str]]:
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
    a dozen wall groups whose zeros are the same flat apron.

    §16b (1): and it is §9's rule WHOLE, contiguity included — two
    pieces of one roof riding carriers at the same height a kilometre
    apart are not one file, or the join undoes the cut that made them
    (``boxes`` one per body index, ``reach_m`` the plan gap)."""
    items = []
    for k, (g, w) in rides.items():
        c = by_key[k]
        z = (None if c.anchor.surface_z is None
             else float(c.anchor.surface_z) - float(c.anchor.y_zero))
        items.append([z, list(g), c, w])
    near = (reach_m > 0.0 and boxes is not None)

    def _hull(g: _t.Sequence[int]):
        return hull_of(boxes[i] for i in g
                       if i < len(boxes) and boxes[i] is not None)

    def _one_terrain(a: _t.Sequence[int], b: _t.Sequence[int]) -> bool:
        """§16b (1): pieces of one roof cut apart by the ground under
        them are not put back in one file by their carriers agreeing."""
        if grounds is None or tol_m <= 0.0:
            return True
        ga = [float(grounds[i]) for i in a
              if i < len(grounds) and grounds[i] is not None]
        gb = [float(grounds[i]) for i in b
              if i < len(grounds) and grounds[i] is not None]
        if not ga or not gb:
            return True
        return max(max(ga), max(gb)) - min(min(ga), min(gb)) <= tol_m

    groups: list[list] = []
    for it in sorted(items, key=lambda q: (-q[2].feet, q[2].member, q[2].group)):
        for gr in groups:
            if tol_m > 0.0 and (it[0] is None) == (gr[0] is None) and (
                    it[0] is None or abs(it[0] - gr[0]) <= tol_m) and (
                    not near
                    or box_gap_m(_hull(it[1]), _hull(gr[1])) <= reach_m) and (
                    _one_terrain(it[1], gr[1])):
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

from .placement_boxes import group_at_zero            # noqa: E402,F401
from .placement_census import (                          # noqa: E402
    CARRIED_GROUND_TOL_M, CARRIED_OWN_GROUND_TOL_M, FOOTLESS_KEPT,
    GEOM_GROUND_TOL_M, KEPT_FOOTLESS,
    KEPT_NO_CARRIER, LAWFUL_SKIPS, OWN_GROUND, STANDS_OVER_TOL_M,
    THICKNESS_SKIP, _v15_rows, census_population, census_population_lines,
    census_v14, census_v14_lines, census_v15, census_v15_lines, census_v16,
    census_torn_seams, census_torn_seams_lines, census_bridges,
    census_bridges_lines, census_families, census_families_lines,
    OUTSIDE_TOL_M, census_outside_box, census_outside_box_lines,
    census_v16_lines, census_v16b, census_v16b_lines,
    # §17 THE COCKPIT FRAME, object stage (RULINGS 2026-09-12x/12y)
    COCKPIT_RULING, cockpit_block, cockpit_block_lines)
