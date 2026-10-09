"""gapapron probe 1 (dry, no solve): ROAD EVIDENCE per apron-touching gap
piece, read through the EXISTING readers — the 1206 truck chains
(`classify.evidence.chains_from_edges`), the OSM highway ways the ribbon
mint reads (`rules.osm_roads`), the minted ribbon cells flush with the piece
(`model.planar.is_osm_ribbon_ref`, late_stage._WELD_M), the road-family
faces across the stand-off (`constraints.roads.road_family_roles`), and the
§27 airside-edge reader itself (`classify.airside_edge._lateral_airside_m`,
`_is_mouth`) on the piece's apron contact.

usage: evidence_read.py CAPTURE.pkl CL.pkl OUT.json
"""
import json, math, pickle, sys, time
sys.path[:0] = ["src", "."]
import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

cap_p, cl_p, out_p = sys.argv[1:4]
t = time.time()
cap = pickle.load(open(cap_p, "rb"))
airport = cap["airport"]
cl = pickle.load(open(cl_p, "rb"))["cl"]
print("loaded", round(time.time() - t), "s", flush=True)

from auto_patch_v2.law import Law
from auto_patch_v2.classify import load_rules
from auto_patch_v2.classify.evidence import chains_from_edges
from auto_patch_v2.classify.gap_mint import _poly, standoff_m
from auto_patch_v2.classify import airside_edge as ae
from auto_patch_v2.constraints.roads import road_family_roles
from auto_patch_v2.model.planar import is_gap_ref, is_osm_ribbon_ref
from auto_patch_v2.law.tables import role_side

law = Law.for_airport(cap["icao"])
rules = load_rules()
to_ll = airport.frame.transformers()[1]
weld_m = float(law.tables.emit.identity.weld_spacing_m)
stand = standoff_m(law)
on_tol = float(rules.cells.on_tol_m)
min_edge = float(rules.lot.airside_edge_min_m)
frac = float(rules.lot.road_airside_edge_frac)
factor = float(rules.lot.mouth_width_factor)
road_roles = frozenset(road_family_roles(law))
print("law: weld", weld_m, "stand", stand, "on_tol", on_tol, "min_edge", min_edge,
      "frac", frac, "factor", factor, "road_roles", sorted(road_roles))

# ---- the readers' inputs
node_xy = {nid: n.xy for nid, n in airport.taxi_nodes.items()}
truck_edges = [(r.a, r.b, None, r.name) for r in airport.ground_routes]
truck = chains_from_edges(node_xy, truck_edges, (), True, 0)
truck_lines = [c.line for c in truck]
truck_tree = STRtree(truck_lines) if truck_lines else None
hw = set(rules.osm_roads.highways)
osm = [(w.id, w.tags.get("highway"), LineString(w.points)) for w in airport.osm_ways
       if w.tags.get("highway") in hw and len(w.points) >= 2]
osm_lines = [g for _i, _h, g in osm]
osm_tree = STRtree(osm_lines)
cells = list(cl.cells)
polys = [(c, _poly(c.ring, c.holes)) for c in cells]
polys = [(c, q) for c, q in polys if q is not None]
gap = [(c, q) for c, q in polys if is_gap_ref(c.ref)]
aprons = [(c, q) for c, q in polys if c.role == "apron"]
apron_tree = STRtree([q for _c, q in aprons])
ribbons = [(c, q) for c, q in polys if is_osm_ribbon_ref(c.ref)]
rib_tree = STRtree([q for _c, q in ribbons]) if ribbons else None
roadf = [(c, q) for c, q in polys if c.role in road_roles and not is_osm_ribbon_ref(c.ref)]
roadf_tree = STRtree([q for _c, q in roadf]) if roadf else None
pads = [(c, q) for c, q in polys if c.role == "building"]
pad_tree = STRtree([q for _c, q in pads]) if pads else None
# §27's own airside list (the fixed airside cells less pads) + the reader
air = [(q, False) for c, q in polys if c.role != "building" and c.side == "airside"
       and not is_gap_ref(c.ref)]
