"""ELEVATED STRUCTURES OVER MAPPED ROADS AND RAILS -- THE CROSSING READ
(owner RULINGS 2026-11-20g; spec ``docs/specs/elevated-clearance-20g-spec.md``).

Owner 2026-11-20T16:59Z: "When a pack has buildings connected by elevated
structures that cross mapped roads or rails, e.g. skybridges ... or roads
and rails like KMCO, determine the optimal way to take their clearance into
account".  RULED (1): where a pack's elevated structure crosses a mapped
road or rail, its soffit keeps the class minimum clearance over it.

THE ONE READING, for every consumer (the census tool, the object stage):

* A MAPPED WAY a structure may stand over (:func:`crossable`): a
  ``highway`` or ``railway`` way that is no bridge itself
  (``deck_signature.is_bridge_way``: a bridge is the elevated thing, never
  the thing under it).  A ``tunnel`` way is kept: a road the map tags as
  passing under a building is exactly a crossing (KMCO's ``-1878``,
  §34 (12) (5) (e) "the road's passage under it").
* Its CARRIAGEWAY (:func:`carriageways`): the centreline grown by half the
  mapped carriageway width (``model/road_clearance.carriageway_width_m``),
  flat ends; its NEED the class minimum (``design_clearance_m``: 4.2 m over
  a small road, 5.0 m over every other road and rail -- owner
  2026-11-17T19:08Z).
* THE SOFFIT over a carriageway cell (:func:`read_crossings`): the LOWEST
  static solid face of one placed structure whose plan holds the cell
  (``geom/lowest_face.every_z_at``: its plane there).  The cell is a
  CROSSING cell where that lowest face stands over the structure's FLOOR
  -- the plane its geometry is at grade on (an owner's ``floor``: the
  object stage passes the frame zero plus ``[rebake] elevated_base_m``, so
  a soffit pushed into the road still counts, at a negative clearance);
  with no floor, :data:`OVER_GROUND_M` over the ground there (what the
  installed product alone can say).  A cell whose lowest face is AT GRADE
  is a part standing on the road -- a building the road enters -- and is
  no crossing cell.
* A structure CROSSES the way only where it SPANS the carriageway: in some
  :data:`STEP_M` station along the centreline its crossing cells cover
  :data:`SPAN_SHARE` of the carriageway's cells there.  A car parked at the
  kerb, a canopy over one lane, a tree's crown is no crossing; a sky
  bridge, a viaduct, a sign gantry is.  Only the spanning stations count.
* THE CLEARANCE of one crossing is ``soffit - ground`` at its least cell;
  the ground is the caller's (the drawn mesh, the solved surface).

Nothing here names an airport, a pack or a resource (RULINGS 2026-10-05e).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

__all__ = ["Carriageway", "Crossing", "crossable", "carriageways", "read_crossings",
           "OVER_GROUND_M", "STEP_M", "SPAN_SHARE"]

#: overhead geometry stands at least this far over the ground where no
#: floor is known (``planar/level_underside.OVER_FLOOR_M``'s reading: a
#: kerb, a road surface drawn on the ground itself, is no soffit)
OVER_GROUND_M = 0.5
#: the carriageway is read on a grid this fine, metres
STEP_M = 1.0
#: a structure spans the carriageway at a station where its crossing cells
#: are at least this share of the carriageway's cells there
SPAN_SHARE = 0.8


@_dc.dataclass(frozen=True)
class Carriageway:
    """One mapped way's carriageway: ``way`` its id, ``kind`` its class
    (``highway=service``, ``railway=rail``), ``need_m`` the class minimum
    clearance, ``poly`` the carriageway in the caller's metric frame."""

    way: str
    kind: str
    need_m: float
    poly: _t.Any
    tunnel: bool = False
    #: the centreline the stations are read along
    line: _t.Any = None


@_dc.dataclass(frozen=True)
class Crossing:
    """One structure (``owner``, the caller's key) over one carriageway:
    the crossing cells read, the LEAST clearance and where it is (``at``,
    frame xy), the soffit and ground there, the median clearance."""

    owner: _t.Any
    way: str
    kind: str
    need_m: float
    cells: int
    least_m: float
    at: tuple[float, float]
    soffit_z: float
    ground_z: float
    p50_m: float

    @property
    def short_m(self) -> float:
        """How far the least clearance falls short of the class minimum
        (0 where it clears)."""
        return max(0.0, self.need_m - self.least_m)


def crossable(tags: _t.Mapping[str, str]) -> bool:
    """A mapped road or rail a structure may stand over (module doc)."""
    from .deck_signature import is_bridge_way
    tags = tags or {}
    if not (tags.get("highway") or tags.get("railway")):
        return False
    return not is_bridge_way(tags)


