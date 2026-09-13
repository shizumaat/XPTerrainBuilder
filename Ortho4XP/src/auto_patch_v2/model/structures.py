"""STRUCTURE records (M4, plan §1 row 5 "structure constraints") — the
tunnel corridors, road bridge decks and basins the planar map carries
beside its faces, so the constraint generator and the verifier read ONE
record instead of re-deriving the corridor from face rings.

Data only (no shapely, no numpy — ``test_model.py`` enforces it).  Every
coordinate is in the airport frame; every ``s`` is metres along the
ramp axis measured from the mouth (``s = 0`` at the mouth line, growing
OUTWARD, away from the bore).  Values (crest = DEM, mouth datum) are
recorded here exactly as the planar builder sampled them; the generator
turns them into rows and never invents another.

THE MODEL (RULINGS 2026-08-30 canonical mouth; 2026-09-01c/e; 2026-09-03b):
ONE ramp descending the corridor to the mouth line, a ``wall_gap_m``
unowned gap, ONE wall band per side whose crest is the DEM, ONE end cap
across the mouth; the bore under cover is NOT emitted (the covering
surface keeps its own law).  A road bridge deck (2026-08-30c/d/f) severs
the ramp: the stretch under the deck is covered, the cut stays at bore
datum from the mouth to the deck and the climb begins beyond it.
"""
from __future__ import annotations

import dataclasses as _dc

from .frame import XY

__all__ = ["Deck", "Tunnel", "Basin", "profile_z"]


def profile_z(profile: "tuple[tuple[float, float], ...]", s: float) -> float:
    """A sunken road's floor at ``s`` along its axis: linear between the
    profile's stations ``(s, z)``, the end values beyond them (RULINGS
    2026-09-08b/c Law B: the floor is the plate's own y per station)."""
    if s <= profile[0][0]:
        return float(profile[0][1])
    if s >= profile[-1][0]:
        return float(profile[-1][1])
    for (sa, za), (sb, zb) in zip(profile[:-1], profile[1:]):
        if sa <= s <= sb:
            f = (s - sa) / ((sb - sa) or 1.0)
            return float(za + (zb - za) * f)
    return float(profile[-1][1])


@_dc.dataclass(frozen=True)
class Deck:
    """A road bridge deck across a ramp (RULINGS 2026-08-30c/d/f/m).
    ``s0 < s1`` is the covered stretch along the ramp axis; ``ring`` the
    deck face's outline; ``datum`` names the level the deck sits at
    (``"dem"`` = terrain deck at road level — the only kind M4 emits,
    a hard-deck object deck being ``"deck_top"``)."""

    ref: str
    way: int
    s0: float
    s1: float
    ring: tuple[XY, ...]
    datum: str = "dem"
    z: float | None = None
    #: spec §33 (4) (owner RULINGS 2026-09-13d item 9): A TERRAIN DECK IS
    #: TIED TO ITS ENDS.  The ground at the mapped way's two ends — the
    #: apron on one side, the road on the other — and the governed cell
    #: standing there (``""`` = bare ground, the DEM).  The deck's datum
    #: is the higher of (trench floor + ``bridge.clearance_m``) and these;
    #: the ramp beneath yields downward.  Empty for an object deck, whose
    #: authored top IS its datum.
    end_z: tuple[float, ...] = ()
    end_ref: tuple[str, ...] = ()
    end_xy: tuple[XY, ...] = ()


