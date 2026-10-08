"""jetspec: read a base/bays arm pair — per held block the plateau (area, ring vertices on the datum),
hard_conflict by tier, verify families, stands on the plateau. usage: python arm_read.py ICAO"""
import json, sys, glob
from collections import Counter
icao = sys.argv[1]
S = "/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/jetspec"
for arm in ("base", "bays"):
    d = f"{S}/arm_{arm}_{icao}/emit"
    ax = json.load(open(f"{d}/{icao}_auto.patch.osm.axes.json"))
    gp = glob.glob(f"{d}/**/{icao}.graded.json", recursive=True) + glob.glob(f"{d}/*.graded.json")
    g = json.load(open(gp[0])) if gp else None
    print(f"== {arm} {icao}: graded {gp[0] if gp else None}")
    V = {v[0]: v for v in g["vertices"]} if g else {}
    dat = {p["ref"]: p for p in ax["platforms"]}
    plat = {}
    if g:
        for f in g["faces"]:
            r = str(f.get("ref")); 
            if "#plateau:" in r:
                b = r.split("#plateau:")[1]; plat.setdefault(b, []).append(f)
    for b, fs in sorted(plat.items(), key=lambda kv: -len(kv[1])):
        p = dat.get(b, {}); D = p.get("datum")
        zs = [V[i][3] for f in fs for i in f["ring"]]
        dz = [z - D for z in zs] if (D is not None and zs) else [0.0]
        print(f"   {b:18s} datum {D} plateau faces {len(fs):3d} ring v {len(zs):5d} within0.02 {sum(1 for x in dz if abs(x)<=0.02):5d} within0.3 {sum(1 for x in dz if abs(x)<=0.3):5d} dz {min(dz):+.2f}/{max(dz):+.2f} sidecar area {p.get('plateau_area_m2')} src {p.get('stand_zone_source')} welded {p.get('welded')} released {p.get('released')} warned {p.get('warned')}")
    hc = ax.get("hard_conflict") or []
    print("   hard_conflict by tier:", dict(Counter(r.get("tier") for r in hc)), "over 0.2 m:", sum(1 for r in hc if (r.get("s_m") or 0) > 0.2))
    rep = glob.glob(f"{d}/**/{icao}.report.json", recursive=True)
    if rep:
        v = json.load(open(rep[0])).get("verify", {}).get("by_family", {})
        print("   verify:", {k: v[k] for k in sorted(v) if v[k]})
    print("   platforms:", len(ax["platforms"]), "warned", sum(1 for p in ax["platforms"] if p.get("warned")))
