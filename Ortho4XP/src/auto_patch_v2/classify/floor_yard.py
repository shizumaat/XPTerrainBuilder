"""THE FLOOR YARD: A UNIT'S FENCE ON ITS FLOOR STANDS ON THE FLOOR'S GROUND
(#2068; owner sim read 2026-11-14T20:01Z on 1.0.528: "the black fence is
evidence the terrain is flatter for the groundside of the fence where the
road and parking area is, with a steeper embankment on the airside of the
fence dropping down to the service road").

``classify/fence_yard`` reads a unit's fence a storey up beside an UPPER
pad.  The same fence the pack authored at the unit's FLOOR is the same
witness one storey down: its foot is the author's ground (unit zero plus
its base ``y``), and where the natural ground at it stands more than a
band under the floor's, the fence is the edge of a TERRACE at the floor —
the ground it encloses with the unit's floor pad stands on the fence-foot
plane, and the step to the natural ground falls on the fence's far side.

Gates (doubt -> nothing, RULINGS 2026-11-13r):

* F1 the unit has a floor ``t`` (``airport/unit_storey``) and a FLOOR PAD:
  a building cell (no upper pad) whose unit parts stand within
  ``split_level.BAND_M`` of ``t``.
* F2 only the unit's own fences (``EdgeLine.unit``; ``airport/unit_fence``
  admits only a class that stands on its zero).
* F3 a station is a FLOOR station when its base is within ``BAND_M`` of
  ``t``, in a run of them at least ``[edge_lines] min_run_m`` long
  (``fence_yard.run_flags``).
* F4 THE TERRACE WITNESS: a fence line is a witness when the DEM median at
  its floor stations stands more than ``BAND_M`` UNDER the floor pad's own
  DEM median (the fence stands proud of the natural ground: the author's
  floor is a platform built out to it); the witnesses chained within
  ``[edge_lines] host_reach_m`` of one another, one of them within that
  reach of the pad, are the pad's terrace edge.  A fence at grade marks no
  terrace; a fence the natural ground stands over (a cut) is not read
  (13r: the measured class is the fill).
* F5 the plane (``geom/capped_plane``, tilt capped at ``[common]
  pavement_max_grade``) has rms at most ``[edge_lines] step_min_m`` over
  the witness stations.
* F6 AIRSIDE IS KING: the yard is the fence's GROUNDSIDE — cut along the
  witness fences, a piece of the gross yard that meets airside pavement
  (a non-building airside cell) is the fence's airside and keeps its
  ground.  The yard is a late cell, projected after the solve
  (``solve/project_yard``), never a row.

THE REGION is ``fence_yard``'s (flood ∪ pockets ∪ band, cut to the
witness Voronoi, less the stand-off) round the floor pad, with the
witness stations in the upper stations' place.  The pad's evidence
carries the plane, the gross yard and :data:`FLOOR_YARD_KEY` (the floor
``t``); the planar stage hands them to the pad's held block record
(:func:`floor_yard_reads`), whose solved floor is the yard's level."""
from __future__ import annotations

import math
import statistics as _st
import typing as _t

import numpy as np
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from ..geom.capped_plane import capped_plane, plane_at
from ..law import Law
from .evidence import polygon_parts
from .rules import Rules

__all__ = ["FLOOR_YARD_KEY", "floor_yard_reads", "mint_floor_yards"]

#: the floor pad's evidence: the unit floor ``t`` its yard stands over
FLOOR_YARD_KEY = "floor_yard_t"


def floor_yard_reads(cells) -> dict[str, dict[str, _t.Any]]:
    """``{floor pad ref: its yard record}`` (``yard_plane``, ``yard_hull``,
    ``y_p`` = the floor ``t``) for every pad a floor yard was read beside;
    the planar stage stores it on the pad's held block record."""
    from .fence_yard import yard_record_of
    out = {}
    for c in cells:
        ev = c.evidence or {}
        if c.role == "building" and FLOOR_YARD_KEY in ev \
                and (rec := yard_record_of(ev)) is not None:
            out[str(c.ref)] = dict(rec, y_p=float(ev[FLOOR_YARD_KEY]))
    return out


def mint_floor_yards(airport, cells: list, law: Law, rules: Rules, add, lines: list,
                     stats: dict, n: int) -> int:
    """Mint the floor yards of every unit with fences in ``lines`` onto
    ``cells`` (``fence_yard.mint_yard``), counting into ``stats``; returns
    the next yard number."""
    from ..airport.unit_storey import _unit_reads
    from ..law.tables import design as design_law
    from .fence_yard import mint_yard
    from .storey_edge import UPPER_Y_KEY
    part = getattr(airport, "partition", None)
    frame = getattr(airport, "frame", None)
    if part is None or frame is None or getattr(airport, "dem", None) is None:
        return n
    air = unary_union([Polygon(c.ring, c.holes).buffer(0.0) for c in cells
                       if c.side == "airside" and c.role != "building"])
    if air.is_empty:
        return n
    near = air.buffer(float(design_law(law).pad_frontage_m))
    units = {ur.ui: ur for ur in _unit_reads(part, near, frame.entry())}
    for ui in sorted({int(el.unit) for el in lines}):
        ur = units.get(ui)
        if ur is None:
            continue                                                 # F1
        own = [el for el in lines if el.unit == ui]                  # F2
        for k in _floor_pads(cells, ur, UPPER_Y_KEY):
            ref = cells[k].ref
            got = _floor_yard(airport, cells, law, rules, Polygon(cells[k].ring, cells[k].holes),
                              own, ur.t, air)
            if isinstance(got, str):
                if got:
                    stats[f"floor_yard_refused:{ref}"] = got
                continue
            got[2][FLOOR_YARD_KEY] = ur.t
            n = mint_yard(cells, k, got, rules, add, stats, n,
                          (*_yard_keys(), FLOOR_YARD_KEY))
            info = got[2]
            stats[f"floor_yard:{ref}"] = (
                f"tilt {info['yard_tilt']:.4f} rms {info['yard_rms']:.3f} "
                f"witness {info['yard_upper']}/{info['yard_stations']} "
                f"fences {info['yard_fences']} off {info['yard_g6_ratio']:+.2f} m")
    return n


