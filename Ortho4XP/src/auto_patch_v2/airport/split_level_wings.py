"""THE UPPER WING OF A SPLIT-LEVEL BUILDING (#1934 R5; owner sim read
2026-11-17T05:18Z, KLAX: "There's no pit there, terminal 8, sitting on the
apron"; RULINGS 2026-11-13w (2): every wall bottom on terrain, the upper
storey's on the upper ground; 2026-11-16t: a cut of several metres against
1 m lidar needs a named witness).

``airport/split_level`` cuts the plan's outline into RUNS and reads each
run's level from the foot of its walls.  What lies inside the frontage
strips is the UNWITNESSED REMAINDER, and spec 2062 A1 (1) (c) hands each
piece of it to the LOWEST level it touches.  A terminal whose concourse
wing has every wall footed on the upper floor, joined to a block whose
walls run down to a lot a storey below, is ONE remainder piece: it touched
the block's lower walls, so the whole concourse went to the lower floor
and the pit sank it a storey under the apron it stands on.

THE WALLS ARE THE WITNESS.  The outline is a ring of ARCS, each a maximal
chain of runs on one level (a run with no foot continues its neighbour's
arc).  An arc on a level above the lowest HOLDS the plan between itself and
the straight CHORD joining its two ends: inside it, every wall the building
shows stands on that level, and no wall of a lower storey looks into it.
A building cut into a slope with one open side has a straight upper arc --
its chord is the arc, it holds nothing, and its whole plan stays on the
lower floor as before.  A lower arc holds nothing: the lowest level is the
remainder's default already.

Pure geometry: no law constant, nothing names a pack, a resource or an
airport."""
from __future__ import annotations

import math
import typing as _t

import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from ..geom.parts import polygon_parts_with_area

__all__ = ["arcs", "upper_wings"]


def arcs(run_levels: _t.Sequence["int | None"], lengths: _t.Sequence[float] = (),
         min_arc_m: float = 0.0) -> list[tuple[int, list[int]]]:
    """The outline's ARCS: ``(level, run indices)`` per maximal cyclic chain
    of runs on one level, a run with no level taking the level of the arc
    it continues (``[]`` when no run has a level, or all share one).  An
    arc shorter than ``min_arc_m`` (run ``lengths``) is no reading -- a
    corner's sliver -- and joins its longer neighbour."""
    lv = list(run_levels)
    while True:
        out = _chains(lv)
        if not lengths or min_arc_m <= 0.0 or len(out) < 2:
            return out
        size = [sum(lengths[i] for i in idx) for _k, idx in out]
        j = min(range(len(out)), key=lambda a: size[a])
        if size[j] >= min_arc_m:
            return out
        a, b = (j - 1) % len(out), (j + 1) % len(out)
        k = out[a][0] if size[a] >= size[b] else out[b][0]
        for i in out[j][1]:
            lv[i] = k


def _chains(run_levels: _t.Sequence["int | None"]) -> list[tuple[int, list[int]]]:
    n = len(run_levels)
    known = [i for i, k in enumerate(run_levels) if k is not None]
    if not known or len({run_levels[i] for i in known}) < 2:
        return []
    lv = list(run_levels)
    # fill forward from the first known run, cyclically
    i0 = known[0]
    cur = lv[i0]
    for d in range(n):
        i = (i0 + d) % n
        if lv[i] is None:
            lv[i] = cur
        cur = lv[i]
    # start at a level change so no arc wraps the seam
    s = next(i for i in range(n) if lv[i] != lv[i - 1])
    out: list[tuple[int, list[int]]] = []
    for d in range(n):
        i = (s + d) % n
        if out and out[-1][0] == lv[i]:
            out[-1][1].append(i)
        else:
            out.append((int(lv[i]), [i]))
    return out


def upper_wings(plan: Polygon, runs: _t.Sequence[tuple], run_levels: _t.Sequence,
                min_arc_m: float = 0.0) -> dict[int, Polygon]:
    """Per level above the lowest, the part of ``plan`` its arcs hold
    (module docstring).  ``runs`` are the outline's runs in ring order, each
    a pair of end points (either orientation); arcs under ``min_arc_m``
    join their neighbours (:func:`arcs`)."""
    out: dict[int, list] = {}
    lengths = [math.dist(p0, p1) for p0, p1 in runs]
    for k, idx in arcs(run_levels, lengths, min_arc_m):
        if k == 0 or len(idx) < 2:
            continue
        lines = [LineString([runs[i][0], runs[i][1]]) for i in idx]
        ends = _ends(lines)
        if ends is None:
            continue
        chord = LineString(ends)
        if chord.length <= 0.0:
            continue
        # the union nodes the chain and the chord (a chord crossing the arc
        # splits the held region into faces, all of them held)
        faces = shapely.polygonize(shapely.get_parts(unary_union([*lines, chord])))
        held = unary_union(polygon_parts_with_area(faces)).intersection(plan).buffer(0)
        if not held.is_empty and held.area > 0.0:
            out.setdefault(k, []).append(held)
    return {k: unary_union(v).buffer(0) for k, v in out.items()}


def _ends(lines: _t.Sequence[LineString]):
    """The two free ends of a chain of ``lines`` (each end point met once),
    exactly as the lines carry them, or ``None`` when the chain does not
    have exactly two."""
    seen: dict[tuple, list] = {}
    for ln in lines:
        for p in (ln.coords[0], ln.coords[-1]):
            seen.setdefault((round(p[0], 6), round(p[1], 6)), []).append(p)
    free = [ps[0] for ps in seen.values() if len(ps) % 2 == 1]
    return free if len(free) == 2 else None
