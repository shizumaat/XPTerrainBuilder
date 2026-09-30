"""THE FLAT PAD CUT INTO FLAT BLOCKS AT ITS NECKS — the mint-time
feasibility test and the block partition of a unit platform (flat-pad-apron
spec §2 as amended by owner RULINGS 2026-09-30r, taking Q-111b option (1)
of spec-author 30n; 30f, 30k; issue #111).

Called from :func:`planar.platform.platform_split` — the ONE derivation site
of the platform (spec §3 C1) — for every minted platform.  Nothing here
mints a face: it READS the pad polygon, the airside regions, the DEM and the
pack partition carried on ``Airport.partition`` and returns a
:class:`BlockPlan` (the verdict, the blocks, their polygons, datums, held
contacts and the cut lines between them).

WHY A CUT OF THE OBJECT (30n).  The spec's first reading split a unit per
RIGID ATOM; measured, every terminal is ONE contact-bound atom (HECA T3
94.5 % of its footprint, T2 98.8 %, SPJC ``building5`` 98.9 %), so no split
by atom exists.  30r takes option (1): the terminal OBJECT is cut at the
NARROWEST NECKS of its footprint — where the fewest metres of its footed
parts cross a straight chord of the pad — and each block is seated flat at
its own level; the walls step at the block boundary (a declared pad|pad
terrace, exempt from the cap, 30l).

THE TEST, PER FRONTAGE CONTACT.  A welded contact ``c`` (a pad ring sample
within ``near`` of a fronted apron body) can carry a level ``D`` iff the
apron in front of it grades from ``D`` to the taxiway it faces within the
apron's hard cap ``a`` (``common.roles.apron``), the taxiway moving by at
most its budget ``τ_q``: ``J_c = [z_c − r_c, z_c + r_c]`` with ``z_c`` the
contact's ground (the DEM — stage 1 has not run at the arrangement) and the
REACH ``r_c = max(0, a·d_c + τ_q)`` (:func:`reach`), ``d_c`` the straight
distance to the nearest taxi edge vertex ``q``, ``τ_q = max(0, t·s_q −
u_q) − margin`` (``t`` the taxi letter cap ``law.ruleset.taxi.longitudinal``,
``s_q`` the distance to the nearest PINNED point — a runway-family face
widened by its zone-2 half width — ``u_q`` the grade the route already
spends, ``margin`` = ``[building_pad] frontage_hold_margin_m``).  The
frontage is itself an apron edge graded within ``a``, so the ``J`` are
closed under that reach along the ring (:func:`band`); a block's interval
is the intersection over its contacts.  :func:`band` records why the spec's
far-field ``∩_q`` reading was replaced (a DEM artefact, measured).

THE PARTITION.  A block whose band misses a contact by more than ``margin``
is BISECTED by the chord that (1) leaves each side at least a jetway BAY of
frontage (``emit.design.jetway_strip_m`` — the apron strip each gate holds
level with the terminal) and (2) brings the worse side's miss to within
``margin`` of the best any chord reaches, choosing among those the chord
that crosses the fewest metres of footed pack parts (the neck).  The worst
block is bisected until every block holds, or ``[building_pad]
frontage_blocks_max`` is reached — a unit needing more is a STOP (30k Q4),
reported with its best partition.

THE CHAIN (spec §2 (2), 30k Q2: no apron joint).  Two neighbouring blocks'
frontages are one continuous apron edge, so the apron ramps between their
datums over ``|ΔD| / a``: a contact nearer than ``|ΔD| / (2a)`` (along the
ring) to the other block's frontage is reported as RAMP — the collar there
carries at most ``|ΔD| / 2``.  The hold itself is a stage-1 row
(``constraints/platform.frontage_hold_rows``) and the solve, not this
reading, decides where each contact lands; this plan is the partition and
its prediction."""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import split as _split, unary_union

__all__ = ["Block", "BlockPlan", "plan_blocks", "reach", "band", "arc_distance",
           "bisect_blocks", "hold_mask", "bay_m", "BLOCK_PLANS"]

#: The frontage sampling step (m): ``platform._STEP_M``'s resolution.
_STEP_M = 2.0
#: The apron edge sampling step for the taxi-edge vertices ``q`` (m) — a
#: geometric resolution, not a law value.
_Q_STEP_M = 8.0
#: A taxi-family face within this of an apron edge sample makes it a ``q``
#: (the arrangement's snap scale).
_Q_TOUCH_M = 1.0
#: Chord directions tried per seed point (a geometric resolution).
_CHORD_DIRS = 12
#: Seed points per bisection (the grid is sized to the piece's area).
_CHORD_SEEDS = 900


