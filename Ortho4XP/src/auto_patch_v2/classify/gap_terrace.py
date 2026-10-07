"""THE TERRACE INSIDE A GAP PIECE (spec §55 (2)-(3); owner RULINGS
2026-10-04u "it terraces inside the piece", 2026-10-06d "a lot terrace by
the road, a capped ramp to the apron").

PURE GEOMETRY, ONE derivation site: ``(piece, stations, law, rules) ->
parts``.  A STATION is a point of a standing ring beside the piece with the
level the earlier stages gave it — a constant; the caller reads them
(``pipeline/late_stage.late_stations``).  Nothing here reads a DEM, a map or
an airport.

THE STEP CUT (04u).  Two stations are CONSISTENT when the cap can join them
over their distance (:func:`consistent`).  The stations are grouped greedily
into pairwise-consistent LEVEL GROUPS (:func:`level_groups`); every point of
the piece belongs to the group of its nearest station (a Voronoi partition);
a candidate under the mint's own floors is merged into its longest
neighbour and its stations are REPORTED; a KNIFE of ground
(:func:`knife_m`) stands between two parts of different groups.

THE LOT CUT (06d).  Inside a part that meets a ROAD and an APRON at
different levels, the lot is where the road's level, carried flat across,
can still be reached from the apron at the cap; the rest is the ramp.  The
two share a BREAKLINE (one shape, no step).  A part that meets roads only is
one lot.

The counterpart of ``planar/pad_terrace`` and ``planar/pad_blocks`` for a
piece whose neighbours are already solved; it shares their vocabulary and
calls neither."""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
import shapely
from scipy.spatial import cKDTree
from shapely.geometry import MultiPoint, Polygon
from shapely.strtree import STRtree

from ..law import Law
from .evidence import polygon_parts

__all__ = ["Station", "Part", "TerraceCut", "knife_m", "consistent",
           "level_groups", "terrace_cut", "ROAD", "APRON", "PAD"]

ROAD, APRON, PAD = "road", "apron", "pad"


@_dc.dataclass(frozen=True)
class Station:
    """A point on a standing ring beside the piece (spec §55 (1))."""

    xy: tuple[float, float]
    z: float
    cls: str                 #: road | apron | pad | lot | band | structure
    cap: float               #: the tighter of the piece's cap and the ring's
    knife: float = 0.0       #: the pad set-back for a pad, else 0
    ring: str = ""           #: ``role:ref`` of the ring, for the report


@_dc.dataclass(frozen=True)
class Part:
    """One part of a cut piece.  ``suffix`` is appended to the piece's ref
    (``""`` = the piece uncut); ``kind`` is what
    ``model.planar.gap_part_kind`` reads back from it."""

    poly: Polygon
    suffix: str
    kind: str | None         #: "step" | "lot" | "ramp" | None
    group: int
    stations: tuple[int, ...]


@_dc.dataclass(frozen=True)
class TerraceCut:
    parts: tuple[Part, ...]
    groups: tuple[tuple[int, ...], ...]
    knives: int              #: pairs of parts a knife strip separates
    merged: tuple[dict, ...]  #: stations whose part the floors merged away
    dropped_m2: float = 0.0  #: area the knife left under the floors


def knife_m(law: Law) -> float:
    """THE KNIFE between two parts at different levels (spec §55 (2) 4):
    wide enough that the two sides are two SHAPES and their rims two NODES,
    narrow enough that the step is a DECLARED gap joint."""
    return float(law.tables.emit.terrace.separation_m) \
        + 0.5 * float(law.tables.emit.identity.min_distinct_spacing_m)


def consistent(s: Station, t: Station) -> bool:
    """Can the cap join ``s`` and ``t`` over their plan distance?"""
    d = math.dist(s.xy, t.xy)
    return abs(s.z - t.z) <= min(s.cap, t.cap) * max(0.0, d - s.knife - t.knife)


