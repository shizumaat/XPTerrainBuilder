"""A PACK LINE OBJECT AT A PAVED EDGE IS THE GRADED AREA'S TRUE EDGE (issue
#2054; owner 2026-11-13 15:29Z, KSFO 37.606308, -122.378419: "the
fence/barrier line stays flat on the paved area and the drop happens on
the groundside (outer) side of that line"; 16:04Z, KCRW 38.363304,
-81.588474, the mirror: "use the fence as the marker for the graded area,
and then terrain rises outside the fence").

ONE derivation site, called by ``roles.classify`` after every cell stands.
A pack LINE facade (``Airport.edge_lines``) that STANDS ON the upper
level — a wire fence, a low barrier or a solid wall not authored below its
zero (``airport/line_solidity.kind_of``) — is read every
``[edge_lines] station_m`` along its length.  A station MARKS AN EDGE when

* a paved face (``law.tables.pavement_roles``) lies within
  ``host_reach_m`` of it — the HOST, on one side;
* the ground ``step_probe_m`` beyond the line's base on the OTHER side is
  not paved, and DEPARTS from the graded level: water there, or the DEM
  ``step_min_m`` under OR over the DEM at the host's edge (a fall to the
  bay, a rise past a boundary fence).

Consecutive marking stations of one host and side, at least ``min_run_m``
long, mark THE EDGE GROUND: from the host's edge out to the line plus its
base half-width (``EdgeLine.half_width_m``), less the water.

* A GROUNDSIDE host (a road ribbon, a lot) TAKES it, as the §47 road takes
  the ground to its retaining wall: the host cell grows by it, less every
  other cell standing — one face at the host's own grade, however narrow
  the gap (MEASURED KSFO: the ribbon stands within 0.3 m of the barrier,
  under the §52 stand-off, and the barrier's base stood on the drop).
* An AIRSIDE host never grows (airside is king): the ground is ONE STRIP,
  less every cell standing with the §52 stand-off round it, role
  ``groundside_pavement``, ref ``edgestrip:<k>:<host ref>``
  (``model.planar.edge_strip_host``), a LATE cell (``model.planar.
  is_late_ref``) whose level is the host's rim, taken AFTER the solve
  (``solve/project_strip.project_facade_strips``): the airside and every
  cell standing are what they were BY CONSTRUCTION.  The cut or fill
to natural ground is then the one-triangle step from the strip's outer
edge to the ground beyond the line — outside the line, never inside it.

A RETAINING WALL (authored below its zero) marks no strip here: it is the
step itself, seated at its low side's ground (``airport/wall_class``)."""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..airport.dem import dem_z_many
from ..airport.line_solidity import ON_TOP, kind_of
from ..law import Law
from ..law.tables import pavement_roles, snap_margin_m
from ..model.planar import EDGE_STRIP_PREFIX
from .evidence import polygon_parts
from .rules import Rules

__all__ = ["mint_edge_strips", "STRIP_ROLE"]

STRIP_ROLE = "groundside_pavement"


class _Station(_t.NamedTuple):
    s: float
    p: tuple[float, float]
    q: tuple[float, float]          # the host's nearest edge point
    host: str
    side: int                       # +1: the host is left of the line
    cell: int = -1                  # the host cell's id


def _stations(line: LineString, step: float) -> list[tuple[float, tuple, tuple]]:
    """``(s, point, unit left normal)`` every ``step`` along ``line``."""
    out = []
    n = max(1, int(math.ceil(line.length / step)))
    for k in range(n + 1):
        s = min(line.length, k * line.length / n)
        a = line.interpolate(max(0.0, s - 0.5))
        b = line.interpolate(min(line.length, s + 0.5))
        dx, dy = b.x - a.x, b.y - a.y
        d = math.hypot(dx, dy)
        if d <= 0.0:
            continue
        p = line.interpolate(s)
        out.append((s, (p.x, p.y), (-dy / d, dx / d)))
    return out


