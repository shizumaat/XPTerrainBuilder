"""padreview2 C follow-up evidence: for each OTHH deck print, the pieces of the deck's triangles whose authored y
crosses the band ABOUT THE UNIT LEVEL [-B, +B] (not about the object's lowest y): count + plan area, and the
same for the landed lowest-y band."""
import pickle, sys, math
sys.path.insert(0, "src")
from auto_patch_v2.planar import landing as L
from auto_patch_v2.airport import bridge_family as bf
from shapely.geometry import Polygon
from shapely.ops import unary_union
cap = pickle.load(open(sys.argv[1], "rb")); part = cap["airport"].partition
B = L.BAND_M
for p in L._prints(part):
    la0 = p.box[0]; mlat = 111320.0; mlon = 111320.0 * math.cos(math.radians(la0))
    def area(rings):
        polys = []
        for r in rings:
            q = Polygon([((lo) * mlon, (la) * mlat) for la, lo in r])
            if q.is_valid and q.area > 0: polys.append(q)
        if not polys: return 0.0, 0
        u = unary_union(polys); return u.area, (1 if u.geom_type == "Polygon" else len(u.geoms))
    low = [r for r, y in bf.landing_pieces(p, B)]
    a_low, n_low = area(low)
    # band about the unit level: whole triangles whose y-range meets [-B, +B] (no clipping; an upper bound)
    about0 = [t for t, ys in zip(p.tris, p.ys) if min(ys) <= B and max(ys) >= -B]
    a0, n0 = area(about0)
    on0 = [t for t, ys in zip(p.tris, p.ys) if max(ys) - min(ys) < 2 * B and -B <= min(ys) <= B]  # near-flat pieces at the level
    a00, n00 = area(on0)
    print(f"unit {p.unit:3d} {p.key.split('/')[-1]:38s} y {min(y for t in p.ys for y in t):+6.2f}..{max(y for t in p.ys for y in t):+6.2f} | lowest-y band: {a_low:7.1f} m2 {n_low:2d} comp | about-0 any-tri: {a0:7.1f} m2 {n0:2d} comp | flat-at-0 tris: {a00:7.1f} m2 {n00:2d} comp")