def level_groups(stations: _t.Sequence[Station]) -> list[list[int]]:
    """THE LEVEL GROUPS, deterministic: stations in ``(z, x, y)`` order, each
    joining the FIRST group it is consistent with every member of."""
    order = sorted(range(len(stations)),
                   key=lambda i: (stations[i].z, *stations[i].xy, i))
    xy = np.array([s.xy for s in stations], dtype=float).reshape(-1, 2)
    z = np.array([s.z for s in stations], dtype=float)
    cap = np.array([s.cap for s in stations], dtype=float)
    kn = np.array([s.knife for s in stations], dtype=float)
    groups: list[list[int]] = []
    for i in order:
        for g in groups:
            m = np.asarray(g)
            d = np.hypot(xy[m, 0] - xy[i, 0], xy[m, 1] - xy[i, 1])
            ok = np.abs(z[m] - z[i]) <= np.minimum(cap[m], cap[i]) \
                * np.maximum(0.0, d - kn[m] - kn[i])
            if bool(ok.all()):
                g.append(i)
                break
        else:
            groups.append([i])
    return groups


def _key(p: Polygon) -> tuple:
    return (-round(p.area), round(p.bounds[0], 2), round(p.bounds[1], 2))


def _under_floor(p: Polygon, min_m2: float, lane: float) -> bool:
    return p.area < min_m2 or p.buffer(-0.5 * lane).is_empty


def _shared(a: Polygon, b: Polygon, tol: float):
    """The boundary ``a`` and ``b`` share (lines), tolerant of the snap."""
    x = a.boundary.intersection(b.boundary.buffer(tol))
    return x if x.length > 0.0 else None


def _voronoi_candidates(piece: Polygon, pts: np.ndarray, grp: np.ndarray,
                        grid: float) -> list[tuple[int, Polygon]]:
    """``(group, polygon)`` candidates: the piece partitioned by its nearest
    station, the cells unioned per group."""
    uniq, first = np.unique(pts, axis=0, return_index=True)
    grp = grp[first]
    if len(uniq) < 2:
        return [(int(grp[0]), piece)]
    env = piece.envelope.buffer(max(piece.length, 1.0))
    cells = list(shapely.voronoi_polygons(MultiPoint(uniq), extend_to=env).geoms)
    tree = STRtree(cells)
    pi, ci = tree.query(shapely.points(uniq), predicate="intersects")
    of: dict[int, int] = {}
    for p, c in zip(pi.tolist(), ci.tolist()):
        of.setdefault(c, int(grp[p]))
    out: list[tuple[int, Polygon]] = []
    for g in sorted(set(of.values())):
        geom = shapely.union_all([cells[c] for c, gg in of.items() if gg == g])
        geom = shapely.set_precision(geom.intersection(piece), grid)
        out.extend((g, q) for q in polygon_parts(geom))
    return out


def _merge_floors(cands: list[tuple[int, Polygon]], min_m2: float, lane: float,
                  grid: float) -> tuple[list[tuple[int, Polygon]], list[tuple[int, int, Polygon]]]:
    """The mint's floors: a candidate under them joins the neighbour with
    the longest shared boundary.  ``(parts, [(from group, into group,
    polygon)])``."""
    cands = sorted(cands, key=lambda c: _key(c[1]))
    gone: list[tuple[int, int, Polygon]] = []
    while len(cands) > 1:
        small = [i for i, (_g, q) in enumerate(cands) if _under_floor(q, min_m2, lane)]
        if not small:
            break
        i = small[-1]                           # the smallest first
        g, q = cands[i]
        best, best_len = None, 0.0
        for j, (_gj, qj) in enumerate(cands):
            if j == i:
                continue
            x = _shared(q, qj, 2.0 * grid)
            if x is not None and x.length > best_len:
                best, best_len = j, x.length
        if best is None:
            break
        gj, qj = cands[best]
        merged = shapely.set_precision(shapely.union_all([q, qj]), grid)
        whole = max(polygon_parts(merged), key=lambda p: p.area)
        if gj != g:
            gone.append((g, gj, q))
        cands = [c for k, c in enumerate(cands) if k not in (i, best)] + [(gj, whole)]
        cands = sorted(cands, key=lambda c: _key(c[1]))
    # adjacent parts of ONE group are one part
    out: list[tuple[int, Polygon]] = []
    for g in sorted({g for g, _q in cands}):
        geom = shapely.set_precision(
            shapely.union_all([q for gg, q in cands if gg == g]), grid)
        out.extend((g, q) for q in polygon_parts(geom))
    return sorted(out, key=lambda c: _key(c[1])), gone


