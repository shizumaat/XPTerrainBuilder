"""osmnear.py PATCH.osm LAT,LON R — the patch's own nodes within R m of the site: alt_abs and the ways (ref / role)
each is on (a read of the emitted patch; late-stage pieces included)."""
import collections
import math
import sys
import xml.etree.ElementTree as ET


def main(a):
    lat, lon = map(float, a[1].split(",")); R = float(a[2])
    root = ET.parse(a[0]).getroot()
    k = math.cos(math.radians(lat)) * 111320.0
    near = {}
    for n in root.iter("node"):
        la, lo = float(n.get("lat")), float(n.get("lon"))
        d = math.hypot((la - lat) * 111320.0, (lo - lon) * k)
        if d <= R:
            z = next((t.get("v") for t in n.iter("tag") if t.get("k") == "alt_abs"), None)
            near[n.get("id")] = (d, la, lo, z)
    on = collections.defaultdict(list)
    for w in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in w.iter("tag")}
        lab = f"{tags.get('role') or tags.get('o4_feature') or tags.get('aeroway')}:{tags.get('ref') or w.get('id')}"
        for nd in w.iter("nd"):
            if nd.get("ref") in near:
                on[nd.get("ref")].append(lab)
    for i, (d, la, lo, z) in sorted(near.items(), key=lambda kv: kv[1][0]):
        print(f"  n{i} d {d:5.1f} {la:.8f}, {lo:.8f} z {z} {sorted(set(on[i]))}")


if __name__ == "__main__":
    main(sys.argv[1:])
