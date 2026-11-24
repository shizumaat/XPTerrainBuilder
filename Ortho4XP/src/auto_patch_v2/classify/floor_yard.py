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
  ``split_level.BAND_M`` of ``t``.  The yard is read here; it STANDS only
  where its level exists (spec 2068 A4 F1'): the planar stage stores the
  record on a held, non-conforming pad only, drops the yard cells of a
  pad with no record before pass C (``planar/overlay``,
  ``fence_yard_no_level``), and ``model/yard_run.yard_records``
  keeps a record only while a yard face of its pad stands in the map.
* F2 only the unit's own fences (``EdgeLine.unit``; ``airport/unit_fence``
  admits only a class that stands on its zero).
* F3 a station is a FLOOR station when its base is within ``BAND_M`` of
  ``t``, in a run of them at least ``[edge_lines] min_run_m`` long
  (``fence_yard.run_flags``).
* F4' THE TERRACE IS WITNESSED AT THE FENCE (spec 2068 A4; measured KMCI
  building43: a rail ring on the rim of a pad whose ground rises 3.2 m
  along its 176 m stood level with the pad ground beside it, yet 1.5 m
  under the whole pad's median): a fence line is a witness when the DEM
  median at its floor stations stands more than ``BAND_M`` under the DEM
  median of the pad's FACING GROUND -- the part of the floor pad within
  d(line, pad) + 2 ``[edge_lines] host_reach_m`` of the line, read with
  ``unit_storey.dem_samples`` at 1 m (empty, or no finite sample: no
  witness).  Read along the chain: the lines within ``host_reach_m`` of
  the pad first, then only lines within that reach of a tied line.  A
  fence at grade marks no terrace; a fence the natural ground stands over
  (a cut) is not read (13r: the measured class is the fill).  Where floor
  lines stand within reach and none is a witness the refusal is named
  (``no terrace at the fence (local drop <x> m)``).  The stat's "off" is
  the weakest tied line's fence DEM minus its facing ground's.
* F5 the plane (``geom/capped_plane``, tilt capped at ``[common]
  pavement_max_grade``) has rms at most ``[edge_lines] step_min_m`` over
  the witness stations.
* F6 AIRSIDE IS KING: the yard is the fence's GROUNDSIDE — cut along the
  witness fences, a piece of the gross yard that meets airside pavement
  (a non-building airside cell) is the fence's airside and keeps its
  ground.  The yard is a late cell, projected after the solve
  (``solve/project_yard``), never a row.
* F7 THE YARD IS ITS FILL (#2068 follow-up, measured KMCI building43: the
  plane cut a 1.5 m bank on 233/630 of its edge samples): the fence
  witnesses a terrace only where the terrace is a fill, so the part of the
  yard (and of its gross) where the DEM stands more than ``BAND_M`` OVER
  the yard plane -- read in the DEM frame as the pad's DEM median plus the
  plane over the floor ``t``, an ESTIMATE of the level (``project_yard``
  lands on the solved level, known only after the solve) -- is
  trimmed out; what the trim severs from the witness fences (farther than
  one DEM sample from them) is dropped with it, and no fill left at the
  fence is no yard.
* F8 NO SLIVERS (measured HECA building155 three slivers of 30 m2; LOWS
  building17 67 of 1-13 m2 along ~1 km of fence): a yard piece under
  ``[edge_lines] yard_piece_min_m2`` or nowhere ``yard_piece_min_width_m``
  wide (its inward buffer by half that is empty) terraces nothing a pilot
  could read and leaves its ground.

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
import shapely
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
                f"fences {info['yard_fences']} off {info['yard_g6_ratio']:+.2f} m "
                f"(local drops {info['yard_drops']} m)")
    return n


def _yard_keys() -> tuple:
    from .fence_yard import _RATIO_KEY, _YARD_KEYS
    return (*_YARD_KEYS, _RATIO_KEY)


