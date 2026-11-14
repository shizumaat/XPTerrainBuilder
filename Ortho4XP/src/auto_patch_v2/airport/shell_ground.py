"""A PACK SHELL'S DEPTH IS READ AGAINST THE AUTHOR'S GROUND (#1950; owner
RULINGS 2026-11-07b (1): "a pack's below-grade intent ... is judged against
the pack's OWN ground plates — the author's ground — never against our
terrain or the placement zero, for every airport").

``object_cut.shell_reading`` reads a resource in its own authored frame, so
its two below-grade tests stand on the placement's ZERO: the floor plate
``shell_floor_min_m`` under it, and the share of the trench outline that
plates at or over it cover (``shell_at_zero_max_fraction``: a building's
floors, never a trench's).  A shared-datum pack hangs every object off ONE
datum (TaiModels KMCI, LGAV), so the zero states nothing about the ground
there.  Once a reading is PLACED (``object_cut.shell_cut``), both are read
again here against the author's ground around the trench outline
(``airport/below_grade_witness``), the shell's and its cover's own faces
left out; where the author laid no plates around it, the zero stands as
before (the DEM is no reading of the pack's intent).

Every number is a ``[tunnel.object]`` law value; nothing here names a pack
or an airport.
"""
from __future__ import annotations

import typing as _t

import numpy as np

from . import below_grade_witness as _bgw

__all__ = ["placed_refusal", "floor_under_ground"]


def floor_under_ground(o, low_y: float, foot, exclude: _t.AbstractSet[str], ground, law
                       ) -> "str | None":
    """The refusal (a string) when placement ``o``'s solid ``low_y`` metres
    over its zero stands less than ``shell_floor_min_m`` under the author's
    ground around ``foot``, else ``None`` — and ``None`` where the author
    laid no plates around it: the zero is then all the pack states."""
    ob = law.tables.structures.tunnel.object
    if ground is None or foot is None or \
            _bgw.around(foot, exclude, ground.ag, ground.dem, law).source != "plates":
        return None
    b = _bgw.row_depth_under(o, low_y, foot, exclude, ground, law, "its floor")
    if b.depth != b.depth or b.depth >= ob.shell_floor_min_m:
        return None
    return (f"{b.why} (< shell_floor_min_m {ob.shell_floor_min_m}): not below the "
            f"author's ground (RULINGS 2026-11-07b (1))")


def placed_refusal(o, r, cov_obj, outline, zero: float, ground, law) -> "str | None":
    """The refusal of a PLACED shell reading ``r`` (``object_cut.
    ShellReading``; ``outline`` its trench outline in the frame, ``zero``
    its placement's zero) against the author's ground, else ``None``: its
    floor must stand ``shell_floor_min_m`` under that ground, and plates at
    or over that ground must cover no more than ``shell_at_zero_max_fraction``
    of the trench outline (a building's floors, #1726)."""
    from .object_cut import _graded_share
    ob = law.tables.structures.tunnel.object
    if ground is None:
        return None
    own = frozenset({o.id, cov_obj.id})
    why = floor_under_ground(o, r.floor_y, outline, own, ground, law)
    if why is not None:
        return why
    if r.floor_faces is None or not len(r.floor_faces):
        return None
    at = _bgw.around(outline, own, ground.ag, ground.dem, law)
    if at.source != "plates":
        return None
    level_y = at.z - zero
    faces = np.asarray(r.floor_faces, float)
    graded = _graded_share(faces.reshape(-1, 3), np.arange(3 * len(faces)).reshape(-1, 3),
                           r.interior, ob, level_y)
    if graded <= ob.shell_at_zero_max_fraction:
        return None
    return (f"a building, not a trench: plates at or above the author's ground "
            f"({at.z:.2f}, {level_y:+.2f} over its zero) cover {graded:.0%} of the trench "
            f"outline (> shell_at_zero_max_fraction {ob.shell_at_zero_max_fraction:.0%}) — a "
            f"trench states its geometry below grade over its floor footprint")
