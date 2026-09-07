"""Lane v2terrace3 replay: the 07g territory stage on the captured HECA pass-1
map (HECA_t3_capture.pkl), the filtered constraint set, ONE weighted hard
solve (the ablation's arm, docs/specs/auto-patch-v2/heca-sag-ablation/
ablate_heca_pin.py) — v1444 / bow vs round 3 (107.89 / -10.38), the label
boundary at the 07e site, the joint counts by family, the joint KML."""
import os, sys, pickle, time, math, json, dataclasses as _dc
ROOT = "/Users/noah/XPTerrainBuilder/.claude/worktrees/v2terrace3/Ortho4XP"
SP = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/b89d7ebd-242d-4009-8bda-cfdad9b8aad0/scratchpad"
os.chdir(ROOT); sys.path.insert(0, ROOT + "/src")
import numpy as np
from shapely.geometry import LineString, Point
prog = open(f"{ROOT}/scratch/.progress", "a")
def stamp(s): prog.write(f"{time.strftime('%H:%M:%S')} replay: {s}\n"); prog.flush(); print(s, flush=True)
stamp("START")
from auto_patch_v2.law import Law
from auto_patch_v2.pipeline.territory import territory_stage, territory_constraints, joint_steps
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS, weights_under_law
from auto_patch_v2.solve import Options, Status
from auto_patch_v2.solve.tiers import solve_law_ordered
from auto_patch_v2.constraints.routes import RIDGE_KIND
cap = pickle.load(open(f"{SP}/HECA_t3_capture.pkl", "rb")); airport, cl, pm = cap["airport"], cap["cl"], cap["pm"]
law = Law.for_airport("HECA")
t = time.perf_counter()
stage = territory_stage(pm, law, airport, cl, out=stamp)
stamp(f"territory stage {time.perf_counter()-t:.1f} s")
pm = stage.pm; terr = stage.terr; st = terr.stats
to_xy, to_ll = airport.frame.transformers(); ox, oy = to_xy(31.412022, 30.127729)
site = Point(ox, oy)
best = min(((LineString(j.points).distance(site), j) for j in stage.joints), key=lambda t: t[0], default=(None, None))
stamp(f"SITE 07e: nearest contour {best[0] if best[0] is None else round(best[0],1)} m  (contour {None if best[1] is None else best[1].id}, {None if best[1] is None else round(best[1].length_m)} m, roles {None if best[1] is None else best[1].roles})")
for j in sorted(stage.joints, key=lambda j: -j.length_m)[:12]:
    stamp(f"  contour {j.id}: {j.length_m:.0f} m, pairs {len(j.pairs)}, roles {j.roles}, site {LineString(j.points).distance(site):.0f} m")
stamp("pairs (disagreeing): " + json.dumps([p for p in st.pairs if p[6]][:12]))
stamp("floor-only pairs: " + json.dumps([p for p in st.pairs if not p[6] and p[5] > p[4]][:8]))
t = time.perf_counter()
cs, counts, walls = territory_constraints(pm, law, airport, stage)
stamp(f"constraints {time.perf_counter()-t:.1f} s: {cs.counts()}  dropped {json.dumps(stage.dropped)}  bands withdrawn {stage.bands_withdrawn}  flats straddling {stage.flats_straddling}")
w = _dc.replace(weights_under_law(DEFAULT_WEIGHTS, law), lexicographic=None) if hasattr(DEFAULT_WEIGHTS, "lexicographic") else weights_under_law(DEFAULT_WEIGHTS, law)
def bow_05c(z):
    for b in pm.breaklines.values():
        if b.kind != RIDGE_KIND or "05C" not in str(b.ref): continue
        vs = b.vertices(pm)
        rw = next(r for r in airport.runways if "05C" in r.id)
        e0, e1 = rw.ends; L = math.dist(e0.xy, e1.xy)
        ux, uy = (e1.xy[0]-e0.xy[0])/L, (e1.xy[1]-e0.xy[1])/L
        worst = None
        for v in vs:
            x, y = pm.vertices[v].xy; s = (x-e0.xy[0])*ux + (y-e0.xy[1])*uy
            line = e0.threshold_elev_m + (e1.threshold_elev_m - e0.threshold_elev_m) * s / L
            dz = z[v] - line
            if worst is None or dz < worst[0]: worst = (dz, s, v, z[v])
        return worst
t = time.perf_counter()
size = {}
sol, tier_rep = solve_law_ordered(pm, cs, law, w, Options(diagnose_iis=False), size_out=size)
wall = time.perf_counter() - t
stamp(f"solve {sol.status} {wall:.0f} s {sol.message[:100]}  LP {size}")
stamp("tiers: " + tier_rep.line())
if tier_rep.failure: stamp("FAILURE " + str(tier_rep.failure))
if sol.status in (Status.OPTIMAL, Status.FEASIBLE):
    z = np.asarray(sol.z, float); b = bow_05c(z)
    stamp(f"RESULT bow 05C/23C {b[0]:+.2f} m at s={b[1]:.0f} (v{b[2]} z {b[3]:.2f}); v1444 z {z[1444]:.3f} (dem {pm.vertices[1444].dem_z:.2f})  [round 3: 107.89 / -10.38; 07a target ~109.3 / -6.5..-7]")
    js = joint_steps(pm, law, stage, z)
    stamp("joint steps by roles: " + json.dumps(js["by_roles"]))
    stamp("road steps: " + json.dumps(js["roads"][:10]))
    stamp("contours: " + json.dumps(sorted(js["contours"], key=lambda c: -c["step_m"])[:10]))
    pickle.dump({"z": z, "stage_stats": _dc.asdict(st), "dropped": stage.dropped, "joints": [(j.id, j.points_ll, len(j.pairs), j.length_m, j.roles) for j in stage.joints], "edges": stage.edges, "label": terr.label}, open(f"{SP}/HECA_t3_replay.pkl", "wb"))
    # the joint KML
    os.makedirs(f"{SP}/v2terrace3_kml", exist_ok=True)
    kml = ['<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>HECA 07g label-boundary joints (replay)</name>',
           '<Style id="big"><LineStyle><color>ff0000ff</color><width>5</width></LineStyle></Style>',
           '<Style id="mid"><LineStyle><color>ff00a5ff</color><width>4</width></LineStyle></Style>',
           '<Style id="small"><LineStyle><color>ff00ff00</color><width>3</width></LineStyle></Style>',
           f'<Placemark><name>07e site</name><Point><coordinates>31.412022,30.127729,0</coordinates></Point></Placemark>']
    steps = {c["id"]: c["step_m"] for c in js["contours"]}
    for j in stage.joints:
        s_ = steps.get(j.id, 0.0); st_ = "big" if s_ > 2.0 else ("mid" if s_ > 0.5 else "small")
        kml.append(f'<Placemark><name>joint {j.id}: step {s_:.2f} m, {j.length_m:.0f} m, {"/".join(j.roles)}, {len(j.pairs)} pairs</name><styleUrl>#{st_}</styleUrl><LineString><coordinates>' + " ".join(f"{lo:.7f},{la:.7f},0" for la, lo in j.points_ll) + '</coordinates></LineString></Placemark>')
    kml.append('</Document></kml>')
    open(f"{SP}/v2terrace3_kml/HECA_label_joints_replay.kml", "w").write("\n".join(kml))
    stamp(f"KML {SP}/v2terrace3_kml/HECA_label_joints_replay.kml")
stamp("EXIT")
