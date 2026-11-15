"""THE CUT BESIDE A GROUPED MOUTH'S WINGS (#2099 R2; spec
``docs/specs/2099-R2-wing-cut.md``): the record the planar stage derives
(``planar/wing_cut``) and the constraint generator reads
(``constraints/wing_cut``).

A mouth's wing walls (``airport/mouth_group``) are a RAMP WITNESS: each
wing's FOOT -- its lowest solid y per station, over the mouth's floor --
is the authored floor line along it.  The ground between the wings and
across the mouth's opening, from the mouth out to the wings' ends, stands
on that line: :func:`wing_floor_y` is the foot under a point, the wings'
feet weighted by inverse squared distance.

Data only (no shapely, no numpy -- ``test_model.py``).  Frame metres.
"""
from __future__ import annotations

import dataclasses as _dc
import math

from .frame import XY

__all__ = ["WingCut", "WING_CUT_REF", "wing_floor_y"]

#: the ref prefix of the ground minted in a wing cut (``wing_cut:<mouth>``)
WING_CUT_REF = "wing_cut"


@_dc.dataclass(frozen=True)
class WingCut:
    """One mouth's cut: ``region`` its plan (exterior rings), ``feet`` the
    wings' foot samples ``(x, y, foot y over the mouth's floor, wing id)``
    along their inner faces; the floor's seat is the mouth's own --
    a hard deck's end lines (``seats`` = its two end lines' stations,
    ``tops`` their authored tops; zero = the solved surface there less the
    top) with ``floor_y`` its floor under its zero, or, for a row-seated
    portal, the absolute ``floor_z`` its record states."""

    mouth: str
    ref: str
    region: tuple[tuple[XY, ...], ...]
    feet: tuple[tuple[float, float, float, str], ...]
    floor_y: float = 0.0
    seats: tuple[tuple[XY, ...], ...] = ()
    tops: tuple[float, ...] = ()
    floor_z: "float | None" = None


def wing_floor_y(cut: WingCut, xy: XY, near_m: float = 0.5) -> float:
    """The foot over the mouth's floor under ``xy``: per wing, the foot at
    its nearest sample; the wings weighted by ``1 / max(d, near_m)**2``."""
    best: dict[str, tuple[float, float]] = {}
    for x, y, f, w in cut.feet:
        d = math.hypot(x - xy[0], y - xy[1])
        if w not in best or d < best[w][0]:
            best[w] = (d, f)
    if not best:
        return 0.0
    num = den = 0.0
    for d, f in best.values():
        k = 1.0 / max(d, near_m) ** 2
        num += k * f
        den += k
    return num / den
