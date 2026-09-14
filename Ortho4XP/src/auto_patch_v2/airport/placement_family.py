"""§16f AN OBJECT FAMILY STAYS TOGETHER (owner RULINGS 2026-09-13af).

Owner, on the KCLT read (item 9): "Many parts of the main terminal
building complex are seated at different heights creating floating or
sunken elements by a few meters"; on the proposal: "approved, whenever
feasible, keep object families together".

A pack authors a whole terminal complex on ONE FLAT DATUM PLANE over
real relief.  Every law up to §16e reads ONE BODY at a time: §16c (6)/(7)
binds components and bodies the plan's own ε-contact graph links (a
2 mm VERTEX contact) and §16d (6) puts a body's anchor on the pad it
stands on — but the walls, the roofs, the glazing and the interior floors
of one complex are separate RESOURCES whose vertices never touch, and
each is then seated to the ground under itself.  At KCLT that is 259
bodies of 30 members over 18.33 m of zero.

THE FAMILY (§16f (1)) is the pack's set of MEMBERS that

  (a) share one authored datum plane — one placement row set at one
      authored y, which is exactly the plan's :class:`Unit` ("every
      placement sharing one anchor spelling"), the §16c (6)/(7) unit of
      contact — AND
  (b) form ONE CONNECTED PLAN CLUSTER: their footprints in contact
      within ``[placement] contact_eps_m``, or overlapping.

Two placement rows do NOT make a family — LEMD's shared-datum pack puts
2,035 of 2,109 bodies on two rows and they are not one object.  (b) is
the whole test, and it is MEASURED, never assumed: a member whose
footprint stands apart from every other is not in the family and is cut
to its own ground by §16c, and a unit whose members form no cluster of
two makes no family at all (OTHH's bridge clutter beside the deck plate,
§16e (3) WITHDRAWN — a PARTIAL family bound is worse than none).

THE ONE ZERO PLANE (§16f (2)): a family's bodies take one zero — the
datum of the emitted ``building`` pad their ground contacts mostly stand
on (§16d (6)'s pad-majority read taken over the FAMILY's contacts rather
than one body's), else the median ground under the family's own contacts.
Every member anchors ON that plane: each keeps an anchor point of its
own — the ground contact whose own ground stands nearest the family's
plane — and its ``y_zero`` is set so that its zero IS the plane, the same
shape §16e's :func:`anchor_rule._datum_anchor` takes for a crest plate or
a deck top (an authored height the law puts AT a chosen ground).

Rule 5b's basin refusal (RULINGS 2026-09-09ag, ``planar/basins.py``)
stays for a genuine slab-on-relief SINGLE member; a family's slab is the
family's floor, and this is where it is admitted — as the family's zero,
never as a pit to cut.

The relation is derived ONCE per plan and published per body as
``family_of``; the census prints per family its members, its zero
spread, the members cut apart and the pad or ground it seated on.
"""
from __future__ import annotations

import bisect as _bi
import dataclasses as _dc
import typing as _t

from . import anchor_rule as _ar
from . import placement_boxes as _pb
from .placement_contact import (_clusters,  # noqa: F401
                                boxes_touch, rings_touch)

__all__ = ["Family", "FAMILY_MIN_MEMBERS", "FAMILY_SHARE_MIN",
           "pad_plurality", "bind_families",
           "census_families", "census_families_lines",
           "union_area_m2", "PlanCluster", "plan_clusters", "bodies_of_plan",
           "cluster_plane"]

#: §16f (1): two placement rows do not make a family and neither does one
#: member — a FAMILY is a cluster of at least this many members of one
#: unit whose footprints touch.  A single member is already one object to
#: §14 (3) / §16c and needs nothing here.
FAMILY_MIN_MEMBERS = 2

#: How many ground contacts of one family the pad-majority read and the
#: median are taken over.  A terminal publishes tens of thousands of
#: feet and both readings are order statistics: sampling them evenly
#: changes no verdict a metre wide and keeps the pass off the plan
#: stage's critical path.
FAMILY_CONTACTS_MAX = 4000

#: §16f (3): FEASIBILITY.  A cluster is the unit's family only where it
#: holds more than this share of the unit's family-eligible footed
#: bodies.  A UNIT is a shared-datum row set, and a pack that authored a
#: whole complex on one plane puts nearly all of it in one cluster —
#: KCLT's terminal rows 122 of 139 and 25 of 28.  A row set whose bodies
#: fall into many small clusters is a row, NOT a complex: KCLT's unit:3
#: is eight separate hangars and its largest cluster is 7 bodies of
#: ~200.  Binding those made the airport's worst §17 motion row 2.52 ->
#: 3.73 m — a PARTIAL family bound is worse than none (§16e (3)
#: WITHDRAWN, RULINGS 2026-09-13ae), so the fragments are REPORTED per
#: body and left on their own ground.
FAMILY_SHARE_MIN = 0.5




@_dc.dataclass(frozen=True)
class Family:
    """One derived family, for the census (§16f (3))."""

    id: str
    unit: str
    members: tuple[str, ...]
    bodies: int
    contacts: int
    #: the family's ONE zero plane, in world height
    zero_z: float
    #: the ``building`` pad it seated on, or ``""`` for the median ground
    pad: str
    #: the per-body zero spread BEFORE the bind and AFTER it
    spread_before_m: float
    spread_after_m: float
    #: members of the unit that stood APART and were left on their own
    #: ground (§16f (2)), by resource
    apart: tuple[str, ...]

    def line(self) -> str:
        where = (f"pad {self.pad}" if self.pad else "the median ground")
        return (f"{self.id}: {len(self.members)} member(s), {self.bodies} "
                f"footed body(ies), {self.contacts} contact(s) -> one zero "
                f"{self.zero_z:.2f} on {where}; per-body zero spread "
                f"{self.spread_before_m:.2f} -> {self.spread_after_m:.2f} m; "
                f"{len(self.apart)} member(s) cut apart")


