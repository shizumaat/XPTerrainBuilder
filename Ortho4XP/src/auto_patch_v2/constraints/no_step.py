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

THE PAD↔PAVEMENT PAIRS (M5; RULINGS 2026-09-04i closing 03k; measured
feasible at SPJC, M3b §4): a RIGID airside vertex (a pad's, touching
rigid faces and nothing else) joins the population as an endpoint
AGAINST pavement only (``pad_pavement_edges``, its own list and
sidecar key) — a pair whose both endpoints are pad-only vertices prices
one flat value against another and is not minted, and a pad vertex a
groundside lot shares is the lot's (09-01g); the cap is the strictest
governed cap at either endpoint (a pad carries the apron law,
``common.roles.building``).  A pad is not pavement and lies on no route:
these pairs stay K-per-sector at DIRECT distance (04o names pavement
pairs; the pad pairs are left for the owner — m5b-report open question).
The pad is the junior tier, so where the pair contradicts a governed
surface the pad's side yields (``solve/tiers.py``).
"""
from __future__ import annotations

import math

from ..law import Law, LawError
from ..law.tables import is_rigid_role, is_value_role, role_cap, role_side
from ..model.airport import Airport
from ..model.constraints import REACH_GENERATOR, Band, Diff, Linear, Row, Source
from ..model.planar import PlanarMap
from .routes import reach, route_neighbours, routes
from .precedence import View, view
from .runway_profile import threshold_pins

__all__ = ["no_step_roles", "rigid_airside_roles", "no_step_pairs",
           "no_step_rate", "no_step_edges", "pad_only_vertices",
           "pad_pavement_edges", "rate_rows_for_chain", "reach_bands",
           "reach_band_values"]

GEN = "no_step"
_SECTORS = 8


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


def _sector_pairs(vw: View, ns, caps: dict[int, float], sources: list[int],
                  targets: dict[int, float], skip_pair) -> list[tuple[int, int, float, float]]:
    """K nearest ``targets`` per source over eight sectors within the
    window, deduplicated; ``caps`` maps every vertex to its cap."""
    cell = ns.window_m
    grid: dict[tuple[int, int], list[int]] = {}
    for v in sorted(targets):
        x, y = vw.xy[v]
        grid.setdefault((int(x // cell), int(y // cell)), []).append(v)
    per_sector = max(1, ns.k // _SECTORS)
    seen: set[tuple[int, int]] = set()
    out: list[tuple[int, int, float, float]] = []
    for v in sources:
        x, y = vw.xy[v]
        cx, cy = int(x // cell), int(y // cell)
        buckets: list[list[tuple[float, int]]] = [[] for _ in range(_SECTORS)]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for u in grid.get((cx + dx, cy + dy), ()):
                    if u == v or skip_pair(v, u):
                        continue
                    ux, uy = vw.xy[u]
                    d = math.hypot(ux - x, uy - y)
                    if d > ns.window_m or d <= 0.0:
                        continue
                    sec = int(((math.atan2(uy - y, ux - x) + math.pi)
                               / (2.0 * math.pi)) * _SECTORS) % _SECTORS
                    buckets[sec].append((d, u))
        for b in buckets:
            b.sort()
            for d, u in b[:per_sector]:
                key = (v, u) if v < u else (u, v)
                if key in seen:
                    continue
                seen.add(key)
                out.append((key[0], key[1], min(caps[v], caps[u]), d))
    return out


def no_step_edges(planar: PlanarMap, law: Law
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
    vw = view(planar, law)
    caps = _airside_vertices(vw, no_step_roles(law))
    g = routes(planar, law)
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
    return reach(routes(planar, law), pins)


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


def pad_pavement_edges(planar: PlanarMap, law: Law
                       ) -> list[tuple[int, int, float, float]]:
    """``(pad vertex, pavement vertex, cap, direct distance)`` — the PAD↔
    PAVEMENT pairs (M5): from every pad-only vertex, K nearest pavement
    vertices per sector within the window; never pad↔pad.  Published
    under their own sidecar key (``pad_pavement_no_step_edges``) so the
    pavement list the v1 oracle prices is unchanged, and priced by v2
    verify by identity."""
    vw = view(planar, law)
    pav = _airside_vertices(vw, no_step_roles(law))
    pads = pad_only_vertices(planar, law)
    if not pads:
        return []
    caps = dict(pav)
    caps.update(pads)
    return _sector_pairs(vw, law.tables.emit.no_step, caps, sorted(pads), pav,
                         lambda v, u: False)


def no_step_pairs(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """§1.1 as ``Diff`` rows: the pavement pairs, then the pad↔pavement
    pairs (M5; the pad is the junior tier and yields first)."""
    src = Source(GEN, "airside_no_step §1.1 route pairs (2026-08-27, 04o/04q-1)", ())
    src_pad = Source(GEN, "airside_no_step §1.1 pad↔pavement (M5, 2026-09-04i)", ())
    return ([Diff(a, b, cap, d, src) for a, b, cap, d in no_step_edges(planar, law)]
            + [Diff(a, b, cap, d, src_pad) for a, b, cap, d in pad_pavement_edges(planar, law)])


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
