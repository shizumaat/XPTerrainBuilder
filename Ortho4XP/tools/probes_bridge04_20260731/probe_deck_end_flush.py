"""W1's acceptance measurement, offline: how flush is each deck END?

Owner ruling 2026-07-31: the six OTHH bridges are above-ground road
bridges and "just need to be set so their top edge (the road deck) at
either end is flush with grade".  The plan asks for the terrain-vs-deck-end
delta on all TWELVE ends, so "the others are unchanged" is demonstrated
rather than assumed.

Measured here against the DEM directly (no build): for each bridge family
the deck top profile is rebuilt with the classifier's own helpers
(``_deck_axis`` + ``_deck_top_profile``), and each end's WORLD elevation
(terrain(anchor) + AGL + deck-end y) is compared with the DEM under that
end.  Positive delta = the deck end stands above the ground; negative =
the ground stands over it.

Also reports WHY each family fails to become a BridgeStructure, which is
the prerequisite W1b's partition outcome depends on:
  * no hard near-horizontal face  -> only the COSMETIC limb can fire
  * cosmetic limb needs >= BRIDGE_MIN_DECK_AREA_M2 of deck at or above
    BRIDGE_DECK_CARRIED_MIN_HEIGHT_M (+2.0 m)
  * and the pool must have no hard components at all (whole-pool path)

Run from Ortho4XP/ cwd.
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.getcwd(), "src"))
sys.path.insert(0, os.getcwd())

from auto_patch import dsf_reader, obj8_reader  # noqa: E402
from auto_patch import object_terrain_features as otf  # noqa: E402
from auto_patch.elevation import _load_airport_dem, _sample_dem  # noqa: E402
from auto_patch.object_anchor import discover_object_pools  # noqa: E402
from auto_patch.object_terrain_assembly import (  # noqa: E402
    _load_object_geometry_by_resource,
)

XP = "/Users/noah/X-Plane 12"
DSF = os.path.join(XP, "Custom Scenery", "OTHH Doha (Aeroscape)",
                   "Earth nav data", "+20+050", "+25+051.dsf")
TILE_LAT, TILE_LON = 25, 51
AIRPORT_LAT, AIRPORT_LON = 25.2539, 51.6221

lines = dsf_reader._load_dsf_text(DSF)
terrain = [p for p in obj8_reader.read_dsf_object_placements(
    lines, accept_resource=lambda r: r.lower().endswith(".obj"))
    if p.placement_kind != "OBJECT_MSL"]
pack_root = dsf_reader._pack_root_for_dsf(DSF)
geometry = _load_object_geometry_by_resource(terrain, pack_root, XP)
cache = otf._ResourceGeometryCache(geometry)
dem = _load_airport_dem(AIRPORT_LAT, AIRPORT_LON)
print(f"DEM loaded: {dem is not None}")

# Which pool does each bridge land in?  A bridge absorbed into a pool that
# owns hard faces can never reach the whole-pool cosmetic limb.
resolved = {p.resource_path: p.resource_path for p in terrain
            if p.resource_path in geometry}
pools = discover_object_pools(list(terrain), resolved, geometry,
                              epsilon_metres=otf.STRUCTURE_GROUPING_EPSILON_M)
pool_of = {}
for index, pool in enumerate(pools):
    for placement in pool.placements:
        pool_of.setdefault(placement.resource_path, (index,
                                                     len(pool.placements)))

families = defaultdict(list)
for placement in terrain:
    if "Bridge_" not in placement.resource_path:
        continue
    base = os.path.basename(placement.resource_path)
    families["Bridge_" + base.split("Bridge_")[1][:2]].append(placement)

print(f"\n{'family':11s} {'pool#':>6s} {'poolN':>6s} {'poolHard':>9s} "
      f"{'deck>=+2 m2':>12s} {'cosmetic?':>10s}")
for family in sorted(families):
    placements = families[family]
    pool_index, pool_size = pool_of.get(
        placements[0].resource_path, (-1, 0))
    pool_hard = "?"
    if 0 <= pool_index < len(pools):
        pool_frame = otf._build_structure_frame(
            pools[pool_index].placements, geometry, cache)
        pool_hard = bool((pool_frame.triangle_hardness_codes > 0).any())
    frame = otf._build_structure_frame(placements, geometry, cache)
    near = frame.triangle_horizontality >= otf.NEAR_HORIZONTAL_NORMAL_Y_MIN
    elevated = float(frame.triangle_area_m2[
        near & (frame.triangle_height_m
                >= otf.BRIDGE_DECK_CARRIED_MIN_HEIGHT_M)].sum())
    verdict = ("blocked: pool owns hard faces" if pool_hard
               else ("cosmetic OK" if elevated >= otf.BRIDGE_MIN_DECK_AREA_M2
                     else f"blocked: {elevated:.0f} < "
                          f"{otf.BRIDGE_MIN_DECK_AREA_M2:.0f} m2"))
    print(f"{family:11s} {pool_index:6d} {pool_size:6d} {str(pool_hard):>9s} "
          f"{elevated:12.1f} {verdict:>10s}")

print(f"\n{'family':11s} {'end':>4s} {'deck y':>8s} {'world':>9s} "
      f"{'ground':>9s} {'delta':>8s}  (delta>0 = deck end above ground)")
for family in sorted(families):
    placements = families[family]
    frame = otf._build_structure_frame(placements, geometry, cache)
    if not frame.triangle_count:
        continue
    near_horizontal = [t for t in frame.triangles
                       if t.horizontality >= otf.NEAR_HORIZONTAL_NORMAL_Y_MIN]
    if not near_horizontal:
        continue
    deck_polygon = otf._union_horizontal(
        near_horizontal, close_m=otf.BRIDGE_DECK_CLOSE_M, keep_all_parts=True)
    if deck_polygon is None:
        print(f"{family:11s} (no deck polygon)")
        continue
    axis = otf._deck_axis(deck_polygon)
    if axis is None:
        print(f"{family:11s} (degenerate axis)")
        continue
    profile = otf._deck_top_profile(near_horizontal, axis)
    if not profile:
        print(f"{family:11s} (no profile)")
        continue
    reference = placements[0]
    anchor_dem = _sample_dem(dem, TILE_LAT, TILE_LON,
                             reference.latitude, reference.longitude)
    if anchor_dem is None or anchor_dem != anchor_dem:
        print(f"{family:11s} (no anchor DEM)")
        continue
    for end_index, line in enumerate(axis.abutment_lines):
        (x0, z0), (x1, z1) = line
        mid_x, mid_z = (x0 + x1) / 2.0, (z0 + z1) / 2.0
        deck_y = profile[0][1] if end_index == 0 else profile[-1][1]
        # Frame (x, z) are metres east/south of the frame origin.
        longitude, latitude = otf.frame_xz_to_longitude_latitude(
            mid_x, mid_z, frame.origin_longitude, frame.origin_latitude
        ) if hasattr(otf, "frame_xz_to_longitude_latitude") else (None, None)
        if longitude is None:
            from shapely.geometry import Point
            converted = otf.frame_polygon_to_longitude_latitude(
                Point(mid_x, mid_z).buffer(0.5),
                (frame.origin_longitude, frame.origin_latitude),
            )
            longitude, latitude = (converted.centroid.x, converted.centroid.y)
        ground = _sample_dem(dem, TILE_LAT, TILE_LON, latitude, longitude)
        world = anchor_dem + deck_y
        if ground is None or ground != ground:
            print(f"{family:11s} {end_index:4d} {deck_y:8.2f} {world:9.2f} "
                  f"{'  no DEM':>9s}")
            continue
        print(f"{family:11s} {end_index:4d} {deck_y:8.2f} {world:9.2f} "
              f"{ground:9.2f} {world - ground:8.2f}")
