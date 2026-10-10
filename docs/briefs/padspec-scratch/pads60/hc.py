"""pads60 scratch: sidecar reads — landings, hard_conflict by tier and on landings, platforms warned/released."""
import json, sys, collections
for path in sys.argv[1:]:
    d = json.load(open(path))
    print("==", path)
    print(" landings:", [(l["ref"], l["y"], l["level"], l["deck"].split("/")[-1]) for l in d.get("landings", [])] if "landings" in d else "(no key)")
    hc = d.get("hard_conflict") or []
    tier = collections.Counter(str(r.get("tier")) for r in hc)
    print(" hard_conflict", len(hc), dict(tier))
    def onl(r): return "landing" in json.dumps(r)
    L = [r for r in hc if onl(r)]
    print("  on landings:", len(L), "max s_m", max((r.get("s_m", 0) for r in L), default=0))
    nl = [r for r in hc if not onl(r)]
    by = collections.Counter((str(r.get("tier")), str(r.get("law", r.get("family", "")))[:60]) for r in nl)
    for k, n in by.most_common(8): print("  ", n, k)
    P = d.get("platforms") or []
    print(" platforms", len(P), "landing recs", sum(1 for p in P if "/landing" in str(p.get("ref"))),
          "released>0", [(p["ref"], p.get("released"), p.get("released_max_m"), p.get("warned")) for p in P if (p.get("released") or 0) > 0])
    for p in P:
        if p.get("warned"): print("  WARNED:", p.get("warning"))