@_dc.dataclass
class Block:
    k: int
    n_contacts: int
    datum: "float | None" = None
    held: int = 0
    #: contacts whose band misses the datum (the collar carries them)
    residual: int = 0
    residual_max_m: float = 0.0
    #: contacts left free for the apron ramp to the next block (spec §2 (2))
    ramp: int = 0
    contact_min: float = 0.0
    contact_max: float = 0.0
    contact_median: float = 0.0
    area_m2: float = 0.0
    frontage_m: float = 0.0
    polygon: _t.Any = None
    #: the block's frontage samples (plan xy) and whether each is HELD —
    #: the hold rows bind only these (``constraints/platform.
    #: frontage_hold_rows``: a RAMP or residual contact is left free)
    samples_xy: _t.Any = None
    samples_held: _t.Any = None

    def to_dict(self) -> dict:
        d = _dc.asdict(self)
        for k in ("polygon", "samples_xy", "samples_held"):
            d.pop(k, None)
        return d


@_dc.dataclass
class BlockPlan:
    ref: str
    #: one_block | split | residual | stop_cap
    verdict: str
    contacts: int
    q: int
    blocks: list[Block]
    #: the cut chords (plan xy), one per block boundary
    cuts: list = _dc.field(default_factory=list)
    #: the metres of footed pack parts each cut crosses (the neck width)
    neck_m: list[float] = _dc.field(default_factory=list)
    #: ``(i, j, D_i - D_j)`` per cut: the declared pad|pad step
    steps: list[tuple[int, int, float]] = _dc.field(default_factory=list)
    bay_m: float = 0.0
    note: str = ""

    def to_dict(self) -> dict:
        return {"ref": self.ref, "verdict": self.verdict, "contacts": self.contacts,
                "q": self.q, "bay_m": self.bay_m, "note": self.note,
                "neck_m": [round(n, 2) for n in self.neck_m],
                "steps": [[i, j, round(s, 3)] for i, j, s in self.steps],
                "cuts": [[list(c) for c in s.coords] for s in self.cuts],
                "blocks": [b.to_dict() for b in self.blocks]}

    def line(self) -> str:
        bl = "; ".join(
            f"b{b.k} {b.area_m2:,.0f} m2 front {b.frontage_m:.0f} m contacts "
            f"{b.n_contacts} [{b.contact_min:.2f}..{b.contact_max:.2f}] D "
            + ("-" if b.datum is None else f"{b.datum:.2f}")
            + f" held {b.held} ramp {b.ramp} residual {b.residual}"
            + (f" (max {b.residual_max_m:.2f})" if b.residual else "")
            for b in self.blocks)
        st = ", ".join(f"b{i}|b{j} {s:+.2f}" for i, j, s in self.steps)
        return (f"{self.ref}: {self.verdict} contacts {self.contacts} q {self.q} "
                f"blocks {len(self.blocks)} bay {self.bay_m:g} m steps [{st}] "
                f"necks {[round(n, 1) for n in self.neck_m]}"
                f"{' ' + self.note if self.note else ''} | {bl}")


#: The last arrangement's block plans (the ``PLATFORMS`` pattern).
BLOCK_PLANS: list[BlockPlan] = []


def arc_distance(S: np.ndarray, S2: np.ndarray, perim: float) -> np.ndarray:
    """The distance ALONG THE PAD RING between contacts at ring positions
    ``S`` and ``S2`` (the frontage path; the apron in front of the ring is
    never farther than it, so a reach read on it is never tighter than the
    apron's) — ``|S| x |S2|``."""
    d = np.abs(S[:, None] - S2[None, :])
    return np.minimum(d, perim - d) if perim > 0.0 else d


def reach(C: np.ndarray, Q: np.ndarray, tau: np.ndarray, a: float) -> np.ndarray:
    """Per contact the REACH ``r_c``: how far the apron in front of it can
    carry a level away from its own ground — ``a`` over the distance to the
    NEAREST taxi edge vertex ``q`` plus the budget ``τ_q`` that taxiway may
    move (spec §2 (1); never negative).  ``inf`` without a ``q``."""
    n = C.shape[0]
    if Q.shape[0] == 0:
        return np.full(n, np.inf)
    r = np.empty(n)
    for i0 in range(0, n, 512):
        c = C[i0:i0 + 512]
        d = np.hypot(c[:, None, 0] - Q[None, :, 0], c[:, None, 1] - Q[None, :, 1])
        j = np.argmin(d, axis=1)
        r[i0:i0 + 512] = np.maximum(0.0, a * d[np.arange(len(c)), j] + tau[j])
    return r