def _water(dem, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    many = getattr(dem, "water_many", None)
    if many is None:
        return np.zeros(len(xs), dtype=bool)
    return np.asarray(many(xs, ys)[0], dtype=bool)


def _marking(el, line: LineString, paved, tree: STRtree, dem, cfg) -> list[_Station]:
    """The stations of ``line`` that mark a paved edge (module doc)."""
    hw = float(el.half_width_m)
    rows = []
    for s, p, n in _stations(line, float(cfg.station_m)):
        pt = Point(p)
        best = None
        for j in tree.query(pt.buffer(float(cfg.host_reach_m))):
            c, g = paved[int(j)]
            d = g.distance(pt)
            if d <= float(cfg.host_reach_m) and (best is None or d < best[0]):
                best = (d, c, g)
        if best is None:
            continue
        _d, c, g = best
        q = shapely.ops.nearest_points(g, pt)[0]
        side = 1 if (q.x - p[0]) * n[0] + (q.y - p[1]) * n[1] >= 0.0 else -1
        out = hw + float(cfg.step_probe_m)
        f = (p[0] - side * n[0] * out, p[1] - side * n[1] * out)
        if any(paved[int(j)][1].contains(Point(f)) for j in tree.query(Point(f))):
            continue                        # paved beyond as well: no edge
        rows.append((s, p, (q.x, q.y), c.ref.split("#")[0] if c.role == "building"
                     else c.ref, side, f, c.id))
    if not rows:
        return []
    q = np.array([r[2] for r in rows], dtype=float)
    f = np.array([r[5] for r in rows], dtype=float)
    zq, zf = dem_z_many(dem, q[:, 0], q[:, 1]), dem_z_many(dem, f[:, 0], f[:, 1])
    wet = _water(dem, f[:, 0], f[:, 1])
    departs = wet | (np.isfinite(zq) & np.isfinite(zf)
                     & (np.abs(zq - zf) >= float(cfg.step_min_m)))
    return [_Station(*r[:5], r[6]) for r, ok in zip(rows, departs, strict=True) if ok]


def _runs(st: list[_Station], step: float, min_run: float) -> list[list[_Station]]:
    """Consecutive stations of one host and side, ``min_run`` long."""
    runs: list[list[_Station]] = []
    for x in st:
        last = runs[-1][-1] if runs else None
        if last is not None and last.host == x.host and last.side == x.side \
                and x.s - last.s <= step * 1.5 + 1e-9:
            runs[-1].append(x)
        else:
            runs.append([x])
    return [r for r in runs if r[-1].s - r[0].s >= min_run]


def _strip(run: list[_Station], line: LineString, hw: float) -> Polygon:
    """The ground from the host's edge out past the line by ``hw``."""
    quads = []
    for a, b in zip(run, run[1:], strict=False):
        def out(x: _Station) -> tuple[float, float]:
            px, py = x.p
            dx, dy = px - x.q[0], py - x.q[1]
            d = math.hypot(dx, dy)
            if d < 1e-6:                    # the host reaches the line
                pa = line.interpolate(max(0.0, x.s - 0.5))
                pb = line.interpolate(min(line.length, x.s + 0.5))
                tx, ty = pb.x - pa.x, pb.y - pa.y
                t = math.hypot(tx, ty) or 1.0
                dx, dy, d = x.side * ty / t, -x.side * tx / t, 1.0
            return (px + dx / d * hw, py + dy / d * hw)
        g = Polygon([a.q, out(a), out(b), b.q])
        if not g.is_valid:
            g = g.buffer(0.0)
        if not g.is_empty:
            quads.append(g)
    return unary_union(quads) if quads else Polygon()


def mint_edge_strips(airport, cells: list, law: Law, rules: Rules, add) -> dict[str, _t.Any]:
    """Mint the edge strips onto ``cells`` through ``add`` (the
    classifier's own cell constructor); returns the counts."""
    stats: dict[str, _t.Any] = {"edge_lines": 0, "edge_lines_on_top": 0,
                                "edge_strips": 0, "edge_strip_m2": 0.0}
    lines = tuple(getattr(airport, "edge_lines", ()) or ())
    stats["edge_lines"] = len(lines)
    cfg = rules.edge_lines
    roles = set(pavement_roles(law))
    paved = [(c, g) for c in cells if c.role in roles
             for g in [Polygon(c.ring, c.holes)] if g.is_valid and not g.is_empty]
    if not lines or not paved:
        return stats
    tree = STRtree([g for _c, g in paved])
    standing = unary_union([Polygon(c.ring, c.holes).buffer(0.0) for c in cells])
    standoff = float(law.tables.structures.building_pad.groundside_cutback_m) \
        + snap_margin_m(law) + float(law.tables.emit.identity.min_distinct_spacing_m)
    keep_off = standing.buffer(standoff, join_style="mitre", mitre_limit=2.0)
    dem = getattr(airport, "dem", None)
    wg = getattr(dem, "water_geometry", None)
    n, grid = 0, rules.cells.snap_grid_m
    by_id = {c.id: k for k, c in enumerate(cells)}
    grow: dict[int, list] = {}              # groundside host index -> its extensions
    for el in lines:
        kind = kind_of(el, rules.service)
        stats[f"edge_kind_{kind}"] = stats.get(f"edge_kind_{kind}", 0) + 1
        if kind not in ON_TOP or len(el.points) < 2:
            continue
        stats["edge_lines_on_top"] += 1
        pts = list(el.points) + ([el.points[0]] if el.closed else [])
        line = LineString(pts)
        if line.length <= 0.0:
            continue
        for run in _runs(_marking(el, line, paved, tree, dem, cfg),
                         float(cfg.station_m), float(cfg.min_run_m)):
            geom = _strip(run, line, float(el.half_width_m))
            if geom.is_empty:
                continue
            wet = wg(geom.bounds) if wg is not None else None
            if wet is not None:
                geom = geom.difference(wet)
            k = by_id.get(run[0].cell, -1)
            if k >= 0 and cells[k].side == "groundside":
                # a GROUNDSIDE host takes the ground itself, as the §47 road
                # takes the ground to its retaining wall: one face, graded
                # with it, nothing airside in its rows
                grow.setdefault(k, []).append((geom, el, kind, run))
                continue
            geom = shapely.set_precision(geom.difference(keep_off), grid)
            for part in polygon_parts(geom):
                if part.area < rules.cells.min_area_m2:
                    continue
                add(STRIP_ROLE, f"{EDGE_STRIP_PREFIX}:{n}:{run[0].host}", part,
                    "edge_strip", None, None,
                    {"edge_line": el.id, "edge_def": el.def_path,
                     "edge_kind": kind, "host": run[0].host,
                     "edge_run_m": round(run[-1].s - run[0].s, 1)})
                n += 1
                stats["edge_strips"] += 1
                stats["edge_strip_m2"] += round(part.area, 1)
    stats.update(_grow_hosts(cells, grow, rules))
    return stats


def _grow_hosts(cells: list, grow: dict, rules: Rules) -> dict[str, float]:
    """Each groundside host cell grown by its edge ground (``grow``: cell
    index -> ``[(geom, line, kind, run)]``), less every OTHER cell standing:
    the part joined to the host replaces it, same role and ref."""
    out = {"edge_hosts_grown": 0, "edge_host_m2": 0.0}
    if not grow:
        return out
    polys = [Polygon(c.ring, c.holes).buffer(0.0) for c in cells]
    tree = STRtree(polys)
    for k in sorted(grow):
        host = polys[k]
        ext = unary_union([g for g, *_r in grow[k]])
        others = [polys[int(j)] for j in tree.query(ext) if int(j) != k]
        if others:
            ext = ext.difference(unary_union(others))
        got = shapely.set_precision(unary_union([host, ext]), rules.cells.snap_grid_m)
        part = max(polygon_parts(got), key=lambda g: g.intersection(host).area, default=None)
        if part is None or part.area <= host.area + rules.cells.min_area_m2:
            continue
        _g, el, kind, run = grow[k][0]
        c = cells[k]
        cells[k] = _dc.replace(c, ring=tuple(part.exterior.coords)[:-1],
                               holes=tuple(tuple(h.coords)[:-1] for h in part.interiors),
                               evidence=dict(c.evidence, edge_line=el.id, edge_kind=kind,
                                             edge_grown_m2=round(part.area - host.area, 1)))
        out["edge_hosts_grown"] += 1
        out["edge_host_m2"] += round(part.area - host.area, 1)
    return out
