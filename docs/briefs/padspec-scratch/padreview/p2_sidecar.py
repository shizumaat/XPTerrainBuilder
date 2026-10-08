"""padreview P2: cluster_pads + platforms records for named refs."""
import json, sys
side = sys.argv[1]; refs = sys.argv[2].split(",")
d = json.load(open(side))
for key in ("cluster_pads", "platforms"):
    for r in d.get(key, []):
        if r.get("ref") in refs or r.get("pad_ref") in refs:
            rr = {k: v for k, v in r.items() if k not in ("released_ll", "reach_bands_contacts", "contacts_ll", "ring_ll", "outline_ll")}
            print(key, json.dumps(rr, default=str)[:1200])
