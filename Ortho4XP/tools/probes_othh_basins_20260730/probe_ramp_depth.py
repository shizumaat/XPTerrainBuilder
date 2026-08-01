"""W3a — the terminal ramps, measured the RIGHT way.

Plan §1's measurement law: depth must be read from deck/floor faces against
the LOCAL ground, never from authored y (which is relative to the drape datum
at one point).  This applies that test to every non-bridge structure the sweep
flagged, so only genuinely-sunken decks proceed to a cutout.

Reads the classification sidecar + the pack; samples the same DEM the build
uses.  Run from Ortho4XP/ cwd.
"""
import os
import pickle
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.getcwd(), "src"))
sys.path.insert(0, os.getcwd())

import numpy  # noqa: E402

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
BELOW_GRADE_M = 1.0

lines = dsf_reader._load_dsf_text(DSF)
terrain = [p for p in obj8_reader.read_dsf_object_placements(
    lines, accept_resource=lambda r: r.lower().endswith(".obj"))
    if p.placement_kind != "OBJECT_MSL"]
geometry = _load_object_geometry_by_resource(
    terrain, dsf_reader._pack_root_for_dsf(DSF), XP)
result = pickle.load(open(CACHE, "rb"))["result"]
dem = _load_airport_dem(25.2539, 51.6221)

# every interface that carries a below-grade LEVEL, plus the sweep's
# terminal-ramp resources, grouped by the interface's own resource set
interesting = {}
for interface in result.ground_interfaces:
    below = [lv for lv in interface.interface_levels if lv[0] < -1.0]
    if below or any("TerminalRoads" in r for r in interface.object_resources):
        interesting[interface.object_resources[0]] = interface

by_resource = defaultdict(list)
for placement in terrain:
    by_resource[placement.resource_path].append(placement)

print(f"{'structure':34s} {'faces>1m below LOCAL ground':>28s}  "
      f"{'deck part':>10s}  {'deepest':>8s}")
for key, interface in sorted(interesting.items()):
    placements = [p for r in interface.object_resources
                  for p in by_resource.get(r, [])]
    if not placements:
        continue
    below_area = 0.0
    below_deck_area = 0.0
    total_area = 0.0
    deepest = 0.0
    for placement in placements:
        geom = geometry.get(placement.resource_path)
        if geom is None or not geom.solid_triangles:
            continue
        anchor_ground = _sample_dem(dem, TILE_LAT, TILE_LON,
                                    placement.latitude, placement.longitude)
        if anchor_ground is None or anchor_ground != anchor_ground:
            continue
        agl = float(placement.above_ground_level_metres or 0.0)
        vertices = geom.vertices
        for tri in geom.solid_triangles:
            try:
                corners = [vertices[i] for i in tri]
            except IndexError:
                continue
            mean_y = sum(c[1] for c in corners) / 3.0
            mean_x = sum(c[0] for c in corners) / 3.0
            mean_z = sum(c[2] for c in corners) / 3.0
            # horizontal area of the face (deck-likeness proxy)
            ax, az = corners[1][0] - corners[0][0], corners[1][2] - corners[0][2]
            bx, bz = corners[2][0] - corners[0][0], corners[2][2] - corners[0][2]
            plan_area = abs(ax * bz - az * bx) / 2.0
            if plan_area <= 0.0:
                continue
            total_area += plan_area
            world = anchor_ground + agl + mean_y
            latitude, longitude = obj8_reader.local_offset_to_lonlat(
                placement.latitude, placement.longitude,
                placement.heading_degrees, mean_x, mean_z)
            ground = _sample_dem(dem, TILE_LAT, TILE_LON,
                                 latitude, longitude)
            if ground is None or ground != ground:
                continue
            depth = ground - world
            if depth > deepest:
                deepest = depth
            if depth > BELOW_GRADE_M:
                below_area += plan_area
                # a near-horizontal face is deck/floor, not a wall stub
                v1 = numpy.subtract(corners[1], corners[0])
                v2 = numpy.subtract(corners[2], corners[0])
                normal = numpy.cross(v1, v2)
                norm = numpy.linalg.norm(normal)
                if norm > 0 and abs(normal[1]) / norm >= 0.7:
                    below_deck_area += plan_area
    name = os.path.basename(key)[:34]
    verdict = ("CARVE — real sunken deck" if below_deck_area >= 20.0
               else "no (stubs only)" if below_area > 0 else "no")
    print(f"{name:34s} {below_area:12,.0f} m2 of {total_area:9,.0f}  "
          f"{below_deck_area:8,.0f} m2  {deepest:7.2f}  {verdict}")
