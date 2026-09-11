"""THE CONTACT-CLUSTER SEAT (RULINGS 2026-09-06g; v1's
``object_clusters.form_clusters`` + ``object_anchor._build_structure_clusters``
/ ``_seat_clusters`` as v2 code — v2 never imports v1).

Over the plan's parts and contact edges (``airport/contact.py``), after
the mesh:

* every GROUND part reads the mesh under its OWN FEET (RULINGS
  2026-09-09s (2)): its SEAT TARGET is the median over its feet of
  ``mesh z − the foot's authored y`` — the world elevation of its
  object's ``y = 0`` plane that lands the component on the mesh (with a
  single foot at the centroid carrying ``base_y`` this is the pre-09s
  ``ground − base_y``).  GROUND is still ``base_y ≤ elevated_base_m``,
  and the plan carries the verdict by carrying the feet.  A part
  none of whose feet lands on the mesh (water with ``water_founds_seat``
  off, or off the mesh) is UNMEASURED and never votes (merge on doubt
  survives for it);
* the CUT (RULINGS 2026-09-10i (1)): a ground-to-ground edge ACROSS TWO
  PLACEMENTS whose measured seat targets differ by more than
  ``cluster_seat_tolerance_m`` is cut; an edge INSIDE one placement is
  NEVER cut — two touching components of one authored placement are one
  BODY.  The connected components of the kept ground edges are the
  CLUSTERS (the bodies);
* ELEVATED parts never vote (10i (3)): they are assigned by multi-source
  BFS over the contact graph FROM the bodies' ground parts — the body
  TOUCHED, transitively, never a contact-count vote.  The BFS assigns a
  COHESION GROUP, not a part (RULINGS 2026-09-10u (1)): elevated
  components of ONE placement that touch each other are one group and
  take ONE body, because assigning them independently tore LEMD's
  terminals (1,679 of 2,345 torn intra-placement edges were elevated x
  elevated — the plate at +3.550 and the wall it rests on at -5.621,
  0.089 m apart).  A group never BRIDGES two bodies: where it touches
  several it joins the one whose touched part has the largest PLAN
  OVERLAP with it — the wall it rests on — then a body holding a ground
  part of the same placement, then the lowest body id.  A group touching
  NOTHING joins the nearest body only within
  ``identity.min_distinct_spacing_m`` x 4, else it is HELD;
* a STRUCTURE-seated member (a deck plate at its abutment grade, a plate
  family) is a FIXED cluster with the structure's delta: the parts of its
  own deck-family members reached through contact join it (a pier, a
  railing), every other ground part's contact with it is DROPPED — a
  deck never founds the ground parts around or under it;
* the SEAT: a body's ground is the MEDIAN SEAT TARGET of its measured
  ground parts, and EVERY part of the body takes it (10i (2), superseding
  09s (2)'s per-part own target; the per-foot residual is REPORTED on the
  seat, never written).  A body wider than ``body_feet_span_m`` carrying
  fewer than one measured foot per that span samples the design surface
  under every ground-contact part's footprint centroid as extra feet;
  the delta is that target minus ``base(resource)`` (v1 I-3: the
  anchor spelling is only the subtrahend), written per vertex; a cluster
  whose largest part delta is under ``min_delta_m`` STAYS; a cluster no wider than ``a3_guard_max_diameter_m``
  whose single offset would worsen the mean ground-part residual is
  REFUSED (v1 A3); ground relief over ``cluster_span_pad_m`` bakes and
  pads; ground parts left further than ``cluster_residual_pad_m`` off the
  mesh raise PAD REQUESTS by connected group (reported);
* THE FACILITY RULE at cluster level (05p / 05q): within one STRUCTURE
  (a contact component), a cluster standing more than ``[basin]
  contact_band_m`` under the mesh AND that much beyond the structure's
  agreeing coalition of cluster lifts is a FACILITY cluster: never
  seated, authored y kept (the cutout is the basin pass's affair); a
  structure sunk uniformly lifts as one.

Pure bookkeeping over the plan and the samples; no I/O.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import statistics
import typing as _t

from ..model.rebake import ClusterSeat, PadRequest, Part, RebakePlan

__all__ = ["Outcome", "MemberParts", "seat_clusters", "metres_per_degree", "coalition"]

#: ``sampler(lat, lon) -> (z, is_water)`` or ``None`` off the mesh.
Sampler = _t.Callable[[float, float], "tuple[float, bool] | None"]
MemberKey = tuple[int, int]          # (unit index, member index)


def metres_per_degree(lat: float) -> tuple[float, float]:
    """``(m per degree of latitude, m per degree of longitude)``."""
    m_lat = 111_132.954 - 559.822 * math.cos(2 * math.radians(lat)) \
        + 1.175 * math.cos(4 * math.radians(lat))
    m_lon = 111_412.84 * math.cos(math.radians(lat)) - 93.5 * math.cos(3 * math.radians(lat))
    return m_lat, m_lon


def _plan_overlap_m2(a: tuple[float, float, float, float],
                     b: tuple[float, float, float, float]) -> float:
    """The overlap AREA of two plan boxes ``(min_lat, min_lon, max_lat,
    max_lon)`` in m² — the "which wall does it rest on" measure of
    RULINGS 2026-09-10u (1); ``0.0`` when they do not overlap."""
    dla = min(a[2], b[2]) - max(a[0], b[0])
    dlo = min(a[3], b[3]) - max(a[1], b[1])
    if dla <= 0.0 or dlo <= 0.0:
        return 0.0
    m_lat, m_lon = metres_per_degree((max(a[0], b[0]) + min(a[2], b[2])) / 2.0)
    return dla * m_lat * dlo * m_lon


def coalition(values: _t.Sequence[float], window: float) -> tuple[list[float] | None, str]:
    """The largest ≥2-member subset within ``window`` that strictly
    out-numbers every rival subset; ``(None, why)`` on a tie or none."""
    if len(values) < 2:
        return None, "single member"
    order = sorted(range(len(values)), key=lambda i: values[i])
    vs = [values[i] for i in order]
    best: list[frozenset[int]] = []
    best_n = 1
    for i in range(len(vs)):
        j = i
        while j + 1 < len(vs) and vs[j + 1] - vs[i] <= window:
            j += 1
        n = j - i + 1
        if n > best_n:
            best_n, best = n, [frozenset(order[i:j + 1])]
        elif n == best_n and n >= 2:
            s = frozenset(order[i:j + 1])
            if s not in best:
                best.append(s)
    if best_n < 2:
        return None, "no two members agree within the window"
    if len(best) > 1:
        return None, f"tie: {len(best)} rival coalitions of {best_n}"
    return [values[i] for i in sorted(best[0])], ""


@_dc.dataclass
class MemberParts:
    """What the seat learned about one member's parts."""

    part_deltas: list[tuple[int, int, float | None]] = _dc.field(default_factory=list)
    #: THE SEGMENT SEAT (10bb rule 3): ``(comp, lat, lon, delta)`` rows a
    #: LINE component drapes on — every vertex takes the nearest one.
    line_stations: list[tuple[int, float, float, float]] = _dc.field(default_factory=list)
    witnesses: int = 0
    water: int = 0
    off_mesh: int = 0
    outliers: int = 0
    grounds: list[float] = _dc.field(default_factory=list)
    n_ground: int = 0
    n_facility: int = 0
    clusters: set[int] = _dc.field(default_factory=set)

    @property
    def facility(self) -> bool:
        return self.n_ground > 0 and self.n_facility == self.n_ground

    @property
    def ground_m(self) -> float | None:
        return float(statistics.median(self.grounds)) if self.grounds else None

    @property
    def one_delta(self) -> float | None:
        ds = {d for _c, _k, d in self.part_deltas}
        if len(ds) == 1 and None not in ds:
            return next(iter(ds))
        return None


