"""Fine height-band ladder for the AGL-limb candidates + the EGLL shells.

Follow-up to ``probe_agl_limb.py``, which showed the separating signal is
the DEPTH of the below-grade near-horizontal area, not its total:

    Bridge_04   <=-0.5 1022.1   <=-1.0    8.4   <=-2.0   0.0
    EGLL 7.obj  <=-0.5   89.8   <=-1.0   52.8   <=-2.0  19.4

i.e. Bridge_04's "below-grade deck" is the UNDERSIDE of an at-grade slab
(0.5-1.0 m of slab thickness), while a true shell has a real floor.  The
plan's literal candidate (floor at TUNNEL_MIN_BODY_DEPTH_M = 2.0) would
drop EGLL 7.obj to 19.4 m2, under the 25 m2 gate — it must be measured,
not assumed.

This prints the full ladder for every AGL-limb candidate and, at EGLL,
every numbered tunnel object in the pack (6/7/10 are the historical AGL
shells named in the TUNNEL_AGL_* constant comments) with its placement
offset, so the constants' provenance can be re-checked against the pack
that is actually installed.

Run from Ortho4XP/ cwd.
"""
import os
import re
import sys

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
                          "Earth nav data", "+20+050", "+25+051.dsf")),
    ("EGLL", os.path.join(XP, "Custom Scenery",
                          "c_GBR - 100_airport - EGLL_LONDON_TAIMODELS",
                          "Earth nav data", "+50-010", "+51-001.dsf")),
]

# Bands are LOWER edges: area of near-horizontal face at or below each.
BELOW = (0.5, 0.75, 1.0, 1.5, 2.0, 3.0)
# Bands are LOWER edges: area of near-horizontal face at or above each.
ABOVE = (-0.5, 0.0, 0.5, 1.0, 2.0)

NUMBERED = re.compile(r"^\d+\.obj$", re.IGNORECASE)


def ladder(frame):
    near = frame.triangle_horizontality >= otf.NEAR_HORIZONTAL_NORMAL_Y_MIN
    below = [
        float(frame.triangle_area_m2[
            near & (frame.triangle_height_m <= -d)].sum())
        for d in BELOW
    ]
    above = [
        float(frame.triangle_area_m2[
            near & (frame.triangle_height_m >= h)].sum())
        for h in ABOVE
    ]
    return below, above


def main():
    original = otf._agl_tunnel_seed_resources
    rows = []

    def instrumented(placements, frame):
        seeds = original(placements, frame)
        if frame.triangle_count:
            below, above = ladder(frame)
            rows.append({
                "name": os.path.basename(frame.triangle_resource_paths[0]),
                "n": len(frame.triangle_resource_paths),
                "crest": float(frame.triangle_height_m.max()),
                "floor": float(frame.triangle_height_m.min()),
                "below": below,
                "above": above,
                "seeds": len(seeds),
            })
        return seeds

    otf._agl_tunnel_seed_resources = instrumented
    try:
        for icao, dsf_path in AIRPORTS:
            if not os.path.exists(dsf_path):
                print(f"{icao}: DSF missing")
                continue
            rows.clear()
            lines = dsf_reader._load_dsf_text(dsf_path)
            all_placements = obj8_reader.read_dsf_object_placements(
                lines, accept_resource=lambda r: r.lower().endswith(".obj"),
                include_object_msl=True)
            terrain = [p for p in all_placements
                       if p.placement_kind != "OBJECT_MSL"]
            msl = [p for p in all_placements
                   if p.placement_kind == "OBJECT_MSL"]
            pack_root = dsf_reader._pack_root_for_dsf(dsf_path)
            geometry = _load_object_geometry_by_resource(
                terrain, pack_root, XP)

            if icao == "EGLL":
                print(f"\n--- EGLL numbered tunnel objects in the pack ---")
                print(f"{'resource':14s} {'kind':12s} {'agl':>7s} "
                      f"{'placements':>10s} {'tris':>7s}")
                by_resource = {}
                for placement in terrain:
                    base = os.path.basename(placement.resource_path)
                    if NUMBERED.match(base):
                        by_resource.setdefault(
                            placement.resource_path, []).append(placement)
                for resource in sorted(by_resource):
                    group = by_resource[resource]
                    geom = geometry.get(resource)
                    print(f"{os.path.basename(resource):14s} "
                          f"{group[0].placement_kind:12s} "
                          f"{float(group[0].above_ground_level_metres or 0):7.2f} "
                          f"{len(group):10d} "
                          f"{len(geom.solid_triangles) if geom else 0:7d}")

            result = otf.classify_object_terrain_features(
                terrain, geometry, mean_sea_level_placements=msl,
                pack_root=pack_root or "")
            print(f"\n{'=' * 120}")
            print(f"{icao}: {len(result.tunnels)} tunnels "
                  f"({sorted(os.path.basename(list(t.object_resources)[0]) for t in result.tunnels)})")
            print(f"{'=' * 120}")
            print(f"{'structure':30s} {'n':>4s} {'crest':>7s} {'floor':>7s} | "
                  + " ".join(f"{'>=' + str(h):>8s}" for h in ABOVE)
                  + " | " + " ".join(f"{'<=-' + str(d):>8s}" for d in BELOW)
                  + f" {'seed':>4s}")
            seen = set()
            for row in rows:
                key = (row["name"], round(row["crest"], 2),
                       round(row["floor"], 2))
                if key in seen:
                    continue
                seen.add(key)
                if row["seeds"] == 0 and row["below"][0] < 20.0:
                    continue
                if row["crest"] > 25.0 and row["seeds"] == 0:
                    continue
                print(f"{row['name'][:30]:30s} {row['n']:4d} "
                      f"{row['crest']:7.2f} {row['floor']:7.2f} | "
                      + " ".join(f"{a:8.1f}" for a in row["above"])
                      + " | " + " ".join(f"{b:8.1f}" for b in row["below"])
                      + f" {row['seeds']:4d}")
    finally:
        otf._agl_tunnel_seed_resources = original


if __name__ == "__main__":
    main()