def _floor_pads(cells, ur, upper_key: str) -> list[int]:
    """F1: the indices of the building cells (no upper pad) whose unit
    parts stand at the unit's floor."""
    from shapely.strtree import STRtree

    from ..airport.split_level import BAND_M
    out = []
    bx0, by0, bx1, by1 = ur.bounds
    # the unit's parts by box (#2206: ``unit_storey._on`` asked every part
    # of the unit of every building cell, 5.5 M intersects at HECA)
    tree = STRtree([g for _p, g in ur.parts]) if ur.parts else None
    for k, c in enumerate(cells):
        if c.role != "building" or upper_key in (c.evidence or {}):
            continue
        xs, ys = [p[0] for p in c.ring], [p[1] for p in c.ring]
        if min(xs) > bx1 or max(xs) < bx0 or min(ys) > by1 or max(ys) < by0:
            continue
        on = _on_near(ur, tree, Polygon(c.ring, c.holes))
        if on and abs(min(p.base_y for p, _g in on) - ur.t) <= BAND_M:
            out.append(k)
    return sorted(out, key=lambda k: str(cells[k].ref))


def _on_near(ur, tree, P) -> list:
    """``unit_storey._on(ur, P)`` over the parts whose box meets ``P``'s
    (no other part can meet ``P``), in the unit's part order."""
    if tree is None:
        return []
    near = sorted(int(i) for i in tree.query(P))
    return [(p, g) for p, g in (ur.parts[i] for i in near) if g.intersects(P)
            and g.intersection(P).area >= 0.5 * g.area]


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
    tied, drops = _witnesses(airport, own, st, floor, P, BAND_M,
                             float(cfg.host_reach_m))                        # F4'
    if not tied:
        return _no_terrace(drops)
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
    witness = unary_union([LineString(own[i].points) for i in sorted(tied)])
    region, gross, cut_m2 = _trim_to_fill(airport.dem, region, gross, plane,
                                          _st.median(zp) - t, witness, BAND_M)  # F7
    if region.is_empty:
        return "no fill at the witness fence"
    region = _min_pieces(region, float(cfg.yard_piece_min_m2),
                         float(cfg.yard_piece_min_width_m))                # F8
    if region.is_empty:
        return "no yard piece wide enough"
    off = -min(drops[i] for i in tied)            # the weakest tied line's fence - facing
    info = dict(zip(_yard_keys()[:5], (round(v, 6) for v in plane), strict=True))
    info.update(yard_rms=round(rms, 3), yard_stations=len(st), yard_upper=len(U),
                yard_g6_ratio=round(off, 3),
                yard_dem_m=round(_dem_median(airport, region), 2),
                yard_tilt=round(math.hypot(plane[1], plane[2]), 4),
                yard_resid=f"{res.max():+.2f}/{res.min():+.2f}",
                yard_fences=",".join(sorted(own[i].id for i in tied)),
                yard_drops="/".join(f"{drops[i]:+.2f}" for i in
                                    sorted(tied, key=lambda i: -drops[i])),
                yard_cut_m2=round(cut_m2, 1))
    return region, gross, info


#: the trim's DEM read: at least this fine, at most ~this many samples
_TRIM_STEP_M, _TRIM_MAX_SAMPLES = 2.0, 40000


def _trim_to_fill(dem, region, gross, plane, lift: float, witness, band: float):
    """F7: ``(region, gross, m2 trimmed off region)`` less the ground where
    the DEM stands more than ``band`` over the yard plane (``plane`` +
    ``lift`` in the DEM frame), read on a square grid; a region piece left
    farther than one grid step from ``witness`` goes too, and the gross
    keeps only what meets the region left."""
    from ..airport.dem import dem_z_many
    x0, y0, x1, y1 = gross.union(region).bounds
    h = max(_TRIM_STEP_M, math.sqrt(max((x1 - x0) * (y1 - y0), 1.0) / _TRIM_MAX_SAMPLES))
    xs, ys = np.meshgrid(np.arange(x0 + 0.5 * h, x1, h), np.arange(y0 + 0.5 * h, y1, h))
    xs, ys = xs.ravel(), ys.ravel()
    with np.errstate(invalid="ignore"):
        over = dem_z_many(dem, xs, ys) - (plane_at(plane, xs, ys) + lift) > band
    if not over.any():
        return region, gross, 0.0
    cut = shapely.union_all(shapely.box(xs[over] - 0.5 * h, ys[over] - 0.5 * h,
                                        xs[over] + 0.5 * h, ys[over] + 0.5 * h))
    keep = []
    for g in polygon_parts(region):
        if not g.intersects(cut):
            keep.append(g)                     # a piece the trim leaves whole stays whole
            continue
        keep += [r for r in polygon_parts(g.difference(cut)) if r.distance(witness) <= h]
    if not any(g.distance(witness) <= h for g in keep):
        keep = []                              # no fill left at the witness fence
    left = unary_union(keep) if keep else Polygon()
    gross = unary_union([g for g in polygon_parts(gross.difference(cut))
                         if g.distance(left) <= h]) if keep else Polygon()
    return left, gross, float(region.area - left.area)


