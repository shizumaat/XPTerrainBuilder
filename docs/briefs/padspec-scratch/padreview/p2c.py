import json, sys, math
f=sys.argv[1]; lat,lon=30.1125123,31.3961245
d=json.load(open(f))
hits=[]
for v in d["platforms"]:
    c=v.get("centroid_ll")
    if c and abs(c[0]-lat)<0.004 and abs(c[1]-lon)<0.004:
        hits.append(v["ref"]); print("PL",json.dumps({a:b for a,b in v.items() if a not in("released_ll","reach_bands_contacts","contacts_ll","warning")},default=str)[:1100])
for v in d["cluster_pads"]:
    if set(v["pads"])&set(hits) or any(h.split("#")[0] in v["pads"] for h in hits):
        print("CP",json.dumps({a:b for a,b in v.items() if "ll" not in a},default=str)[:900])
for v in d.get("pad_refusals",[]):
    if v.get("ref") in hits: print("REF",v)
