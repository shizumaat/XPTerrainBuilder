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

__all__ = ["Deck", "Tunnel", "Basin", "Channel", "ChannelWall",
           "profile_z", "deck_z_on_faces", "CHANNEL_FLOOR_ROLE",
           "CHANNEL_WALL_ROLE", "CREST_DESIGN", "CREST_DEM"]

#: §45 (8) EMISSION: the channel's floor faces carry ``tunnel_trench``
#: (already an ``emit/graded.FLOOR_ROLES`` member) and its banks the VOID
#: role ``retaining_wall`` — the same two the tunnel and the basin use, so
#: every downstream reader (``rim_runs``, the rim breaklines, the DSF
#: adapter) follows with no edit.  No new role is minted (§45 C15
#: "prefer none").
CHANNEL_FLOOR_ROLE = "tunnel_trench"
CHANNEL_WALL_ROLE = "retaining_wall"
#: §45 (5): the two crest laws.  ``"dem"`` is the BORE's (RULINGS
#: 2026-09-03b, unchanged anywhere); ``"design"`` is the CHANNEL's — the
#: solved surface of the governed cell at the corridor edge.
CREST_DEM = "dem"
CREST_DESIGN = "design"


#: A point this far outside a corridor ring (METRES, the planar frame's
#: default) still reads as under it — ``emit.weld_spacing_m``'s own
#: identity spacing.  A ramp floor face's
#: OWN ring vertices sit exactly on the outline, and the identity grid
#: moves them by up to half a grid step: judged by bare ray casting they
#: would fall arbitrarily one side or the other and take the basin's one
#: depth instead of the deck — a cliff along the ramp's own edge.
_RING_TOL_M = 1.0


def deck_z_on_faces(faces, rings, x: float, y: float,
                    ring_tol: float = _RING_TOL_M) -> "float | None":
    """THE ONE READING of a basin ramp corridor's authored deck elevation
    over a plan point (spec §24 (5), owner RULINGS 2026-09-13g).

    ``faces`` are ``((x, y, z), (x, y, z), (x, y, z))`` deck triangles and
    ``rings`` the corridors' plan outlines, in ONE coordinate system (the
    airport frame in the planar map, longitude/latitude in the published
    sidecar — barycentric weights are affine-invariant, so the same call
    answers in both).  The triangle covering the point is interpolated at
    it; a point inside a corridor ring but off every triangle (the identity
    grid moved a floor vertex off the deck's edge) takes the nearest face's
    plane; a point under no ramp returns ``None`` and the basin's one depth
    stands.

    ``constraints/structures.basins`` states the floor row with this and
    ``verify/structures.basin_floor_at_declaration`` judges the emitted
    floor with it: two copies of this arithmetic is how a stated row and a
    published expectation drift apart, so there is one, here."""
    if not faces:
        return None
    top = None                                    # the highest covering face
    best = None                                   # (distance2, z) off every face
    for tri in faces:
        (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = tri
        d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(d) < 1e-15:
            continue
        a = ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) / d
        b = ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) / d
        c = 1.0 - a - b
        if a >= -1e-9 and b >= -1e-9 and c >= -1e-9:
            # THE DECK IS THE TOP of what covers the point: the corridor's
            # faces are read with |n_y| (the codebase's near-horizontal
            # test), so a slab's SOFFIT is in the set beside its deck and
            # the lower of the two must never be the one answered with.
            z = a * z0 + b * z1 + c * z2
            top = z if top is None else max(top, z)
            continue
        cx, cy = (x0 + x1 + x2) / 3.0, (y0 + y1 + y2) / 3.0
        d2 = (cx - x) ** 2 + (cy - y) ** 2
        if best is None or d2 < best[0]:
            best = (d2, (z0 + z1 + z2) / 3.0)
    if top is not None:
        return top
    if best is None or not _in_any_ring(rings, x, y, ring_tol):
        return None
    return best[1]


def _in_any_ring(rings, x: float, y: float, tol: float = 1.0) -> bool:
    """Point in (or within ``tol`` of) any of the plan rings — ray casting,
    no shapely (this module is data only).  ``tol`` is in the rings' OWN
    units: metres in the planar frame, DEGREES against the published
    lon/lat corridor (``verify`` passes the conversion)."""
    for ring in rings or ():
        n = len(ring)
        if n < 3:
            continue
        inside = False
        for i in range(n):
            ax, ay = ring[i][0], ring[i][1]
            bx, by = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
            if (ay > y) != (by > y):
                t = (y - ay) / (by - ay)
                if x < ax + t * (bx - ax):
                    inside = not inside
            if not inside and _seg_dist2(ax, ay, bx, by, x, y) <= tol * tol:
                return True
        if inside:
            return True
    return False


def _seg_dist2(ax: float, ay: float, bx: float, by: float,
               x: float, y: float) -> float:
    dx, dy = bx - ax, by - ay
    d2 = dx * dx + dy * dy
    t = 0.0 if d2 <= 0.0 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / d2))
    ex, ey = ax + t * dx - x, ay + t * dy - y
    return ex * ex + ey * ey


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


