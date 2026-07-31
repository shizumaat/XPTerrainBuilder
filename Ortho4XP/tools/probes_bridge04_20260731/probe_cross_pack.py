"""Cross-pack effect of the cosmetic-bridge COMPONENT pass.

The change classifies hard-less, name-hinted bridge candidates per
component instead of per pool.  It is scoped by
``COSMETIC_BRIDGE_NAME_HINT`` on structures with ZERO hard triangles, so
nothing that reaches the geometric deck path can be diverted — but every
installed pack that owns a hard-less "bridge"-named object is still in
range, and the tunnel/bridge fixtures for most of them SKIP (pack dumps
absent), so the unit suite is not the net here.

Prints tunnels / bridges / refusals per pack.  Run twice — once with the
component pass forced off — to get an honest before/after.

Run from Ortho4XP/ cwd:
    venv/bin/python tools/probes_bridge04_20260731/probe_cross_pack.py
    venv/bin/python tools/probes_bridge04_20260731/probe_cross_pack.py --off
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
SCENERY = os.path.join(XP, "Custom Scenery")

PACKS = [
    ("OTHH", "OTHH Doha (Aeroscape)"),
    ("EGLL", "c_GBR - 100_airport - EGLL_LONDON_TAIMODELS"),
    ("KBNA", "US-KBNA Nashville Airport"),
    ("KMCO", "c_USA - 100_airport - KMCO - Orlando (Nimbus Simulation)"),
    ("EGGW", "c_GBR - 100_airport - EGGW London Luton (UK2000 2020HD)"),
    ("ELLX", "c_LUX - 100_airport - ELLX_JustSim_XPL12_v1.0"),
    ("LFPG", "c_FRA - 100_airport - 1_LFPG_PARIS_T1_2_3_XP12"),
]


def dsf_paths(pack_name):
    root = os.path.join(SCENERY, pack_name, "Earth nav data")
    found = []
    for directory, _subdirs, files in os.walk(root):
        for name in files:
            if name.lower().endswith(".dsf"):
                found.append(os.path.join(directory, name))
    return sorted(found)


def short(resources):
    names = sorted(os.path.basename(r) for r in resources)
    return names[0][:34] if names else "(none)"


off = "--off" in sys.argv
if off:
    otf._cosmetic_bridge_components = lambda *_a, **_k: []
    print("*** COMPONENT PASS FORCED OFF (whole-pool baseline) ***")

for icao, pack_name in PACKS:
    paths = dsf_paths(pack_name)
    if not paths:
        print(f"\n{icao}: no DSF found under {pack_name!r}")
        continue
    for dsf_path in paths:
        try:
            lines = dsf_reader._load_dsf_text(dsf_path)
            every = obj8_reader.read_dsf_object_placements(
                lines,
                accept_resource=lambda r: r.lower().endswith(".obj"),
                include_object_msl=True,
            )
            terrain = [p for p in every
                       if p.placement_kind != "OBJECT_MSL"]
            msl = [p for p in every if p.placement_kind == "OBJECT_MSL"]
            if not terrain:
                continue
            pack_root = dsf_reader._pack_root_for_dsf(dsf_path)
            geometry = _load_object_geometry_by_resource(
                terrain, pack_root, XP)
            if not geometry:
                continue
            result = otf.classify_object_terrain_features(
                terrain, geometry, mean_sea_level_placements=msl,
                pack_root=pack_root or "")
        except Exception as error:            # noqa: BLE001 - probe
            print(f"\n{icao} {os.path.basename(dsf_path)}: FAILED {error}")
            continue
        print(f"\n{icao} {os.path.basename(dsf_path)}: "
              f"{len(result.tunnels)} tunnel(s), "
              f"{len(result.bridges)} bridge(s), "
              f"{len(result.refusals)} refusal(s)")
        for bridge in result.bridges:
            print(f"    BRIDGE  {short(bridge.object_resources):36s} "
                  f"contract={bridge.contract:16s} "
                  f"hardness={bridge.deck_hardness:10s} "
                  f"crest={bridge.deck_top_y_m:7.2f} "
                  f"ends=({bridge.deck_end_elevations_y_m[0]:.2f}, "
                  f"{bridge.deck_end_elevations_y_m[1]:.2f}) "
                  f"len={bridge.deck_length_m:.0f}m")
        for refusal in result.refusals:
            print(f"    REFUSED {short(refusal.object_resources):36s} "
                  f"{refusal.reason[:64]}")
