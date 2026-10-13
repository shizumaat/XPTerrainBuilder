"""CAN THE ROAD REACH THE PAD WITHIN GRADE? (issue #609; owner RULINGS
2026-10-13d "road ramps first, pad takes the remainder, capped").

A pad road (``model.planar.pad_road_faces``) is solved in the last stage
between CONSTANTS: the rim of the pad it is welded to and every other
standing vertex its ring carries (another pad's rim, a lot, the patch's own
ribbon, airside).  Whether a ramp of lawful grade FITS between two of them
is geometry, read before the solve:

    the least grade the road needs = |level difference| / the road's run

the run being the shortest path between the two along the pad roads' own
edges.  Over the road cap (``role_cap(service_road).longitudinal``) no
profile fits, and ``|difference| - cap x run`` is THE REMAINDER — the least
rigid shift of the pad that would let the road reach; ``[road_contact]
pad_shift_max_m`` bounds what the pad may take of it (``shift_m``) and the
rest stands as the road's step (``step_m``).  This module reads them; it
moves nothing.  An end where the road LEAVES the patch is no
constant (its join is released and the core road carries the ramp on,
``road_ramp.pad_ramp_rewrite``), so it never binds here.
"""
from __future__ import annotations

import heapq
import typing as _t

from ..law import Law
from ..law.tables import is_rigid_role, role_cap
from ..model.planar import PlanarMap, face_edge_ids, pad_road_faces

__all__ = ["pad_road_reach"]


def _components(faces, verts: dict[int, set[int]]) -> list[list]:
    """The pad-road faces grouped by shared vertices."""
    by_v: dict[int, list[int]] = {}
    for f in faces:
        for v in verts[f.id]:
            by_v.setdefault(v, []).append(f.id)
    face = {f.id: f for f in faces}
    seen: set[int] = set()
    out = []
    for f in faces:
        if f.id in seen:
            continue
        seen.add(f.id)
        comp, queue = [], [f.id]
        while queue:
            fid = queue.pop()
            comp.append(face[fid])
            for v in verts[fid]:
                for q in by_v[v]:
                    if q not in seen:
                        seen.add(q)
                        queue.append(q)
        out.append(comp)
    return out


def pad_road_reach(planar: PlanarMap, law: Law, fixed: _t.Mapping[int, float]
                   ) -> list[dict]:
    """One record per (pad, pad-road network) whose road meets another
    constant: the WORST far end — ``pad``, ``road`` (the network's refs),
    ``far`` (the standing face there), ``run_m``, ``rise_m`` (far level
    minus the pad's rim level at the near end), ``grade`` (the least the
    road needs), ``cap`` and ``remainder_m`` (signed: the rigid shift of
    the pad toward the far end that lets a cap-grade ramp fit; 0.0 when
    one fits), ``shift_m`` (the remainder inside ``[road_contact]
    pad_shift_max_m``) and ``step_m`` (what is left: the road's step at the
    pad).  ``fixed`` is the last stage's constants."""
    roads = pad_road_faces(planar)
    if not roads:
        return []
    rc = role_cap(law, "service_road")
    cap = float(rc.longitudinal) if rc and rc.longitudinal else 0.0
    most = float(law.tables.emit.road_contact.pad_shift_max_m)
    V, E, F = planar.vertices, planar.edges, planar.faces
    road_ids = {f.id for f in roads}
    verts = {f.id: {v for e in face_edge_ids(f) for v in (E[e].a, E[e].b)}
             for f in roads}

    def owner(v: int) -> tuple[str | None, str]:
        """``(pad ref or None, name of a standing face at v)``."""
        pad, name = None, ""
        for q in V[v].incident_faces:
            f = F.get(q)
            if f is None or q in road_ids:
                continue
            if is_rigid_role(law, f.role):
                pad = str(f.ref).split("#")[0]
            name = name or f"{f.role}:{f.ref}"
        return pad, name

    out: list[dict] = []
    for comp in _components(roads, verts):
        adj: dict[int, list[tuple[int, float]]] = {}
        for f in comp:
            for e in face_edge_ids(f):
                a, b = E[e].a, E[e].b
                (ax, ay), (bx, by) = V[a].xy, V[b].xy
                d = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
                adj.setdefault(a, []).append((b, d))
                adj.setdefault(b, []).append((a, d))
        ends = {v: owner(v) for v in adj if v in fixed}
        pads: dict[str, list[int]] = {}
        for v, (pad, _n) in ends.items():
            if pad:
                pads.setdefault(pad, []).append(v)
        refs = sorted({str(f.ref) for f in comp})
        for pad, rim in sorted(pads.items()):
            dist = {v: 0.0 for v in rim}
            src = {v: v for v in rim}
            heap = [(0.0, v) for v in rim]
            heapq.heapify(heap)
            while heap:
                d, v = heapq.heappop(heap)
                if d > dist[v]:
                    continue
                for w, dw in adj[v]:
                    # a standing vertex ends the road: the run to it counts,
                    # nothing is walked THROUGH it
                    if v in ends and v not in rim:
                        break
                    nd = d + dw
                    if nd < dist.get(w, float("inf")):
                        dist[w], src[w] = nd, src[v]
                        heapq.heappush(heap, (nd, w))
            worst = None
            for q, (qpad, name) in ends.items():
                if qpad == pad or q not in dist or dist[q] <= 0.0:
                    continue
                rise = float(fixed[q]) - float(fixed[src[q]])
                rem = max(0.0, abs(rise) - cap * dist[q])
                rec = {"pad": pad, "road": refs, "far": name, "far_v": int(q),
                       "run_m": round(dist[q], 2), "rise_m": round(rise, 3),
                       "grade": round(abs(rise) / dist[q], 4), "cap": cap,
                       "remainder_m": round(rem if rise > 0 else -rem, 3),
                       "shift_m": round(min(rem, most) * (1 if rise > 0 else -1), 3),
                       "step_m": round(max(0.0, rem - most), 3)}
                if worst is None or (abs(rec["remainder_m"]), rec["grade"]) > \
                        (abs(worst["remainder_m"]), worst["grade"]):
                    worst = rec
            if worst is not None:
                out.append(worst)
    return out