#: THE UNDERPASS MARK (spec §34 (5) as amended; RULINGS 2026-09-13ai).
#: The prefix of the ``Tunnel.notes`` line the planar stage writes when an
#: ``aeroway`` ``bridge=yes`` way STATED the crossing, naming that way.
#: The constraint generator reads it to put the portal rim on the DECK
#: cell's own solved surface instead of ``DEM(mouth)``, which is the road
#: down in the cutting.  It lives on the RECORD because both layers read
#: it and ``constraints`` may not import ``planar``.
UNDERPASS_NOTE = "underpass under aeroway "


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
    #: §34 (9) THE PINCHED RAMP (owner RULINGS 2026-09-14ak/14am;
    #: ``planar/wall_corridor_ramps.stop_and_steepen``): ``(road ref, span
    #: m, grade)`` when this corridor's climb ENDED at an airside-locked
    #: service road's edge and its cap was LIFTED for that run, else
    #: ``None``.  THE RECORD, never re-derived: the lifted-cap publication
    #: (``pipeline/publication.lifted_caps``) reads THIS, so the judged cap
    #: and the built one are one law (RULINGS 2026-09-12m's class — "a
    #: build steeper than the judged cap mints a violation by
    #: construction").
    pinched: tuple[str, float, float] | None = None


@_dc.dataclass(frozen=True)
class ChannelWall:
    """One SIDE of an open channel (spec §45 (2)/(5)).

    ``shape`` is how the bank between crest and floor is made:
    ``"face"`` — a pack wall face stands here and the bank hides behind
    it at the identity spacing (near-vertical at the face); ``"lidar"`` —
    a credible lidar inset states the bank and it is KEPT (clamped
    monotone crest → floor); ``"bank"`` — neither, so ``[channel]
    bank_slope`` (1:2) runs from crest to floor.  ``crest`` names the
    crest REFERENCE, always :data:`CREST_DESIGN` for a channel: the
    solved surface of the governed cell at the corridor edge, never
    ``DEM(x, y)``.  ``path`` is the crest line in the airport frame and
    ``toe`` the floor-edge line beneath it, station for station."""

    side: str                       # "left" | "right" (the axis's own sense)
    shape: str                      # "face" | "lidar" | "bank"
    crest: str = CREST_DESIGN
    path: tuple[XY, ...] = ()
    toe: tuple[XY, ...] = ()
    witness: str = ""               # the pack resource / inset that stated it


