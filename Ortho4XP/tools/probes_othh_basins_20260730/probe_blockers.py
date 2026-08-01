"""Why do Drainage_02 (no floor) and Drainage_06 (962 of 5 720 m2) still
lack a trench floor, when NO pavement covers either?

Replays the emitter's floor-geometry computation per pit body against the
built layout and names, by role and ref, whatever eats the floor pan.

Run from Ortho4XP/ cwd.
"""
import os
import pickle
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.getcwd(), "tools"))
sys.path.insert(0, os.path.join(os.getcwd(), "src"))
sys.path.insert(0, os.getcwd())

import _diag  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from auto_patch import object_terrain_features as otf  # noqa: E402
from auto_patch.layout import ROLE_TUNNEL_TRENCH  # noqa: E402
from auto_patch.object_terrain_assembly import (  # noqa: E402
    _TUNNEL_FLOOR_OWNED_CLEARANCE_M,
    _TUNNEL_RIM_BAND_WIDTH_M,
    _TUNNEL_WALL_SETBACK_M,
)

CACHE = ("Airport_mod_cache/OTHH Doha (Aeroscape)/"
         "o4_object_terrain_classification_+25+051.cache")

layout = _diag.build("OTHH")
print("\n\n" + "#" * 74)
print("FLOOR BLOCKERS — what owns the ground over each pit")
print("#" * 74)

result = pickle.load(open(CACHE, "rb"))["result"]
to_m = layout.ll_to_m


def body_in_metres(interface):
    geographic = otf.frame_polygon_to_longitude_latitude(
        interface.below_grade_footprint,
        interface.frame_origin_longitude_latitude)
    parts = (list(geographic.geoms)
             if geographic.geom_type == "MultiPolygon" else [geographic])
    metre = []
    for part in parts:
        ring = [to_m(lat, lon) for lon, lat in part.exterior.coords]
        if len(ring) < 3:
            continue
        polygon = Polygon(ring)
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        if not polygon.is_empty:
            metre.append(polygon)
    return unary_union(metre) if metre else None


# Everything that is NOT one of our own basin plates counts as an owner —
# the emitter's own output must not be read back as the blocker.
owners = [
    shape for shape in layout.shapes
    if shape.polygon is not None and not shape.polygon.is_empty
    and not (shape.role == ROLE_TUNNEL_TRENCH
             and str(shape.ref).startswith("object_basin"))
]

for interface in sorted(result.ground_interfaces,
                        key=lambda i: i.object_resources[0]):
    if not otf.is_carved_basin_interface(interface):
        continue
    name = os.path.basename(interface.object_resources[0])
    body = body_in_metres(interface)
    if body is None:
        print(f"\n{name}: no metre body")
        continue
    inset = body.buffer(-_TUNNEL_WALL_SETBACK_M, join_style=2,
                        mitre_limit=2.0)
    envelope = body.buffer(
        _TUNNEL_WALL_SETBACK_M + _TUNNEL_RIM_BAND_WIDTH_M + 1.0)
    near = [s for s in owners if s.polygon.intersects(envelope)]
    blocking = defaultdict(float)
    for shape in near:
        try:
            overlap = shape.polygon.intersection(inset).area
        except Exception:
            overlap = 0.0
        if overlap > 0.5:
            blocking[(shape.role, str(shape.ref))] += overlap
    if blocking:
        eaten = unary_union([
            s.polygon for s in near
            if s.polygon.intersects(inset)]).intersection(envelope).buffer(
                _TUNNEL_FLOOR_OWNED_CLEARANCE_M, join_style=2,
                mitre_limit=2.0)
        remaining = inset.difference(eaten)
    else:
        remaining = inset
    usable = sum(
        p.area for p in (list(remaining.geoms)
                         if remaining.geom_type == "MultiPolygon"
                         else [remaining])
        if p.geom_type == "Polygon" and p.area >= 4.0)
    print(f"\n{name}  body={body.area:,.0f} m2  inset={inset.area:,.0f} "
          f"m2  floor-after-owners={usable:,.0f} m2")
    for (role, ref), area in sorted(blocking.items(), key=lambda kv: -kv[1]):
        print(f"    blocked by {role:22s} ref={ref!r:24s} {area:9,.0f} m2")
    if not blocking:
        print("    nothing overlaps the inset body")
