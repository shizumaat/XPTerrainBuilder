"""Owner sites by COORDINATE, main vs branch: every way within R m (tools/osm_site.py is the reader).
usage: sites.py MAIN.osm BRANCH.osm [R]"""
import json, subprocess, sys, tempfile, os
SITES = [("#453", 25.2559273, 51.6083381), ("#454", 25.2792668, 51.6001421), ("#455", 25.2762962, 51.5920062),
         ("#450 a", 25.2542342, 51.6213069), ("#450 b", 25.253661, 51.6208155),
         ("#451 a", 25.2536839, 51.6231506), ("#451 b", 25.2539056, 51.6221564), ("#451 c", 25.2963819, 51.6065055),
         ("terminal", 25.259994, 51.6104872), ("cliff 04-Oct", 25.25535, 51.62062)]
main, br = sys.argv[1:3]; R = sys.argv[3] if len(sys.argv) > 3 else "25"
def read(p, lat, lon):
    t = tempfile.mktemp(suffix=".json")
    subprocess.run([sys.executable, "tools/osm_site.py", "--at", f"{lat},{lon}", "--radius", R, "--json", t, p],
                   check=True, capture_output=True)
    d = json.load(open(t)); os.unlink(t)
    out = {}
    for w in d["files"][0]["near"]:
        tg = w["tags"]; k = (tg.get("role") or tg.get("o4_feature") or "?", tg.get("ref", "?"))
        n = 0
        while (k + (n,)) in out: n += 1
        out[k + (n,)] = (w["nodes"], w["alt_min"], w["alt_max"], w["distance_m"])
    return out
for name, lat, lon in SITES:
    a, b = read(main, lat, lon), read(br, lat, lon)
    same = [k for k in a if k in b and a[k] == b[k]]
    zs = [z for v in a.values() for z in v[1:3]]
    print(f"{name:13s} {lat}, {lon}: main {len(a)} ways within {R} m (alt {min(zs) if zs else '-'}..{max(zs) if zs else '-'}); branch {len(b)}; identical (nodes, alt span) {len(same)}")
    for k in sorted(set(a) | set(b)):
        if k in a and k in b and a[k] == b[k]: continue
        print(f"      {'CHANGED' if k in a and k in b else 'ONLY MAIN' if k in a else 'NEW':9s} {k[0]}:{k[1]}  main {a.get(k)}  branch {b.get(k)}   (nodes, alt_min, alt_max, node distance m)")
