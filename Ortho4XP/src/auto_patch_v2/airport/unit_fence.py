"""A UNIT'S OWN FENCES JOIN THE ONE FENCE LIST (spec ``2068-fence-grade-spec-A2.md``
F1; owner sim read #2068 2026-11-14T14:44Z: the pack's black wire fence is
"a good clue as to how the author expects the grade around the tower").

A wire fence, a low barrier or a wall standing on its zero that the pack
authored as a member of a UNIT (one anchor family, ``model.rebake.Unit``)
carries the author's ground along its foot: the unit's zero plus each
column's authored base ``y``.  Nothing read it: it is no DSF line facade
(``Airport.edge_lines`` held only those, ``airport/load``).

ONE derivation site, called beside ``airport/wall_shade.attach_wall_shade``.
For every member of a unit whose parts are all LINE parts
(``airport/line_object``) and whose file reads a class that stands on its
zero (``line_solidity.ON_TOP``), each genuine component's vertices are read
in the planar frame (``sunken_ramp.member_vertices``), grouped into COLUMNS
(vertices within ``emit.identity.min_distinct_spacing_m`` in plan), the
columns joined where a triangle spans two of them, and the joins chained
into RUNS split at every branch.  A run at least ``[edge_lines] min_run_m``
long is one :class:`model.airport.EdgeLine` with ``unit`` set, id
``unit:<unit>:<member>#<comp>`` (``/<k>`` for a component's later runs),
``base_ys`` its columns' authored bases and ``panel_m`` their median
height.

A DSF line facade, an OSM fence (RULINGS 2026-11-13y (1)) and a retaining
wall (the step itself, ``airport/wall_class``) are not read here.  This
round the §27 division and the edge strips skip a unit line
(``classify/fence_division``, ``classify/edge_line_mint``; owner Q4);
``classify/fence_yard`` is its one reader."""
from __future__ import annotations

import dataclasses as _dc
import math
import statistics as _st

import numpy as np

__all__ = ["attach_unit_fences"]

#: the id prefix of a unit fence's ``EdgeLine``
_UNIT_PREFIX = "unit:"


def attach_unit_fences(airport, rules, law, cache=None):
    """``airport`` with its unit fences appended to ``Airport.edge_lines``
    (module doc); a unit line already there is replaced, so a replay that
    re-attaches reads the current tree once.  ``rules`` the classify rules
    (``[service] line_*``, ``[edge_lines]``), ``cache`` the build's
    ``ResourceCache``."""
    part = getattr(airport, "partition", None)
    frame = getattr(airport, "frame", None)
    if frame is None:
        return airport
    kept = tuple(el for el in (getattr(airport, "edge_lines", ()) or ())
                 if getattr(el, "unit", None) is None)
    if part is None:
        return _dc.replace(airport, edge_lines=kept)
    if cache is None:
        from .frame_entry import quantum
        from .obj8 import ResourceCache
        cache = ResourceCache(law.tables.structures.basin.min_solid_thickness_m, quantum(law))
    to_xy = frame.entry()
    weld = float(law.tables.emit.identity.min_distinct_spacing_m)
    min_run = float(rules.edge_lines.min_run_m)
    got: list = []
    for ui, u in enumerate(part.units):
        for m in u.members:
            got.extend(_member_lines(ui, u, m, rules, to_xy, cache, weld, min_run))
    return _dc.replace(airport, edge_lines=kept + tuple(got))


def _member_lines(ui, u, m, rules, to_xy, cache, weld, min_run) -> list:
    """The ``EdgeLine`` runs of one member, or ``[]``."""
    from ..model.airport import EdgeLine
    from .line_object import component_shape
    from .line_solidity import ON_TOP, kind_of, obj_solidity
    from .placement_cut import pristine_path
    from .sunken_ramp import member_vertices
    from .wall_class import _origin
    parts = tuple(m.parts or ())
    if not parts or not all(getattr(p, "line", False) for p in parts):
        return []
    origin = _origin(u, m)
    if origin is None:
        return []
    try:
        path = pristine_path(m)
    except (OSError, ValueError):
        return []
    sol = obj_solidity(path)
    if sol is None or kind_of(sol, rules.service) not in ON_TOP:
        return []
    got = member_vertices(m, origin, to_xy, cache)
    if got is None:
        return []
    P, g = got
    comps = cache.genuine(path)
    out = []
    for p in parts:
        if not 0 <= p.comp < len(comps):
            continue
        comp = comps[p.comp]
        zero = float(p.base_y) - float(comp.min_y)          # the member's own zero
        # the base half-width is the component's own (a sheet's is 0); the
        # file's foot extent (``Solidity.half_width_m``) spans every leg
        half = 0.5 * component_shape(g, comp)[1]
        for k, (pts, base, top, closed) in enumerate(
                _unit_fence_runs(P, np.asarray(comp.tris), weld, min_run)):
            out.append(EdgeLine(
                f"{_UNIT_PREFIX}{ui}:{m.id}#{p.comp}{'' if k == 0 else f'/{k}'}",
                m.resource, pts, closed, float(sol.base_y), float(sol.top_y),
                float(sol.solid_top_y), float(sol.opaque_share), half,
                unit=ui, base_ys=tuple(round(b + zero, 3) for b in base),
                panel_m=round(float(_st.median(t - b for b, t in zip(base, top, strict=True))),
                              3)))
    return out


