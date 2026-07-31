"""Can the OTHH bridges reach the bridge classifier at all?

``_hard_face_components`` seeds bridge candidates on near-horizontal HARD
faces (_FACE_CLASS_HARD_NEAR_HORIZONTAL).  A structure with zero hard
area can never produce a BridgeStructure, whatever its shape — so the
deck-flush partition (W1b) would never see it.  The plan asserts the six
OTHH bridges carry no hard triangles; verify it on this tree before
designing anything around it, and show what the EGLL bridge (which DOES
classify) carries for contrast.

Run from Ortho4XP/ cwd.
"""
import os
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
AIRPORTS = [
    ("OTHH", os.path.join(XP, "Custom Scenery", "OTHH Doha (Aeroscape)",
                          "Earth nav data", "+20+050", "+25+051.dsf"),
     "Bridge_"),
    ("EGLL", os.path.join(XP, "Custom Scenery",
                          "c_GBR - 100_airport - EGLL_LONDON_TAIMODELS",
                          "Earth nav data", "+50-010", "+51-001.dsf"),
     "/4.obj"),
]

for icao, dsf_path, needle in AIRPORTS:
    if not os.path.exists(dsf_path):
        print(f"{icao}: DSF missing")
        continue
    lines = dsf_reader._load_dsf_text(dsf_path)
    terrain = [p for p in obj8_reader.read_dsf_object_placements(
        lines, accept_resource=lambda r: r.lower().endswith(".obj"))
        if p.placement_kind != "OBJECT_MSL"]
    pack_root = dsf_reader._pack_root_for_dsf(dsf_path)
    geometry = _load_object_geometry_by_resource(terrain, pack_root, XP)
    cache = otf._ResourceGeometryCache(geometry)

    families = defaultdict(list)
    for placement in terrain:
        if needle not in placement.resource_path:
            continue
        base = os.path.basename(placement.resource_path)
        if needle == "Bridge_":
            key = "Bridge_" + base.split("Bridge_")[1][:2]
        else:
            key = base
        families[key].append(placement)

    print(f"\n{icao}: {len(families)} families matching {needle!r}")
    print(f"{'family':14s} {'plc':>4s} {'tris':>8s} {'near-h m2':>11s} "
          f"{'HARD m2':>10s} {'hard tris':>10s} {'hard codes':>12s}")
    for family in sorted(families):
        placements = families[family]
        frame = otf._build_structure_frame(placements, geometry, cache)
        if not frame.triangle_count:
            print(f"{family:14s} {len(placements):4d} (no frame triangles)")
            continue
        near = frame.triangle_horizontality >= otf.NEAR_HORIZONTAL_NORMAL_Y_MIN
        hard = frame.triangle_hardness_codes > 0
        codes = sorted(set(frame.triangle_hardness_codes.tolist()))
        print(f"{family:14s} {len(placements):4d} "
              f"{frame.triangle_count:8d} "
              f"{float(frame.triangle_area_m2[near].sum()):11.1f} "
              f"{float(frame.triangle_area_m2[near & hard].sum()):10.1f} "
              f"{int((near & hard).sum()):10d} "
              f"{str(codes)[:12]:>12s}")
