"""A PORTAL IN A CUT STANDS ITS TOP ON THE COVER (#2120 R2 Part P2; spec
``sim-review/2120-R2.md`` §3 P2; owner RULINGS 2026-11-16l / 16t /
2026-11-13u (1)).

A portal in a cut (``airport/cut_portal``) is authored with its zero at
the road floor and its walls up to the cover; the object stage's generic
rule seats a body by its FEET, and the feet of such a frame stand in the
cut -- MEASURED KATL (owner build, Orbx 2026-11): the four I-285 portals
were seated "low-side foot" at zeros 301.88-302.33, their roofs (y 20.0)
standing ~20 m over the 301 m cover beside the cut.

THE RULE.  The portal is seated by a PLATE DATUM: its ``top_y`` (the top
of its tallest static component, the headwall / roof the cover meets; a
parapet above it stands proud, 16l) on the solved surface at STATIONS
``grid`` outside its plan, every ``step`` along it, on the COVER SIDE --
where the ground stands in the upper half of the cut's relief
(``CutPortal.floor_z`` .. ``cover_z``), never in the cut below it.  Its
foot goes where that puts it (13u (1): buried under the road floor; no
ground is dug to show it).  A member another rule already seats
(``taken``) is never entered.

NO LAW CONSTANT LIVES HERE: the grid and the step are the caller's
(``emit.identity.min_distinct_spacing_m``,
``structures.bridge.abutment_sample_step_m``)."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np
import shapely

__all__ = ["CUT_BRIDGE_PLATE", "PORTAL_PLATE", "cover_side", "portal_seats"]

#: the plate kind of a portal in a cut's seat (``anchor_rule.datum_of``)
PORTAL_PLATE = "portal_cut"
#: the plate kind of a bridge over a portal's cut (``airport/cut_bridge``):
#: the same datum reading, its own reason text
CUT_BRIDGE_PLATE = "cut_bridge"


@_dc.dataclass(frozen=True)
class _PortalSeat:
    """One portal's plate: its placement id, the authored ``y`` put on the
    cover and the stations (frame xy) the cover is read at."""

    oid: str
    top_y: float
    stations: tuple
    resource: str = ""


def _outline_points(plan, grid_m: float, step_m: float) -> np.ndarray:
    """Points ``grid_m`` outside ``plan``'s outer rings, every ``step_m``."""
    grown = plan.buffer(float(grid_m), join_style="mitre", mitre_limit=2.0)
    out = []
    for g in getattr(grown, "geoms", [grown]):
        ring = g.exterior
        n = max(4, int(np.ceil(ring.length / float(step_m))))
        out.append(shapely.get_coordinates(shapely.line_interpolate_point(
            ring, np.linspace(0.0, ring.length, n, endpoint=False))))
    return np.concatenate(out) if out else np.zeros((0, 2))


def _cover_stations(portal, dem, grid_m: float, step_m: float) -> tuple:
    """The stations of ``portal`` on the cover side (module doc): outline
    points whose DEM stands in the upper half of the cut's relief."""
    pts = _outline_points(portal.plan, grid_m, step_m)
    if not len(pts) or dem is None:
        return ()
    keep = cover_side(portal, dem, pts)
    return tuple((float(x), float(y)) for x, y in pts[keep])


def cover_side(portal, dem, pts: np.ndarray) -> np.ndarray:
    """Which of ``pts`` (frame xy, ``(n, 2)``) stand on ``portal``'s COVER
    SIDE: their DEM in the upper half of the cut's relief
    (``CutPortal.floor_z`` .. ``cover_z``), never in the cut below it."""
    from .dem import dem_z_many
    if not len(pts) or dem is None:
        return np.zeros(len(pts), dtype=bool)
    z = dem_z_many(dem, pts[:, 0], pts[:, 1])
    mid = 0.5 * (float(portal.floor_z) + float(portal.cover_z))
    return np.isfinite(z) & (z >= mid)


def portal_seats(airport, grid_m: float, step_m: float,
                 taken: _t.Container[str] = frozenset()) -> tuple[_PortalSeat, ...]:
    """Every portal in a cut of ``airport`` (``Airport.cut_portals``) the
    rule seats (module doc), one record per placement."""
    dem = getattr(airport, "dem", None)
    out = []
    for p in getattr(airport, "cut_portals", ()) or ():
        if p.object_id in taken:
            continue
        st = _cover_stations(p, dem, grid_m, step_m)
        if st:
            out.append(_PortalSeat(p.object_id, float(p.top_y), st, p.resource))
    return tuple(out)
