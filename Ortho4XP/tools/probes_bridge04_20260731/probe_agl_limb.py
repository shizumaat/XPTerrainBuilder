"""Measure the AGL tunnel limb's gates on every candidate structure.

W1a landed the whole-structure above-grade cap and killed Bridge_01's wrong
trench.  Bridge_04 survives it: crest +1.91 m is under
``TUNNEL_AGL_MAX_ABOVE_GRADE_HEIGHT_M`` = 2.0 and its below-grade
near-horizontal area clears ``TUNNEL_AGL_MIN_BELOW_GRADE_DECK_AREA_M2`` = 25,
because ``below_grade_mask`` keys on ``TUNNEL_ROOF_TOP_TOLERANCE_M`` = 0.5 —
a shallow tolerance that catches the UNDERSIDE of an at-grade deck.

Before changing any threshold, measure what every candidate ACTUALLY carries.
This instruments ``_agl_tunnel_seed_resources`` (both call sites: the
component seeding inside ``_below_grade_drivable_components`` and the
signature test inside ``_is_tunnel_signature``) and records, per call, the
frame metrics each candidate discriminator would read.

The measurement airports are the two that matter: OTHH (Bridge_01..06, the
owner's case) and EGLL (tunnels 6/7/10, the fixtures any change must not
flip).

Run from Ortho4XP/ cwd:  venv/bin/python tools/probes_bridge04_20260731/probe_agl_limb.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.getcwd(), "src"))
sys.path.insert(0, os.getcwd())

import numpy  # noqa: E402

from auto_patch import dsf_reader, obj8_reader  # noqa: E402
from auto_patch import object_terrain_features as otf  # noqa: E402
from auto_patch.object_terrain_assembly import (  # noqa: E402
    _load_object_geometry_by_resource,
)

XP = "/Users/noah/X-Plane 12"

AIRPORTS = [
    (
        "OTHH",
        os.path.join(XP, "Custom Scenery", "OTHH Doha (Aeroscape)",
                     "Earth nav data", "+20+050", "+25+051.dsf"),
    ),
    (
        "EGLL",
        os.path.join(XP, "Custom Scenery",
                     "c_GBR - 100_airport - EGLL_LONDON_TAIMODELS",
                     "Earth nav data", "+50-010", "+51-001.dsf"),
    ),
]

# Depth ladders reported per frame (metres below effective grade).
DEPTHS = (0.5, 1.0, 2.0)


def _label(resource_paths):
    """Short, stable name for a frame: the commonest basename stem."""
    stems = [os.path.basename(path) for path in resource_paths]
    if not stems:
        return "(empty)"
    head = stems[0]
    for candidate in ("Bridge_", "Tunnel", "Drainage_", "AuxBuilding_"):
        for stem in stems:
            if candidate in stem:
                head = stem
                break
        else:
            continue
        break
    return f"{head[:34]:34s} x{len(stems):<3d}"


def _metrics(frame):
    near_horizontal = (
        frame.triangle_horizontality >= otf.NEAR_HORIZONTAL_NORMAL_Y_MIN
    )
    row = {
        "crest": float(frame.triangle_height_m.max()),
        "floor": float(frame.triangle_height_m.min()),
        # Near-horizontal area AT OR ABOVE the at-grade band: the deck
        # standing on/over grade.  This is the candidate discriminator.
        "at_or_above": float(
            frame.triangle_area_m2[
                near_horizontal
                & (frame.triangle_height_m
                   >= -otf.TUNNEL_ROOF_TOP_TOLERANCE_M)
            ].sum()
        ),
        # Same, but strictly ABOVE grade by the deck-carried height.
        "above_2m": float(
            frame.triangle_area_m2[
                near_horizontal
                & (frame.triangle_height_m
                   >= otf.BRIDGE_DECK_CARRIED_MIN_HEIGHT_M)
            ].sum()
        ),
        "n_res": len(frame.triangle_resource_paths),
    }
    for depth in DEPTHS:
        row[f"below_{depth}"] = float(
            frame.triangle_area_m2[
                near_horizontal & (frame.triangle_height_m <= -depth)
            ].sum()
        )
    return row


def main():
    original = otf._agl_tunnel_seed_resources
    rows = []

    def instrumented(placements, frame):
        seeds = original(placements, frame)
        if frame.triangle_count:
            row = _metrics(frame)
            row["label"] = _label(frame.triangle_resource_paths)
            row["seeds"] = len(seeds)
            row["n_placements"] = len(placements)
            rows.append(row)
        return seeds

    otf._agl_tunnel_seed_resources = instrumented
    try:
        for icao, dsf_path in AIRPORTS:
            if not os.path.exists(dsf_path):
                print(f"{icao}: DSF missing at {dsf_path}")
                continue
            rows.clear()
            lines = dsf_reader._load_dsf_text(dsf_path)
            all_placements = obj8_reader.read_dsf_object_placements(
                lines,
                accept_resource=lambda r: r.lower().endswith(".obj"),
                include_object_msl=True,
            )
            terrain = [
                p for p in all_placements if p.placement_kind != "OBJECT_MSL"
            ]
            msl = [
                p for p in all_placements if p.placement_kind == "OBJECT_MSL"
            ]
            pack_root = dsf_reader._pack_root_for_dsf(dsf_path)
            geometry = _load_object_geometry_by_resource(
                terrain, pack_root, XP
            )
            result = otf.classify_object_terrain_features(
                terrain,
                geometry,
                mean_sea_level_placements=msl,
                pack_root=pack_root or "",
            )
            print(f"\n{'=' * 118}")
            print(f"{icao}: {len(result.tunnels)} tunnels, "
                  f"{len(result.bridges)} bridges, "
                  f"{len(rows)} AGL-limb calls")
            print(f"{'=' * 118}")
            header = (
                f"{'structure':38s} {'plc':>4s} {'crest':>7s} {'floor':>7s} "
                f"{'>=-0.5':>9s} {'>=+2.0':>9s} "
                + " ".join(f"{'<=-' + str(d):>9s}" for d in DEPTHS)
                + f" {'seeds':>6s}"
            )
            print(header)
            seen = set()
            for row in rows:
                key = (row["label"], round(row["crest"], 2),
                       round(row["floor"], 2))
                if key in seen:
                    continue
                seen.add(key)
                # Only frames that could plausibly seed: something below
                # grade and a crest under a few metres, plus anything that
                # actually seeded.
                if row["seeds"] == 0 and row["below_0.5"] < 5.0:
                    continue
                print(
                    f"{row['label']:38s} {row['n_placements']:4d} "
                    f"{row['crest']:7.2f} {row['floor']:7.2f} "
                    f"{row['at_or_above']:9.1f} {row['above_2m']:9.1f} "
                    + " ".join(
                        f"{row[f'below_{d}']:9.1f}" for d in DEPTHS
                    )
                    + f" {row['seeds']:6d}"
                )
            tunnel_names = sorted(
                os.path.basename(r)
                for tunnel in result.tunnels
                for r in list(tunnel.object_resources)[:1]
            )
            print(f"  tunnels: {tunnel_names}")
    finally:
        otf._agl_tunnel_seed_resources = original


if __name__ == "__main__":
    main()
