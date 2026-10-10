"""pads62 scratch: two census JSONs — adjudicated airside, CRITICAL motion/visual, per-family airside counts that differ."""
import json, sys
def rd(p):
    d = json.load(open(p)); d = d[0] if isinstance(d, list) else d
    d = d.get("reports", [d])[0] if "reports" in d else d
    return d
a, b = rd(sys.argv[1]), rd(sys.argv[2])
c = lambda d, k: (d["cockpit"][k]["n"], d["cockpit"][k].get("by_family"), d["cockpit"][k].get("worst_m"))
print("adjudicated airside_for_acceptance", a["adjudicated_airside_for_acceptance"], "->", b["adjudicated_airside_for_acceptance"])
for k in ("critical_motion", "critical_visual"):
    x, y = c(a, k), c(b, k); print(k, x[0], "->", y[0], "| worst", x[2], "->", y[2]); print("    ", x[1], "\n     ->", y[1])
fa = {f["family"]: f for f in a["families"]}; fb = {f["family"]: f for f in b["families"]}
for k in sorted(set(fa) | set(fb)):
    x, y = fa.get(k, {}), fb.get(k, {})
    if (x.get("airside", 0), x.get("n", 0)) != (y.get("airside", 0), y.get("n", 0)):
        print(f"   {k:28s} airside {x.get('airside',0):6d} -> {y.get('airside',0):6d}   n {x.get('n',0):6d} -> {y.get('n',0):6d}   worst {x.get('worst_m')} -> {y.get('worst_m')}")
