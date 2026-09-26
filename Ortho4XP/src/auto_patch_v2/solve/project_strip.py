"""THE JETWAY STRIP PROJECTION (spec ``docs/specs/jetway-strip-spec.md``
§2; owner RULINGS 2026-09-18t Q3, issues #31/#32).

"UNDER THE JETWAYS THE APRON STRIP IS LEVEL WITH THE TERMINAL — a NEW
AIRSIDE LAW, solved airside-first; nothing groundside pulls it."

Applied like §16 / §32: AFTER the stage-1 airside solve and BEFORE stage
2, on the stage-1 levels stage 2 substitutes as constants — so the pads
read the projected apron as their constants and the pad's datum IS the
strip's level (§2 (2)) with no new pad row.  A PROJECTION, NOT A ROW SET
(§2 (4)): §30 (4)'s collar — the same plane minted as stage-1 rows — was
built and DISARMED (14bk: 11,363 airside vertices moved, 2,211 of them >
500 m away, a field-wide shift of an unsettled stage-1 optimum).  A
projection moves only what it names, so "airside moved outside the
strips + transitions <= hard_tol_m" holds BY CONSTRUCTION.

1. ONE LEVEL PER STRIP: every strip vertex takes ``L = median`` of the
   stage-1 z over the strip's vertices (the apron's own value where the
   jetways stand; nothing groundside is in it).
2. THE TRANSITION: every movable apron vertex off the strip takes its
   stage-1 value CLAMPED into ``[L - s d, L + s d]``, ``d`` its plan
   distance to the strip's nearest vertex and ``s`` the apron's
   ``max`` longitudinal grade (1.5 %) — the §13.9 field construction as
   a cone: it reaches exactly ``L_t = |fall| / s`` and no further, and
   the min/max of s-Lipschitz fields grades no pair steeper than the
   larger of ``s`` and the stage-1 surface's own grade.  Several strips:
   the intersection of their intervals, the nearest strip's where empty.
3. CLAMPS: a taxi / runway / pinned (threshold, §38 seam) vertex, or a
   vertex another pad owns, is NEVER moved; where the field would move it
   more than ``hard_tol_m`` the residual is REPORTED per strip (the
   ``jetway_strip`` family's (c) row), never absorbed.
"""
from __future__ import annotations

import dataclasses as _dc
import time
import typing as _t

import numpy as np

from ..law import Law
from ..law.tables import design as design_law, role_cap
from ..model.jetway import StripSet
from ..model.planar import PlanarMap

__all__ = ["StripReport", "project_strips"]


@_dc.dataclass
class StripReport:
    """What the strip projection did (the report's ``jetway_strip``)."""

    ran: bool = False
    status: str = "off"
    #: per strip: ``id``, ``pad_ref``, ``level``, ``riders``, ``vertices``,
    #: ``moved_max_m``, ``transition``, ``clamps`` ([vertex, why, metres])
    strips: list[dict[str, _t.Any]] = _dc.field(default_factory=list)
    strip_vertices: int = 0
    transition_vertices: int = 0
    moved_max_m: float = 0.0
    clamps: int = 0
    clamp_max_m: float = 0.0
    conflicts: int = 0
    flats_held: int = 0
    unlevelled: int = 0
    wall_s: float = 0.0

    def line(self) -> str:
        if not self.ran:
            return f"jetway strip (18t Q3): {self.status}"
        return (f"jetway strip (18t Q3): {len(self.strips)} strip(s), "
                f"{self.strip_vertices} strip vertices levelled + "
                f"{self.transition_vertices} transition, max move "
                f"{self.moved_max_m:.3f} m; {self.clamps} clamp(s) worst "
                f"{self.clamp_max_m:.3f} m; {self.conflicts} interval conflicts; "
                f"{self.wall_s:.2f} s")

    def as_dict(self) -> dict[str, _t.Any]:
        return {"ran": self.ran, "status": self.status, "strips": self.strips,
                "strip_vertices": self.strip_vertices,
                "transition_vertices": self.transition_vertices,
                "moved_max_m": round(self.moved_max_m, 4),
                "clamps": self.clamps, "clamp_max_m": round(self.clamp_max_m, 4),
                "conflicts": self.conflicts, "flats_held": self.flats_held,
                "unlevelled": self.unlevelled, "wall_s": round(self.wall_s, 3)}