def bodies_of_plan(plan: _t.Any
                   ) -> "tuple[dict[tuple[int, int, int], tuple[int, ...]], dict[int, tuple[int, int, int]]]":
    """``(body -> its part ids, part id -> its body)`` over a whole plan,
    from ``placement_plan._bodies_of`` — §9's own body law, the
    intra-placement ε-contact component, with a LINE part binding
    nothing.  ONE derivation: the split writer, ``planar/group.py`` (which
    re-exports this) and §16g's footprint unit cut the same bodies or they
    are not talking about the same object.

    It lives in ``airport`` because §16g needs it at LOAD time and
    ``airport`` may not import ``planar``."""
    from .placement_plan import _bodies_of

    member_of_pid: dict[int, tuple[int, int]] = {}
    for ui, u in enumerate(plan.units):
        for mi, m in enumerate(u.members):
            for p in m.parts:
                member_of_pid[p.pid] = (ui, mi)
    intra: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for a, b in plan.contacts:
        ka, kb = member_of_pid.get(a), member_of_pid.get(b)
        if ka is not None and ka == kb:
            intra.setdefault(ka, []).append((a, b))
    bodies: dict[tuple[int, int, int], tuple[int, ...]] = {}
    of_pid: dict[int, tuple[int, int, int]] = {}
    for ui, u in enumerate(plan.units):
        for mi, m in enumerate(u.members):
            for gi, g in enumerate(_bodies_of(m, intra.get((ui, mi), []))):
                key = (ui, mi, gi)
                bodies[key] = tuple(g)
                for q in g:
                    of_pid[q] = key
    return bodies, of_pid


def union_area_m2(boxes: _t.Iterable[tuple[float, float, float, float]]
                  ) -> float:
    """§16f (7): THE FOOTPRINT UNION of a set of plan boxes, in square
    metres — the area the boxes COVER, each overlap counted once.

    Never the hull (a terminal's two wings and the apron between them
    read as one 200 x 300 m rectangle) and never the sum of the parts (a
    wall ring's boxes overlap each other hundreds of times).  A
    rectangle-union sweep: the distinct latitudes cut the plan into
    slabs, and within a slab the covering longitude intervals are merged.
    Exact and dependency-free.

    THE SWEEP CARRIES AN ACTIVE SET (RULINGS 2026-09-14b, lane
    ``v2unionsweep``).  It used to RE-SCAN every box for every slab
    (``[b for b in bs if b[0] <= y0 and b[2] >= y1]``), which is
    O(slabs x boxes): at OTHH that is 88 calls x 246 k slabs = 45.8 M
    evaluations, **284 s of a 300 s ``plan_clusters``** — while the merge
    itself cost 3.4 s, because the live spans are few and the box list is
    long.  The box y-starts and y-ends are now sorted ONCE and the live
    spans maintained incrementally across the slab boundaries: a box
    enters at its ``b[0]`` and leaves at its ``b[2]``, so each box is
    touched twice instead of once per slab.  The slab's span list is the
    SAME SEQUENCE the old ``sorted()`` produced (``bisect.insort`` keeps
    the identical total order on the ``(lon0, lon1)`` tuples), the merge
    and the accumulation below are untouched, and the areas are
    FLOAT-EXACT against the old reading (twin:
    ``tests/auto_patch_v2/test_v2unionsweep.py``)."""
    bs = [b for b in boxes if b and b[2] > b[0] and b[3] > b[1]]
    if not bs:
        return 0.0
    ys = sorted({b[0] for b in bs} | {b[2] for b in bs})
    n = len(bs)
    by_start = sorted(bs, key=lambda b: b[0])
    by_end = sorted(bs, key=lambda b: b[2])
    live: list[tuple[float, float]] = []
    si = ei = 0
    total = 0.0
    for y0, y1 in zip(ys, ys[1:]):
        # a box covers this slab iff ``b[0] <= y0 and b[2] >= y1``; every
        # ``b[0]`` and ``b[2]`` is itself one of ``ys``, so that is
        # exactly ``b[0] <= y0 < b[2]`` — enter at the start, leave at
        # the end.  Leaves run FIRST (a box never enters and leaves at
        # one boundary: ``b[2] > b[0]`` and both are in ``ys``).
        while ei < n and by_end[ei][2] <= y0:
            b = by_end[ei]
            ei += 1
            del live[_bi.bisect_left(live, (b[1], b[3]))]
        while si < n and by_start[si][0] <= y0:
            b = by_start[si]
            si += 1
            _bi.insort(live, (b[1], b[3]))
        dy = y1 - y0
        if dy <= 0.0:
            continue
        spans = live
        if not spans:
            continue
        ml, mo = _ar._m_per_deg(0.5 * (y0 + y1))
        cover = 0.0
        lo, hi = spans[0]
        for a, b in spans[1:]:
            if a > hi:
                cover += hi - lo
                lo, hi = a, b
            else:
                hi = max(hi, b)
        cover += hi - lo
        total += (dy * ml) * (cover * mo)
    return total