def band(z: np.ndarray, r: np.ndarray, S: np.ndarray, perim: float, a: float
         ) -> tuple[np.ndarray, np.ndarray]:
    """Per contact the level band ``[L_c, U_c]``: its own
    ``J_c = [z_c − r_c, z_c + r_c]`` (``z`` its ground, the level the apron
    and the taxiway in front of it follow; ``r`` its :func:`reach`), closed
    under the frontage's own Lipschitz reach ``a`` ALONG THE RING
    (:func:`arc_distance`: two contacts' apron levels differ by at most
    ``a`` times the frontage between them).

    WHY THE CONTACT'S OWN GROUND AND THE NEAREST ``q`` (spec §2 (1) read
    ``∩`` over EVERY taxi edge vertex of the fronted bodies at its DEM):
    MEASURED on the HECA dry read (lane ``flatpad111b``) the DEM at T3's
    526 taxi edge vertices is itself 1.5 %-inconsistent in 6,416 of 138,075
    pairs — the solved taxiways are not on the DEM — which emptied 475 of
    2,452 T3 bands and all 243 of T2's, and a band read from the far field
    at the building's own face put T2's datum 5.4 m below every contact.
    The local reading asks the spec's own question (``ℓ_max ≈ 2·a·d /
    grade``, §2's pre-registered verdicts) of the apron that fronts the
    contact."""
    L, U = z - r, z + r
    n = z.shape[0]
    if n >= 2 and np.isfinite(r).all():
        L2, U2 = L.copy(), U.copy()
        for i0 in range(0, n, 512):
            d = arc_distance(S[i0:i0 + 512], S, perim)
            L2[i0:i0 + 512] = np.max(L[None, :] - a * d, axis=1)
            U2[i0:i0 + 512] = np.min(U[None, :] + a * d, axis=1)
        L, U = L2, U2
    return L, U


def _datum(L: np.ndarray, U: np.ndarray, z: np.ndarray) -> tuple[float, float]:
    """``(D, worst miss)`` for one block: the level of the block's band
    nearest its contacts' median ground (the least apron moves for it); an
    empty band takes its midpoint and misses by half its width.  Contacts no
    level serves (``L > U``) do not vote."""
    ok = L <= U
    if not ok.any():
        return float(np.median(z)), float("inf")
    lo, hi = float(np.max(L[ok])), float(np.min(U[ok]))
    if lo <= hi:
        return float(min(max(float(np.median(z)), lo), hi)), 0.0
    return 0.5 * (lo + hi), 0.5 * (lo - hi)


def hold_mask(D: np.ndarray, own: np.ndarray, S: np.ndarray, perim: float,
              L: np.ndarray, U: np.ndarray, a: float) -> tuple[np.ndarray, np.ndarray]:
    """``(held, ramp)`` per contact: HELD iff its band contains its block's
    datum and it stands at least ``|ΔD| / (2a)`` from every other block's
    frontage (spec §2 (2): the apron ramps between two held frontages over
    ``|ΔD| / a``); RAMP marks the contacts the second test freed."""
    held = (L <= D[own]) & (D[own] <= U)
    ramp = np.zeros(len(own), dtype=bool)
    ks = sorted(set(own.tolist()))
    for b in ks:
        mb = own == b
        for b2 in ks:
            if b2 == b:
                continue
            w = abs(float(D[b] - D[b2])) / (2.0 * a)
            if w <= 0.0:
                continue
            d = np.min(arc_distance(S[mb], S[own == b2], perim), axis=1)
            near = d < w
            idx = np.flatnonzero(mb)[near]
            ramp[idx] = True
    return held & ~ramp, ramp


