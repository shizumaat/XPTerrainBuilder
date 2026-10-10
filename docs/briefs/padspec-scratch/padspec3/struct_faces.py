"""padspec3 scratch: the STRUCTURE faces of one or more *.graded.json, airport-wide and
within R of a site — count / area per structure role, and per ramp face which cell
family it borders (building pad vs road vs apron), so a replay arm can be read against
the base for §56 (6)'s bar ("trench / basin / corridor faces identical in count and
area ±1 %").
usage: venv/bin/python <this> LAT LON R A.graded.json [B.graded.json ...]"""
import json, math, sys
from collections import Counter, defaultdict
from shapely.geometry import Polygon, Point

STRUCT = ("tunnel_ramp", "wall_corridor_ramp", "garage_ramp", "door_ramp", "retaining_wall",
          "tunnel_trench", "tunnel_wall")
lat, lon, R = map(float, sys.argv[1:4])
mx = 111320.0 * math.cos(math.radians(lat)); my = 110574.0


def read(path):
    g = json.load(open(path))
    V = {v[0]: (v[1], v[2]) for v in g["vertices"]}
    faces = []
    for f in g["faces"]:
        ring = [((V[i][1] - lon) * mx, (V[i][0] - lat) * my) for i in f["ring"] if i in V]
        if len(ring) < 3:
            continue
        p = Polygon(ring); p = p if p.is_valid else p.buffer(0)
        faces.append((f.get("role", "?"), str(f.get("ref", "?")), p, set(f["ring"])))
    return faces


for path in sys.argv[4:]:
    faces = read(path)
    print(f"== {path}")
    n = Counter(); a = Counter(); ns = Counter(); as_ = Counter()
    byrole_v = defaultdict(set)
    for role, ref, p, vs in faces:
        byrole_v[role].update(vs)
    for role, ref, p, vs in faces:
        if role in STRUCT:
            n[role] += 1; a[role] += p.area
            if p.distance(Point(0, 0)) <= R:
                ns[role] += 1; as_[role] += p.area
    for role in STRUCT:
        if n[role]:
            print(f"  {role:20s} airport-wide {n[role]:3d} faces {a[role]:9,.0f} m2 | site {ns[role]:2d} faces {as_[role]:7,.0f} m2")
    # what each ramp face borders (shares >= 2 vertices with)
    fam = {"building": "pad", "service_road": "road", "service_junction": "road", "apron": "apron",
           "parking_lot": "lot", "groundside_pavement": "gs_pav"}
    border = Counter()
    for role, ref, p, vs in faces:
        if role in ("wall_corridor_ramp", "garage_ramp", "door_ramp", "tunnel_ramp"):
            for other, ov in byrole_v.items():
                if other in fam and len(vs & ov) >= 2:
                    border[(role, fam[other])] += 1
    print("  ramp faces bordering (role, family): n =", dict(sorted(border.items())))