def _min_pieces(region, min_m2: float, min_width_m: float):
    """F8: ``region`` less every piece under ``min_m2`` or nowhere
    ``min_width_m`` wide."""
    keep = [g for g in polygon_parts(region)
            if g.area >= min_m2 and not g.buffer(-0.5 * min_width_m).is_empty]
    return unary_union(keep) if keep else Polygon()


def _line_dem(airport, st, floor, lines) -> list[float]:
    """The DEM at the floor stations of ``lines`` (indices into the unit's
    fences)."""
    from ..airport.dem import dem_z_many
    pick = [s for s, f in zip(st, floor, strict=True) if f and s.line in lines]
    if not pick:
        return []
    z = dem_z_many(airport.dem, np.array([s.x for s in pick]), np.array([s.y for s in pick]))
    return [float(v) for v in z if math.isfinite(v)]


def _witnesses(airport, own, st, floor, P, band: float, reach: float
               ) -> tuple[set[int], dict[int, float]]:
    """F4': ``(tied, drops)`` -- the witness fences (indices into ``own``)
    chained to ``P``, and the local drop of every line tested (its facing
    ground's DEM median minus its floor stations' DEM median).  Evaluated
    along the chain: the roots within ``reach`` of the pad first, then only
    lines within ``reach`` of a tied line."""
    geo = {i: LineString(own[i].points) for i in range(len(own))}
    drops: dict[int, float] = {}
    tested: set[int] = set()

    def witness(i: int) -> bool:
        if i not in tested:
            tested.add(i)
            d = _local_drop(airport, st, floor, i, geo[i], P, reach)
            if d is not None:
                drops[i] = d
        return drops.get(i, math.nan) > band

    tied = {i for i in geo if geo[i].distance(P) <= reach and witness(i)}
    grow = set(tied)
    while grow:
        grow = {i for i in geo if i not in tied and i not in tested
                and any(geo[i].distance(geo[j]) <= reach for j in tied) and witness(i)}
        tied |= grow
    return tied, drops


def _local_drop(airport, st, floor, i: int, line, P, reach: float) -> "float | None":
    """F4': the DEM median of ``P``'s facing ground (the pad within
    d(line, pad) + 2 ``reach`` of the line, 1 m grid) minus the DEM median
    at line ``i``'s floor stations; ``None`` where the line has no floor
    station, NaN where the facing ground is empty or no sample is finite."""
    from ..airport.unit_storey import dem_samples
    z = _line_dem(airport, st, floor, {i})
    if not z:
        return None
    facing = P.intersection(line.buffer(line.distance(P) + 2.0 * reach))
    zf = dem_samples(airport.dem, facing, step=1.0) if not facing.is_empty else []
    return _st.median(zf) - _st.median(z) if zf else math.nan


def _no_terrace(drops: dict[int, float]) -> str:
    """The F4' refusal where a floor line stands within reach of the pad
    and none is a witness (``""`` where no line was tested)."""
    if not drops:
        return ""
    got = [d for d in drops.values() if math.isfinite(d)]
    lo, hi = (min(got), max(got)) if got else (math.nan, math.nan)
    x = "n/a" if not got else f"{lo:+.2f}" if hi - lo < 0.005 else f"{lo:+.2f}…{hi:+.2f}"
    return f"no terrace at the fence (local drop {x} m)"


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
