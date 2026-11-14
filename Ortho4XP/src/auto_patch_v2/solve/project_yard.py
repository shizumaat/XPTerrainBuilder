"""THE FENCE YARD STANDS ON THE FENCE-FOOT PLANE (spec
``2068-fence-grade-spec-A2.md`` F3; the yard is ``classify/fence_yard``'s).

A PROJECTION AFTER THE WHOLE SOLVE, on the final ``z``, as the §52 facade
strips are (``solve/project_strip.project_facade_strips``, which calls
this): every vertex of a ``fenceyard:<k>:<pad>`` face takes

    z = L + plane(x, y) - y_p

with ``plane`` the fence-foot plane the upper level's landing record
carries (``planar/group_up``, ``yard_plane``: the fence's authored base
over the frame), ``y_p`` the storey's base and ``L`` the solved level of
the record's own ``<block>/p<k>`` faces.  The yard mints no row and the
level is read, never written.  A vertex an AIRSIDE-side face carries is
never moved (airside is king); a vertex any other standing face carries
YIELDS too, counted in ``yielded`` (expected 0: the yard was cut off every
cell standing with the §52 stand-off).

THE YARD'S ROADS (spec 2068 A3 R5, "a road inside the yard stands on the
yard's ground"), right after: every FREE vertex of a yard road run
(``constraints/yard_edge.yard_runs``) takes

    z = clamp(L + plane(x, y) - y_p, lo, hi)

``hi`` / ``lo`` the run's slope bounds (``geom/slope_bound``) off its
SOURCES — the fixed vertices of its faces less the level's own — at
``[road_contact] upper_pad_road_grade`` along the shortest path inside the
run's faces.  ``lo > hi`` takes their mean and is counted ``infeasible``
(expected 0).  The level's rim keeps A1 (2) (c)'s declared step."""
from __future__ import annotations

import typing as _t

from ..constraints.yard_edge import YardRun
from ..geom.capped_plane import plane_at
from ..law import Law
from ..law.tables import role_side
from ..model.planar import PlanarMap, face_vertex_set, fence_yard_pad

__all__ = ["project_fence_yards", "run_bounds"]


def project_fence_yards(planar: PlanarMap, law: Law, z: _t.Sequence[float]
                        ) -> "tuple[tuple[float, ...], dict | None]":
    """The new ``z`` and the report, or ``z`` unchanged and ``None`` when
    the map holds no fence yard."""
    yards = [f for f in planar.faces.values() if fence_yard_pad(f.ref) is not None]
    if not yards:
        return tuple(z), None
    lands = getattr(planar.registries, "landings", None) or {}
    by_pad = {str(r.get("pad")): (lv, r) for lv, r in lands.items() if r.get("yard_plane")}
    out = [float(v) for v in z]
    users: set[int] = set()
    airside: set[int] = set()
    levels: dict[str, list[int]] = {}
    for f in planar.faces.values():
        if fence_yard_pad(f.ref) is not None:
            continue
        vs = _face_vertices(planar, f)
        users |= vs
        if role_side(law, f.role) == "airside":
            airside |= vs
        levels.setdefault(str(f.ref), []).extend(vs)
    rep: dict[str, _t.Any] = {"yards": [], "vertices": 0, "yielded": 0, "airside": 0,
                              "no_level": 0}
    done: set[int] = set()
    for f in sorted(yards, key=lambda f: f.id):
        got = by_pad.get(str(fence_yard_pad(f.ref)))
        lv_vs = [v for v in levels.get(got[0], ()) if v < len(out)] if got else []
        if not lv_vs:
            rep["no_level"] += 1
            continue
        lv, rec = got
        L = sum(out[v] for v in lv_vs) / len(lv_vs)
        pl = tuple(float(c) for c in rec["yard_plane"])
        y_p = float(rec.get("y_p", 0.0))
        lo, hi = float("inf"), float("-inf")
        for v in sorted(_face_vertices(planar, f)):
            if v >= len(out) or v in done:
                continue
            done.add(v)
            if v in users:
                rep["airside" if v in airside else "yielded"] += 1
                continue
            x, y = planar.vertices[v].xy
            out[v] = L + float(plane_at(pl, x, y)) - y_p
            lo, hi = min(lo, out[v]), max(hi, out[v])
            rep["vertices"] += 1
        rep["yards"].append({"face": f.id, "ref": f.ref, "level": lv, "L": round(L, 3),
                             "z": [round(lo, 3), round(hi, 3)] if hi >= lo else None})
    rep["runs"] = _project_runs(planar, law, by_pad, levels, out)
    return tuple(out), rep


def run_bounds(planar: PlanarMap, law: Law, run: YardRun, z: _t.Sequence[float]
               ) -> "dict[int, tuple[float, float]]":
    """``{free vertex: (lo, hi)}`` of one yard road ``run``
    (``constraints/yard_edge.YardRun``) off its sources' ``z``."""
    import numpy as np
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    from ..geom.slope_bound import slope_bounds
    vs = sorted(set().union(*(face_vertex_set(planar, planar.faces[f]) for f in run.faces)))
    def ring(r):
        return [planar.vertices[v].xy for v in planar.ring_vertices(r)]
    region = unary_union([Polygon(ring(f.ring), [ring(h) for h in f.holes]).buffer(0.0)
                          for f in (planar.faces[fid] for fid in run.faces)])
    xy = np.array([planar.vertices[v].xy for v in vs], dtype=float)
    ix = {v: i for i, v in enumerate(vs)}
    g = float(law.tables.emit.road_contact.upper_pad_road_grade)
    lo, hi = slope_bounds(xy, region, {ix[v]: float(z[v]) for v in run.sources}, g)
    return {v: (float(lo[ix[v]]), float(hi[ix[v]])) for v in sorted(run.free)}


def _project_runs(planar: PlanarMap, law: Law, by_pad, levels, out: list) -> list[dict]:
    """Stand every yard road run's free vertices on the plane within the
    road grade of its sources (module doc), in place on ``out``."""
    from ..constraints.yard_edge import yard_runs
    recs = {lv: rec for lv, rec in by_pad.values()}
    reps: list[dict] = []
    for run in yard_runs(planar, law):
        rec = recs.get(run.level)
        lv_vs = [v for v in levels.get(run.level, ()) if v < len(out)]
        if rec is None or not lv_vs:
            continue
        L = sum(out[v] for v in lv_vs) / len(lv_vs)
        pl = tuple(float(c) for c in rec["yard_plane"])
        y_p = float(rec.get("y_p", 0.0))
        bounds = run_bounds(planar, law, run, out)
        bad = 0
        for v, (lo, hi) in bounds.items():
            target = L + float(plane_at(pl, *planar.vertices[v].xy)) - y_p
            if lo > hi:
                bad += 1
                out[v] = 0.5 * (lo + hi)
            else:
                out[v] = min(max(target, lo), hi)
        reps.append({"level": run.level, "faces": [str(planar.faces[f].ref) for f in run.faces],
                     "free": len(run.free), "sources": len(run.sources), "infeasible": bad})
    return reps


def _face_vertices(planar: PlanarMap, f) -> set[int]:
    """Every vertex of face ``f``'s rings."""
    return {v for ring in (f.ring, *f.holes) for v in planar.ring_vertices(ring)}
