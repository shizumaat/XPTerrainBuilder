"""AUTHORED TO THE CUT — the seat is kept where it already works over the
terrain the engine cuts (object-placement spec §18; owner RULINGS
2026-10-07b (1), (3) and 2026-10-07c (3), (4), (5)).

A scenery pack's author may have set his below-grade objects' elevations
for the terrain THIS engine cuts under them.  Such an object is left
exactly where he put it; only an object whose authored seat does NOT work
over the cut is re-seated.  The witness is geometry and two law bands —
never a pack, an airport or a coordinate:

* a WALL (a tunnel wall object, ``airport/tunnel_objects``): its crest
  plate, rendered at the AUTHORED seat over the terrain the engine cuts
  under its anchor, stands ``0 … [tunnel.object] authored_crest_max_m``
  over the surrounding grade (:func:`crest_over`, :func:`crest_in_band`);
* a PIT (a basin's witness, ``planar/basins``): its rim, rendered at the
  authored seat over the floor the basin law cuts, stands within
  ``[basin] authored_rim_tol_m`` of the ring's ground (:func:`rim_over`,
  :func:`rim_in_band`); and a placement LIFTED by its own shell depth
  within the same band is READ ground-seated by the basin intake
  (:func:`lifted_by_own_depth`), so it founds the same basin as its
  plain twin.

A wall that is NOT authored to the cut is re-seated as before (RULINGS
2026-09-05n-4), but to THE PACK'S OWN MEDIAN PROUD HEIGHT
(:func:`pack_proud_height`, 07c (4): "choose a median and standardize"),
flush only where the pack states no height at all.

Pure arithmetic: no geometry library, no law table, no model record —
the callers (``obj8`` for the intake, ``planar`` for the readings,
``pipeline/authored_seats`` for the decision) hand the numbers in.
"""
from __future__ import annotations

import math
import statistics
import typing as _t

__all__ = ["SEAT_AUTHORED", "SEAT_RESEATED", "lifted_by_own_depth", "crest_over",
           "crest_in_band", "rim_over", "rim_in_band", "stated_height",
           "pack_proud_height"]

#: The two values a seat record carries (the plan's ``seat`` column).
SEAT_AUTHORED = "authored (cut)"
SEAT_RESEATED = "re-seated"


def lifted_by_own_depth(agl_m: float, deepest_y: float, tol_m: float,
                        min_depth_m: float = 0.0) -> bool:
    """§18 (5): is this placement LIFTED BY ITS OWN SHELL DEPTH?  ``agl_m``
    the authored lift (``OBJECT_AGL``), ``deepest_y`` the resource's
    deepest authored vertex (negative under the object's zero plane): the
    lift puts that vertex within ``tol_m`` of the terrain at the anchor,
    and the shell is at least ``min_depth_m`` deep (the basin floor gate:
    a shallower shell could witness no pit, so a figure lifted 4 cm off
    the ground is never "ground-seated").  The basin intake then reads
    the shell as ground-seated.  A plain placement (no lift), a lift that
    is not the shell's depth (a pit on a podium, a vent stack) and a
    ``tol_m`` of 0 all read ``False`` — the reading as it was."""
    if tol_m <= 0.0 or agl_m <= 0.0 or not math.isfinite(deepest_y):
        return False
    if deepest_y >= 0.0 or -deepest_y < min_depth_m:
        return False
    return abs(agl_m + deepest_y) <= tol_m


def crest_over(terrain_z: float, agl_m: float, plate_y: float, grade_z: float) -> float:
    """A wall's crest height over the surrounding grade with the AUTHORED
    seat: ``terrain under the anchor + agl + crest plate y − grade``.
    Hand it the CUT terrain for ``h_cut`` and the uncut ground for
    ``h_uncut``."""
    return float(terrain_z) + float(agl_m) + float(plate_y) - float(grade_z)


def crest_in_band(h_m: float | None, max_m: float) -> bool:
    """``0 ≤ h ≤ authored_crest_max_m`` — never below ground (05n-4
    stands), at most a parapet.  ``None`` (no reading) is out of band."""
    return h_m is not None and -1e-9 <= h_m <= max_m + 1e-9


def rim_over(terrain_z: float, agl_m: float, grade_z: float) -> float:
    """A pit's rim (its zero plane, §14 (2)) over the ring's ground with
    the AUTHORED seat: ``terrain under the anchor + agl − grade``."""
    return float(terrain_z) + float(agl_m) - float(grade_z)


def rim_in_band(r_m: float | None, tol_m: float) -> bool:
    """``|r| ≤ authored_rim_tol_m``."""
    return r_m is not None and abs(r_m) <= tol_m + 1e-9


def stated_height(h_cut_m: float | None, h_uncut_m: float | None,
                  max_m: float) -> float | None:
    """The proud height ONE wall's authoring states: its crest over the
    cut where that reads in band (authored to the cut), else its crest
    over uncut ground where THAT reads in band (authored to flat ground),
    else nothing."""
    if crest_in_band(h_cut_m, max_m):
        return float(h_cut_m)                                # type: ignore[arg-type]
    if crest_in_band(h_uncut_m, max_m):
        return float(h_uncut_m)                              # type: ignore[arg-type]
    return None


def pack_proud_height(stated: _t.Iterable[float | None]) -> float | None:
    """RULINGS 2026-10-07c (4): the pack's own MEDIAN proud height over
    every wall that states one — what a re-seated wall's crest is set to;
    ``None`` (flush, 05n-4) when no wall of the pack states a height."""
    hs = [float(h) for h in stated if h is not None]
    return float(statistics.median(hs)) if hs else None
