import sys, re, collections
import xml.etree.ElementTree as ET
def rims(p):
    out = {}; alt = {}
    for ev, el in ET.iterparse(p):
        if el.tag == "node":
            alt[el.get("id")] = float(el.get("alt")) if el.get("alt") else None   # may be a tag
            for t in el.findall("tag"):
                if t.get("k") in ("alt", "ele"): alt[el.get("id")] = float(t.get("v"))
        elif el.tag == "way":
            tg = {t.get("k"): t.get("v") for t in el.findall("tag")}
            if tg.get("o4_feature") == "structure_rim":
                nds = [n.get("ref") for n in el.findall("nd")]
                zs = [alt.get(n) for n in dict.fromkeys(nds)]
                zs = [z for z in zs if z is not None]
                out.setdefault(tg.get("ref"), []).append((len(set(nds)), round(min(zs), 2) if zs else None, round(max(zs), 2) if zs else None))
    return out
R = [rims(p) for p in sys.argv[1:]]
print("structure_rim ways:", [sum(len(v) for v in r.values()) for r in R])
for ref in sorted(set().union(*R), key=str):
    v = [sorted(r.get(ref, [])) for r in R]
    if any(x != v[0] for x in v) or ref in ("basin_wall:0", "basin_wall:3", "basin_wall:4"):
        print(" ", ref, *v)
print("refs differing from the first:", [sum(1 for ref in set(R[0]) | set(r) if sorted(r.get(ref, [])) != sorted(R[0].get(ref, []))) for r in R])
