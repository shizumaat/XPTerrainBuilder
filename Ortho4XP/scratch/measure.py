"""Territory chords on the captured pass-1 HECA map (lane v2terrace3)."""
import os, sys, pickle, time, math, dataclasses as _dc, json, shapely, numpy as np
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2terrace3/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src")
icao = sys.argv[1] if len(sys.argv) > 1 else "HECA"
from auto_patch_v2.law import Law
from auto_patch_v2.constraints.no_step import reach_band_values
import auto_patch_v2.planar.territories as T
cap = pickle.load(open(f"{SP}/{icao}_t3_capture.pkl", "rb")); airport, cl, pm = cap["airport"], cap["cl"], cap["pm"]
law = Law.for_airport(icao)
t = time.perf_counter(); bands = reach_band_values(pm, law, airport); print("routes+reach", round(time.perf_counter()-t, 1), "reached", len(bands), flush=True)
t = time.perf_counter(); cl2, st = T.territory_cuts(pm, law, airport, cl, bands); print("territory_cuts", round(time.perf_counter()-t, 1), flush=True)
d = _dc.asdict(st); chords = d.pop("chords"); pairs = d.pop("pairs"); print(json.dumps(d))
print("disagreeing pairs (top by gap):", sorted([p for p in pairs if p[2] > p[4]], key=lambda p: -(p[2]-p[4]))[:8])
print("floor-only:", [p for p in pairs if p[5] > p[4] >= p[2]][:8])
to_xy, _ = airport.frame.transformers(); ox, oy = to_xy(31.412022, 30.127729)
from shapely.geometry import LineString, Point
for c in chords:
    ml = shapely.multilinestrings([np.asarray(sg) for sg in c["segments"]])
    print(f"CHORD round {c['round']} {c['length_m']:.1f} m x{c['n_segments']}  pair {c['contact_1']}({c['ceiling_1']:.1f}) | {c['contact_2']}({c['ceiling_2']:.1f}) gap {c['gap_m']:.1f} d {c['d_inshape_m']:.0f} hold {c['hold_m']:.1f}  site {ml.distance(Point(ox, oy)):.1f} m  ll {[[round(v,6) for v in pt] for sg in c['ll'] for pt in sg]}  cut {c['cells_cut']}")

    to_xy, _ = airport.frame.transformers(); ox, oy = to_xy(31.412022, 30.127729)
    from shapely.geometry import LineString, Point
    print("   distance of chord to the 07e site:", round(shapely.multilinestrings([np.asarray(sg) for sg in c["segments"]]).distance(Point(ox, oy)), 1), "m")
print("cells", len(cl.cells), "->", len(cl2.cells))
pickle.dump({"cl2": cl2, "stats": st, "bands": bands}, open(f"{SP}/{icao}_t3_cut.pkl", "wb"))
