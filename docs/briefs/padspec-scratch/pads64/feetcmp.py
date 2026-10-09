"""pads64 scratch: obj8_split_report --json feet_in rows of several arms side by side (site r 60 m and the whole pad).
usage: feetcmp.py name=FEET.json ..."""
import json, sys
arms = [(a.split("=", 1)[0], json.load(open(a.split("=", 1)[1]))) for a in sys.argv[1:]]
rows = {}
for n, d in arms:
    for r in d["feet_in"]:
        s = r["site"]; rows.setdefault((r["unit"], s["lat"], s["lon"]), {})[n] = r
    c = d.get("census") or {}
    print(n, "COCKPIT:", {k: (v.get("n") if isinstance(v, dict) else v) for k, v in c.items() if "critical" in k} or list(c)[:8])
print(f"{'pad@site':38s} " + " | ".join(f"{n:>30s}" for n, _ in arms))
for (u, la, lo), by in rows.items():
    cell = lambda r: (f"{r['site']['within_0_3']:4d}/{r['site']['feet']:<4d} fl {r['site']['floating']:3d} bu {r['site']['buried']:3d} w {r['site']['worst']['float'] if r['site'].get('worst') else 0:+.2f}" if r else "-")
    print(f"{u + '@' + str(la) + ',' + str(lo):38s} " + " | ".join(f"{cell(by.get(n)):>30s}" for n, _ in arms))
print("whole pad (feet within 0.3 / feet; bodies within / bodies):")
seen = set()
for (u, la, lo), by in rows.items():
    if u in seen: continue
    seen.add(u)
    cell = lambda r: (f"{r['pad']['within_0_3']:5d}/{r['pad']['feet']:<5d} b {r['pad']['bodies_within']:3d}/{r['pad']['bodies']:<3d} w {r['pad']['worst']['float'] if r['pad'].get('worst') else 0:+.2f}" if r else "-")
    print(f"{u:38s} " + " | ".join(f"{cell(by.get(n)):>30s}" for n, _ in arms))
