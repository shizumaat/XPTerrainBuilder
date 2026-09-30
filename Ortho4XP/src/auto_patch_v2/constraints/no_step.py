"""AIRSIDE NO-STEP generator (family ``airside_no_step``, RULINGS
2026-08-27 "no steps in airside pavement", CLARIFIED by 2026-09-04o /
04q-1: the pairs are formed ALONG PAVEMENT and priced over the ROUTE).

Two terms, one law:

* §1.1 ROUTE-DISTANCE pairs: for every airside vertex, ``emit.no_step.k``
  law edges to its nearest airside vertices BY ROUTE DISTANCE through the
  taxi network (``planar.routes``) within ``emit.no_step.window_m`` ROUTE
  metres, each a ``Diff`` whose bound is ``Σ cap_e · len_e`` along that
  path — the path's own caps, so an apron↔taxiway pair carries the
  taxiway's cap on the taxiway stretch and the apron's on the apron
  stretch, never the apron's 1 % over a plan chord (04q-1; measured
  trigger CYXY apron 156, `why-report-cyxy.md`).  A pair with no pavement
  path inside the window DOES NOT EXIST (04o: "aircraft can't travel
  straight across the grass").  ``emit.no_step.metric`` must read
  ``"route"`` — the chord metric is the refuted reading and is refused.
  The solver publishes exactly these pairs (:func:`no_step_edges`,
  sidecar ``airside_no_step_edges`` with ``budget_m`` and the ROUTE
  ``dist_m``) and the census prices the same list — one law, one
  population.
* §1.2 RATE OF CHANGE along every airside ring sequence (wrap-around
  triples included, as the census walks them): the grade change across a
  station may not outrun the aerodrome's vertical-curve rate
  (``rulesets.strip.arc_rate`` — ONE constant, the strip family's,
  never a second number), a three-term ``Linear`` row
  ``|(z_c − z_b)/dn − (z_b − z_a)/dp| ≤ rate · (dp + dn)/2 + q·(1/dp + 1/dn)``.
  The second term is THE RATE READER'S OWN BLIND SPOT
  (``emit.instrument.coarse_noise_m``; v1 ``_rate_reader_blind_spot``):
  a ring SEQUENCE is the instrument's walk, not a travel path — at a
  ring corner beside a crowned ridge the exact rate is unsatisfiable at
  1–3 m spacings (measured CYXY 02/20: crown floor + rate + direct pair
  form an IIS), and the reader itself cannot distinguish such a station
  from rounding.  Bound in the instrument's frame, stated once here.

THE REACH BANDS (04o; v1 ``reach_band_unified`` as a v2 constraint):
the runway thresholds' CIFP values propagated along every route at the
path caps give each airside vertex a floor and a ceiling
(``planar.routes.reach``), minted as ``Band`` rows under
``model.constraints.REACH_GENERATOR`` — the solver cannot place a vertex
outside what any route from the thresholds allows.  They are the
envelope the hard path rows already imply; the law-ordered solve
withdraws them once a tier yields (``solve/tiers.py``).

THE POPULATION is derived from the tables (03i): the airside VALUE roles
that are governed and not rigid — a pad is a flat group levelled by its
contact and is never a no-step endpoint of its own (v1
``enclaves.ENCLAVE_AIRSIDE_ROLES`` is the same set by other means).

THE PAD↔PAVEMENT PAIRS (RULINGS 2026-09-04r, under 03h/03i + 04o; M5's
chord population refuted at HECA: 1,181 tier-8 rows, the one population
still chord-priced, m5b-report §5): a pad is a flat group LEVELLED BY
ITS CONTACT, so its only law edge to pavement is the CONTACT EDGE — the
vertices its rim shares with airside pavement — priced at the pavement's
own caps along the pavement route.  ``pad_pavement_edges``: for every
ATTACHED pad, from each contact vertex the K nearest pavement vertices
BY ROUTE within the window, the pad's own group never a partner (one
flat value against itself) and never spending the K; each pair
``Σ cap·len`` along its path exactly as a pavement pair.  A DETACHED pad
(no contact) has NO pairs — a DEM-levelled flat group (03h).  The pad's
BODY vertices are never an endpoint: free-standing pad↔pavement chords
do not exist.  A contact vertex a groundside lot shares is the lot's
(09-01g).  Published under the sidecar key ``pad_pavement_no_step_edges``
as the pairs the pavement list does not already carry (the contact
vertex is itself a pavement vertex, so its own K-nearest are in
``airside_no_step_edges``; the v1 oracle's proximity join is why the key
stays separate, M5 §3), priced by v2 verify by identity.  The row's tier
is the contact's owner (the apron), never the pad's: the pad pairs are
apron law.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from ..law import Law, LawError
from ..law.tables import is_rigid_role, is_value_role, role_cap, role_side
from ..model.airport import Airport
from ..model.constraints import (REACH_GENERATOR, Band, ConstraintSet, Diff,
                                 Linear, Row, Source)
from ..model.planar import PlanarMap
from .routes import reach, route_neighbours, routes
from .precedence import View, view
from .runway_profile import threshold_pins

__all__ = ["no_step_roles", "rigid_airside_roles", "no_step_pairs",
           "no_step_rate", "no_step_edges", "pad_only_vertices", "pad_contacts",
           "pad_pavement_edges", "rate_rows_for_chain", "reach_bands",
           "reach_band_values", "hold_interval", "hold_pass", "HoldPass",
           "HoldInterval", "pair_graph", "runway_membership", "RUNWAY_FLEX",
           "FLEX_RULING"]

GEN = "no_step"
#: The §1.1 pair rows' ruling prefix (both the pavement and the pad-contact
#: pairs): the yielding transform selects them by it (``constraints/yielding.py``).
PAIR_RULING_PREFIX = "airside_no_step §1.1"


def no_step_roles(law: Law) -> frozenset[str]:
    """Airside, value-carrying, governed, not rigid (03i)."""
    reg = law.tables.precedence.roles
    return frozenset(r for r in reg
                     if role_side(law, r) == "airside" and is_value_role(law, r)
                     and role_cap(law, r) is not None and not is_rigid_role(law, r))


def rigid_airside_roles(law: Law) -> frozenset[str]:
    """Airside, value-carrying, governed, RIGID (a pad) — the pad side
    of the pad↔pavement pairs."""
    reg = law.tables.precedence.roles
    return frozenset(r for r in reg
                     if role_side(law, r) == "airside" and is_value_role(law, r)
                     and role_cap(law, r) is not None and is_rigid_role(law, r))


def _airside_vertices(vw: View, roles: frozenset[str]) -> dict[int, float]:
    """Vertex -> strictest airside cap over its no-step faces."""
    out: dict[int, float] = {}
    for f in vw.faces_of_role(roles):
        c = vw.caps[f.id]
        if c is None:
            continue
        for v in vw.rings[f.id]:
            out[v] = min(out.get(v, c[0]), c[0])
        for h in vw.holes[f.id]:
            for v in h:
                out[v] = min(out.get(v, c[0]), c[0])
    return out


def no_step_edges(planar: PlanarMap, law: Law, airport: Airport | None = None
                  ) -> list[tuple[int, int, float, float]]:
    """``(a, b, cap, route distance)`` per published PAVEMENT pair — K
    nearest per airside vertex BY ROUTE within the window (route metres),
    deduplicated; ``cap`` is the PATH cap ``budget / route distance`` so
    ``Diff.bound_m`` is exactly ``Σ cap_e · len_e`` along the path
    (04q-1).  The list the oracle prices (``budget_m`` = the bound,
    ``dist_m`` = the route); unchanged by the pad pairs."""
    ns = law.tables.emit.no_step
    if ns.metric != "route":
        raise LawError(f"emit.no_step.metric = {ns.metric!r}: only \"route\" is lawful "
                       "(RULINGS 2026-09-04o — a chord metric is the refuted reading)")
    # ONE READ PER MAP (jetway-strip spec §5 bar 5): the generator, the
    # strip's strike set and the publication all ask for the same list on
    # the same frozen map; a two-entry identity memo keeps it one route walk
    # (HECA ~1 s each).  The caller gets a copy.
    key = (id(planar), id(law), id(airport))
    for k, pm, lw, ap, got in _EDGES_MEMO:
        if k == key and pm is planar and lw is law and ap is airport:
            return list(got)
    out = _no_step_edges(planar, law, airport, ns)
    _EDGES_MEMO.append((key, planar, law, airport, tuple(out)))
    del _EDGES_MEMO[:-2]
    return out


_EDGES_MEMO: list[tuple] = []


def _no_step_edges(planar: PlanarMap, law: Law, airport: Airport | None, ns
                   ) -> list[tuple[int, int, float, float]]:
    vw = view(planar, law)
    caps = _airside_vertices(vw, no_step_roles(law))
    g = routes(planar, law, airport)
    out: list[tuple[int, int, float, float]] = []
    for a, b, d, bud in route_neighbours(g, caps, ns.window_m, ns.k, targets=caps):
        if d <= 0.0:
            continue
        out.append((a, b, bud / d, d))
    return out


def reach_band_values(planar: PlanarMap, law: Law, airport: Airport
                      ) -> dict[int, tuple[float, float]]:
    """Vertex -> ``(floor, ceiling)`` from the threshold pins along the
    routes (``planar.routes.reach``); empty when no runway carries a
    CIFP threshold."""
    pins = threshold_pins(planar, law, airport)
    if not pins:
        return {}
    return reach(routes(planar, law, airport), pins)


#: THE RUNWAY FLEX RECORDS of the last solve (flat-pad spec v2 §6 A11):
#: one per PULLED runway, written by :meth:`HoldPass.finish`, reset by
#: :func:`hold_pass` — the sidecar's ``runway_flex`` (``pipeline/
#: publication``), an empty list where no runway was pulled.
RUNWAY_FLEX: list[dict] = []

#: The ruling HEAD of the runway's flex budget ``Band`` rows — named by
#: ``[design] hard_rulings`` (flat-pad spec v2 §1 (4))
FLEX_RULING = "rulesets.runway.flex_budget"
FLEX_GEN = "runway_flex"


def runway_stage_family(law: Law) -> frozenset[str]:
    """The runway family's roles (``precedence.toml``)."""
    from ..law.tables import role_family
    return frozenset(r for r in law.tables.precedence.roles
                     if role_family(law, r) == "runway")


