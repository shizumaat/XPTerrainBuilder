"""pads60 scratch: hard_conflict rows by tier, arm A vs B; the rows of the runway/taxi/apron tiers in B that A has not (by row + site at 6 dp)."""
import json, sys, collections
A = json.load(open(sys.argv[1])); B = json.load(open(sys.argv[2]))
def key(r): return (r.get("tier"), r["row"], round(r["site"][0], 6), round(r["site"][1], 6))
ka = collections.Counter(key(r) for r in A.get("hard_conflict", [])); 
for n, d in (("A", A), ("B", B)):
    print(n, len(d.get("hard_conflict", [])), dict(collections.Counter(r.get("tier") for r in d.get("hard_conflict", []))))
kb = collections.Counter(key(r) for r in B.get("hard_conflict", []))
for tier in ("runway", "taxi", "apron"):
    new = [r for r in B.get("hard_conflict", []) if r.get("tier") == tier and key(r) not in ka]
    gone = [r for r in A.get("hard_conflict", []) if r.get("tier") == tier and key(r) not in kb]
    print(f"tier {tier}: new {len(new)} gone {len(gone)}")
    for r in sorted(new, key=lambda r: -r["s_m"]): print("   NEW ", round(r["s_m"], 3), r["row"][:60], [round(x, 5) for x in r["site"]], r.get("inputs", [])[:3])
    for r in sorted(gone, key=lambda r: -r["s_m"]): print("   GONE", round(r["s_m"], 3), r["row"][:60], [round(x, 5) for x in r["site"]], r.get("inputs", [])[:3])
