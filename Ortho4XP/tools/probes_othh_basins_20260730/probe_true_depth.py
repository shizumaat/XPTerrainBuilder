"""CORRECTED depth measurement for the OTHH bridges.

My earlier sweep read the object's own authored ``y`` (plus any AGL offset)
as "depth below grade".  That is depth below the DRAPE DATUM — the terrain
at the object's PLACEMENT ANCHOR — not below the ground under each vertex.
For a bridge whose anchor sits at the deck crest, every ramp and pier reads
several metres "below grade" while physically resting ON the ground.

This measures the real thing: world elevation of each solid vertex
(terrain(anchor) + AGL + authored y) against the DEM directly beneath THAT
vertex.  Positive depth = genuinely buried.

Run from Ortho4XP/ cwd.
"""
import math
import os
import pickle
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.getcwd(), "src"))
sys.path.insert(0, os.getcwd())

from auto_patch import dsf_reader, obj8_reader  # noqa: E402
from auto_patch import object_terrain_features as otf  # noqa: E402
from auto_patch.elevation import _load_airport_dem, _sample_dem  # noqa: E402
from auto_patch.object_terrain_assembly import (  # noqa: E402
    _load_object_geometry_by_resource,
)

XP = "/Users/noah/X-Plane 12"
DSF = os.path.join(XP, "Custom Scenery", "OTHH Doha (Aeroscape)",
                   "Earth nav data", "+20+050", "+25+051.dsf")
CACHE = ("Airport_mod_cache/OTHH Doha (Aeroscape)/"
         "o4_object_terrain_classification_+25+051.cache")
TILE_LAT, TILE_LON = 25, 51

lines = dsf_reader._load_dsf_text(DSF)
terrain = [p for p in obj8_reader.read_dsf_object_placements(
    lines, accept_resource=lambda r: r.lower().endswith(".obj"))
    if p.placement_kind != "OBJECT_MSL"]
geometry = _load_object_geometry_by_resource(
    terrain, dsf_reader._pack_root_for_dsf(DSF), XP)
result = pickle.load(open(CACHE, "rb"))["result"]

carved = set()
for tunnel in result.tunnels:
    carved.update(tunnel.object_resources)
for interface in result.ground_interfaces:
    if otf.is_carved_basin_interface(interface):
        carved.update(interface.object_resources)

dem = _load_airport_dem(25.2539, 51.6221)
print(f"DEM loaded: {dem is not None}")

families = defaultdict(list)
for placement in terrain:
    base = os.path.basename(placement.resource_path)
    if "Bridge_" not in base:
        continue
    key = base.split("Bridge_")[1][:2]
    if key.isdigit():
        families[f"Bridge_{key}"].append(placement)

print(f"\n{'family':11s} {'cut?':5s} {'anchor_dem':>10s} "
      f"{'authored_y':>18s} {'WORLD elev':>16s} {'DEM under':>16s} "
      f"{'max burial':>11s}")

for family in sorted(families):
    placements = families[family]
    authored_low = authored_high = None
    world_low = world_high = None
    ground_low = ground_high = None
    anchor_dems = []
    max_burial = -1e9
    burial_at = None
    for placement in placements:
        geom = geometry.get(placement.resource_path)
        if geom is None or not geom.solid_triangles:
            continue
        anchor_dem = _sample_dem(dem, TILE_LAT, TILE_LON,
                                 placement.latitude, placement.longitude)
        if anchor_dem is None or anchor_dem != anchor_dem:
            continue
        anchor_dems.append(anchor_dem)
        agl = float(placement.above_ground_level_metres or 0.0)
        used = {i for tri in geom.solid_triangles for i in tri}
        # sample at most ~400 vertices per placement, evenly
        used = sorted(used)
        step = max(1, len(used) // 400)
        for index in used[::step]:
            x, y, z = geom.vertices[index]
            effective = agl + y
            world = anchor_dem + effective
            latitude, longitude = obj8_reader.local_offset_to_lonlat(
                placement.latitude, placement.longitude,
                placement.heading_degrees, x, z)
            ground = _sample_dem(dem, TILE_LAT, TILE_LON,
                                 latitude, longitude)
            if ground is None or ground != ground:
                continue
            burial = ground - world
            authored_low = effective if authored_low is None else min(
                authored_low, effective)
            authored_high = effective if authored_high is None else max(
                authored_high, effective)
            world_low = world if world_low is None else min(world_low, world)
            world_high = world if world_high is None else max(
                world_high, world)
            ground_low = ground if ground_low is None else min(
                ground_low, ground)
            ground_high = ground if ground_high is None else max(
                ground_high, ground)
            if burial > max_burial:
                max_burial = burial
                burial_at = (latitude, longitude)
    if authored_low is None:
        continue
    is_cut = any(p.resource_path in carved for p in placements)
    print(f"{family:11s} {'YES' if is_cut else 'no':5s} "
          f"{sum(anchor_dems) / len(anchor_dems):10.2f} "
          f"{authored_low:8.2f}..{authored_high:<8.2f} "
          f"{world_low:7.2f}..{world_high:<7.2f} "
          f"{ground_low:7.2f}..{ground_high:<7.2f} "
          f"{max_burial:11.2f}")
    if burial_at is not None:
        print(f"{'':11s} deepest burial at {burial_at[0]:.6f},"
              f"{burial_at[1]:.6f}")
