"""classify the capture twice (rim closure on / off) and pickle both."""
import dataclasses as dc, pickle, sys
sys.path[:0] = ["src", "."]
from auto_patch_v2.airport import frame_entry as fe
from auto_patch_v2.airport.obj8 import ResourceCache
from auto_patch_v2.classify import classify, gap_mint as gm
from auto_patch_v2.classify.rules import load_rules
from auto_patch_v2.law import Law
from auto_patch_v2.planar.cluster import clusters
airport = pickle.load(open(sys.argv[1], "rb"))["airport"]
law = Law.for_airport(airport.icao)
airport = dc.replace(airport, clusters=clusters(airport, law))
cache = ResourceCache(law.tables.structures.basin.min_solid_thickness_m, fe.quantum(law))
cl = classify(airport, law, load_rules(), cache=cache)
orig = gm.close_rim
gm.close_rim = lambda part, *a, **k: part
cl0 = classify(airport, law, load_rules(), cache=cache)
pickle.dump({"cl": cl, "cl0": cl0, "airport": airport}, open(sys.argv[2], "wb"))
for n in cl.notes:
    if "gap" in n: print(n)
print({k: v for k, v in cl.stats.items() if "gap" in k})
