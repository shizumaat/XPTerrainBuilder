"""THE VERTICAL DROP ON THE ROAD'S LOW SIDE (owner RULINGS 2026-10-20d;
spec ``docs/specs/road-edge-drop-spec.md`` R4, round 3 D4).

The owner: the road "should be graded to road rules, and reach the high
terminals, and then allow a vertical drop on the low side so the buildings
on that side can be seated on the ground".  A road a pad fill runs to
(``planar/fill_road``) climbs to the fill by §37 (6) alone: its kerb
vertices on the fill are mouths at the fill's highest predicted level
(``airport/road_ramp.road_ramp_targets``).  Where its OTHER kerb then stands
over the ground beside it, that kerb is a DROP, in two derivations:

* :func:`drop_runs` (the BASE derive): the HIGH-KERB RUNS — stretches of the
  ring of a road face sharing a fill's ring, whose vertices lie on road faces
  only (the low side STANDS OFF, so the mesh has two lines to build the drop
  between), are not on the fill, and whose §37 target stands more than
  ``[cockpit] visual_m`` over their own DEM.  Published as
  ``road_terrace['drop']``; :func:`drop_edges` is its reading.  The last
  stage reads it: a station never lies on a drop edge
  (``pipeline/late_stage.late_stations``), and a gap piece never follows one
  (``constraints/gap_follow``) — the low side keeps its own ground.
* :func:`road_edge_walls` (the LATE derive, when the gap pieces stand
  across the stand-off): one ``road_terrace['wall']`` record per run with a
  LOWER side — the groundside non-rigid, non-road vertices across the
  stand-off within ``[service] retaining_wall_reach_m`` — of the shape the
  pack walls take (``airport/road_ramp.wall_terraces``), ``retains`` set, so
  the machinery that reads them reads these: the pair rows across the line
  are released (``constraints/road_ramp.wall_release``), the bending is cut
  (``solve/wall_cut``), the lower side is bounded at the wall's height
  (``_wall_step_rows``) and the census is told the step
  (``pipeline/publication.wall_terrace_joints``).  The riser is the gap
  sheet's own stand-off (``EPS_M`` to ``BAND_M`` off the kerb); no new face.
  A run with no lower side (no gap piece beyond the kerb) declares nothing:
  the terrain drapes from the kerb to the DEM (``road_edge_no_lower``)."""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import is_rigid_role, role_side
from ..model.planar import PlanarMap
from ..model.platform import fill_levels

__all__ = ["drop_runs", "drop_edges", "road_edge_walls", "LABEL_PREFIX",
           "EPS_M", "BAND_M"]

#: the record label's head: ``road_edge:<road ref>#<k>``
LABEL_PREFIX = "road_edge:"
#: the wall line's offset band off the kerb, metres: inside the gap
#: pieces' stand-off (MEASURED HECA: nearest 0.50 m, median 2.1 m)
EPS_M = 0.05
BAND_M = 0.4


def _runs(ring: list[int], ok: _t.Callable[[int], bool]) -> list[list[int]]:
    """The maximal runs of consecutive ``ok`` vertices of the closed
    ``ring`` (two or more vertices each)."""
    n = len(ring)
    flags = [ok(v) for v in ring]
    if all(flags):
        return [ring + ring[:1]] if n >= 2 else []
    start = next(i for i in range(n) if not flags[i])
    out, cur = [], []
    for k in range(1, n + 1):
        i = (start + k) % n
        if flags[i]:
            cur.append(ring[i])
        elif cur:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return [r for r in out if len(r) >= 2]


def _road_ring_vertices(pm: PlanarMap, roads) -> set[int]:
    return {v for f in pm.faces.values() if f.role in roads
            for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)}


def drop_runs(pm: PlanarMap, law: Law, targets: _t.Mapping[int, float],
              counts: dict | None = None) -> list[dict[str, _t.Any]]:
    """THE HIGH-KERB RUNS (module docstring): ``[{"face", "ref", "run"}]``,
    ``run`` the run's vertex ids in ring order, of every road face sharing a
    landing's ring (``model.platform.fill_levels``)."""
    from .road_ramp import _road_roles
    fills = fill_levels(pm)
    if not fills or not targets:
        return []
    fill_v = set().union(*(r["vertices"] for r in fills.values()))
    roads = _road_roles(law)
    visual = float(law.tables.emit.cockpit.visual_m)
    V, F = pm.vertices, pm.faces

    def high(v: int) -> bool:
        t, dz = targets.get(v), V[v].dem_z
        return (t is not None and dz is not None and v not in fill_v
                and all(F[g].role in roads for g in V[v].incident_faces)
                and t - float(dz) > visual)

    out: list[dict[str, _t.Any]] = []
    for f in sorted(F.values(), key=lambda q: q.id):
        if f.role not in roads:
            continue
        cycles = [list(pm.ring_vertices(c)) for c in (f.ring, *f.holes)]
        if fill_v.isdisjoint(v for c in cycles for v in c):
            continue
        for cyc in cycles:
            out.extend({"face": f.id, "ref": str(f.ref), "run": run}
                       for run in _runs(cyc, high))
    if counts is not None:
        counts["road_drop_runs"] = len(out)
        counts["road_drop_vertices"] = len({v for r in out for v in r["run"]})
    return out


