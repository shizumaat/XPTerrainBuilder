"""A PACK WITNESS COUNTS ONLY ALONG ITS OWN STRETCH (owner RULINGS
2026-11-09a (6), issue #1961) — lane ``l1961``.

"Below-ground evidence from a pack object counts only for the stretch of a
channel/trench the object actually runs along; beyond it, where the survey
shows no cut, the channel follows the ground (stops, or is refused if what
is left is shorter than ``corridor_min_length_m``)."

§45 (16) ran a channel's ENDS to its outermost crossings and then EXTENDED
them by a depth witness; nothing ever SHORTENED them to the witness.  So a
pack floor of §45 (3) (i) — one flat datum — was carried over every metre
between the outermost decks, witnessed or not.  The site: LFMN
``channel:0`` (tram ways −446 / −532, 1,284 m) took the T1 car-park level
``terminal-1-park-01.009-O4XP.obj`` / ``.008`` (a level 4.4 m under the
author's plates, real evidence) which runs along stations 1..83 m only, and
cut a 0.36 m floor 864 m long — a 14 ha ``tunnel_trench`` where the
credible lidar (FRANCE1M) reads no cut.

This is the ONE derivation site: the channel's ends.  Every consumer (the
floor, the walls, the region, the crest ring, the deck rows, the claimed
cells) reads the stations between the ends, so a channel cut back here is
cut back everywhere.  The survey is asked only where it is CREDIBLE lidar
(the inset's own class): §45 (7) — a coarse DEM is never a witness against
a channel — so under a coarse DEM nothing here changes.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString

from ..law import Law
from ..model.airport import Airport
from .channel_geometry import _lidar_reach, _witness_along

__all__ = ["witnessed_stretch"]


class _Stretch(_t.NamedTuple):
    """The ends a pack witness supports: ``ends`` (the new, never wider
    ``(s0, s1)``), ``witness`` (the stations the witnesses' below-grade
    footprints run along), ``survey`` (those stations widened by the
    credible lidar's own reach) and ``cut`` (metres taken off the old
    ends)."""

    ends: tuple[float, float]
    witness: tuple[float, float]
    survey: tuple[float, float]
    cut: float


def witnessed_stretch(airport: Airport, law: Law, axis_ln: LineString, axis_fn,
                      ends: tuple[float, float], half_at: float,
                      objects: _t.Sequence, packs: _t.Sequence[str]) -> _Stretch | None:
    """RULINGS 2026-11-09a (6): the channel's ends cut back to the stretch
    its pack witnesses run along, widened only where the credible survey
    itself still reads a cut (``channel_geometry._lidar_reach``, the walk
    §45 (16) already takes for a lidar witness).  ``None`` when no witness
    states a below-grade footprint on the axis (nothing to judge).

    The caller asks this only for a pack-witnessed channel under a
    CREDIBLE lidar inset; it refuses the channel when the stretch left is
    shorter than ``corridor_min_length_m``."""
    span = _witness_along(axis_ln, objects, packs)
    if span is None:
        return None
    lo, hi = _lidar_reach(airport, law, axis_fn, axis_ln.length, half_at,
                          float(span[0]), float(span[1]))
    new = (max(float(ends[0]), lo), min(float(ends[1]), hi))
    if new[1] < new[0]:
        new = (new[0], new[0])
    cut = (new[0] - float(ends[0])) + (float(ends[1]) - new[1])
    return _Stretch(new, (float(span[0]), float(span[1])), (lo, hi), max(0.0, cut))
