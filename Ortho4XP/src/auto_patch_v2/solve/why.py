"""WHAT BINDS THIS SHAPE — the owner's sim-read question as one command
(lane v2why, 2026-09-04): ``python -m auto_patch_v2 why ICAO --shape N |
--at LAT,LON``.

Read-only over the pipeline's own LP (``pipeline/why.py`` rebuilds it:
load → classify → planar → constraints → the same HiGHS LP, no emit;
this module reads ``law`` and ``model`` only, 04q-3): for the vertices of one face
it prints the solved z, the DEM, z − dem, the ACTIVE rows touching them
(zero slack, with generator, ruling, the other endpoint's face / role,
cap, distance and the HiGHS dual), a CHAIN TRACE of binding rows from
the shape down to the nearest hard terminal (a CIFP pin, a seam value,
a band bound, or a vertex the objective holds on its DEM) whose bounds
sum to the height difference, and a RELAX-ONE-FAMILY table: for each
law family binding the shape, the full re-solve with that family's rows
dropped and how far the shape rises.  A relaxed family is a MEASUREMENT
ARM, never a build — nothing here writes a patch or edits a table.

Terms.  A row is BINDING when its slack is at most ``tol``.  A binding
row BLOCKS raising vertex ``v`` when raising ``v`` alone would break it;
the vertices that must rise with ``v`` are its successors, and the
chain follows successors to a terminal.  For a ``Diff`` at
``z[a] − z[b] = cap·d`` the successor of ``a`` is ``b`` — the chain runs
DOWNHILL, which is why an apron held ABOVE a low runway by a climbing
taxiway traces to the runway's pins.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import time
import typing as _t
from collections import deque

import numpy as np
from scipy.optimize import linprog

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import (Band, ConstraintSet, Diff, Flat, Linear,
                                 Offset, Pin, Row)
from ..model.planar import PlanarMap
from .api import Weights
from .assemble import Problem, assemble

__all__ = ["Prepared", "prepare", "solve_with_duals", "family_of",
           "resolve_faces", "Binding", "bindings", "Step", "Trace",
           "chain_trace", "RelaxResult", "relax_family", "taxi_letters",
           "report"]

#: Binding tolerance in metres — the LP sits on its bounds to ~1e-9.
BIND_TOL_M = 1e-5


# ── the prepared LP ──────────────────────────────────────────────────────

@_dc.dataclass
class Prepared:
    """Everything one ``why`` reads: the airport, the map, the rows, the
    assembled LP and its HiGHS result (duals kept)."""

    icao: str
    airport: Airport
    law: Law
    pm: PlanarMap
    cs: ConstraintSet
    counts: dict[str, int]
    weights: Weights
    prob: Problem
    res: _t.Any
    z: np.ndarray
    escalation: dict[str, float]
    wall: dict[str, float]
    #: THE RELAXED MODE (RULINGS 2026-09-04t(1)): when the hard set was
    #: infeasible, the last resort's report (``relax.RelaxReport``) and
    #: ``cs`` is the RELAXED hard set the LP above solved
    relaxation: _t.Any = None

    @property
    def dem(self) -> np.ndarray:
        return np.array([self.pm.vertices[i].dem_z if self.pm.vertices[i].dem_z is not None
                         else math.nan for i in range(len(self.pm.vertices))], float)


def solve_with_duals(pm: PlanarMap, cs: ConstraintSet, weights: Weights
                     ) -> tuple[Problem, _t.Any]:
    """The pipeline's LP (``solve.assemble.assemble`` + HiGHS) with the
    scipy result kept, so the row duals (``res.ineqlin.marginals``) can
    be read back against ``Problem.ub_rows``."""
    prob = assemble(pm, cs, weights)
    res = linprog(prob.c, A_ub=prob.A_ub, b_ub=prob.b_ub, A_eq=prob.A_eq,
                  b_eq=prob.b_eq, bounds=prob.bounds, method="highs",
                  options={"disp": False, "presolve": True})
    return prob, res


# ── families ─────────────────────────────────────────────────────────────

_FAMILY_KEYS: tuple[tuple[str, str, str], ...] = (
    # (generator, substring of the ruling, family label)
    ("taxi", "short-pair box", "taxi_box"),
    ("taxi", "chain", "taxi_chain"),
    ("apron", "chain", "apron_chain"),
    ("apron", "short-pair box", "apron_route_box"),
    ("runway_profile", "vertical_curve", "runway_vertical_curve"),
    ("runway_profile", "chain", "runway_chain"),
    ("taxi", "longitudinal centreline", "taxi_centreline"),
    ("taxi", "plane_gradient", "plane_gradient"),
    ("apron", "", "apron_within_shape"),
    ("no_step", "§1.1", "no_step_pairs"),
    ("no_step", "§1.2", "no_step_rate"),
    ("proximity", "", "cross_shape"),
    ("transverse", "", "transverse"),
    ("roads", "longitudinal", "road_within_shape"),
    ("roads", "cross_section", "road_cross_section"),
    ("runway_profile", "CIFP", "runway_pins"),
    ("runway_profile", "crown", "runway_crown"),
    ("runway_profile", "end_zone", "runway_end_zone"),
    ("runway_profile", "", "runway_profile"),
    ("zones", "strip tie", "strip_transverse"),
    ("zones", "", "zone_bands"),
    ("strips", "strip.longitudinal", "strip_longitudinal"),
    ("strips", "arc_rate", "strip_arc"),
    ("strips", "resa", "resa_transverse"),
    ("strips", "end_skirt", "end_corridor"),
    ("strips", "raoa", "raoa"),
    ("pads", "", "pads"),
    ("seams", "", "seam_values"),
    ("reach", "", "reach_bands"),
)


#: The route-reach bands (RULINGS 2026-09-04o) are the ENVELOPE the path
#: rows imply, not a law of their own: an arm that drops a family drops
#: them too, or the envelope of the rows just removed would still hold the
#: shape and every relax arm would read 0.000 (measured on the why
#: fixture: 1e-13 m for every family).
_ENVELOPE = "reach_bands"


def _drop(cs: ConstraintSet, families: _t.Sequence[str]) -> ConstraintSet:
    if not families:
        return cs
    bad = set(families) | {_ENVELOPE}
    return ConstraintSet.from_rows(r for r in cs.rows() if family_of(r) not in bad)


def family_of(row: Row) -> str:
    """The law family a row serves — generator + the ruling keyword."""
    g, r = row.source.generator, row.source.ruling
    for gen, key, label in _FAMILY_KEYS:
        if g == gen and key in r:
            return label
    return g


# ── target resolution ────────────────────────────────────────────────────

def face_vertices(prep: Prepared, fid: int) -> list[int]:
    f = prep.pm.faces[fid]
    out = list(prep.pm.ring_vertices(f.ring))
    for h in f.holes:
        out += list(prep.pm.ring_vertices(h))
    return out


# ── binding rows ─────────────────────────────────────────────────────────

@_dc.dataclass(frozen=True)
class Binding:
    """One binding row seen from vertex ``v``: the successors ``must_rise``
    (the vertices that must rise with ``v``), the row's family, the
    slack (m), the bound (m) and the HiGHS dual (objective per metre of
    bound; ``None`` when the row is a bound / equality without one)."""

    v: int
    row: Row
    family: str
    slack_m: float
    bound_m: float | None
    must_rise: tuple[int, ...]
    dual: float | None
    note: str = ""


def _row_index(prob: Problem) -> dict[int, list[tuple[str, int]]]:
    """``id(row)`` -> the LP rows it became (kind, index)."""
    idx: dict[int, list[tuple[str, int]]] = {}
    for k, r in enumerate(prob.ub_rows):
        if r is not None:
            idx.setdefault(id(r), []).append(("ub", k))
    for k, r in enumerate(prob.eq_rows):
        if r is not None:
            idx.setdefault(id(r), []).append(("eq", k))
    return idx


def _dual(prep: Prepared, idx: dict[int, list[tuple[str, int]]], row: Row,
          which: int = 0) -> float | None:
    hits = idx.get(id(row), [])
    if not hits or which >= len(hits):
        return None
    kind, k = hits[which]
    try:
        m = prep.res.ineqlin.marginals if kind == "ub" else prep.res.eqlin.marginals
        return float(m[k])
    except (AttributeError, IndexError, TypeError):
        return None


def _touching(cs: ConstraintSet) -> dict[int, list[Row]]:
    """Vertex -> every row naming it."""
    acc: dict[int, list[Row]] = {}

    def add(v: int, r: Row) -> None:
        acc.setdefault(v, []).append(r)

    for p in cs.pins:
        add(p.v, p)
    for d in cs.diffs:
        add(d.a, d); add(d.b, d)
    for f in cs.flats:
        for v in f.group:
            add(v, f)
    for b in cs.bands:
        add(b.v, b)
    for o in cs.offsets:
        add(o.a, o); add(o.b, o)
    for ln in cs.linears:
        for v, _c in ln.terms:
            add(v, ln)
    return acc


def _bindings_of(prep: Prepared, v: int, rows: list[Row], idx, tol: float
                 ) -> list[Binding]:
    """The binding rows of ``v`` with the successors raising ``v`` needs."""
    z, esc = prep.z, prep.escalation
    out: list[Binding] = []
    for r in rows:
        fam = family_of(r)
        if isinstance(r, Pin):
            out.append(Binding(v, r, fam, 0.0, None, (), _dual(prep, idx, r), "PIN"))
        elif isinstance(r, Diff):
            cap = r.cap + (esc.get(r.soft, 0.0) if r.soft is not None else 0.0)
            bound = cap * r.d
            other = r.b if r.a == v else r.a
            s_up = bound - (z[v] - z[other])       # v above other by the max
            if s_up <= tol:
                note = "" if r.soft is None else f"preference {r.soft}"
                out.append(Binding(v, r, fam, s_up, bound, (other,),
                                   _dual(prep, idx, r, 0 if r.a == v else 1), note))
        elif isinstance(r, Flat):
            out.append(Binding(v, r, fam, 0.0, 0.0, tuple(u for u in r.group if u != v),
                               _dual(prep, idx, r), "FLAT"))
        elif isinstance(r, Band):
            if r.hi is not None and r.hi - z[v] <= tol:
                out.append(Binding(v, r, fam, r.hi - z[v], None, (), None, "BAND hi"))
        elif isinstance(r, Offset):
            s = (z[r.a] - z[r.b]) - r.min_delta
            if s <= tol and v == r.b:               # raising b needs a to rise
                out.append(Binding(v, r, fam, s, r.min_delta, (r.a,),
                                   _dual(prep, idx, r), "OFFSET"))
        elif isinstance(r, Linear):
            s = sum(c * z[u] for u, c in r.terms)
            cv = dict(r.terms).get(v, 0.0)
            relax = esc.get(r.soft, 0.0) if r.soft is not None else 0.0
            if r.hi is not None and (r.hi + relax) - s <= tol and cv > 0:
                succ = tuple(u for u, c in r.terms if c < 0 and u != v)
                out.append(Binding(v, r, fam, (r.hi + relax) - s, r.hi, succ,
                                   _dual(prep, idx, r, 0),
                                   "at hi" + (f" (preference {r.soft})" if r.soft else "")))
            elif r.lo is not None and s - (r.lo - relax) <= tol and cv < 0:
                succ = tuple(u for u, c in r.terms if c > 0 and u != v)
                out.append(Binding(v, r, fam, s - (r.lo - relax), r.lo, succ,
                                   _dual(prep, idx, r, -1),
                                   "at lo" + (f" (preference {r.soft})" if r.soft else "")))
    return out


def bindings(prep: Prepared, verts: _t.Iterable[int], tol: float = BIND_TOL_M
             ) -> dict[int, list[Binding]]:
    """Binding rows per vertex of ``verts`` (raising direction)."""
    touching = _touching(prep.cs)
    idx = _row_index(prep.prob)
    return {v: _bindings_of(prep, v, touching.get(v, []), idx, tol) for v in verts}


# ── chain trace ──────────────────────────────────────────────────────────

@_dc.dataclass(frozen=True)
class Step:
    """One hop of the chain: ``v`` is blocked by ``row`` and must be
    followed by ``u``; ``dz`` = z[v] − z[u]."""

    v: int
    u: int
    family: str
    row: Row
    dz: float
    bound_m: float | None
    dual: float | None


@_dc.dataclass(frozen=True)
class Trace:
    """The shortest chain from the shape to a terminal."""

    start: int
    steps: tuple[Step, ...]
    terminal: int
    terminal_kind: str          # PIN | SEAM | BAND | FREE
    terminal_note: str
    reached: dict[str, int]     # terminals reachable by kind (count)
    visited: int

    @property
    def sum_dz(self) -> float:
        return sum(s.dz for s in self.steps)


def _terminal_kind(prep: Prepared, v: int, blist: list[Binding]) -> tuple[str, str] | None:
    """Whether ``v`` ends a chain, and why."""
    for b in blist:
        if b.note == "PIN":
            return "PIN", f"{b.row.source.ruling} ({b.row.source.inputs})"
        if b.note.startswith("BAND"):
            return "BAND", f"{b.row.source.ruling}"
        if b.family == "seam_values" and b.slack_m <= BIND_TOL_M:
            return "SEAM", "seam DEM value held"
    if not any(b.must_rise for b in blist):
        dem = prep.pm.vertices[v].dem_z
        from .assemble import vertex_weights
        w = float(vertex_weights(prep.pm, prep.weights)[v])
        rel = "on" if dem is not None and abs(prep.z[v] - dem) <= 1e-3 else (
            "above" if dem is not None and prep.z[v] > dem else "below")
        return "FREE", f"no binding row blocks it: {rel} its DEM (fit weight {w:g})"
    return None


def chain_trace(prep: Prepared, start: _t.Iterable[int], tol: float = BIND_TOL_M,
                max_visited: int = 200000) -> Trace | None:
    """BFS over binding rows from ``start`` (the shape's vertices) to the
    nearest terminal; PIN preferred over SEAM over BAND over FREE when
    several are reached at the same depth."""
    touching = _touching(prep.cs)
    idx = _row_index(prep.prob)
    start = list(start)
    q: deque[int] = deque(start)
    prev: dict[int, tuple[int, Binding] | None] = {v: None for v in start}
    found: dict[str, list[int]] = {}
    reached: dict[str, int] = {}
    order = ("PIN", "SEAM", "BAND", "FREE")
    depth_of: dict[int, int] = {v: 0 for v in start}
    stop_depth: int | None = None
    while q:
        v = q.popleft()
        if stop_depth is not None and depth_of[v] > stop_depth:
            break
        if len(prev) > max_visited:
            break
        bl = _bindings_of(prep, v, touching.get(v, []), idx, tol)
        term = None if v in start else _terminal_kind(prep, v, bl)
        if term is not None:
            reached[term[0]] = reached.get(term[0], 0) + 1
            found.setdefault(term[0], []).append(v)
            if term[0] == "PIN" and stop_depth is None:
                stop_depth = depth_of[v]
            continue
        for b in bl:
            for u in b.must_rise:
                if u not in prev:
                    prev[u] = (v, b)
                    depth_of[u] = depth_of[v] + 1
                    q.append(u)
    for kind in order:
        if found.get(kind):
            t = found[kind][0]
            break
    else:
        return None
    steps: list[Step] = []
    cur = t
    while prev[cur] is not None:
        v, b = prev[cur]
        steps.append(Step(v, cur, b.family, b.row, float(prep.z[v] - prep.z[cur]),
                          b.bound_m, b.dual))
        cur = v
    steps.reverse()
    bl = _bindings_of(prep, t, touching.get(t, []), idx, tol)
    tk = _terminal_kind(prep, t, bl) or ("FREE", "")
    return Trace(cur, tuple(steps), t, tk[0], tk[1], reached, len(prev))


# ── relax one family ─────────────────────────────────────────────────────

@_dc.dataclass(frozen=True)
class RelaxResult:
    family: str
    rows_dropped: int
    status: str
    dz_median: float
    dz_min: float
    dz_max: float
    zdem_median_after: float
    wall_s: float


def relax_family(prep: Prepared, family: str, verts: _t.Sequence[int]
                 ) -> RelaxResult:
    """Re-solve with every row of ``family`` dropped (and the reach
    envelope, ``_ENVELOPE``); the shape's rise."""
    from .highs import solve as _solve
    rows = [r for r in prep.cs.rows() if family_of(r) not in (family, _ENVELOPE)]
    dropped = len(prep.cs.rows()) - len(rows)
    t = time.perf_counter()
    sol = _solve(prep.pm, ConstraintSet.from_rows(rows), prep.weights)
    wall = time.perf_counter() - t
    if sol.status.value not in ("optimal", "feasible"):
        return RelaxResult(family, dropped, sol.status.value, math.nan, math.nan,
                           math.nan, math.nan, wall)
    z2 = np.asarray(sol.z, float)
    vs = list(verts)
    dz = z2[vs] - prep.z[vs]
    dem = prep.dem[vs]
    return RelaxResult(family, dropped, sol.status.value, float(np.median(dz)),
                       float(dz.min()), float(dz.max()),
                       float(np.nanmedian(z2[vs] - dem)), wall)


# ── the report ───────────────────────────────────────────────────────────

def _vname(prep: Prepared, v: int) -> str:
    fs = prep.pm.vertices[v].incident_faces
    roles = sorted({f"{prep.pm.faces[f].role}#{f}" for f in fs})
    return f"v{v}[" + ",".join(roles[:3]) + ("…" if len(roles) > 3 else "") + "]"


def _row_desc(prep: Prepared, b: Binding) -> str:
    r = b.row
    if isinstance(r, Diff):
        other = r.b if r.a == b.v else r.a
        return (f"{b.family:18s} cap {r.cap:.2%} × {r.d:6.1f} m = {b.bound_m:6.3f} m  "
                f"-> {_vname(prep, other)}")
    if isinstance(r, Linear):
        others = [u for u, _c in r.terms if u != b.v]
        return (f"{b.family:18s} {len(r.terms)}-term {b.note}; bound {b.bound_m if b.bound_m is not None else float('nan'):.4f} "
                f"-> {', '.join(_vname(prep, u) for u in others[:3])}")
    if isinstance(r, Pin):
        return f"{b.family:18s} PIN z={r.z:.3f} {r.source.ruling}"
    if isinstance(r, Flat):
        return f"{b.family:18s} FLAT group {len(r.group)} {r.source.ruling}"
    if isinstance(r, Band):
        return f"{b.family:18s} BAND hi={r.hi} {r.source.ruling}"
    if isinstance(r, Offset):
        return f"{b.family:18s} OFFSET ≥ {r.min_delta:.3f} -> {_vname(prep, r.a)}"
    return b.family


def report(prep: Prepared, fid: int, *, top: int = 3, relax: _t.Sequence[str] | None = None,
           max_relax: int = 5, tol: float = BIND_TOL_M,
           letters: _t.Sequence[str] | None = None) -> str:
    """The whole ``why`` for one face.  ``letters``: the code-letter
    evidence lines the caller read from the airport inputs
    (``pipeline.why.taxi_letters``) — the solver reads no producer."""
    f = prep.pm.faces[fid]
    verts = face_vertices(prep, fid)
    z, dem = prep.z, prep.dem
    L: list[str] = []
    zd = z[verts] - dem[verts]
    L.append(f"== face {fid}: role={f.role} ref={f.ref} letter={f.code_letter or '-'} "
             f"code={f.code_number or '-'} side={f.side} vertices={len(verts)}")
    L.append(f"   z {z[verts].min():.2f}..{z[verts].max():.2f}  DEM {np.nanmin(dem[verts]):.2f}.."
             f"{np.nanmax(dem[verts]):.2f}  z−dem median {np.nanmedian(zd):+.2f} "
             f"(min {np.nanmin(zd):+.2f}, max {np.nanmax(zd):+.2f})")
    bl = bindings(prep, verts, tol)
    fam_n: dict[str, int] = {}
    fam_d: dict[str, float] = {}
    for v, lst in bl.items():
        for b in lst:
            fam_n[b.family] = fam_n.get(b.family, 0) + 1
            fam_d[b.family] = fam_d.get(b.family, 0.0) + abs(b.dual or 0.0)
    L.append("-- binding rows on the shape's vertices, by family (rows, Σ|dual|):")
    for fam, n in sorted(fam_n.items(), key=lambda kv: -fam_d.get(kv[0], 0.0)):
        L.append(f"   {fam:20s} {n:6d}   {fam_d.get(fam, 0.0):10.2f}")
    if not fam_n:
        L.append("   (none: no row is binding here — the objective holds the shape)")
    L.append("-- vertices (z, DEM, z−dem, binding rows; top by |dual|):")
    for v in verts:
        lst = sorted(bl[v], key=lambda b: -abs(b.dual or 0.0))
        d = dem[v]
        L.append(f"   v{v:<6d} z {z[v]:8.3f}  dem {d:8.3f}  z−dem {z[v] - d:+7.3f}  "
                 f"binding {len(lst)}")
        for b in lst[:top]:
            du = f"dual {b.dual:9.3f}" if b.dual is not None else "dual     -   "
            L.append(f"        {du}  {_row_desc(prep, b)}")
    tr = chain_trace(prep, verts, tol)
    L.append("-- chain trace (binding rows from the shape to the nearest hard terminal):")
    if tr is None:
        L.append("   no terminal reached: nothing binds the shape to a pin — the objective holds it")
    else:
        L.append(f"   start {_vname(prep, tr.start)} z {z[tr.start]:.3f}; terminal "
                 f"{_vname(prep, tr.terminal)} z {z[tr.terminal]:.3f} [{tr.terminal_kind}: "
                 f"{tr.terminal_note}]; {len(tr.steps)} hops; Σ dz {tr.sum_dz:+.3f} m = "
                 f"z[start] − z[terminal] {z[tr.start] - z[tr.terminal]:+.3f} m; "
                 f"terminals reachable {tr.reached}; visited {tr.visited}")
        fams: dict[str, float] = {}
        for s in tr.steps:
            fams[s.family] = fams.get(s.family, 0.0) + s.dz
        L.append("   by family along the chain (Σ dz): " + ", ".join(
            f"{k} {v:+.3f}" for k, v in sorted(fams.items(), key=lambda kv: -abs(kv[1]))))
        for i, s in enumerate(tr.steps):
            r = s.row
            extra = (f"cap {r.cap:.2%} × {r.d:.1f} m" if isinstance(r, Diff) else
                     f"{type(r).__name__} {r.source.ruling[:40]}")
            du = f" dual {s.dual:.2f}" if s.dual is not None else ""
            L.append(f"   {i + 1:3d}. {_vname(prep, s.v)} z {z[s.v]:.3f} -> {_vname(prep, s.u)} "
                     f"z {z[s.u]:.3f}  dz {s.dz:+.3f}  {s.family} {extra}{du}")
    # relax-one-family
    cand = list(relax) if relax else [fam for fam, _n in sorted(
        fam_n.items(), key=lambda kv: -fam_d.get(kv[0], 0.0))]
    if tr is not None and not relax:
        for s in tr.steps:
            if s.family not in cand:
                cand.append(s.family)
    cand = [c for c in cand if c != "runway_pins"][:max_relax]
    L.append(f"-- relax one family (full re-solve each; the shape's rise), {len(cand)} arms:")
    for fam in cand:
        rr = relax_family(prep, fam, verts)
        L.append(f"   {fam:20s} −{rr.rows_dropped:6d} rows  {rr.status:8s}  dz median "
                 f"{rr.dz_median:+.3f}  min {rr.dz_min:+.3f}  max {rr.dz_max:+.3f}  "
                 f"z−dem after {rr.zdem_median_after:+.3f}  ({rr.wall_s:.2f} s)")
    L.append("-- taxi centrelines touching the shape (code-letter evidence):")
    L += list(letters) if letters else ["   (none)"]
    return "\n".join(L)
