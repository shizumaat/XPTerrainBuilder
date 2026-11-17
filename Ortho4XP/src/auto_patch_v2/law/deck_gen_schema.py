"""``structures.toml [deck_gen]`` / ``[road_gen]`` -- THE GENERATED TAXIWAY
DECK AND THE GENERATED ROAD BRIDGE (spec ``docs/specs/2123.md`` A1-A2 /
B1-B2; owner RULINGS 2026-11-16y; issues #2123, #2124).

The numbers ``planar/deck_generated`` (where a deck is generated, its
ring, its tilt and its floor), ``planar/road_bridge_gen`` (where a road
bridge is generated) and ``airport/generated_pack`` (the object, the
paint, the road chain) read.  Defaulted so a law dir without the tables
still loads -- the ``[walled_plate]`` precedent.
"""
from __future__ import annotations

import dataclasses as _dc

__all__ = ["DeckGenLaw", "RoadGenLaw"]


@_dc.dataclass(frozen=True)
class DeckGenLaw:
    """``[deck_gen]`` (spec 2123 A1-A2; Q2/Q3/Q6 as ruled 16y)."""

    #: A1 (3) / Q2: a road covered longer than this is a tunnel (m),
    #: measured on the ROAD's covered length, never the deck's
    max_cover_m: float = 100.0
    #: A2: the cut C grows by this before the pavement is read (m)
    bearing_m: float = 2.0
    #: A2 / Q3: the deck ring stands this far outside the pavement (m)
    edge_margin_m: float = 1.5
    #: A2: the bank each side of a road's carriageway inside C (m), 30b
    bank_m: float = 3.0
    #: A2: the slab's thickness (m)
    thickness_m: float = 1.0
    #: A2: the top stands this far over the solved end lines (m)
    top_lift_m: float = 0.02
    #: A2: the pre-solve tilt is clamped to this share of the family cap
    tilt_cap_share: float = 0.8
    #: A2: the DEM read for the tilt stands this far outside each end line (m)
    tilt_probe_m: float = 6.0
    #: A2: ... out to this far: the ground beside the road's cut is the
    #: highest DEM there (a bare-earth DEM reads the cut under the bridge)
    level_probe_m: float = 30.0
    #: a deck piece smaller than this is not generated (m2)
    min_area_m2: float = 50.0
    #: A2: the generated object's draw distance (m)
    lod_m: float = 6000.0
    #: A2: a centreline light every this many metres on the deck (m), Q4
    light_spacing_m: float = 15.0


@_dc.dataclass(frozen=True)
class RoadGenLaw:
    """``[road_gen]`` (spec 2123 B1-B2; Q5 spans only)."""

    #: B1 (b): a pack page or apt.dat 110 covers at least this share of
    #: the bridge's carriageway
    page_cover_frac: float = 0.5
    #: B1 (c): a road-pack segment this close (m) ...
    pack_road_near_m: float = 5.0
    #: ... and this parallel (deg) already draws the bridge
    pack_road_angle_deg: float = 15.0
    #: B3: the span's page clip is the carriageway half width plus this (m)
    span_margin_m: float = 0.5
    #: B2: the road network definition written when the pack has none
    net_def: str = "lib/g10/roads.net"
    #: B2: the subtype (``#VROAD``) of a generated bridge (P0: SHOW_LEVEL 2
    #: on simHeaven's roads_EU override; the owner saw it draw)
    subtype: int = 50
    #: B2: the level-1 junctions stand this far inside each crest (m)
    level1_inset_m: float = 12.0
    #: B3 / owner 16y (3): the ends stand on their embankments: the
    #: span's ground is never cut within this of its abutment (m)
    abutment_keep_m: float = 25.0
