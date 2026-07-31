"""What do the OTHH bridges classify AS, now that Bridge_04 is no longer
a tunnel?  W1b (the deck-flush partition) is only meaningful for a
structure that reaches the partition at all, so name the record first.

Prints every bridge record and every refusal, with the fields the
partition reads.

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
AIRPORTS = [
    ("OTHH", os.path.join(XP, "Custom Scenery", "OTHH Doha (Aeroscape)",
                          "Earth nav data", "+20+050", "+25+051.dsf")),
    ("EGLL", os.path.join(XP, "Custom Scenery",
                          "c_GBR - 100_airport - EGLL_LONDON_TAIMODELS",
                          "Earth nav data", "+50-010", "+51-001.dsf")),
]


def short(resources):
    names = sorted(os.path.basename(r) for r in resources)
    return names[0][:38] if names else "(none)"


for icao, dsf_path in AIRPORTS:
    if not os.path.exists(dsf_path):
        print(f"{icao}: DSF missing")
        continue
    lines = dsf_reader._load_dsf_text(dsf_path)
    every = obj8_reader.read_dsf_object_placements(
        lines, accept_resource=lambda r: r.lower().endswith(".obj"),
        include_object_msl=True)
    terrain = [p for p in every if p.placement_kind != "OBJECT_MSL"]
    msl = [p for p in every if p.placement_kind == "OBJECT_MSL"]
    pack_root = dsf_reader._pack_root_for_dsf(dsf_path)
    geometry = _load_object_geometry_by_resource(terrain, pack_root, XP)
    result = otf.classify_object_terrain_features(
        terrain, geometry, mean_sea_level_placements=msl,
        pack_root=pack_root or "")

    print(f"\n{'=' * 100}\n{icao}\n{'=' * 100}")
    print(f"BRIDGES ({len(result.bridges)}):")
    for bridge in result.bridges:
        ends = getattr(bridge, "deck_end_elevations_y_m", None)
        print(f"  {short(bridge.object_resources):40s} "
              f"contract={getattr(bridge, 'terrain_contract', '?')} "
              f"carry={getattr(bridge, 'deck_carry_class', '?')} "
              f"crest={getattr(bridge, 'deck_crest_y_m', float('nan')):.2f} "
              f"ends={ends}")
    print(f"REFUSALS ({len(result.refusals)}):")
    for refusal in result.refusals:
        print(f"  {short(refusal.object_resources):40s} "
              f"reason={refusal.reason}")
    print(f"TUNNELS ({len(result.tunnels)}): "
          f"{sorted(short(t.object_resources) for t in result.tunnels)}")
    interfaces = [
        i for i in result.ground_interfaces
        if any("Bridge" in os.path.basename(r) for r in i.object_resources)
    ]
    print(f"BRIDGE-NAMED GROUND INTERFACES ({len(interfaces)}):")
    for interface in interfaces:
        print(f"  {short(interface.object_resources):40s} "
              f"class={interface.interface_class}")
