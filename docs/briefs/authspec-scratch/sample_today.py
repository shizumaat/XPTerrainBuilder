"""Probe 1: today's graded surface (swg_OTHH) under each wall / pit anchor and the walls' plate stations."""
import json, math, sys
from shapely.geometry import Polygon, Point
from shapely.strtree import STRtree
G=json.load(open('/tmp/harness/swg_OTHH.v2/OTHH.graded.json'))
R=json.load(open('/tmp/harness/swg_OTHH.v2/OTHH.rebake.json'))
V={v[0]:(v[1],v[2],v[3]) for v in G['vertices']}
Z0=3.962
polys=[]; meta=[]
for f in G['faces']:
    ring=[(V[i][1],V[i][0]) for i in f["ring"]]  # lon,lat
    if len(ring)<3: continue
    try: p=Polygon(ring)
    except Exception: continue
    polys.append(p); meta.append((f['role'],f['ref'],f['ring']))
tree=STRtree(polys)
def sample(lat,lon):
    pt=Point(lon,lat)
    hits=[i for i in tree.query(pt) if polys[i].covers(pt)]
    if not hits: return None,None
    i=hits[0]; role,ref,ring=meta[i]
    # IDW over the face's vertices (3 nearest)
    pts=sorted(((math.hypot((V[k][1]-lon)*100000*0.9,(V[k][0]-lat)*111000),V[k][2]) for k in ring))[:3]
    w=[1/max(d,0.01) for d,_ in pts]; z=sum(wi*z for wi,(_,z) in zip(w,pts))/sum(w)
    return z,(role,ref)
walls={'tunnel south west 2.obj':(-5.5,10.0),'tunnel_sw.obj':(0.0,5.0),'tunnel1.obj':(-5.0,9.55),
       'tunnel middle - west.obj':(-3.0,5.0),'tunnel middle - east.obj':(-3.0,5.0),'tunnel west 2.obj':(0.0,5.0),
       'tunnel west 1.obj':(2.5,5.0),'tunnel west 3.obj':(1.0,5.0)}
old={'tunnel south west 2.obj':-8.0,'tunnel_sw.obj':-3.0,'tunnel1.obj':-7.0,'tunnel middle - west.obj':-3.0,
     'tunnel middle - east.obj':-3.0,'tunnel west 2.obj':-3.0,'tunnel west 1.obj':-3.0,'tunnel west 3.obj':-3.0}
print("%-26s %-9s %-10s %6s %6s %6s %7s %7s %7s  %s"%("wall","unit","anchor","T_today","a_new","crest_y","h_cut","h_uncut","h_old_uncut","face / plate stations (n, mean ground, today's flush seat)"))
for u in R['units']:
    for m in u['members']:
        name=m['resource'].split('/')[-1]
        if name in walls:
            lat,lon=m['origin']; z,face=sample(lat,lon)
            a,c=walls[name]; T=z if z is not None else Z0
            st=m.get('plate_stations') or []
            gs=[sample(la,lo)[0] for la,lo in st]; gs=[g if g is not None else Z0 for g in gs]
            mg=sum(gs)/len(gs) if gs else float('nan')
            print("%-26s %-9s %.6f,%.6f %6.2f %6.2f %6.2f %7.2f %7.2f %7.2f  %s | st %d mean %.2f -> seat %.2f (move %+.2f)"%(
                name,u['id'],lat,lon,T,a,c,T+a+c-Z0,Z0+a+c-Z0,Z0+old[name]+c-Z0,face,len(st),mg,(mg-c) if gs else float('nan'),((mg-c)-(T+a)) if gs else float('nan')))
pits={'OTHH_Drainage_01_LOD0_001.obj':(4.2985,-3.816),'OTHH_Drainage_02_LOD0_001.obj':(4.2985,-3.816),'OTHH_Drainage_03_LOD0_001.obj':(4.2985,-3.816),
      'OTHH_Drainage_04_LOD0_001.obj':(4.2985,-3.816),'OTHH_Drainage_05_001.obj':(4.2985,-3.816),'OTHH_Dewatering_01_LOD0_002.obj':(13.4978,-13.142),
      'OTHH_Drainage_06_001.obj':(0.0,-4.201),'OTHH_Dewatering_02_LOD0_002.obj':(0.0,-13.142)}
print()
print("%-32s %-9s %-10s %7s %7s %7s %7s  %s"%("pit","unit","anchor","T_today","a","floor_y","rim-G(cut@shell)","face"))
for u in R['units']:
    for m in u['members']:
        name=m['resource'].split('/')[-1]
        if name in pits:
            lat,lon=m['origin']; z,face=sample(lat,lon); a,fy=pits[name]; T=z if z is not None else Z0
            print("%-32s %-9s %.6f,%.6f %7.2f %7.2f %7.2f %7.2f  %s"%(name,u['id'],lat,lon,T,a,fy,(Z0+fy)+a-Z0,face))
