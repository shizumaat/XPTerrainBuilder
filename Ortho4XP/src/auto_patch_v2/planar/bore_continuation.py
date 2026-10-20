"""A BORE END THAT IS NO PORTAL (issue #1028, owner Q32: "either there isn't
really a tunnel there, or it's steeper, or the shape is wrong").

A mapped tunnel way's end is a mouth only where the road comes up out of the
ground.  It is NOT one where the road goes on UNDERGROUND: another tunnel way
leaves the end's node within the approach turn cap, either straight away
(a second OSM feed's copy of the same tunnel, which splits
``structure_approach.chains`` because four ways meet at the node) or after
an open stretch of road shorter than the shortest lawful ramp
(``mouth_depth_m / ramp_max_grade``), which cannot come up to grade and go
back down again.  Measured at EDDF: rail ``-27364`` continuing as
``-10179`` at 1°, service ``-25266`` as its other feed's ``-33590`` at 0°,
and KCLT ``-6954`` running into ``-8739`` 19 m on.  Each built a full ramp
along the tunnel ahead.

:func:`tunnel_ends` indexes the tunnel ways' ends once per pass;
:func:`continues_underground` names why an end is no portal (or ``None``).
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString

from ..law import Law
from ..model.airport import OsmWay
from ..model.frame import XY
from .structure_approach import _key, is_tunnel, unit

__all__ = ["tunnel_ends", "continues_underground"]


def tunnel_ends(osm: _t.Sequence[OsmWay], admitted: _t.Sequence[str]
                ) -> dict[tuple[int, int], list[tuple[OsmWay, XY, XY]]]:
    """Every tunnel way's two ends by node key: ``(way, end, next point)``."""
    out: dict[tuple[int, int], list[tuple[OsmWay, XY, XY]]] = {}
    for w in osm:
        if len(w.points) < 2 or not is_tunnel(w, admitted):
            continue
        out.setdefault(_key(w.points[0]), []).append((w, w.points[0], w.points[1]))
        out.setdefault(_key(w.points[-1]), []).append((w, w.points[-1], w.points[-2]))
    return out


def _walked(path: _t.Sequence[XY], inward: XY, reach_m: float
            ) -> tuple[float, XY, XY] | None:
    """``(metres walked on mapped ways, the node the walk ended at, its
    heading)`` when ``structure_approach.approach`` ended its walk early
    (it then appends ONE straight extension to ``reach_m + 1``), else
    ``None``: the road runs on for the whole reach."""
    if len(path) < 2 or abs(LineString(path).length - (reach_m + 1.0)) > 1e-6:
        return None
    walked = LineString(path[:-1]).length if len(path) >= 3 else 0.0
    last = path[-2]
    heading = unit(path[-3], path[-2]) if len(path) >= 3 else (-inward[0], -inward[1])
    return walked, last, heading


def continues_underground(bore, inward: XY, path: _t.Sequence[XY], ends, law: Law,
                          reach_m: float) -> str | None:
    """Why the bore end whose approach is ``path`` is NO PORTAL (module
    doc), or ``None``.  ``ends`` is :func:`tunnel_ends`."""
    tn = law.tables.structures.tunnel
    got = _walked(path, inward, reach_m)
    if got is None:
        return None
    walked, last, heading = got
    if walked >= tn.mouth_depth_m / tn.ramp_max_grade:
        return None
    own = {id(w) for w in bore.ways}
    cos_max = math.cos(math.radians(tn.approach_turn_max_deg))
    for w, a, b in ends.get(_key(last), ()):
        if id(w) in own:
            continue
        d = unit(a, b)
        if d[0] * heading[0] + d[1] * heading[1] >= cos_max:
            ids = "+".join(str(x.id) for x in bore.ways)
            return (f"bore {ids}: its end is no portal — the road goes on underground as "
                    f"tunnel way {w.id} {walked:.0f} m out (under the shortest lawful ramp "
                    f"{tn.mouth_depth_m / tn.ramp_max_grade:.0f} m; #1028)")
    return None
