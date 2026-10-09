import pickle, sys
sys.path[:0] = ["src", "."]
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree
from auto_patch_v2.model import planar as mp
d = pickle.load(open(sys.argv[1], "rb"))
to_ll = d["airport"].frame.transformers()[1]
def off(g, r): return g.buffer(r, join_style="mitre", mitre_limit=2.0)
for name in ("cl0", "cl"):
    cl = d[name]
    allc = [(c, Polygon(c.ring, c.holes)) for c in cl.cells]
    standing = [q for c, q in allc if c.role == "apron" and not mp.is_gap_apron_ref(c.ref)]
    others = [(c, q) for c, q in allc if c.role != "apron"]
    otree = STRtree([q for _c, q in others])
    tree = STRtree(standing)
    print(name)
    for c, part in allc:
        if not mp.is_gap_apron_ref(c.ref): continue
        near = unary_union([standing[int(j)] for j in tree.query(off(part, 2.0), predicate="intersects")])
        both = part.union(near)
        gap = unary_union([g for g in getattr(off(off(both, 1.0), -1.0).difference(both),'geoms',[]) if g.distance(part)<=1e-3 and g.distance(near)<=1e-3] or [Polygon()])
        print(f"  {c.ref:12s} {c.evidence['gap_ref']:7s} area {part.area:8.1f} between {gap.area:7.2f}")
        for g in sorted((g for g in getattr(gap, "geoms", [gap]) if not g.is_empty and g.area > 0.3), key=lambda g: -g.area)[:4]:
            rp = g.representative_point()
            nb = sorted(((round(q.distance(g), 2), oc.ref, oc.role) for oc, q in (others[int(j)] for j in otree.query(g.buffer(3.0), predicate="intersects")) if oc.ref != c.ref))[:4]
            print(f"      {g.area:6.2f} m2 at %.7f, %.7f  len {g.length:.1f} nearest non-apron: {nb}" % to_ll(rp.x, rp.y))
