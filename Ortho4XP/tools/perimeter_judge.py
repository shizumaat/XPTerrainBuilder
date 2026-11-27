"""THE PERIMETER JUDGE (owner RULINGS 2026-11-25m (2)/(3); spec
``docs/specs/underside-height-map-20261125.md`` §3 G4, §7 step 3) -- the
library ``tools/underside_census.py --perimeter`` reads.

On one SOLVED replay (``v2_solve_replay --solved-out``: the map, ``z``,
the airport with its underside maps): every graded group's perimeter
(``airport/unit_perimeter.perimeters`` on the solved pads) judged on the
drawn surface --

* IN THE PATCH: each station on a map face reads the solved surface there
  (each face triangulated on its own ring, the way the mesh takes it); its
  offset from the station's interval, by the face's role; ``airside`` and
  ``building`` stations apart (airside is never pulled: 25n (2) lists them);
(or the build's own records, a rebake plan's ``perimeters``)
* OUTSIDE (FREE): the tile raster the build grades -- the airport's DEM at
  the tile posting (:data:`POSTING_DEG`), the patch's faces frozen --
  before and after ``airport/perimeter_grade.perimeter_grade``, judged by
  ``perimeter_grade.judge`` (free / boundary / far / over, the interiors
  left uncut).

Reads only; writes nothing."""
from __future__ import annotations

import types
import typing as _t

import numpy as np

__all__ = ["POSTING_DEG", "GROUNDSIDE", "solved_pads", "surface_at", "patch_sampler",
           "in_patch", "free_raster", "judge_solved"]

#: the tile raster's posting (degrees; Ortho4XP's 1 m-class DEM grid)
POSTING_DEG = 1.0 / 11016.0


def solved_pads(pm, law, z) -> tuple:
    """The solved surface's object pads, read as the object stage reads them
    (``placement_read.pads_rims_from_graded_doc`` on ``emit/graded``)."""
    from auto_patch_v2.airport.placement_read import pads_rims_from_graded_doc
    from auto_patch_v2.emit.graded import graded_surface
    from auto_patch_v2.solve.api import Status
    sol = types.SimpleNamespace(z=tuple(float(v) for v in z), iterations=0,
                                status=Status.OPTIMAL, residual=None)
    return pads_rims_from_graded_doc(graded_surface(pm, law, sol, (0.0, 0.0)).to_dict())[0]


def surface_at(pm, z, xs, ys) -> tuple[np.ndarray, np.ndarray]:
    """``(zs, roles)`` of the solved surface at frame points ``(xs, ys)``:
    linear over the map face holding each point, triangulated on its own
    ring (``geom/triangulate.face_triangles``, the mesh's way); ``nan`` /
    ``""`` off every face (outside the patch).  Only the faces whose box
    meets the points' box are triangulated."""
    import shapely
    from auto_patch_v2.geom.triangulate import face_triangles
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    out = np.full(len(xs), np.nan)
    role = np.full(len(xs), "", dtype=object)
    if not len(xs):
        return out, role
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    xy = {v: vx.xy for v, vx in pm.vertices.items()}
    tri, rl = [], []
    for f in pm.faces.values():
        ring = list(pm.ring_vertices(f.ring))
        if len(ring) < 3:
            continue
        fx = [xy[v][0] for v in ring]
        fy = [xy[v][1] for v in ring]
        if max(fx) < x0 or min(fx) > x1 or max(fy) < y0 or min(fy) > y1:
            continue
        for t in face_triangles(xy, ring, [list(pm.ring_vertices(h)) for h in f.holes]):
            tri.append(t)
            rl.append(str(f.role))
    if not tri:
        return out, role
    T = np.asarray(tri, int)
    P = np.array([[xy[int(v)] for v in t] for t in T], float)        # (k, 3, 2)
    Z = np.array([[float(z[int(v)]) for v in t] for t in T], float)
    boxes = shapely.box(P[:, :, 0].min(1), P[:, :, 1].min(1), P[:, :, 0].max(1),
                        P[:, :, 1].max(1))
    pi, ti = shapely.STRtree(boxes).query(shapely.points(xs, ys), predicate="intersects")
    a, b, c = P[ti, 0], P[ti, 1], P[ti, 2]
    det = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    ok = np.abs(det) > 1e-12
    det = np.where(ok, det, 1.0)
    px, py = xs[pi], ys[pi]
    w1 = ((b[:, 1] - c[:, 1]) * (px - c[:, 0]) + (c[:, 0] - b[:, 0]) * (py - c[:, 1])) / det
    w2 = ((c[:, 1] - a[:, 1]) * (px - c[:, 0]) + (a[:, 0] - c[:, 0]) * (py - c[:, 1])) / det
    w3 = 1.0 - w1 - w2
    inside = ok & (w1 >= -1e-9) & (w2 >= -1e-9) & (w3 >= -1e-9)
    pi, ti, w1, w2, w3 = pi[inside], ti[inside], w1[inside], w2[inside], w3[inside]
    first = np.unique(pi, return_index=True)[1]
    pi, ti = pi[first], ti[first]
    out[pi] = w1[first] * Z[ti, 0] + w2[first] * Z[ti, 1] + w3[first] * Z[ti, 2]
    role[pi] = np.asarray(rl, dtype=object)[ti]
    return out, role


def patch_sampler(pm, z) -> _t.Callable:
    """``f(xs, ys) -> (zs, roles)``: :func:`surface_at` bound to one map."""
    return lambda xs, ys: surface_at(pm, z, xs, ys)


