"""#2206 twin: the indexed ``nearest_vertex_of_containing_cell`` equals the
full per-call scan it replaced, for random faces and points incl. ties."""
import random
import types

from auto_patch_v2.constraints import geometry as G
from shapely.geometry import Point, Polygon


def _old(planar, vw, v, structure_roles):
    pt = Point(planar.vertices[v].xy)
    best = None
    for fid, cap in vw.caps.items():
        f = planar.faces[fid]
        if cap is None or f.role in structure_roles or f.role == "graded_strip":
            continue
        ring = list(vw.rings[fid])
        if v in ring:
            continue
        poly = Polygon([planar.vertices[u].xy for u in ring])
        if not poly.is_valid or not poly.contains(pt):
            continue
        for u in ring:
            d = pt.distance(Point(planar.vertices[u].xy))
            if best is None or d < best[0]:
                best = (d, u)
    return None if best is None else best[1]


def _world(seed):
    rnd = random.Random(seed)
    verts, faces, caps, rings = {}, {}, {}, {}
    nid = 0

    def vert(x, y):
        nonlocal nid
        verts[nid] = types.SimpleNamespace(xy=(x, y))
        nid += 1
        return nid - 1
    roles = ["taxiway", "apron", "graded_strip", "deck", "runway"]
    for fid in range(40):
        cx, cy = rnd.randint(0, 20), rnd.randint(0, 20)
        s = rnd.choice([1, 2, 3])
        if rnd.random() < 0.15:     # a bow-tie: invalid, must be skipped
            ring = [vert(cx, cy), vert(cx + s, cy + s), vert(cx + s, cy), vert(cx, cy + s)]
        else:                        # integer squares: overlaps and ties
            ring = [vert(cx, cy), vert(cx + s, cy), vert(cx + s, cy + s), vert(cx, cy + s)]
        faces[fid] = types.SimpleNamespace(role=rnd.choice(roles))
        caps[fid] = None if rnd.random() < 0.1 else 1.0
        rings[fid] = tuple(ring)
    probes = [vert(rnd.randint(0, 22) + rnd.choice([0, 0.5]),
                   rnd.randint(0, 22) + rnd.choice([0, 0.5])) for _ in range(300)]
    planar = types.SimpleNamespace(vertices=verts, faces=faces)
    vw = types.SimpleNamespace(caps=caps, rings=rings)
    return planar, vw, probes + list(range(0, nid - 300, 3))


def test_indexed_equals_full_scan():
    for seed in range(12):
        planar, vw, vs = _world(seed)
        for v in vs:
            assert G.nearest_vertex_of_containing_cell(planar, vw, v, {"deck"}) \
                == _old(planar, vw, v, {"deck"}), (seed, v)
