"""THE FENCE YARD: A UNIT'S FENCE STANDS ON THE GROUND IT ENCLOSES (spec
``2068-fence-grade-spec-A2.md`` §1, F2; owner sim read #2068
2026-11-14T14:44Z: "The tower area that's at the higher level is larger,
with a short steep embankment down to the apron, the fence marks the
transition").

A wire fence, low barrier or wall-on-its-zero the pack authored inside a
unit's own frame (``airport/unit_fence``: ``EdgeLine.unit``) carries the
author's ground along its foot.  Where such a fence stands a storey up
beside an UPPER PAD of the same unit (``classify/storey_edge.arm_storeys``),
the ground it encloses is the FENCE-FOOT PLANE; this module mints that
ground as late cells, called ONCE right after ``edge_line_mint``.

Gates (doubt -> nothing, RULINGS 2026-11-13r):

* G1 an upper pad already read; none -> nothing is read.
* G2 only the fences of that pad's own unit.
* G3 class in ``line_solidity.ON_TOP`` (``airport/unit_fence`` admits no
  other).
* G4 a station every ``[edge_lines] station_m`` is UPPER when its base
  stands at or over ``t + (y_p - t) / 2``; upper runs at least
  ``min_run_m`` long carry the plane, which needs rank 3.
* G5 the plane's rms over the upper stations is at most ``step_min_m``;
  the plane's tilt is capped at ``[common] pavement_max_grade`` (spec 2068
  A3 R2) and the rms read on the capped plane.
* G6' (spec 2068 A3 R1, replacing A2's G6) the ground confirms the fence's
  foot AT THE FENCE'S OWN STATIONS: with U the upper stations and F the
  stations of the unit's fences whose base is within
  ``split_level.BAND_M`` of the floor ``t``, the DEM's rise
  ``median DEM(U) - median DEM(F)`` is between half and one and a half
  times the fence's ``median base(U) - median base(F)``.  F short of
  ``min_run_m / station_m`` stations reads T4's airside ground
  (``storey_edge.UPPER_AIR_Z_KEY``) and ``t`` instead; NaN refuses.
* G7 airside is king: a yard is a LATE cell (``model.planar.is_late_ref``),
  projected after the solve (``solve/project_strip``), never a row.

THE REGION = (flood ∪ pockets ∪ the upper fence's base band) ∩ the upper
Voronoi − the §52 stand-off.  The FLOOD is the free ground connected to
within ``host_reach_m`` of the pad, inside the convex hull of the upper
stations and the pad grown by ``host_reach_m``; it crosses no unit fence and no
standing cell but a groundside road-family one.  A POCKET is a face of the
unit's fence runs closed by one chord per run end (to the nearest fence
vertex not on its own run) that is fenced on :data:`_POCKET_FENCED` of its
outline and shares ``min_run_m`` of upper fence with the flood or an
accepted pocket.  The UPPER VORONOI is the ground nearer an upper station
than any other.  Each piece is ``groundside_pavement``, ref
``fenceyard:<k>:<pad ref>``, its evidence the plane (``YARD_*`` keys)."""
from __future__ import annotations

import dataclasses as _dc
import math
import statistics as _st
import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString, MultiPoint, Polygon
from shapely.ops import polygonize, unary_union

from ..geom.capped_plane import capped_plane, plane_at
from ..law import Law
from ..law.tables import road_family_roles
from ..model.planar import FENCE_YARD_PREFIX
from .edge_line_mint import STRIP_ROLE, standing_keep_off
from .evidence import polygon_parts
from .rules import Rules

__all__ = ["mint_fence_yards", "yard_record_of", "YARD_HULL_KEY"]

#: the share of a pocket's outline its fence must stand on (spec F2 (3))
_POCKET_FENCED = 0.75

#: the yard's evidence keys of its plane ``(z0, gx, gy, x0, y0)``, in the
#: unit's authored ``y`` (the fence-foot base at ``(x, y)``)
_YARD_KEYS = ("yard_z0", "yard_gx", "yard_gy", "yard_x0", "yard_y0")

#: spec 2068 A3 R5: the GROSS yard on the pad's evidence, as rings
#: ``((exterior, *holes), ...)`` — the ground the yard's roads stand on
YARD_HULL_KEY = "yard_hull"
#: spec 2068 A3 R1: the G6' ratio, on the evidence
_RATIO_KEY = "yard_g6_ratio"


class _Station(_t.NamedTuple):
    x: float
    y: float
    base: float
    line: int
    s: float


def _yard_plane_of(evidence) -> "tuple[float, float, float, float, float] | None":
    """The fence-foot plane a yard cell's (or its upper pad's) ``evidence``
    carries, or ``None``."""
    ev = evidence or {}
    if not all(k in ev for k in _YARD_KEYS):
        return None
    return tuple(float(ev[k]) for k in _YARD_KEYS)  # type: ignore[return-value]


