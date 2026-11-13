"""A FENCE IS A DIVISION (owner RULINGS 2026-11-13s (2), #1338; owner
18:02Z: "fence lines are another clear indicator of a division, a fence
cannot cross airside, so a fence can be airside on one side and groundside
on the other, or groundside on both, but never airside on both sides of a
fence").

THE FENCES (:func:`fence_lines`): every pack LINE facade
(``Airport.edge_lines``) that ``airport/line_solidity.kind_of`` reads as a
wire fence, a low barrier or a solid wall standing on its zero
(``line_solidity.ON_TOP``), and every OSM way tagged ``barrier=fence`` /
``barrier=wall`` the loaded feeds carry.

A fence RUNS ALONG an edge within ``[edge_lines] host_reach_m`` of it: the
one tolerance the engine already has for "a line object marks this paved
edge" (``classify/edge_line_mint``, #2054).  Two readers:

* §27 (``airside_edge.airside_edge_flip``) drops the run of a contact
  inside :func:`fence_band` — airside never propagates across a fence;
* :func:`airside_both_sides` is the DEFECT CHECK: a fence station whose
  probes either side (``[edge_lines] step_probe_m`` off the line) both land
  in airside pavement, summed into runs of ``[edge_lines] min_run_m``."""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..airport.line_solidity import ON_TOP, kind_of
from ..law import Law
from ..law.tables import role_side
from .rules import Rules

__all__ = ["FENCE_BARRIER_TAGS", "fence_lines", "fence_band", "airside_both_sides"]

#: OSM ``barrier=*`` values that are a fence line (the ruling's words)
FENCE_BARRIER_TAGS = ("fence", "wall")


def fence_lines(airport, rules: Rules) -> list[tuple[str, LineString]]:
    """``(id, line)`` of every fence of ``airport`` (module doc), in the frame."""
    out: list[tuple[str, LineString]] = []
    for el in tuple(getattr(airport, "edge_lines", ()) or ()):
        if kind_of(el, rules.service) not in ON_TOP or len(el.points) < 2:
            continue
        pts = list(el.points) + ([el.points[0]] if el.closed else [])
        out.append((el.id, LineString(pts)))
    for w in tuple(getattr(airport, "osm_ways", ()) or ()):
        if w.tags.get("barrier") in FENCE_BARRIER_TAGS and len(w.points) >= 2:
            pts = list(w.points) + ([w.points[0]] if w.closed else [])
            out.append((f"osm:{w.id}", LineString(pts)))
    return [(i, ln) for i, ln in out if ln.length > 0.0]


def fence_band(lines: _t.Sequence[tuple[str, LineString]], rules: Rules):
    """The ground a fence RUNS ALONG: each line widened by ``[edge_lines]
    host_reach_m``; ``None`` with no fence."""
    if not lines:
        return None
    reach = float(rules.edge_lines.host_reach_m)
    return unary_union([ln.buffer(reach, cap_style="flat") for _i, ln in lines])


def _probe(line: LineString, s: float, d: float) -> tuple[Point, Point]:
    """The two points ``d`` off ``line`` either side of station ``s``."""
    p = line.interpolate(s)
    a = line.interpolate(max(0.0, s - 0.5))
    b = line.interpolate(min(line.length, s + 0.5))
    tx, ty = b.x - a.x, b.y - a.y
    n = (tx * tx + ty * ty) ** 0.5 or 1.0
    nx, ny = -ty / n * d, tx / n * d
    return Point(p.x + nx, p.y + ny), Point(p.x - nx, p.y - ny)


def _runs(marks: list[tuple[float, bool]], min_run: float) -> list[tuple[float, float]]:
    """Consecutive marking stations ``(s, marked)`` as ``(s0, s1)`` runs at
    least ``min_run`` long."""
    runs, start, last = [], None, None
    for s, hit in marks:
        if hit:
            start = s if start is None else start
            last = s
        elif start is not None:
            runs.append((start, last))
            start = None
    if start is not None:
        runs.append((start, last))
    return [(s0, s1) for s0, s1 in runs if s1 - s0 >= min_run]


def airside_both_sides(cells: _t.Sequence, lines: _t.Sequence[tuple[str, LineString]],
                       law: Law, rules: Rules) -> dict[str, _t.Any]:
    """THE DEFECT CHECK (module doc) over classified ``cells``: how many
    fences, and how many metres of them, stand with airside pavement on
    BOTH sides.  A station marks when both probes lie in a non-building
    airside cell; consecutive marking stations at least ``min_run_m`` long
    count.  Returns ``fence_lines``, ``fence_airside_both`` (fences),
    ``fence_airside_both_m`` and ``fence_airside_both_sites`` (fence id and
    the frame point of each fence's first run)."""
    out: dict[str, _t.Any] = {"fence_lines": len(lines), "fence_airside_both": 0,
                              "fence_airside_both_m": 0.0, "fence_airside_both_sites": []}
    air = [Polygon(c.ring, c.holes) for c in cells
           if c.role != "building" and role_side(law, c.role) == "airside"]
    air = [g if g.is_valid else g.buffer(0.0) for g in air]
    air = [g for g in air if not g.is_empty]
    if not lines or not air:
        return out
    tree = STRtree(air)
    cfg = rules.edge_lines
    step, d = float(cfg.station_m), float(cfg.step_probe_m)

    def inside(p: Point) -> bool:
        return any(air[int(j)].covers(p) for j in tree.query(p))

    for fid, line in lines:
        marks = []
        for k in range(int(line.length // step) + 1):
            s = min(line.length, k * step)
            a, b = _probe(line, s, d)
            marks.append((s, inside(a) and inside(b)))
        runs = _runs(marks, float(cfg.min_run_m))
        if runs:
            out["fence_airside_both"] += 1
            out["fence_airside_both_m"] += round(sum(s1 - s0 for s0, s1 in runs), 1)
            p = line.interpolate(runs[0][0])
            out["fence_airside_both_sites"].append((fid, round(p.x, 1), round(p.y, 1)))
    return out
