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

1. THE PAD'S PLANE PER STRIP (spec-author ruling Q-32a (d), 2026-09-25:
   "level with the terminal" = COPLANAR with the 23a pad): every strip
   vertex takes the pad plane evaluated at it — §20's least-squares plane
   through the pad's airside frontage at its stage-1 values, tilt <= the
   pad's 1 % ceiling.  Airside-derived; nothing groundside is in it.
   (Measured, round 1: ONE horizontal level per pad fought the apron's
   own fall along a 1 km terminal — SPJC adjudicated 913 -> 3,305.)
2. THE TRANSITION: each strip vertex's CHANGE ``L - z1`` propagates to
   the movable apron beyond it, decaying at ``s`` (the apron's ``max``
   longitudinal grade, 1.5 %) and gone at ``L_t = |fall| / s`` — the
   §13.9 field construction (the change's upper / lower cone envelope).
3. CLAMPS: a taxi / runway / pinned (threshold, §38 seam) vertex, or a
   vertex another pad owns, is NEVER moved; the change beside it is held
   to ``s·d`` from it, and where the field wanted it moved more than
   ``hard_tol_m`` the residual is REPORTED per strip (the
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
    #: strips the planarity gate refused (Q-32d (i))
    gated: int = 0
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
                f"{self.clamp_max_m:.3f} m; {self.gated} gated (frontage not a plane); "
                f"{self.wall_s:.2f} s")

    def as_dict(self) -> dict[str, _t.Any]:
        return {"ran": self.ran, "status": self.status, "strips": self.strips,
                "strip_vertices": self.strip_vertices,
                "transition_vertices": self.transition_vertices,
                "moved_max_m": round(self.moved_max_m, 4),
                "clamps": self.clamps, "clamp_max_m": round(self.clamp_max_m, 4),
                "conflicts": self.conflicts, "flats_held": self.flats_held,
                "gated": self.gated,
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
    planes: list[tuple[float, float, float, float, float] | None] = []
    trees = []
    in_strip: dict[int, int] = {}
    tilt_max = float(law.tables.emit.within_shape.pad_slope_max)
    plane_tol = float(design_law(law).jetway_strip_plane_tol_m)
    resid_of: list[tuple[float, bool]] = []
    for k, st in enumerate(strips.strips):
        vs = [v for v in st.vertices if v in levels]
        rep.unlevelled += len(st.vertices) - len(vs)
        if not vs:
            L.append(float("nan"))
            planes.append(None)
            trees.append(None)
            resid_of.append((float("nan"), False))
            continue
        pl = _pad_plane(st, levels, xy, vs, tilt_max)
        # THE PLANARITY GATE (spec-author ruling Q-32d (i), 2026-09-25): a
        # strip forms only on a pad whose stage-1 airside frontage fits its
        # plane within ``[design] jetway_strip_plane_tol_m``; elsewhere no
        # strip — the 23a weld alone governs (measured: SPJC's 1 km
        # terminal, whose frontage is not a plane, bent the pad between
        # the levelled rider edges and the rest, 243 -> 604 rows)
        resid = _frontage_residual(st, levels, xy, vs, pl)
        gated = resid > plane_tol
        resid_of.append((resid, gated))
        if gated:
            rep.gated += 1
            L.append(float("nan"))
            planes.append(pl)
            trees.append(None)
            continue
        planes.append(pl)
        tgt = {v: _at(pl, xy[v]) for v in vs}
        L.append(float(np.median(list(tgt.values()))))
        trees.append(cKDTree(np.array([xy[v] for v in vs], dtype=float)))
        for v in vs:
            in_strip[v] = k
            new[v] = tgt[v]
    live = [k for k in range(len(L)) if trees[k] is not None]

    # THE TRANSITION (§2 (3)): "from the strip's outer line the surface
    # grades to the stage-1 value over L_t = |fall| / max".  Each strip
    # vertex u carries its CHANGE d_u = L - z1(u); the change propagates
    # outward decaying at the apron max s and is gone at |d_u| / s — the
    # §13.9 field construction, as the upper / lower envelope of every
    # strip vertex's cone of change (each s-Lipschitz, so the transition
    # adds at most s to the stage-1 grade of any pair and moves nothing
    # beyond L_t).  It is the CHANGE that is propagated, never the level:
    # an absolute-level cone reaches every vertex whose stage-1 value is
    # more than s·d from L, i.e. across every terrace of a hilly airport
    # (measured, HECA: 4,196 vertices moved up to 21 m).
    src_xy = np.array([xy[v] for v in in_strip], dtype=float)
    src_dz = np.array([new[v] - levels[v] for v in in_strip], dtype=float)
    src_k = np.array([in_strip[v] for v in in_strip], dtype=np.int64)
    reach = float(np.max(np.abs(src_dz)) / s) if src_dz.size else 0.0
    # A GATED PAD IS NOT MOVED BY ITS NEIGHBOURS' STRIPS (Q-32d (i),
    # round 2): where the gate refused a pad's strip "the 23a weld alone
    # governs" — so its own vertices join the never-moved set, or another
    # pad's transition reaches its weld and bends it anyway (measured:
    # SPJC's gated terminal 243 -> 326 rows through the concourse pads'
    # strips beside it).
    why_fixed: dict[int, str] = dict(strips.fixed)
    for k, st in enumerate(strips.strips):
        if resid_of[k][1]:
            for v in st.pad_vertices:
                why_fixed.setdefault(v, "gated_pad")
    fixed = sorted(v for v in why_fixed if v < len(z1a))
    ftree = (cKDTree(np.array([xy[v] for v in fixed], dtype=float))
             if fixed else None)

    def _change(pts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(the propagated change, the strip it comes from) at ``pts``."""
        up = np.zeros(len(pts))
        dn = np.zeros(len(pts))
        kk = np.full(len(pts), -1, dtype=np.int64)
        best = np.zeros(len(pts))
        for j0 in range(0, len(pts), 2048):
            P = pts[j0:j0 + 2048]
            d = np.hypot(P[:, None, 0] - src_xy[None, :, 0],
                         P[:, None, 1] - src_xy[None, :, 1])
            pos = src_dz[None, :] - s * d
            neg = src_dz[None, :] + s * d
            u = np.maximum(0.0, np.where(src_dz[None, :] > 0, pos, 0.0).max(axis=1))
            n_ = np.minimum(0.0, np.where(src_dz[None, :] < 0, neg, 0.0).min(axis=1))
            up[j0:j0 + 2048], dn[j0:j0 + 2048] = u, n_
            mag = np.where(src_dz[None, :] > 0, pos, -neg)
            arg = mag.argmax(axis=1)
            kk[j0:j0 + 2048] = src_k[arg]
            best[j0:j0 + 2048] = mag.max(axis=1)
        return up + dn, np.where(best > 0.0, kk, -1)

    mov = sorted(v for v in strips.movable if v not in in_strip and v in levels
                 and v not in why_fixed)
    if mov and src_xy.size and reach > 0.0:
        stree = cKDTree(src_xy)
        pts_all = np.array([xy[v] for v in mov], dtype=float)
        dmin, _i = stree.query(pts_all, distance_upper_bound=reach)
        near = np.nonzero(np.isfinite(dmin))[0]
        if near.size:
            pts = pts_all[near]
            dz, _kk = _change(pts)
            # "the field is clamped there": a never-moved vertex has zero
            # change, and the change beside it is bounded by s·d to it
            if ftree is not None:
                dc, _ic = ftree.query(pts)
                dz = np.clip(dz, -s * dc, s * dc)
            for j, dzj in zip(near, dz):
                if abs(dzj) > 1e-9:
                    v = mov[int(j)]
                    new[v] = float(levels[v] + dzj)
    # THE CLAMPS (§2 (3), the ``jetway_strip`` family's (c)): every
    # never-moved vertex the transition WANTED to move by more than
    # hard_tol_m, with the metres — the residual the law leaves there,
    # REPORTED, never absorbed.
    clamps_of: dict[int, list[list[_t.Any]]] = {k: [] for k in range(len(L))}
    if fixed and src_xy.size and reach > 0.0:
        fpts = np.array([xy[v] for v in fixed], dtype=float)
        dmin, _i = cKDTree(src_xy).query(fpts, distance_upper_bound=reach)
        near = np.nonzero(np.isfinite(dmin))[0]
        if near.size:
            dz, kk = _change(fpts[near])
            for j, dzj, k in zip(near, dz, kk):
                if abs(dzj) > tol and k >= 0:
                    v = fixed[int(j)]
                    clamps_of[int(k)].append([int(v), why_fixed[v],
                                              round(float(dzj), 3)])
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
            # Q-32d (i): the frontage's max residual off the pad plane and
            # whether the planarity gate refused the strip
            "frontage_resid_m": round(resid_of[k][0], 3),
            "gated": bool(resid_of[k][1]),
            # Q-32a (d): the PAD'S PLANE — z at (x0, y0) and its gradient
            "plane": (None if planes[k] is None
                      else [round(c, 6) for c in planes[k]]),
            "targets": ({} if trees[k] is None else
                        {int(v): round(new.get(v, levels[v]), 4)
                         for v in st.vertices if v in levels}),
            "riders": len(st.riders), "vertices": len(st.vertices),
            "moved_max_m": round(max(mv), 3) if mv else 0.0,
            "clamps": cl})
    rep.wall_s = time.perf_counter() - t0
    return rep


def _at(pl: tuple[float, float, float, float, float], p: tuple[float, float]
        ) -> float:
    z0, gx, gy, x0, y0 = pl
    return z0 + gx * (p[0] - x0) + gy * (p[1] - y0)


def _pad_plane(st: _t.Any, levels: _t.Mapping[int, float],
               xy: _t.Mapping[int, tuple[float, float]], vs: list[int],
               tilt_max: float) -> tuple[float, float, float, float, float]:
    """Q-32a (d) (spec-author ruling 2026-09-25): THE PAD'S PLANE the
    strip takes — §20's own construction: the least-squares plane through
    the pad's FRONTAGE CONTACTS (its rim vertices stage 1 already levelled,
    i.e. the airside weld, 23a) at their stage-1 values, its tilt bounded
    by the pad's hard ceiling ``emit.within_shape.pad_slope_max`` (1 %;
    a steeper fit keeps its direction at the ceiling and re-centres).  A
    pad with fewer than three non-collinear contacts reads the strip's own
    stage-1 values instead.  ``(z0, gx, gy, x0, y0)``."""
    pts = [v for v in st.pad_vertices if v in levels]
    if len(pts) < 3:
        pts = vs
    P = np.array([xy[v] for v in pts], dtype=float)
    z = np.array([levels[v] for v in pts], dtype=float)
    x0, y0 = float(P[:, 0].mean()), float(P[:, 1].mean())
    A = np.column_stack([np.ones(len(P)), P[:, 0] - x0, P[:, 1] - y0])
    if len(P) >= 3 and np.linalg.matrix_rank(A) == 3:
        c, *_ = np.linalg.lstsq(A, z, rcond=None)
        z0, gx, gy = float(c[0]), float(c[1]), float(c[2])
    else:
        z0, gx, gy = float(np.median(z)), 0.0, 0.0
    g = float(np.hypot(gx, gy))
    if g > tilt_max > 0.0:
        gx, gy = gx * tilt_max / g, gy * tilt_max / g
        z0 = float(np.mean(z - gx * (P[:, 0] - x0) - gy * (P[:, 1] - y0)))
    return (z0, gx, gy, x0, y0)


def _frontage_residual(st: _t.Any, levels: _t.Mapping[int, float],
                       xy: _t.Mapping[int, tuple[float, float]], vs: list[int],
                       pl: tuple[float, float, float, float, float]) -> float:
    """Q-32d (i): the largest |stage-1 z - pad plane| over the pad's
    airside frontage contacts (the population :func:`_pad_plane` fitted;
    the strip's own vertices where the pad has fewer than 3)."""
    pts = [v for v in st.pad_vertices if v in levels]
    if len(pts) < 3:
        pts = vs
    return float(max(abs(levels[v] - _at(pl, xy[v])) for v in pts))
