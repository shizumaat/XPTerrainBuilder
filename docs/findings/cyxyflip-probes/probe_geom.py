import sys
sys.path.insert(0, "src")
from auto_patch_v2.pipeline.__main__ import default_inputs
from auto_patch_v2.airport.load import load_with_report
from auto_patch_v2.classify import classify, load_rules
from auto_patch_v2.classify import airside_edge as AE
from auto_patch_v2.classify.evidence import build_evidence
from auto_patch_v2.law import Law
from shapely.geometry import Polygon, LineString
icao="CYXY"
inputs = default_inputs(None, None, None, 60.0, "production", True)
law = Law.for_airport(icao); airport,_ = load_with_report(icao, inputs, law); rules = load_rules()
to_xy, to_ll = airport.frame.transformers()
ev = build_evidence(airport, rules, law.tables.structures.building_pad.min_area_m2, law)
state={}
orig=AE.airside_edge_flip
def flip(final, cells, law, rules):
    state["final"]=[list(f) for f in final]; return orig(final, cells, law, rules)
import auto_patch_v2.classify.roles as R; R.airside_edge_flip=flip
cl=classify(airport, law, rules)
F={f[1]:f for f in state["final"]}
p123=F["dsf:pol123"][2]; 
pav9=[Polygon(c.ring,c.holes) for c in cl.cells if c.ref=="pav9" and c.role=="apron"]
pav9=max(pav9,key=lambda p:p.area)
weld=law.tables.emit.identity.weld_spacing_m
contact=p123.boundary.intersection(pav9.boundary.buffer(weld))
print("weld_m",weld,"road_width_m",rules.service.road_width_m,"mouth factor",rules.lot.mouth_width_factor)
print("contact len",contact.length,"geom",contact.geom_type, "bounds", contact.bounds)
print("pol123-pav9 distance", p123.distance(pav9))
print("truck chains:", len(ev.truck_chains))
for c in ev.truck_chains:
    ln=c.line
    if ln.distance(contact)<15:
        print(" chain",getattr(c,"id",None), "len",ln.length,"dist to contact",ln.distance(contact),"crosses contact buffer(1)?", ln.intersects(contact.buffer(1.0)),
              "in pol123 m", ln.intersection(p123).length, "in pav9 m", ln.intersection(pav9).length)
        pts=list(ln.coords); print("   ends", to_ll(*pts[0]), to_ll(*pts[-1]))
# pol123 ring shape: width across along road
print("pol123 area",p123.area,"perim",p123.length,"mrr", AE._strip_axis_width(p123))
# the min rotated rect of the contact region: where is the road? corridor pieces
for k in ("route4","route6"):
    f=F[k][2]; print(k, "area",f.area,"per",f.length,"dist pav9",f.distance(pav9),"dist pol123",f.distance(p123), "dist contact", f.distance(contact))
# gap between pol123 and pav9 near contact: sample points along contact
import numpy as np
for g in getattr(contact,"geoms",[contact]):
    for i in np.linspace(0,1,6):
        pt=g.interpolate(i,normalized=True); print("  contact pt", to_ll(pt.x,pt.y), "gap to pav9 %.2f"%pt.distance(pav9))
