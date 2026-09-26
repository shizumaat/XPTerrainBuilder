import sys, math
sys.path.insert(0, "src")
from auto_patch_v2.pipeline.__main__ import default_inputs
from auto_patch_v2.airport.load import load_with_report
from auto_patch_v2.classify import classify, load_rules
from auto_patch_v2.classify import airside_edge as AE
from auto_patch_v2.classify.evidence import build_evidence
from auto_patch_v2.law import Law
from shapely.geometry import Polygon, LineString, Point
inputs = default_inputs(None, None, None, 60.0, "production", True)
law = Law.for_airport("CYXY"); airport,_ = load_with_report("CYXY", inputs, law); rules = load_rules()
ev = build_evidence(airport, rules, law.tables.structures.building_pad.min_area_m2, law)
state={}
orig=AE.airside_edge_flip
def flip(final, cells, law, rules):
    state["final"]=[list(f) for f in final]; return orig(final, cells, law, rules)
import auto_patch_v2.classify.roles as R; R.airside_edge_flip=flip
cl=classify(airport, law, rules)
F={f[1]:f for f in state["final"]}
p123=F["dsf:pol123"][2]
pav9=max([Polygon(c.ring,c.holes) for c in cl.cells if c.ref=="pav9" and c.role=="apron"],key=lambda p:p.area)
for tol in (1.0,0.75,0.5,0.25,0.1,0.05):
    c=p123.boundary.intersection(pav9.boundary.buffer(tol)); print(f"tol {tol:4.2f}: contact {c.length:6.2f} m  chord {AE._chord_dir(c) and 0 or 0}")
ch=[c for c in ev.truck_chains if 50<c.line.length<60][0].line
print("chain start on contact? dist", ch.distance(p123.boundary.intersection(pav9.boundary.buffer(1.0))))
for d in (0.5,1,2,3,4,6):
    p=ch.interpolate(d); q=ch.interpolate(d+0.5); r=ch.interpolate(d-0.5)
    dx,dy=q.x-r.x,q.y-r.y; L=math.hypot(dx,dy) or 1; nx,ny=-dy/L*40,dx/L*40
    for name,poly in (("pol123",p123),("pol123+weld",p123.buffer(1.0))):
        xs=LineString([(p.x-nx,p.y-ny),(p.x+nx,p.y+ny)]).intersection(poly)
        piece=max([g.length for g in (xs.geoms if hasattr(xs,"geoms") else [xs]) if g.geom_type=="LineString" and g.distance(p)<1.5] or [0])
        print(f"  d={d} {name:12s} cross-section {piece:5.2f}")
# angle between chain direction at start and the contact chord
c=p123.boundary.intersection(pav9.boundary.buffer(1.0)); cd=AE._chord_dir(c)
q=ch.interpolate(3); p0=Point(ch.coords[0]); ax=((q.x-p0.x),(q.y-p0.y)); L=math.hypot(*ax); ax=(ax[0]/L,ax[1]/L)
print("chain axis", ax, "contact chord", cd, "cos", abs(ax[0]*cd[0]+ax[1]*cd[1]))
# strip-axis of pol123's neck: pol123 ∩ chain.buffer(6)
neck=p123.intersection(ch.buffer(8, cap_style="flat"))
print("neck mrr", AE._strip_axis_width(neck), "neck area", neck.area)
