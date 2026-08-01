"""What do the OTHH bridge OBJECT FILES actually say about height?

Answers the owner's question directly: per bridge, where the solid face AREA
sits in authored y (the drape datum, y=0 = terrain at the placement anchor),
split into near-horizontal DECK faces and everything else — and what the deck
does at the two ENDS of its long axis, which is the surface that should be
flush with grade.

Run from Ortho4XP/ cwd.
"""
import math
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.getcwd(), "src"))
sys.path.insert(0, os.getcwd())

import numpy  # noqa: E402

from auto_patch import dsf_reader, obj8_reader  # noqa: E402
from auto_patch import object_terrain_features as otf  # noqa: E402
from auto_patch.object_terrain_assembly import (  # noqa: E402
    _load_object_geometry_by_resource,
)

XP = "/Users/noah/X-Plane 12"
DSF = os.path.join(XP, "Custom Scenery", "OTHH Doha (Aeroscape)",
                   "Earth nav data", "+20+050", "+25+051.dsf")

lines = dsf_reader._load_dsf_text(DSF)
terrain = [p for p in obj8_reader.read_dsf_object_placements(
    lines, accept_resource=lambda r: r.lower().endswith(".obj"))
    if p.placement_kind != "OBJECT_MSL"]
geometry = _load_object_geometry_by_resource(
    terrain, dsf_reader._pack_root_for_dsf(DSF), XP)

families = defaultdict(list)
for placement in terrain:
    base = os.path.basename(placement.resource_path)
    if "Bridge_" not in base:
        continue
    key = base.split("Bridge_")[1][:2]
    if key.isdigit():
        families[f"Bridge_{key}"].append(placement)

DECK_HORIZONTALITY = otf.NEAR_HORIZONTAL_NORMAL_Y_MIN

for family in sorted(families):
    frame = otf._build_structure_frame(families[family], geometry)
    if frame.triangle_count == 0:
        continue
    height = numpy.asarray(frame.triangle_height_m)
    area = numpy.asarray(frame.triangle_area_m2)
    horizontality = numpy.asarray(frame.triangle_horizontality)
    deck_mask = horizontality >= DECK_HORIZONTALITY
    total = float(area.sum())
    print(f"\n{'=' * 66}\n{family}   solid faces={frame.triangle_count}  "
          f"total area={total:,.0f} m2   "
          f"near-horizontal share={float(area[deck_mask].sum()) / total:.2f}")

    # where the AREA sits, by 1 m band of authored y
    print("   authored y band     all faces      near-horizontal (deck-like)")
    bands = defaultdict(lambda: [0.0, 0.0])
    for h, a, d in zip(height.tolist(), area.tolist(), deck_mask.tolist()):
        key = math.floor(h)
        bands[key][0] += a
        if d:
            bands[key][1] += a
    for key in sorted(bands):
        all_area, deck_area = bands[key]
        if all_area < 1.0:
            continue
        bar = "#" * min(40, int(40 * all_area / max(total, 1e-9) * 4))
        print(f"   {key:+4d}..{key + 1:+4d} m   {all_area:9,.0f}   "
              f"{deck_area:9,.0f}  {bar}")

    # the deck itself, along its long axis
    if deck_mask.any():
        cx = numpy.asarray(frame.triangle_centroid_x_m)[deck_mask]
        cz = numpy.asarray(frame.triangle_centroid_z_m)[deck_mask]
        dy = height[deck_mask]
        da = area[deck_mask]
        # principal axis of the deck centroids
        points = numpy.column_stack([cx, cz])
        centred = points - points.mean(axis=0)
        _u, _s, vectors = numpy.linalg.svd(centred, full_matrices=False)
        axis = vectors[0]
        along = centred @ axis
        order = numpy.argsort(along)
        span = float(along.max() - along.min())
        # weighted mean deck height in the first/last 10 % of the span
        edge = 0.10 * span
        low_end = along <= along.min() + edge
        high_end = along >= along.max() - edge
        def weighted(mask):
            if not mask.any() or da[mask].sum() <= 0:
                return float("nan")
            return float((dy[mask] * da[mask]).sum() / da[mask].sum())
        print(f"   deck span {span:,.0f} m along its own axis; "
              f"deck y at the two ENDS: "
              f"{weighted(low_end):+.2f} m and {weighted(high_end):+.2f} m; "
              f"crest {float(dy.max()):+.2f} m")
        deepest_deck = float(dy.min())
        print(f"   deck y range {deepest_deck:+.2f} .. {float(dy.max()):+.2f}"
              f"   |   ALL-face y range {float(height.min()):+.2f} .. "
              f"{float(height.max()):+.2f}")
        below = area[(height < -1.0)].sum()
        below_deck = da[(dy < -1.0)].sum()
        print(f"   face area more than 1 m below datum: {float(below):,.0f} "
              f"m2 total, of which deck-like {float(below_deck):,.0f} m2 "
              f"({float(below) / total * 100:.1f} % of the structure)")