@_dc.dataclass
class Outcome:
    clusters: list[ClusterSeat]
    members: dict[MemberKey, MemberParts]
    pad_requests: list[PadRequest]
    cut_edges: int
    structures: int
    #: RULINGS 2026-09-10i (1): ground-to-ground edges INSIDE one placement
    #: whose feet disagree by more than ``cluster_seat_tolerance_m`` and
    #: which are therefore KEPT (the cuts 10i forbids).
    intra_placement_kept: int = 0
    #: 10i (3): parts touching no body within the identity spacing × 4.
    held_parts: int = 0
    #: RULINGS 2026-09-10u (1): the intra-placement ELEVATED cohesion
    #: groups the BFS assigned as one, and how many of them resolved on
    #: no plan overlap at all (the residual body-id tie).
    elevated_groups: int = 0
    group_ties: int = 0
    #: RULINGS 2026-09-10bb (spec §16): line-object bodies, the contact
    #: edges their rule refused to bind, and the ORPHAN bodies rule 4
    #: seated by sampling (before 10bb they were held, or dragged to the
    #: nearest body — the fence's).
    line_bodies: int = 0
    line_edges_dropped: int = 0
    orphan_bodies: int = 0


class _UF:
    def __init__(self, keys: _t.Iterable[int]) -> None:
        self.p = {k: k for k in keys}

    def find(self, a: int) -> int:
        p = self.p
        while p[a] != a:
            p[a] = p[p[a]]
            a = p[a]
        return a

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)

    def components(self) -> list[list[int]]:
        g: dict[int, list[int]] = {}
        for k in sorted(self.p):
            g.setdefault(self.find(k), []).append(k)
        return [g[r] for r in sorted(g)]


