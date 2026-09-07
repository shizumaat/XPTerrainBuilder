import sys; sys.path.insert(0, "tests/auto_patch_v2"); sys.path.insert(0, "src")
import test_v2terrace3 as T
from auto_patch_v2.law import Law
from shapely.geometry import Polygon
law = Law.for_airport("ZZZZ")
which = sys.argv[1]
cell, cut = T._east(900.0)
if which == "lane":
    apron_w = T.Cell(1, "apron", "apron", T._rect(-150, T.Y0, -11.5, T.Y1), (), None, None, "airside", "apron", {})
    apron_e = T.Cell(5, "apron", "apron", T._rect(11.5, T.Y0, 150, T.Y1), (), None, None, "airside", "apron", {})
    lane = T.Cell(4, "stub", "laneN", T._rect(-11.5, T.Y0, 11.5, T.Y1), (), None, "D", "airside", "taxi", {})
    lane_cut = T.CutLine("taxi_centerline", "laneN", ((0.0, T.Y0), (0.0, T.Y1)))
    airport, pm, stage, ps, cl = T._airport(law, [T.RUNWAY, apron_w, apron_e, T.STUB_W, cell, lane], [T.CUT_W, cut, lane_cut])
else:
    jx = T.Cell(4, "junction", "jx", T._rect(-40, T.Y1, 40, T.Y1 + 30), (), None, "D", "airside", "junction", {})
    road = T.Cell(5, "service_road", "svc", T._rect(-60, T.Y1 + 30, 60, T.Y1 + 42), (), None, None, "airside", "pavement", {})
    airport, pm, stage, ps, cl = T._airport(law, [T.RUNWAY, T.APRON, T.STUB_W, cell, jx, road], [T.CUT_W, cut])
terr = stage.terr
for f in pm.faces.values():
    if f.role in ("graded_strip", "runway") and which != "lane": continue
    ids = list(pm.ring_vertices(f.ring))
    print("FACE", f.id, f.role, f.ref, "n", len(ids), "bounds", [round(v,1) for v in Polygon([pm.vertices[v].xy for v in ids]).bounds], "labels", sorted({terr.label.get(v, -1) for v in ids}))
print(terr.stats.joint_edges_by_roles, "contacts", sorted(terr.contacts))
for c in sorted(terr.contacts): print("  contact", c, pm.vertices[c].xy, stage.bands.get(c))