def yard_record_of(evidence) -> "dict[str, _t.Any] | None":
    """What an upper pad's ``evidence`` hands its level's landing record
    (``planar/group_up``): ``yard_plane``, ``yard_hull`` and
    ``yard_g6_ratio``, or ``None`` without a yard."""
    pl = _yard_plane_of(evidence)
    if pl is None:
        return None
    ev = evidence or {}
    return {"yard_plane": pl, "yard_hull": tuple(ev.get(YARD_HULL_KEY, ())),
            "yard_g6_ratio": float(ev.get(_RATIO_KEY, math.nan))}


def mint_fence_yards(airport, cells: list, law: Law, rules: Rules, add) -> dict[str, _t.Any]:
    """Mint the fence yards onto ``cells`` through ``add`` (the
    classifier's cell constructor) -- an upper pad's (this module) and a
    floor's (``classify/floor_yard``); returns the counts."""
    from .floor_yard import mint_floor_yards
    from .storey_edge import UPPER_AIR_Z_KEY, UPPER_FLOOR_KEY, UPPER_UNIT_KEY, UPPER_Y_KEY
    stats: dict[str, _t.Any] = {"fence_yards": 0, "fence_yard_m2": 0.0}
    pads = [(k, c.ref, Polygon(c.ring, c.holes), c.evidence) for k, c in enumerate(cells)
            if c.role == "building" and UPPER_Y_KEY in (c.evidence or {})]
    lines = [el for el in (getattr(airport, "edge_lines", ()) or ())
             if getattr(el, "unit", None) is not None and len(el.points) >= 2]
    if not lines:
        return stats                                             # G1
    n = 0
    for k, ref, P, ev in sorted(pads, key=lambda r: r[1]):
        ui = int(ev[UPPER_UNIT_KEY])
        own = [el for el in lines if el.unit == ui]              # G2
        got = _yard(airport, cells, law, rules, P, own, float(ev[UPPER_Y_KEY]),
                    float(ev[UPPER_FLOOR_KEY]), float(ev.get(UPPER_AIR_Z_KEY, math.nan)))
        if isinstance(got, str):
            stats[f"fence_yard_refused:{ref}"] = got
            continue
        n = mint_yard(cells, k, got, rules, add, stats, n, (*_YARD_KEYS, _RATIO_KEY))
        info = got[2]
        stats[f"fence_yard:{ref}"] = (f"tilt {info['yard_tilt']:.4f} rms {info['yard_rms']:.3f} "
                                      f"upper {info['yard_upper']}/{info['yard_stations']} "
                                      f"ground ratio {info['yard_g6_ratio']:.3f} "
                                      f"yard dem {info['yard_dem_m']:.2f}")
    mint_floor_yards(airport, cells, law, rules, add, lines, stats, n)
    return stats


def mint_yard(cells: list, k: int, got, rules: Rules, add, stats: dict, n: int,
              pad_keys: tuple) -> int:
    """Mint one pad's yard ``got`` (``(region, gross, evidence)``) beside
    ``cells[k]``; the pad carries ``pad_keys`` of the evidence and the
    gross yard (A3 R5) -- the planar front reads no late cell.  Returns
    the next yard number."""
    region, gross, info = got
    ref = cells[k].ref
    cells[k] = _dc.replace(cells[k], evidence=dict(
        cells[k].evidence, **{key: info[key] for key in pad_keys},
        **{YARD_HULL_KEY: _rings(gross)}))
    for part in polygon_parts(region):
        if part.area < rules.cells.min_area_m2:
            continue
        add(STRIP_ROLE, f"{FENCE_YARD_PREFIX}:{n}:{ref}", part, "fence_yard", None, None,
            dict(info, yard_pad=ref))
        n += 1
        stats["fence_yards"] += 1
        stats["fence_yard_m2"] += round(part.area, 1)
    return n