def _union_area_m2_reference(boxes: _t.Iterable[tuple[float, float, float, float]]
                             ) -> float:
    """THE PRE-SWEEP READING of :func:`union_area_m2`, kept for the
    EXACT-EQUALITY TWIN alone (RULINGS 2026-09-14b): the same law read
    with the O(slabs x boxes) re-scan the active set replaced.  It is
    called by nothing in the engine; `test_v2unionsweep` asserts the two
    agree BIT FOR BIT (``==`` on the float, and on the raw bytes of
    ``struct.pack``) on synthetic overlapping / touching / nested /
    disjoint boxes and on the OTHH capture's own cluster boxes."""
    bs = [b for b in boxes if b and b[2] > b[0] and b[3] > b[1]]
    if not bs:
        return 0.0
    ys = sorted({b[0] for b in bs} | {b[2] for b in bs})
    total = 0.0
    for y0, y1 in zip(ys, ys[1:]):
        dy = y1 - y0
        if dy <= 0.0:
            continue
        spans = sorted((b[1], b[3]) for b in bs if b[0] <= y0 and b[2] >= y1)
        if not spans:
            continue
        ml, mo = _ar._m_per_deg(0.5 * (y0 + y1))
        cover = 0.0
        lo, hi = spans[0]
        for a, b in spans[1:]:
            if a > hi:
                cover += hi - lo
                lo, hi = a, b
            else:
                hi = max(hi, b)
        cover += hi - lo
        total += (dy * ml) * (cover * mo)
    return total


@_dc.dataclass(frozen=True)
class PlanCluster:
    """§16f (7) / design §30 (4): ONE LARGE TERMINAL CLUSTER, derived from
    the REBAKE PLAN alone so the DESIGN SURFACE can emit its pad before
    the object stage exists (the family census runs after the planar
    stage; the cluster must be known at planar time or there is no pad
    for the object stage to seat on)."""

    id: str
    unit: str
    #: the resources of the members in the cluster
    members: tuple[str, ...]
    #: every PART box of the cluster, ``(lat0, lon0, lat1, lon1)``
    boxes: tuple[tuple[float, float, float, float], ...]
    #: the footprint UNION's area (:func:`union_area_m2`)
    area_m2: float
    #: the hull of the union — the cheap plan reject every reader takes
    hull: tuple[float, float, float, float]
    #: §16g (8) (owner RULINGS 2026-09-14u): the AUTHORED FLOOR of each
    #: box in ``boxes``, aligned with it — the pack's own ``Part.base_y``,
    #: the height that box's geometry starts at above its placement row.
    #: The design surface derives a cluster's OTHER pads from its
    #: reference pad with THIS (pad = reference + the authored offset),
    #: and it must be an AUTHORED quantity: the seated unit datum is read
    #: out of the SOLVED cluster pad (`placement_plan.build_splits` takes
    #: the emitted surface), so the object stage runs after the solve and
    #: cannot be what the solve derives a pad from.  Empty in a cluster
    #: built before the field, and the reader then has no offset to
    #: derive with and leaves the group at one plane, as it was.
    floors: tuple[float, ...] = ()

    def line(self) -> str:
        return (f"{self.id}: {len(self.members)} member(s), footprint union "
                f"{self.area_m2:,.0f} m2")


class _Shim:
    """A plan MEMBER's body dressed as the candidate :func:`_clusters`
    reads — the ONE cluster law, asked of the plan instead of the
    placement candidates.  Nothing else of a candidate is touched."""

    __slots__ = ("member", "part_boxes", "box", "body_class", "resource",
                 "floors")

    def __init__(self, member: int, boxes: list, resource: str,
                 floors: "list | None" = None) -> None:
        self.member = member
        self.part_boxes = boxes
        #: §16g (8): the authored floor of each of ``part_boxes``
        self.floors = list(floors or ())
        self.box = _pb.hull_of(boxes)
        self.body_class = ""
        self.resource = resource


def plan_clusters(plan: _t.Any, contact_eps_m: float, min_m2: float
                  ) -> list[PlanCluster]:
    """§16f (7)'s CLUSTERS read off a ``RebakePlan`` — the planar-time
    half of the family law (design spec §30 (4)).

    The same three tests §16f (1)/(3)/(7) state, in the same order and
    through the same :func:`_clusters`: one authored datum plane (the
    plan's own ``Unit``), one connected plan cluster of at least
    ``FAMILY_MIN_MEMBERS`` members within ``contact_eps_m``, more than
    ``FAMILY_SHARE_MIN`` of the unit's eligible bodies, and a footprint
    union over ``min_m2``.  A LINE part founds no body here for the same
    reason §16f (1) excludes a line segment.

    The BODY is the unit of contact, as it is at the object stage
    (``_clusters``'s own docstring: a member-level read dragged a body
    500 m out on the apron onto the plane).  ``planar/group.bodies_of_plan``
    is the ONE body derivation and is imported, never re-implemented."""
    if contact_eps_m <= 0.0 or min_m2 <= 0.0 or not getattr(plan, "units", ()):
        return []
    bodies, _of_pid = bodies_of_plan(plan)
    out: list[PlanCluster] = []
    for ui, u in enumerate(plan.units):
        parts_of: dict[int, _t.Any] = {p.pid: p for m in u.members
                                       for p in m.parts}
        shims: list[_Shim] = []
        for (bu, mi, _gi), pids in sorted(bodies.items()):
            if bu != ui:
                continue
            live = [parts_of[q] for q in pids
                    if q in parts_of and not parts_of[q].line]
            bx = [q.box for q in live]
            if bx:
                shims.append(_Shim(mi, bx, u.members[mi].resource,
                                   [float(q.base_y) for q in live]))
        if len(shims) < FAMILY_MIN_MEMBERS:
            continue
        clusters, _adj = _clusters(shims, contact_eps_m)
        for cl in clusters:
            if len(cl) <= FAMILY_SHARE_MIN * max(1, len(shims)):
                continue                      # §16f (3): a PARTIAL cluster
            boxes = [b for i in cl for b in shims[i].part_boxes]
            floors = [f for i in cl for f in shims[i].floors]
            area = union_area_m2(boxes)
            if area < min_m2:
                continue
            hull = _pb.hull_of(boxes)
            if hull is None:
                continue
            out.append(PlanCluster(
                id=f"{u.id}#{cl[0]}", unit=u.id,
                members=tuple(sorted({shims[i].resource for i in cl})),
                boxes=tuple(boxes), area_m2=area, hull=hull,
                floors=tuple(floors) if len(floors) == len(boxes) else ()))
    return out