def _chords(Q: Polygon, seeds: int, dirs: int) -> list[LineString]:
    """Straight chords of ``Q`` (each a segment of a line through a seed
    point, both ends on the exterior) — the candidate cut lines.  Each end
    is SNAPPED to the nearest EXISTING ring vertex: a cut that ended mid-
    edge would add a vertex to the pad rim, which the 23a weld shares with
    the apron — the pad stage minting an AIRSIDE vertex (``pad_airside_
    renode``, MEASURED arm 1 at HECA: +5), which spec §7 makes a STOP."""
    from scipy.spatial import cKDTree
    V = np.asarray(Q.exterior.coords[:-1], dtype=float)
    vt = cKDTree(V)
    cover = Q.buffer(1e-6)
    x0, y0, x1, y1 = Q.bounds
    step = max(1.0, math.sqrt(Q.area / max(1, seeds)))
    diam = math.hypot(x1 - x0, y1 - y0) + 1.0
    ext = Q.exterior
    seen: set = set()
    out: list[LineString] = []
    ys = np.arange(y0 + 0.5 * step, y1, step)
    xs = np.arange(x0 + 0.5 * step, x1, step)
    for y in ys:
        for x in xs:
            p = Point(x, y)
            if not Q.contains(p):
                continue
            for k in range(dirs):
                th = math.pi * k / dirs
                dx, dy = math.cos(th) * diam, math.sin(th) * diam
                g = Q.intersection(LineString([(x - dx, y - dy), (x + dx, y + dy)]))
                segs = [g] if isinstance(g, LineString) else list(getattr(g, "geoms", []))
                for s in segs:
                    if not isinstance(s, LineString) or s.length <= 0.0:
                        continue
                    if s.distance(p) > 1e-6:
                        continue
                    a_, b_ = Point(s.coords[0]), Point(s.coords[-1])
                    if ext.distance(a_) > 1e-6 or ext.distance(b_) > 1e-6:
                        continue
                    _d, (ia, ib) = vt.query([s.coords[0], s.coords[-1]])
                    if ia == ib:
                        continue
                    s = LineString([tuple(V[ia]), tuple(V[ib])])
                    if not cover.covers(s):
                        continue
                    key = tuple(sorted((tuple(round(v / step) for v in s.coords[0]),
                                        tuple(round(v / step) for v in s.coords[-1]))))
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(s)
    return out


def bisect_blocks(P: Polygon, C: np.ndarray, L: np.ndarray, U: np.ndarray,
                  z: np.ndarray, *, margin: float, bay_m: float, max_blocks: int,
                  neck: _t.Callable[[LineString], float],
                  seeds: int = _CHORD_SEEDS, dirs: int = _CHORD_DIRS
                  ) -> tuple[list[Polygon], list[LineString], list[float], bool]:
    """THE PARTITION (module docstring): ``(pieces, cuts, neck metres,
    complete)`` — ``complete`` False when ``max_blocks`` pieces still leave
    a block missing a contact by more than ``margin`` (the STOP)."""
    pieces: list[Polygon] = [P]
    cuts: list[LineString] = []
    necks: list[float] = []

    def miss(m: np.ndarray) -> float:
        if not m.any():
            return 0.0
        return _datum(L[m], U[m], z[m])[1]

    mem = [np.ones(C.shape[0], dtype=bool)]
    res = [miss(mem[0])]
    while len(pieces) < max_blocks:
        order = sorted(range(len(pieces)), key=lambda i: -res[i])
        i = order[0]
        if res[i] <= margin:
            return pieces, cuts, necks, True
        Q = pieces[i]
        ext = Q.exterior
        ix = np.flatnonzero(mem[i])
        tc = np.asarray([ext.project(Point(C[j])) for j in ix])
        best: list[tuple[float, int, LineString, np.ndarray, np.ndarray]] = []
        for s in _chords(Q, seeds, dirs):
            ta, tb = sorted((ext.project(Point(s.coords[0])),
                             ext.project(Point(s.coords[-1]))))
            side = (tc > ta) & (tc < tb)
            if min(side.sum(), (~side).sum()) * _STEP_M < bay_m:
                continue
            # a block never smaller than a jetway bay: a bay of frontage
            # AND a bay square of floor on each side
            try:
                ga = _split(Q, s).geoms
            except Exception:  # noqa: BLE001 — a degenerate chord
                continue
            if len(ga) != 2 or min(g.area for g in ga) < bay_m * bay_m:
                continue
            m0 = np.zeros(C.shape[0], dtype=bool)
            m1 = np.zeros(C.shape[0], dtype=bool)
            m0[ix[side]] = True
            m1[ix[~side]] = True
            best.append((max(miss(m0), miss(m1)), len(best), s, m0, m1))
        if not best:
            break
        w0 = min(b[0] for b in best)
        cand = [b for b in best if b[0] <= w0 + margin]
        cand.sort(key=lambda b: (neck(b[2]), b[0]))
        done = False
        for worst, _n, s, m0, m1 in cand:
            try:
                parts = [g for g in _split(Q, s).geoms if isinstance(g, Polygon)]
            except Exception:  # noqa: BLE001 — a degenerate chord
                continue
            if len(parts) != 2:
                continue
            p0 = C[np.flatnonzero(m0)[0]]
            if parts[0].distance(Point(p0)) > parts[1].distance(Point(p0)):
                parts.reverse()
            pieces[i:i + 1] = parts
            mem[i:i + 1] = [m0, m1]
            res[i:i + 1] = [miss(m0), miss(m1)]
            done = True
            break
        if not done:
            break
        necks.append(neck(s))
        cuts.append(s)
    return pieces, cuts, necks, max(res) <= margin


