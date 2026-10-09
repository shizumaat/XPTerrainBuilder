"""gapapron probe 1b (dry): would §43's NECK CUT (`classify/neck.necks_of` +
`split_at_necks`, the existing 'an apron ends at its mouth' reader) make the
08c (6) read LOCAL — i.e. does any apron-touching piece hold a lobe that
touches an apron and carries no road evidence?  Also fixes probe 1's site
cover (to_xy takes (lon, lat)).

usage: neck_read.py CAPTURE.pkl CL.pkl EVIDENCE.json
"""
import json, pickle, sys, time
sys.path[:0] = ["src", "."]
import shapely
from shapely.geometry import LineString, Point
from shapely.ops import unary_union
from shapely.strtree import STRtree

cap_p, cl_p, ev_p = sys.argv[1:4]
cap = pickle.load(open(cap_p, "rb"))
airport = cap["airport"]
cl = pickle.load(open(cl_p, "rb"))["cl"]
from auto_patch_v2.law import Law
from auto_patch_v2.classify import load_rules
from auto_patch_v2.classify.gap_mint import _poly, standoff_m
from auto_patch_v2.classify.neck import necks_of, split_at_necks
from auto_patch_v2.constraints.roads import road_family_roles
from auto_patch_v2.model.planar import is_gap_ref, is_osm_ribbon_ref

law = Law.for_airport(cap["icao"])
rules = load_rules()
to_xy, to_ll = airport.frame.transformers()
weld_m = float(law.tables.emit.identity.weld_spacing_m)
stand = standoff_m(law)
road_roles = frozenset(road_family_roles(law))
hw = set(rules.osm_roads.highways)
osm_lines = [LineString(w.points) for w in airport.osm_ways
             if w.tags.get("highway") in hw and len(w.points) >= 2]
osm_tree = STRtree(osm_lines)
polys = [(c, _poly(c.ring, c.holes)) for c in cl.cells]
polys = [(c, q) for c, q in polys if q is not None]
gap = {c.ref: q for c, q in polys if is_gap_ref(c.ref)}
aprons = [q for c, q in polys if c.role == "apron"]
apron_tree = STRtree(aprons)
ribbons = [q for c, q in polys if is_osm_ribbon_ref(c.ref)]
rib_tree = STRtree(ribbons)
roadf = [q for c, q in polys if c.role in road_roles and not is_osm_ribbon_ref(c.ref)]
roadf_tree = STRtree(roadf)
sites = {"430": (30.1154841, 31.4105884), "292": (30.1159784, 31.4106264),
         "358": (30.1193169, 31.4085087)}
site_xy = {k: Point(*to_xy(lon, lat)) for k, (lat, lon) in sites.items()}
for k, p in site_xy.items():
    print("site", k, "in", [r for r, q in gap.items() if q.covers(p)])


def shared(q, tree, items, tol):
    runs = [q.boundary.intersection(items[int(j)].boundary.buffer(tol))
            for j in tree.query(q.buffer(tol), predicate="intersects")]
    runs = [r for r in runs if not r.is_empty and r.length > 0]
    return float(unary_union(runs).length) if runs else 0.0


rows = json.load(open(ev_p))
tot_lobes = 0
apron_lobes = []
for r in rows:
    q = gap[r["ref"]]
    if q.area > 200000:
        print(f"{r['ref']}: {q.area:,.0f} m2 — neck read skipped (gap:0 is the landside network; "
              "read its parts below)", flush=True)
        continue
    t = time.time()
    necks = necks_of(q, rules)
    lobes = split_at_necks(q, necks, rules) if necks else [(q, False)]
    dt = time.time() - t
    tot_lobes += len(lobes)
    out = []
    for poly, is_neck in lobes:
        a = shared(poly, apron_tree, aprons, weld_m)
        if a < float(rules.lot.airside_edge_min_m):
            continue
        osm_m = sum(float(osm_lines[int(j)].intersection(poly).length)
                    for j in osm_tree.query(poly, predicate="intersects"))
        rb = shared(poly, rib_tree, ribbons, 0.3)
        rf = shared(poly, roadf_tree, roadf, stand + weld_m)
        ev = bool(osm_m > 0 or rb > 0 or rf > 0)
        share = a / poly.length if poly.length else 0.0
        cls = "ROAD" if ev and share < float(rules.lot.road_airside_edge_frac) else "APRON"
        out.append((round(poly.area), round(a, 1), round(osm_m, 1), round(rb, 1), round(rf, 1),
                    round(share, 3), cls, "neck" if is_neck else "lobe"))
        if cls == "APRON":
            apron_lobes.append((r["ref"], round(poly.area)))
    print(f"{r['ref']:7s} {q.area:>9,.0f} m2 necks {len(necks)} lobes {len(lobes)} ({dt:.1f} s) "
          f"piece class {r['class_08c_with_s37_share']}; apron-touching lobes: {out}", flush=True)
print("apron lobes by the neck read:", apron_lobes, "sum m2", sum(a for _r, a in apron_lobes))
