"""A FLAT-BUILT TERMINAL GROUP (owner Q370 a, 2026-11-03T10:47:23Z, #1717;
spec ``docs/specs/flat-airside-terminal-20261103.md`` §1).

Owner: "Next to a terminal whose pack is built flat, should the airside be:
a) held flat at the terminal's own level, as in your patch, so the lower
level stays 7 m under it and the terminal's objects stay seated" -- (a);
and 13:58:37Z, the level is the highest one grade law allows (O-F1 a).

THE GROUP is the object stage's one-zero group read at planar time: the
pack partition's grounded parts (every unit; line and scatter parts out)
chained by footprint ring within ``open_frame_seat.TOUCH_M`` (22o; 23e's
cross-unit merge is the same chain).  A held block belongs to the group
whose chained footprints its pad overlaps most.

THE WITNESS: the group's STAND-SIDE walled feet -- the feet
``airside_group_seat.airside_zeros`` reads the zero on (on or within
``TOUCH_M`` of rolled-on pavement, within ``STAND_M`` of a stand or a
jetway, walled) -- are at least ``PLANE_MIN_FEET``; more than
``flat_pack.detector.level_share_min`` of them lie within
``PLANE_BAND_M`` of their ``floor_plane`` (20x's "greater than 90 % at one
level", on the group's own frontage); and the DEM under them has relief
over the class's floor (``flat_pack.relief_floor``: on flat ground there
is nothing to hold).  No constant of its own.

:func:`flat_groups` answers ``{block ref: record}`` for every held block of
a flat-built group holding two or more of them; the record's ``lead`` is
the block nearest the most stand-side feet (23e's winner).  The datum tie
and the level are ``constraints/platform.datum_groups`` /
``constraints/no_step.hold_interval``'s; the fronting apron is
``planar/pad_cut.plateau_cut``'s.
"""
from __future__ import annotations

import typing as _t

import numpy as np
import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

__all__ = ["flat_groups", "WITNESS_MAX"]

#: at most this many stand-side feet witness the group's zero
WITNESS_MAX = 256


def _part_footprints(airport, to_xy, wall_min: float):
    """``(footprints buffered by half the touch, feet [(k, x, y, y_foot,
    walled)])`` of every grounded part of the partition."""
    from ..airport.open_frame_seat import TOUCH_M
    geoms: list = []
    feet: list = []
    for u in airport.partition.units:
        for m in u.members:
            for p in m.parts:
                if getattr(p, "line", False) or getattr(p, "scatter", False):
                    continue
                gs = [Polygon([to_xy(lo, la) for la, lo in rg])
                      for rg in (p.rings or ()) if len(rg) >= 3]
                gs = [g if g.is_valid else g.buffer(0.0) for g in gs]
                g = unary_union(gs) if gs else None
                if g is None or g.is_empty:
                    continue
                k = len(geoms)
                geoms.append(g.buffer(0.5 * TOUCH_M))
                walled = float(getattr(p, "height_m", 0.0) or 0.0) >= wall_min
                for f in (p.feet or ()):
                    x, y = to_xy(float(f[1]), float(f[0]))
                    feet.append((k, x, y, float(f[2]), walled))
    return geoms, feet


def _components(geoms) -> list[int]:
    """The chained-footprint component of every footprint (union-find)."""
    tree = STRtree(geoms)
    par = list(range(len(geoms)))

    def find(a: int) -> int:
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    for i, g in enumerate(geoms):
        for j in tree.query(g, predicate="intersects"):
            a, b = find(i), find(int(j))
            if a != b:
                par[a] = b
    return [find(i) for i in range(len(geoms))]


