import sys, math
sys.path.insert(0, "src")
from auto_patch_v2.pipeline.__main__ import default_inputs
from auto_patch_v2.airport.load import load_with_report
from auto_patch_v2.classify import load_rules
from auto_patch_v2.classify.evidence import build_evidence
from auto_patch_v2.law import Law
from shapely.geometry import LineString
inputs = default_inputs(None, None, None, 60.0, "production", True)
law = Law.for_airport("CYXY"); airport,_ = load_with_report("CYXY", inputs, law); rules = load_rules()
ev = build_evidence(airport, rules, law.tables.structures.building_pad.min_area_m2, law)
pu = ev.pavement_union
ch = [c for c in ev.truck_chains if getattr(c,"id",None)==50 or "50" in str(getattr(c,"id",""))]
print("service rules:", {k: getattr(rules.service,k) for k in dir(rules.service) if not k.startswith("_")})
for c in ev.truck_chains:
    ln=c.line
    if ln.length < 60 and ln.length > 50:
        print("chain", getattr(c,"id",None), "len %.1f"%ln.length)
        for d in range(0, int(ln.length)+1, 4):
            p=ln.interpolate(d); q=ln.interpolate(min(ln.length,d+0.5)); r=ln.interpolate(max(0,d-0.5))
            dx,dy=q.x-r.x,q.y-r.y; L=math.hypot(dx,dy) or 1
            nx,ny=-dy/L*40, dx/L*40
            xs=LineString([(p.x-nx,p.y-ny),(p.x+nx,p.y+ny)]).intersection(pu)
            piece=0
            for g in (xs.geoms if hasattr(xs,"geoms") else [xs]):
                if g.geom_type=="LineString" and g.distance(p)<0.6: piece=max(piece,g.length)
            print(f"   d={d:3d} pavement cross-section {piece:6.1f} m")