def _unit_fence_runs(P: np.ndarray, tris: np.ndarray, weld: float, min_run: float
                    ) -> list[tuple[tuple, tuple, tuple, bool]]:
    """THE RUNS of one fence component: ``P`` ``(n, 3)`` of ``(x, y,
    authored y)``, ``tris`` ``(k, 3)`` vertex indices, of which only the
    SHEET triangles (standing vertical) are read.  Returns
    ``(points, bases, tops, closed)`` per run at least ``min_run`` long:
    the columns' plan positions, their lowest and highest authored ``y``
    and whether the run is a ring.  Columns weld vertices within ``weld``
    in plan; two columns join where one triangle spans both; the chains
    split at every column joined to other than two."""
    tris = _sheet_tris(P, tris)
    used = np.unique(tris.reshape(-1))
    if used.size < 2:
        return []
    col = _columns(P[used, :2], weld)
    cmap = dict(zip(used.tolist(), col.tolist(), strict=True))
    n = int(col.max()) + 1
    xy, cnt = np.zeros((n, 2)), np.zeros(n)
    lo, hi = np.full(n, np.inf), np.full(n, -np.inf)
    np.add.at(xy, col, P[used, :2])
    np.add.at(cnt, col, 1.0)
    np.minimum.at(lo, col, P[used, 2])
    np.maximum.at(hi, col, P[used, 2])
    xy /= cnt[:, None]
    adj: dict[int, set] = {i: set() for i in range(n)}
    for a, b, c in tris.tolist():
        ca, cb, cc = cmap[a], cmap[b], cmap[c]
        for i, j in ((ca, cb), (cb, cc), (ca, cc)):
            if i != j:
                adj[i].add(j)
                adj[j].add(i)
    out = []
    for chain, closed in _chains(adj):
        pts = [(round(float(xy[i, 0]), 3), round(float(xy[i, 1]), 3)) for i in chain]
        length = sum(math.dist(a, b) for a, b in zip(pts, pts[1:], strict=False))
        if closed and len(pts) > 2:
            length += math.dist(pts[-1], pts[0])
        if length >= min_run:
            out.append((tuple(pts), tuple(float(lo[i]) for i in chain),
                        tuple(float(hi[i]) for i in chain), closed))
    return out


#: a triangle whose plan area is under this share of its own area is
#: a SHEET triangle (stands vertical); a cap, a sloped top or a post's
#: lid is not read as the fence's foot
_SHEET_PLAN_SHARE = 0.05


def _sheet_tris(P: np.ndarray, tris: np.ndarray) -> np.ndarray:
    """The rows of ``tris`` that stand vertical (:data:`_SHEET_PLAN_SHARE`)."""
    if tris.size == 0:
        return tris.reshape(0, 3)
    a, b, c = P[tris[:, 0]], P[tris[:, 1]], P[tris[:, 2]]
    full = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    plan = 0.5 * np.abs((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1])
                        - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1]))
    return tris[(full > 0.0) & (plan <= _SHEET_PLAN_SHARE * full)]


def _columns(xy: np.ndarray, weld: float) -> np.ndarray:
    """A column label per plan point: points within ``weld`` of one
    another, transitively, are one column (labels dense from 0, in order
    of first appearance)."""
    from scipy.spatial import cKDTree

    from ..geom.union_find import find_root
    parent = list(range(len(xy)))
    for i, j in sorted(cKDTree(xy).query_pairs(weld)):
        ri, rj = find_root(parent, i), find_root(parent, j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)
    labels: dict[int, int] = {}
    return np.array([labels.setdefault(find_root(parent, i), len(labels))
                     for i in range(len(xy))], dtype=np.int64)


def _walk(adj: dict[int, set], seen: set, s: int, nxt: int, stop_at_branch: bool) -> list[int]:
    """The chain from ``s`` through ``nxt`` over unseen joins, marking
    them seen; it stops at a node of degree other than two (when
    ``stop_at_branch``), or where no unseen join is left."""
    chain, prev, cur = [s], s, nxt
    seen.update({(s, nxt), (nxt, s)})
    while True:
        if cur == s:
            return chain
        chain.append(cur)
        if stop_at_branch and len(adj[cur]) != 2:
            return chain
        step = next((j for j in sorted(adj[cur]) if j != prev and (cur, j) not in seen), None)
        if step is None:
            return chain
        seen.update({(cur, step), (step, cur)})
        prev, cur = cur, step


def _chains(adj: dict[int, set]) -> list[tuple[list[int], bool]]:
    """The column graph cut into chains at every node of degree other
    than two; what remains is rings.  Deterministic (lowest node first)."""
    seen: set[tuple[int, int]] = set()
    out: list[tuple[list[int], bool]] = []
    for s in sorted(i for i, nb in adj.items() if len(nb) != 2 and nb):
        for nxt in sorted(adj[s]):
            if (s, nxt) not in seen:
                out.append((_walk(adj, seen, s, nxt, True), False))
    for s in sorted(adj):
        for nxt in sorted(adj[s]):
            if (s, nxt) not in seen:
                out.append((_walk(adj, seen, s, nxt, False), True))
    return out
