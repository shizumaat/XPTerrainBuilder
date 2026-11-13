"""THE SURVEYED CUTTING A KEPT MOUTH OPENS INTO (#1939; RULINGS 2026-11-13h
N1, 2026-11-06c (3)/(5)).

A KEPT survey mouth (``lidar_road.survey_mouth``: the credible survey
already carries the road the owed depth under the cover) cuts nothing: its
floor IS the surveyed road, its cap the portal face, its ramp the short run
to where the floor meets the survey.  Two of the mapped-mouth rules of
``structure_mouth`` were written for a mouth that DIGS, and refuse one that
does not:

* **Clause 4's stops** (owner RULINGS 2026-10-19o: every road or lot beside
  the ramp stops it) protect pavement standing AT GRADE beside a trench.
  Pavement the survey reads DOWN IN THE CUTTING with the road -- the pack's
  paving of the carriageways, their shoulders, a lot on the cutting floor
  -- is the floor the mouth opens onto, and a ramp that cuts nothing cannot
  cut it.  :meth:`Cutting.floor_face` reads which: the face's surveyed
  level beside the mouth under the MID-HEIGHT of the portal face (half way
  from the surveyed road to the cover) is the cutting's; above it, the
  ground's, and it still stops.
* **#1028's "surfaces under the pavement"** refuses a slid mouth whose road
  reaches grade before the mouth stands clear: the DEM was read as ground.
  On a credible survey the road stands at its own surveyed level the whole
  way, so "reaching grade" says nothing; what matters is whether the
  survey still reads a cut where the mouth came to stand.
  :meth:`Cutting.slid_floor` re-reads it there (the readers
  ``survey_mouth`` used at the portal): a cut ``[channel]
  object_min_depth_m`` or deeper under the surrounding ground -- the mouth
  is built there at the surveyed road; none -- the road has come out of
  its cutting under the pavement and the refusal stands.

MEASURED ESSA (#1939): four carriageways in a 7 m cutting pass under
taxiway U's bridge (way -74; lidar cover 31.2-31.3 over roads 23.3 / 24.1,
both mouths KEPT).  The north mouth stood against the pack's paving of the
cutting floor (``dsf:pol204`` at 24.0-24.6 beside the service road) and the
south one, slid 11 m out of the deck's own taxi cell, "reached grade" 9 m
out on the cutting floor: both were refused, and the four roads were
ramped up 5-7 m to meet the taxiway at grade (owner: "This road is raised
instead of sloping down").
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import LineString, Point, Polygon

from ..airport.dem import dem_z_at
from ..law import Law
from ..model.frame import XY
from .lidar_road import KEPT, SurveyMouth, surround_level, surveyed_road

__all__ = ["Cutting", "cutting_of"]

#: Plan step (m) of the survey samples a face is read with beside the mouth.
_SAMPLE_M = 2.0


@_dc.dataclass(frozen=True)
class Cutting:
    """A KEPT survey mouth's cutting (module doc): ``road`` the surveyed
    road at the mapped portal, ``cover`` the cover over the bore,
    ``width`` the carriageway width the survey reads the road across."""

    airport: _t.Any
    law: Law
    road: float
    cover: float
    width: float

    @property
    def mid(self) -> float:
        """Half way up the portal face: the level that parts the cutting's
        floor from the ground beside it."""
        return 0.5 * (self.road + self.cover)

    def floor_face(self, poly: Polygon, mouth: XY, reach: float) -> bool:
        """``poly`` (a groundside pavement face) lies on the cutting floor
        within ``reach`` of the mouth: the median of the survey over its part
        there stands under :attr:`mid`."""
        near = poly.intersection(Point(mouth).buffer(reach))
        if near.is_empty or near.area <= 0.0:
            return False
        zs = _samples(self.airport, near)
        if not zs:
            return False
        zs.sort()
        return zs[len(zs) // 2] < self.mid

    def slid_floor(self, axis: LineString) -> float | None:
        """The surveyed road at a mouth slid to ``axis``'s start, where the
        survey still reads a cut there (module doc); ``None`` where it does
        not."""
        def fn(s: float) -> XY:
            q = axis.interpolate(min(s, axis.length))
            return (q.x, q.y)
        road = surveyed_road(self.airport, fn, self.width)
        ground = surround_level(self.airport, fn(0.0))
        if math.isnan(road) or math.isnan(ground):
            return None
        depth = float(self.law.tables.structures.channel.object_min_depth_m)
        return road if ground - road >= depth else None


def cutting_of(airport, law: Law, sm: SurveyMouth | None, width: float) -> Cutting | None:
    """The cutting of a KEPT survey mouth, or ``None`` for any other (a
    mouth that digs keeps every rule of ``structure_mouth``)."""
    if sm is None or sm.verdict != KEPT or sm.rail:
        return None
    return Cutting(airport, law, float(sm.road), float(sm.cover), float(width))


def _samples(airport, region) -> list[float]:
    """The survey on a ``_SAMPLE_M`` grid over ``region`` (at least its
    representative point)."""
    x0, y0, x1, y1 = region.bounds
    pts = [region.representative_point()]
    x = x0 + _SAMPLE_M / 2.0
    while x < x1:
        y = y0 + _SAMPLE_M / 2.0
        while y < y1:
            p = Point(x, y)
            if region.contains(p):
                pts.append(p)
            y += _SAMPLE_M
        x += _SAMPLE_M
    out = [dem_z_at(airport, (p.x, p.y)) for p in pts]
    return [z for z in out if not math.isnan(z)]
