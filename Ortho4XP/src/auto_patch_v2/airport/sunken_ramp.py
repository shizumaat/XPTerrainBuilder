"""THE RAMP END THAT SINKS INTO THE GROUND (issue #516; owner RULINGS
2026-09-13bi / 13cm, the master's reading 2026-10-13 pending the owner).

The owner, on the ramp object that leads up to a terminal: it "should stay
locked to the building and sink into the ground so its ramp meets DEM";
"the top deck meeting the sloping terrain at the ramp ends".  A unit's pad
is the union of its members' footprints (``geom.cluster_outlines``), so a
sloped road deck that is a member of the unit puts its WHOLE footprint
into the flat pad.  Where the deck's low end, at the unit's level, stands
under the natural ground, the pad cuts the ground away to the unit's level
under it and the ramp lies in a pit (SPJC −12.0318118, −77.1134626: the
ramp end 3.9 m under the DEM; the road ran into a 4.1 m step, and since
#631 it ramps down into a trench instead).

THE RULE.  Inside a cluster's outline, the ground where a member's TOP
SURFACE is one CONTINUOUS SLOPED DECK that rises THROUGH the natural
ground — below it at one end, above it further on — and where that ground
stands above the unit's level, is not the pad's: it is returned here as a
SHADE and leaves the outline at the same site and in the same way as a
welded deck's shade (``geom.cluster_outlines`` rule 8).  The terrain there
keeps its own design surface (the DEM, a road), the object keeps its seat
on the unit, and the road meets the deck where the deck comes out of the
ground.  The object stage is not touched.

On a raster of ``[placement] sunken_ramp_grid_m`` cells over the outline:

* ``D`` — the unit's level, estimated as the DEM median over the outline
  (the pad's level is solved later; the estimate only moves the station
  where the trim ends by its error over the deck's grade);
* ``G`` — the DEM at the cell; ``T`` — the member's top surface (the
  highest authored ``y`` of its solid triangles over the cell centre);
* the candidate ground: ``G > D + band`` (``band`` = ``[cockpit]
  visual_m``) — a pad never cuts less than that, so nothing else moves;
* a COMPONENT: candidate cells chained 4-ways where ``T`` changes by at
  most ``sunken_ramp_step_grade`` x the cell — one ROAD deck surface (the
  road cap's 10 % and a cell's noise), never across a wall, a roof edge
  or a roof's pitch (KASE's fire station: its sloped surround climbs
  17-22 % and is a building in a cut, not a ramp);
* a component is a SUNKEN RAMP iff it holds a cell where the deck stands
  under the ground (``D + T < G - band``, the deck at or above its own
  zero, ``T >= -band`` — a pit floor is the basin law's), a cell where it
  stands over it (``D + T > G + band``), comes down to its own zero
  (``min T <= band``: the ramp end's lip — a roof's eave never does) and
  climbs at least ``sunken_ramp_climb_min_m`` — a flat roof or slab in a
  cut never does.

Only a member some part of which reaches under its own zero over the
candidate ground is read at all: the pack authors such a ramp to sink
into the ground (SPJC's ramp walls run 8.76 m under it), and the parse is
the cost (HECA: 86 of 429 members read, 3.6 s of a 1,046 s build).

The shade is the accepted cells' union, widened to the deck's own walls,
closed by half a cell and clipped to the member's own part rings.  It is
derived ONCE, at load beside the clusters (:func:`attach_sunken_ramps`),
and travels as ``Airport.sunken_ramps``: the pad mint
(``classify/evidence``) and its census (``constraints/cluster_pad``, which
may not import this layer) read that one value.
"""
from __future__ import annotations

import math as _math
import typing as _t

import numpy as np
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

__all__ = ["sunken_ramp_shades", "attach_sunken_ramps", "SUNKEN"]

#: the last derivation's report (per cluster: member, cells, area)
SUNKEN: dict[str, _t.Any] = {}

_MEMO: list = []

#: how far, in cells, the accepted deck reaches to take its own walls
_REACH_CELLS = 2


