"""THE FLAT PAD LEADS ITS FRONTAGE — the mint-time feasibility test and the
per-rigid-block partition (flat-pad-apron spec §2; owner RULINGS 2026-09-30f,
spec-author 2026-09-30k; issue #111).

Called from :func:`planar.platform.platform_split` — the ONE derivation site
of the platform (spec §3 C1) — for every minted platform.  Nothing here
mints a face: it READS the pad polygon, the airside regions, the DEM and the
cluster outlines carried on ``Airport.clusters`` and returns a
:class:`BlockPlan` (the verdict, the atoms, the blocks, their datums and
intervals).

THE TEST (§2 (1)).  For block ``b`` with welded contacts ``F_b`` the datum
interval is ``I_b = ∩_q [T(q) − a·d_q − τ_q, T(q) + a·d_q + τ_q]`` over the
taxi-family edge vertices ``q`` of the apron bodies the pad fronts;
``T`` = the DEM (stage 1 has not run at the arrangement), ``a`` = the apron
HARD cap (``common.roles.apron``), ``d_q`` = the distance from ``q`` to the
block's nearest held contact (straight — a lower bound of the geodesic, so
the interval read is never looser than the spec's), and
``τ_q = max(0, t·s_q − u_q) − margin`` with ``t`` the taxi letter cap
(``law.ruleset.taxi.longitudinal``), ``s_q`` the distance to the nearest
PINNED point (a runway-family face widened by its zone-2 half width; a
straight lower bound of the route distance), ``u_q = |T(q) − T(pin)|`` and
``margin`` = ``[building_pad] frontage_hold_margin_m``.  ``τ ≡ 0`` is the
HELD-TAXI test.

THE PARTITION (§2 (2)-(4)).  The atoms are the unit's rigid clusters: the
cluster outline rings inside the pad, chained at ``[placement]
rigid_reach_m`` (a contact pair is a touch, so a contact-bound pair is one
atom by construction — never split).  Each welded contact belongs to the
atom it stands nearest.  Atoms are ordered along the frontage (projection
on the contacts' principal axis) and grouped greedily from the low end
while the block's interval stays non-empty; then the chain
``|D_b − D_{b+1}| ≤ a·g_b`` (``g_b`` = the gap between the two blocks'
contact sets) is propagated forward and backward.  A chain that empties an
interval is REPORTED (``chain_ok`` False) — the caller decides (STOP)."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

__all__ = ["Block", "BlockPlan", "plan_blocks", "hold_interval", "chain_propagate",
           "greedy_blocks", "BLOCK_PLANS"]

#: The frontage sampling step (m): ``platform._STEP_M``'s resolution.
_STEP_M = 2.0
#: The apron edge sampling step for the taxi-edge vertices ``q`` (m) — a
#: geometric resolution, not a law value.
_Q_STEP_M = 8.0
#: A taxi-family face within this of an apron edge sample makes it a ``q``
#: (the arrangement's snap scale).
_Q_TOUCH_M = 1.0


@_dc.dataclass
class Block:
    k: int
    atoms: list[int]
    n_contacts: int
    interval_held: tuple[float, float]
    interval: tuple[float, float]
    datum: "float | None" = None
    contact_min: float = 0.0
    contact_max: float = 0.0
    contact_median: float = 0.0
    #: §2 (6): contacts whose hold was dropped (one-block infeasible unit)
    residual: int = 0
    residual_max_m: float = 0.0
    polygon: _t.Any = None

    def to_dict(self) -> dict:
        d = _dc.asdict(self)
        d.pop("polygon", None)
        return d


@_dc.dataclass
class BlockPlan:
    ref: str
    verdict: str                      # one_block | split | infeasible_one_body | stop_cap | no_atoms
    atoms: int
    contacts: int
    q: int
    blocks: list[Block]
    chain_ok: bool = True
    steps: list[float] = _dc.field(default_factory=list)
    gaps_m: list[float] = _dc.field(default_factory=list)
    note: str = ""

    def line(self) -> str:
        bl = "; ".join(
            f"b{b.k} atoms {len(b.atoms)} contacts {b.n_contacts} "
            f"[{b.contact_min:.2f}..{b.contact_max:.2f}] "
            f"I_held [{b.interval_held[0]:.2f},{b.interval_held[1]:.2f}] "
            f"I [{b.interval[0]:.2f},{b.interval[1]:.2f}] D "
            + ("-" if b.datum is None else f"{b.datum:.2f}")
            + (f" residual {b.residual} (max {b.residual_max_m:.2f})" if b.residual else "")
            for b in self.blocks)
        return (f"{self.ref}: {self.verdict} atoms {self.atoms} contacts {self.contacts} "
                f"q {self.q} blocks {len(self.blocks)} chain "
                f"{'ok' if self.chain_ok else 'EMPTY'} steps "
                f"{[round(s, 2) for s in self.steps]} gaps {[round(g, 1) for g in self.gaps_m]}"
                f"{' ' + self.note if self.note else ''} | {bl}")


#: The last arrangement's block plans (the ``PLATFORMS`` pattern).
BLOCK_PLANS: list[BlockPlan] = []


def hold_interval(Tq: np.ndarray, dq: np.ndarray, tau: np.ndarray, a: float
                  ) -> tuple[float, float]:
    """§2 (1): ``∩_q [T − a·d − τ, T + a·d + τ]``.  An empty ``q`` set is the
    whole line (nothing binds)."""
    if Tq.size == 0:
        return (-np.inf, np.inf)
    r = a * dq + tau
    return (float(np.max(Tq - r)), float(np.min(Tq + r)))


def chain_propagate(intervals: list[tuple[float, float]], gaps: list[float], a: float
                    ) -> list[tuple[float, float]]:
    """§2 (2): forward–backward propagation of ``|D_b − D_{b+1}| ≤ a·g_b``."""
    iv = [list(x) for x in intervals]
    for b in range(1, len(iv)):
        w = a * gaps[b - 1]
        iv[b][0] = max(iv[b][0], iv[b - 1][0] - w)
        iv[b][1] = min(iv[b][1], iv[b - 1][1] + w)
    for b in range(len(iv) - 2, -1, -1):
        w = a * gaps[b]
        iv[b][0] = max(iv[b][0], iv[b + 1][0] - w)
        iv[b][1] = min(iv[b][1], iv[b + 1][1] + w)
    return [(x[0], x[1]) for x in iv]


def greedy_blocks(order: list[int], interval_of: _t.Callable[[list[int]], tuple[float, float]]
                  ) -> list[list[int]]:
    """§2 (4) (c): atoms in frontage order, grouped greedily from the low end
    while the block's own interval stays non-empty.  An atom that is
    infeasible ALONE starts (and ends) its own block."""
    blocks: list[list[int]] = []
    cur: list[int] = []
    for i in order:
        trial = cur + [i]
        lo, hi = interval_of(trial)
        if not cur or lo <= hi:
            cur = trial
        else:
            blocks.append(cur)
            cur = [i]
    if cur:
        blocks.append(cur)
    return blocks


def _sample_ring(ring, step: float) -> list[tuple[float, float]]:
    n = max(4, int(ring.length // step))
    return [ring.interpolate(i * ring.length / n).coords[0] for i in range(n)]


def _dem(dem, x: float, y: float) -> float:
    try:
        z = float(dem.z(x, y))
    except Exception:  # noqa: BLE001 — off the raster: no witness
        return float("nan")
    return z


def _atoms(P: Polygon, airport, reach: float) -> list[Polygon]:
    """§2 (4) (a)/(b): the cluster outline rings inside the pad, chained at
    the rigid reach — the rigid atoms of the unit."""
    cl = getattr(airport, "clusters", None) or ()
    if not cl:
        return []
    to_xy = airport.frame.entry()
    x0, y0, x1, y1 = P.bounds
    polys: list[Polygon] = []
    for c in cl:
        for ring in (getattr(c, "rings", ()) or ()):
            if len(ring) < 3:
                continue
            try:
                pts = [to_xy(float(lo), float(la)) for la, lo in ring]
            except Exception:  # noqa: BLE001
                continue
            q = Polygon(pts)
            if not q.is_valid:
                q = q.buffer(0)
            if q.is_empty or q.area <= 0.0:
                continue
            bx0, by0, bx1, by1 = q.bounds
            if bx1 < x0 or bx0 > x1 or by1 < y0 or by0 > y1:
                continue
            if q.intersection(P).area >= 0.5 * q.area:
                polys.append(q)
    if not polys:
        return []
    u = unary_union([q.buffer(0.5 * reach, join_style=2, mitre_limit=2.0) for q in polys])
    comps = [u] if isinstance(u, Polygon) else list(getattr(u, "geoms", []))
    out = []
    for g in comps:
        mem = [q for q in polys if g.intersects(q.representative_point())]
        out.append(unary_union(mem) if mem else g)
    return out


def plan_blocks(ref: str, P: Polygon, base_regions, law, dem, airport,
                near: float) -> "BlockPlan | None":
    """The §2 test and partition for one platform pad (module docstring)."""
    from scipy.spatial import cKDTree

    from ..law.tables import (apron_roles, role_cap, role_side, zone2_half_width_m,
                              is_rigid_role)
    if dem is None or airport is None:
        return None
    bp = law.tables.structures.building_pad
    margin = float(bp.frontage_hold_margin_m)
    cap_blocks = int(bp.frontage_blocks_max)
    reach = float(law.tables.structures.placement.rigid_reach_m)
    p = law.tables.precedence
    runway_roles = set(p.runway_family.members)
    taxi_roles = set(p.taxi_family.members)
    ap_roles = {r for r in apron_roles(law)
                if role_side(law, r) == "airside" and not is_rigid_role(law, r)}
    a = float(role_cap(law, "apron").longitudinal)
    letters = [rw.code_letter for rw in getattr(airport, "runways", ()) if rw.code_letter]
    letter = max(letters) if letters else None
    t = float(law.ruleset.taxi.longitudinal.value(None, letter))
    # the regions
    aprons = [r.polygon for r in base_regions if r.source == "cell" and r.role in ap_roles
              and r.polygon is not None and not r.polygon.is_empty]
    taxis = [r.polygon for r in base_regions if r.source == "cell" and r.role in taxi_roles
             and r.polygon is not None and not r.polygon.is_empty]
    pins = []
    for r in base_regions:
        if r.source == "cell" and r.role in runway_roles and r.polygon is not None \
                and not r.polygon.is_empty:
            w = zone2_half_width_m(law, r.role, getattr(r, "code_number", None),
                                   getattr(r, "code_letter", None)) or 0.0
            pins.append(r.polygon.buffer(float(w), join_style=2, mitre_limit=2.0)
                        if w > 0.0 else r.polygon)
    # the welded contacts: pad ring samples within ``near`` of an apron body
    fronted = [q for q in aprons if q.distance(P) <= near]
    if not fronted:
        return None
    afr = unary_union(fronted)
    C = np.asarray([xy for xy in _sample_ring(P.exterior, _STEP_M)
                    if afr.distance(Point(xy)) <= near], dtype=float).reshape(-1, 2)
    if C.shape[0] < 3:
        return None
    Cz = np.asarray([_dem(dem, x, y) for x, y in C])
    ok = np.isfinite(Cz)
    C, Cz = C[ok], Cz[ok]
    # the q set: apron-edge samples of the fronted bodies that touch a taxi face
    tx = unary_union(taxis) if taxis else None
    pin_u = unary_union(pins) if pins else None
    Q = []
    for g in fronted:
        for ring in (g.exterior, *g.interiors):
            for xy in _sample_ring(ring, _Q_STEP_M):
                if tx is not None and tx.distance(Point(xy)) <= _Q_TOUCH_M:
                    Q.append(xy)
    Q = np.asarray(Q, dtype=float).reshape(-1, 2)
    Tq = np.asarray([_dem(dem, x, y) for x, y in Q])
    okq = np.isfinite(Tq)
    Q, Tq = Q[okq], Tq[okq]
    tau = np.full(Q.shape[0], -margin)
    if pin_u is not None and Q.shape[0]:
        from shapely.ops import nearest_points
        for i, (x, y) in enumerate(Q):
            pt = Point(x, y)
            s = pin_u.distance(pt)
            if s <= 0.0:
                continue
            pp = nearest_points(pin_u, pt)[0]
            u = abs(Tq[i] - _dem(dem, pp.x, pp.y))
            if u != u:
                u = 0.0
            tau[i] = max(0.0, t * s - u) - margin
    else:
        tau[:] = np.inf                       # no runway: nothing pins
    tau_held = np.zeros_like(tau)

    atoms = _atoms(P, airport, reach)
    plan = BlockPlan(ref, "", len(atoms), int(C.shape[0]), int(Q.shape[0]), [])
    if not atoms:
        atoms = [P]
        plan.note = "no cluster atoms: the pad is one atom"
        plan.atoms = 1
    # contact -> nearest atom
    own = np.asarray([min(range(len(atoms)), key=lambda j: atoms[j].distance(Point(xy)))
                      for xy in C])
    # frontage order: projection on the contacts' principal axis
    c0 = C.mean(axis=0)
    _u, _s, vt = np.linalg.svd(C - c0, full_matrices=False)
    ax = vt[0]
    proj_c = (C - c0) @ ax
    fr_atoms = [j for j in range(len(atoms)) if np.any(own == j)]
    back = [j for j in range(len(atoms)) if j not in fr_atoms]
    pos = {j: float(np.median(proj_c[own == j])) for j in fr_atoms}
    # the low end first
    lo_end = float(np.median(Cz[proj_c <= np.quantile(proj_c, 0.1)]))
    hi_end = float(np.median(Cz[proj_c >= np.quantile(proj_c, 0.9)]))
    order = sorted(fr_atoms, key=lambda j: pos[j], reverse=lo_end > hi_end)
    qtree = None

    def _iv(atom_ids: list[int], held: bool = False) -> tuple[float, float]:
        m = np.isin(own, atom_ids)
        if not np.any(m) or Q.shape[0] == 0:
            return (-np.inf, np.inf)
        tr = cKDTree(C[m])
        dq, _ = tr.query(Q)
        return hold_interval(Tq, dq, tau_held if held else tau, a)

    whole = _iv(fr_atoms)
    groups = [list(order)] if whole[0] <= whole[1] else greedy_blocks(order, _iv)
    # the chain
    gaps = []
    for b in range(len(groups) - 1):
        m0, m1 = np.isin(own, groups[b]), np.isin(own, groups[b + 1])
        d, _ = cKDTree(C[m0]).query(C[m1])
        gaps.append(float(d.min()))
    ivs = [_iv(g) for g in groups]
    prop = chain_propagate(ivs, gaps, a) if len(groups) > 1 else ivs
    plan.chain_ok = all(lo <= hi for lo, hi in prop)
    plan.gaps_m = gaps
    for k, g in enumerate(groups):
        m = np.isin(own, g)
        z = Cz[m]
        blk = Block(k, list(g), int(m.sum()), _iv(g, held=True), prop[k],
                    contact_min=float(z.min()), contact_max=float(z.max()),
                    contact_median=float(np.median(z)))
        lo, hi = prop[k]
        if lo <= hi:
            blk.datum = float(min(max(blk.contact_median, lo), hi))
        plan.blocks.append(blk)
    # §2 (4) (d): atoms behind the frontage join the nearest block
    for j in back:
        dist = [min(atoms[j].distance(atoms[i]) for i in blk.atoms) for blk in plan.blocks]
        plan.blocks[int(np.argmin(dist))].atoms.append(j)
    if len(groups) == 1:
        if whole[0] <= whole[1]:
            plan.verdict = "one_block"
        else:
            # §2 (6) (Q1 default): one rigid atom that fails and cannot split —
            # flat at the mid of the contacts' [min, max], clipped to what
            # the taxi budget reaches; unreachable contacts are the residual
            blk = plan.blocks[0]
            mid = 0.5 * (blk.contact_min + blk.contact_max)
            lo, hi = whole
            blk.datum = float(min(max(mid, min(lo, hi)), max(lo, hi)))
            plan.verdict = "infeasible_one_body"
            plan.chain_ok = True
            # the reachable contacts: a contact's OWN interval (the q set
            # measured from it alone) contains the datum -> its hold row is
            # HARD; the rest are the residual (dropped to the preference)
            if Q.shape[0]:
                dd = np.hypot(C[:, None, 0] - Q[None, :, 0], C[:, None, 1] - Q[None, :, 1])
                r = a * dd + tau[None, :]
                clo = np.max(Tq[None, :] - r, axis=1)
                chi = np.min(Tq[None, :] + r, axis=1)
                reach_ok = (clo <= blk.datum) & (blk.datum <= chi)
                blk.residual = int((~reach_ok).sum())
                plan.note = (f"held {int(reach_ok.sum())} / residual {blk.residual}; "
                             f"contacts off the datum > 0.3 m: "
                             f"{int((np.abs(Cz - blk.datum) > margin).sum())}")
    else:
        plan.verdict = "split" if len(groups) <= cap_blocks else "stop_cap"
        plan.steps = [(plan.blocks[b].datum or 0.0) - (plan.blocks[b + 1].datum or 0.0)
                      for b in range(len(groups) - 1)]
    # the residual per block: contacts the datum misses by more than the
    # apron can carry to the nearest q (reported, §2 (6))
    for blk in plan.blocks:
        if blk.datum is None:
            continue
        m = np.isin(own, blk.atoms)
        miss = np.abs(Cz[m] - blk.datum)
        blk.residual_max_m = float(miss.max()) if miss.size else 0.0
    # per-block polygons (for the downstream mint): the pad cut by the
    # Voronoi of the block atoms
    for blk in plan.blocks:
        blk.polygon = unary_union([atoms[j] for j in blk.atoms])
    return plan