air_tree = STRtree([q for q, _r in air])
roads_ctx = ae._Roads(truck_lines, weld_m, rules.service.free_max_width_m,
                      rules.service.min_run_m)
print(f"cells {len(cells)}: gap {len(gap)}, aprons {len(aprons)}, ribbons {len(ribbons)}, "
      f"road faces {len(roadf)}, pads {len(pads)}; truck chains {len(truck)}, osm highways {len(osm)}",
      flush=True)

sites = {"430": (30.1154841, 31.4105884), "292": (30.1159784, 31.4106264),
         "358": (30.1193169, 31.4085087)}
to_xy = airport.frame.transformers()[0]
site_xy = {k: Point(*to_xy(*v)) for k, v in sites.items()}


def runs_with(poly, tree, items, tol):
    """(shared metres, [(ref, metres)], union geometry of the runs)."""
    out, geoms = [], []
    for j in tree.query(poly.buffer(tol), predicate="intersects"):
        c, q = items[int(j)]
        run = poly.boundary.intersection(q.boundary.buffer(tol))
        if not run.is_empty and run.length > 0:
            out.append((c.ref, round(float(run.length), 1)))
            geoms.append(run)
    u = unary_union(geoms) if geoms else None
    return (float(u.length) if u is not None else 0.0), sorted(out, key=lambda x: -x[1]), u


rows = []
for c, q in gap:
    touches = float(c.evidence.get("touches_apron", 0.0)) > 0
    if not touches:
        continue
    r = {"ref": c.ref, "m2": round(q.area), "perimeter_m": round(q.length),
         "apron_shared_m_mint": round(float(c.evidence.get("apron_shared_m", 0.0)), 1)}
    a_m, a_runs, a_geom = runs_with(q, apron_tree, aprons, weld_m)
    r["apron_contact_m"] = round(a_m, 1)
    r["apron_runs"] = a_runs[:6]
    # (a) 1206 truck chains: inside the piece (on_tol), and touching the apron contact
    tk = []
    for j in truck_tree.query(q.buffer(on_tol), predicate="intersects") if truck_tree else []:
        ln = truck_lines[int(j)]
        inside = ln.intersection(q.buffer(on_tol))
        if inside.length > 0:
            tk.append((truck[int(j)].id, round(float(inside.length), 1),
                       round(float(ln.distance(a_geom)), 1) if a_geom is not None else None))
    r["truck_chains"] = sorted(tk, key=lambda x: -x[1])[:5]
    r["truck_m"] = round(sum(x[1] for x in tk), 1)
    # (b) OSM highway ways inside the piece
    ow = []
    for j in osm_tree.query(q, predicate="intersects"):
        wid, h, ln = osm[int(j)]
        inside = ln.intersection(q)
        if inside.length > 0:
            ow.append((wid, h, round(float(inside.length), 1),
                       round(float(ln.distance(a_geom)), 1) if a_geom is not None else None))
    r["osm_ways"] = sorted(ow, key=lambda x: -x[2])[:6]
    r["osm_ways_n"] = len(ow)
    r["osm_m"] = round(sum(x[2] for x in ow), 1)
    # (c) ribbon cells flush with the piece (the late stage's followers)
    rb_m, rb_runs, rb_geom = runs_with(q, rib_tree, ribbons, 0.3) if rib_tree else (0.0, [], None)
    r["ribbons_flush"] = rb_runs[:6]
    r["ribbons_flush_n"] = len(rb_runs)
    r["ribbon_to_apron_contact_m"] = (round(float(rb_geom.distance(a_geom)), 1)
                                      if rb_geom is not None and a_geom is not None else None)
    # (d) road-family faces across the stand-off (route corridors, service roads, junctions)
    rf_m, rf_runs, rf_geom = runs_with(q, roadf_tree, roadf, stand + weld_m) if roadf_tree else (0.0, [], None)
    r["road_faces_standoff"] = rf_runs[:6]
    r["road_faces_m"] = round(rf_m, 1)
    r["road_face_to_apron_contact_m"] = (round(float(rf_geom.distance(a_geom)), 1)
                                         if rf_geom is not None and a_geom is not None else None)
    pd_m, pd_runs, _ = runs_with(q, pad_tree, pads, stand + weld_m) if pad_tree else (0.0, [], None)
    r["pads_standoff_n"] = len(pd_runs)
    r["pads_standoff_m"] = round(pd_m, 1)
    # (e) §27's reader on the piece: lateral airside metres with the piece read as a
    #     lot (no mouth unless a centreline enters) and as a road-class strip
    lat_lot = ae._lateral_airside_m(q, False, air_tree, air, weld_m, factor, {}, roads_ctx)
    lat_road = ae._lateral_airside_m(q, True, air_tree, air, weld_m, factor, {}, roads_ctx)
    r["s27_lateral_m_as_lot"] = round(lat_lot, 1)
    r["s27_lateral_m_as_road"] = round(lat_road, 1)
    r["s27_share_as_road"] = round(lat_road / q.length, 3) if q.length else None
    r["s27_flip_as_lot"] = bool(lat_lot >= min_edge and q.area / q.length >= ae._LOT_SLIVER_RADIUS_M)
    r["s27_flip_as_road"] = bool(lat_road >= min_edge and lat_road >= frac * q.length)
    # the class under the owner's 08c (6) sentence
    evidence = bool(tk or ow or rb_runs or rf_runs)
    kinds = []
    if tk: kinds.append("1206 route")
    if ow: kinds.append("OSM highway")
    if rb_runs: kinds.append("ribbon flush")
    if rf_runs: kinds.append("road face at stand-off")
    r["road_evidence"] = kinds
    # does a road TOUCH the apron contact (within the weld)?
    touch_d = [d for d in (r["ribbon_to_apron_contact_m"], r["road_face_to_apron_contact_m"]) if d is not None]
    touch_d += [x[2] for x in tk if x[2] is not None] + [x[3] for x in ow if x[3] is not None]
    r["road_to_apron_contact_min_m"] = min(touch_d) if touch_d else None
    r["class_08c"] = "ROAD (class i, late)" if evidence else "APRON (stage 1)"
    r["class_08c_with_s37_share"] = ("APRON by share (§37 (2))" if evidence and r["s27_flip_as_road"]
                                     else r["class_08c"])
    r["sites"] = [k for k, p in site_xy.items() if q.covers(p)]
    rp = q.representative_point()
    r["at"] = "%.7f, %.7f" % to_ll(rp.x, rp.y)
    rows.append(r)

