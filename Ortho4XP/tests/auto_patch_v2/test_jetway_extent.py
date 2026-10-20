"""Issue #1082: ``jetways._obj_extent`` places the authored vertices in
numpy and hands GEOS one array; its ring must equal, coordinate for
coordinate, the per-vertex Python placement it replaced."""
from types import SimpleNamespace

import numpy as np
from auto_patch_v2.airport import jetways, obj8
from shapely.geometry import MultiPoint


def _reference(verts, xy, hdg):
    a = obj8.placement_affine(xy, hdg)
    pts = [(a[0] * x + a[1] * z + a[4], a[2] * x + a[3] * z + a[5])
           for x, z in verts[:, [0, 2]].tolist()]
    hull = MultiPoint(pts).convex_hull
    return tuple(hull.exterior.coords)[:-1]


def test_obj_extent_matches_per_vertex_placement():
    rng = np.random.default_rng(1082)
    for dtype in (np.float32, np.float64):
        verts = (rng.normal(size=(5000, 3)) * 7.0).astype(dtype)
        verts[:40] = verts[40:80]                      # authored duplicates
        geom = SimpleNamespace(vertices=verts)
        cache = SimpleNamespace(geometry=lambda _p, g=geom: g)
        for hdg in (0.0, 37.25, 211.9):
            o = SimpleNamespace(resolved_path="j.obj", xy=(1234.5, -987.25),
                                heading_deg=hdg)
            assert jetways._obj_extent(cache, o) == _reference(verts, o.xy, hdg)