def _law(law):
    st = law.tables.structures.placement
    return (float(getattr(st, "sunken_ramp_grid_m", 0.0) or 0.0),
            float(getattr(st, "sunken_ramp_climb_min_m", 1.0)),
            float(getattr(st, "sunken_ramp_step_grade", 0.12)),
            float(law.tables.emit.cockpit.visual_m))


def _poly(ring, to_xy) -> "Polygon | None":
    if len(ring) < 3:
        return None
    q = Polygon([to_xy(lo, la) for la, lo in ring])
    if not q.is_valid:
        q = q.buffer(0.0)
    return None if q.is_empty else q


def _local_frame(to_xy, lat: float, lon: float):
    """``(x0, y0, J)``: the frame at ``(lat, lon)`` and its Jacobian per
    metre east / north — a footprint a few hundred metres across is
    placed by it to well under a centimetre, without projecting every
    vertex through the scalar entry projection."""
    from .rebake_plan import _mpd
    ml, mo = _mpd(lat)
    x0, y0 = to_xy(lon, lat)
    xe, ye = to_xy(lon + 100.0 / mo, lat)
    xn, yn = to_xy(lon, lat + 100.0 / ml)
    J = np.array([[(xe - x0) / 100.0, (xn - x0) / 100.0],
                  [(ye - y0) / 100.0, (yn - y0) / 100.0]])
    return x0, y0, J


def _dem_many(dem, xs, ys) -> np.ndarray:
    zm = getattr(dem, "z_many", None)
    if zm is not None:
        return np.asarray(zm(xs, ys), dtype=float)
    return np.array([float(dem.z(float(a), float(b))) for a, b in zip(xs, ys)])


def _box_xy(b, to_xy):
    """A part's ``(lat0, lon0, lat1, lon1)`` box in the frame."""
    (ax, ay), (bx, by) = to_xy(b[1], b[0]), to_xy(b[3], b[2])
    return box(min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))


def _member_tris(m, origin, to_xy):
    """The member's solid triangles in the planar frame: ``(n, 3, 3)`` of
    ``(x, y, authored y)``, or None when its file cannot be read."""
    from . import obj8 as _obj8
    from .placement_cut import pristine_path
    try:
        g = _obj8.parse_obj8(pristine_path(m))
    except (OSError, ValueError):
        return None
    if g is None or not len(g.solid):
        return None
    v = g.vertices
    h = _math.radians(float(m.heading_deg))
    s0, c0 = _math.sin(h), _math.cos(h)
    e = v[:, 0] * c0 - v[:, 2] * s0
    n = -v[:, 0] * s0 - v[:, 2] * c0
    x0, y0, J = _local_frame(to_xy, float(origin[0]), float(origin[1]))
    xy = np.column_stack([x0 + J[0, 0] * e + J[0, 1] * n,
                          y0 + J[1, 0] * e + J[1, 1] * n])
    P = np.column_stack([xy, v[:, 1]])
    return P[g.solid]


def _top_surface(tris, xs, ys, mask) -> np.ndarray:
    """``T[i, j]`` = the highest triangle over cell centre ``(xs[j],
    ys[i])`` among the cells of ``mask``; NaN where none covers it."""
    T = np.full(mask.shape, np.nan)
    if tris is None:
        return T
    g = xs[1] - xs[0] if len(xs) > 1 else 1.0
    x0, y0 = xs[0], ys[0]
    lo = tris[:, :, :2].min(axis=1)
    hi = tris[:, :, :2].max(axis=1)
    j0 = np.clip(np.ceil((lo[:, 0] - x0) / g).astype(int), 0, len(xs))
    j1 = np.clip(np.floor((hi[:, 0] - x0) / g).astype(int) + 1, 0, len(xs))
    i0 = np.clip(np.ceil((lo[:, 1] - y0) / g).astype(int), 0, len(ys))
    i1 = np.clip(np.floor((hi[:, 1] - y0) / g).astype(int) + 1, 0, len(ys))
    for k in np.nonzero((j1 > j0) & (i1 > i0))[0]:
        sub = mask[i0[k]:i1[k], j0[k]:j1[k]]
        if not sub.any():
            continue
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = tris[k]
        det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(det) < 1e-9:
            continue                      # a wall seen from above
        X, Y = np.meshgrid(xs[j0[k]:j1[k]], ys[i0[k]:i1[k]])
        l1 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / det
        l2 = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / det
        l3 = 1.0 - l1 - l2
        inside = (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9) & sub
        if not inside.any():
            continue
        z = l1 * az + l2 * bz + l3 * cz
        blk = T[i0[k]:i1[k], j0[k]:j1[k]]
        upd = inside & ~(blk >= z)
        blk[upd] = z[upd]
    return T