rows.sort(key=lambda r: -r["m2"])
json.dump(rows, open(out_p, "w"), indent=1)
tot = sum(r["m2"] for r in rows)
print(f"\napron-touching pieces {len(rows)}, {tot:,} m2")
for r in rows:
    print(f"{r['ref']:7s} {r['m2']:>9,} m2 per {r['perimeter_m']:>6,} apron {r['apron_contact_m']:>7.1f} m "
          f"| truck {r['truck_m']:>6.1f} osm {r['osm_m']:>8.1f}({r['osm_ways_n']}) ribbons {r['ribbons_flush_n']:>2} "
          f"roadf {r['road_faces_m']:>6.1f} pads {r['pads_standoff_n']:>2} | s27 lot {r['s27_lateral_m_as_lot']:>7.1f} "
          f"road {r['s27_lateral_m_as_road']:>7.1f} share {r['s27_share_as_road']} "
          f"| road->apron {r['road_to_apron_contact_min_m']} | {r['class_08c_with_s37_share']} {r['sites']} {r['at']}")
n_ap = [r for r in rows if r["class_08c"].startswith("APRON")]
print(f"\nNO road evidence -> APRON: {len(n_ap)} pieces, {sum(r['m2'] for r in n_ap):,} m2")
n_sh = [r for r in rows if r["class_08c_with_s37_share"].startswith("APRON by share")]
print(f"road evidence but §37 (2) share >= {frac}: {len(n_sh)} pieces, {sum(r['m2'] for r in n_sh):,} m2: "
      + ", ".join(r['ref'] for r in n_sh))
