"""THE VERTICAL DROP ON THE ROAD'S LOW SIDE (owner RULINGS 2026-10-20d;
spec ``docs/specs/road-edge-drop-spec.md`` R4).

The owner: the road "should be graded to road rules, and reach the high
terminals, and then allow a vertical drop on the low side so the buildings
on that side can be seated on the ground".  A road a pad fill runs to
(``planar/fill_road``) reaches the fill's level (``constraints/fill_road``);
where its kerb then stands over the ground beside it, that kerb is a
DECLARED WALL — one ``road_terrace['wall']`` record per kerb run, of the
shape the pack walls already take (``airport/road_ramp.wall_terraces``), so
the machinery that reads them reads these: the pair rows across the line are
released (``constraints/road_ramp.wall_release``), the bending is cut
(``solve/wall_cut``), the lower side is bounded at the wall's height
(``_wall_step_rows``), a gap piece does not follow the road across it
(``constraints/gap_follow``) and the census is told the step
(``pipeline/publication.wall_terrace_joints``).

A run is a stretch of the road's ring whose vertices lie on road faces only
(no other face shares them — the low side STANDS OFF, so the mesh has two
lines to build the wall between), are not on the fill, and whose §37 target
stands more than ``[cockpit] visual_m`` over their own DEM.  Its LOWER side
is the vertices of the groundside faces across it within ``[service]
retaining_wall_reach_m``: not road, not rigid, below the run's level.  The
wall's line is the run offset outward into the stand-off (``EPS_M`` to
``BAND_M`` off the kerb), so no row along the road crosses it.  A run whose
low side SHARES the kerb has no second line to step across: counted
``shared_kerb``, never declared (it needs the riser of #951)."""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import is_rigid_role, role_side
from ..model.planar import PlanarMap
from ..model.platform import fill_levels

__all__ = ["road_edge_walls", "LABEL_PREFIX", "is_road_edge_wall", "EPS_M", "BAND_M"]

#: the record label's head: ``road_edge:<road ref>#<k>``
LABEL_PREFIX = "road_edge:"
#: the wall line's offset band off the kerb, metres: inside the gap
#: pieces' stand-off (MEASURED HECA: nearest 0.50 m, median 2.1 m)
EPS_M = 0.05
BAND_M = 0.4


def is_road_edge_wall(rec: _t.Mapping) -> bool:
    """A record of this module's (its ``road_edge`` mark, which
    ``constraints/gap_follow`` reads without importing this layer)."""
    return bool(rec.get("road_edge"))


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


def road_edge_walls(pm: PlanarMap, law: Law, targets: _t.Mapping[int, float],
                    reach_m: float, counts: dict | None = None) -> list[dict[str, _t.Any]]:
    """The R4 wall records (module docstring) of every road face sharing a
    pad fill's ring."""
    from .road_ramp import _road_roles
    fills = fill_levels(pm)
    if not fills or not targets:
        return []
    fill_v = set().union(*(r["vertices"] for r in fills.values()))
    roads = _road_roles(law)
    visual = float(law.tables.emit.cockpit.visual_m)
    V, F = pm.vertices, pm.faces
    road_v = {v for f in F.values() if f.role in roads
              for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)}
    low_ok = {v for v in V if v not in road_v and V[v].dem_z is not None
              and V[v].incident_faces
              and all(role_side(law, F[g].role) == "groundside"
                      and not is_rigid_role(law, F[g].role) for g in V[v].incident_faces)}
    ids = sorted(low_ok)
    tree = STRtree([Point(V[v].xy) for v in ids]) if ids else None
    out: list[dict[str, _t.Any]] = []
    stat = {"runs": 0, "shared_kerb": 0}

    def upper_ok(v: int) -> bool:
        t, dz = targets.get(v), V[v].dem_z
        return (t is not None and dz is not None and v not in fill_v
                and all(F[g].role in roads for g in V[v].incident_faces)
                and t - float(dz) > visual)

    for f in sorted(F.values(), key=lambda q: q.id):
        if f.role not in roads:
            continue
        cycles = [list(pm.ring_vertices(c)) for c in (f.ring, *f.holes)]
        if fill_v.isdisjoint(v for c in cycles for v in c):
            continue
        face = Polygon([V[v].xy for v in cycles[0]],
                       [[V[v].xy for v in c] for c in cycles[1:]])
        face = face if face.is_valid else face.buffer(0.0)
        for cyc in cycles:
            for run in _runs(cyc, upper_ok):
                stat["runs"] += 1
                line = LineString([V[v].xy for v in run])
                band = line.buffer(BAND_M, cap_style=2).difference(face.buffer(EPS_M))
                parts = [g for g in getattr(band, "geoms", [band])
                         if g.geom_type == "Polygon" and not g.is_empty]
                if not parts or tree is None:
                    continue
                band = max(parts, key=lambda g: g.area)
                top = max(targets[v] for v in run)
                near = [ids[int(j)] for j in tree.query(line.buffer(reach_m),
                                                        predicate="intersects")]
                lower = []
                for w in near:
                    if float(V[w].dem_z) >= top - visual:
                        continue
                    p = V[w].xy
                    u = min(run, key=lambda q: (Point(V[q].xy).distance(Point(p)), q))
                    if LineString([p, V[u].xy]).intersects(band) and not face.contains(Point(p)):
                        lower.append(w)
                if not lower:
                    stat["shared_kerb"] += 1
                    continue
                h = top - min(float(V[w].dem_z) for w in lower)
                out.append({"line": [tuple(c) for c in band.exterior.coords],
                            "height_m": round(h, 3),
                            "label": f"{LABEL_PREFIX}{f.ref}#{len(out)}",
                            "retains": True, "mouth": False, "road_edge": True,
                            "upper": list(run), "lower": sorted(lower),
                            "lots": [], "pairs": []})
    if counts is not None:
        counts.update({f"road_edge_{k}": v for k, v in stat.items()})
        counts["road_edge_walls"] = len(out)
    return out
