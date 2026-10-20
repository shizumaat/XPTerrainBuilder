"""THE BAND'S WALL AGAINST A ROAD, DECLARED (owner RULINGS 2026-10-19a / 19i /
19k / 19l, 2026-10-20c (39); issues #951 / #949 / #1060; spec
``docs/specs/band-road-wall-joint-spec.md`` §8).

A runway / taxi band stands off every groundside road by the stand-off
(``groundside_cutback_m`` + ``snap_margin_m``): a drawn road page as a
groundside cell, and a mapped carriageway through zone 2 by its own cut
(``planar/road_yield``).  The road follows its own ground; across the
stand-off the mesh draws the step between the two as a steep face — the
retaining wall 19i rules, never a bank (15g (B)) and never a ramp (19k).

THE DECLARED LINE, one rule for ribbons and pages alike: the roads'
outline grown by half the stand-off, kept where it lies in no face (in the
stand-off itself) and within one stand-off of a band face.  One
``terrace_joints`` record (``kind`` ``wall_terrace``, shape :data:`LABEL`)
per connected part, declared at the largest step of the census's own
straddling pairs across it (each vertex within the straddle window of the
line paired with its nearest partner on the other side,
``emit.terrace.straddle_perp_m`` / ``straddle_pair_m`` — the window
``check_grade._check_terrace_actual_step`` reads).  A part whose step is
under the elevation materiality floor and the cockpit's visual step is
ground, not a wall, and is dropped.  The census exempts the record from
CRITICAL visual (19l) and from the runway-strip wall check (19i) by its
shape label."""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..model.planar import PlanarMap
from ..model.road_yield import is_band_zone_ref

__all__ = ["band_road_wall_joints", "LABEL"]

#: the shape label the record carries (``tools/check_grade`` quotes it)
LABEL = "band_road_wall"
#: the patch writes elevations to the centimetre (``publication``'s own)
_EMIT_Z_ROUND_M = 0.01
_MITRE = dict(join_style="mitre", mitre_limit=2.0)


def band_road_wall_joints(planar: PlanarMap, law: Law,
                          z: _t.Sequence[float] | None = None
                          ) -> list[dict[str, _t.Any]]:
    """The ``wall_terrace`` records of the band's walls against the roads
    it stands off (module docstring).  Empty before a solve."""
    if z is None:
        return []
    parts = wall_lines(planar, law)
    if not parts:
        return []
    from .ribbon_steps import _to_ll
    to_ll = _to_ll(planar)
    tr = law.tables.emit.terrace
    floor = max(float(law.tables.emit.materiality.elevation_m),
                float(law.tables.emit.cockpit.visual_m))
    steps = straddle_steps(planar, z, parts, float(tr.straddle_perp_m),
                           float(tr.straddle_pair_m))
    out: list[dict[str, _t.Any]] = []
    for line, s in zip(parts, steps, strict=True):
        if s <= floor:
            continue
        declared = round(s + _EMIT_Z_ROUND_M, 4)
        out.append({
            "points": [list(to_ll(x, y)) for x, y in line.coords],
            "step_m": declared, "declared_step_m": declared, "faced": False,
            "kind": "wall_terrace", "faces": [], "shapes": [LABEL],
            "gap": False, "roles": ["graded_strip"], "pairs": 0,
            "length_m": round(float(line.length), 2),
            "height_m": round(s, 3), "emitted_step_m": round(s, 3),
            "agreement_m": 0.0})
    return out


def wall_lines(planar: PlanarMap, law: Law) -> list:
    """The declared line's connected parts (module docstring), plan
    ``LineString``\\ s."""
    import shapely
    from shapely.ops import unary_union

    from ..constraints.roads import road_family_roles
    from ..law.tables import snap_margin_m
    cut = float(law.tables.zones.adjacent_ground.groundside_cutback_m) + snap_margin_m(law)
    roads = set(road_family_roles(law))
    road, band, other = [], [], []
    for f in planar.faces.values():
        g = _poly(planar, f)
        if f.role in roads:
            road.append(g)
        elif f.role == "graded_strip" and is_band_zone_ref(f.ref):
            band.append(g)
        else:
            other.append(g)
    # THE ROAD'S EDGE IS ITS LANES OR ITS DRAWN EDGE, WHICHEVER IS LARGER
    # (owner 39): the drawn faces and the carriageways the bands were cut by
    from shapely.geometry import Polygon
    road.extend(Polygon(ext, holes) for ext, holes in
                (getattr(planar, "road_cut_outlines", ()) or ()))
    if not road or not band:
        return []
    bands = unary_union(band)
    near = bands.buffer(cut, **_MITRE)
    outline = unary_union(road).buffer(0.5 * cut, **_MITRE).boundary.intersection(near)
    if outline.is_empty:
        return []
    faced = unary_union([bands, *road, *[g for g in other if g.intersects(near)]])
    kept = outline.difference(faced)
    if kept.geom_type == "MultiLineString":
        kept = shapely.line_merge(kept)
    return [p for p in shapely.get_parts(kept)
            if p.geom_type == "LineString" and len(p.coords) >= 2 and p.length > 0.0]


