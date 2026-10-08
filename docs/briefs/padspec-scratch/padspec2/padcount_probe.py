"""padspec2: pad COUNT today (rule 2) vs step 1 (rule 2b) per capture — which refs appear / vanish and why (counts dict)."""
import pickle,sys,json
sys.path.insert(0,"/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/padspec2")
from rider_probe import outlines
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import pad_outline
for icao,p in [a.split(":",1) for a in sys.argv[1:]]:
    cap=pickle.load(open(p,"rb")); airport=cap["airport"]; law=Law.for_airport(icao); to_xy=airport.frame.entry()
    t,c0=outlines(icao,airport,law,to_xy,None); s,c1=outlines(icao,airport,law,to_xy,pad_outline(law))
    print(icao,"today",c0["pads"],"step1",c1["pads"])
    print("  counts diff",{k:(c0.get(k),c1.get(k)) for k in set(c0)|set(c1) if c0.get(k)!=c1.get(k)})
    lost=[k for k in t if k not in s]; new=[k for k in s if k not in t]
    print("  lost",[(k,round(t[k].area)) for k in lost]); print("  new",[(k,round(s[k].area)) for k in new])
    multi=[(k,len(getattr(s[k],'geoms',[1]))) for k in s if s[k].geom_type=="MultiPolygon"]
    print("  step1 multipolygons",multi)