def flat_groups(pads: _t.Mapping[str, _t.Any], air, airport, law) -> dict[str, dict]:
    """``{held block ref: {"lead", "group", "feet", "share", "relief_m",
    "y_plane"}}`` for the held blocks of every flat-built group (module
    docstring).  ``pads`` maps each held block to its pad outline (planar
    frame), ``air`` is the rolled-on airside union.  Empty without a pack
    partition, stands or a DEM."""
    from ..airport import airside_group_seat as ag
    from ..airport.flat_pack import relief_floor
    from ..law.tables import flat_pack as _fp
    from .low_level import _stands_xy
    if getattr(airport, "partition", None) is None or getattr(airport, "dem", None) is None \
            or not pads or air is None or air.is_empty:
        return {}
    to_xy = airport.frame.entry()
    stands = _stands_xy(airport, to_xy)
    if not stands:
        return {}
    wall_min = float(law.tables.structures.placement.chain_min_height_m)
    geoms, feet = _part_footprints(airport, to_xy, wall_min)
    if not geoms or not feet:
        return {}
    comp = _components(geoms)
    tree = STRtree(geoms)
    of: dict[str, int] = {}
    for b, P in sorted(pads.items()):
        best = None
        for j in tree.query(P, predicate="intersects"):
            a = P.intersection(geoms[int(j)]).area
            if a > 0.0 and (best is None or a > best[0]):
                best = (a, comp[int(j)])
        if best is not None:
            of[b] = best[1]
    by: dict[int, list[str]] = {}
    for b, c in of.items():
        by.setdefault(c, []).append(b)
    F = np.asarray(feet, dtype=float)
    fc = np.asarray([comp[int(k)] for k in F[:, 0]])
    xy = F[:, 1:3]
    at = (shapely.contains_xy(air.buffer(ag.TOUCH_M), xy[:, 0], xy[:, 1]) & (F[:, 4] > 0.5))
    near = np.zeros(len(F), dtype=bool)
    hit = STRtree(shapely.points(np.asarray(stands, dtype=float))).query(
        shapely.points(xy), predicate="dwithin", distance=ag.STAND_M)
    near[hit[0]] = True
    at &= near
    floor_m, _klass = relief_floor(airport, law)
    share_min = float(_fp(law).detector.level_share_min)
    storey = ag.storey_m(law)
    out: dict[str, dict] = {}
    for c, bs in sorted(by.items()):
        sel = at & (fc == c)
        if len(bs) < 2 or int(sel.sum()) < ag.PLANE_MIN_FEET:
            continue
        Y = F[sel, 3]
        t = -float(ag.floor_plane([-float(y) for y in Y], storey))
        share = float(np.mean(np.abs(Y - t) <= ag.PLANE_BAND_M))
        g = []
        for x, y in xy[sel]:
            try:
                v = float(airport.dem.z(float(x), float(y)))
            except Exception:  # noqa: BLE001 -- off the raster
                continue
            if v == v:
                g.append(v)
        if len(g) < ag.PLANE_MIN_FEET:
            continue
        relief = float(np.percentile(g, 95) - np.percentile(g, 5))
        if not (share > share_min and relief > floor_m):
            continue
        # THE LEAD: the block nearest the most stand-side feet (23e's winner)
        n_of: dict[str, int] = {}
        for x, y in xy[sel]:
            pt = shapely.points(float(x), float(y))
            d, b = min((float(pads[q].distance(pt)), q) for q in bs)
            if d <= ag.STAND_M:
                n_of[b] = n_of.get(b, 0) + 1
        lead = max(sorted(bs), key=lambda b: n_of.get(b, 0))
        # the WITNESSES the object stage reads the zero on (frame xy, y),
        # at most WITNESS_MAX of them evenly sampled
        idx = np.flatnonzero(sel)[::max(1, -(-int(sel.sum()) // WITNESS_MAX))]
        wit = (tuple((round(float(F[i, 1]), 3), round(float(F[i, 2]), 3)) for i in idx),
               tuple(round(float(F[i, 3]), 3) for i in idx))
        for b in bs:
            out[b] = {"lead": lead, "group": len(bs), "feet": n_of.get(b, 0),
                      "share": round(share, 3), "relief_m": round(relief, 2),
                      "y_plane": round(t, 3), "air_xy": wit[0], "air_y": wit[1]}
    return out