@_dc.dataclass(frozen=True)
class Channel:
    """THE OPEN CHANNEL (spec §45; owner RULINGS 2026-09-15i) — a road /
    rail corridor under a STATED CROSSING that keeps its own floor
    through the field.

    Data only, like every record here: ``planar/channel.py`` derives it
    once and ``constraints/channel.py`` + ``verify/channel.py`` READ it.
    Neither re-derives the corridor (the defect class this module's
    docstring names).

    ``ways`` the OSM road/rail way ids sharing the corridor (both
    carriageways, the frontage roads, the rail) within ``[channel]
    merge_m``; ``axis`` the merged centreline through the field, ``s``
    growing from the field ENTRY (unlike a ``Tunnel``, whose ``s`` grows
    outward from a mouth — a channel has no mouth, §45 (6));
    ``profile`` the FLOOR as ``(s, z)`` stations and ``widths`` the
    half-width as ``(s, half)``; ``decks`` the crossings (``Deck``
    records with ``datum = "design"``, §45 (4): the neck's faces keep
    their airside role and law); ``walls`` one :class:`ChannelWall` per
    side; ``ends`` the two stations where the corridor leaves the
    airside pavement union ⊕ ``mouth_standoff_m`` (beyond them §37
    governs and the floor rejoins the road's own profile at
    ≤ ``ramp_max_grade``); ``witnesses`` each identification witness by
    NAME (§45 (1): "Each witness is recorded on the record by name");
    ``datum_source`` which of §45 (3)'s three the floor came from —
    ``"pack"`` (i), ``"lidar"`` (ii) or ``"clearance"`` (iii) — so a
    ``--refresh-data dem`` moving a site from (iii) to (ii) is visible in
    the report with no law change."""

    id: str
    ways: tuple[int, ...]
    axis: tuple[XY, ...]
    profile: tuple[tuple[float, float], ...]
    widths: tuple[tuple[float, float], ...] = ()
    decks: tuple[Deck, ...] = ()
    walls: tuple[ChannelWall, ...] = ()
    ends: tuple[float, float] = (0.0, 0.0)
    witnesses: tuple[str, ...] = ()
    datum_source: str = ""
    #: THE MEMBER WAYS AS ``(feed, id)`` KEYS — what every cross-pass
    #: join uses (``planar/channel_claims.way_key``).  ``ways`` above is
    #: the same ways' plain ids, for the citations and the sidecar; it is
    #: NOT an identity, because the feeds' negative ids collide (owner
    #: addendum 2026-09-15: 8 of 11 LEMD deck ids carry two ways).
    way_keys: tuple[tuple[str, int], ...] = ()
    #: §45 (10)/(11): the corridor's CREST estimate (the DEM's own mean
    #: along the axis) and the pack placements that witnessed it (1) (c).
    #: The crest estimate is what ``object_min_depth_m`` is measured
    #: against when a pass asks whether an object is the channel's own —
    #: a pit BESIDE the corridor keeps its basin (§45 (11)).
    crest_estimate_m: float = 0.0
    witness_ids: tuple[str, ...] = ()
    #: How the width was reached: ``"pack walls (10) (i)"``, ``"lidar
    #: bank toes (10) (ii)"`` or ``"carriageways ⊕ lane_width_m (10)
    #: (iii)"`` — the hole states the CROSSING, never the width.
    width_source: str = ""
    crest: str = CREST_DESIGN
    bank_slope: float = 0.5
    #: §45 (17) THE CHANNEL'S OWN WALL BAND (owner RULINGS 2026-09-15bo):
    #: the plan width of the band between the floor ring and the crest
    #: ring — the bank of (5), never thinner than a bore's ``[tunnel]
    #: wall_gap_m + wall_band_width_m``.  The floor stands this far back
    #: from every airside or adjacent-ground cell AND from every DECK, so
    #: a floor face never shares a vertex with a pavement cell.
    wall_band_m: float = 0.0
    #: The emitted faces' refs (``planar/channel.py`` writes the cells):
    #: the floor ``channel_floor:<k>`` and the void ``channel_wall:<k>``.
    floor_ref: str = ""
    wall_ref: str = ""
    #: The corridor's plan ring (the floor's outline BEFORE the decks are
    #: subtracted) and the crest ring (the corridor ⊕ the banks), in the
    #: frame — what the flat-site region subtracts (§45 (8), C13) and
    #: what the object gates read as "inside an identified corridor"
    #: (§45 (7), C5/C6/C7).
    region: tuple[XY, ...] = ()
    crest_ring: tuple[XY, ...] = ()
    #: The same two in LONGITUDE / LATITUDE — what the SIDECAR publishes,
    #: for the same reason ``Basin.ramp_rings_ll`` exists: the patch's
    #: metres are not the planar frame's, so the published corridor is
    #: carried in the one coordinate system both sides agree on.
    region_ll: tuple[tuple[float, float], ...] = ()
    profile_ll: tuple[tuple[float, float, float], ...] = ()
    notes: tuple[str, ...] = ()

    def floor_z(self, s: float) -> float:
        """The floor at ``s`` along the axis — :func:`profile_z`, the ONE
        reading both the generator's row and the verifier's expectation
        are stated with."""
        return profile_z(self.profile, s)

    def half_width(self, s: float) -> float:
        """The corridor's half-width at ``s`` (§45 (2)); the end values
        beyond the stated stations, exactly as :func:`profile_z`."""
        if not self.widths:
            return 0.0
        return profile_z(self.widths, s)


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
    #: THE RAMP CORRIDORS (spec §24 (5), owner RULINGS 2026-09-13g): the
    #: basin resource's own DECK geometry climbing from the floor plate to
    #: the rim — one plan ring per corridor (``ramp_rings``) and the deck
    #: faces themselves as ``((x, y, z), (x, y, z), (x, y, z))`` triangles
    #: in the frame (``ramp_faces``).  The floor UNDER a corridor follows
    #: the deck per station (:meth:`deck_z_at`) instead of taking the one
    #: depth: a modelled road ramp is only visible if the terrain under it
    #: climbs with it.  Empty for a basin with no ramp — every OTHH pit.
    ramp_rings: tuple[tuple[XY, ...], ...] = ()
    ramp_faces: tuple[tuple[tuple[float, float, float], ...], ...] = ()
    #: The same two in LONGITUDE / LATITUDE — what the SIDECAR publishes.
    #: The patch's own metres are not the planar frame's (``verify`` builds
    #: its ``xy`` from the sidecar's own origin: measured at LEMD, the T4S
    #: ramp published at frame (−799, 2227) while the floor vertices over
    #: it read (−148, 889)), so the published corridor is carried in the
    #: one coordinate system both sides agree on.
    ramp_rings_ll: tuple[tuple[tuple[float, float], ...], ...] = ()
    ramp_faces_ll: tuple[tuple[tuple[float, float, float], ...], ...] = ()

    def deck_z_at(self, x: float, y: float) -> float | None:
        """This basin's ramp deck elevation over ``(x, y)``, or ``None``
        where no ramp stands (:func:`deck_z_on_faces`, the ONE reading —
        ``constraints/structures.basins`` states the floor row with it and
        ``verify/structures`` judges the emitted floor against the same
        call on the published faces)."""
        return deck_z_on_faces(self.ramp_faces, self.ramp_rings, x, y)

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
