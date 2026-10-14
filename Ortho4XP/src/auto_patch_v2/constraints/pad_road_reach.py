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
rest is what the road's grade is released for (``step_m``; 13e: no step).
An end where the road LEAVES the patch is no constant (its join is released
and the ramp runs on inside the patch, ``classify/pad_road_exit``), so it
never binds here.

THE ORDER (13e, 13f): (1) the ramp at the least grade inside the cap —
nothing here; (2) ONLY A FREE-STANDING PAD SHIFTS (:func:`free_standing_pads`,
:func:`pad_shifts`, :func:`shift_pads`): one rigid pad, the least amount,
inside ``pad_shift_max_m``; a pad with other pavement beside it stays;
(3) what is still out of reach is released above the cap over the whole run
(:func:`pad_grade_release`) and published as a lifted cap on those faces
(``PlanarMap.pad_road_released`` -> ``pipeline/publication.lifted_caps``).
"""
from __future__ import annotations

import dataclasses as _dc
import heapq
import typing as _t

from ..law import Law
from ..law.tables import is_rigid_role, role_cap
from ..model.constraints import ConstraintSet, Diff
from ..model.planar import PlanarMap, face_edge_ids, pad_road_faces

#: the released cap stands this far (relative) over the least grade that
#: reaches, so the straight ramp is strictly inside it
RELEASE_SLACK = 1e-3
#: the ruling head of the cross-fall rows, which the release never touches
_TRANSVERSE = "road_cross_section"

__all__ = ["pad_road_reach", "pad_grade_release", "RELEASE_SLACK",
           "free_standing_pads", "pad_shifts", "shift_pads"]


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
    wide = 2.0 * float(law.tables.emit.road_profile.lane_width_m)
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
                # an end nearer than the road is WIDE stands BESIDE the pad
                # across the road, not along it: no ramp runs there (the
                # two levels are each other's wall with or without a road
                # — MEASURED SPJC: a lot 3.9 m over building24's pad, 2.4 m
                # away through the road between them, read as 161 %)
                if qpad == pad or q not in dist or dist[q] <= wide:
                    continue
                rise = float(fixed[q]) - float(fixed[src[q]])
                rem = max(0.0, abs(rise) - cap * dist[q])
                rec = {"pad": pad, "road": refs, "far": name, "far_v": int(q),
                       "faces": sorted(int(f.id) for f in comp),
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


def pad_grade_release(planar: PlanarMap, cs: ConstraintSet,
                      reach: _t.Sequence[_t.Mapping], design_head: str
                      ) -> tuple[ConstraintSet, list[dict]]:
    """13e: on every pad|road network of ``reach`` whose least grade is over
    the road cap, each LONGITUDINAL cap row between two of its vertices
    (a ``Diff`` that is not a cross-fall row) is widened to that grade, and
    its ramp design rows (``design_head``, built at the design grade) leave
    — between two constants the sheet's own bending lays the one straight
    ramp.  ``(set, [{pad, road, grade, run_m, rise_m, faces, rows}])``."""
    need: dict[int, float] = {}
    out: list[dict] = []
    E, F = planar.edges, planar.faces
    for r in reach:
        if not r["remainder_m"]:
            continue
        vs = {v for f in r["faces"] for e in face_edge_ids(F[f]) for v in (E[e].a, E[e].b)}
        g = float(r["grade"]) * (1.0 + RELEASE_SLACK)
        for v in vs:
            need[v] = max(need.get(v, 0.0), g)
        out.append({"pad": r["pad"], "road": list(r["road"]), "grade": r["grade"],
                    "run_m": r["run_m"], "rise_m": r["rise_m"], "far": r["far"],
                    "far_v": r["far_v"], "faces": list(r["faces"]), "rows": 0})
    if not need:
        return cs, out
    rows, n = [], 0
    for row in cs.rows():
        head = str(row.source.ruling)
        if isinstance(row, Diff) and row.a in need and row.b in need \
                and not head.startswith(_TRANSVERSE):
            g = min(need[row.a], need[row.b])
            if row.cap < g:
                row = _dc.replace(row, cap=g)
                n += 1
        elif head == design_head and any(v in need for v, _c in getattr(row, "terms", ())):
            continue
        rows.append(row)
    for rec in out:
        rec["rows"] = n
    return ConstraintSet.from_rows(rows), out


def _pad_of(ref) -> str:
    return str(ref).split("#")[0]


def free_standing_pads(planar: PlanarMap, law: Law) -> frozenset[str]:
    """THE PADS THAT MAY SHIFT FOR A ROAD (owner RULINGS 2026-10-13f: "only
    a free-standing pad shifts"; a pad welded to a lot, an apron or other
    pavement stays).  A pad is free-standing when NO value-carrying face
    but its own and its pad roads' stands within ``[design] pad_frontage_m``
    of it — the radius beyond which a pad and a cell have no relation
    (``classify/pad_touch``).  Geometry only: nothing is asked of the pad
    but what stands beside it."""
    import shapely
    from shapely.strtree import STRtree
    from ..law.tables import is_value_role
    road_ids = {f.id for f in pad_road_faces(planar)}
    V = planar.vertices

    def poly(f):
        return shapely.polygons([V[v].xy for v in planar.ring_vertices(f.ring)])
    pads: dict[str, list] = {}
    others, names = [], []
    for f in planar.faces.values():
        if f.id in road_ids or len(planar.ring_vertices(f.ring)) < 3:
            continue
        if is_rigid_role(law, f.role):
            pads.setdefault(_pad_of(f.ref), []).append(poly(f))
        if is_value_role(law, f.role):
            others.append(poly(f))
            names.append(_pad_of(f.ref) if is_rigid_role(law, f.role) else None)
    if not pads:
        return frozenset()
    reach = float(law.tables.emit.design.pad_frontage_m)
    tree = STRtree(others) if others else None
    free = set()
    for pad, parts in pads.items():
        hit = tree.query(parts, predicate="dwithin", distance=reach)[1].tolist() \
            if tree is not None else []
        if all(names[j] == pad for j in hit):
            free.add(pad)
    return frozenset(free)


def pad_shifts(reach: _t.Sequence[_t.Mapping], free: _t.AbstractSet[str]
               ) -> dict[str, float]:
    """13d step 2 as 13f settles it: ``{pad: its rigid shift}`` — for a
    FREE-STANDING pad whose road cannot reach inside the cap, the largest
    ``shift_m`` its roads ask (each already the remainder inside
    ``pad_shift_max_m``), when they all ask the same way.  Two roads asking
    opposite ways leave the pad where it is: a shift for one is a longer
    climb for the other."""
    ask: dict[str, list[float]] = {}
    for r in reach:
        if r["remainder_m"] and r["pad"] in free:
            ask.setdefault(r["pad"], []).append(float(r["shift_m"]))
    return {pad: max(a, key=abs) for pad, a in sorted(ask.items())
            if all(x > 0.0 for x in a) or all(x < 0.0 for x in a)}


def shift_pads(planar: PlanarMap, law: Law, fixed: dict[int, float],
               shifts: _t.Mapping[str, float]) -> dict[str, int]:
    """Each pad of ``shifts`` moved AS ONE RIGID PAD: every constant of
    ``fixed`` (in place) on a face of that pad takes the pad's shift.
    ``{pad: vertices moved}``."""
    moved: dict[str, set[int]] = {}
    for f in planar.faces.values():
        pad = _pad_of(f.ref)
        if pad in shifts and is_rigid_role(law, f.role):
            moved.setdefault(pad, set()).update(
                v for cyc in (f.ring, *f.holes) for v in planar.ring_vertices(cyc)
                if v in fixed)
    for pad, vs in moved.items():
        for v in vs:
            fixed[v] = float(fixed[v]) + float(shifts[pad])
    return {pad: len(vs) for pad, vs in sorted(moved.items())}