def _components(ok, T, step):
    """4-way components of ``ok`` cells whose neighbours' ``T`` differ by
    at most ``step``."""
    lab = np.full(ok.shape, -1, dtype=int)
    comps: list[list[tuple[int, int]]] = []
    H, W = ok.shape
    for i, j in zip(*np.nonzero(ok)):
        if lab[i, j] >= 0:
            continue
        k = len(comps)
        lab[i, j] = k
        stack, cells = [(i, j)], []
        while stack:
            a, b = stack.pop()
            cells.append((a, b))
            for c, d in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                if (0 <= c < H and 0 <= d < W and ok[c, d] and lab[c, d] < 0
                        and abs(T[c, d] - T[a, b]) <= step):
                    lab[c, d] = k
                    stack.append((c, d))
        comps.append(cells)
    return comps


def _cluster_shades(c, members, dem, to_xy, law_v, report) -> list:
    grid, climb, grade, band = law_v
    outs = [q for q in (_poly(r, to_xy) for r in c.rings) if q is not None]
    if not outs:
        return []
    outline = unary_union(outs)
    x0, y0, x1, y1 = outline.bounds
    xs = np.arange(x0 + 0.5 * grid, x1, grid)
    ys = np.arange(y0 + 0.5 * grid, y1, grid)
    if not len(xs) or not len(ys):
        return []
    import shapely
    X, Y = np.meshgrid(xs, ys)
    inside = shapely.contains_xy(outline, X, Y)
    if not inside.any():
        return []
    G = np.full(X.shape, np.nan)
    G[inside] = _dem_many(dem, X[inside], Y[inside])
    D = float(np.nanmedian(G[inside]))
    high = inside & (G > D + band)
    if not high.any():
        return []
    high_poly = unary_union([box(X[a, b] - 0.5 * grid, Y[a, b] - 0.5 * grid,
                                 X[a, b] + 0.5 * grid, Y[a, b] + 0.5 * grid)
                             for a, b in zip(*np.nonzero(high))]
                            ).buffer(grid, join_style=2)   # the outline's edge cells
    got = []
    for m, origin in members:
        # cheap reject: no part of the member over the candidate ground
        # cheap reject before the file is parsed: a ramp that sinks into
        # the ground is AUTHORED to — some part of it over the candidate
        # ground reaches under its own zero (SPJC's ramp walls run 8.76 m
        # under it); a member with nothing under its zero there is not one
        if not any(float(getattr(p, "base_y", -1e9)) < -band
                   and (not getattr(p, "box", None)
                        or high_poly.intersects(_box_xy(p.box, to_xy)))
                   for p in m.parts):
            continue
        mfoot = unary_union([q for p in m.parts for r in (p.rings or ())
                             for q in [_poly(r, to_xy)] if q is not None])
        if mfoot.is_empty or not mfoot.intersects(box(*outline.bounds)):
            continue
        T = _top_surface(_member_tris(m, origin, to_xy), xs, ys, high)
        ok = high & ~np.isnan(T)
        if not ok.any():
            continue
        for cells in _components(ok, T, grade * grid):
            ii = np.array([a for a, _b in cells])
            jj = np.array([b for _a, b in cells])
            t, gz = T[ii, jj], G[ii, jj]
            sunk = (D + t < gz - band) & (t >= -band)
            over = D + t > gz + band
            # a RAMP: under the ground at one end and over it further on,
            # climbing, and coming down to its own zero (the ramp end's
            # lip, 10-03e's landing band) — a roof's eave never does
            if not (sunk.any() and over.any() and float(t.min()) <= band
                    and float(t.max() - t.min()) >= climb):
                continue
            sq = unary_union([box(X[a, b] - 0.5 * grid, Y[a, b] - 0.5 * grid,
                                  X[a, b] + 0.5 * grid, Y[a, b] + 0.5 * grid)
                              for a, b in cells])
            # the deck's own walls and parapets: a top-surface step breaks
            # the chain at the deck's edge, so the accepted deck is widened
            # by ``_REACH_CELLS`` cells and clipped to the member's
            # footprint over the candidate ground (never the pad's other
            # ground)
            reach = _REACH_CELLS * grid
            q = (sq.buffer(reach, join_style=2)
                 .intersection(mfoot).intersection(high_poly))
            q = q.buffer(0.5 * grid, join_style=2).buffer(
                -0.5 * grid, join_style=2).intersection(mfoot)
            if q.is_empty:
                continue
            got.append(q)
            report.setdefault("ramps", []).append(
                {"cluster": str(c.id), "member": str(m.resource),
                 "cells": len(cells), "sunk_cells": int(sunk.sum()),
                 "area_m2": round(q.area, 1), "datum_est": round(D, 2),
                 "deepest_m": round(float((gz - D - t)[sunk].max()), 2)})
    return got