def pad_plurality(cands: _t.Sequence[tuple[float, float, float, float]],
                  pads: _t.Sequence[_ar.PadRing]) -> "_ar.PadRing | None":
    """§16f (4): THE PAD A FAMILY MEMBER JOINS — the pad holding the
    LARGEST share of its ground contacts, whatever that share is
    (RULINGS 2026-09-13aq (i): §16d (6)'s "mostly" is amended to
    PLURALITY for families).

    Measured, round 1: KCLT's `unit:31#0` puts 43 of 129 anchors on
    `building80` and the rest on no pad at all, so a MAJORITY read
    declined and the whole row took its median ground 4.26 m off the pad
    the other row stands on.  The pad is still the best evidence there
    is; a plurality of zero is no evidence and returns ``None``."""
    if not pads or not cands:
        return None
    boxes = [(p, min(v[0] for v in p.ring), min(v[1] for v in p.ring),
              max(v[0] for v in p.ring), max(v[1] for v in p.ring))
             for p in pads if len(p.ring) >= 3]
    hits: dict[str, tuple[_ar.PadRing, int]] = {}
    for la, lo, _y, _z in cands:
        for p, y0, x0, y1, x1 in boxes:
            if y0 <= la <= y1 and x0 <= lo <= x1 and _ar._inside(p.ring, la, lo):
                got = hits.get(p.ref)
                hits[p.ref] = (p, (got[1] if got else 0) + 1)
                break
    if not hits:
        return None
    return max(hits.values(), key=lambda q: (q[1], q[0].ref))[0]


def _all_on_pavement(cc: _t.Sequence[tuple[float, float, float, float]],
                     surface: _ar.Surface) -> bool:
    """§16f (5) PAVEMENT IS KING: does EVERY ground contact of this body
    stand on a face the aircraft ROLLS on?  §17's own reading, through
    ``anchor_rule._all_on_rolled`` — one implementation, and a caller
    whose surface carries no roles reads FALSE (no reading is no
    evidence) and the body stays in its family."""
    return bool(_ar._all_on_rolled(cc, surface, None, None))


def _pad_groups(order: _t.Sequence[int], pad_of: _t.Mapping[int, str],
                adj: _t.Mapping[int, _t.AbstractSet[int]]
                ) -> dict[str, list[int]]:
    """§16f (4): the family's bodies partitioned into ONE GROUP PER PAD.

    A body on a pad seeds that pad's group; a body on NO pad joins the
    group it TOUCHES (§16c (6) contact), by a multi-source breadth-first
    walk out of the seeds so the nearest group in the contact graph wins
    and the tie goes to the lower pad ref; a body touching no group at
    all is left out and cut to its own ground (§16c)."""
    groups: dict[str, list[int]] = {}
    seen: dict[int, str] = {}
    frontier: list[int] = []
    for i in sorted(order, key=lambda i: (pad_of.get(i, ""), i)):
        ref = pad_of.get(i, "")
        if ref:
            groups.setdefault(ref, []).append(i)
            seen[i] = ref
            frontier.append(i)
    live = set(order)
    while frontier:
        nxt: list[int] = []
        for i in sorted(frontier, key=lambda i: (seen[i], i)):
            for j in sorted(adj.get(i, ())):
                if j in seen or j not in live:
                    continue
                seen[j] = seen[i]
                groups[seen[i]].append(j)
                nxt.append(j)
        frontier = nxt
    return {k: sorted(v) for k, v in sorted(groups.items())}


def _contacts_of(c: _t.Any, st: _t.Any, surface: _ar.Surface
                 ) -> list[tuple[float, float, float, float]]:
    """One footed candidate's ground contacts as
    ``(lat, lon, authored y, surface z)`` — the same reading
    :func:`anchor_rule.anchor_for` takes."""
    grp = st.groups[c.group] if 0 <= c.group < len(st.groups) else ()
    out = []
    for i in grp:
        for f in st.raw[i][3]:
            z = surface(f[0], f[1])
            if z is not None:
                out.append((float(f[0]), float(f[1]), float(f[2]), float(z)))
    return out


