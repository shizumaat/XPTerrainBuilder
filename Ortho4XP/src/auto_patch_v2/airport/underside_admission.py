"""WHICH UNITS THE UNDERSIDE MAP MAY SEAT WHOLE: ADMISSION S3 (owner
RULINGS 2026-11-25m (4); spec ``docs/specs/underside-height-map-20261125.md``
§2 S3).  A REPORT in step 1: nothing is seated by the verdict yet.

A unit on a pad block at level ``D`` would be written whole at
``z0 = D - t`` (``t``: the floor its airside contacts stand at,
``geom.underside_map``).  Today it is seated at ``D - base`` (``base``: its
walls' feet median, ``footprint_unit._wall_base``).  The verdict:

* ``exception`` -- no ground contact (``footless``) or no pad (``D``
  unknown; owner Q1): today's seat;
* ``composite`` -- a recognised composite (25l; ``underside_composite``)
  welded to airside (25n (2): ``t`` read at its airside contacts);
* ``coherent`` -- ``|t - base|`` under :data:`COHERENT_M`: the two zeros
  agree (identity);
* ``mis-zeroed`` -- ``|t - base|`` at least :data:`MIS_ZEROED_M` and the
  GROUND CONFIRMS: the L1 misfit of our ground to the unit's non-airside
  stations (``median |g - (z0 + h)|``) falls by :data:`MIS_ZEROED_M` or
  more from today's zero to ``z0``;
* ``doubt`` -- anything else: today's seat (13r); and a COMPOSITE (the
  one verdict our ground does not confirm) whose zero would leave half or
  more of its non-airside stations our ground reads FAR (a storey or more
  outside their interval, 25f: :func:`far_share`) -- lane lellxpit S0,
  MEASURED ELLX ``Lux_Fuel_base``: a composite zero 15.5 m under its
  ground at every station (its pad ``building49#s1`` read 360.54 m).  A unit touching no
  airside (``t`` read from its own feet) is never re-zeroed but on the
  ground's confirmation (25n (2): only airside welds a unit to ``D``),
  and its predicted ``z0`` is today's.

Not judged here (spec S5, step 2): the exception classes other than
footless and no-pad, the ground's credibility, and S4's far pieces."""
from __future__ import annotations

import typing as _t

import numpy as np

__all__ = ["COHERENT_M", "MIS_ZEROED_M", "VERDICTS", "admit", "far_share"]

#: two zeros this close are one (m)
COHERENT_M = 0.05
#: a zero this far off, with the ground confirming by as much, is wrong (m)
MIS_ZEROED_M = 0.5
VERDICTS = ("coherent", "mis-zeroed", "composite", "doubt", "exception")


def _misfit(m: _t.Any, z0: float, g: np.ndarray) -> float:
    """The L1 misfit of our ground ``g`` (per station of ``m``, ``nan``
    unread) to ``m``'s non-airside stations seated at ``z0``; ``nan`` when
    none is read."""
    ok = np.isfinite(g) & ~np.asarray(m.airside, dtype=bool)
    if not ok.any():
        return float("nan")
    return float(np.median(np.abs(g[ok] - (z0 + m.h[ok]))))


def far_share(m: _t.Any, z0: float, g: "np.ndarray | None", storey_m: float
              ) -> "float | None":
    """The share of ``m``'s non-airside stations our ground ``g`` reads
    that stand ``storey_m`` or more outside their interval at zero ``z0``
    (``unit_perimeter``'s FAR), or ``None`` when none is read."""
    from .unit_perimeter import _interval, off_interval
    if g is None:
        return None
    ok = np.isfinite(g) & ~np.asarray(m.airside, dtype=bool)
    if not ok.any():
        return None
    lo, hi = _interval(m, z0)
    far = np.abs(off_interval(g, lo, hi)) >= float(storey_m)
    return float(far[ok].mean())


def admit(m: _t.Any, D: "float | None", g: "np.ndarray | None" = None,
          storey_m: float = 3.0) -> tuple[str, dict[str, _t.Any]]:
    """``(verdict, detail)`` of map ``m`` on a pad at ``D`` with our
    ground ``g`` read at its stations (module doc); ``storey_m``: the FAR
    step (``[building_pad] low_level_min_step_m``)."""
    verdict, det = _verdict(m, D, g)
    if verdict == "composite":
        share = far_share(m, float(det["z0"]), g, storey_m)
        if share is not None and share >= 0.5:
            det["far_share"] = round(share, 3)
            return "doubt", det
    return verdict, det


def _verdict(m: _t.Any, D: "float | None", g: "np.ndarray | None"
             ) -> tuple[str, dict[str, _t.Any]]:
    if m.footless or m.t is None:
        return "exception", {"why": "footless"}
    if D is None:
        return "exception", {"why": "no pad"}
    base = float(m.base or 0.0)
    welded = m.t_from == "airside"
    det: dict[str, _t.Any] = {"z0": round(D - (m.t if welded else base), 3),
                              "z_base": round(D - base, 3)}
    if m.composite and welded:
        return "composite", det
    off = abs(m.t - base)
    if off < COHERENT_M:
        return "coherent", det
    if off >= MIS_ZEROED_M and g is not None:
        before, after = _misfit(m, D - base, g), _misfit(m, D - m.t, g)
        det.update(misfit_today=round(before, 3), misfit_z0=round(after, 3))
        if np.isfinite(before) and np.isfinite(after) and before - after >= MIS_ZEROED_M:
            det["z0"] = round(D - m.t, 3)
            return "mis-zeroed", det
    return "doubt", det
