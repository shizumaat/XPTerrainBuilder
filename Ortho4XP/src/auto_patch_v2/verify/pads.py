"""THE PAD-FLAT CHECK over the emitted product (RULINGS 2026-09-03h "a
pad is a rigid flat group levelled by its apron contact"; 03i; and the
ONE lawful exception, 04t(1): a pad the last resort relaxed is ONE PLANE,
published in the sidecar ``relaxed_rows`` with ``kind = "pad"``).

Every rigid-role shape (``precedence.toml`` ``rigid``) is read:

* an UNRELAXED pad carries one elevation over its outer ring and holes —
  a spread above ``emit.materiality.elevation_m`` is a ``pad_flat`` row
  (a sloped building would ship);
* a RELAXED pad lies on one plane — its least-squares plane residual
  above ``emit.relaxation.materiality_m`` is a row (``reading =
  "plane_residual"``).

Not a law family: an ACCEPTANCE check beside the tunnel / basin ones, so
the register twins (v1 families == v2 families) hold.  A pad's ``Flat``
is a hard equality no tier demotes (``solve/tiers.py``) and a plane
exists only inside the relaxation, so a row here can only come from a
solver / emit defect: the pipeline reports it as a DEFECT
(``verify.DEFECT_KEYS``), the app driver as a named failure.
"""
from __future__ import annotations

import numpy as np

from .frame import Patch, Row, Shape, row

__all__ = ["pad_flat", "plane_residual"]

FAMILY = "pad_flat"


def plane_residual(xy: list[tuple[float, float]], z: list[float]) -> float:
    """Max |z − fit| of the least-squares plane through the points (the
    spread when fewer than three points or a degenerate fit)."""
    if len(z) < 3:
        return max(z) - min(z) if z else 0.0
    a = np.column_stack([np.ones(len(z)), np.asarray(xy, float)])
    zz = np.asarray(z, float)
    coef, _res, rank, _sv = np.linalg.lstsq(a, zz, rcond=None)
    if rank < 3:
        return float(zz.max() - zz.min())
    return float(np.abs(zz - a @ coef).max())


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
    rel = p.publication.get("relaxed_rows") or []
    relaxed_faces = {r.get("face") for r in rel if r.get("kind") == "pad"}
    flat_tol = p.law.tables.emit.materiality.elevation_m
    plane_tol = p.law.tables.emit.relaxation.materiality_m
    out: list[Row] = []
    for sh in p.shapes:
        if not p.is_rigid(sh.role) or len(sh.ids) < 2:
            continue
        xy, z, ids = _pad_points(p, sh)
        lo_i = min(range(len(z)), key=z.__getitem__)
        hi_i = max(range(len(z)), key=z.__getitem__)
        spread = z[hi_i] - z[lo_i]
        if sh.key in relaxed_faces:
            reading, magnitude, tol = "plane_residual", plane_residual(xy, z), plane_tol
        else:
            reading, magnitude, tol = "spread", spread, flat_tol
        if magnitude <= tol:
            continue
        lat, lon = p.ll[ids[hi_i]]
        r = row(FAMILY, [sh.role], p.side(sh.role), magnitude, None, None, None,
                xy[lo_i], xy[hi_i], sh.ref, sh.ref, lat=lat, lon=lon)
        r.update({"reading": reading, "spread_m": round(spread, 4), "face": sh.key,
                  "relaxed": sh.key in relaxed_faces, "vertices": len(ids)})
        out.append(r)
    return out
