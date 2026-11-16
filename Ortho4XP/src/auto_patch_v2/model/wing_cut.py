"""THE CUT BESIDE A GROUPED MOUTH'S WALLS (#2099 R2 / R3; specs
``docs/specs/2099-R2-wing-cut.md``, ``docs/specs/2099-R3.md`` Part D): the
record the planar stage derives (``planar/wing_cut``) and the constraint
generator reads (``constraints/wing_cut``).

A mouth's wing walls (``airport/mouth_group``) are a RAMP WITNESS.  Each
wing's plan is one or more WALL LINES (``planar/wing_cut.wall_line_feet``);
each line's stations, from the end nearest the mouth, carry its FOOT -- the
lowest solid y of the cross-section normal to the line, over the mouth's
floor -- and its TOP.  The ground on the ROAD side of a line stands on its
foot, read along the line it faces (:func:`wing_floor_y`); the strip on its
far side meets its top (:func:`wing_top_y`).

Data only (no shapely, no numpy -- ``test_model.py``).  Frame metres.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from .frame import XY

__all__ = ["WallLine", "WingCut", "WING_CUT_REF", "WING_BACK_REF", "wing_floor_y",
           "wing_top_y"]

#: the ref prefix of the ground minted in a wing cut (``wing_cut:<mouth>``)
WING_CUT_REF = "wing_cut"
#: the ref prefix of the strip behind a wall line (``wing_back:<mouth>``, R3 D5)
WING_BACK_REF = "wing_back"


@_dc.dataclass(frozen=True)
class WallLine:
    """One wall line of wing ``wing``, its stations from the end nearest the
    mouth: ``face`` the road-side face point, ``back`` the far face point,
    ``foot`` / ``top`` its lowest / highest solid there over the mouth's
    floor."""

    wing: str
    face: tuple[XY, ...]
    back: tuple[XY, ...]
    foot: tuple[float, ...]
    top: tuple[float, ...]


@_dc.dataclass(frozen=True)
class WingCut:
    """One mouth's cut: ``region`` the road-side ground's plan (exterior
    rings), ``back`` the strip behind the lines (rings), ``lines`` the wall
    lines; the floor's seat is the mouth's own -- a hard deck's end lines
    (``seats`` = its two end lines' stations, ``tops`` their authored tops;
    zero = the solved surface there less the top) with ``floor_y`` its floor
    under its zero, or, for a row-seated portal, the absolute ``floor_z`` its
    record states."""

    mouth: str
    ref: str
    region: tuple[tuple[XY, ...], ...]
    lines: tuple[WallLine, ...] = ()
    back: tuple[tuple[XY, ...], ...] = ()
    floor_y: float = 0.0
    seats: tuple[tuple[XY, ...], ...] = ()
    tops: tuple[float, ...] = ()
    floor_z: "float | None" = None
    #: how far from a wall line's face a vertex may stand and still read
    #: that line (R3b D4b; ``[tunnel] dual_carriageway_max_separation_m``)
    reach: float = math.inf

    @property
    def back_ref(self) -> str:
        """The ref of the strip behind the lines (``wing_back:<mouth>``)."""
        return f"{WING_BACK_REF}:{self.mouth}"


def _along(pts: _t.Sequence[XY], xy: XY) -> tuple[float, float, int]:
    """``(t, distance, segment)``: ``xy`` projected on the polyline ``pts``
    -- ``t`` the station index with its fraction (clamped to the line)."""
    if len(pts) == 1:
        return 0.0, math.hypot(xy[0] - pts[0][0], xy[1] - pts[0][1]), 0
    best = (math.inf, 0.0, 0)
    for i, (a, b) in enumerate(zip(pts, pts[1:], strict=False)):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        f = 0.0 if L2 <= 1e-12 else min(1.0, max(0.0, ((xy[0] - a[0]) * dx
                                                       + (xy[1] - a[1]) * dy) / L2))
        d = math.hypot(a[0] + f * dx - xy[0], a[1] + f * dy - xy[1])
        if d < best[0]:
            best = (d, i + f, i)
    return best[1], best[0], best[2]


def _at(vals: _t.Sequence[float], t: float) -> float:
    i = min(int(t), len(vals) - 1)
    f = t - i
    return vals[i] if f <= 0.0 or i + 1 >= len(vals) else vals[i] + f * (vals[i + 1] - vals[i])


def _facing(line: WallLine, xy: XY, reach: float = math.inf
            ) -> "tuple[float, float] | None":
    """``(foot along the line under xy, distance)`` where ``xy`` stands on
    the road side of the line's BACK face (a vertex on the wall's own plan
    reads its own wall), abeam its stations and no farther than ``reach``
    from its face (R3b D4b), else ``None``."""
    if not line.face:
        return None
    t, d, i = _along(line.face, xy)
    j = min(i, len(line.face) - 1)
    fx, fy = line.face[j]
    bx, by = line.back[j]
    if (xy[0] - bx) * (fx - bx) + (xy[1] - by) * (fy - by) < -1e-6 or d > reach:
        return None
    if len(line.face) > 1:
        a, b = line.face[i], line.face[min(i + 1, len(line.face) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        raw = 0.0 if L2 <= 1e-12 else ((xy[0] - a[0]) * dx + (xy[1] - a[1]) * dy) / L2
        if (i == 0 and raw < -0.5) or (i + 2 >= len(line.face) and raw > 1.5):
            return None
    return _at(line.foot, t), d


def wing_floor_y(cut: WingCut, xy: XY) -> float:
    """The foot over the mouth's floor under ``xy`` (R3 D4): read along the
    wall line it faces, linear between stations; between two facing lines,
    linear across (each weighted by the other's distance); where it faces
    none, the nearest line's foot.  A line faces only a vertex within
    ``cut.reach`` of its face, on the road side of its back face (R3b D4b:
    measured, five vertices 0.1-0.2 m behind _T's face read a wall 80 m
    away and stood at the floor)."""
    got = sorted((r[1], r[0]) for ln in cut.lines
                 if (r := _facing(ln, xy, cut.reach)) is not None)
    if len(got) >= 2:
        (d0, f0), (d1, f1) = got[0], got[1]
        return f0 if d0 + d1 <= 1e-9 else (f0 * d1 + f1 * d0) / (d0 + d1)
    if got:
        return got[0][1]
    near = [(_along(ln.face, xy)[1], _at(ln.foot, _along(ln.face, xy)[0]))
            for ln in cut.lines if ln.face]
    return min(near)[1] if near else 0.0


def wing_top_y(cut: WingCut, xy: XY) -> float:
    """The wall top over the mouth's floor behind which ``xy`` stands (R3
    D5): the nearest line's top, read along its far face."""
    near = [(_along(ln.back, xy)[1], _at(ln.top, _along(ln.back, xy)[0]))
            for ln in cut.lines if ln.back]
    return min(near)[1] if near else 0.0