def straddle_steps(planar: PlanarMap, z, parts, perp_m: float, pair_m: float
                   ) -> list[float]:
    """Per part, the largest ``|Δz|`` of the census's straddling pairs: every
    face vertex within ``perp_m`` of the part, sided by its nearest segment,
    paired with its nearest partner on the other side within ``pair_m``
    (both directions).  A road the patch has no vertex of stands in at its
    ground (``PlanarMap.road_cut_ground``)."""
    import numpy as np
    from scipy.spatial import cKDTree

    ids = sorted({v for f in planar.faces.values() for c in (f.ring, *f.holes)
                  for v in planar.ring_vertices(c)})
    if not ids:
        return [0.0] * len(parts)
    # the road the core mesh draws where the patch has no vertex of it
    ground = getattr(planar, "road_cut_ground", ()) or ()
    xy = np.array([planar.vertices[v].xy for v in ids] + [(x, y) for x, y, _z in ground],
                  dtype=float)
    zz = np.array([float(z[v]) for v in ids] + [g[2] for g in ground], dtype=float)
    tree = cKDTree(xy)
    out = []
    for p in parts:
        seg = np.asarray(p.coords, dtype=float)
        a, b = seg[:-1], seg[1:]
        cand = sorted({int(i) for c in tree.query_ball_point(
            seg, perp_m + 0.5 * _max_seg(a, b)) for i in c})
        if not cand:
            out.append(0.0)
            continue
        side, dist = _side(xy[cand], a, b)
        keep = (dist <= perp_m) & (side != 0)
        c = np.asarray(cand)[keep]
        sd = side[keep]
        out.append(max(_nearest_dz(xy, zz, c[sd > 0], c[sd < 0], pair_m),
                       _nearest_dz(xy, zz, c[sd < 0], c[sd > 0], pair_m)))
    return out


def _poly(planar: PlanarMap, f):
    from shapely.geometry import Polygon
    ring = [planar.vertices[v].xy for v in planar.ring_vertices(f.ring)]
    holes = [[planar.vertices[v].xy for v in planar.ring_vertices(h)] for h in f.holes]
    g = Polygon(ring, holes)
    return g if g.is_valid else g.buffer(0.0)


def _max_seg(a, b) -> float:
    import numpy as np
    return float(np.max(np.hypot(*(b - a).T))) if len(a) else 0.0


def _side(pts, a, b):
    """Per point, the sign of its side of its NEAREST segment and the
    distance to it (``check_grade``'s reading)."""
    import numpy as np
    import shapely
    from shapely.strtree import STRtree
    segs = shapely.linestrings(np.stack([a, b], axis=1))
    (pi, k), dist = STRtree(segs).query_nearest(shapely.points(pts), return_distance=True,
                                                all_matches=False)
    order = np.argsort(pi)
    k, dist = k[order], dist[order]
    d = (b - a)[k]
    rk = pts - a[k]
    s = d[:, 0] * rk[:, 1] - d[:, 1] * rk[:, 0]
    return np.sign(np.where(np.abs(s) < 1e-12, 0.0, s)), dist


def _nearest_dz(xy, zz, src, dst, pair_m: float) -> float:
    """The largest ``|Δz|`` of each ``src`` vertex to its nearest ``dst``
    vertex within ``pair_m``."""
    import numpy as np
    from scipy.spatial import cKDTree
    if not len(src) or not len(dst):
        return 0.0
    d, j = cKDTree(xy[dst]).query(xy[src], distance_upper_bound=pair_m)
    ok = np.isfinite(d)
    if not ok.any():
        return 0.0
    return float(np.max(np.abs(zz[src[ok]] - zz[dst[j[ok]]])))