@_dc.dataclass
class _P:
    pid: int
    key: MemberKey
    part: Part
    base: float | None          # the member's rendered y = 0 plane (None: anchor off the mesh)
    ground: bool
    feet: tuple[tuple[float, float, float], ...] = ()
    #: THE SEAT TARGET (RULINGS 2026-09-09s (2)): the world elevation of
    #: this object's ``y = 0`` plane that lands the part's own FEET on the
    #: mesh — the median over its feet of ``mesh z − the foot's authored
    #: y``.  With one foot at the centroid carrying ``base_y`` this is
    #: literally the pre-09s ``z − base_y``.
    target: float | None = None
    #: THE LOW-SIDE READING (owner RULINGS 2026-09-10ag; spec §22.3): the
    #: MINIMUM over the same feet, which lands the part's LOWEST foot on
    #: the mesh.  A skirted body seats on this instead of ``target``: the
    #: low side touches the ground and the high side buries into the
    #: skirt.  ``None`` exactly when ``target`` is.
    low: float | None = None
    water: bool = False
    off: bool = False
    #: THE LINE OBJECT (owner RULINGS 2026-09-10bb, spec §16): a fence /
    #: kerb / jet-blast line / light string component.  It binds nothing,
    #: founds no foot for anything else, is its OWN body, and is seated
    #: PER SEGMENT on its stations (``feet``).
    line: bool = False
    #: THE DRAPE STATIONS of a line part (10bb rule 3): ``(lat, lon, seat
    #: target)`` per foot that read the design surface.  Empty for a part
    #: the seat never sampled (off the mesh, on water, structure-seated).
    stations: tuple[tuple[float, float, float], ...] = ()
    fixed: str | None = None    # the unit id of a structure seat this part follows
    family: str | None = None   # the unit id of the deck family this part may attach to

    @property
    def measured(self) -> bool:
        return self.target is not None

    @property
    def lift(self) -> float | None:
        return None if self.target is None or self.base is None else self.target - self.base


def _diameter(parts: _t.Sequence[_P]) -> float:
    if not parts:
        return 0.0
    la0 = min(p.part.box[0] for p in parts); lo0 = min(p.part.box[1] for p in parts)
    la1 = max(p.part.box[2] for p in parts); lo1 = max(p.part.box[3] for p in parts)
    m_lat, m_lon = metres_per_degree((la0 + la1) / 2.0)
    return math.hypot((la1 - la0) * m_lat, (lo1 - lo0) * m_lon)


