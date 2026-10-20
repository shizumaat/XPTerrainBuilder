"""THE ROAD REACHES THE HIGH SIDE — the derivation (owner RULINGS
2026-10-20d; spec ``docs/specs/road-edge-drop-spec.md`` R3).

A road meets a landing (a viaduct's deck landing, or a pad fill run to the
road, ``planar/fill_road``) at its kerb: the shared vertices are landing
vertices, held at the block's datum + the landing's ``y``.  This module
reads, for every road-owned vertex, its distance ``d`` from each landing's
FRONTAGE along the road's own edges (``road_ramp._graph``, the graph §37 (6)
walks, over every road ring vertex) and publishes ``{vertex: ((landing ref, block, y, d), ...)}`` as
``road_terrace['fill_ramp']`` — out to the station where the design ramp off
the landing's highest predicted level (``model.platform.fill_levels``'
``z_hi``) has met that vertex's DEM.  The rows are
``constraints/fill_road``'s: one derivation, its readers read the channel."""
from __future__ import annotations

import heapq
import typing as _t

from ..law import Law
from ..model.planar import PlanarMap
from ..model.platform import fill_levels

#: ``planar/landing_runout.RUNOUT_REF_PREFIX``, quoted (``airport`` may not
#: import ``planar``)
RUNOUT_REF_PREFIX = "runout:"

__all__ = ["fill_ramp", "frontage_distances"]


def frontage_distances(adj: _t.Mapping[int, list[tuple[int, float]]],
                       front: _t.AbstractSet[int], limit: float) -> dict[int, float]:
    """Shortest distance along ``adj`` from any ``front`` vertex, out to
    ``limit``."""
    dist = {v: 0.0 for v in front}
    heap = [(0.0, v) for v in sorted(front)]
    while heap:
        d, v = heapq.heappop(heap)
        if d > dist.get(v, float("inf")):
            continue
        for w, ln in adj.get(v, ()):
            nd = d + ln
            if nd <= limit and nd < dist.get(w, float("inf")):
                dist[w] = nd
                heapq.heappush(heap, (nd, w))
    return dist


def fill_ramp(pm: PlanarMap, law: Law, owned: _t.Mapping[int, str],
              counts: dict | None = None) -> dict[int, tuple]:
    """The channel (module docstring) over ``owned`` (the road-owned
    vertices, ``road_ramp._owned``)."""
    from .road_ramp import _graph, _road_roles
    levels = fill_levels(pm)
    g = float(law.tables.emit.road_contact.ramp_grade)
    if not levels or not owned or g <= 0.0:
        return {}
    roads = _road_roles(law)
    V, F = pm.vertices, pm.faces
    dems = [float(V[v].dem_z) for v in owned if V[v].dem_z is not None]
    if not dems:
        return {}
    # THE WALK IS EVERY ROAD RING VERTEX: a kerb vertex a collar or a ribbon
    # shares is no road-owned vertex, and a walk over the owned ones alone
    # stops there (MEASURED HECA: 5 vertices reached off 6 frontages)
    road_v = {v for f in F.values() if f.role in roads
              for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)}
    # a landing's RUN-OUT strip keeps its own law (``constraints/ramp_runout``,
    # off its foot's straight axis): a second ramp off another frontage of
    # the same block contested it (MEASURED HECA, lane l1088 it2b: 44 rows
    # relaxed by up to 6.05 m beside the run-outs)
    runout_v = {v for f in F.values() if str(f.ref).startswith(RUNOUT_REF_PREFIX)
                for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)}
    out: dict[int, list] = {}
    n = 0
    for ref, rec in sorted(levels.items()):
        front = {v for v in rec["vertices"]
                 if any(F[f].role in roads for f in V[v].incident_faces)}
        if not front:
            continue
        n += 1
        limit = max(0.0, (rec["z_hi"] - min(dems)) / g)
        dist = frontage_distances(_graph(pm, road_v), front, limit)
        for v, d in sorted(dist.items()):
            if v in front or v not in owned or v in runout_v or V[v].dem_z is None:
                continue
            if rec["z_hi"] - g * d > float(V[v].dem_z):
                out.setdefault(v, []).append((ref, rec["block"], rec["y"], round(d, 3)))
    if counts is not None:
        counts["fill_ramp_landings"] = n
        counts["fill_ramp_vertices"] = len(out)
    return {v: tuple(x) for v, x in out.items()}
