"""Isolated frames for the three EGLL AGL shells named in the constants.

``TUNNEL_AGL_MAX_ABOVE_GRADE_HEIGHT_M``'s comment (2026-07-18) warns that
"an above-grade AREA test cannot do this job: Tunnel/10 carries MORE
near-horizontal area above grade (128.7 m2) than below (55.1 m2)".  That
warning is about a FRACTION test (above vs below).  The Bridge_04
discriminator under consideration is an ABSOLUTE floor on the area standing
CLEARLY above the at-grade band (>= +TUNNEL_ROOF_TOP_TOLERANCE_M), so the
number that matters is Tunnel/10's area in THAT band, which has never been
measured.  Measure it, plus 6 and 7, on the installed pack.

Run from Ortho4XP/ cwd.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), "src"))
sys.path.insert(0, os.getcwd())

from auto_patch import dsf_reader, obj8_reader  # noqa: E402
from auto_patch import object_terrain_features as otf  # noqa: E402
from auto_patch.object_terrain_assembly import (  # noqa: E402
    _load_object_geometry_by_resource,
)

XP = "/Users/noah/X-Plane 12"
DSF = os.path.join(XP, "Custom Scenery",
                   "c_GBR - 100_airport - EGLL_LONDON_TAIMODELS",
                   "Earth nav data", "+50-010", "+51-001.dsf")

WANTED = ("/6.obj", "/7.obj", "/10.obj", "/11.obj", "/12.obj")
ABOVE = (-0.5, 0.0, 0.5, 1.0, 2.0)
BELOW = (0.5, 1.0, 1.5, 2.0)

lines = dsf_reader._load_dsf_text(DSF)
terrain = [p for p in obj8_reader.read_dsf_object_placements(
    lines, accept_resource=lambda r: r.lower().endswith(".obj"))
    if p.placement_kind != "OBJECT_MSL"]
pack_root = dsf_reader._pack_root_for_dsf(DSF)
geometry = _load_object_geometry_by_resource(terrain, pack_root, XP)
cache = otf._ResourceGeometryCache(geometry)

print(f"{'resource':40s} {'kind':11s} {'agl':>6s} {'crest':>7s} {'floor':>7s}"
      " | " + " ".join(f"{'>=' + str(h):>8s}" for h in ABOVE)
      + " | " + " ".join(f"{'<=-' + str(d):>8s}" for d in BELOW))
for placement in terrain:
    if not any(placement.resource_path.endswith(w) for w in WANTED):
        continue
    if placement.resource_path not in geometry:
        continue
    frame = otf._build_structure_frame([placement], geometry, cache)
    if not frame.triangle_count:
        print(f"{placement.resource_path[-40:]:40s} (no frame triangles)")
        continue
    near = frame.triangle_horizontality >= otf.NEAR_HORIZONTAL_NORMAL_Y_MIN
    above = [float(frame.triangle_area_m2[
        near & (frame.triangle_height_m >= h)].sum()) for h in ABOVE]
    below = [float(frame.triangle_area_m2[
        near & (frame.triangle_height_m <= -d)].sum()) for d in BELOW]
    print(f"{placement.resource_path[-40:]:40s} "
          f"{placement.placement_kind:11s} "
          f"{float(placement.above_ground_level_metres or 0):6.2f} "
          f"{float(frame.triangle_height_m.max()):7.2f} "
          f"{float(frame.triangle_height_m.min()):7.2f} | "
          + " ".join(f"{a:8.1f}" for a in above)
          + " | " + " ".join(f"{b:8.1f}" for b in below))
