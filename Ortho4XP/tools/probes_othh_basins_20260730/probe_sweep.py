"""Owner directive 2026-07-30: "chase any additional objects that are below
terrain, they should be getting carve outs."

Sweeps EVERY object placement in the pack, measures how far its own solid
geometry reaches below effective grade, and reports what the classifier does
with it — so anything genuinely sunken but uncarved is named.

Reads caches only (DSF text sidecar + the classification sidecar); no build.
Run from Ortho4XP/ cwd.
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
PACK = os.path.join(XP, "Custom Scenery", "OTHH Doha (Aeroscape)")
DSF = os.path.join(PACK, "Earth nav data", "+20+050", "+25+051.dsf")
CACHE = ("Airport_mod_cache/OTHH Doha (Aeroscape)/"
         "o4_object_terrain_classification_+25+051.cache")

#: how far below effective grade counts as "genuinely sunken"
DEPTH_FLOOR_M = 1.0

lines = dsf_reader._load_dsf_text(DSF)
placements = obj8_reader.read_dsf_object_placements(
    lines, accept_resource=lambda r: r.lower().endswith(".obj"),
    include_object_msl=True)
terrain = [p for p in placements if p.placement_kind != "OBJECT_MSL"]
geometry = _load_object_geometry_by_resource(
    terrain, dsf_reader._pack_root_for_dsf(DSF), XP)
print(f"placements={len(placements)} terrain={len(terrain)} "
      f"geometry={len(geometry)}")

result = pickle.load(open(CACHE, "rb"))["result"]

# ── what the classifier did with each resource ───────────────────────
verdict: dict[str, str] = {}
for tunnel in result.tunnels:
    for resource in tunnel.object_resources:
        verdict[resource] = "TUNNEL (carved)"
for bridge in result.bridges:
    for resource in bridge.object_resources:
        verdict[resource] = "BRIDGE"
for refusal in result.refusals:
    for resource in getattr(refusal, "object_resources", []):
        verdict.setdefault(resource, "REFUSED")
for interface in result.ground_interfaces:
    carved = otf.is_carved_basin_interface(interface)
    pit = otf.is_open_pit_interface(interface)
    label = interface.interface_class
    if carved:
        label += " (carved" + (", R13 cuts pavement)" if pit else ")")
    for resource in interface.object_resources:
        verdict[resource] = label

# ── measured below-grade reach, per resource ─────────────────────────
offset_by_resource: dict[str, float] = defaultdict(lambda: 0.0)
for placement in terrain:
    # keep the DEEPEST (most negative) placement offset seen
    current = offset_by_resource.get(placement.resource_path)
    agl = float(placement.above_ground_level_metres or 0.0)
    if current is None or agl < current:
        offset_by_resource[placement.resource_path] = agl

rows = []
for resource, geom in geometry.items():
    if geom is None or not geom.vertices:
        continue
    solid_indices = {i for tri in geom.solid_triangles for i in tri}
    if not solid_indices:
        continue
    offset = offset_by_resource.get(resource, 0.0)
    ys = [geom.vertices[i][1] for i in solid_indices
          if i < len(geom.vertices)]
    if not ys:
        continue
    minimum = min(ys) + offset
    maximum = max(ys) + offset
    if minimum >= -DEPTH_FLOOR_M:
        continue
    rows.append((minimum, maximum, resource,
                 verdict.get(resource, "— nothing —")))

rows.sort()
print(f"\n{len(rows)} resource(s) whose SOLID geometry reaches more than "
      f"{DEPTH_FLOOR_M} m below effective grade\n")
print(f"{'min_y':>8s} {'max_y':>8s}  {'classifier verdict':38s} resource")
uncarved = []
for minimum, maximum, resource, label in rows:
    print(f"{minimum:8.2f} {maximum:8.2f}  {label:38s} "
          f"{os.path.basename(resource)}")
    if "carved" not in label and label not in ("BRIDGE",):
        uncarved.append((minimum, resource, label))

print(f"\n=== NOT CARVED: {len(uncarved)} resource(s) ===")
by_label = defaultdict(list)
for minimum, resource, label in uncarved:
    by_label[label].append((minimum, resource))
for label, items in sorted(by_label.items(), key=lambda kv: -len(kv[1])):
    print(f"\n  {label}  ({len(items)})")
    for minimum, resource in sorted(items)[:14]:
        print(f"     {minimum:8.2f} m   {resource}")
    if len(items) > 14:
        print(f"     ... and {len(items) - 14} more")