def sunken_ramp_shades(airport, law, to_xy):
    """The union (planar frame metres) of every sunken ramp's ground of
    ``airport`` (module docstring), or None; memoised per airport."""
    # keyed on what the derivation READS (an airport is ``replace``d
    # between the mint and the census; its partition, clusters and DEM
    # are the same objects)
    key = tuple(getattr(airport, k, None) for k in ("partition", "clusters",
                                                    "dem"))
    for ap, val, rep in _MEMO:
        if len(ap) == len(key) and all(a is b for a, b in zip(ap, key)):
            SUNKEN.clear()
            SUNKEN.update(rep)
            return val
    SUNKEN.clear()
    val = None
    lv = _law(law) if law is not None else (0.0, 0.0, 0.0, 0.0)
    part = getattr(airport, "partition", None)
    cl = getattr(airport, "clusters", None) or ()
    dem = getattr(airport, "dem", None)
    if lv[0] > 0.0 and part is not None and cl and dem is not None:
        by_res: dict[tuple[str, str], list] = {}
        for u in part.units:
            for m in u.members:
                org = getattr(m, "origin", None) or u.anchor
                by_res.setdefault((str(u.id), str(m.resource)), []).append(
                    (m, org))
        polys: list = []
        pad_min = float(law.tables.structures.placement.cluster_pad_min_m2)
        for c in cl:
            # only a cluster that MINTS a pad (``cluster_outlines`` rule 5:
            # walled, over ``cluster_pad_min_m2``) has ground to give back
            if (not getattr(c, "rings", ()) or not getattr(c, "walled", 1)
                    or float(getattr(c, "area_m2", pad_min)) < pad_min):
                continue
            ms = [x for r in c.members
                  for x in by_res.get((str(c.unit), str(r)), ())]
            if ms:
                polys.extend(_cluster_shades(c, ms, dem, to_xy, lv, SUNKEN))
        if polys:
            val = unary_union(polys)
            SUNKEN["area_m2"] = round(val.area, 1)
    SUNKEN["count"] = len(SUNKEN.get("ramps", ()))
    _MEMO.append((key, val, dict(SUNKEN)))
    del _MEMO[:-2]
    return val


def attach_sunken_ramps(airport, law):
    """``airport`` with :attr:`Airport.sunken_ramps` derived — called once
    where the clusters are attached (``pipeline/build``, the replay)."""
    import dataclasses as _dc
    frame = getattr(airport, "frame", None)
    if frame is None or law is None:
        return airport
    return _dc.replace(airport, sunken_ramps=sunken_ramp_shades(
        airport, law, frame.entry()))
