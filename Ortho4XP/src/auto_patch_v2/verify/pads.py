"""THE PAD-PLANE CHECK over the emitted product (owner RULINGS
2026-09-09c: "building pads are targeting flat, with up to 1 % allowance
where no other solution exists"; 03h "levelled by its apron contact";
03i).  A pad is ONE PLANE whose flatness is a design TARGET
(``[design] pad_flat``) and whose tilt is bounded HARD at
``emit.within_shape.pad_slope_max`` (1 %).

Every rigid-role shape (``precedence.toml`` ``rigid``) is read:

* a pad lies on ONE PLANE — its least-squares plane residual
  above ``emit.materiality.elevation_m`` is a row (``reading =
  "plane_residual"``) — no steeper than ``emit.within_shape.pad_slope_max``
  (RULINGS 2026-09-05f: 1 %): a plane's gradient over it by more than the
  grade materiality PLUS the emit quantum's fit sensitivity (RULINGS
  2026-09-06k (3): ``plane_slope ≤ cap + quantum``, the 04x allowance)
  is a row (``reading = "plane_slope"``).

Not a law family: an ACCEPTANCE check beside the tunnel / basin ones, so
the register twins (v1 families == v2 families) hold.  RULINGS
2026-09-08v withdrew ``pad_flat`` from ``verify.DEFECT_KEYS``: under the
design surface the pad's flatness is a TARGET of the one solve, and the
DEFECT gate reads the runway family only.  A ``plane_slope`` row IS a
missed hard ceiling and the census reports it.
"""
from __future__ import annotations

import numpy as np

from .frame import Patch, Row, Shape, row

__all__ = ["pad_flat", "plane_fit", "plane_fit_quantum", "plane_residual"]

FAMILY = "pad_flat"


def plane_fit(xy: list[tuple[float, float]], z: list[float]) -> tuple[float, float]:
    """``(residual, slope)`` of the least-squares plane through the
    points: max |z − fit| and the plane's gradient magnitude (m/m).  Fewer
    than three points or a degenerate fit: the spread, slope 0."""
    r, s, _q = plane_fit_quantum(xy, z)
    return r, s


def plane_fit_quantum(xy: list[tuple[float, float]], z: list[float]
                      ) -> tuple[float, float, float]:
    """``(residual, slope, sensitivity)``: :func:`plane_fit` plus the
    fitted gradient's SENSITIVITY to a unit perturbation of every
    elevation — ``Σ_i |∂∇z/∂z_i|`` over the least-squares solution
    (for a triangle exactly ``Σ 1/h_i``, ``verify.within.plane_fit_noise``).
    Times the emit half-quantum it is the 04x quantization allowance the
    census's plane reading grants: an emitted pad relaxed EXACTLY to the
    cap reads over it by up to this (RULINGS 2026-09-06k (3))."""
    if len(z) < 3:
        return (max(z) - min(z) if z else 0.0), 0.0, 0.0
    a = np.column_stack([np.ones(len(z)), np.asarray(xy, float)])
    zz = np.asarray(z, float)
    coef, _res, rank, _sv = np.linalg.lstsq(a, zz, rcond=None)
    if rank < 3:
        return float(zz.max() - zz.min()), 0.0, 0.0
    pinv = np.linalg.pinv(a)                       # coef = pinv @ z
    sens = float(np.hypot(pinv[1], pinv[2]).sum())
    return (float(np.abs(zz - a @ coef).max()), float(np.hypot(coef[1], coef[2])),
            sens)


def plane_residual(xy: list[tuple[float, float]], z: list[float]) -> float:
    """Max |z − fit| of the least-squares plane through the points."""
    return plane_fit(xy, z)[0]


def _pad_points(p: Patch, sh: Shape) -> tuple[list[tuple[float, float]], list[float], list[int]]:
    ids = list(sh.ids)
    for h in p.features:
        if h.feature == "gap_interior_ring" and h.ref == sh.ref \
                and not set(h.ids) <= set(ids):
            ids.extend(h.ids)
    return [p.xy[i] for i in ids], [p.z[i] for i in ids], ids


def pad_flat(p: Patch) -> list[Row]:
    """One row per rigid pad that is not one flat value (or, relaxed under
    04t(1), not one plane) — see the module docstring."""
    # EVERY PAD IS ONE PLANE (owner RULINGS 2026-09-09c, spec §9.2 B6):
    # its flatness is a design TARGET and its tilt is bounded hard at
    # ``pad_slope_max``.  The ``relaxed_rows`` branch went with the
    # relaxation machinery it named (08t deleted tiers / IIS / relaxation).
    plane_tol = p.law.tables.emit.materiality.elevation_m
    slope_max = p.law.tables.emit.within_shape.pad_slope_max
    grade_tol = p.law.tables.emit.materiality.grade
    # RULINGS 2026-09-06k (3): the reading tolerates the EMIT QUANTUM — a
    # pad relaxed exactly to the cap, emitted at the coordinate quantum,
    # reads over it by the plane fit's rounding sensitivity × q/2 (the 04x
    # allowance the census's plane_gradient reader grants)
    half_q = 0.5 * p.law.tables.emit.materiality.elevation_m
    out: list[Row] = []
    for sh in p.shapes:
        if not p.is_rigid(sh.role) or len(sh.ids) < 2:
            continue
        xy, z, ids = _pad_points(p, sh)
        lo_i = min(range(len(z)), key=z.__getitem__)
        hi_i = max(range(len(z)), key=z.__getitem__)
        spread = z[hi_i] - z[lo_i]
        resid, slope, sens = plane_fit_quantum(xy, z)
        quantum = sens * half_q
        reading, magnitude, tol = "plane_residual", resid, plane_tol
        if resid <= plane_tol and slope > slope_max + grade_tol + quantum:
            # one plane, but steeper than the ruling allows (05f / 09c)
            reading, magnitude, tol = "plane_slope", spread, -1.0
        if magnitude <= tol:
            continue
        lat, lon = p.ll[ids[hi_i]]
        r = row(FAMILY, [sh.role], p.side(sh.role), magnitude, None, None, None,
                xy[lo_i], xy[hi_i], sh.ref, sh.ref, lat=lat, lon=lon)
        r.update({"reading": reading, "spread_m": round(spread, 4), "face": sh.key,
                  "relaxed": False, "vertices": len(ids),
                  "slope": round(slope, 6), "slope_max": slope_max,
                  "quantum": round(quantum, 6)})
        out.append(r)
    return out