@_dc.dataclass(frozen=True)
class Tunnel:
    """One emitted tunnel structure.

    ``axis`` runs from the mouth outward (``axis[0]`` = the mouth line's
    centre); ``half_width_m`` the ramp's half width; ``mouth_dem_z`` the
    DEM at the mouth and ``mouth_z`` the ramp's mouth datum
    (``mouth_dem_z - tunnel.bore_datum_m``); ``top_s`` where the ramp
    reaches the DEM; ``climb_from_s`` where the climb starts (0, or the
    far edge of the last deck + the gap); ``ramp_refs`` / ``wall_ref`` /
    ``deck_refs`` the face refs the planar map carries for it;
    ``wall_path`` the wall band's centreline as a U (left band from the
    top to the mouth, across the cap, right band back to the top) — the
    crest is the DEM along it (2026-09-03b L1); ``ways`` the OSM bore
    way ids (both carriageways of a dual, 2026-08-31h)."""

    id: str
    ways: tuple[int, ...]
    axis: tuple[XY, ...]
    half_width_m: float
    mouth_dem_z: float
    mouth_z: float
    top_s: float
    climb_from_s: float
    ramp_refs: tuple[str, ...]
    wall_ref: str
    wall_path: tuple[XY, ...]
    decks: tuple[Deck, ...] = ()
    notes: tuple[str, ...] = ()
    #: The top edge reaches the DEM (pinned there); False when a building
    #: pad clipped the ramp short (08-07 ruling 3): the ramp climbs as far
    #: as the pad edge and the pad's face is the portal.
    top_pinned: bool = True
    clipped_by: str = ""
    #: The two end-cap corner points on the band's centreline (left,
    #: right): the mouth datum is their crest's mean minus ``bore_datum_m``.
    cap_corners: tuple[XY, XY] | None = None
    #: The end cap's centre point on the band's centreline: the MOUTH WALL
    #: NODE of 2026-09-03b — the mouth datum is its crest − bore_datum_m.
    cap_centre: XY | None = None
    # ── TUNNEL WALL OBJECTS (RULINGS 2026-09-05k-1; ``[tunnel.object]``) ──
    #: ``"osm"`` (a mapped bore) or ``"object"`` (the pack's wall object:
    #: seat = floor, plate = crest, hull = footprint).
    source: str = "osm"
    #: The crest law this tunnel's wall band carries: ``"dem"`` (09-03b,
    #: OSM bores) or ``"plate"`` (``crest_z`` = floor + the plate height).
    crest: str = "dem"
    crest_z: float | None = None
    #: The object corridor's reading: the resource, its placement ids,
    #: the plate height (= depth), the hull's sides, the ends
    #: (``"closed/open"`` from s = 0 outward) and the OSM bore way ids
    #: it replaced.
    resource: str = ""
    objects: tuple[str, ...] = ()
    depth_m: float = 0.0
    #: The crest plate's height above the seat — the SEAT datum (05n-4:
    #: crest flush at grade); equals ``depth_m`` for a full wall, the
    #: low crest for an EDGE WALL whose depth is the bore law's
    #: (RULINGS 2026-09-06c (2), ``edge_wall``).
    plate_y_m: float = 0.0
    edge_wall: bool = False
    hull_length_m: float = 0.0
    hull_width_m: float = 0.0
    ends: str = ""
    replaced_ways: tuple[int, ...] = ()
    #: The band closes across s = 0 (``capped``) and across the far end
    #: (``far_capped``, a corridor closed at both ends); an open+open
    #: corridor is two capless halves meeting at its midpoint.
    capped: bool = True
    far_capped: bool = False
    # ── ROUND 2 (RULINGS 2026-09-05n; ``plate_datum = "ground"``) ──
    #: The ramp's DESIGN grade: ``min(ramp_max_grade, depth / wall
    #: length)`` for an object corridor (the ramp reaches the ground at
    #: the wall end), ``ramp_max_grade`` for an OSM bore — what
    #: ``ramp_targets`` aims the ramp at.
    design_grade: float = 0.0
    #: The wall length along the axis (the trench inside the walls ends
    #: there; ``top_s − wall_length_m`` is the ramp beyond the walls).
    wall_length_m: float = 0.0
    #: How the mouth was chosen (``"bore"`` / ``"family"`` / ``"closed"``),
    #: and what the far end is (``"open"`` / ``"closed"`` / ``"bore"`` —
    #: a second mouth: the trench is flat at the floor).
    mouth_kind: str = ""
    ground_kind: str = ""
    #: The re-seat the design implies per placement, ``ground − (floor at
    #: the anchor's station + agl + plate)`` (the post-mesh seat measures
    #: the real one); the largest distance any trench vertex stands
    #: OUTSIDE the walls' inner faces (the 05n-2 assertion, expect 0).
    reseat_expect_m: tuple[float, ...] = ()
    trench_outside_max_m: float = 0.0
    #: THE OBJECT'S FOOTPRINT (RULINGS 2026-09-08d c): the walls' plan
    #: union (their OUTER faces) as a ring in frame xy — the plate seat's
    #: stations stand outside it by the identity spacing, whichever side
    #: of the outer face the trench rim is on; empty for an OSM bore.
    footprint: tuple[XY, ...] = ()
    # ── THE RAMP LAWS (RULINGS 2026-09-08b/c; spec othh-terminal-ramps-spec.md) ──
    #: ``source`` is ``"door"`` (Law A: the well is the "walls" —
    #: ``wall_length_m`` its reach ⊕ overlaps, ``mouth_z`` the SILL,
    #: ``hull_width_m`` the sill width, the climb beyond at
    #: ``design_grade`` = ``cutout.door.ramp_grade``) or ``"sunken_road"``
    #: (Law B: ``profile`` the plate's own floor per station ``(s, z)`` from
    #: the deep-end cut, pinned by the generator; ``mouth_z`` the floor at
    #: the cut).  Both: ``seat = "none"`` — never plate-seated.
    profile: tuple[tuple[float, float], ...] = ()
    #: A door ramp's ground at the top station and the climb's reach
    #: (``top_s − wall_length_m``: the "small ramp" the owner asked for).
    top_ground_z: float | None = None


