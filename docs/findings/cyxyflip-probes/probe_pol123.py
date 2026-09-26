"""Scratch: per-neighbour airside contact of the CYXY-1 faces in every §27 round."""
import sys, math
sys.path.insert(0, "src")
from auto_patch_v2.pipeline.__main__ import default_inputs
from auto_patch_v2.airport.load import load_with_report
from auto_patch_v2.classify import classify, load_rules
from auto_patch_v2.classify import airside_edge as AE
from auto_patch_v2.law import Law
from shapely.geometry import Polygon
from shapely.ops import unary_union

TARGETS = {"dsf:pol123", "dsf:pol20", "dsf:pol17"}
icao = sys.argv[1] if len(sys.argv) > 1 else "CYXY"
inputs = default_inputs(None, None, None, 60.0, "production", True)
law = Law.for_airport(icao)
airport, _ = load_with_report(icao, inputs, law)
rules = load_rules()
to_xy, to_ll = airport.frame.transformers()

orig_flip = AE.airside_edge_flip
orig_lat = AE._lateral_airside_m
state = {"final": None, "round": 0}

def flip(final, cells, law, rules):
    state["final"] = final
    state["ref_of"] = {id(f[2]): (f[1], f[0]) for f in final}
    state["fixed"] = {id(Polygon(c.ring, c.holes)): (c.ref, c.role) for c in cells}
    # keep a parallel map by geometry wkb for fixed cells
    state["cell_by_wkb"] = {Polygon(c.ring, c.holes).wkb: (c.ref, c.role) for c in cells}
    state["final_by_wkb"] = {f[2].wkb: (f[1], f[0]) for f in final}
    return orig_flip(final, cells, law, rules)

def lat(face, face_is_road, tree, air, weld_m, factor, cache=None):
    ref = state["final_by_wkb"].get(face.wkb, ("?", "?"))
    if ref[0] in TARGETS:
        print(f"\n== {ref[0]} (now {ref[1]}; born road={face_is_road}) area={face.area:,.0f} per={face.length:.1f}")
        for j in tree.query(face.buffer(weld_m), predicate="intersects"):
            other, other_is_road = air[int(j)]
            oref = state["final_by_wkb"].get(other.wkb) or state["cell_by_wkb"].get(other.wkb, ("cell?", "?"))
            contact = face.boundary.intersection(other.boundary.buffer(weld_m))
            exact = face.boundary.intersection(other.boundary)
            if contact.is_empty or contact.length <= 0: 
                continue
            mouth = AE._is_mouth(face, other, contact, factor, face_is_road, other_is_road, cache)
            c = contact.centroid
            print(f"   vs {oref[0]:<14} {oref[1]:<20} road={other_is_road} welded={contact.length:6.2f} exact={exact.length:6.2f} mouth={mouth} at {to_ll(c.x, c.y)[0]:.7f},{to_ll(c.x, c.y)[1]:.7f}")
    return orig_lat(face, face_is_road, tree, air, weld_m, factor, cache)

AE.airside_edge_flip = flip
AE._lateral_airside_m = lat
import auto_patch_v2.classify.roles as R
R.airside_edge_flip = flip
cl = classify(airport, law, rules)
print("\n== road faces (final service_road entries) near pol123")
p123 = [f for f in state["final"] if f[1] == "dsf:pol123"][0][2]
for f in state["final"]:
    if f[1].startswith("route") and f[2].distance(p123) < 30:
        ex = f[2].boundary.intersection(p123.boundary)
        print(f"   {f[1]:<8} {f[0]:<14} area={f[2].area:7.1f} per={f[2].length:6.1f} dist_to_pol123={f[2].distance(p123):5.2f} shared_exact={ex.length:5.2f} at {to_ll(f[2].centroid.x, f[2].centroid.y)}")
print("\n== final roles at the three refs")
for c in cl.cells:
    if c.ref in TARGETS or c.ref.startswith("route"):
        p = Polygon(c.ring, c.holes)
        print(f"   {c.ref:<12} {c.role:<20} {p.area:8.1f} m2")