def in_patch(pers, sample) -> list[dict[str, _t.Any]]:
    """Per perimeter its in-patch stations' offsets by role (module doc):
    ``{role: [stations, over, p50 offset]}``, and the groundside total."""
    from auto_patch_v2.airport.unit_perimeter import GAP_M, off_interval
    out = []
    for p in pers:
        zs, role = sample(p.e, p.n)
        off = off_interval(zs, p.lo, p.hi)
        inside = np.isfinite(zs) & ~p.far
        by: dict[str, list] = {}
        for r in sorted({str(x) for x in role[inside]}):
            k = inside & (role == r)
            by[r] = [int(k.sum()), int(np.sum(k & (np.abs(off) > GAP_M))),
                     round(float(np.median(off[k])), 2)]
        ground = inside & np.isin(role.astype(str), list(GROUNDSIDE))
        out.append({"unit": p.unit, "row": p.row, "why": p.why, "z0": round(p.z0, 3),
                    "in_patch": int(inside.sum()), "by_role": by,
                    "groundside": int(ground.sum()),
                    "groundside_over": int(np.sum(ground & (np.abs(off) > GAP_M)))})
    return out


#: the groundside pavement roles the in-patch bar counts (spec §7 step 3:
#: lots and roads; ``law/precedence.toml`` side ``groundside``, no structure)
GROUNDSIDE = ("parking_lot", "service_road", "service_junction", "groundside_pavement")


def free_raster(airport, pm, pers):
    """``(raster, to_xy, to_ll)``: the tile raster round ``pers`` (the
    airport DEM at :data:`POSTING_DEG`, the patch's faces frozen) and its
    frame's projector in ``terrain_fill``'s convention."""
    import shapely
    from auto_patch_v2.airport import terrain_fill as _tf
    from auto_patch_v2.airport.underside_composite import dem_many
    from auto_patch_v2.airport.unit_perimeter import projector
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    to_xy, to_ll = projector(airport.frame)
    xs = np.concatenate([np.r_[p.e, p.plan_e] for p in pers])
    ys = np.concatenate([np.r_[p.n, p.plan_n] for p in pers])
    pad = 2.0 * 60.0
    lo, la = to_ll(np.r_[xs.min() - pad, xs.max() + pad], np.r_[ys.min() - pad, ys.max() + pad])
    c0, c1 = np.floor(lo.min() / POSTING_DEG), np.ceil(lo.max() / POSTING_DEG)
    r0, r1 = np.floor(la.min() / POSTING_DEG), np.ceil(la.max() / POSTING_DEG)
    lons = np.arange(c0, c1 + 1) * POSTING_DEG
    lats = np.arange(r1, r0 - 1, -1) * POSTING_DEG
    LO, LA = np.meshgrid(lons, lats)
    X, Y = to_xy(LO.ravel(), LA.ravel())
    alt = np.asarray(dem_many(airport.dem)(X, Y), float).reshape(LO.shape)
    faces = []
    for f in pm.faces.values():
        ring = [pm.vertices[v].xy for v in pm.ring_vertices(f.ring)]
        if len(ring) >= 3:
            g = Polygon(ring)
            faces.append(g if g.is_valid else g.buffer(0.0))
    patch = unary_union(faces)
    shapely.prepare(patch)

    def frozen(rows, cols, lons_, lats_):
        x, y = to_xy(lons_, lats_)
        return shapely.contains_xy(patch, x, y)
    return _tf.Raster(alt, float(lons[0]), float(lats[0]), POSTING_DEG, POSTING_DEG,
                      frozen), to_xy, to_ll


def judge_solved(solved: _t.Mapping[str, _t.Any], law, storey_m: float = 3.0,
                 records: "_t.Sequence[_t.Mapping[str, _t.Any]] | None" = None
                 ) -> dict[str, _t.Any]:
    """The whole judge (module doc) of one ``--solved-out`` pickle's dict;
    ``records``: the build's own perimeter records (a rebake plan's
    ``perimeters``, ``RebakePlan.perimeters``) in place of the population
    read again here (which cannot know the rows another seat takes)."""
    from auto_patch_v2.airport import perimeter_grade as _pg
    from auto_patch_v2.airport import unit_perimeter as _up
    pm, z, airport = solved["pm"], solved["z"], solved["airport"]
    if records is not None:
        to_xy = _up.projector(airport.frame)[0]
        pers = [_up.from_dict(r, to_xy) for r in records]
    else:
        pers = _up.perimeters(airport, solved_pads(pm, law, z), storey_m=storey_m)
    if not pers:
        return {"perimeters": [], "in_patch": [], "free_before": [], "free_after": []}
    patch = in_patch(pers, patch_sampler(pm, z))
    raster, to_xy, to_ll = free_raster(airport, pm, pers)
    before = _pg.judge(raster, to_xy, to_ll, pers)
    grade = _pg.perimeter_grade(raster, to_xy, to_ll, pers)
    after = _pg.judge(raster, to_xy, to_ll, pers)
    part = getattr(airport, "partition", None)
    res = {str(m.id): str(m.resource).rsplit("/", 1)[-1]
           for u in (getattr(part, "units", ()) or ()) for m in u.members}
    return {"perimeters": [{"unit": p.unit, "row": p.row, "res": res.get(p.row, ""),
                            "why": p.why, "z0": round(p.z0, 3),
                            "stations": int(len(p.e)), "far": int(p.far.sum())}
                           for p in pers],
            "in_patch": patch, "free_before": before, "free_after": after, "grade": grade}