def seat_clusters(plan_: RebakePlan, sampler: Sampler, law, base_by_member: _t.Mapping[MemberKey, float | None],
                  fixed: _t.Mapping[MemberKey, tuple[str, float]],
                  family: _t.Mapping[MemberKey, str],
                  authored: _t.Mapping[int, float] | None = None,
                  stay: _t.Collection[str] = ()) -> Outcome:
    """The cluster seat (module doc).  ``base_by_member`` is each
    member's rendered ``y = 0`` plane (``None``: its anchor is off the
    mesh, its parts are held); ``fixed`` maps a structure-seated member
    to ``(unit id, delta)``; ``family`` maps a deck-family member to the
    unit id of the deck it may attach to; ``authored`` (RULINGS
    2026-09-08d e, the flat-site datum under the footprint) maps a part
    id to the ground it reads INSTEAD of the mesh — its object's authored
    ``y = 0`` plane, so the seat lands the plane where the pack put it
    (delta 0) and the pack's seat stands; ``stay`` names the fixed units
    that STAY (a structure seat under the threshold, 08d d): their parts
    and whatever inherits their cluster carry no delta."""
    rb = law.tables.structures.rebake
    band = law.tables.structures.basin.contact_band_m
    # THE GROUND VERDICT (RULINGS 2026-09-09s (2)) travels in the plan: a
    # part carries FEET when the partition judged it GROUND against its
    # contact structure's floor.  A plan written before 09s carries none,
    # and every part falls back to the file-relative test with ONE foot at
    # its centroid carrying ``base_y`` — the pre-09s reading exactly.
    has_feet = any(p.feet for u in plan_.units for m in u.members for p in m.parts)
    ps: dict[int, _P] = {}
    for ui, u in enumerate(plan_.units):
        for mi, m in enumerate(u.members):
            key = (ui, mi)
            for p in m.parts:
                feet = tuple(p.feet) or ((p.lat, p.lon, p.base_y),)
                ps[p.pid] = _P(p.pid, key, p, base_by_member.get(key),
                               bool(p.feet) if has_feet else p.base_y <= rb.elevated_base_m,
                               feet,
                               fixed=fixed.get(key, (None, 0.0))[0] if key in fixed else None,
                               family=family.get(key),
                               # a STRUCTURE-seated member is never a line
                               # object (spec §16.1 rule 1 / 14.1 rule 4):
                               # its deck / plate seat governs it, whatever
                               # shape the plan read
                               line=bool(getattr(p, "line", False))
                               and key not in fixed and key not in family)
    # ── the samples: every ground part's own FEET ───────────────────────
    for p in ps.values():
        if not p.ground or p.fixed or p.base is None:
            continue
        if authored and p.pid in authored:
            # 08d (e): the pack's authored y = 0 plane IS this part's ground
            p.target = p.low = float(authored[p.pid])
            continue
        ts: list[float] = []
        st: list[tuple[float, float, float]] = []
        for la, lo, y in p.feet:
            smp = sampler(la, lo)
            if smp is None:
                p.off = True
            elif smp[1] and not rb.water_founds_seat:
                p.water = True
            else:
                t = float(smp[0]) - float(y)
                ts.append(t)
                if p.line:
                    st.append((float(la), float(lo), t))
        p.stations = tuple(st)
        if ts:
            p.target = float(statistics.median(ts))
            p.low = float(min(ts))
            p.off = p.water = False
    edges = [(a, b) for a, b in plan_.contacts if a in ps and b in ps
             and ps[a].base is not None and ps[b].base is not None]
    # ── structures: components of the whole contact graph ───────────────
    struct = _UF(ps)
    for a, b in edges:
        struct.union(a, b)
    struct_of = {pid: struct.find(pid) for pid in ps}
    # ── the deck-attached parts: fixed parts + family parts reached through family parts
    fixed_key: dict[int, str] = {p.pid: p.fixed for p in ps.values() if p.fixed}
    adj: dict[int, list[int]] = {}
    for a, b in edges:
        adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
    attached: dict[int, str] = dict(fixed_key)
    stack = list(fixed_key)
    while stack:
        a = stack.pop()
        uid = attached[a]
        for b in adj.get(a, ()):
            if b not in attached and ps[b].family == uid:
                attached[b] = uid
                stack.append(b)
    # ── the cut (spec §3.2) ─────────────────────────────────────────────
    ground_ids = [pid for pid, p in ps.items() if p.ground or pid in attached]
    # the BODY union-find spans EVERY part (RULINGS 2026-09-10u (1)): an
    # intra-placement contact edge binds whatever it joins — ground to
    # ground, ground to elevated, elevated to elevated — so ONE PLACEMENT'S
    # TOUCHING SET IS ONE BODY, exactly as 10i (1) says, and the components
    # that hold no ground part at all are the FREE GROUPS the BFS assigns.
    guf = _UF(list(ps))
    by_unit: dict[str, list[int]] = {}
    for pid, uid in attached.items():
        by_unit.setdefault(uid, []).append(pid)
    for pids in by_unit.values():
        for pid in pids[1:]:
            guf.union(pids[0], pid)
    kept: list[tuple[int, int]] = []
    free_ids = [pid for pid, p in ps.items() if not p.ground and pid not in attached]
    euf = _UF(free_ids)
    n_cut = n_intra_kept = 0
    n_line_edges = 0
    for a, b in edges:
        pa, pb = ps[a], ps[b]
        # THE LINE OBJECT BINDS NOTHING (owner RULINGS 2026-09-10bb, spec
        # §16.1 rule 2): a fence's contact edge is a physical fact and
        # stays in the plan, but it forms no body and founds no foot —
        # at LEMD one LEMDzaun component chained 38 parts of 5 resources
        # over 1,406 m onto its single foot, and Terminal4_green-LEMD50
        # came out 6.86 m under its own ground.
        if pa.line or pb.line:
            n_line_edges += 1
            continue
        a_att, b_att = a in attached, b in attached
        if a_att and b_att:
            continue                            # one structure seat, or two decks touching: apart
        if a_att or b_att:
            continue                            # a deck founds nothing around it; the BFS below
            #                                     hands its free neighbours to the deck's cluster
        if pa.ground and pb.ground:
            ta, tb = pa.target, pb.target      # the feet-founded y = 0 planes
            # THE CUT APPLIES ONLY ACROSS PLACEMENTS (RULINGS 2026-09-10i
            # (1)): a contact edge INSIDE one authored placement is NEVER
            # cut — two touching components of one placement are ONE BODY
            # with ONE delta, and a placement carries several deltas only
            # across a physical separation (no contact edge at all).  At
            # LEMD 13,979 of 23,371 edges are intra-placement and 929 cuts
            # tore car-park walls, terminal facades and their deck plates
            # metres apart under the design surface.
            if pa.key != pb.key and rb.cluster_seat_tolerance_m > 0.0 \
                    and ta is not None and tb is not None \
                    and abs(ta - tb) > rb.cluster_seat_tolerance_m:
                n_cut += 1
                continue
            if pa.key == pb.key and ta is not None and tb is not None \
                    and rb.cluster_seat_tolerance_m > 0.0 \
                    and abs(ta - tb) > rb.cluster_seat_tolerance_m:
                n_intra_kept += 1
            kept.append((a, b))
            guf.union(a, b)
        else:
            if not (pa.ground or pb.ground):
                euf.union(a, b)
            # RULINGS 2026-09-10u (1), widened — see spec §15.  An
            # intra-placement edge with an ELEVATED end binds too: before
            # 10u each elevated part was assigned INDEPENDENTLY by the
            # BFS, in the same round, from whatever ground it reached, so
            # two touching components of one file landed metres apart.
            # At LEMD 2,345 intra-placement contact edges carried
            # different deltas — 1,679 of them elevated x elevated,
            # including the worst site (Terminal4SAT_Yellow-LEMD11 plate
            # c5153 +3.550 against wall c3104 -5.621, 0.089 m apart, BOTH
            # elevated).  Across placements nothing changes: the elevated
            # end is still assigned by the BFS and never bridges two
            # bodies (10i (3)).
            if pa.key == pb.key:
                guf.union(a, b)
            elif pa.ground or pb.ground:
                continue
    # A component holding at least one GROUND (or deck-attached) part is a
    # BODY; one made only of elevated parts founds nothing and is a FREE
    # GROUP the BFS below assigns whole (10i (3): it joins one body, it
    # never bridges two).
    all_comps = guf.components()
    comps = [c for c in all_comps if any(ps[pid].ground or pid in attached for pid in c)]
    free_groups = [c for c in all_comps if not any(ps[pid].ground or pid in attached
                                                   for pid in c)]
    cluster_of: dict[int, int] = {}
    for k, pids in enumerate(comps):
        for pid in pids:
            cluster_of[pid] = k
    members_of: dict[int, list[int]] = {k: list(pids) for k, pids in enumerate(comps)}
    # A LINE BODY is one line part alone (10bb rule 2): nothing joins it —
    # not the elevated BFS, not the nearest-body fallback.  A building
    # that touched only the fence must find its OWN ground (rule 4), not
    # ride the fence a second time through the fallback.
    line_body_ks = {k for k, pids in members_of.items()
                    if len(pids) == 1 and ps[pids[0]].line}
    # ── PLATES FOLLOW THE BODY THEY TOUCH (RULINGS 2026-09-10i (3)) ─────
    # Multi-source BFS over the contact graph FROM the bodies' ground (and
    # structure-seated) parts: an elevated part takes the body it touches,
    # transitively — never a contact-count vote against a touching wall
    # (LEMD13's deck plates went to c142 on 20 contacts against the c64
    # they also touch).  An elevated part NEVER bridges two bodies: it
    # joins one, it does not merge them.  A tie at equal hop distance
    # resolves to a body holding a ground part of the SAME placement, then
    # to the lowest body id.
    #
    # RULINGS 2026-09-10u (1): the BFS assigns a COHESION GROUP — the
    # touching set of ELEVATED components of one placement — never a
    # single part, so two touching elevated components of one file can
    # never land in different bodies; and where a group touches several
    # bodies the tie resolves to THE WALL IT RESTS ON (the largest plan-
    # footprint overlap between a group part and the touched part), then
    # to a body holding a ground part of the same placement, and only
    # then to the lowest body id.
    keys_of: dict[int, set[MemberKey]] = {}
    for k, pids in members_of.items():
        keys_of[k] = {ps[pid].key for pid in pids}
    groups: dict[int, list[int]] = {g: list(pids) for g, pids in enumerate(free_groups)}
    n_groups = len(groups)
    n_group_ties = 0
    unassigned = sorted(groups)
    while unassigned:
        found: dict[int, int] = {}
        for g in unassigned:
            best: tuple[float, int, int] | None = None
            for pid in groups[g]:
                p = ps[pid]
                for n in adj.get(pid, ()):
                    k = cluster_of.get(n)
                    if k is None or k in line_body_ks:
                        continue
                    ov = _plan_overlap_m2(p.part.box, ps[n].part.box)
                    rank = (-ov, 0 if p.key in keys_of[k] else 1, k)
                    if best is None or rank < best:
                        best = rank
            if best is not None:
                found[g] = best[2]
                if best[0] == 0.0:
                    n_group_ties += 1
        if not found:
            break
        for g, k in found.items():
            for pid in groups[g]:
                cluster_of[pid] = k
                members_of[k].append(pid)
                keys_of[k].add(ps[pid].key)
        unassigned = [g for g in unassigned if g not in found]
    unassigned = [pid for g in unassigned for pid in groups[g]]
    # what the BFS never reached: a part touching no body at all.  It joins
    # the NEAREST body only within the identity spacing × 4 (10i (3));
    # beyond that it is HELD and reported.
    held_parts: list[int] = []
    orphan_ks: set[int] = set()
    if unassigned:
        boxes: dict[int, tuple[float, float, float, float]] = {}
        for k, pids in members_of.items():
            if k in line_body_ks:
                continue
            bx = [ps[pid].part.box for pid in pids]
            boxes[k] = (min(b[0] for b in bx), min(b[1] for b in bx),
                        max(b[2] for b in bx), max(b[3] for b in bx))
        reach = law.tables.emit.identity.min_distinct_spacing_m * 4.0
        for ecomp in euf.components():
            grp = [pid for pid in ecomp if pid in unassigned]
            if not grp:
                continue
            bx = [ps[pid].part.box for pid in grp]
            gb = (min(b[0] for b in bx), min(b[1] for b in bx),
                  max(b[2] for b in bx), max(b[3] for b in bx))
            m_lat, m_lon = metres_per_degree((gb[0] + gb[2]) / 2.0)
            best_k, best_d = None, None
            for k, b in boxes.items():
                dla = max(0.0, b[0] - gb[2], gb[0] - b[2]) * m_lat
                dlo = max(0.0, b[1] - gb[3], gb[1] - b[3]) * m_lon
                d = math.hypot(dla, dlo)
                if best_d is None or d < best_d - 1e-9 or (abs(d - best_d) <= 1e-9 and k < best_k):
                    best_k, best_d = k, d
            if best_d is not None and best_d <= reach:
                for pid in grp:
                    cluster_of[pid] = best_k
                    members_of[best_k].append(pid)
            elif any(ps[n].line for pid in grp for n in adj.get(pid, ())) \
                    and any(ps[pid].base is not None for pid in grp):
                # THE ORPHAN (owner RULINGS 2026-09-10bb, spec §16.1 rule 4):
                # a group that touched A LINE OBJECT and NO body is its OWN
                # body, seated by SAMPLING the design
                # surface under its parts (10i (2)'s sampler, extended to a
                # body with no ground part at all).  This is what "the
                # buildings that touched only through the fence become their
                # own bodies with their own feet" means at LEMD, where
                # Terminal4_green-LEMD50's two components stand 0.67 m over
                # the pack datum and carry no feet.
                k = (max(members_of) + 1) if members_of else 0
                members_of[k] = list(grp)
                keys_of[k] = {ps[pid].key for pid in grp}
                for pid in grp:
                    cluster_of[pid] = k
                orphan_ks.add(k)
            else:
                held_parts.extend(grp)
    # ── the seats ───────────────────────────────────────────────────────
    lifts: dict[int, float | None] = {}
    grounds_of: dict[int, list[float]] = {}
    lows_of: dict[int, list[float]] = {}
    sampled_of: dict[int, int] = {}
    span_law = getattr(rb, "body_feet_span_m", 0.0)
    for k, pids in members_of.items():
        own = [ps[pid] for pid in pids
               if ps[pid].ground and ps[pid].measured and pid not in attached]
        gs = [float(p.target) for p in own if p.target is not None]
        # §22.3: the same feet read at their LOWEST, for a skirted body
        lows = [float(p.low) for p in own if p.low is not None]
        lf = [float(p.lift) for p in own if p.lift is not None]
        n_sampled = 0
        # FEET ACROSS THE BODY (RULINGS 2026-09-10i (2)): a body wider than
        # body_feet_span_m carrying fewer than one measured foot per that
        # span is not seated on what it has — it SAMPLES the design surface
        # under every ground-contact part's footprint centroid, and those
        # samples join the median (LEMD k1: 4,202 parts over 982 m decided
        # by ONE foot at −6.507 against neighbours +2.8).
        if span_law > 0.0 and gs:
            diam_k = _diameter([ps[pid] for pid in pids])
            need = math.ceil(diam_k / span_law)
            if diam_k > span_law and len(gs) < need:
                for pid in pids:
                    p = ps[pid]
                    if not p.ground or p.fixed or pid in attached or p.base is None:
                        continue
                    if authored and pid in authored:
                        z = float(authored[pid])
                    else:
                        smp = sampler(p.part.lat, p.part.lon)
                        if smp is None or (smp[1] and not rb.water_founds_seat):
                            continue
                        z = float(smp[0]) - float(p.part.base_y)
                    gs.append(z)
                    lows.append(z)
                    lf.append(z - p.base)
                    n_sampled += 1
        # THE ORPHAN'S GROUND (owner RULINGS 2026-09-10bb, spec §16.1 rule
        # 4): a body with NO ground part at all — everything it touched
        # was a line object — samples the design surface under every one
        # of its parts' footprint centroids, and those samples ARE its
        # feet.  Without this the group is held at its authored y, which
        # is the pack's global anchor ground, kilometres away.
        if not gs and k in orphan_ks:
            for pid in pids:
                p = ps[pid]
                if p.base is None:
                    continue
                if authored and pid in authored:
                    z = float(authored[pid])
                else:
                    smp = sampler(p.part.lat, p.part.lon)
                    if smp is None or (smp[1] and not rb.water_founds_seat):
                        continue
                    z = float(smp[0]) - float(p.part.base_y)
                gs.append(z)
                lows.append(z)
                lf.append(z - p.base)
                n_sampled += 1
        grounds_of[k] = gs
        lows_of[k] = lows
        sampled_of[k] = n_sampled
        lifts[k] = float(statistics.median(lf)) if lf else None
    # the facility rule, per structure (05p / 05q at cluster level)
    facility: set[int] = set()
    by_struct: dict[int, list[int]] = {}
    for k, pids in members_of.items():
        # A LINE BODY and an ORPHAN are outside the facility vote (owner
        # RULINGS 2026-09-10bb, spec §16): the "structure" they sit in is
        # the very chain the line rule refused to bind, and an orphan is
        # seated on the surface UNDER ITSELF — it can never stand a band
        # below the mesh.  Left in, LEMD49's +1.33 m orphan was read as a
        # facility against a coalition made of the fence it no longer
        # belongs to, and kept its authored y.
        if lifts[k] is not None and k not in line_body_ks and k not in orphan_ks:
            by_struct.setdefault(struct_of[pids[0]], []).append(k)
    for ks in by_struct.values():
        vals = [lifts[k] for k in ks for _ in grounds_of[k]]       # one vote per measured ground part
        coal, _why = coalition(vals, rb.agreement_window_m)
        d0 = float(statistics.median(coal if coal else vals))
        if rb.facility_requires_at_grade_coalition and abs(d0) > band:
            # the structure's coalition is itself off the mesh by more than
            # the band (a row on a slope, HECA's plane over 85 m of relief):
            # there is no AT-GRADE reference (05q's words), every cluster
            # lifts by its own ground (v1)
            continue
        for k in ks:
            lf = lifts[k]
            if lf is not None and lf > d0 + band and lf > band:
                facility.add(k)
    seats: list[ClusterSeat] = []
    pads: list[PadRequest] = []
    members: dict[MemberKey, MemberParts] = {}
    for ui, u in enumerate(plan_.units):
        for mi in range(len(u.members)):
            members[(ui, mi)] = MemberParts()
    for k in sorted(members_of):
        pids = sorted(members_of[k])
        parts = [ps[pid] for pid in pids]
        fixed_uid = next((attached[pid] for pid in pids if pid in attached), None)
        res = tuple(sorted({plan_.units[p.key[0]].members[p.key[1]].resource for p in parts}))
        ground_parts = [p for p in parts if p.ground and p.fixed is None]
        measured = [p for p in ground_parts if p.measured]
        gs = grounds_of[k]
        span = (max(gs) - min(gs)) if gs else 0.0
        diam = _diameter(parts)
        if fixed_uid is not None:
            # a structure seat: ONE delta for every part it holds
            delta = next(d for key, (uid, d) in fixed.items() if uid == fixed_uid)
            if fixed_uid in stay:
                delta = None
            seats.append(ClusterSeat(k, struct_of[pids[0]], res, len(parts), len(ground_parts),
                                     0, None, None, span, diam, False, False, False,
                                     "structure stays (below its threshold)" if delta is None
                                     else None, 0))
            for p in parts:
                mp = members[p.key]
                mp.part_deltas.append((p.part.comp, k, delta))
                mp.clusters.add(k)
            continue
        # THE LOW-SIDE FOOT FOR A SKIRTED BODY (owner RULINGS 2026-09-10ag;
        # spec §22.3, a deliberate deviation from 10i's median): a body
        # EVERY one of whose members carries a foundation skirt sets its
        # zero at the LOWEST foot — the low side touches the ground and
        # the high side buries into the skirt, which is what the skirt is
        # for.  The median would float the low side by half the relief.
        skirted_body = bool(parts) and all(
            plan_.units[p.key[0]].members[p.key[1]].skirted for p in parts)
        lows = lows_of.get(k, ())
        ground_m = None
        if gs:
            ground_m = float(min(lows)) if skirted_body and lows \
                else float(statistics.median(gs))
        skip: str | None = None
        held = False
        if ground_m is None:
            held = True
            nw = sum(1 for p in ground_parts if p.water)
            skip = (f"held: no measured ground part ({nw} on water, "
                    f"{sum(1 for p in ground_parts if p.off)} off the mesh, "
                    f"{len(parts) - len(ground_parts)} elevated) — the current bytes are kept")
        elif k in facility:
            skip = (f"facility cluster (05p at cluster level): stands {lifts[k]:+.2f} m under the "
                    f"mesh, more than contact_band_m {band} beyond its structure's coalition — "
                    "never seated, authored y kept (the cutout is the basin pass's affair)")
        # THE DELTA, ONE PER BODY (RULINGS 2026-09-10i (2), superseding
        # 09s (2)'s per-part own target): every part of a touching body —
        # measured ground, elevated, on water, off the mesh — takes the
        # body's MEDIAN ground.  The per-part own target was the second
        # source of the LEMD tear: two touching walls of one placement
        # whose feet read 1.2 m apart came out 1.2 m apart even where the
        # cut law kept them in one cluster.  A file carries several deltas
        # only across a physical separation (09b (5)'s per-vertex deltas
        # BETWEEN disconnected components).  The per-foot residual is
        # reported instead of being written into the geometry.
        def _delta(p: _P) -> float | None:
            if ground_m is None or p.base is None:
                return None
            return ground_m - p.base
        max_delta = max((abs(d) for d in (_delta(p) for p in parts) if d is not None),
                        default=0.0)
        # THE SEGMENT SEAT of a LINE BODY (owner RULINGS 2026-09-10bb, spec
        # §16.1 rule 3): its stations each read the design surface under
        # themselves; every VERTEX takes the delta of the station nearest
        # it in plan, so a 5 km fence follows the ground instead of taking
        # one median.  The threshold is put to the LARGEST station, never
        # the median — a fence whose middle happens to sit right must still
        # drape its ends.
        is_line_body = k in line_body_ks
        stations: list[tuple[int, float, float, float]] = []
        if is_line_body:
            lp = parts[0]
            if lp.base is not None:
                stations = [(lp.part.comp, la, lo, t - lp.base) for la, lo, t in lp.stations]
            if stations:
                max_delta = max(abs(d) for *_x, d in stations)
        needs_pad = span > rb.cluster_span_pad_m
        if skip is None and max_delta < rb.min_delta_m:
            skip = (f"below_threshold: largest resource correction |{max_delta:.3f}| m < "
                    f"{rb.min_delta_m} m — the cluster stays at its authored y and the terrain adapts")
        if skip is None and measured and diam <= rb.a3_guard_max_diameter_m:
            corrected = statistics.mean(abs(ground_m - p.target) for p in measured)
            uncorrected = statistics.mean(abs(p.base - p.target) for p in measured)
            if corrected > uncorrected + rb.a3_tolerance_m:
                skip = (f"refused: the single offset would worsen the seating — mean ground-part "
                        f"residual {corrected:.3f} m corrected vs {uncorrected:.3f} m uncorrected "
                        f"over {len(measured)} part(s) (v1 A3, cluster {k})")
        bakes = skip is None and not held
        # pads: the ground parts the seat (or the authored base) still leaves off the mesh
        floor = rb.cluster_residual_pad_m if bakes else rb.nobake_pad_floor_m
        residual: dict[int, float] = {}
        rendered: dict[int, float] = {}
        if bakes or (skip or "").startswith("below_threshold"):
            for p in measured:
                rg = (p.base + (_delta(p) or 0.0)) if bakes else p.base
                rendered[p.pid] = rg
                r = rg - p.target
                if abs(r) > floor:
                    residual[p.pid] = r
        n_res = len(residual)
        if residual:
            ruf = _UF(residual)
            for a, b in kept:
                if a in residual and b in residual:
                    ruf.union(a, b)
            for grp in ruf.components():
                worst = max(grp, key=lambda pid: (abs(residual[pid]), pid))
                w = ps[worst]
                pads.append(PadRequest(
                    k, plan_.units[w.key[0]].members[w.key[1]].resource, w.part.lat, w.part.lon,
                    residual[worst],
                    float(statistics.median(rendered[pid] + ps[pid].part.base_y for pid in grp)),
                    len(grp), abs(residual[worst]) > rb.pad_max_relief_m, bakes))
        # THE PER-FOOT RESIDUAL (10i (2)): what each measured ground part's
        # own feet wanted, against the one delta the body took.
        foot_res = tuple(round(float(z) - ground_m, 3) for z in gs) if ground_m is not None else ()
        seats.append(ClusterSeat(k, struct_of[pids[0]], res, len(parts), len(ground_parts),
                                 len(measured), ground_m, lifts[k], span, diam,
                                 needs_pad and bakes, k in facility, held, skip, n_res,
                                 foot_res, max((abs(x) for x in foot_res), default=0.0),
                                 sampled_of.get(k, 0), is_line_body, k in orphan_ks))
        for p in parts:
            mp = members[p.key]
            mp.part_deltas.append((p.part.comp, k, _delta(p) if bakes else None))
            mp.clusters.add(k)
            if bakes and stations and p is parts[0]:
                mp.line_stations.extend(stations)
            if p.ground:
                mp.n_ground += 1
                if k in facility:
                    mp.n_facility += 1
                if p.measured:
                    mp.witnesses += 1
                    mp.grounds.append(p.target)
                if p.water:
                    mp.water += 1
                if p.off:
                    mp.off_mesh += 1
                if p.pid in residual:
                    mp.outliers += 1
    # A part the BFS never reached and no body stands within the identity
    # spacing × 4 of (10i (3)): HELD at its authored y, reported as a part
    # with no delta and no cluster (id −1) so ``engine_v2`` leaves it alone.
    for pid in held_parts:
        p = ps[pid]
        mp = members[p.key]
        mp.part_deltas.append((p.part.comp, -1, None))
        mp.clusters.add(-1)
    for mp in members.values():
        mp.part_deltas.sort()
    return Outcome(seats, members, pads, n_cut, len({struct_of[pid] for pid in ps}),
                   n_intra_kept, len(held_parts), n_groups, n_group_ties,
                   len(line_body_ks), n_line_edges, len(orphan_ks))
