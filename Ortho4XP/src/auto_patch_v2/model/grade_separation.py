"""THE GRADE-SEPARATED ROAD CROSSINGS (#2128 round 4; owner RULINGS
2026-11-17d: "a road takes a level only along its direction of travel,
never laterally"; spec ``sim-review/2128-R2b.md`` B2).

Two roads whose centrelines cross where one passes over the other share no
level: the descent of one never walks into the other through the vertices
their faces share at the crossing, and a vertex of one is never stationed
on the other's route.  The crossings are derived ONCE on the full map
(``planar/grade_separation``) and published as ``PlanarMap.road_crossings``;
the road ramp (``airport/road_ramp``) reads them.

A road is named by its centreline (:func:`road_key`): a mapped way
``osm:<way>``, an apt.dat route or network centreline by its breakline ref
-- the same names the road profile's ways carry (``airport/road_profile``).
Each side of a crossing is the set of road-face vertices whose faces run
ALONG that centreline near the crossing.

In ``model`` so the ``planar`` writer and the ``airport`` reader share one
record.  Nothing here names an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from .frame import XY

__all__ = ["RoadCrossing", "road_key", "crossing_vertices", "far_keys", "other_side"]


@_dc.dataclass(frozen=True)
class RoadCrossing:
    """Roads ``a`` and ``b`` (by :func:`road_key`) cross at ``xy`` one over
    the other (``witness``: what says so); ``a_vertices`` / ``b_vertices``
    the vertices of the road faces running along each there."""
    a: str
    b: str
    xy: XY
    witness: str
    a_vertices: frozenset[int] = frozenset()
    b_vertices: frozenset[int] = frozenset()

    @property
    def vertices(self) -> frozenset[int]:
        """The vertices both roads' faces share at the crossing."""
        return self.a_vertices & self.b_vertices


def road_key(ref: str) -> str:
    """The centreline a profile way stands on: its ref less the breakline
    suffix (``route<k>#<id>`` -> ``route<k>``; ``osm:<way>`` stays)."""
    return str(ref).split("#", 1)[0]


def crossing_vertices(crossings: _t.Iterable[RoadCrossing]) -> frozenset[int]:
    """Every vertex two separated roads' faces share."""
    return frozenset(v for c in crossings or () for v in c.vertices)


def far_keys(crossings: _t.Iterable[RoadCrossing]) -> dict[int, frozenset[str]]:
    """``vertex -> the roads it crosses over or under``: a vertex on one
    side only (never a shared one)."""
    out: dict[int, set[str]] = {}
    for c in crossings or ():
        for v in c.a_vertices - c.b_vertices:
            out.setdefault(v, set()).add(c.b)
        for v in c.b_vertices - c.a_vertices:
            out.setdefault(v, set()).add(c.a)
    return {v: frozenset(k) for v, k in out.items()}


def other_side(crossings: _t.Iterable[RoadCrossing]) -> dict[str, frozenset[int]]:
    """``road -> the vertices of the roads it crosses over or under``."""
    out: dict[str, set[int]] = {}
    for c in crossings or ():
        out.setdefault(c.a, set()).update(c.b_vertices)
        out.setdefault(c.b, set()).update(c.a_vertices)
    return {k: frozenset(v) for k, v in out.items()}
