"""AIRSIDE NO-STEP generator (family ``airside_no_step``, RULINGS
2026-08-27 "no steps in airside pavement": the runway-style grade +
curvature pair applied to ALL airside pavement).

Two terms, one law:

* §1.1 DIRECT-DISTANCE pairs: for every airside vertex, ``emit.no_step.k``
  law edges to its nearest airside vertices within ``emit.no_step.window_m``
  spread over eight sectors (two per sector), each a ``Diff`` at
  ``cap × direct distance`` where the cap is the strictest governed cap
  at either endpoint.  The solver publishes exactly these pairs
  (:func:`no_step_edges`, sidecar ``airside_no_step_edges``) and the
  census prices the same list — one law, one population.
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

THE POPULATION is derived from the tables (03i): the airside VALUE roles
that are governed and not rigid — a pad is a flat group levelled by its
contact and is never a no-step endpoint of its own (v1
``enclaves.ENCLAVE_AIRSIDE_ROLES`` is the same set by other means).
"""
from __future__ import annotations

import math

from ..law import Law
from ..law.tables import is_rigid_role, is_value_role, role_cap, role_side
from ..model.airport import Airport
from ..model.constraints import Diff, Linear, Row, Source
from ..model.planar import PlanarMap
from .precedence import View, view

__all__ = ["no_step_roles", "no_step_pairs", "no_step_rate",
           "no_step_edges", "rate_rows_for_chain"]

GEN = "no_step"
_SECTORS = 8


def no_step_roles(law: Law) -> frozenset[str]:
    """Airside, value-carrying, governed, not rigid (03i)."""
    reg = law.tables.precedence.roles
    return frozenset(r for r in reg
                     if role_side(law, r) == "airside" and is_value_role(law, r)
                     and role_cap(law, r) is not None and not is_rigid_role(law, r))


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


def no_step_edges(planar: PlanarMap, law: Law
                  ) -> list[tuple[int, int, float, float]]:
    """``(a, b, cap, direct distance)`` per published pair — K nearest
    per vertex over eight sectors within the window, deduplicated."""
    vw = view(planar, law)
    ns = law.tables.emit.no_step
    caps = _airside_vertices(vw, no_step_roles(law))
    ids = sorted(caps)
    if not ids:
        return []
    cell = ns.window_m
    grid: dict[tuple[int, int], list[int]] = {}
    for v in ids:
        x, y = vw.xy[v]
        grid.setdefault((int(x // cell), int(y // cell)), []).append(v)
    per_sector = max(1, ns.k // _SECTORS)
    seen: set[tuple[int, int]] = set()
    out: list[tuple[int, int, float, float]] = []
    for v in ids:
        x, y = vw.xy[v]
        cx, cy = int(x // cell), int(y // cell)
        buckets: list[list[tuple[float, int]]] = [[] for _ in range(_SECTORS)]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for u in grid.get((cx + dx, cy + dy), ()):
                    if u == v:
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


def no_step_pairs(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """§1.1 as ``Diff`` rows."""
    src = Source(GEN, "airside_no_step §1.1 (2026-08-27)", ())
    return [Diff(a, b, cap, d, src) for a, b, cap, d in no_step_edges(planar, law)]


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