@_dc.dataclass(frozen=True)
class Basin:
    """A below-grade FACILITY derived from the pack's own objects
    (RULINGS 2026-08-26; 2026-09-06b (1)/(3); ``structures.toml [basin]``,
    ``[cutout]``; M4b): the floor face(s) at ``floor_z`` (role
    ``tunnel_trench``, ref ``floor_ref`` / ``floor_ref#j``) — the
    members' floor plates ⊕ ``floor_overlap_m`` — and ONE void face
    (role ``retaining_wall``, ref ``wall_ref``; never a surface) whose
    exterior is the at-grade RIM (inside the shells' footprint by
    ``rim_inset_fraction`` × their thickness, 09-08a;
    the DEM where bare, the governed ground's value where shared — the
    rim LEVEL with the apron, 2026-08-28c item 3).

    ``ring`` is the largest floor face's outline; ``wall_path`` the rim
    ring (ground by station along it); ``region`` the admitted region
    (the shells' footprint below the ground, before the rim gap);
    ``rim_estimate_m`` is ``R_est`` (the median DEM around the region,
    ``rim_sample_step_m`` apart); ``solid_min_z`` the RENDERED elevation
    of the facility's deepest genuine solid (``DEM(anchor) + agl + y``,
    thickness-gated) — the floor itself (``floor_z == solid_min_z``) —
    and ``solid_min_y_m`` the same relative to ``R_est`` (the sidecar's
    ``solid_minimum_y_m``); ``covered_fraction`` the cover reading (the
    pack's own geometry above the contact band over the region —
    reported, never a refusal: 04i); ``anchor_ll`` a representative
    point inside the region.

    THE SEAT (2026-09-06b (3); scoped by RULINGS 2026-09-09ac (2)):
    ``member_ids`` the placements OF the region — every object with a
    witness footprint in it — and ``witness_id`` the one whose own floor
    plate the basin CUT (the deepest genuine solid).  The plate seat is
    the WITNESS's alone: ``plate_y_m`` is its plate y relative to its
    rendered y = 0 plane, ``anchor_inside_floor`` whether ITS anchor
    lies on the floor (it renders ON the trench floor after the mesh),
    and ``seat_expect_m`` the delta the design implies for it (``floor −
    (mesh(anchor) + agl + plate_y)``, the mesh at the anchor predicted
    as the floor inside, the DEM outside) — the post-mesh seat measures
    the real one.  Another member whose plate merely SHARES that
    ``plate_y_m`` is not plate-seated: it seats by its feet like any
    other resource (measured at LEMD: 12 terminal slabs stood 12–17 m
    off their own feet by the family-wide seat)."""

    id: str
    objects: tuple[str, ...]
    floor_z: float
    floor_ref: str
    wall_ref: str
    ring: tuple[XY, ...]
    wall_path: tuple[XY, ...] = ()
    rim_estimate_m: float = 0.0
    solid_min_z: float = 0.0
    solid_min_y_m: float = 0.0
    covered_fraction: float = 0.0
    area_m2: float = 0.0
    anchor_ll: tuple[float, float] = (0.0, 0.0)
    notes: tuple[str, ...] = ()
    #: 04i: the deep floor plates' area inside the ring (the floor
    #: evidence) and the kind — ``"pit"`` (open) or ``"covered pit"``
    #: (cover above the contact band over it; the cover is the object).
    floor_plate_m2: float = 0.0
    kind: str = "pit"
    region: tuple[XY, ...] = ()
    member_ids: tuple[str, ...] = ()
    plate_y_m: float = 0.0
    #: 09ac (2): the deepest member — the basin's own witness resource
    witness_id: str = ""
    anchor_inside_floor: bool = False
    seat_expect_m: float = 0.0
    agl_m: float = 0.0

    def floor_below_rim_m(self, clearance_m: float = 0.0) -> float:
        """THE ONE DERIVATION of how far the trench floor stands under its
        rim (owner RULINGS 2026-09-10ba, 2026-09-11t; spec §22.1c, §24 (2)).

        ``body_depth`` is the facility's own deepest genuine solid under
        ``R_est`` (``-solid_min_y_m``); a record from before that instrument
        (or a fixture stating only floor and R_est) falls back to the
        declared floor under the rim estimate — the same number the long
        way.  ``clearance_m`` (``[basin] floor_clearance_m``) is what the
        terrain drops BELOW the object's floor plate so the plate renders.

        ``constraints/structures.basins`` states the row with it and
        ``pipeline/publication.basin_facilities`` publishes it as
        ``floor_below_rim_m``; the census joins the two.  Two copies of this
        arithmetic is how a published depth and a stated row drift apart —
        there is one, here.  ``0.0`` when the basin evidences no depth at
        all (the caller keeps the absolute pin)."""
        depth = -float(self.solid_min_y_m)
        if depth <= 1e-6:
            depth = float(self.rim_estimate_m) - float(self.floor_z)
        return 0.0 if depth <= 1e-6 else depth + float(clearance_m)
