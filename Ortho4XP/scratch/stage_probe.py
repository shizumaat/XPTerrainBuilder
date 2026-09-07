import os, sys, pickle, time, json, dataclasses as _dc
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2terrace3/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src")
from shapely.geometry import LineString, Point
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline.territory import territory_stage
cap = pickle.load(open(f"{SP}/HECA_t3_capture.pkl", "rb")); airport, cl, pm = cap["airport"], cap["cl"], cap["pm"]
law = Law.for_airport("HECA")
stage = territory_stage(pm, law, airport, cl, out=print)
terr = stage.terr
to_xy, to_ll = airport.frame.transformers(); site = Point(to_xy(31.412022, 30.127729))
best = min(((LineString(j.points).distance(site), j) for j in stage.joints), key=lambda t: t[0], default=(None, None))
print("SITE nearest contour", None if best[0] is None else round(best[0],1), "m")
for v in (10228, 10159, 10564, 10765, 10154):
    print(v, "label", terr.label.get(v), "path", terr.path_m.get(v), "contact", v in terr.contacts, "band", stage.bands.get(v), "faces", [pm.faces[f].role+"#"+str(f) for f in pm.vertices[v].incident_faces])
print("pairs joint:", [p for p in terr.stats.pairs if p[6]])
pickle.dump(stage, open(f"{SP}/HECA_t3_stage.pkl", "wb"))
