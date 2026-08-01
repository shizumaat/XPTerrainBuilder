"""Triage every uncarved below-grade object at OTHH into WHY it is uncarved,
so the owner sees a decision list rather than a pile of resources.

Cache-only.  Run from Ortho4XP/ cwd.
"""
import os
import pickle
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.getcwd(), "src"))
sys.path.insert(0, os.getcwd())

from auto_patch import dsf_reader, obj8_reader  # noqa: E402
from auto_patch import object_terrain_features as otf  # noqa: E402
from auto_patch.object_terrain_assembly import (  # noqa: E402
    _load_object_geometry_by_resource,
)

XP = "/Users/noah/X-Plane 12"
DSF = os.path.join(XP, "Custom Scenery", "OTHH Doha (Aeroscape)",
                   "Earth nav data", "+20+050", "+25+051.dsf")
CACHE = ("Airport_mod_cache/OTHH Doha (Aeroscape)/"
         "o4_object_terrain_classification_+25+051.cache")
DEPTH_FLOOR_M = 1.0

lines = dsf_reader._load_dsf_text(DSF)
terrain = [p for p in obj8_reader.read_dsf_object_placements(
    lines, accept_resource=lambda r: r.lower().endswith(".obj"))
    if p.placement_kind != "OBJECT_MSL"]
geometry = _load_object_geometry_by_resource(
    terrain, dsf_reader._pack_root_for_dsf(DSF), XP)
result = pickle.load(open(CACHE, "rb"))["result"]

offset = defaultdict(float)
for placement in terrain:
    agl = float(placement.above_ground_level_metres or 0.0)
    offset[placement.resource_path] = min(
        offset.get(placement.resource_path, 0.0), agl)

deep = {}
for resource, geom in geometry.items():
    if geom is None or not geom.vertices or not geom.solid_triangles:
        continue
    idx = {i for tri in geom.solid_triangles for i in tri}
    ys = [geom.vertices[i][1] for i in idx if i < len(geom.vertices)]
    if not ys:
        continue
    minimum = min(ys) + offset.get(resource, 0.0)
    if minimum < -DEPTH_FLOOR_M:
        deep[resource] = minimum

carved = set()
for tunnel in result.tunnels:
    carved.update(tunnel.object_resources)
for bridge in result.bridges:
    carved.update(bridge.object_resources)
for interface in result.ground_interfaces:
    if otf.is_carved_basin_interface(interface):
        carved.update(interface.object_resources)

refused = set()
for refusal in result.refusals:
    refused.update(getattr(refusal, "object_resources", []))

interface_of = {}
for interface in result.ground_interfaces:
    for resource in interface.object_resources:
        interface_of[resource] = interface

buckets = defaultdict(list)
for resource, minimum in sorted(deep.items(), key=lambda kv: kv[1]):
    if resource in carved:
        buckets["A carved already"].append((minimum, resource, None))
        continue
    if resource in refused:
        buckets["C refused bridge (amendment A4)"].append(
            (minimum, resource, None))
        continue
    interface = interface_of.get(resource)
    if interface is None:
        buckets["E no ground interface at all"].append(
            (minimum, resource, None))
        continue
    below = [lv for lv in interface.interface_levels if lv[0] < -1.0]
    if not below:
        buckets["D incidental buried slack (no clustered below-grade "
                "LEVEL — amendment A6 buries these by design)"].append(
            (minimum, resource, interface))
    elif interface.at_grade_wall_base_share > otf.BOWL_MAX_AT_GRADE_BASE_SHARE:
        buckets["B structure AT GRADE with a below-grade interior "
                "(ruling R10 INTERIOR_CUTOUT — designed, no emitter)"].append(
            (minimum, resource, interface))
    else:
        buckets["F sunken, walls NOT at grade, still FLAT_CONFIRMED "
                "(classifier gap)"].append((minimum, resource, interface))

for label in sorted(buckets):
    items = buckets[label]
    print(f"\n=== {label}  —  {len(items)} resource(s) ===")
    seen = set()
    for minimum, resource, interface in items:
        key = (interface.object_resources[0] if interface is not None
               else resource)
        if key in seen:
            continue
        seen.add(key)
        extra = ""
        if interface is not None:
            below = [lv for lv in interface.interface_levels if lv[0] < -1.0]
            extra = (f"  gndcont={interface.ground_contact_fraction:.3f} "
                     f"wallbase={interface.at_grade_wall_base_share:.3f} "
                     f"above={interface.above_grade_area_fraction:.3f} "
                     f"level={min(lv[0] for lv in below):.2f}m"
                     if below else
                     f"  gndcont={interface.ground_contact_fraction:.3f}")
        print(f"  {minimum:8.2f} m  {os.path.basename(resource):46s}{extra}")
        if len(seen) >= 10:
            print(f"  ... ({len(items)} resources in "
                  f"{len({(i.object_resources[0] if i else r) for _m, r, i in items})} pool(s))")
            break
