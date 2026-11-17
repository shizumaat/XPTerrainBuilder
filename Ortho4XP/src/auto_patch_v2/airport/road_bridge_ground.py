"""THE GROUND UNDER A GENERATED ROAD BRIDGE IS CUT TO ITS CLEARANCE (#2141
item 5; the plan is ``planar/road_bridge_clear``'s; sibling of
``airport/bridge_ground``).

Each generated road bridge (``Airport.road_bridges``) carries ``ground``:
CUT ribbons in frame xy -- a lower road's axis, a half width and a
``(station, level)`` profile along it: the road cut to the clearance under
the span, ramped back to its survey.  A point inside reads the lower of its
own value and the profile (LOWER ONLY).

TWO SITES, ONE MODEL (as ``bridge_ground``): ``planar/build`` substitutes
``Vertex.dem_z`` of the vertices no airside face carries (tile-seam
vertices keep theirs), and ``airport/road_profile.core_profiles`` chains
:func:`clearance_sampler` inside the patch's band, so the road profiles and
every ``preferred_z`` reader read one ground.  A cut reaches only the
patch's vertices: under the span's own hole the base mesh reads the
survey.  No generated road bridge, no ribbon: the identity.  Nothing here
names an airport."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

__all__ = ["ClearanceGround", "clearance_ribbons", "clearance_sampler", "clearance_ground"]


@_dc.dataclass(frozen=True)
class _Ribbon:
    axis: LineString
    poly: Polygon
    s: tuple[float, ...]
    z: tuple[float, ...]

    def level(self, p: Point) -> float:
        return float(np.interp(self.axis.project(p), self.s, self.z))


class Ribbons(tuple):
    """The ribbons (a tuple of :class:`_Ribbon`) with their index cached."""

    _tree: _t.Any = None


@_dc.dataclass
class ClearanceGround:
    """What the planar site did (the build's line)."""

    ribbons: int = 0
    cut: int = 0
    max_cut_m: float = 0.0
    seam_kept: int = 0

    def line(self) -> str:
        return (f"road bridge ground (#2141): {self.ribbons} cut ribbon(s); {self.cut} "
                f"vertex(es) cut under the spans (max {self.max_cut_m:.2f} m); tile-seam "
                f"vertices kept: {self.seam_kept}")


def clearance_ribbons(airport) -> Ribbons:
    """Every generated road bridge's ground ribbons (module doc)."""
    out = []
    for b in getattr(airport, "road_bridges", ()) or ():
        for g in b.get("ground", ()) or ():
            ax = LineString(g["axis"]) if len(g.get("axis", ())) >= 2 else None
            if ax is None or ax.length <= 0.0 or len(g.get("prof", ())) < 2:
                continue
            prof = sorted((float(s), float(z)) for s, z in g["prof"])
            if g.get("kind") != "cut":
                continue
            out.append(_Ribbon(ax,
                               ax.buffer(float(g["half"]), cap_style="flat"),
                               tuple(s for s, _z in prof), tuple(z for _s, z in prof)))
    return Ribbons(out)


def _levels(rs: Ribbons, xs, ys, zs) -> np.ndarray:
    """``zs`` read under the ribbons: the lower of each and the cut."""
    out = np.array(zs, dtype=float, copy=True)
    if not rs or len(out) == 0:
        return out
    if rs._tree is None:
        rs._tree = STRtree([r.poly for r in rs])
    for i in range(len(out)):
        if not np.isfinite(out[i]):
            continue
        p = Point(float(xs[i]), float(ys[i]))
        for k in rs._tree.query(p):
            if rs[int(k)].poly.covers(p):
                out[i] = min(out[i], rs[int(k)].level(p))
    return out


def clearance_sampler(sample, rs: Ribbons, in_band=None):
    """``sample`` read under the ribbons (inside the patch's band,
    ``in_band``: ``(xy (n, 2)) -> mask``, where given); ``sample`` itself
    with none."""
    if not rs:
        return sample

    def _sample(xs, ys):
        xs = np.atleast_1d(np.asarray(xs, float))
        ys = np.atleast_1d(np.asarray(ys, float))
        z = np.array(sample(xs, ys), dtype=float)
        new = _levels(rs, xs, ys, z)
        if in_band is not None:
            band = np.asarray(in_band(np.column_stack([xs, ys])), bool)
            new = np.where(band, new, z)
        return new
    return _sample


def clearance_ground(rs: Ribbons, xs, ys, zs, airside: _t.AbstractSet[int],
                     seam: _t.AbstractSet[int] = frozenset()
                     ) -> tuple[np.ndarray, ClearanceGround]:
    """THE PLANAR SITE: ``zs`` read under the ribbons at every vertex no
    airside face carries and off the tile seams; and the report."""
    rep = ClearanceGround(ribbons=len(rs))
    zs = np.asarray(zs, float)
    new = _levels(rs, np.asarray(xs, float), np.asarray(ys, float), zs)
    out = zs.copy()
    for v in np.flatnonzero(np.isfinite(zs) & (new < zs - 1e-9)):
        v = int(v)
        if v in airside:
            continue
        if v in seam:
            rep.seam_kept += 1
            continue
        out[v] = new[v]
        rep.cut += 1
        rep.max_cut_m = max(rep.max_cut_m, float(zs[v] - new[v]))
    return out, rep