_PART_CACHE: dict[int, tuple] = {}


def _part_index(airport) -> "tuple[list[Polygon], _t.Any] | None":
    """The FOOTED pack parts' footprints (plan xy) and an STRtree over them,
    once per airport — the neck's measure."""
    from shapely.strtree import STRtree
    key = id(airport)
    hit = _PART_CACHE.get(key)
    if hit is not None and hit[0] is airport:
        return hit[1], hit[2]
    part = getattr(airport, "partition", None)
    if part is None:
        return None
    to_xy = airport.frame.entry()
    polys: list[Polygon] = []
    for u in part.units:
        for m in u.members:
            for p in m.parts:
                if getattr(p, "line", False) or not getattr(p, "feet", ()):
                    continue
                for r in getattr(p, "rings", ()) or ():
                    if len(r) < 3:
                        continue
                    q = Polygon([to_xy(float(lo), float(la)) for la, lo in r])
                    if not q.is_valid:
                        q = q.buffer(0)
                    if not q.is_empty and q.area > 0.0:
                        polys.append(q)
    tree = STRtree(polys) if polys else None
    _PART_CACHE.clear()
    _PART_CACHE[key] = (airport, polys, tree)
    return polys, tree


def _sample_ring(ring, step: float) -> list[tuple[float, float]]:
    n = max(4, int(ring.length // step))
    return [ring.interpolate(i * ring.length / n).coords[0] for i in range(n)]


def _dem(dem, x: float, y: float) -> float:
    try:
        return float(dem.z(x, y))
    except Exception:  # noqa: BLE001 — off the raster: no witness
        return float("nan")


def bay_m(law) -> float:
    """The smallest block's frontage: one jetway BAY — the apron strip a
    gate holds level with the terminal, ``emit.design.jetway_strip_m`` (the
    jetway-strip spec's measured cabin reach; 30r: no block smaller than a
    jetway bay)."""
    return float(law.tables.emit.design.jetway_strip_m)


def plan_blocks(ref: str, P: Polygon, base_regions, law, dem, airport,
                near: float) -> "BlockPlan | None":
    """The §2 test and partition for one platform pad (module docstring)."""
    from ..law.tables import (apron_roles, is_rigid_role, role_cap, role_side,
                              zone2_half_width_m)
    if dem is None or airport is None:
        return None
    # the arrangement's regions carry a PRECISION GRID (0.5 m): a chord cut
    # of a gridded polygon snaps its ends off the ring, so the partition
    # reads the pad at full precision (the mint's own intersections snap
    # back to the grid)
    import shapely
    P = shapely.set_precision(P, 0.0)
    bp = law.tables.structures.building_pad
    margin = float(bp.frontage_hold_margin_m)
    cap_blocks = int(bp.frontage_blocks_max)
    p = law.tables.precedence
    runway_roles = set(p.runway_family.members)
    taxi_roles = set(p.taxi_family.members)
    ap_roles = {r for r in apron_roles(law)
                if role_side(law, r) == "airside" and not is_rigid_role(law, r)}
    a = float(role_cap(law, "apron").longitudinal)
    letters = [rw.code_letter for rw in getattr(airport, "runways", ()) if rw.code_letter]
    letter = max(letters) if letters else None
    t = float(law.ruleset.taxi.longitudinal.value(None, letter))
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
    fronted = [q for q in aprons if q.distance(P) <= near]
    if not fronted:
        return None
    afr = unary_union(fronted)
    ring = P.exterior
    perim = float(ring.length)
    samp = _sample_ring(ring, _STEP_M)
    step = perim / len(samp)
    keep = [i for i, xy in enumerate(samp) if afr.distance(Point(xy)) <= near]
    C = np.asarray([samp[i] for i in keep], dtype=float).reshape(-1, 2)
    S = np.asarray([i * step for i in keep], dtype=float)
    if C.shape[0] < 3:
        return None
    Cz = np.asarray([_dem(dem, x, y) for x, y in C])
    ok = np.isfinite(Cz)
    C, Cz, S = C[ok], Cz[ok], S[ok]
    if C.shape[0] < 3:
        return None
    tx = unary_union(taxis) if taxis else None
    pin_u = unary_union(pins) if pins else None
    Qs = []
    for g in fronted:
        for ring in (g.exterior, *g.interiors):
            for xy in _sample_ring(ring, _Q_STEP_M):
                if tx is not None and tx.distance(Point(xy)) <= _Q_TOUCH_M:
                    Qs.append(xy)
    Q = np.asarray(Qs, dtype=float).reshape(-1, 2)
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
    L, U = band(Cz, reach(C, Q, tau, a), S, perim, a)
    bay = bay_m(law)
    idx = _part_index(airport)

    def neck(s: LineString) -> float:
        if idx is None or idx[1] is None:
            return s.length
        polys, tree = idx
        return float(sum(s.intersection(polys[int(j)]).length
                         for j in tree.query(s, predicate="intersects")))

    pieces, cuts, necks, complete = bisect_blocks(
        P, C, L, U, Cz, margin=margin, bay_m=bay, max_blocks=cap_blocks, neck=neck)
    own = np.full(C.shape[0], -1, dtype=int)
    for k, g in enumerate(pieces):
        for i, (x, y) in enumerate(C):
            if own[i] < 0 and g.distance(Point(x, y)) <= 1e-6:
                own[i] = k
    own[own < 0] = 0
    D = np.zeros(len(pieces))
    for k in range(len(pieces)):
        m = own == k
        D[k] = _datum(L[m], U[m], Cz[m])[0] if m.any() else float(np.median(Cz))
    held, ramp = hold_mask(D, own, S, perim, L, U, a)
    plan = BlockPlan(ref, "", int(C.shape[0]), int(Q.shape[0]), [], bay_m=bay)
    for k, g in enumerate(pieces):
        m = own == k
        z = Cz[m]
        lo, hi = L[m], U[m]
        missv = np.maximum(0.0, np.maximum(lo - D[k], D[k] - hi))
        rmask = m & ~held & ~ramp
        plan.blocks.append(Block(
            k, int(m.sum()), float(D[k]), held=int((held & m).sum()),
            residual=int(rmask.sum()),
            residual_max_m=float(missv[~(held[m] | ramp[m])].max()) if rmask.any() else 0.0,
            ramp=int((ramp & m).sum()),
            contact_min=float(z.min()) if z.size else 0.0,
            contact_max=float(z.max()) if z.size else 0.0,
            contact_median=float(np.median(z)) if z.size else 0.0,
            area_m2=float(g.area), frontage_m=float(m.sum() * _STEP_M), polygon=g,
            samples_xy=C[m], samples_held=held[m]))
    plan.cuts = list(cuts)
    plan.neck_m = list(necks)
    for s in cuts:
        near_k = sorted(range(len(pieces)), key=lambda k: pieces[k].distance(s.centroid))[:2]
        i, j = sorted(near_k)
        plan.steps.append((i, j, float(D[i] - D[j])))
    # the verdicts: one_block / split hold everywhere; a unit that still
    # misses is ``stop_cap`` when the block cap was reached (30k Q4: the
    # owner reads it) and ``residual`` when no admissible neck is left (a
    # further cut would leave a block under a jetway bay) — §2 (6)'s
    # residual, carried by the collar and reported
    if complete:
        plan.verdict = "one_block" if len(pieces) == 1 else "split"
    else:
        plan.verdict = "stop_cap" if len(pieces) >= cap_blocks else "residual"
        plan.note = (f"{'STOP' if plan.verdict == 'stop_cap' else 'RESIDUAL'}: "
                     f"{len(pieces)} block(s) still miss by "
                     f"{max(b.residual_max_m for b in plan.blocks):.2f} m")
    return plan