def _median(vals: list[float]) -> float:
    v = sorted(vals)
    return v[len(v) // 2]


def pair_graph(planar: PlanarMap, cs: ConstraintSet,
               cols: _t.AbstractSet[int],
               heads: _t.AbstractSet[str] | None = None) -> "RouteGraph":
    """THE PAIR GRAPH (flat-pad spec v2 §2): one edge per ``Diff`` cap row
    of ``cs`` between two vertices of ``cols`` (stage 1's columns and its
    pins), budget ``cap · d`` — the rows themselves, so a datum inside the
    interval it certifies is exactly one for which a Lipschitz extension of
    every pair cap exists (McShane–Whitney); parallel rows keep the least
    budget; a rigid ``Flat`` group's members are joined at budget 0.  A
    relief-offset row (``rel``) and a three-column row (``Linear``,
    ``taxi_box`` planes) are outside the pair metric.  Every vertex is a
    STATION (no leaf hop: the rows are the edges)."""
    import numpy as np
    from .routes import CENTRELINE, RouteGraph
    best: dict[tuple[int, int], tuple[float, float]] = {}
    for d in cs.diffs:
        a, b = int(d.a), int(d.b)
        if a == b or a not in cols or b not in cols or float(getattr(d, "rel", 0.0)):
            continue
        if heads is not None and d.source.ruling.split(" (")[0].strip() not in heads:
            continue
        k = (a, b) if a < b else (b, a)
        bud = float(d.cap) * float(d.d)
        cur = best.get(k)
        if cur is None or bud < cur[0]:
            best[k] = (bud, float(d.d))
    for f in cs.flats if heads is None else ():
        g = [int(v) for v in f.group if int(v) in cols]
        for u, v in zip(g, g[1:]):
            if u != v:
                best[(u, v) if u < v else (v, u)] = (0.0, 0.0)
    n = max(len(planar.vertices), (max(planar.vertices) + 1) if planar.vertices else 0)
    ks = sorted(best)
    a = np.array([k[0] for k in ks], np.int64)
    b = np.array([k[1] for k in ks], np.int64)
    bud = np.array([best[k][0] for k in ks], float)
    ln = np.array([best[k][1] for k in ks], float)
    # ``RouteGraph`` carries (cap, length); a zero-length edge carries its
    # budget as length 1 x cap (a Flat weld: 0 x 1)
    L = np.where(ln > 0.0, ln, 1.0)
    return RouteGraph(n=n, nodes=frozenset(int(v) for v in cols), a=a, b=b,
                      length=L, cap=bud / L, kind=np.full(len(a), CENTRELINE),
                      station=np.ones(n, bool))


def runway_membership(planar: PlanarMap, law: Law,
                      verts: _t.AbstractSet[int]) -> dict[int, tuple[str, ...]]:
    """Runway-family vertex -> the runway ids it belongs to: a ``runway``
    face's ref IS its runway id, a ``runway_crossing`` face's ref joins its
    runways with ``+`` (``runway_profile.crown_drops``' own reading)."""
    from ..law.tables import role_family
    out: dict[int, set[str]] = {}
    for f in planar.faces.values():
        if role_family(law, f.role) != "runway":
            continue
        ids = [str(f.ref)] if f.role == "runway" else str(f.ref).split("+")
        for ring in (f.ring, *f.holes):
            for v in planar.ring_vertices(ring):
                if v in verts:
                    out.setdefault(v, set()).update(ids)
    return {v: tuple(sorted(r)) for v, r in out.items()}


@_dc.dataclass
class HoldInterval:
    """:func:`hold_interval`'s answer: the rows pass 1b adds (datum pins,
    runway Bands, the re-priced residual holds), the per-block records and
    the per-runway flex records (``used_m`` filled by
    :meth:`HoldPass.finish`)."""

    rows: list
    blocks: dict[str, dict]
    runways: dict[str, dict]
    #: runway id -> {vertex: z¹ᵃ} over its Band-carrying columns
    columns: dict[str, dict[int, float]]
    #: the pair graph's size and the precondition read (§2)
    stats: dict = _dc.field(default_factory=dict)
    #: §5 the fronting set's vertices (``PlanarMap.fronting_vertices``)
    fronting: frozenset = frozenset()


def hold_interval(planar: PlanarMap, law: Law, cs: ConstraintSet,
                  z1a: _t.Mapping[int, float],
                  rw_cols: _t.Mapping[int, int]) -> HoldInterval | None:
    """THE FEASIBILITY INTERVAL OF EVERY HELD BLOCK AND THE RUNWAY'S FLEX
    BUDGET (flat-pad spec v2 §1 / §2, owner RULINGS 2026-09-30y (2) /
    30as) — the ONE derivation site of ``[design] runway_flex_share``.

    ``cs`` is PASS 1a's problem (stage 1 without the hold rows), ``z1a``
    its levelled airside values, ``rw_cols`` the runway's free columns
    (``solve.design.runway_columns``).  Per held block ``b`` with hold set
    ``C_b`` (``platform.hold_sets``): ``I_b = ∩_c [max_p (z_p − w_p −
    B(p,c)), min_p (z_p + w_p + B(p,c))]`` over the ANCHORS — every runway
    column at ``z¹ᵃ`` widened by its runway's budget ``w = β_R``, every
    stage-1 ``Pin`` at ``w = 0`` — on :func:`pair_graph`.

    (i) ``I⁰`` at every ``β_R = 0``: non-empty → the datum ``D_b`` is its
    point nearest the median of the contacts' ``z¹ᵃ``; empty → ``D⁰_b`` =
    the bound nearest that median.  ``Λ_c = |D_b − z¹ᵃ_c|``; ``R(c)`` =
    the runway of ``c``'s least-budget runway column; ``β_R =
    runway_flex_share · max Λ_c`` over ``R(c) = R``.  (ii) an empty
    block's interval re-read with the widened runway terms: non-empty → HELD
    at its point nearest the median; still empty → RESIDUAL (the bound
    nearest the median of the contact bands' mid-points; a contact whose
    band excludes it keeps its hold PRICED, ``HOLD_RESIDUAL_RULING``).
    No third pass: ``β_R`` is a constant of pass 1b.

    Rows: the datum ``Pin`` per block, ONE hard ``Band(p, z¹ᵃ_p ± β_R)``
    per column of every PULLED runway (``FLEX_RULING``), the residual
    holds re-priced.  ``None`` without a held block (nothing runs)."""
    import numpy as np
    from ..law.tables import design as design_law
    from ..model.platform import HELD
    from .platform import GEN as PGEN, HOLD_RULING, hold_sets, hold_row
    from .routes import reach_anchored, route_path
    sets = hold_sets(planar, law)
    if not sets:
        return None
    share = float(design_law(law).runway_flex_share)
    # every stage-1 Pin is a FIXED point of the interval — except a
    # YIELDING pin (``[design] yielding_pin_rulings``, 27a (10)): the law
    # releases it where the airside cannot reach it, so it anchors nothing
    yh = frozenset(getattr(design_law(law), "yielding_pin_rulings", ()) or ())
    pins = {int(p.v): float(p.z) for p in cs.pins
            if p.source.ruling.split(" (")[0].strip() not in yh}
    cols = set(int(v) for v in z1a) | set(pins)
    g = pair_graph(planar, cs, cols,
                   frozenset(design_law(law).interval_pair_rulings))
    rw_v = {int(v) for v in rw_cols if int(v) in z1a}
    member = runway_membership(planar, law, rw_v)
    rw_v = {v for v in rw_v if v in member}

    def zof(v: int) -> float:
        return float(z1a[v]) if v in z1a else float(pins[v])

    def anchors(beta: dict[str, float]) -> dict[int, tuple[float, float]]:
        out = {v: (z, 0.0) for v, z in pins.items()}
        for v in rw_v:
            out[v] = (float(z1a[v]), min(beta.get(r, 0.0) for r in member[v]))
        return out

    def interval(ar, cs_b: list[int]):
        lo_c = {c: float(ar.lo[c]) for c in cs_b if np.isfinite(ar.lo[c])}
        hi_c = {c: float(ar.hi[c]) for c in cs_b if np.isfinite(ar.hi[c])}
        lo = max(lo_c.values(), default=-math.inf)
        hi = min(hi_c.values(), default=math.inf)
        return lo, hi, lo_c, hi_c

    def nearest(lo: float, hi: float, m: float) -> float:
        # in the interval: its point nearest m; empty: the bound nearest m
        return min(max(m, lo), hi) if lo <= hi else min(max(m, hi), lo)

    ar0 = reach_anchored(g, anchors({}), transit=False)
    # THE PRECONDITION (§2): every anchor inside what the others allow it —
    # an anchor the rest exclude is a fixed pair farther apart than the
    # caps between them (``fronting_cap_infeasible``, reported)
    tol = float(design_law(law).hard_tol_m)
    bad = []
    diag = reach_anchored(g, anchors({}))            # WITH transit: the pairs
    for v, (z, _w) in anchors({}).items():
        if v in g.nodes:
            ex = max(float(diag.lo[v]) - z, z - float(diag.hi[v]))
            if ex > tol:
                bad.append((ex, v))
    stats = {"edges": int(len(g.a)), "nodes": len(g.nodes), "anchors_runway": len(rw_v),
             "anchors_pin": len(pins), "anchors_inconsistent": len(bad),
             "anchors_inconsistent_worst_m": round(max(bad)[0], 3) if bad else 0.0,
             "anchors_inconsistent_worst": (list(planar.vertices[max(bad)[1]].key)
                                            if bad else None)}
    pin_gen = {int(p.v): p.source.generator for p in cs.pins}
    by: dict[str, list] = {}
    for ex, v in bad:
        k = "runway" if v in rw_v else f"pin:{pin_gen.get(v, '?')}"
        by.setdefault(k, []).append((ex, v))
    stats["anchors_inconsistent_by"] = {
        k: [len(x), round(max(x)[0], 3), list(planar.vertices[max(x)[1]].key)]
        for k, x in sorted(by.items())}
    # every contact's LEAST-BUDGET runway column (R(c), §1 (2))
    near = reach_anchored(g, {v: (0.0, 0.0) for v in rw_v}, transit=False)
    blocks: dict[str, dict] = {}
    for pref, dv, weld, n_all, n_ramp in sets:
        if not weld:
            continue
        lo, hi, lo_c, hi_c = interval(ar0, weld)
        med = _median([zof(c) for c in weld if c in cols] or [0.0])
        D = nearest(lo, hi, med)
        blocks[pref] = {"dv": dv, "weld": weld, "n_all": n_all, "n_ramp": n_ramp,
                        "I0": (lo, hi), "empty0": lo > hi, "med": med, "D": D,
                        "unreached": sum(1 for c in weld if c not in lo_c and c not in hi_c)}
    if not blocks:
        return None
    # Λ_c and R(c) → β_R
    lift: dict[str, tuple[float, str, int]] = {}
    for pref, b in blocks.items():
        for c in b["weld"]:
            if c not in cols:
                continue
            path = near.binding(c, "hi")
            if not path:
                continue
            p0 = path[0]
            lam = abs(b["D"] - zof(c))
            for r in member.get(p0, ()):
                if r not in lift or lam > lift[r][0]:
                    lift[r] = (lam, pref, c)
    beta = {r: share * lam for r, (lam, _p, _c) in lift.items()}
    ar1 = None
    for pref, b in blocks.items():
        if not b["empty0"]:
            b["eval"], b["I"], b["held"] = "i", b["I0"], True
            continue
        if ar1 is None:
            ar1 = reach_anchored(g, anchors(beta), transit=False)
        lo, hi, lo_c, hi_c = interval(ar1, b["weld"])
        b["I"] = (lo, hi)
        if lo <= hi:
            b["eval"], b["held"], b["D"] = "ii", True, nearest(lo, hi, b["med"])
            continue
        b["eval"], b["held"] = "residual", False
        mids = sorted(0.5 * (lo_c.get(c, -math.inf) + hi_c.get(c, math.inf))
                      for c in b["weld"] if c in lo_c and c in hi_c)
        m = mids[len(mids) // 2] if mids else b["med"]
        D = nearest(lo, hi, m)
        b["D"] = D
        b["residual"] = [c for c in b["weld"] if c in lo_c and c in hi_c
                         and not (lo_c[c] - 1e-9 <= D <= hi_c[c] + 1e-9)]
    # the rows
    rows: list = []
    for pref, b in blocks.items():
        res = set(b.get("residual") or ())
        for o in b["weld"]:
            rows.extend(hold_row(o, b["dv"], pref, residual=o in res))
        # THE DATUM BAND (§2 "Derivation site" / §5 "datum Band"): the
        # block's datum column within its pair-graph interval — HARD, head
        # ``HOLD_RULING``; a residual block's collapses to its chosen D.
        # ``D_b`` (§2 "The datum") sets the lift and the runway's budget;
        # the solver places the datum inside the band, so two held blocks
        # of one unit meet across their ramp (a per-block PIN at each
        # median measured SPJC building5 b0|b1 INFEASIBLE: 3.6 m over a
        # ramp of a few metres, 27 hard rows, 10.6 m shortfall)
        lo_b, hi_b = b["I"] if b["held"] else (b["D"], b["D"])
        rows.append(Band(b["dv"], lo_b if math.isfinite(lo_b) else None,
                         hi_b if math.isfinite(hi_b) else None,
                         Source(PGEN, HOLD_RULING + " (the block datum within "
                                "its pair-graph interval: flat-pad spec v2 §2, "
                                "RULINGS 2026-09-30y (2) / 30as)",
                                (pref, f"platform:{pref}"))))
    columns: dict[str, dict[int, float]] = {}
    seen: dict[str, set[int]] = {}
    for v in sorted(rw_v):
        for r in member[v]:
            if beta.get(r, 0.0) > 0.0 and rw_cols[v] not in seen.setdefault(r, set()):
                seen[r].add(rw_cols[v])
                columns.setdefault(r, {})[v] = float(z1a[v])
    for r, cmap in columns.items():
        src = Source(FLEX_GEN, FLEX_RULING + f" (flat-pad spec v2 §1 (4), RULINGS "
                     f"2026-09-30as: runway {r} flexes at most beta_R = "
                     f"runway_flex_share x its pulling route's lift)", (r,))
        for v, z in cmap.items():
            rows.append(Band(v, z - beta[r], z + beta[r], src))
    runways: dict[str, dict] = {}
    for r, (lam, pref, c) in sorted(lift.items()):
        path = near.binding(c, "hi")
        rp = route_path(g, c, path[0], weight="budget") if path else None
        runways[r] = {"runway": r, "share": share, "budget_m": round(beta[r], 3),
                      "lift_m": round(lam, 3), "pulling_block": pref,
                      "pulling_contact": list(planar.vertices[c].key),
                      "route_hops": (len(rp[2]) - 1) if rp else None,
                      "route_len_m": round(rp[0], 1) if rp else None,
                      "route_budget_m": round(rp[1], 3) if rp else None}
    # the per-block record (the sidecar's ``platforms[]``, P20)
    for pref, b in blocks.items():
        h = HELD[pref]
        lo, hi = b["I"]
        lo0, hi0 = b["I0"]

        def _r(x: float) -> float | None:
            return round(x, 3) if math.isfinite(x) else None
        h["hold_contacts"] = [(o, None) for o in b["weld"]
                              if o not in set(b.get("residual") or ())]
        h["welded_total"] = b["n_all"]
        h["reach_band"] = [_r(lo), _r(hi)]
        h["reach_band0"] = [_r(lo0), _r(hi0)]
        h["reach_width_m"] = _r(hi - lo) if lo <= hi else 0.0
        h["reach_gap_m"] = _r(lo - hi) if lo > hi else 0.0
        h["reach_gap0_m"] = _r(lo0 - hi0) if lo0 > hi0 else 0.0
        h["reach_empty"] = bool(lo > hi)
        h["reach_eval"] = b["eval"]
        h["reach_unreached"] = b["unreached"]
        h["datum_chosen"] = round(float(b["D"]), 3)
        h["residual"] = list(b.get("residual") or ())
        # the binding anchors of the (final) interval
        ar = ar1 if (b["eval"] != "i" and ar1 is not None) else ar0
        for side, pick in (("lo", max), ("hi", min)):
            vals = [(float(getattr(ar, side)[c]), c) for c in b["weld"]
                    if np.isfinite(getattr(ar, side)[c])]
            if not vals:
                continue
            _z, c = pick(vals)
            path = ar.binding(c, side)
            if path:
                h[f"reach_{side}_binding"] = {
                    "contact": list(planar.vertices[c].key),
                    "anchor": list(planar.vertices[path[0]].key),
                    "anchor_runway": list(member.get(path[0], ())),
                    "hops": len(path) - 1}
    # §5 THE FRONTING SET: per block the apron bodies welded to it, the
    # junction / taxi faces sharing a vertex with them, and every face on
    # the least-budget path from each held contact to its nearest fixed
    # vertex; the faces on a path that joins two INCONSISTENT anchors
    # (the precondition's failures, ``fronting_cap_infeasible``) are left
    # priced — the rows there cannot all hold
    from ..law.tables import airside_stage_roles
    front_roles = airside_stage_roles(law) - runway_stage_family(law)
    infeasible: set[int] = set()
    for _ex, v in bad:
        for side in ("lo", "hi"):
            infeasible.update(diag.binding(v, side))
    nearest_fixed = reach_anchored(g, {v: (0.0, 0.0) for v in anchors({})},
                                   transit=False)
    faces = planar.faces
    front_f: set[int] = set()
    for b in blocks.values():
        seed = set(b["weld"])
        apron_f = {fid for c in seed for fid in planar.vertices[c].incident_faces
                   if faces[fid].role in front_roles}
        body_v = {v for fid in apron_f for ring in (faces[fid].ring, *faces[fid].holes)
                  for v in planar.ring_vertices(ring)}
        touch = {fid for v in body_v for fid in planar.vertices[v].incident_faces
                 if faces[fid].role in front_roles}
        path_v: set[int] = set()
        for c in b["weld"]:
            if c in g.nodes:
                path_v.update(nearest_fixed.binding(c, "hi"))
        path_f = {fid for v in path_v - infeasible
                  for fid in planar.vertices[v].incident_faces
                  if faces[fid].role in front_roles}
        front_f |= apron_f | touch | path_f
    fronting = frozenset(v for fid in front_f
                         for ring in (faces[fid].ring, *faces[fid].holes)
                         for v in planar.ring_vertices(ring)) - frozenset(infeasible)
    stats.update(fronting_faces=len(front_f), fronting_vertices=len(fronting),
                 fronting_cap_infeasible_vertices=len(infeasible))
    stats.update(blocks=len(blocks),
                 held=sum(1 for b in blocks.values() if b["held"]),
                 held_eval_ii=sum(1 for b in blocks.values() if b["eval"] == "ii"),
                 residual=sum(1 for b in blocks.values() if not b["held"]),
                 runway_bands=sum(len(c) for c in columns.values()))
    return HoldInterval(rows, blocks, runways, columns, stats, fronting)


@_dc.dataclass
class HoldPass:
    """The frontage hold's two passes, bound by the caller (``solve`` may
    not import ``constraints``, M0 §1): :meth:`strip` gives PASS 1a's
    problem (``None`` = no hold row: pass 1a IS stage 1, nothing else
    runs), :meth:`derive` pass 1b's (:func:`hold_interval`),
    :meth:`finish` the per-runway flex records off pass 1b's values."""

    planar: PlanarMap
    law: Law
    result: HoldInterval | None = None

    def strip(self, cs: ConstraintSet) -> ConstraintSet | None:
        from .platform import HOLD_RULING
        keep = [r for r in cs.rows()
                if r.source.ruling.split(" (")[0].strip() != HOLD_RULING]
        if len(keep) == len(cs.rows()):
            return None
        return ConstraintSet.from_rows(keep)

    def derive(self, cs1a: ConstraintSet, z1a: _t.Mapping[int, float],
               rw_cols: _t.Mapping[int, int]) -> ConstraintSet | None:
        self.result = hold_interval(self.planar, self.law, cs1a, z1a, rw_cols)
        if self.result is None:
            return None
        return ConstraintSet.from_rows([*cs1a.rows(), *self.result.rows])

    def finish(self, z1b: _t.Mapping[int, float], z1b_all: _t.Any = None,
               caps_held: bool = True) -> list[dict]:
        out: list[dict] = []
        res = self.result
        if res is not None:
            for r, rec in res.runways.items():
                cm = res.columns.get(r, {})
                used, worst = 0.0, None
                for v, za in cm.items():
                    zb = z1b.get(v)
                    if zb is None and z1b_all is not None:
                        zb = float(z1b_all[v])
                    if zb is None:
                        continue
                    if abs(zb - za) > used or worst is None:
                        used, worst = max(used, abs(zb - za)), v
                lam = float(rec["lift_m"])
                out.append(dict(rec, used_m=round(used, 3),
                                share_used=(round(used / lam, 4) if lam > 0 else 0.0),
                                worst=(list(self.planar.vertices[worst].key)
                                       if worst is not None else None),
                                columns=len(cm), caps_held=bool(caps_held)))
        RUNWAY_FLEX[:] = out
        return out


def hold_pass(planar: PlanarMap, law: Law) -> HoldPass:
    """The caller's binding of the hold's two passes (``pipeline/build``,
    ``tools/v2_solve_replay``); resets :data:`RUNWAY_FLEX`."""
    RUNWAY_FLEX[:] = []
    return HoldPass(planar, law)


def reach_bands(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """THE REACH BANDS as ``Band`` rows (module docstring); a vertex whose
    floor exceeds its ceiling is skipped — the pins already contradict
    along the routes and the path rows will say so."""
    src = Source(REACH_GENERATOR, "reach band: threshold values along taxi routes "
                 "at the path caps (2026-09-04o)", ())
    rows: list[Row] = []
    for v, (lo, hi) in sorted(reach_band_values(planar, law, airport).items()):
        if lo <= hi:
            rows.append(Band(v, lo, hi, src))
    return rows


def pad_only_vertices(planar: PlanarMap, law: Law) -> dict[int, float]:
    """Vertex -> cap for every PAD-ONLY airside vertex: a rigid face's
    vertex touching rigid faces and nothing else (a pad vertex shared
    with airside pavement is that pavement's; one shared with a
    groundside lot is the lot's — a mixed pad, 09-01g: the terrace in
    the stand-off is lawful; measured SPJC: pairing it minted 7.2 m
    building|groundside_pavement rows)."""
    vw = view(planar, law)
    rigid = {r for r in law.tables.precedence.roles if is_rigid_role(law, r)}
    pav = _airside_vertices(vw, no_step_roles(law))
    return {v: c for v, c in _airside_vertices(vw, rigid_airside_roles(law)).items()
            if v not in pav and all(planar.faces[f].role in rigid
                                    for f in vw.vertex_faces[v])}


def pad_contacts(planar: PlanarMap, law: Law) -> dict[int, list[int]]:
    """Pad face id -> its CONTACT vertices, sorted: the rim vertices
    shared with airside pavement (the no-step roles), and — RULINGS
    2026-09-05ab — the rim vertices a ``frontage_near_miss`` row binds
    to an airside soft vertex (``pads.frontage_contacts``: the pad's
    doorway onto the route graph, ``routes`` CONTACT).  A pad with none
    is DETACHED and absent.  A rim vertex a groundside lot shares and no
    airside pavement does is the lot's (09-01g) and is no contact."""
    from .pads import frontage_contacts
    vw = view(planar, law)
    pav = _airside_vertices(vw, no_step_roles(law))
    rigid = {r for r in law.tables.precedence.roles if is_rigid_role(law, r)}
    near: dict[int, set[int]] = {}
    for e, j, pid, _d, _cap, _sf in frontage_contacts(planar, law):
        if e in pav:
            near.setdefault(pid, set()).add(j)
    out: dict[int, list[int]] = {}
    for f in vw.faces_of_role(rigid):
        seen: set[int] = set(near.get(f.id, ()))
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            seen.update(v for v in ring if v in pav)
        if seen:
            out[f.id] = sorted(seen)
    return out


def pad_pavement_edges(planar: PlanarMap, law: Law,
                       pavement: list[tuple[int, int, float, float]] | None = None,
                       airport: Airport | None = None
                       ) -> list[tuple[int, int, float, float]]:
    """``(contact vertex, pavement vertex, path cap, route distance)`` —
    THE PAD↔PAVEMENT PAIRS through the contact (module docstring, 04r):
    for every attached pad, from each contact vertex the K nearest
    pavement vertices by route inside the window, the pad's own vertices
    excluded, ``cap = budget / d`` so ``Diff.bound_m = Σ cap_e·len_e``
    along the path; pairs the pavement list (``pavement``, computed when
    not given) already carries are not repeated.  Detached pads: none."""
    contacts = pad_contacts(planar, law)
    if not contacts:
        return []
    ns = law.tables.emit.no_step
    vw = view(planar, law)
    pav = _airside_vertices(vw, no_step_roles(law))
    own: dict[int, set[int]] = {}
    for fid, cvs in contacts.items():
        group: set[int] = set(vw.rings[fid])
        for h in vw.holes[fid]:
            group.update(h)
        for v in cvs:
            own.setdefault(v, set()).update(group)
    have = {(a, b) for a, b, _c, _d in (pavement if pavement is not None
                                          else no_step_edges(planar, law, airport))}
    g = routes(planar, law, airport)
    out: list[tuple[int, int, float, float]] = []
    for a, b, d, bud in route_neighbours(g, sorted(own), ns.window_m, ns.k,
                                         targets=pav, exclude=own):
        if d <= 0.0 or (a, b) in have:
            continue
        out.append((a, b, bud / d, d))
    return out


def no_step_pairs(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """§1.1 as ``Diff`` rows: the pavement pairs, then the pad↔pavement
    pairs through the contact (04r; apron law rows by the vertex rule)."""
    src = Source(GEN, "airside_no_step §1.1 route pairs (2026-08-27, 04o/04q-1)", ())
    src_pad = Source(GEN, "airside_no_step §1.1 pad contact↔pavement route pairs "
                     "(2026-09-04r)", ())
    pav = no_step_edges(planar, law, airport)
    return ([Diff(a, b, cap, d, src) for a, b, cap, d in pav]
            + [Diff(a, b, cap, d, src_pad)
               for a, b, cap, d in pad_pavement_edges(planar, law, pav, airport)])


def rate_rows_for_chain(vw: View, chain: list[int], rate: float, src: Source,
                        closed: bool, q: float = 0.0) -> list[Row]:
    """Three-term rate rows over consecutive triples of ``chain``; ``q``
    is the reader's rounding quantum (its blind spot ``q·(1/dp+1/dn)``)."""
    idx = list(range(len(chain)))
    if closed:
        idx = idx + [0, 1]
    rows: list[Row] = []
    for k in range(1, len(idx) - 1):
        a, b, c = chain[idx[k - 1]], chain[idx[k]], chain[idx[k + 1]]
        if len({a, b, c}) < 3:
            continue
        dp, dn = vw.dist(a, b), vw.dist(b, c)
        if dp < 1e-6 or dn < 1e-6:
            continue
        bound = rate * 0.5 * (dp + dn) + q * (1.0 / dp + 1.0 / dn)
        terms = ((c, 1.0 / dn), (b, -(1.0 / dn + 1.0 / dp)), (a, 1.0 / dp))
        rows.append(Linear(terms, -bound, bound, src))
    return rows


def no_step_rate(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """§1.2 along every airside ring (wrap triples included)."""
    vw = view(planar, law)
    r = law.ruleset.strip.arc_rate
    rate = r.grade / r.per_m
    # the reader's blind spot LESS the one emit quantum: the LP sits on
    # its bounds, and a bound that spends the whole envelope is broken
    # by the 0.01 m rounding it is then read at (measured CYXY: 17 rate
    # rows 0.1 mm over, all at the bound)
    q = law.tables.emit.instrument.coarse_noise_m - law.tables.emit.materiality.elevation_m
    rows: list[Row] = []
    for f in vw.faces_of_role(no_step_roles(law)):
        src = Source(GEN, "airside_no_step §1.2 rate (2026-08-27)",
                     (f"face:{f.id}", f.ref))
        for ring in [vw.rings[f.id], *vw.holes[f.id]]:
            if len(ring) >= 3:
                rows.extend(rate_rows_for_chain(vw, ring, rate, src, True, q))
    return rows