def _yard(airport, cells, law, rules, P, own, y_p, t, za):
    """``(region, gross yard, evidence)`` of one upper pad's yard, or the
    refusal."""
    cfg = rules.edge_lines
    st = _stations(own, float(cfg.station_m))
    if not st:
        return "no unit fence"
    cut = t + 0.5 * (y_p - t)
    up = run_flags(st, [s.base >= cut for s in st], float(cfg.station_m), float(cfg.min_run_m))
    U = [s for s, u in zip(st, up, strict=True) if u]                 # G4
    xy = np.array([(s.x, s.y) for s in U], dtype=float).reshape(-1, 2)
    if len(U) < 3 or np.linalg.matrix_rank(np.column_stack([np.ones(len(U)), xy])) < 3:
        return "no rank-3 upper run"
    plane = capped_plane(xy, np.array([s.base for s in U]),
                         float(law.tables.common.pavement_max_grade))       # R2
    res = np.array([s.base for s in U]) - plane_at(plane, xy[:, 0], xy[:, 1])
    rms = float(np.sqrt(np.mean(res ** 2)))
    if rms > float(cfg.step_min_m):
        return f"plane rms {rms:.2f} > {cfg.step_min_m}"         # G5
    ratio = _ground_ratio(airport, st, up, t, za, float(cfg.min_run_m) / float(cfg.station_m))
    if not 0.5 <= ratio <= 1.5:                                  # G6' (NaN refuses)
        return f"ground ratio {ratio:.2f} outside 0.5-1.5"
    region, gross = _region(cells, law, rules, P, own, st, up, U)
    if region.is_empty:
        return "no free ground"
    info = dict(zip(_YARD_KEYS, (round(v, 6) for v in plane), strict=True))
    info.update(yard_rms=round(rms, 3), yard_stations=len(st), yard_upper=len(U),
                yard_g6_ratio=round(ratio, 3),
                yard_dem_m=round(_dem_median(airport, region), 2),
                yard_tilt=round(math.hypot(plane[1], plane[2]), 4),
                yard_resid=f"{res.max():+.2f}/{res.min():+.2f}",
                yard_fences=",".join(sorted({el.id for el in own})))
    return region, gross, info


def _rings(g) -> tuple:
    """``g``'s parts as ``(exterior, *holes)`` rings of rounded points."""
    def ring(r):
        return tuple((round(x, 3), round(y, 3)) for x, y in r.coords)
    return tuple((ring(p.exterior), *(ring(h) for h in p.interiors))
                 for p in polygon_parts(g))


def _ground_ratio(airport, st: list[_Station], up: list[bool], t: float, za: float,
                  f_min: float) -> float:
    """G6' (spec 2068 A3 R1): the DEM's rise from the fence's floor
    stations to its upper ones over the fence's own (module doc)."""
    from ..airport.dem import dem_z_many
    from ..airport.split_level import BAND_M
    dem = getattr(airport, "dem", None)
    if dem is None or not st:
        return math.nan
    base = np.array([s.base for s in st], dtype=float)
    z = dem_z_many(dem, np.array([s.x for s in st]), np.array([s.y for s in st]))
    u = np.asarray(up, dtype=bool) & np.isfinite(z)
    f = (np.abs(base - t) <= BAND_M) & np.isfinite(z)
    if not u.any():
        return math.nan
    if f.sum() >= f_min:
        dz, db = float(np.median(z[f])), float(np.median(base[f]))
    else:
        dz, db = za, t
    rise = float(np.median(base[u])) - db
    return (float(np.median(z[u])) - dz) / rise if rise > 0.0 else math.nan


def _stations(lines, step: float) -> list[_Station]:
    """Stations every ``step`` along each unit line (both ends kept), the
    fence-foot base interpolated between its columns."""
    out: list[_Station] = []
    for li, el in enumerate(lines):
        pts = np.array(el.points, dtype=float)
        base = np.array(el.base_ys, dtype=float)
        if el.closed:
            pts, base = np.vstack([pts, pts[:1]]), np.append(base, base[0])
        s = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])
        if s[-1] <= 0.0 or len(base) != len(pts):
            continue
        k = max(1, int(math.ceil(s[-1] / step)))
        for q in np.linspace(0.0, s[-1], k + 1):
            out.append(_Station(float(np.interp(q, s, pts[:, 0])),
                                float(np.interp(q, s, pts[:, 1])),
                                float(np.interp(q, s, base)), li, float(q)))
    return out