def _yard_keys() -> tuple:
    from .fence_yard import _RATIO_KEY, _YARD_KEYS
    return (*_YARD_KEYS, _RATIO_KEY)


def _floor_pads(cells, ur, upper_key: str) -> list[int]:
    """F1: the indices of the building cells (no upper pad) whose unit
    parts stand at the unit's floor."""
    from ..airport.split_level import BAND_M
    from ..airport.unit_storey import _on
    out = []
    bx0, by0, bx1, by1 = ur.bounds
    for k, c in enumerate(cells):
        if c.role != "building" or upper_key in (c.evidence or {}):
            continue
        xs, ys = [p[0] for p in c.ring], [p[1] for p in c.ring]
        if min(xs) > bx1 or max(xs) < bx0 or min(ys) > by1 or max(ys) < by0:
            continue
        on = _on(ur, Polygon(c.ring, c.holes))
        if on and abs(min(p.base_y for p, _g in on) - ur.t) <= BAND_M:
            out.append(k)
    return sorted(out, key=lambda k: str(cells[k].ref))


def _floor_yard(airport, cells, law, rules, P, own, t: float, air):
    """``(region, gross, evidence)`` of one floor pad's yard, ``""`` where
    no witness fence is tied to it, or the refusal."""
    from ..airport.split_level import BAND_M
    from ..airport.unit_storey import dem_samples
    from .fence_yard import _dem_median, _region, _stations, run_flags
    cfg = rules.edge_lines
    st = _stations(own, float(cfg.station_m))
    if not st:
        return ""
    floor = run_flags(st, [abs(s.base - t) <= BAND_M for s in st], float(cfg.station_m),
                      float(cfg.min_run_m))                                  # F3
    zp = dem_samples(airport.dem, P)
    if not zp:
        return ""
    tied = _witnesses(airport, own, st, floor, P, _st.median(zp), BAND_M,
                      float(cfg.host_reach_m))                               # F4
    if not tied:
        return ""
    up = [f and s.line in tied for s, f in zip(st, floor, strict=True)]
    U = [s for s, u in zip(st, up, strict=True) if u]
    xy = np.array([(s.x, s.y) for s in U], dtype=float).reshape(-1, 2)
    base = np.array([s.base for s in U], dtype=float)
    plane = capped_plane(xy, base, float(law.tables.common.pavement_max_grade))
    res = base - plane_at(plane, xy[:, 0], xy[:, 1])
    rms = float(np.sqrt(np.mean(res ** 2)))
    if rms > float(cfg.step_min_m):
        return f"plane rms {rms:.2f} > {cfg.step_min_m}"                     # F5
    region, gross = _region(cells, law, rules, P, own, st, up, U)
    region, gross = _groundside(region, gross, [own[i] for i in sorted(tied)], air,
                                max(float(rules.cells.snap_grid_m), 0.01))   # F6
    if region.is_empty:
        return "no free groundside ground"
    off = _st.median(_line_dem(airport, st, floor, tied)) - _st.median(zp)
    info = dict(zip(_yard_keys()[:5], (round(v, 6) for v in plane), strict=True))
    info.update(yard_rms=round(rms, 3), yard_stations=len(st), yard_upper=len(U),
                yard_g6_ratio=round(off, 3),
                yard_dem_m=round(_dem_median(airport, region), 2),
                yard_tilt=round(math.hypot(plane[1], plane[2]), 4),
                yard_resid=f"{res.max():+.2f}/{res.min():+.2f}",
                yard_fences=",".join(sorted(own[i].id for i in tied)))
    return region, gross, info


def _line_dem(airport, st, floor, lines) -> list[float]:
    """The DEM at the floor stations of ``lines`` (indices into the unit's
    fences)."""
    from ..airport.dem import dem_z_many
    pick = [s for s, f in zip(st, floor, strict=True) if f and s.line in lines]
    if not pick:
        return []
    z = dem_z_many(airport.dem, np.array([s.x for s in pick]), np.array([s.y for s in pick]))
    return [float(v) for v in z if math.isfinite(v)]


def _witnesses(airport, own, st, floor, P, zp: float, band: float, reach: float) -> set[int]:
    """F4: the witness fences (indices into ``own``) chained to ``P``."""
    wit = set()
    for i in range(len(own)):
        z = _line_dem(airport, st, floor, {i})
        if z and zp - _st.median(z) > band:
            wit.add(i)
    geo = {i: LineString(own[i].points) for i in wit}
    tied = {i for i in wit if geo[i].distance(P) <= reach}
    grow = True
    while grow:
        more = {i for i in wit - tied if any(geo[i].distance(geo[j]) <= reach for j in tied)}
        grow = bool(more)
        tied |= more
    return tied


def _groundside(region, gross, fences, air, eps: float):
    """F6: ``region`` and ``gross`` less every piece of the gross yard, cut
    along the witness ``fences``, that meets airside pavement ``air``."""
    cut = unary_union([LineString(tuple(el.points) + ((el.points[0],) if el.closed else ()))
                       for el in fences]).buffer(eps)
    bad = [g for g in polygon_parts(gross.difference(cut)) if g.distance(air) <= eps]
    if not bad:
        return region, gross
    drop = unary_union(bad).buffer(eps)
    return region.difference(drop), gross.difference(drop)