def _median(xs: _t.Sequence[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def cluster_plane(boxes: _t.Sequence[tuple[float, float, float, float]],
                  pads: _t.Sequence[_ar.PadRing]
                  ) -> "tuple[float | None, tuple[str, ...]]":
    """§16f (7) / §30 (4): THE CLUSTER PAD'S LEVEL — the median of the
    graded ring heights of EVERY emitted ``building`` pad the cluster's
    footprint union stands on, and the refs of those pads.

    The design surface priced those faces as ONE plane
    (``constraints.pads._plane_groups``), so their vertices are one
    plane's and the median is that plane's level whatever the sampling.
    ``(None, ())`` where the caller read no pads with their heights (the
    twins that build a pad by hand) — the caller then falls back to the
    median ground under the cluster's own contacts, as §16f (2) does."""
    if not pads or not boxes:
        return None, ()
    zs: list[float] = []
    refs: list[str] = []
    for p in pads:
        if not p.z or len(p.ring) < 3:
            continue
        pb0 = (min(v[0] for v in p.ring), min(v[1] for v in p.ring),
               max(v[0] for v in p.ring), max(v[1] for v in p.ring))
        if any(_pb.box_gap_m(pb0, b) <= 0.0 for b in boxes):
            zs.extend(float(q) for q in p.z)
            refs.append(p.ref)
    if not zs:
        return None, ()
    return _median(zs), tuple(sorted(set(refs)))


def _bind_cluster(cands: list, by_mi: _t.Mapping[int, _t.Any],
                  surface: _ar.Surface, pads: _t.Sequence[_ar.PadRing],
                  counts: dict, per: _t.Mapping[int, list],
                  cl: _t.Sequence[int], area_m2: float, *,
                  unit_id: str, bind_ground_m: float,
                  bound_ci: set) -> list[Family]:
    """§16f (7): ONE UNIT, ONE PLANE, ONE PAD.  Every body of ``per``
    takes the cluster pad's level — no pad partition (4), no pavement
    clause (5), no ground bound at the join.  A member whose own contacts
    stand further than ``bind_ground_m`` off the plane is COUNTED and
    NAMED, never re-seated: "these large complex structures have to be
    seated as a unit"."""
    from . import placement_carrier as _pc
    boxes = [b for ci in cl for b in (cands[ci].part_boxes or
                                      ([cands[ci].box] if cands[ci].box else []))]
    zero, refs = cluster_plane(boxes, pads)
    where = "+".join(refs) if refs else ""
    if zero is None:
        zero = _median([q[3] - q[2] for cc in per.values() for q in cc])
    fid = f"{unit_id or 'unit'}#{cl[0]}@cluster"
    mems = sorted({cands[ci].member for ci in per})
    gz = [cands[ci].anchor.surface_z - cands[ci].anchor.y_zero
          for ci in per if cands[ci].anchor.surface_z is not None]
    moved = 0
    n_off = 0
    worst = 0.0
    n_contacts = 0
    for ci, cc in sorted(per.items()):
        c = cands[ci]
        st = by_mi[c.member]
        n_contacts += len(cc)
        _st = max(1, len(cc) // _pb.GROUND_OFF_FEET_MAX)
        own_med = _median([q[3] - q[2] for q in cc[::_st]])
        if bind_ground_m > 0.0 and abs(own_med - zero) > bind_ground_m:
            n_off += 1
            if abs(own_med - zero) > abs(worst):
                worst = own_med - zero
        best = min(cc, key=lambda q: (round(abs(q[3] - q[2] - zero), 6),
                                      round(abs(q[2]), 6), q[0], q[1]))
        own = best[3] - best[2]
        a = _ar.Anchor(
            c.anchor.body_class, best[0], best[1], best[3] - zero,
            f"§16f (7) cluster {fid} of {len(mems)} member(s) on "
            + (f"pad {where}" if where else "its median ground")
            + f" at {zero:.2f} (own ground {own - zero:+.2f} m)",
            best[3], family=fid)
        grp0 = (st.groups[c.group] if 0 <= c.group < len(st.groups) else ())
        if not grp0:
            continue
        k0 = _pc.senior_of(st.raw, grp0)
        r0 = st.raw[k0]
        st.raw[k0] = (r0[0], r0[1], a) + tuple(r0[3:])
        _off = _pb.anchor_ground_off(
            a, tuple(f for j in grp0 for f in st.raw[j][3]), surface)
        if c.group < len(st.ground_off):
            st.ground_off[c.group] = _off
        cands[ci] = _dc.replace(c, anchor=a, ground_off=_off)
        bound_ci.add(ci)
        moved += 1
    if not moved:
        return []
    counts["bodies_bound_to_family"] = \
        counts.get("bodies_bound_to_family", 0) + moved
    counts["families"] = counts.get("families", 0) + 1
    counts["family_clusters"] = counts.get("family_clusters", 0) + 1
    counts["cluster_bodies"] = counts.get("cluster_bodies", 0) + moved
    counts["cluster_footprint_union_m2"] = max(
        counts.get("cluster_footprint_union_m2", 0), int(area_m2))
    if n_off:
        counts["cluster_members_off_the_plane"] = \
            counts.get("cluster_members_off_the_plane", 0) + n_off
        counts["cluster_worst_off_the_plane_cm"] = max(
            counts.get("cluster_worst_off_the_plane_cm", 0),
            int(round(abs(worst) * 100)))
    return [Family(
        id=fid, unit=unit_id or "",
        members=tuple(by_mi[m].m.resource for m in mems if m in by_mi),
        bodies=moved, contacts=n_contacts, zero_z=zero, pad=where,
        spread_before_m=((max(gz) - min(gz)) if gz else 0.0),
        spread_after_m=0.0, apart=())]


def bind_families(cands: list, staged: _t.Sequence[_t.Any],
                  surface: _ar.Surface, pads: _t.Sequence[_ar.PadRing],
                  counts: dict, *, unit_id: str = "",
                  contact_eps_m: float = 0.0, bind_ground_m: float = 0.0,
                  cluster_min_m2: float = 0.0,
                  has_deck: bool = False) -> list[Family]:
    """§16f APPLIED TO ONE UNIT.  ``cands`` and each ``staged`` member's
    ``raw`` / ``ground_off`` are mutated in place, exactly as
    :func:`placement_atom.bind_unit` mutates them — this runs AFTER it,
    so §16c (7)'s rigid clusters are formed and the family plane is the
    last word on a FOOTED body's zero.  The carried and elevated bodies
    are untouched: each rides a footed carrier by §15 and follows it onto
    the plane.

    A unit carrying a DECK member forms NO family (§16f (3), naming the
    case): OTHH's bridges put three decks 250 m apart on one row with
    their piers and clutter BESIDE the plate, §16e (3) is WITHDRAWN
    exactly because a footprint family there is PARTIAL, and a
    plan-contact family binds the same clutter by another route —
    measured, unit:6 came out 29 members at one zero with a member
    8.20 m off its own ground.  The deck is the only datum body of a
    bridge (§16e (2)) and its clutter rests on its own ground.

    §16f (7) A LARGE TERMINAL CLUSTER IS ONE UNIT ON ONE PAD (owner
    RULINGS 2026-09-13bj item 1).  A family whose FOOTPRINT UNION
    (:func:`union_area_m2`) exceeds ``cluster_min_m2`` is a CLUSTER, and
    for it (4)'s pad partition, (5)'s pavement clause and the pad-join
    ground bound are ALL withdrawn: every member — walls, roofs, floors,
    the interior furniture, the pieces standing on the apron — takes ONE
    zero, the plane of the CLUSTER PAD the design surface emitted for it
    (design spec §30 (4)).  The owner read the alternative at KCLT
    1.0.327: 13aq's partition put the terminal on two pad groups, and the
    passengers and seats, which have no pad of their own and no contact
    with one, were cut to the ground UNDER the building.  A member whose
    own contacts stand further than ``bind_ground_m`` off the plane is
    REPORTED here (``cluster_members_off_the_plane``) and seated anyway —
    that is the whole of "seated as a unit".

    Returns the families derived, for the census."""
    if contact_eps_m <= 0.0 or not cands:
        return []
    if has_deck:
        counts["family_units_with_a_deck"] = \
            counts.get("family_units_with_a_deck", 0) + 1
        return []
    from . import placement_carrier as _pc
    by_mi = {st.mi: st for st in staged}
    families: list[Family] = []
    clusters, adj = _clusters(cands, contact_eps_m)
    # §16f (3): the unit's family-eligible population, and the partial
    # clusters that are NOT a family — reported, never bound
    eligible = sum(1 for c in cands
                   if c.body_class not in (_ar.LINE_SEGMENT, _ar.BASIN)
                   and (c.part_boxes or c.box))
    partial = [cl for cl in clusters
               if len(cl) <= FAMILY_SHARE_MIN * max(1, eligible)]
    if partial:
        counts["family_partial_clusters"] = \
            counts.get("family_partial_clusters", 0) + len(partial)
        counts["family_bodies_partial"] = \
            counts.get("family_bodies_partial", 0) + sum(len(c) for c in partial)
    bound_ci: set[int] = set()
    for cl in clusters:
        if len(cl) <= FAMILY_SHARE_MIN * max(1, eligible):
            continue
        # §16f (7): IS THIS A CLUSTER?  The FOOTPRINT UNION of the plan
        # cluster's own part boxes, measured before anything is cut away
        # from it — (5)'s pavement clause and (4)'s pad partition are
        # what a cluster withdraws, so neither may decide whether it is
        # one.
        area = union_area_m2([b for ci in cl for b in
                              (cands[ci].part_boxes or
                               ([cands[ci].box] if cands[ci].box else []))])
        is_cluster = cluster_min_m2 > 0.0 and area >= cluster_min_m2
        # every contact of the family, and the zero each body reads today
        per: dict[int, list] = {}
        zeros_before: list[float] = []
        n_paved = 0
        for ci in cl:
            c = cands[ci]
            st = by_mi.get(c.member)
            if st is None:
                continue
            cc = _contacts_of(c, st, surface)
            if not cc:
                continue
            # §16f (5) PAVEMENT IS KING (RULINGS 2026-09-13aq (ii)): a
            # body every ground contact of which stands on rolled-on
            # pavement is CUT APART from its family and stays on that
            # pavement — an object never moves the aircraft.  Round 1
            # held a KCLT terminal wall +2.99 m over the apron.
            #
            # IT YIELDS INSIDE A CLUSTER (§16f (7), RULINGS 2026-09-13bj
            # item 1): a wall standing on apron takes the cluster plane
            # and the apron under it is the design surface's business
            # (§30 (4)'s reach) — the owner ruled the terminal seats as
            # one unit and the apron around it may be flattened to it.
            if not is_cluster and _all_on_pavement(cc, surface):
                n_paved += 1
                continue
            per[ci] = cc
            if c.anchor.surface_z is not None:
                zeros_before.append(float(c.anchor.surface_z)
                                    - float(c.anchor.y_zero))
        if is_cluster and per:
            families.extend(_bind_cluster(
                cands, by_mi, surface, pads, counts, per, cl, area,
                unit_id=unit_id, bind_ground_m=bind_ground_m,
                bound_ci=bound_ci))
            continue
        if n_paved:
            counts["family_bodies_on_pavement"] = \
                counts.get("family_bodies_on_pavement", 0) + n_paved
        if len({cands[ci].member for ci in per}) < FAMILY_MIN_MEMBERS:
            continue
        # §16f (4) ONE PLANE PER PAD: each body joins the pad holding the
        # PLURALITY of its own ground contacts; a body on no pad joins
        # the group it touches; a body touching none is left out.
        pad_by_ref: dict[str, _ar.PadRing] = {}
        pad_of: dict[int, str] = {}
        for ci, cc in per.items():
            step = max(1, len(cc) // FAMILY_CONTACTS_MAX)
            p = pad_plurality(cc[::step], pads)
            if p is not None:
                pad_of[ci] = p.ref
                pad_by_ref[p.ref] = p
        groups = _pad_groups(sorted(per), pad_of, adj)
        fid0 = f"{unit_id or 'unit'}#{cl[0]}"
        for ref, gis in groups.items():
            pad = pad_by_ref.get(ref)
            # THE PAD'S PLANE: the median of the group's contacts that
            # stand INSIDE the pad ring — never the ones a footprint
            # spills onto the apron beside it (§16d (6)'s own reading,
            # taken over the group instead of one body).
            on: list[float] = []
            allc: list[float] = []
            n_contacts = 0
            for ci in gis:
                cc = per[ci]
                step = max(1, len(cc) // FAMILY_CONTACTS_MAX)
                n_contacts += len(cc)
                for q in cc[::step]:
                    allc.append(q[3] - q[2])
                    if pad is not None and _ar._inside(pad.ring, q[0], q[1]):
                        on.append(q[3] - q[2])
            # §16f (4): EACH PAD GROUP TAKES ITS PAD'S PLANE — the
            # median of the PAD's own graded vertices, so ONE pad is ONE
            # plane however many families stand on it and whichever unit
            # the walk reaches first.  Measured: KCLT's two terminal rows
            # read their own on-pad contacts as 221.78 and 221.45, and
            # the 0.33 m between them is the pad's own relief sampled
            # twice, not two authorings.  The group's own on-pad contacts
            # are the fallback where the caller read a pad without its
            # heights (every twin that builds one by hand).
            zero = (_median(pad.z) if pad is not None and pad.z
                    else _median(on or allc))
            fid = f"{fid0}@{ref}"
            mems = sorted({cands[ci].member for ci in gis})
            gz = [cands[ci].anchor.surface_z - cands[ci].anchor.y_zero
                  for ci in gis if cands[ci].anchor.surface_z is not None]
            moved = 0
            n_far = 0
            for ci in gis:
                c = cands[ci]
                cc = per[ci]
                st = by_mi[c.member]
                # §16f (4) + §16d (5): THE GROUND BOUND HOLDS AT THE PAD
                # JOIN TOO.  §16c (7)'s bind already refuses where the
                # two bodies' own grounds disagree by more than
                # ``bind_ground_m`` (12ap (A)); the pad join needs the
                # same arbiter, because the members a pad group picks up
                # BY CONTACT (§16c (6)) are exactly the ones standing off
                # the pad on real relief — measured, they came out +4.44
                # (KCLT), +8.92 (LEMD), +12.21 m (OTHH) above their own
                # ground.  A member further than the bound from the pad's
                # plane is CUT TO ITS OWN GROUND (§16c) and counted.
                # THE BOUND AND THE CENSUS READ THE SAME SAMPLE: the
                # census is ``placement_boxes.anchor_ground_off``, which
                # steps the feet down to ``GROUND_OFF_FEET_MAX``; testing
                # on every foot instead let LEMD's worst member read 0.54
                # against a 0.50 bound the walk thought it had met.
                if bind_ground_m > 0.0:
                    _st = max(1, len(cc) // _pb.GROUND_OFF_FEET_MAX)
                    own_zs = [q[3] - q[2] for q in cc[::_st]]
                    if abs(_median(own_zs) - zero) > bind_ground_m:
                        n_far += 1
                        continue
                best = min(cc, key=lambda q: (round(abs(q[3] - q[2] - zero), 6),
                                              round(abs(q[2]), 6), q[0], q[1]))
                own = best[3] - best[2]
                a = _ar.Anchor(
                    c.anchor.body_class, best[0], best[1], best[3] - zero,
                    f"§16f family {fid} of {len(mems)} member(s) on "
                    f"pad {ref} at {zero:.2f} "
                    f"(own ground {own - zero:+.2f} m)",
                    best[3], family=fid)
                grp0 = (st.groups[c.group]
                        if 0 <= c.group < len(st.groups) else ())
                if not grp0:
                    continue
                k0 = _pc.senior_of(st.raw, grp0)
                r0 = st.raw[k0]
                st.raw[k0] = (r0[0], r0[1], a) + tuple(r0[3:])
                _off = _pb.anchor_ground_off(
                    a, tuple(f for j in grp0 for f in st.raw[j][3]), surface)
                if c.group < len(st.ground_off):
                    st.ground_off[c.group] = _off
                cands[ci] = _dc.replace(c, anchor=a, ground_off=_off)
                bound_ci.add(ci)
                moved += 1
            if n_far:
                counts["family_bodies_off_the_pad_plane"] = \
                    counts.get("family_bodies_off_the_pad_plane", 0) + n_far
            if not moved:
                continue
            counts["bodies_bound_to_family"] = \
                counts.get("bodies_bound_to_family", 0) + moved
            counts["family_pad_groups"] = \
                counts.get("family_pad_groups", 0) + 1
            families.append(Family(
                id=fid, unit=unit_id or "",
                members=tuple(by_mi[m].m.resource for m in mems if m in by_mi),
                bodies=moved, contacts=n_contacts, zero_z=zero, pad=ref,
                spread_before_m=((max(gz) - min(gz)) if gz else 0.0),
                spread_after_m=0.0, apart=()))
        if groups:
            counts["families"] = counts.get("families", 0) + 1
        # a body of the family that touches NO pad group is cut to its
        # own ground (§16f (4) / §16c) — counted, never silent
        loose = [ci for ci in per if ci not in bound_ci]
        if loose:
            counts["family_bodies_off_every_pad"] = \
                counts.get("family_bodies_off_every_pad", 0) + len(loose)
    if families:
        fam_members = {m for f in families for m in f.members}
        names = tuple(sorted(
            {f"{cands[ci].resource}" for ci, c in enumerate(cands)
             if ci not in bound_ci
             and c.body_class not in (_ar.LINE_SEGMENT, _ar.BASIN)
             and by_mi.get(c.member) is not None
             and by_mi[c.member].m.resource in fam_members}))
        if names:
            families = [_dc.replace(f, apart=names) for f in families]
            counts["family_bodies_apart"] = \
                counts.get("family_bodies_apart", 0) + len(names)
    return families


# ── §16f (3): THE CENSUS ─────────────────────────────────────────────────

def census_families(splits: _t.Sequence[_t.Mapping[str, _t.Any]],
                    surface=None) -> dict:
    """§16f (3)'s CENSUS over a written placement plan's own rows — the
    same shape and code path every other census in ``placement_census``
    reads (``plan["splits"]``), so the tool and the engine print one
    number.

    Per family (``family_of``): members, bodies, the one zero plane, its
    per-body zero SPREAD (the bar: <= 0.3 m), and — where a surface is
    handed in — the worst |zero - ground| over the family's own written
    geometry, which is what "no member floating or sunken more than
    0.5 m against the pad" reads.  Plus the bodies of a family's own
    members that were CUT APART (no ``family_of``: they stood beyond
    ``contact_eps_m`` from every other footprint) and the placements a
    family spans."""
    fam: dict[str, dict] = {}
    apart: dict[str, int] = {}
    for s in splits:
        res = s.get("placement", {}).get("resource", "")
        for b in s.get("bodies", ()):
            key = b.get("family_of") or ""
            z = b.get("surface_z")
            y = b.get("y_zero")
            if not key:
                if res:
                    apart[res] = apart.get(res, 0) + 1
                continue
            d = fam.setdefault(key, {"bodies": 0, "resources": set(),
                                     "zeros": [], "off": [], "pad": ""})
            d["bodies"] += 1
            d["resources"].add(res)
            if not d["pad"]:
                why = str(b.get("anchor_reason", ""))
                if (("§16f family" in why or "§16f (7) cluster" in why
                     or "§16g unit" in why) and " on pad " in why):
                    d["pad"] = why.split(" on pad ", 1)[1].split(" at ")[0]
            if z is not None and y is not None:
                d["zeros"].append(float(z) - float(y))
            # THE FLOAT AGAINST THE PAD is the body's OWN-FEET reading
            # (``ground_off``, §16a (2): zero - median(surface(foot) -
            # y_foot)) and never the whole written geometry's: a roof
            # plate's lowest written vertex is authored +27 m and reading
            # it called the family 27.51 m off its ground.  A carried
            # body has no feet and publishes none.
            if b.get("ground_off") is not None:
                d["off"].append(float(b["ground_off"]))
    out = {}
    for k, d in fam.items():
        zs = d["zeros"]
        out[k] = {"bodies": d["bodies"], "pad": d["pad"],
                  "resources": sorted(d["resources"]),
                  "zero": (sum(zs) / len(zs)) if zs else None,
                  "spread": (max(zs) - min(zs)) if zs else 0.0,
                  "worst_off": (max(d["off"], key=abs) if d["off"] else None)}
    return {"families": out,
            "apart": {r: n for r, n in sorted(apart.items())
                      if any(r in f["resources"] for f in out.values())}}


def census_families_lines(c: _t.Mapping[str, _t.Any],
                          spread_m: float = 0.3,
                          visual_m: float = 0.5) -> list[str]:
    """The block the report prints (``obj8_split_report`` /
    ``seat_feet_census``)."""
    fams = c.get("families", {})
    out = ["§16f THE OBJECT FAMILY (spec §16f, RULINGS 2026-09-13af)"]
    if not fams:
        out.append("  no family: no unit's footed bodies form one plan "
                   "cluster of two or more members (§16f (1)(b))")
        return out
    worst = max((f["spread"] for f in fams.values()), default=0.0)
    out.append(f"  {len(fams)} family(ies), "
               f"{sum(f['bodies'] for f in fams.values())} body(ies); worst "
               f"per-body zero spread {worst:.2f} m "
               f"({'PASS' if worst <= spread_m else 'OVER'} {spread_m:g} m)")
    for k in sorted(fams, key=lambda k: -fams[k]["bodies"]):
        f = fams[k]
        off = f["worst_off"]
        bar = ("" if off is None else
               f", worst |zero - the ground under its OWN FEET| {off:+.2f} m "
               f"({'PASS' if abs(off) <= visual_m else 'OVER'} {visual_m:g} m "
               f"- a member standing on real relief is held UP by the "
               f"family, §16f (2))")
        out.append(f"  {k}: {len(f['resources'])} member(s), {f['bodies']} "
                   f"body(ies) on "
                   + (f"pad {f['pad']}" if f["pad"] else "its median ground")
                   + ", one zero "
                   + ("-" if f["zero"] is None else "%.2f" % f["zero"])
                   + f", "
                   f"spread {f['spread']:.2f} m{bar}")
    if c.get("apart"):
        out.append("  members cut apart (§16f (2), on their own ground): "
                   + ", ".join(f"{r.rsplit('/', 1)[-1]} x{n}"
                               for r, n in sorted(c["apart"].items())))
    return out
