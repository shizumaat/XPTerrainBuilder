"""STRUCTURE GEOMETRY (M4): tunnel corridors from the OSM bore + approach
ways, road bridge decks, and how they enter the planar map — as CELLS
that CUT the pavement they run through, plus the records
(``model.structures``) the generator and the verifier read.

THE MODEL (RULINGS 2026-08-07 portal fidelity; 2026-08-30 canonical
mouth; 2026-08-31h dual carriageways; 2026-09-01c/e gap; 2026-09-03b
crest = DEM; law ``structures.toml [tunnel]``):

* a BORE is a chain of mapped ``tunnel=yes`` ways; it is generated only
  where a MAPPED END of it stands ON THE FIELD — that end, or the ramp
  reach beyond it, inside the classified cover (with the roofed
  corridors) ⊕ ``mouth_standoff_m`` (spec §29 (1)/(2); owner RULINGS
  2026-09-12r "we should never emit anything for actual tunnels, only
  the tunnel mouths and entrance/exit ramps"; Fable 2026-09-12t; owner
  2026-09-12ab).  A bore with no on-field mouth emits NOTHING however
  much of its length runs under a cell (LEMD's rail bores, 4.0 km out);
  a bore with an on-field mouth is built whether or not it passes under
  an airport surface — a portal on the field is visible on approach —
  and is counted and named where the cover test would have refused it;
* the MOUTH is the mapped end of the bore (08-07 ruling 1: "mapped ends
  are preserved unconditionally" — WHERE IT STANDS ON THE FIELD, §29 (1);
  an end outside the governed region is dropped at ``mouths()`` and
  counted, never built); the bore itself is never emitted —
  the covering surface keeps its own law (08-07 ruling 2: mapped-bore
  interiors are roofed by definition);
* the RAMP descends the approach corridor to the mouth line: its axis
  follows the approach ways outward from the mouth, its width is the
  carriageway's (``width`` tag, else ``lanes × lane_width_m``); two
  bores whose mouths stand within ``dual_carriageway_max_separation_m``
  with parallel approaches are ONE ramp spanning both (31h); the ramp
  ends where a ``ramp_max_grade`` climb from the mouth datum meets the
  DEM (the top edge is DEM);
* the at-grade RIM (RULINGS 2026-09-06b (1); ``[cutout]``): for an OSM
  bore ``wall_gap_m + wall_band_width_m`` off the ramp edge on both
  sides and across the mouth (an END CAP), for an object corridor the
  walls' outer faces ⊖ ``rim_inset_fraction`` × their thickness (09-08a);
  the region between ramp and rim is
  a VOID face (role ``retaining_wall``, never emitted as a surface —
  its exterior IS the rim, emitted as a constrained ring) and the mesh
  makes the wall.  No crest band exists (``emit_wall_band = false``);
* the structure CUTS every pavement it runs through (08-07 ruling 4)
  except the runway family and building pads (``ramp_cuts_runway_family
  = false``, ``ramp_crosses_pad = false``): a ramp that would need to
  cross either before reaching the DEM is REFUSED loudly, never bent;
  a wall inside the runway strip keep-out is refused likewise
  (``retaining_wall.in_runway_strip = false``);
* a mapped ``bridge=*`` way crossing the corridor is a TERRAIN DECK
  (08-30d: no object ⇒ terrain deck at road level): a road face across
  the corridor that severs the ramp and the walls; the cut stays at bore
  datum from the mouth to the deck and the climb begins beyond it
  (08-30f); the deck's ground is road (08-30m);
* a HARD-DECK OBJECT (``ATTR_hard_deck``, read by ``airport/obj8.py``)
  whose footprint crosses the corridor is an OBJECT BRIDGE (M4b; 08-30d
  "where a classified hard-deck OBJECT bridge exists the object law
  governs and the terrain stays open"): the ramp is NOT severed — the
  cut continues under the deck at bore datum and the climb begins
  beyond it (08-30f's depth clause) — and the deck's TOP (memory
  othh-bridge-deck-datum-r12) must clear the ramp by
  ``bridge.clearance_m`` (a bound the generator states, the IIS reports);
  a mapped bridge way over an object deck mints no terrain deck.

* a TUNNEL WALL OBJECT (RULINGS 2026-09-05k-1, round 2 05n; ``airport/
  tunnel_objects``, ``planar/object_corridor``; law ``[tunnel.object]``)
  is the tunnel AUTHORITY where it stands: the trench is the region
  between its walls' inner faces ⊕ ``floor_overlap_m`` following their
  curves, the rim inside its outer faces (2026-09-06b, 09-08a), the
  floor at the mouth = ground − plate height,
  the ramp climbs inside the walls to the ground at the wall end (beyond
  only at ``ramp_max_grade``), the crest = the ground and the object is
  re-seated to it; every OSM bore MOUTH inside its footprint is the
  object's (per mouth: a bore covered at one end keeps its OSM ramp at
  the other), and the corridor enters the SAME ``Tunnel`` product.

Every length here is a law-table value or an input's own tag; the DEM
samples recorded on the records are the builder's, taken once.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..classify.roles import Cell, Classification, is_runway_shoulder
from ..law import Law
from ..law.tables import role_family, role_side, zone2_half_width_m
from ..model.airport import Airport, OsmWay
from ..model.frame import XY
from ..model.structures import Deck, Tunnel
from .basins import object_decks
from .object_corridor import Group, mouth_covered_by, object_groups, trench_outside_m
from .wall_corridor_ramps import (KIND as WALL_KIND, ROAD_ROLES, airside_stops,
                                  locked_road_stops, road_true_edge, stop_and_steepen,
                                  wall_corridor_note, wall_corridor_profile)
from .structure_approach import (FieldRegion, apply_plates,
                                 approach_ground as _approach_ground,
                                 carriageway_width_m,
                                 chains, field_region_for, mouth_reports, under_cover,
                                 is_bridge, is_tunnel, merge_duals, mouths,
                                 pavement_half_widths, ramp_top as _ramp_top, unit)
from .structure_deck import (PavementDeck, deck_intervals, deck_items, emit_decks,
                             object_deck_intervals, pavement_deck_intervals)
from .structure_stats import StructureStats
from .structure_underpass import (underpass_bores as _underpass_bores,
                                  approach_along, UNDERPASS_TAG, UNDERPASS_NOTE)
from .structure_geometry import (beyond_strip, collapse_for_ramp, corner_distance,
                                 covered_start as _covered_start, geometry,
                                 pad_hit as _pad_hit, ramp_targets,
                                 reseat_expect as _reseat_expect)

__all__ = ["StructureStats", "build_structures", "carriageway_width_m"]

_MITRE = dict(join_style="mitre", mitre_limit=2.0)
RUNWAY_FAMILY = ("runway", "runway_crossing")
#: Two OSM node coordinates closer than this (frame metres) are one node.
NODE_TOL = 0.05
#: Approach ways are followed at most this many hops from the mouth.
MAX_HOPS = 6
#: Two directions within 30° are parallel (31h's dual test; the approach kink test).
PARALLEL_COS = math.cos(math.radians(30))


def _dem(airport: Airport, p: XY) -> float:
    return float(airport.dem.z(p[0], p[1]))


def _pad_relief_m(airport: Airport, poly: Polygon) -> float:
    """The DEM relief across a pad's ring (a flat pad is ground; a pad on
    relief is a levelled plane).  ONE implementation, in
    ``airport/skirt.ring_relief_m`` (spec §22 C4)."""
    from ..airport.skirt import ring_relief_m
    return ring_relief_m(lambda x, y: _dem(airport, (x, y)), poly.exterior.coords)


# ── build ────────────────────────────────────────────────────────────────

def build_structures(airport: Airport, classification: Classification, law: Law,
                     objects: _t.Sequence = (), corridors: _t.Sequence = (),
                     extra_groups: _t.Sequence[Group] = (),
                     plates: _t.Sequence = ()
                     ) -> tuple[Classification, tuple[Tunnel, ...], StructureStats]:
    """The classification with the structures applied (cells cut, ramp /
    wall / deck cells added, the gaps as keep-outs), the tunnel records,
    and the stats.  ``objects`` are the pack's placed OBJ8 readings
    (``planar.basins.read_objects``): their hard decks are object
    bridges.  ``corridors`` are the pack's tunnel wall objects read as
    corridors (``airport.tunnel_objects.read_corridors``; RULINGS
    2026-09-05k-1 / 05n): each takes every OSM bore MOUTH standing inside
    its footprint (05n-3, per mouth) and enters the SAME ``Tunnel``
    product — the trench between the inner faces at the ground-
    referenced ramp, the band each wall's footprint at the ground.
    ``extra_groups`` are the door ramps and sunken roads
    (``planar/door_ramps.py``; RULINGS 2026-09-08b/c) as build groups
    through the same machinery.  A classification with no bores, no
    corridors and no groups comes back unchanged."""
    stats = StructureStats()
    odecks = object_decks(objects)
    tn = law.tables.structures.tunnel
    co = law.tables.structures.cutout
    tol_m = law.tables.structures.placement.split_tol_m   # §33 (3)/(4) materiality
    if co.emit_wall_band:
        raise ValueError("cutout.emit_wall_band = true: only false is generated (RULINGS "
                         "2026-09-06b (1): no wall band, the mesh makes the wall)")
    corridors = list(corridors)
    extra_groups = list(extra_groups)
    tunnel_ways = [w for w in airport.osm_ways
                   if is_tunnel(w, tn.admitted_values) and len(w.points) >= 2]
    cells = list(classification.cells)
    polys = [Polygon(c.ring, c.holes) for c in cells]
    # A BRIDGE STATES THE CROSSING (spec §34 (5); ARMED at round 2,
    # RULINGS 2026-09-13ai): an ``aeroway`` ``bridge=yes layer >= 1`` way
    # over a road seeds a bore the OSM data never tagged — neither measured
    # case tags one (LEMD F-6 way -1230, KCLT taxiway U -1560).  The clip
    # puts the mouth INSIDE the taxi cell so the corridor's rim lands on
    # the deck and takes its solved surface (``structure_underpass``'s
    # module doc; the round-1 measurement that forced it is there too).
    up_ways, up_parents, stats.underpasses = _underpass_bores(airport, law, cells, polys)
    tunnel_ways += up_ways
    if (not tunnel_ways and not corridors and not extra_groups) or not classification.cells:
        return classification, (), stats
    cell_tree = STRtree(polys) if polys else None
    bores = chains(tunnel_ways) if tunnel_ways else []
    stats.bores = len(bores)
    reach = tn.max_ramp_length_m + 2 * (tn.wall_gap_m + tn.wall_band_width_m)
    # ADMISSION IS BY THE MOUTH (spec §29 (1)/(2); RULINGS 2026-09-12r/12t,
    # owner 2026-09-12ab answering 12aa-1 "Build them"): a bore is built iff
    # a MAPPED END stands ON THE FIELD — that end, or its ramp reach, inside
    # the cover (with the roofed corridors) ⊕ ``mouth_standoff_m`` — whether
    # or not it passes under an airport surface (a portal on the field is
    # visible on approach, §31 (2)).  The retired cover test is DELETED: it
    # admitted LEMD's 4.9 km rail bores by 125–162 m under ONE pad and built
    # their mouths 4.0 km west, and refused 8 real portals ON the field.
    # Those 8 are counted (``bores_mouth_only``) and named.
    # ...AND WHERE A PILOT WOULD SEE IT (RULINGS 2026-09-12al): the region
    # is the cover ⊕ standoff UNION THE APPROACH CORRIDOR of §31 (2)
    # UNION §29 (7)'s RUNWAY LATERAL BAND (RULINGS 2026-09-13bm (ii): the
    # corridor runs BEYOND each threshold and never BESIDE the runway),
    # one derivation the harness's cockpit block reads through the same
    # classes.
    on_field = field_region_for(airport, law,
                                polys + [c.footprint for c in corridors])
    stats.approach_corridors = len(on_field.corridor or ())
    stats.runway_bands = len(on_field.band or ())
    mouth_list, dropped = (mouths(bores, list(airport.osm_ways), law, reach, on_field)
                           if bores else ([], []))
    for m in mouth_list if up_parents else ():
        par = next((up_parents[id(w)] for w in m.bore.ways if id(w) in up_parents), None)
        if par is not None:                  # §34 (5): the ramp follows the road
            m.approach = approach_along(par, m.xy, m.inward, reach)
    # THE PACK'S WALL OBJECTS GOVERN THE MOUTH (spec §33 (2)): a mouth
    # inside a thin plate spanning its bore moves to the object's end and
    # takes the object's width, before anything is reported or built.
    mouth_list, stats.plate_mouths = apply_plates(mouth_list, plates,
                                                  list(airport.osm_ways), law, reach)
    stats.mouths_off_field = len(dropped)
    (stats.mouths_off_field_nearest, stats.mouths_on_approach,
     stats.mouths_on_approach_named) = mouth_reports(on_field, mouth_list,
                                                     dropped)
    with_mouth = {id(b) for b in bores if any(m.bore is b for m in mouth_list)}
    covered = [b for b in bores if id(b) in with_mouth]
    mouth_only = [b for b in covered if not under_cover(b.line, polys, cell_tree)]
    stats.bores_no_mouth = len(bores) - len(covered)
    stats.bores_mouth_only = len(mouth_only)
    stats.mouth_only_bores = ["+".join(str(w.id) for w in b.ways) for b in mouth_only][:12]
    if not covered and not corridors and not extra_groups:
        return classification, (), stats
    # THE PRECEDENCE PER MOUTH (05n-3, ``tunnel.object.source_precedence``):
    # an OSM bore mouth inside an object corridor's footprint is the
    # object's — its OSM ramp is not built; a mouth outside every object
    # keeps its ramp exactly as before.  A bore covered at both mouths is
    # replaced; one covered at one end ships an object ramp there and an
    # OSM ramp at the other.
    replaced_ways: dict[str, list[int]] = {}
    if corridors and tn.object.source_precedence[0] == "object":
        tol = tn.object.bore_end_tolerance_m    # 2026-09-08o: a bore end within it PAIRS
        kept = []
        by_bore: dict[int, list[str | None]] = {}
        for m in mouth_list:
            cid = mouth_covered_by(m.xy, corridors, tol)
            by_bore.setdefault(id(m.bore), []).append(cid)
            if cid is None:
                kept.append(m)
            else:
                stats.mouths_replaced_by_object += 1
                replaced_ways.setdefault(cid, []).extend(i for i in m.ways
                                                          if i not in replaced_ways.get(cid, []))
        for b in covered:
            cs = by_bore.get(id(b), [])
            ids = "+".join(str(w.id) for w in b.ways)
            if cs and all(c is not None for c in cs):
                stats.bores_replaced_by_object += 1
                stats.bore_precedence.append(f"bore {ids}: both mouths inside {sorted(set(cs))} "
                                             f"— replaced")
            elif any(c is not None for c in cs):
                stats.bore_precedence.append(f"bore {ids}: one mouth inside "
                                             f"{[c for c in cs if c][0]}, the other keeps its OSM "
                                             f"ramp (05n-3)")
            else:
                stats.bore_precedence.append(f"bore {ids}: no object at either mouth — OSM ramps "
                                             f"stand")
        mouth_list = kept
    stats.mouths = len(mouth_list)
    groups = [Group(list(m), xy, inw, w, list(ax))
              for m, xy, inw, w, ax in (merge_duals(mouth_list, law, stats) if mouth_list else [])]
    groups += object_groups(corridors, list(airport.osm_ways), law, reach)
    groups += extra_groups
    stats.object_corridors = len(corridors)
    stats.door_ramps = sum(1 for g in extra_groups if g.kind == "door")
    stats.sunken_roads = sum(1 for g in extra_groups if g.kind == "sunken_road")
    stats.wall_corridors = sum(1 for g in extra_groups if g.kind == WALL_KIND)
    wc_law = co.wall_corridor

    # what a ramp may not cross
    runway_u = unary_union([p for p, c in zip(polys, cells) if c.role in RUNWAY_FAMILY]) \
        if any(c.role in RUNWAY_FAMILY for c in cells) else None
    pads = [(p, c.ref) for p, c in zip(polys, cells) if c.role == "building"]
    pad_refs = {ref for _p, ref in pads}
    pad_poly = {ref: p for p, ref in pads}
    band_m = law.tables.structures.basin.contact_band_m
    pad_tree = STRtree([p for p, _r in pads]) if pads else None
    # what a DOOR ramp stops at (spec othh-terminal-ramps §2/§4): every
    # governed cell beyond the well but the ones the well itself stands in
    # §34 (10) (owner RULINGS 2026-09-14bd): a ramp arriving at a ROAD
    # ends at the road's TRUE edge — ``road_true_edge``, whose docstring
    # carries this law's consumer census.
    _roads = [(p, c) for p, c in zip(polys, cells)
              if c.kind != "structure" and c.role in ROAD_ROLES]
    stops = [(road_true_edge(p, c, _roads) if c.role in ROAD_ROLES else p, c.ref)
             for p, c in zip(polys, cells)
             if c.kind != "structure" and c.role not in RUNWAY_FAMILY]
    stop_tree = STRtree([p for p, _r in stops]) if stops else None
    # a WALL-CORRIDOR ramp stops at AIRSIDE cells and pads only (Law C)
    stops_air = airside_stops(cells, polys, law, RUNWAY_FAMILY)
    # ...and at a SERVICE ROAD LOCKED TO AIRSIDE (§34 (9), owner RULINGS
    # 2026-09-14ak): a road whose level is an airside contact cannot yield
    # to the ramp, so the ramp ends at its edge with the cap lifted
    locked_half: dict = {}
    locked = locked_road_stops(cells, polys, law, RUNWAY_FAMILY,
                               law.tables.emit.road_contact.contact_reach_m, locked_half)
    locked_refs = {ref for _p, ref in locked}
    #: §34 (9) (4): the pack's `markings` bodies, parsed at most once and
    #: only where a ramp is actually pinched (they are refused at load)
    mark_cache: dict = {}
    stops_air = stops_air + locked
    stop_air_tree = STRtree([p for p, _r in stops_air]) if stops_air else None
    strip: list[Polygon] = []
    for p, c in zip(polys, cells):
        # §40 (4) (owner RULINGS 2026-09-14s): a SHOULDER manufactures no
        # region.  It is runway pavement (so every surface reader above
        # keeps it) but the strip keep-out is drawn around the RUNWAY,
        # which the shoulder lies inside; buffering the shoulder too drew
        # a second keep-out nothing ruled and refused VHHH's road tunnel
        # at 22.30368, 113.92917 (84,000 + 8,040 + 6,228 m2 of shoulder
        # by 75 m).  The census of every RUNWAY_FAMILY reader is the
        # spec's §40 (4) MEASURED table.
        if c.role in RUNWAY_FAMILY and not is_runway_shoulder(c):
            hw = zone2_half_width_m(law, "runway", c.code_number, c.code_letter)
            if hw:
                strip.append(p.buffer(hw, **_MITRE))
    strip_u = unary_union(strip) if strip else None
    bridges = [w for w in airport.osm_ways if is_bridge(w) and len(w.points) >= 2]
    bridge_lines = [LineString(w.points) for w in bridges]
    bridge_tree = STRtree(bridge_lines) if bridge_lines else None

    spacing = law.tables.emit.chords.station_spacing_m
    gap = tn.wall_gap_m
    rim_off = tn.wall_gap_m + tn.wall_band_width_m      # an OSM bore's rim stand-off
    grid = law.tables.emit.identity.min_distinct_spacing_m
    tunnels: list[Tunnel] = []
    new_cells: list[tuple[str, str, Polygon, str]] = []
    footprints: list[Polygon] = []
    hull_knives: list[Polygon] = []
    keepouts: list[Polygon] = []
    seen_ids: dict[str, int] = {}
    for g in groups:
        members, mouth, inward, width, axis_path = g.members, g.mouth, g.inward, g.width, g.axis
        c = g.corridor
        if c is None:
            base = "+".join(str(i) for m in members for i in m.ways)
            seen_ids[base] = seen_ids.get(base, -1) + 1
            tid = f"tunnel:{base}@{seen_ids[base]}"
        else:
            tid = g.tid
        half = width / 2.0
        axis_ln = LineString(axis_path)
        # the group's own law (a door ramp, 09-08b/c) or the tunnel's
        spacing_g = g.spacing_m if g.spacing_m else spacing
        grade_g = g.max_grade if g.max_grade else tn.ramp_max_grade
        fits = False

        def axis_fn(s: float, _ln=axis_ln) -> XY:
            p = _ln.interpolate(min(s, _ln.length))
            return (p.x, p.y)

        # THE MOUTH DATUM is the MOUTH WALL NODE's DEM − bore_datum_m
        # (09-03b): the rim's cap centre, the rim stand-off in front of
        # the mouth line — not the axis point's sample (measured LEMD
        # -15327+-5980: a cutting whose cap stands 2 m above the axis
        # sample; the ramp planned from the axis sample was 0.2 % over cap).
        # An OBJECT corridor's datum is ground(mouth) − depth (the floor
        # slab or the bore law, ``mouth_depth = "floor_slab"``, 2026-09-08l),
        # read by the corridor reader.
        cap_c = (mouth[0] + inward[0] * rim_off, mouth[1] + inward[1] * rim_off)
        mouth_dem = _dem(airport, cap_c) if c is None else c.mouth_dem_z
        if math.isnan(mouth_dem):
            stats.refused.append(f"{tid}: no DEM at the mouth")
            continue
        if c is None:
            # THE MOUTH CREST IS THE ROAD'S GROUND, NOT THE OVERBRIDGE'S
            # (spec §33 (3); owner RULINGS 2026-09-13d item 6).  `crest =
            # "dem"` samples the DEM at the mouth node; a portal's cover may
            # stand up to bore_datum_m above the road it lets out onto, and
            # no more — a sample that stands HIGHER is not the portal's
            # cover but an OVERBRIDGE EMBANKMENT crossing the road (measured
            # LEMD bore -5931's south mouth: DEM 610.23 at the cap against
            # 603.9-604.3 along the approach 12-24 m out, a 5.0-5.8 m rim
            # wall and a ramp that DESCENDED).  The crest is capped at the
            # approach's ground + bore_datum_m; the cap only bites beyond
            # split_tol_m, the materiality the sim read is judged at.
            ground = _approach_ground(airport, axis_fn, tn.bore_datum_m, spacing_g)
            cap_z = ground + tn.bore_datum_m if not math.isnan(ground) else None
            if cap_z is not None and mouth_dem - cap_z > tol_m:
                stats.crest_from_approach.append(
                    f"{tid}: mouth crest {mouth_dem:.2f} -> {cap_z:.2f} — the DEM at the mouth "
                    f"stands {mouth_dem - ground:.2f} m over the approach's ground {ground:.2f} "
                    f"(> bore_datum_m {tn.bore_datum_m} + split_tol_m {tol_m}): an "
                    f"overbridge embankment, not the portal's cover (§33 (3))")
                mouth_dem = cap_z
        mouth_z = c.floor_z if c is not None else mouth_dem - tn.bore_datum_m
        # decks across the corridor (a first pass over the full reach)
        deck_ivals = deck_intervals(axis_ln, half + rim_off, bridges, bridge_lines,
                                     bridge_tree, law)
        obj_ivals = object_deck_intervals(axis_ln, half + rim_off, odecks)
        if obj_ivals:
            # the object law governs where an object bridge stands: a
            # mapped bridge way over it mints no terrain deck (08-30d)
            ou = unary_union([dp for _o, _s0, _s1, dp, _z in obj_ivals])
            deck_ivals = [d for d in deck_ivals if not d[3].intersects(ou)]
        design_grade = g.design_grade if c is not None else tn.ramp_max_grade
        pav_ivals: list = []
        if c is not None and g.kind == WALL_KIND:
            # A WALL CORRIDOR (Law C, spec §6a rows 12/13): the floor is the
            # wall bottom, never a climb inside the walls; NO deck is read
            # anywhere along it — inside the walls the deck is the family's
            # own roof (the headroom test read it), and beyond them a mapped
            # bridge way is the pack's own VIADUCT over the sunken road
            # (measured OTHH TerminalRoads_03_004@1/b: the terrain deck the
            # bore model mints for way −8543 severed the ramp and held its
            # top 3.15 m under the ground — a demotion; spec §6b)
            fits = False
            deck_ivals = []
            obj_ivals = []
            design_grade = grade_g if g.climbs else 0.0
        elif c is not None and g.climbs:
            # THE RAMP INSIDE THE WALLS (05n-1): the climb starts AT the
            # mouth — or beyond the last PAVEMENT DECK inside the walls
            # (2026-09-06f: a taxi-family cell spanning the corridor is a
            # deck over the ramp, never cut; the ramp is flat at the mouth
            # datum under it) — and tops at the wall end when the RISE to
            # the ground there (the DEM at the wall end, less the mouth
            # datum: the depth on flat ground, more on relief) fits at the
            # law — along the axis AND over the ring pairs' direct distance
            # (the census prices chords) — else it continues beyond at
            # ramp_max_grade along the approach (mapped bridges inside the
            # walls are not read: the walls are the object's)
            deck_ivals = [d for d in deck_ivals if d[1] >= g.hull_s]
            obj_ivals = [d for d in obj_ivals if d[1] >= g.hull_s]
            pav_ivals = pavement_deck_intervals(axis_ln, half + rim_off, g.hull_s, cells, polys,
                                                 cell_tree, law, grid)
            resume = max([0.0] + [s1 + gap for _d, _s0, s1, _p in pav_ivals])
            e = axis_fn(g.hull_s)
            far_ground = _dem(airport, e)
            rise = (far_ground - mouth_z) if not math.isnan(far_ground) else c.depth_m
            rise = max(rise, 0.0)
            # the ring pairs the census prices: the resume line's corners
            # against the wall end's — their least DIRECT distance (a
            # curved corridor's inner corners stand nearer each other than
            # the axis chord; LEMD Bridge4: 116 m against a 121 m chord,
            # where the crude chord − width read 102 m and sent the climb
            # 430 m beyond the walls up a 7 % bank)
            chord = corner_distance(axis_fn, resume, g.hull_s, g.half_fn, half)
            run = g.hull_s - resume
            fits = (run * grade_g >= rise - 1e-9 and chord * grade_g >= rise - 1e-9)
            design_grade = min(grade_g, rise / max(run, 1e-9))
            if fits:
                deck_ivals, obj_ivals = [], []
            else:
                # the climb beyond the walls is planned first WITHOUT decks:
                # a deck standing beyond where the ramp already meets the
                # DEM is not over the ramp at all (the axis past the walls
                # is an extension, not a mapped road — OTHH tunnel_sw: a
                # bridge 400 m out pushed the climb past the reach)
                design_grade = grade_g
                s_free, _ss = _ramp_top(airport, law, axis_fn, mouth_z, resume, spacing_g,
                                        s_min=g.hull_s, grade=grade_g)
                if s_free is not None:
                    deck_ivals = [d for d in deck_ivals if d[1] <= s_free]
                    obj_ivals = [d for d in obj_ivals if d[1] <= s_free]
        climb_from = 0.0
        climb_from = max([climb_from] + [s1 + gap for _w, s0, s1, _p in deck_ivals]
                         + [s1 + gap for _d, s0, s1, _p in pav_ivals]
                         + [s1 + gap for _o, s0, s1, _p, _z in obj_ivals])
        if g.climb_from_s is not None and not fits:
            # a door ramp (09-08b/c): the well floor stays at the sill, the
            # climb starts at the well's outer edge
            climb_from = max(climb_from, g.climb_from_s)
        covered_from = None
        # ── §34 (9) (5): FULL DEPTH AT THE BUILDING WALL ──────────────
        # (owner RULINGS 2026-09-14aq, CORRECTED by 14be.)  The corridor's
        # full-depth point is where it becomes COVERED — the edge of the
        # COVERING PLATE that gives it its headroom — never the outer end
        # of the wall bands protruding from it, and never the building PAD
        # (14at read the pad and the owner still saw the walls).  The
        # uncovered stretch is RAMP, and the run it adds is what takes the
        # pinched grade down; see ``structure_geometry.covered_start``.
        if g.kind == WALL_KIND and c is not None and g.climbs:
            covered_from = _covered_start(axis_fn, g.hull_s,
                                          getattr(c, "plate_plan", None), grid)
            if covered_from is not None and covered_from < climb_from - 1e-6:
                climb_from = covered_from
        # a group's length law is measured from where its climb starts
        max_len_g = None if g.max_length_m is None else climb_from + g.max_length_m + spacing_g
        if g.climbs and c is not None and fits:
            ss = [spacing_g * k for k in range(int(g.hull_s // spacing_g) + 1)]
            if g.hull_s - ss[-1] > 1e-6:
                ss.append(g.hull_s)
            if climb_from > 0.0 and all(abs(s - climb_from) > 1e-6 for s in ss):
                ss = sorted(ss + [climb_from])      # the resume station beyond the deck
            s_top = g.hull_s
        elif g.climbs:
            if c is not None and c.far_closed:
                stats.refused.append(f"{tid}: the {grade_g:.0%} climb cannot reach the "
                                     f"ground inside the walls ({c.depth_m:.2f} m over "
                                     f"{g.hull_s:.0f} m) and the far end is a wall")
                continue
            s_top, ss = _ramp_top(airport, law, axis_fn, mouth_z, climb_from, spacing_g,
                                  s_min=g.hull_s if c is not None else 0.0, grade=grade_g,
                                  max_len=max_len_g)
            if s_top is None:
                if any(math.isnan(_dem(airport, axis_fn(s))) for s in ss):
                    stats.refused.append(f"{tid}: no DEM along the climb (the corridor leaves "
                                         f"the DEM / reaches water) within {ss[-1]:.0f} m")
                else:
                    ds = [_dem(airport, axis_fn(s)) for s in ss]
                    m = axis_fn(climb_from)
                    e = axis_fn(ss[-1])
                    lim = tn.max_ramp_length_m if g.max_length_m is None else g.max_length_m
                    stats.refused.append(f"{tid}: the {grade_g:.0%} climb from "
                                         f"{mouth_z:.2f} at s {climb_from:.0f} does not reach the "
                                         f"DEM ({min(ds):.2f}..{max(ds):.2f}) within "
                                         f"{lim:.0f} m (axis {axis_ln.length:.0f} m, "
                                         f"chord at the end {math.hypot(e[0] - m[0], e[1] - m[1]):.0f} m, "
                                         f"half {half:.1f} m)")
                continue
            if c is not None and all(abs(s - g.hull_s) > 1e-6 for s in ss):
                # the station ON the wall end: the trench spans the walls
                ss = sorted(ss + [g.hull_s])
        else:
            # a trench flat at the mouth depth (two mouths, 05n-1 at each):
            # stations along the walls, the last one ON the far end line
            ss = [spacing_g * k for k in range(int(g.hull_s // spacing_g) + 1)]
            if g.hull_s - ss[-1] > 1e-6:
                ss.append(g.hull_s)
            s_top = g.hull_s
            climb_from = g.hull_s
        # a building pad across the approach CLIPS the ramp at the pad's
        # edge (08-07 ruling 3); an object corridor's WALLS are never
        # clipped — the object is the authority (05k-1) and the trench is
        # senior to the pad (08-26): only its ramp BEYOND the walls is
        top_pinned = g.climbs
        clipped_by = ""
        moved_m = 0.0
        pinched = None
        road_witness = ""
        ss = [s for s in ss if s <= s_top + 1e-9]
        beyond = beyond_strip(axis_fn, g.hull_s, reach + width) if c is not None and g.climbs else None
        # a door ramp's HOST cells: the ones its well stands in (cut like
        # any structure); every other cell beyond the well stops the ramp
        host: set[str] = set()
        stop_list, stop_tree_g = (stops, stop_tree) if g.stop_side is None \
            else (stops_air, stop_air_tree)
        if g.stop_at_pavement and stop_tree_g is not None and c is not None:
            near = c.footprint.buffer(grid)
            host = {stop_list[int(j)][1] for j in stop_tree_g.query(near, predicate="intersects")}
            if g.kind == WALL_KIND:
                # a building PAD hosts a Law C ramp only when it is FLAT
                # ground (its DEM relief within basin.contact_band_m: the
                # owner's bays stand inside OTHH's terminal pad on the flat
                # site, its plane = the ground); a pad on RELIEF is a levelled
                # plane the ramp's top cannot meet at the DEM (measured LEMD
                # Cargo-NEWCO@5/a: the top pinned 3.2 m over the pad's plane,
                # a demotion) — it stops the ramp (tunnel.ramp_crosses_pad),
                # the walls still cut it (08-26)
                host = {ref for ref in host
                        if ref not in pad_refs or _pad_relief_m(airport, pad_poly[ref]) <= band_m}
        half_fn = g.half_fn
        traced: list[str] = []
        if c is None:
            # THE RAMP WIDTH FROM THE PAVEMENT (2026-09-06b (2)): a pavement
            # tracing the road sets the ramp's edges per station
            pav_hw, traced = pavement_half_widths(axis_fn, ss, cells, polys, law, half)
            if pav_hw:
                def half_fn(s: float, _hw=pav_hw, _h=half) -> tuple[float, float]:
                    return _hw.get(s, (_h, _h))
        while True:
            geom = geometry(axis_fn, ss, half, rim_off, inward, grid, g.capped, g.far_capped,
                            half_fn, g.rim_fn, g.cap_off, g.far_off)
            if geom is None:
                stats.refused.append(f"{tid}: the approach bends tighter than the corridor "
                                     f"(ramp or wall ring self-intersects)")
                break
            if c is not None and g.kind == WALL_KIND:
                # Law C (08m (a)): the RAMP stops at the pavement EDGE — the
                # rim beside its top may enter the pavement (the cut apron's
                # edge becomes the rim, its value shared) — one grid step off
                probe = geom.ramp if beyond is None else geom.ramp.intersection(beyond)
                stop_gap = grid
            else:
                probe = geom.outer if beyond is None else geom.outer.intersection(beyond)
                stop_gap = gap
            if probe.is_empty:
                hit = None
            elif g.stop_at_pavement:
                hit = _pad_hit(probe, stop_list, stop_tree_g, stop_gap, host)
            else:
                hit = _pad_hit(probe, pads, pad_tree, gap)
            if hit is None:
                break
            clipped_by = hit
            top_pinned = False
            if len(ss) <= 2:
                stats.refused.append(f"{tid}: the mouth stands against "
                                     f"{'pavement' if g.stop_at_pavement else 'building pad'} {hit}")
                geom = None
                break
            ss = ss[:-1]
            s_top = ss[-1]
        if geom is None:
            continue
        if c is not None and g.kind == WALL_KIND and clipped_by and g.climbs:
            # Law C (08m (a)): run to the pavement EDGE and steepen, or refuse
            ss, geom, s_top, design_grade, why, moved_to, pinched = stop_and_steepen(
                airport, wc_law, axis_fn, axis_ln, ss, s_top, climb_from, mouth_z, clipped_by,
                stop_list, stop_tree_g, host, beyond, grid, spacing_g,
                lambda ss_try: geometry(axis_fn, ss_try, half, rim_off, inward, grid, g.capped,
                                        g.far_capped, half_fn, g.rim_fn, g.cap_off, g.far_off),
                locked_refs, mark_cache)
            if why:
                stats.refused.append(f"{tid}: {why}")
                continue
            # §34 (8) as amended (14u): the MOUTH moved away from airside by
            # the run the cap needs, back under the building; the ramp runs
            # at the cap from there and still reaches the ground
            moved_m, climb_from = climb_from - moved_to, moved_to
            top_pinned = True
            if pinched:
                # §34 (9) (4)'s witness rides BESIDE ``Tunnel.pinched``, which
                # stays the (road, span, grade) triple 34 (9) (3) unpacks
                road_witness = pinched[3] or "the road face edge (the pack paints no line here)"
                pinched = pinched[:3]
        # ── §34 (7): THE STATIONS ARE THE SAMPLING, NOT THE EMITTED SHAPE
        # (owner RULINGS 2026-09-14n item 2 / 2026-09-14p).  The profile is
        # solved above; now a straight constant-grade run collapses to its
        # two end chords, so the 0.5 m identity ``snap_out`` has nothing
        # between the ends to stagger (OTHH's terminal ramps read 40 and 29
        # nodes on a STRAIGHT route, one grid quantum of zig-zag per 2 m
        # station).  The knees — the mouth, where the climb starts, the wall
        # end and the pinned top — are never collapsed through.
        collapse_note = ""
        if len(ss) > 2:
            # §34 (7): a straight constant-grade run emits its end chords
            ss_c = collapse_for_ramp(
                axis_fn, ss, half, rim_off, half_fn, g, climb_from=climb_from, s_top=s_top,
                mouth_z=mouth_z, design_grade=design_grade, top_pinned=top_pinned,
                wall_kind=g.kind == WALL_KIND, dem_z=airport.dem.z, grid=grid,
                z_tol=law.tables.emit.materiality.elevation_m)
            geom_c = geometry(axis_fn, ss_c, half, rim_off, inward, grid, g.capped,
                              g.far_capped, half_fn, g.rim_fn, g.cap_off, g.far_off) \
                if len(ss_c) < len(ss) else None
            if geom_c is not None:
                collapse_note = (f"stations collapsed {len(ss)} -> {len(ss_c)} (§34 (7): a "
                                 f"cross-chord only where the route bends or the profile breaks)")
                ss, geom = ss_c, geom_c
        axis, left, right = geom.axis, geom.left, geom.right
        ramp, outer, cap_out = geom.ramp, geom.outer, geom.cap_out
        if c is not None and not g.capped and g.mouth_strip:
            # an OPEN mouth (the bore continues under the covering ground):
            # a one-spacing strip beyond the mouth line cuts that ground back,
            # so the mouth edge shares no vertex with it (09-01c/e; 09-08a)
            a, b = left[0], right[0]
            strip_m = LineString([a, b]).buffer(grid, cap_style="flat", **_MITRE)
            outer = unary_union([outer, strip_m])
            if outer.geom_type != "Polygon":
                outer = outer.convex_hull
        # THE VOID between the ramp and the rim (2026-09-06b): one face
        # whose exterior is the rim and whose hole is the ramp — never a
        # surface, the mesh triangulates the wall inside it
        wall = outer.difference(ramp)
        # refusals: a runway-family crossing, the runway strip keep-out
        if runway_u is not None and outer.intersects(runway_u) and \
                outer.intersection(runway_u).area > 1e-6:
            stats.refused.append(f"{tid}: the ramp would cross a runway-family face "
                                 f"before reaching the DEM (ramp_cuts_runway_family = false)")
            continue
        if strip_u is not None and wall.intersects(strip_u) and \
                wall.intersection(strip_u).area > 1e-6:
            stats.refused.append(f"{tid}: the wall would stand inside the runway strip "
                                 f"keep-out (retaining_wall.in_runway_strip = false)")
            continue
        # decks sever the ramp (by the gap) and the walls (exactly)
        # §33 (4) / §34.5 (6) AMENDED (RULINGS 2026-09-14bp item 10): one
        # entry per deck FACE — parallel bridge ways sharing this crossing
        # are ONE deck (``structure_deck.deck_items`` carries the law).
        items = deck_items(deck_ivals, pav_ivals, grid, law)
        deck_notes: list[str] = []
        decks, deck_polys, deck_roles, bridge_faces, dn, npav, nbr, nobj = emit_decks(
            airport, law, items, obj_ivals, outer, s_top, cells, polys, cell_tree)
        deck_notes.extend(dn)
        stats.pavement_decks += npav
        stats.decks += nbr
        stats.object_decks += nobj
        # the ramp's ref is EXACTLY the oracle's population key too
        # §33 (4): a deck face spanning THE WAY reaches past the corridor,
        # so the structure's FOOTPRINT reaches with it — the knife must cut
        # the pavement under the deck too, or the deck cell would stand on
        # top of an uncut cell (two faces, one ground).  The void and the
        # wall are unchanged: the decks are subtracted from both.
        if bridge_faces:
            ext = unary_union([outer, *bridge_faces])
            outer = ext if ext.geom_type == "Polygon" else \
                max(_parts(ext), key=lambda g: g.area, default=outer)
        ramp_refs: list[str] = []
        ramp_geom = ramp
        wall_geom = wall
        if deck_polys:
            du = unary_union(deck_polys)
            ramp_geom = ramp.difference(du.buffer(gap + grid, **_MITRE))
            # the void is severed at the deck like the ramp; the gap strip
            # between a ramp piece and the deck stays unowned (the portal
            # under the bridge the mesh triangulates), never void
            wall_geom = outer.difference(unary_union([ramp, du]))
        ramp_parts = _parts(ramp_geom)
        # a door ramp is its own role (09-08b/c; since 09-12m both face caps
        # are the road 8 %, but the generation and oracle law differ); a
        # wall corridor names its own (Law C: wall_corridor_ramp / garage_ramp)
        ramp_role = g.ramp_role or ("door_ramp" if g.kind == "door" else "tunnel_ramp")
        for part in ramp_parts:
            ramp_refs.append(ramp_role)
            new_cells.append((ramp_role, ramp_role, part, tid))
        wall_ref = "tunnel_wall"
        for part in _parts(wall_geom):
            new_cells.append(("retaining_wall", wall_ref, part, tid))
        for d, dp, drole in zip(decks, deck_polys, deck_roles):
            for k, part in enumerate(_parts(dp)):
                new_cells.append((drole, d.ref + (f"#{k}" if k else ""), part, tid))
        # THE RIM PATH: the rim ring itself (left rim top→mouth, the cap,
        # right rim mouth→top, the far cap) — the generator groups the
        # rim's vertices by projection onto it and pins the bare ones at
        # the DEM there (2026-09-06b: no band, no analytic centreline)
        cap_mid = list(cap_out)
        far_mid = list(geom.far_out)
        wall_path = list(reversed(geom.left_rim)) + cap_mid + list(geom.right_rim) + far_mid
        if far_mid and cap_mid:
            wall_path.append(wall_path[0])          # the O: a closed rim
        notes = list(deck_notes)
        if collapse_note:
            notes.append(collapse_note)
        if len(members) > 1:
            notes.append(f"dual carriageway of {len(members)} bores (2026-08-31h)")
        # spec §34 (5): a bore the aeroway bridge STATED — the rim under its
        # deck takes the taxi cell's solved surface, never DEM(mouth)
        up_deck = next((w.tags[UNDERPASS_TAG] for m in (g.members or ())
                        for w in getattr(getattr(m, "bore", None), "ways", ())
                        if UNDERPASS_TAG in (w.tags or {})), None)
        if up_deck:
            notes.append(f"{UNDERPASS_NOTE}{up_deck}")
        for d, drole in zip(decks, deck_roles):
            if d.datum == "deck_top":
                notes.append(f"object bridge {d.ref} deck top {d.z:.2f} over s {d.s0:.0f}-{d.s1:.0f}")
            elif drole != "service_road":
                notes.append(f"pavement deck {d.ref} ({drole}) over s {d.s0:.0f}-{d.s1:.0f} "
                             f"(2026-09-06f: a deck over the ramp, never a cut; the climb "
                             f"resumes at {climb_from:.0f} m)")
        if clipped_by:
            notes.append(f"clipped at building pad {clipped_by} at {s_top:.1f} m "
                         f"(08-07 ruling 3)")
        if traced:
            hws = [half_fn(s) for s in ss if half_fn is not None]
            notes.append(f"ramp width from the pavement tracing the road (2026-09-06b (2)): "
                         f"{', '.join(traced)} — {min(a + b for a, b in hws):.1f}-"
                         f"{max(a + b for a, b in hws):.1f} m over {len(hws)} stations "
                         f"(lanes default {width:.1f} m)")
        extra: dict = {}
        profile_out: tuple = ()
        if c is not None:
            outside = trench_outside_m(ramp_parts, c, co.floor_overlap_m, grid)
            expect = _reseat_expect(c, mouth_z, design_grade, s_top, airport) \
                if g.kind == "object" else ()
            top_ground = None
            if g.kind == "object":
                notes.append(f"tunnel wall object {c.resource} (2026-09-05n; depth 2026-09-08l): "
                             f"floor at the mouth {mouth_z:.2f} = ground {mouth_dem:.2f} − depth "
                             f"{c.depth_m:.2f} ({'floor slab' if c.floor_y is not None else 'bore_datum_m'}; "
                             f"crest {c.plate_y:.2f}), ends {c.ends}, mouth by {c.mouth_kind}")
            elif g.kind == "door":
                top_ground = _dem(airport, axis_fn(s_top))
                notes.append(f"door ramp (2026-09-08b/c Law A) of {c.resource}: sill {mouth_z:.2f} "
                             f"= ground {mouth_dem:.2f} − {c.depth_m:.2f}, well {g.hull_s:.2f} m "
                             f"(floor overlap {co.floor_overlap_m} m each end), climb "
                             f"{s_top - climb_from:.1f} m at {100.0 * design_grade:.1f} % to the "
                             f"ground {top_ground:.2f} at s {s_top:.1f}"
                             + (f" — STOPS at {clipped_by} (the ramp steps)" if clipped_by else ""))
            elif g.kind == WALL_KIND:
                # LAW C (2026-09-08m/08n): the published profile includes the
                # climb (spec §6a row 19); the site line the report quotes
                profile_out, top_ground = wall_corridor_profile(
                    airport, g, ss, s_top, mouth_z, design_grade, axis_fn, climb_from)
                notes.append(wall_corridor_note(c, g, mouth_dem, s_top, climb_from, design_grade,
                                                top_ground, clipped_by, moved_m, pinched,
                                                covered_from, road_witness))
                if pinched:
                    stats.pinched_ramps.append(
                        f"{tid}: pinched against {pinched[0]} — {pinched[1]:.1f} m from the road "
                        f"edge down to the building edge at {100.0 * pinched[2]:.1f} % "
                        f"(cap lifted, §34 (9)); the road edge is {road_witness or 'the face edge'}"
                        + f" stood out by the road's {locked_half.get(pinched[0], 0.0):.2f} m "
                          f"half-width (§34 (9) (6))"
                        + (f"; full depth at the COVERING PLATE's edge, s {covered_from:.1f} "
                           f"(+{g.hull_s - covered_from:.1f} m of run, §34 (9) (5)/14be)"
                           if covered_from is not None and covered_from < g.hull_s - 1e-6 else ""))
            else:
                notes.append(f"sunken road (2026-09-08b/c Law B) of {c.resource}: cut {mouth_z:.2f} "
                             f"= ground {mouth_dem:.2f} − {c.depth_m:.2f}, {g.hull_s:.1f} m along "
                             f"the plate to its top, floor = the plate per station "
                             f"({len(g.profile)} stations)")
            notes.extend(c.notes)
            extra = dict(source=g.kind, crest=tn.crest, crest_z=mouth_dem,
                         profile=profile_out if g.kind == WALL_KIND else tuple(g.profile),
                         top_ground_z=top_ground,
                         resource=c.resource, objects=tuple(c.objects), depth_m=c.depth_m,
                         plate_y_m=c.plate_y, edge_wall=c.edge_wall,
                         hull_length_m=c.length_m, hull_width_m=c.width_m, ends=c.ends,
                         replaced_ways=tuple(replaced_ways.get(c.id, ())),
                         capped=g.capped, far_capped=g.far_capped,
                         wall_length_m=c.length_m, mouth_kind=c.mouth_kind,
                         ground_kind=c.ground_kind, reseat_expect_m=expect,
                         trench_outside_max_m=outside,
                         footprint=tuple((float(x), float(y)) for x, y in
                                         c.footprint.exterior.coords[:-1])
                         if c.footprint.geom_type == "Polygon" else ())
        tunnels.append(Tunnel(tid, tuple(i for m in members for i in m.ways),
                              tuple(axis), half, mouth_dem, mouth_z, s_top, climb_from,
                              tuple(ramp_refs), wall_ref, tuple(wall_path), tuple(decks),
                              tuple(notes), top_pinned, clipped_by,
                              (cap_mid[0], cap_mid[2]) if cap_mid else None,
                              cap_mid[1] if cap_mid else None, design_grade=design_grade,
                              pinched=pinched, **extra))
        if clipped_by:
            # THE PORTAL FACE AT THE PAD EDGE (08-07 ruling 3): the clipped
            # ramp's top edge stands off the ground beyond it by the gap
            # too — an unowned strip the mesh triangulates as the face
            dx, dy = right[-1][0] - left[-1][0], right[-1][1] - left[-1][1]
            L = math.hypot(dx, dy) or 1.0
            ext = rim_off + 4 * grid
            a = (left[-1][0] - dx / L * ext, left[-1][1] - dy / L * ext)
            b = (right[-1][0] + dx / L * ext, right[-1][1] + dy / L * ext)
            top = LineString([a, b]).buffer(gap + grid, cap_style="flat", **_MITRE)
            outer = unary_union([outer, top])
            if outer.geom_type != "Polygon":
                outer = outer.convex_hull
        footprints.append(outer)
        keepouts.append(outer)
        if c is not None:
            # the walls cut EVERYTHING but the runway family — the pad too
            # (08-26: the trench is senior to the pad authority).  Beyond the
            # walls the ramp cuts the pads it HOSTS and only those (spec §6a
            # row 16; the flat-pad host rule 2026-09-08n): a pad the ramp
            # merely reaches is guarded (tunnel.ramp_crosses_pad — it stopped
            # the ramp, LEMD Cargo-NEWCO@5/a), but a HOST pad that keeps its
            # Flat over the ramp's own vertices is a contradiction the ladder
            # demotes — measured at OTHH Terminal_Base_2_1: 5 `building5` pad
            # flats gripped 7 wall-corridor FLOOR vertices, 10 rows demoted at
            # 1.392 m (the bays' full depth).
            knife = outer
            if beyond is not None:
                guard = []
                if pad_tree is not None:
                    for j in pad_tree.query(beyond, predicate="intersects"):
                        poly, ref = pads[int(j)]
                        if ref not in host:
                            guard.append(poly)
                keep_out = beyond.intersection(unary_union(guard)) if guard else None
                if keep_out is not None and not keep_out.is_empty:
                    knife = outer.difference(keep_out)
            hull_knives.append(knife)
    # TWO STRUCTURES MAY NOT OVERLAP: parallel mouths beyond 31h's test
    # (a diverging separation profile, a crossing approach) would be
    # polygonised into crumbs; the narrower one is refused loudly
    keep = [True] * len(tunnels)
    siblings = {g.tid: g.sibling for g in groups if g.sibling}
    # A LEVEL CORRIDOR IS BUILT WHOLE OR NOT AT ALL (Law C, spec §6a row
    # 15): its two capless halves share their mouth line; a half whose
    # sibling was refused would stand open against the ground there (the
    # measured OTHH tile: a 12.2 m demotion at Qatar_DutyFree_003@1/b)
    built_ids = {t.id for t in tunnels}
    for i, t in enumerate(tunnels):
        sib = siblings.get(t.id)
        if sib and sib not in built_ids:
            keep[i] = False
            stats.refused.append(f"{t.id}: its sibling half {sib} was refused — a level corridor "
                                 f"is built whole or not at all (Law C)")
    for i in range(len(tunnels)):
        for j in range(i + 1, len(tunnels)):
            if not (keep[i] and keep[j]):
                continue
            if siblings.get(tunnels[i].id) == tunnels[j].id:
                continue            # two halves of one corridor meet at their mouth line
            if not footprints[i].intersects(footprints[j]):
                continue
            inter = footprints[i].intersection(footprints[j])
            wall_i, wall_j = tunnels[i].source == WALL_KIND, tunnels[j].source == WALL_KIND
            # a WALL CORRIDOR may not even TOUCH another structure (Law C):
            # a shared ring vertex carries the other's pin into its rows
            # (measured OTHH: a Parking_004 corridor's vertex on the door
            # ramp Parking-Right_000@1's ring — its 8 % rows over 1.6 m
            # yielded 13 mm); the OTHER structure is senior
            touches = (wall_i or wall_j) and (inter.area > 1e-9 or inter.length > grid)
            if inter.area > 1.0 or touches:
                if wall_i != wall_j:
                    drop = i if wall_i else j
                else:
                    drop = i if footprints[i].area < footprints[j].area else j
                other = j if drop == i else i
                keep[drop] = False
                stats.refused.append(f"{tunnels[drop].id}: its corridor overlaps "
                                     f"{tunnels[other].id} (not a dual under 31h's "
                                     f"separation test)")
    if not all(keep):
        new_cells = [c for c in new_cells if _owner_kept(c, tunnels, keep)]
        tunnels = [t for t, k in zip(tunnels, keep) if k]
        footprints = [f for f, k in zip(footprints, keep) if k]
        keepouts = [f for f, k in zip(keepouts, keep) if k]
    stats.tunnels = len(tunnels)
    if not tunnels:
        return classification, (), stats

    # cut the pavement the structures run through (never the runway
    # family, never a pad — those refused above; an object's walls cut pads)
    knife = unary_union(footprints)
    hull_knife = unary_union(hull_knives) if hull_knives else None
    out_cells: list[Cell] = []
    for c, p in zip(cells, polys):
        blade = knife
        if c.role == "building":
            blade = hull_knife
        if c.role in RUNWAY_FAMILY or blade is None or not p.intersects(blade):
            out_cells.append(c)
            continue
        rest = p.difference(blade)
        stats.cells_cut += 1
        for k, part in enumerate(_parts(rest)):
            if part.area < 0.25:
                continue
            out_cells.append(Cell(len(out_cells), c.role, c.ref if k == 0 else f"{c.ref}#{k}",
                                  tuple(part.exterior.coords)[:-1],
                                  tuple(tuple(h.coords)[:-1] for h in part.interiors),
                                  c.code_number, c.code_letter, c.side, c.kind,
                                  dict(c.evidence, structure_cut=1.0)))
    by_ref = {c.ref: c for c in cells}
    for role, ref, part, _tid in new_cells:
        src = by_ref.get(ref.split(":", 1)[1].split("#")[0]) if ref.startswith("bridge_deck:") \
            else None
        if src is not None and src.role == role:
            # a PAVEMENT DECK piece (2026-09-06f): the pavement's own
            # class, side and kind — its law is the pavement's
            out_cells.append(Cell(len(out_cells), role, ref, tuple(part.exterior.coords)[:-1],
                                  tuple(tuple(h.coords)[:-1] for h in part.interiors),
                                  src.code_number, src.code_letter, src.side, src.kind,
                                  dict(src.evidence, pavement_deck=1.0)))
            continue
        out_cells.append(Cell(len(out_cells), role, ref, tuple(part.exterior.coords)[:-1],
                              tuple(tuple(h.coords)[:-1] for h in part.interiors),
                              None, None, role_side(law, role), "structure", {}))
    out_cells = [_dc.replace(c, id=i) for i, c in enumerate(out_cells)]
    cl = _dc.replace(classification, cells=tuple(out_cells),
                     keepouts=tuple(tuple(k.exterior.coords)[:-1] for k in keepouts),
                     stats={**dict(classification.stats), "tunnels": stats.tunnels,
                            "tunnel_decks": stats.decks, "tunnel_object_decks": stats.object_decks,
                            "tunnel_pavement_decks": stats.pavement_decks,
                            "tunnel_cells_cut": stats.cells_cut,
                            "tunnels_refused": len(stats.refused),
                            "tunnel_object_corridors": stats.object_corridors,
                            "bores_replaced_by_object": stats.bores_replaced_by_object,
                            "mouths_replaced_by_object": stats.mouths_replaced_by_object})
    return cl, tuple(tunnels), stats


def _owner_kept(cell: tuple, tunnels: list[Tunnel], keep: list[bool]) -> bool:
    ids = {t.id for t, k in zip(tunnels, keep) if k}
    return cell[3] in ids


def _parts(geom) -> list[Polygon]:
    if geom is None or geom.is_empty:
        return []
    return [g for g in shapely.get_parts(geom) if g.geom_type == "Polygon" and g.area > 1e-6]