def _knife(parts: list[tuple[int, Polygon]], width: float, grid: float,
           min_m2: float, lane: float) -> tuple[list[tuple[int, Polygon]], int, float]:
    """The knife strip between every two parts of different groups, half
    from each side.  ``(parts, knives, m2 left under the floors)``."""
    lines, knives = [], 0
    for i, (gi, qi) in enumerate(parts):
        for gj, qj in parts[i + 1:]:
            if gi == gj:
                continue
            x = _shared(qi, qj, 2.0 * grid)
            if x is not None:
                lines.append(x)
                knives += 1
    if not lines:
        return parts, 0, 0.0
    # the snap may move each rim by half a grid diagonal: the strip carries it
    strip = shapely.union_all(lines).buffer(
        0.5 * width + grid, cap_style="square", join_style="mitre", mitre_limit=2.0)
    out, dropped = [], 0.0
    for g, q in parts:
        for p in polygon_parts(shapely.set_precision(q.difference(strip), grid)):
            if _under_floor(p, min_m2, lane):
                dropped += float(p.area)
            else:
                out.append((g, p))
    return sorted(out, key=lambda c: _key(c[1])), knives, dropped


def _lot_cut(part: Polygon, road: list[Station], apron: list[Station],
             cap: float, step: float, simplify_m: float, grid: float,
             min_m2: float, lane: float) -> tuple[list[Polygon], list[Polygon], list[Polygon]]:
    """``(lots, ramps, ramp components merged into the lot)``: the ramp is
    where the road's level cannot be reached from the apron at the cap."""
    x0, y0, x1, y1 = part.bounds
    xs = np.arange(math.floor(x0 / step), math.ceil(x1 / step)) * step
    ys = np.arange(math.floor(y0 / step), math.ceil(y1 / step)) * step
    gx, gy = np.meshgrid(xs, ys)
    cen = np.column_stack([gx.ravel() + 0.5 * step, gy.ravel() + 0.5 * step])
    _dr, ir = cKDTree([s.xy for s in road]).query(cen)
    da, ia = cKDTree([s.xy for s in apron]).query(cen)
    L = np.array([s.z for s in road])[ir]
    A = np.array([s.z for s in apron])[ia]
    ramp = (L - A) > cap * da
    if not ramp.any():
        return [part], [], []
    c = cen[ramp]
    band = shapely.union_all(shapely.box(c[:, 0] - 0.5 * step, c[:, 1] - 0.5 * step,
                                         c[:, 0] + 0.5 * step, c[:, 1] + 0.5 * step))
    band = band.simplify(simplify_m, preserve_topology=True)
    ramp_g = shapely.set_precision(part.intersection(band), grid)
    lot_g = shapely.set_precision(part.difference(ramp_g), grid)
    lots = [p for p in polygon_parts(lot_g) if not _under_floor(p, min_m2, lane)]
    if not lots:
        return [], [part], []
    # a lot sliver is the ramp's; then a ramp component under the floor is
    # the lot's (its apron stations are conflicts the caller reports) — it
    # borders a standing lot, the part being connected
    lot_ok = shapely.union_all(lots)
    merged = [p for p in polygon_parts(shapely.set_precision(part.difference(lot_ok), grid))
              if _under_floor(p, min_m2, lane)]
    lot_all = shapely.set_precision(shapely.union_all(lots + merged), grid)
    ramp_all = shapely.set_precision(part.difference(lot_all), grid)
    lots = sorted((p for p in polygon_parts(lot_all)
                   if not _under_floor(p, min_m2, lane)), key=_key)
    ramps = sorted(polygon_parts(ramp_all), key=_key)
    return lots, ramps, merged


