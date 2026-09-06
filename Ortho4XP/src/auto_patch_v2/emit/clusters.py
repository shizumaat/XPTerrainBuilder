"""THE CONTACT-CLUSTER SEAT (RULINGS 2026-09-06g; v1's
``object_clusters.form_clusters`` + ``object_anchor._build_structure_clusters``
/ ``_seat_clusters`` as v2 code — v2 never imports v1).

Over the plan's parts and contact edges (``airport/contact.py``), after
the mesh:

* every GROUND part (``base_y ≤ elevated_base_m``) reads the mesh under
  its centroid; its SEAT TARGET is ``ground − base_y`` (the world
  elevation of its object's ``y = 0`` plane that lands it on the mesh);
  a part on water (``water_founds_seat`` off) or off the mesh is
  UNMEASURED and never votes (merge on doubt survives for it);
* the CUT: a ground-to-ground edge whose two measured seat targets differ
  by more than ``cluster_seat_tolerance_m`` is cut; the connected
  components of the kept ground edges are the CLUSTERS;
* ELEVATED parts never vote: each elevated component joins the cluster
  it contacts most (v1 I-8), or — touching none — the cluster whose plan
  box contains it, else the nearest (spec §4.2b);
* a STRUCTURE-seated member (a deck plate at its abutment grade, a plate
  family) is a FIXED cluster with the structure's delta: the parts of its
  own deck-family members reached through contact join it (a pier, a
  railing), every other ground part's contact with it is DROPPED — a
  deck never founds the ground parts around or under it;
* the SEAT: a cluster's ground is the MEDIAN mesh under its measured
  ground parts; each resource's delta is ``ground − base(resource)``
  (v1 I-3: the anchor spelling is only the subtrahend), written per
  vertex; a cluster whose largest per-resource delta is under
  ``min_delta_m`` STAYS; a cluster no wider than ``a3_guard_max_diameter_m``
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
    z: float | None = None      # the mesh under the centroid (measured ground parts)
    water: bool = False
    off: bool = False
    fixed: str | None = None    # the unit id of a structure seat this part follows
    family: str | None = None   # the unit id of the deck family this part may attach to

    @property
    def measured(self) -> bool:
        return self.z is not None

    @property
    def target(self) -> float | None:
        return None if self.z is None else self.z - self.part.base_y

    @property
    def lift(self) -> float | None:
        return None if self.z is None or self.base is None else self.z - self.part.base_y - self.base


def _diameter(parts: _t.Sequence[_P]) -> float:
    if not parts:
        return 0.0
    la0 = min(p.part.box[0] for p in parts); lo0 = min(p.part.box[1] for p in parts)
    la1 = max(p.part.box[2] for p in parts); lo1 = max(p.part.box[3] for p in parts)
    m_lat, m_lon = metres_per_degree((la0 + la1) / 2.0)
    return math.hypot((la1 - la0) * m_lat, (lo1 - lo0) * m_lon)


def seat_clusters(plan_: RebakePlan, sampler: Sampler, law, base_by_member: _t.Mapping[MemberKey, float | None],
                  fixed: _t.Mapping[MemberKey, tuple[str, float]],
                  family: _t.Mapping[MemberKey, str]) -> Outcome:
    """The cluster seat (module doc).  ``base_by_member`` is each
    member's rendered ``y = 0`` plane (``None``: its anchor is off the
    mesh, its parts are held); ``fixed`` maps a structure-seated member
    to ``(unit id, delta)``; ``family`` maps a deck-family member to the
    unit id of the deck it may attach to."""
    rb = law.tables.structures.rebake
    band = law.tables.structures.basin.contact_band_m
    ps: dict[int, _P] = {}
    for ui, u in enumerate(plan_.units):
        for mi, m in enumerate(u.members):
            key = (ui, mi)
            for p in m.parts:
                ps[p.pid] = _P(p.pid, key, p, base_by_member.get(key),
                               p.base_y <= rb.elevated_base_m,
                               fixed=fixed.get(key, (None, 0.0))[0] if key in fixed else None,
                               family=family.get(key))
    # ── the samples: ground parts only ──────────────────────────────────
    for p in ps.values():
        if not p.ground or p.fixed or p.base is None:
            continue
        s = sampler(p.part.lat, p.part.lon)
        if s is None:
            p.off = True
        elif s[1] and not rb.water_founds_seat:
            p.water = True
        else:
            p.z = float(s[0])
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
    guf = _UF(ground_ids)
    by_unit: dict[str, list[int]] = {}
    for pid, uid in attached.items():
        by_unit.setdefault(uid, []).append(pid)
    for pids in by_unit.values():
        for pid in pids[1:]:
            guf.union(pids[0], pid)
    kept: list[tuple[int, int]] = []
    votes: dict[int, list[int]] = {}           # elevated pid -> ground pids it touches
    euf = _UF([pid for pid, p in ps.items() if not p.ground and pid not in attached])
    n_cut = 0
    for a, b in edges:
        pa, pb = ps[a], ps[b]
        a_att, b_att = a in attached, b in attached
        if a_att and b_att:
            continue                            # one structure seat, or two decks touching: apart
        if a_att or b_att:
            other = pb if a_att else pa
            if other.ground:
                continue                        # a deck never founds the ground around it
            votes.setdefault(other.pid, []).append(a if a_att else b)
            continue
        if pa.ground and pb.ground:
            ta, tb = pa.target, pb.target
            if rb.cluster_seat_tolerance_m > 0.0 and ta is not None and tb is not None \
                    and abs(ta - tb) > rb.cluster_seat_tolerance_m:
                n_cut += 1
                continue
            kept.append((a, b))
            guf.union(a, b)
        elif pa.ground or pb.ground:
            e, g = (a, b) if pb.ground else (b, a)
            votes.setdefault(e, []).append(g)
        else:
            euf.union(a, b)
    comps = guf.components()
    cluster_of: dict[int, int] = {}
    for k, pids in enumerate(comps):
        for pid in pids:
            cluster_of[pid] = k
    members_of: dict[int, list[int]] = {k: list(pids) for k, pids in enumerate(comps)}
    # ── elevated components inherit (spec §4.2) ─────────────────────────
    boxes: dict[int, tuple[float, float, float, float]] = {}
    for k, pids in members_of.items():
        bx = [ps[pid].part.box for pid in pids]
        boxes[k] = (min(b[0] for b in bx), min(b[1] for b in bx),
                    max(b[2] for b in bx), max(b[3] for b in bx))
    for ecomp in euf.components():
        count: dict[int, int] = {}
        for pid in ecomp:
            for g in votes.get(pid, ()):
                k = cluster_of[g]
                count[k] = count.get(k, 0) + 1
        if count:
            host = min(count, key=lambda k: (-count[k], k))
        elif members_of:
            bx = [ps[pid].part.box for pid in ecomp]
            cla = (min(b[0] for b in bx) + max(b[2] for b in bx)) / 2.0
            clo = (min(b[1] for b in bx) + max(b[3] for b in bx)) / 2.0
            m_lat, m_lon = metres_per_degree(cla)
            inside = [k for k, b in boxes.items() if b[0] <= cla <= b[2] and b[1] <= clo <= b[3]]
            if inside:
                host = min(inside, key=lambda k: ((boxes[k][2] - boxes[k][0]) * m_lat
                                                   * (boxes[k][3] - boxes[k][1]) * m_lon, k))
            else:
                host = min(boxes, key=lambda k: (math.hypot(
                    ((boxes[k][0] + boxes[k][2]) / 2.0 - cla) * m_lat,
                    ((boxes[k][1] + boxes[k][3]) / 2.0 - clo) * m_lon), k))
        else:
            continue
        for pid in ecomp:
            cluster_of[pid] = host
            members_of[host].append(pid)
    # ── the seats ───────────────────────────────────────────────────────
    lifts: dict[int, float | None] = {}
    grounds_of: dict[int, list[float]] = {}
    for k, pids in members_of.items():
        g = [ps[pid].z for pid in pids if ps[pid].ground and ps[pid].measured and pid not in attached]
        grounds_of[k] = [float(z) for z in g if z is not None]
        lf = [ps[pid].lift for pid in pids if ps[pid].ground and ps[pid].measured and pid not in attached]
        lf = [x for x in lf if x is not None]
        lifts[k] = float(statistics.median(lf)) if lf else None
    # the facility rule, per structure (05p / 05q at cluster level)
    facility: set[int] = set()
    by_struct: dict[int, list[int]] = {}
    for k, pids in members_of.items():
        if lifts[k] is not None:
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
            seats.append(ClusterSeat(k, struct_of[pids[0]], res, len(parts), len(ground_parts),
                                     0, None, None, span, diam, False, False, False, None, 0))
            for p in parts:
                mp = members[p.key]
                mp.part_deltas.append((p.part.comp, k, delta))
                mp.clusters.add(k)
            continue
        ground_m = float(statistics.median(gs)) if gs else None
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
        deltas = {p.key: ground_m - p.base for p in parts if ground_m is not None and p.base is not None}
        max_delta = max((abs(d) for d in deltas.values()), default=0.0)
        needs_pad = span > rb.cluster_span_pad_m
        if skip is None and max_delta < rb.min_delta_m:
            skip = (f"below_threshold: largest resource correction |{max_delta:.3f}| m < "
                    f"{rb.min_delta_m} m — the cluster stays at its authored y and the terrain adapts")
        if skip is None and measured and diam <= rb.a3_guard_max_diameter_m:
            corrected = statistics.mean(abs(ground_m + p.part.base_y - p.z) for p in measured)
            uncorrected = statistics.mean(abs(p.base + p.part.base_y - p.z) for p in measured)
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
                rg = ground_m if bakes else p.base
                rendered[p.pid] = rg
                r = rg + p.part.base_y - p.z
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
        seats.append(ClusterSeat(k, struct_of[pids[0]], res, len(parts), len(ground_parts),
                                 len(measured), ground_m, lifts[k], span, diam,
                                 needs_pad and bakes, k in facility, held, skip, n_res))
        for p in parts:
            mp = members[p.key]
            mp.part_deltas.append((p.part.comp, k, deltas.get(p.key) if bakes else None))
            mp.clusters.add(k)
            if p.ground:
                mp.n_ground += 1
                if k in facility:
                    mp.n_facility += 1
                if p.measured:
                    mp.witnesses += 1
                    mp.grounds.append(p.z)
                if p.water:
                    mp.water += 1
                if p.off:
                    mp.off_mesh += 1
                if p.pid in residual:
                    mp.outliers += 1
    for mp in members.values():
        mp.part_deltas.sort()
    return Outcome(seats, members, pads, n_cut, len({struct_of[pid] for pid in ps}))