def carriageways(ways: _t.Iterable[_t.Any], xy_of: _t.Callable[[_t.Any], list],
                 law: _t.Any) -> list[Carriageway]:
    """Every :func:`crossable` way's carriageway (module doc); ``xy_of(way)``
    its centreline in the caller's metric frame."""
    from shapely.geometry import LineString

    from ..model.road_clearance import carriageway_width_m, design_clearance_m
    from .deck_signature import is_tunnel_way
    out: list[Carriageway] = []
    for w in ways:
        tags = getattr(w, "tags", None) or {}
        if not crossable(tags):
            continue
        pts = xy_of(w)
        if len(pts) < 2:
            continue
        line = LineString(pts)
        poly = line.buffer(carriageway_width_m(tags, law) / 2.0, cap_style="flat")
        if poly.is_empty:
            continue
        kind = (f"highway={tags['highway']}" if tags.get("highway")
                else f"railway={tags.get('railway')}")
        out.append(Carriageway(str(w.id), kind, design_clearance_m(tags, law), poly,
                               is_tunnel_way(tags), line))
    return out


def _cells(poly, box, step: float, pad: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """The grid cell centres of ``step`` metres inside ``poly`` and the
    plan ``box`` ``(x0, y0, x1, y1)`` grown by ``pad`` (a station's share
    is read over the whole carriageway there, not the box's corner)."""
    import shapely
    x0, y0, x1, y1 = box
    g = poly.intersection(shapely.box(x0 - pad, y0 - pad, x1 + pad, y1 + pad))
    if g.is_empty:
        return np.zeros(0), np.zeros(0)
    x0, y0, x1, y1 = g.bounds
    xs = np.arange(math.floor(x0 / step) * step, x1, step) + 0.5 * step
    ys = np.arange(math.floor(y0 / step) * step, y1, step) + 0.5 * step
    px, py = np.repeat(xs, len(ys)), np.tile(ys, len(xs))
    keep = shapely.contains_xy(g, px, py)
    return px[keep], py[keep]


def _spanning(c: Carriageway, px: np.ndarray, py: np.ndarray, hit: np.ndarray,
              step: float) -> np.ndarray:
    """``hit`` kept only at the stations (``step`` along the centreline)
    where it covers :data:`SPAN_SHARE` of the carriageway's cells."""
    import shapely
    if c.line is None:
        return hit
    s = np.floor(shapely.line_locate_point(c.line, shapely.points(px, py)) / step).astype(int)
    keep = np.zeros(hit.shape, dtype=bool)
    for b in np.unique(s[hit]):
        at = s == b
        if hit[at].sum() >= SPAN_SHARE * at.sum():
            keep |= at & hit
    return keep


def read_crossings(owners: _t.Iterable[tuple[_t.Any, np.ndarray, "float | None"]],
                   cways: _t.Sequence[Carriageway],
                   ground: _t.Callable[[np.ndarray, np.ndarray], np.ndarray],
                   step: float = STEP_M, over_m: float = OVER_GROUND_M) -> list[Crossing]:
    """Every crossing of ``owners`` -- ``(key, faces, floor)``: a placed
    structure's static solid faces ``(n, 3, 3)`` (frame x, y, world z) and
    the world z its geometry is at grade on (``None``: read
    :data:`OVER_GROUND_M` over the ground) -- over ``cways`` (module doc);
    ``ground(xs, ys)`` the ground under frame points (``nan`` = none)."""
    import shapely
    from shapely.strtree import STRtree

    from ..geom.lowest_face import every_z_at
    if not cways:
        return []
    tree = STRtree([c.poly for c in cways])
    out: list[Crossing] = []
    for key, faces, floor in owners:
        faces = np.asarray(faces, dtype=np.float64)
        if not len(faces):
            continue
        fx0, fy0 = faces[:, :, 0].min(axis=1), faces[:, :, 1].min(axis=1)
        fx1, fy1 = faces[:, :, 0].max(axis=1), faces[:, :, 1].max(axis=1)
        box = (float(fx0.min()), float(fy0.min()), float(fx1.max()), float(fy1.max()))
        for j in tree.query(shapely.box(*box)):
            c = cways[int(j)]
            cx0, cy0, cx1, cy1 = c.poly.bounds
            near = (fx1 >= cx0) & (fx0 <= cx1) & (fy1 >= cy0) & (fy0 <= cy1)
            if not near.any():
                continue
            sub = faces[near]
            width = c.poly.area / max(c.line.length, 1e-9) if c.line is not None else 0.0
            px, py = _cells(c.poly, box, step, pad=width)
            if not px.size:
                continue
            inb = ((px >= box[0]) & (px <= box[2]) & (py >= box[1]) & (py <= box[3]))
            g = np.full(px.shape, np.nan)
            low = np.full(px.shape, np.nan)
            if not inb.any():
                continue
            g[inb] = np.asarray(ground(px[inb], py[inb]), dtype=np.float64)
            low[inb] = [float(z.min()) if z.size else np.nan
                        for z in every_z_at(sub, px[inb], py[inb])]
            base = (g + over_m) if floor is None else np.full(g.shape, float(floor))
            hit = np.isfinite(low) & np.isfinite(g) & (low > base)
            if hit.any():
                hit = _spanning(c, px, py, hit, step)
            if not hit.any():
                continue
            d = low[hit] - g[hit]
            k = int(np.argmin(d))
            out.append(Crossing(key, c.way, c.kind, c.need_m, int(hit.sum()),
                                round(float(d[k]), 3),
                                (float(px[hit][k]), float(py[hit][k])),
                                round(float(low[hit][k]), 3), round(float(g[hit][k]), 3),
                                round(float(np.median(d)), 3)))
    return out