def terrace_cut(piece: Polygon, stations: _t.Sequence[Station], law: Law,
                rules, *, cap: float | None = None) -> TerraceCut:
    """THE CUT of one gap piece by its standing neighbours' levels.  ``cap``
    is the piece's own longitudinal cap (default: the loosest station cap,
    each being the tighter of the piece's and its ring's)."""
    st = list(stations)
    if not st:
        return TerraceCut((Part(piece, "", None, 0, ()),), (), 0, ())
    lw = law.tables.structures.load
    ident = float(law.tables.emit.identity.min_distinct_spacing_m)
    lane = float(law.tables.emit.road_profile.lane_width_m)
    tr = law.tables.emit.terrace
    grid = float(rules.cells.snap_grid_m)
    min_m2 = float(lw.object_pavement_min_m2)
    cap = float(cap) if cap is not None else max(s.cap for s in st)
    groups = level_groups(st)
    grp = np.zeros(len(st), dtype=int)
    for g, members in enumerate(groups):
        grp[members] = g
    pts = np.array([s.xy for s in st], dtype=float)
    parts: list[tuple[int, Polygon]] = [(0, piece)]
    gone: list[tuple[int, int, Polygon]] = []
    knives, dropped = 0, 0.0
    if len(groups) > 1:
        cands, gone = _merge_floors(_voronoi_candidates(piece, pts, grp, grid),
                                    min_m2, lane, grid)
        if len(cands) > 1:
            parts, knives, dropped = _knife(cands, knife_m(law), grid, min_m2, lane)
        else:
            parts = [(cands[0][0] if cands else 0, piece)]
    stepped = len(parts) > 1
    # each station is its nearest part's; one of another group was merged away
    tree = STRtree([q for _g, q in parts])
    near = tree.nearest(shapely.points(pts)) if parts else np.zeros(0, dtype=int)
    own: dict[int, list[int]] = {k: [] for k in range(len(parts))}
    merged: list[dict] = []
    for i, k in enumerate(np.asarray(near).tolist()):
        own[k].append(i)
        if len(groups) > 1 and parts[k][0] != int(grp[i]):
            merged.append({"station": i, "xy": st[i].xy, "z": st[i].z, "cls": st[i].cls,
                           "ring": st[i].ring, "group": int(grp[i]),
                           "into_group": int(parts[k][0])})
    out: list[Part] = []
    for k, (g, q) in enumerate(parts):
        base = f"/s{k}" if stepped else ""
        mine = own[k]
        road = [st[i] for i in mine if st[i].cls == ROAD]
        apron = [st[i] for i in mine if st[i].cls == APRON]
        ids = tuple(mine)
        if road and len(road) == len(mine):
            out.append(Part(q, base + "/lot", "lot", g, ids))        # 06a
            continue
        differ = road and apron and (
            max(s.z for s in road) - min(s.z for s in apron) > tr.pad_terrace_floor_m
            or max(s.z for s in apron) - min(s.z for s in road) > tr.pad_terrace_floor_m)
        if differ:
            lots, ramps, lost = _lot_cut(q, road, apron, cap, float(tr.gap_cut_sample_m),
                                         0.5 * ident, grid, min_m2, lane)
            if lots and ramps:
                for j, p in enumerate(lots):
                    out.append(Part(p, base + ("/lot" if j == 0 else f"/lot{j}"),
                                    "lot", g, ids))
                for j, p in enumerate(ramps):
                    out.append(Part(p, base + f"/ramp{j}", "ramp", g, ids))
                for p in lost:
                    for i in mine:
                        if st[i].cls == APRON and p.distance(shapely.Point(st[i].xy)) <= lane:
                            merged.append({"station": i, "xy": st[i].xy, "z": st[i].z,
                                           "cls": APRON, "ring": st[i].ring,
                                           "group": int(grp[i]), "into_group": g,
                                           "into": "lot"})
                continue
            if lots and not ramps:
                out.append(Part(q, base + "/lot", "lot", g, ids))
                continue
        out.append(Part(q, base, "step" if stepped else None, g, ids))
    return TerraceCut(tuple(out), tuple(tuple(g) for g in groups), knives,
                      tuple(merged), dropped)