def run_flags(st: list[_Station], flags: list[bool], step: float, min_run: float
              ) -> list[bool]:
    """G4: a station keeps its ``flags`` (upper: its base at or over the
    cut; a floor yard's: at the floor) when it lies in a run of
    consecutive flagged stations of one line at least ``min_run`` long."""
    out = [False] * len(st)
    i = 0
    while i < len(st):
        if not flags[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(st) and flags[j + 1] and st[j + 1].line == st[i].line \
                and st[j + 1].s - st[j].s <= 1.5 * step:
            j += 1
        if st[j].s - st[i].s >= min_run:
            out[i:j + 1] = [True] * (j + 1 - i)
        i = j + 1
    return out


def _region(cells, law, rules, P, own, st, up, U) -> "tuple[Polygon, Polygon]":
    """``(region, gross)``: (flood ∪ pockets ∪ base band) ∩ upper Voronoi
    − stand-off, and the GROSS yard (A3 R5): the flood's passable ground
    with its road cells, the pockets and the band, cut to the upper
    Voronoi, before the cells and the stand-off are taken out."""
    cfg = rules.edge_lines
    reach = float(cfg.host_reach_m)
    eps = max(float(rules.cells.snap_grid_m), 0.01)
    fence = [LineString(list(el.points) + ([el.points[0]] if el.closed else []))
             for el in own]
    barrier = unary_union([f.buffer(eps) for f in fence])
    hull = unary_union([MultiPoint([(s.x, s.y) for s in U]), P.buffer(reach)]).convex_hull
    flood, passable = _flood(cells, law, P, hull, barrier, reach)
    upper_fence = _upper_fence(st, up)
    hw = max(max(float(el.half_width_m) for el in own),
             float(law.tables.emit.identity.min_distinct_spacing_m))
    pockets = _pockets(own, fence, flood, upper_fence, float(cfg.min_run_m), hw)
    band = upper_fence.buffer(hw, cap_style="flat") if not upper_fence.is_empty else Polygon()
    vor = _upper_voronoi(st, up, hull)
    gross = unary_union([passable, pockets, band]).intersection(vor)
    region = unary_union([flood, pockets, band]).intersection(vor)
    region = region.difference(standing_keep_off(cells, law))
    grid = rules.cells.snap_grid_m
    return shapely.set_precision(region, grid), shapely.set_precision(gross, grid)


def _flood(cells, law, P, hull, barrier, reach: float):
    """``(flood, passable)``: the free ground inside ``hull`` connected to
    within ``reach`` of the pad ``P`` — no path crosses ``barrier`` or a
    standing cell other than a groundside road-family one; the cells
    themselves are not taken — and the same ground WITH its road cells."""
    roads = set(road_family_roles(law))
    block = [Polygon(c.ring, c.holes).buffer(0.0) for c in cells
             if not (c.side == "groundside" and c.role in roads)]
    passable = hull.difference(unary_union(block + [barrier]))
    near = [g for g in polygon_parts(passable) if g.distance(P) <= reach]
    if not near:
        return Polygon(), Polygon()
    taken = unary_union([Polygon(c.ring, c.holes).buffer(0.0) for c in cells])
    near_u = unary_union(near)
    return near_u.difference(taken), near_u


def _upper_fence(st: list[_Station], up: list[bool]):
    """The fence between consecutive upper stations of one line."""
    segs = [LineString([(a.x, a.y), (b.x, b.y)])
            for a, b, ua, ub in zip(st, st[1:], up, up[1:], strict=False)
            if ua and ub and a.line == b.line and (a.x, a.y) != (b.x, b.y)]
    return unary_union(segs) if segs else LineString()


def _chords(own, fence) -> list[LineString]:
    """One chord per open run end, to the nearest fence vertex not on its
    own run (none where no other run stands)."""
    out = []
    for i, el in enumerate(own):
        if el.closed:
            continue
        others = [p for j, o in enumerate(own) if j != i for p in o.points]
        if not others:
            continue
        for end in (el.points[0], el.points[-1]):
            q = min(others, key=lambda p: (math.dist(p, end), p))
            if math.dist(q, end) > 0.0:
                out.append(LineString([end, q]))
    return out


def _pockets(own, fence, flood, upper_fence, min_run: float, hw: float):
    """The pockets (module doc), grown from the flood to a fixpoint."""
    if upper_fence.is_empty:
        return Polygon()
    net = unary_union(fence + _chords(own, fence))
    faces = [f for f in polygonize(net) if f.area > 0.0]
    fence_u = unary_union(fence).buffer(hw * 0.1)
    up_u = upper_fence.buffer(hw * 0.1)
    fenced = [f for f in faces
              if f.exterior.intersection(fence_u).length >= _POCKET_FENCED * f.exterior.length]
    got, have = [], flood
    while True:
        more = [f for f in fenced if f not in got and not have.is_empty
                and f.exterior.intersection(up_u).intersection(have.buffer(2.0 * hw)).length
                >= min_run]
        if not more:
            return unary_union(got) if got else Polygon()
        got.extend(more)
        have = unary_union([have, *more])


def _upper_voronoi(st: list[_Station], up: list[bool], hull):
    """The ground inside ``hull`` nearer an upper station than any other."""
    seen: dict[tuple[float, float], bool] = {}
    for s, u in zip(st, up, strict=True):
        key = (round(s.x, 3), round(s.y, 3))
        seen[key] = seen.get(key, False) or u
    if not any(seen.values()):
        return Polygon()
    if all(seen.values()):
        return hull
    keys = list(seen)
    cells = shapely.voronoi_polygons(MultiPoint(keys), extend_to=hull, ordered=True)
    keep = [g for g, k in zip(cells.geoms, keys, strict=True) if seen[k]]
    return unary_union(keep).intersection(hull)


def _dem_median(airport, region) -> float:
    """The DEM median over ``region`` (NaN where none)."""
    from ..airport.unit_storey import dem_samples
    zs = dem_samples(getattr(airport, "dem", None), region)
    return float(_st.median(zs)) if zs else math.nan
