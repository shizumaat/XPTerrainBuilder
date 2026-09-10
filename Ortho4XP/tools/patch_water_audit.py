"""DOES THE PATCH STAND ON WATER? (owner RULINGS 2026-09-09z (3)).

The EMIT-side half of the shore acceptance, beside the mesh-side
``mesh_region_tris.py --water-audit``: given an emitted patch ``.osm``
and its tile, how much of the BANKED REGION covers water and how many
bank-foot nodes stand inside it.

The banked region is read exactly as the mesh reads it (spec
``auto-patch-v2/design-surface-spec.md`` §13.3): the ``o4_feature=
bank_foot`` closed ways are the region's rings, an exterior ring is one
that no other ring contains, and ``banked = union(exteriors) −
union(holes)``.  A ring that follows the water line is a HOLE — counting
ring polygons naively reports its area TWICE and reads as a violation
when the cut is in fact exact (measured at OTHH 2026-09-09: naive
3,218 m², true 0.0 m²).

The water is the tile's own witness (``O4_Vector_Map.cached_tile_water``
— cache only, never a download), the one every consumer reads.

    venv/bin/python tools/patch_water_audit.py PATCH.osm --tile 25 51
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "src"))

#: m² per square degree at the tile's latitude band (the figure the mesh
#: tools use: metres per degree of latitude, times the cosine of the
#: band's centre for longitude).
_M_PER_DEG = 111120.0

BANK_FEATURE = "bank_foot"


def patch_water_audit(patch_osm: str, lat: int, lon: int) -> dict:
    """The payload; prints it."""
    import math

    from shapely.geometry import Point, Polygon
    from shapely.ops import unary_union

    import O4_Config_Utils as CFG
    import O4_Vector_Map as VMAP

    tile = CFG.Tile(int(lat), int(lon), "")
    tile.read_from_config()
    sea, inland = VMAP.cached_tile_water(tile)
    parts = [g for g in (sea, inland) if g is not None]
    if not parts:
        print(f"patch water audit — NO cached water layer for +{lat}+{lon}: "
              "nothing claimed (never a download)")
        return {"water": None}
    water = unary_union(parts)
    m2 = _M_PER_DEG * _M_PER_DEG * math.cos(math.radians(lat + 0.5))

    root = ET.parse(patch_osm).getroot()
    nodes = {n.get("id"): (float(n.get("lon")) - lon, float(n.get("lat")) - lat)
             for n in root.iter("node")}
    rings = []
    for way in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in way.findall("tag")}
        if tags.get("o4_feature") != BANK_FEATURE:
            continue
        pts = [nodes[nd.get("ref")] for nd in way.findall("nd")]
        if len(pts) < 4:
            continue
        poly = Polygon(pts)
        if not poly.is_valid:
            poly = poly.buffer(0)
        rings.append((tags.get("ref"), pts, poly))

    inside = [(ref, p) for ref, pts, _ in rings for p in pts
              if water.contains(Point(p))]
    depth = max((water.boundary.distance(Point(p)) * _M_PER_DEG
                 for _ref, p in inside), default=0.0)
    outer = [poly for _r, _p, poly in rings
             if not any(poly.within(o) and poly.area < o.area
                        for _r2, _p2, o in rings)]
    holes = [poly for _r, _p, poly in rings if poly not in outer]
    region = unary_union(outer) if outer else None
    if region is not None and holes:
        region = region.difference(unary_union(holes))
    over = 0.0 if region is None else region.intersection(water).area * m2
    payload = {
        "patch": patch_osm, "tile": [int(lat), int(lon)],
        "bank_rings": len(rings), "exterior_rings": len(outer),
        "hole_rings": len(holes),
        "foot_nodes": sum(len(p) for _r, p, _q in rings),
        "foot_nodes_in_water": len(inside),
        "deepest_node_inside_m": round(depth, 3),
        "banked_region_m2": 0.0 if region is None else round(region.area * m2, 1),
        "banked_over_water_m2": round(over, 1),
    }
    print(f"patch water audit — {patch_osm} (+{lat}+{lon})")
    print(f"  bank rings {payload['bank_rings']} "
          f"({payload['exterior_rings']} exterior, {payload['hole_rings']} "
          f"hole), foot nodes {payload['foot_nodes']}")
    print(f"  foot nodes inside water {payload['foot_nodes_in_water']} "
          f"(deepest {payload['deepest_node_inside_m']:.3f} m inside the line)")
    print(f"  banked region {payload['banked_region_m2']:.0f} m2, "
          f"OVER WATER {payload['banked_over_water_m2']:.1f} m2")
    return payload


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("patch")
    ap.add_argument("--tile", nargs=2, type=int, required=True,
                    metavar=("LAT", "LON"))
    ap.add_argument("--json", metavar="OUT.json")
    args = ap.parse_args()
    out = patch_water_audit(args.patch, args.tile[0], args.tile[1])
    if args.json:
        with open(args.json, "w") as handle:
            json.dump(out, handle, indent=1)