def project_strips(planar: PlanarMap, law: Law, strips: StripSet,
                   levels: dict[int, float], z1: _t.Sequence[float],
                   flats: _t.Sequence[_t.Any] = ()) -> StripReport:
    """Project ``levels`` (stage 1's answer, edited IN PLACE) onto the
    strip law (module docstring).  ``z1`` is stage 1's full ``z``;
    ``flats`` the constraint set's ``Flat`` rows (a Flat group is one
    column: it moves as one value or not at all)."""
    from scipy.spatial import cKDTree
    rep = StripReport()
    if not strips or not strips.strips:
        rep.status = "no strips"
        return rep
    t0 = time.perf_counter()
    rep.ran = True
    rep.status = "ok"
    s = float(role_cap(law, "apron").longitudinal)
    tol = float(design_law(law).hard_tol_m)
    z1a = np.asarray(z1, dtype=float)
    xy = {v: planar.vertices[v].xy for v in planar.vertices}
    new: dict[int, float] = {}
    L: list[float] = []
    trees = []
    in_strip: dict[int, int] = {}
    for k, st in enumerate(strips.strips):
        vs = [v for v in st.vertices if v in levels]
        rep.unlevelled += len(st.vertices) - len(vs)
        if not vs:
            L.append(float("nan"))
            trees.append(None)
            continue
        lvl = float(np.median([levels[v] for v in vs]))
        L.append(lvl)
        trees.append(cKDTree(np.array([xy[v] for v in vs], dtype=float)))
        for v in vs:
            in_strip[v] = k
            new[v] = lvl
    live = [k for k in range(len(L)) if trees[k] is not None]

    def _interval(pts: np.ndarray, base: np.ndarray
                  ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        lo = np.full(len(pts), -np.inf)
        hi = np.full(len(pts), np.inf)
        dbest = np.full(len(pts), np.inf)
        kbest = np.full(len(pts), -1, dtype=np.int64)
        per: list[tuple[np.ndarray, np.ndarray]] = []
        for k in live:
            d, _i = trees[k].query(pts)
            lo_k, hi_k = L[k] - s * d, L[k] + s * d
            lo = np.maximum(lo, lo_k)
            hi = np.minimum(hi, hi_k)
            per.append((lo_k, hi_k))
            better = d < dbest
            dbest = np.where(better, d, dbest)
            kbest = np.where(better, k, kbest)
        bad = lo > hi
        if bad.any():
            for j in np.nonzero(bad)[0]:
                k = int(kbest[j])
                lo_k, hi_k = per[live.index(k)]
                lo[j], hi[j] = lo_k[j], hi_k[j]
        return np.clip(base, lo, hi), kbest, dbest, bad

    # THE TRANSITION over every movable apron vertex off the strips
    mov = sorted(v for v in strips.movable if v not in in_strip and v in levels)
    if mov and live:
        pts = np.array([xy[v] for v in mov], dtype=float)
        base = np.array([levels[v] for v in mov], dtype=float)
        got, _kb, _db, bad = _interval(pts, base)
        rep.conflicts = int(bad.sum())
        for v, zb, zn in zip(mov, base, got):
            if abs(zn - zb) > 1e-9:
                new[v] = float(zn)
    clamps_of: dict[int, list[list[_t.Any]]] = {k: [] for k in range(len(L))}
    seen: set[int] = set()
    # the struck vertices INSIDE a strip are clamps against its level
    for k, st in enumerate(strips.strips):
        if trees[k] is None:
            continue
        for v, why in st.struck:
            if why == "coupled":
                continue          # moved by the transition, not clamped
            zb = float(levels.get(v, z1a[v]))
            m = L[k] - zb
            if abs(m) > tol:
                clamps_of[k].append([int(v), why, round(m, 3)])
                seen.add(v)
    # THE CLAMPS: the vertices the law never moves, where the field
    # would have moved them by more than hard_tol_m
    fixed = sorted(v for v in strips.fixed if v < len(z1a))
    if fixed and live:
        pts = np.array([xy[v] for v in fixed], dtype=float)
        base = np.array([float(levels.get(v, z1a[v])) for v in fixed])
        got, kb, _db, _bad = _interval(pts, base)
        for v, zb, zn, k in zip(fixed, base, got, kb):
            m = float(zn - zb)
            if abs(m) > tol and k >= 0 and v not in seen:
                clamps_of[int(k)].append([int(v), strips.fixed[v], round(m, 3)])
    # A FLAT GROUP IS ONE COLUMN: it moves as one value, or — where a
    # member may not move — not at all
    for f in flats:
        g = list(f.group)
        if not any(v in new for v in g):
            continue
        if all((v in new or v in strips.movable or v in in_strip) for v in g):
            val = float(np.mean([new.get(v, levels.get(v, z1a[v])) for v in g]))
            for v in g:
                if v in levels:
                    new[v] = val
        else:
            for v in g:
                new.pop(v, None)
            rep.flats_held += 1
    # APPLY, and read the report
    moved_by_strip: dict[int, list[float]] = {}
    for v, zn in new.items():
        zb = levels[v]
        d = abs(zn - zb)
        levels[v] = zn
        if v in in_strip:
            rep.strip_vertices += 1
            moved_by_strip.setdefault(in_strip[v], []).append(d)
        elif d > 1e-9:
            rep.transition_vertices += 1
        rep.moved_max_m = max(rep.moved_max_m, d)
    for k, st in enumerate(strips.strips):
        cl = sorted(clamps_of.get(k, []), key=lambda c: -abs(c[2]))
        rep.clamps += len(cl)
        if cl:
            rep.clamp_max_m = max(rep.clamp_max_m, max(abs(c[2]) for c in cl))
        mv = moved_by_strip.get(k, [])
        rep.strips.append({
            "id": st.id, "pad_ref": st.pad_ref,
            "level": None if trees[k] is None else round(L[k], 3),
            "riders": len(st.riders), "vertices": len(st.vertices),
            "moved_max_m": round(max(mv), 3) if mv else 0.0,
            "clamps": cl})
    rep.wall_s = time.perf_counter() - t0
    return rep
