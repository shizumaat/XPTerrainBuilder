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
    #: #2131 THE DECK SPANS ITS CUT: the level floor each side of a
    #: covered road's carriageway -- the drawn road's shoulders -- under
    #: the deck and along its ramps (m); the bank's run (the slab plus the
    #: clearance over ``emit.design.bank_slope``) stands beyond it, under
    #: the deck
    shoulder_m: float = 1.5
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
    #: #2132: the X-Plane pavement page whose art (TEXTURE, TEXTURE_NORMAL,
    #: SCALE) draws the slab, linked from the user's install
    #: (``airport/deck_skin``); unresolved -> the generated atlas
    concrete_pol: str = "lib/airport/pavement/concrete_4D.pol"
    #: #2132: the page whose alpha art is the tire marks along the route
    rubber_pol: str = "lib/airport/default_runways/rubber.pol"
    #: #2132 / #2141: the tire marks are ONE column of that page's atlas
    #: (u from ``rubber_u0`` to ``rubber_u1``: the dense centre band; the
    #: other three columns read as tiled blocks), a strip along the route
    #: mirrored every repeat
    rubber_u0: float = 0.25
    rubber_u1: float = 0.5
    #: #2141 (3): the first X-Plane line page; its folder's
    #: ``<type>_*.lin`` pages draw the dropped apt.dat lines on the deck
    #: (``airport/deck_line_art``); unresolved -> the generated atlas
    line_lib: str = "lib/airport/lines/1_single_taxi.lin"
    #: the films over the top (m): the tire marks, then the paint over them
    rubber_lift_m: float = 0.005
    paint_lift_m: float = 0.012
    #: #2132 THE STRUCTURE (spec 2132-design section 4; owner 2026-11-17
    #: "kerb only (0.30 x 0.40 m, side edges), no blast screen"),
    #: ``airport/deck_structure``: the slab's depth under the top (m) ...
    slab_m: float = 0.25
    #: ... the beams along the route, one every this across it (m) ...
    beam_spacing_m: float = 2.4
    beam_width_m: float = 0.9
    #: ... the full-depth edge beam round the ring (m) ...
    edge_beam_m: float = 0.6
    #: ... the kerb on the side edges (m) ...
    kerb_h_m: float = 0.30
    kerb_w_m: float = 0.40
    #: ... a ring edge whose middle stands within this of an end line (m)
    #: and that turns more than this off the route (deg) is an END: no
    #: kerb, an expansion joint
    end_tol_m: float = 4.0
    end_angle_deg: float = 25.0
    #: ... the expansion joint across each end: a dark strip this wide (m),
    #: this far in from the end edge (m)
    joint_m: float = 0.08
    joint_inset_m: float = 0.3
    #: ... piers only on a deck longer than this along its route (m), at
    #: each road's floor edge: columns this wide (m) at most this far apart
    #: (m), under a cap beam this wide and deep (m), from this far below
    #: the floor (m)
    pier_min_span_m: float = 30.0
    pier_col_m: float = 1.2
    pier_gap_m: float = 4.5
    pier_cap_w_m: float = 1.5
    pier_cap_h_m: float = 1.2
    pier_foot_m: float = 1.0
    #: ... everything drawn to this distance, then the top, the fascia and
    #: the kerbs only, to ``lod_m`` (m)
    near_lod_m: float = 1200.0


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
    #: B3 / owner 16y (3): the pack pavement over the lower road's CUT
    #: beside the span -- where the survey stands this far or more under the
    #: bridge's lower end -- leaves the cells too (m) ...
    cut_drop_m: float = 1.0
    #: ... read within this of the bridge's axis (m)
    cut_reach_m: float = 20.0