def drop_edges(planar: _t.Any) -> frozenset[frozenset[int]]:
    """The edges of the published drop runs (``road_terrace['drop']``) as
    unordered vertex pairs — the edges no station lies on and no gap piece
    follows."""
    runs = (getattr(planar, "road_terrace", None) or {}).get("drop") or ()
    return frozenset(frozenset((a, b)) for r in runs
                     for a, b in zip(r["run"], r["run"][1:], strict=False))


def _lower_side(pm: PlanarMap, law: Law, roads) -> tuple[list[int], _t.Any]:
    """The candidate LOWER vertices (groundside, non-rigid, off every road
    ring) and their point tree."""
    V, F = pm.vertices, pm.faces
    road_v = _road_ring_vertices(pm, roads)
    ids = sorted(v for v in V if v not in road_v and V[v].dem_z is not None
                 and V[v].incident_faces
                 and all(role_side(law, F[g].role) == "groundside"
                         and not is_rigid_role(law, F[g].role)
                         for g in V[v].incident_faces))
    return ids, (STRtree([Point(V[v].xy) for v in ids]) if ids else None)


def _face_poly(pm: PlanarMap, f) -> Polygon:
    V = pm.vertices
    cycles = [list(pm.ring_vertices(c)) for c in (f.ring, *f.holes)]
    g = Polygon([V[v].xy for v in cycles[0]], [[V[v].xy for v in c] for c in cycles[1:]])
    return g if g.is_valid else g.buffer(0.0)


def road_edge_walls(pm: PlanarMap, law: Law, runs: _t.Sequence[_t.Mapping],
                    targets: _t.Mapping[int, float], reach_m: float,
                    counts: dict | None = None) -> list[dict[str, _t.Any]]:
    """One wall record per drop run (:func:`drop_runs`) with a LOWER side
    across the stand-off (module docstring)."""
    from .road_ramp import _road_roles
    if not runs:
        return []
    V, F = pm.vertices, pm.faces
    visual = float(law.tables.emit.cockpit.visual_m)
    ids, tree = _lower_side(pm, law, _road_roles(law))
    out: list[dict[str, _t.Any]] = []
    stat = {"no_lower": 0}
    faces: dict[int, Polygon] = {}
    for r in runs:
        run = [v for v in r["run"] if v in V]
        if len(run) < 2 or r["face"] not in F or tree is None:
            stat["no_lower"] += 1
            continue
        face = faces.setdefault(r["face"], _face_poly(pm, F[r["face"]]))
        line = LineString([V[v].xy for v in run])
        band = line.buffer(BAND_M, cap_style=2).difference(face.buffer(EPS_M))
        parts = [g for g in getattr(band, "geoms", [band])
                 if g.geom_type == "Polygon" and not g.is_empty]
        top = max(float(targets.get(v, V[v].dem_z or 0.0)) for v in run)
        lower = []
        if parts:
            band = max(parts, key=lambda g: g.area)
            for j in tree.query(line.buffer(reach_m), predicate="intersects"):
                w = ids[int(j)]
                if float(V[w].dem_z) >= top - visual:
                    continue
                p = V[w].xy
                u = min(run, key=lambda q: (Point(V[q].xy).distance(Point(p)), q))
                if LineString([p, V[u].xy]).intersects(band) and not face.contains(Point(p)):
                    lower.append(w)
        if not lower:
            stat["no_lower"] += 1
            continue
        h = top - min(float(V[w].dem_z) for w in lower)
        out.append({"line": [tuple(c) for c in band.exterior.coords],
                    "height_m": round(h, 3),
                    "label": f"{LABEL_PREFIX}{r['ref']}#{len(out)}",
                    "retains": True, "mouth": False, "road_edge": True,
                    "upper": list(run), "lower": sorted(lower),
                    "lots": [], "pairs": []})
    if counts is not None:
        counts["road_edge_no_lower"] = stat["no_lower"]
        counts["road_edge_walls"] = len(out)
    return out
