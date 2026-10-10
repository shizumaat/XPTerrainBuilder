"""pads63 scratch: the seat read per held block of a sidecar — datum, the pair-graph interval I0 (reach_band0) and its
gap, the route reach intersection, released welds, binding anchors; and the heads the pad-tier relaxations stand against.
usage: seatread.py SIDECAR.axes.json [--all]"""
import json, sys, collections
sc = json.load(open(sys.argv[1])); every = "--all" in sys.argv
P = sc.get("platforms") or []
n_rel = sum(int(p.get("released") or 0) for p in P)
print(f"blocks {len(P)}  released welds {n_rel}  pads releasing {sum(1 for p in P if p.get('released'))}  "
      f"I0 empty {sum(1 for p in P if p.get('reach_empty'))}  reach_isect empty {sum(1 for p in P if p.get('reach_isect_empty'))}  "
      f"warned {sum(1 for p in P if p.get('warned'))}  widened pads {sum(1 for p in P if p.get('weld_widened'))}")
for p in P:
    if not (every or p.get("released") or p.get("reach_empty") or p.get("reach_isect_empty") or p.get("weld_widened")):
        continue
    print(f"- {p['ref']} unit {p.get('unit')} block {p.get('block')}/{p.get('blocks')} at {p.get('centroid_ll')} {p.get('pad_m2')} m2: "
          f"datum {p.get('datum')} median {p.get('datum_median')} chosen {p.get('datum_chosen')}; I0 {p.get('reach_band0')} gap {p.get('reach_gap0_m')}; "
          f"reach_isect {p.get('reach_isect')} empty {p.get('reach_isect_empty')}; welds {p.get('held_contacts')} released {p.get('released')} "
          f"max {p.get('released_max_m')} spread {p.get('released_spread_m')}; widened {p.get('weld_widened')}")
    for s in ("lo", "hi"):
        b = p.get(f"reach_{s}_binding")
        if b: print(f"    {s} binding: contact {b['contact']} <- anchor {b['anchor']} runway {b['anchor_runway']} hops {b['hops']}")
    if p.get("released_ll"): print("    released at", p["released_ll"][:8])
ag = collections.Counter(); tiers = collections.Counter()
for r in sc.get("hard_conflict") or []:
    tiers[r.get("tier")] += 1
    if r.get("tier") == "pad" and "frontage_hold" in str(r.get("row")):
        for k, v in (r.get("against") or {}).items(): ag[k] += 1
print("hard_conflict by tier", dict(tiers)); print("pad frontage_hold relaxations stand against (rows naming the head):", dict(ag.most_common(12)))
