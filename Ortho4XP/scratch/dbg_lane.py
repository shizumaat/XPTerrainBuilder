import sys; sys.path.insert(0, "tests/auto_patch_v2"); sys.path.insert(0, "src")
import test_v2terrace3 as T
from auto_patch_v2.law import Law
import auto_patch_v2.planar.territories as TT
from auto_patch_v2.constraints.no_step import reach_band_values
law = Law.for_airport("ZZZZ")
cell, cut = T._east(900.0)
lane = T.Cell(4, "stub", "laneN", T._rect(-11.5, T.Y0, 11.5, T.Y1), (), None, "D", "airside", "taxi", {})
lane_cut = T.CutLine("taxi_centerline", "laneN", ((0.0, T.Y0), (0.0, T.Y1)))
airport, pm, stage, ps, cl = T._airport(law, [T.RUNWAY, T.APRON, T.STUB_W, cell, lane], [T.CUT_W, cut, lane_cut])
for f in pm.faces.values():
    print("FACE", f.id, f.role, f.ref, len(pm.ring_vertices(f.ring)), [round(v,1) for v in __import__("shapely").geometry.Polygon([pm.vertices[v].xy for v in pm.ring_vertices(f.ring)]).bounds])
bands = reach_band_values(pm, law, airport)
st = TT.reached_stations(pm, bands)
fids = TT._complex_faces(pm, law, st, set())
print("complex faces", fids)
for poly, members in TT._complexes(pm, fids):
    print("COMPLEX area", round(poly.area), "members", members, "bounds", [round(b,1) for b in poly.bounds])
print("stats", stage.terr.stats)
