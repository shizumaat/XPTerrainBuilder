"""padreview P3: building faces within R m of a site: ref, area, n, z, and which non-building faces share its ring."""
import json, sys, math, collections, statistics
from shapely.geometry import Polygon, Point
g=json.load(open(sys.argv[1])); lat,lon,R=float(sys.argv[2]),float(sys.argv[3]),float(sys.argv[4])
V={v[0]:(v[1],v[2],v[3]) for v in g["vertices"]}
mx=111320.0*math.cos(math.radians(lat)); my=110574.0
own=collections.defaultdict(set)
for f in g["faces"]:
    for i in f["ring"]: own[i].add((f["role"],f["ref"]))
P=Point(0,0); tot=0; totv=0; byrole=collections.Counter()
for f in g["faces"]:
    ring=[((V[i][1]-lon)*mx,(V[i][0]-lat)*my) for i in f["ring"] if i in V]
    if len(ring)<3: continue
    p=Polygon(ring); p=p if p.is_valid else p.buffer(0)
    if p.distance(P)>R: continue
    tot+=1; totv+=len(f["ring"]); byrole[f["role"]]+=1
    if f["role"]!="building": continue
    zs=[V[i][2] for i in f["ring"] if i in V]
    nb=collections.Counter()
    for i in f["ring"]:
        for o in own[i]:
            if o[1]!=f["ref"]: nb[o]+=1
    c=p.centroid
    print(f"{f['ref']:28s} area {p.area:10.1f} n {len(f['ring']):5d} z {min(zs):.2f}..{max(zs):.2f} at {lat+c.y/my:.6f},{lon+c.x/mx:.6f} | {dict(nb.most_common(5))}")
print("faces",tot,"ring vertices",totv,dict(byrole))
