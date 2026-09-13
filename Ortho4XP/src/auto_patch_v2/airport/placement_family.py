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

import dataclasses as _dc
import typing as _t

from . import anchor_rule as _ar
from . import placement_boxes as _pb

__all__ = ["Family", "FAMILY_MIN_MEMBERS", "FAMILY_SHARE_MIN",
           "bind_families", "census_families", "census_families_lines"]

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


def _clusters(cands: _t.Sequence[_t.Any], eps_m: float) -> list[list[int]]:
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
    if len(live) < FAMILY_MIN_MEMBERS:
        return []
    boxes = {i: (list(cands[i].part_boxes) or [cands[i].box]) for i in live}
    hull = {i: _pb.hull_of(boxes[i]) for i in live}
    live = [i for i in live if hull[i] is not None]
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
    for ai, a in enumerate(order):
        north = hull[a][2]
        for b in order[ai + 1:]:
            if hull[b][0] > north:
                break
            if find(a) == find(b) or _pb.box_gap_m(hull[a], hull[b]) > eps_m:
                continue
            if any(_pb.box_gap_m(x, y) <= eps_m
                   for x in boxes[a] for y in boxes[b]):
                parent[find(a)] = find(b)
    out: dict[int, list[int]] = {}
    for i in live:
        out.setdefault(find(i), []).append(i)
    # a cluster is a FAMILY only where it spans more than one MEMBER:
    # one member's own bodies are already one object to §14 (3) / §16c
    return [sorted(v) for _k, v in sorted(out.items(),
                                          key=lambda kv: min(kv[1]))
            if len({cands[i].member for i in v}) >= FAMILY_MIN_MEMBERS]


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


def bind_families(cands: list, staged: _t.Sequence[_t.Any],
                  surface: _ar.Surface, pads: _t.Sequence[_ar.PadRing],
                  counts: dict, *, unit_id: str = "",
                  contact_eps_m: float = 0.0,
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
    clusters = _clusters(cands, contact_eps_m)
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
        # every contact of the family, and the zero each body reads today
        per: list[tuple[int, list]] = []
        contacts: list[tuple[float, float, float, float]] = []
        zeros_before: list[float] = []
        for ci in cl:
            c = cands[ci]
            st = by_mi.get(c.member)
            if st is None:
                continue
            cc = _contacts_of(c, st, surface)
            if not cc:
                continue
            per.append((ci, cc))
            contacts.extend(cc)
            if c.anchor.surface_z is not None:
                zeros_before.append(float(c.anchor.surface_z)
                                    - float(c.anchor.y_zero))
        if (not contacts
                or len({cands[ci].member for ci, _ in per})
                < FAMILY_MIN_MEMBERS):
            continue
        step = max(1, len(contacts) // FAMILY_CONTACTS_MAX)
        sample = contacts[::step]
        # §16f (2): THE PAD THE FAMILY STANDS ON, else its own ground
        pad = _ar.pad_majority(sample, pads)
        if pad is not None:
            on = [q for q in sample if _ar._inside(pad.ring, q[0], q[1])]
        else:
            on = list(sample)
        zero = _median([q[3] - q[2] for q in on])
        # §16f (2): EVERY MEMBER ANCHORS ON THAT PLANE.  The anchor point
        # stays the body's OWN — the contact whose own ground stands
        # nearest the family's zero — and ``y_zero`` is what puts the
        # plane there (§16e's shape: an authored height at a chosen
        # ground, not the ground under a foot).
        pad_ref = pad.ref if pad is not None else ""
        fid = f"{unit_id or 'unit'}#{cl[0]}"
        mems = sorted({cands[ci].member for ci, _ in per})
        moved = 0
        for ci, cc in per:
            c = cands[ci]
            st = by_mi[c.member]
            best = min(cc, key=lambda q: (round(abs(q[3] - q[2] - zero), 6),
                                          round(abs(q[2]), 6), q[0], q[1]))
            own = best[3] - best[2]
            a = _ar.Anchor(
                c.anchor.body_class, best[0], best[1], best[3] - zero,
                f"§16f family {fid} of {len(mems)} member(s) on "
                + (f"pad {pad_ref}" if pad_ref else "its median ground")
                + f" at {zero:.2f} (own ground {own - zero:+.2f} m)",
                best[3], family=fid)
            grp0 = st.groups[c.group] if 0 <= c.group < len(st.groups) else ()
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
        counts["bodies_bound_to_family"] = \
            counts.get("bodies_bound_to_family", 0) + moved
        counts["families"] = counts.get("families", 0) + 1
        spread_before = ((max(zeros_before) - min(zeros_before))
                         if zeros_before else 0.0)
        families.append(Family(
            id=fid, unit=unit_id or "",
            members=tuple(by_mi[m].m.resource for m in mems
                           if m in by_mi),
            bodies=moved, contacts=len(contacts), zero_z=zero, pad=pad_ref,
            spread_before_m=spread_before, spread_after_m=0.0,
            apart=()))
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
                if "§16f family" in why and " on pad " in why:
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
