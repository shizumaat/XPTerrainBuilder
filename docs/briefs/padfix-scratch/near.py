"""near.py LAT,LON R GRADED_A.json [GRADED_B.json] — vertices of graded surface A within R m of the site: z in A,
z in B (joined on the 11-dp lat/lon), the faces (role:ref) each stands on.  A read; prices nothing."""
import collections
import json
import math
import sys


def main(a):
    lat, lon = map(float, a[0].split(",")); R = float(a[1])
    g = json.load(open(a[2]))
    zb = {}
    if len(a) > 3:
        zb = {(f"{v[1]:.11f}", f"{v[2]:.11f}"): v[3] for v in json.load(open(a[3]))["vertices"]}
    faces = collections.defaultdict(set)
    for f in g["faces"]:
        for ring in (f["ring"], *f.get("holes", [])):
            for v in ring:
                faces[v].add(f"{f.get('role')}:{f.get('ref')}")
    k = math.cos(math.radians(lat)) * 111320.0
    out = []
    for v in g["vertices"]:
        d = math.hypot((v[1] - lat) * 111320.0, (v[2] - lon) * k)
        if d <= R:
            out.append((d, v))
    for d, v in sorted(out):
        b = zb.get((f"{v[1]:.11f}", f"{v[2]:.11f}"))
        bs = "   -   " if b is None else f"{b:7.2f} ({b - v[3]:+.2f})"
        print(f"  v{v[0]:<6d} d {d:5.1f}  {v[1]:.8f}, {v[2]:.8f}  A {v[3]:7.2f}  B {bs}  {sorted(faces[v[0]])}")


if __name__ == "__main__":
    main(sys.argv[1:])
