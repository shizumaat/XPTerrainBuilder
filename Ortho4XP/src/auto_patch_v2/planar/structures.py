"""STRUCTURE GEOMETRY (M4): tunnel corridors from the OSM bore + approach
ways, road bridge decks, and how they enter the planar map — as CELLS
that CUT the pavement they run through, plus the records
(``model.structures``) the generator and the verifier read.

THE MODEL (RULINGS 2026-08-07 portal fidelity; 2026-08-30 canonical
mouth; 2026-08-31h dual carriageways; 2026-09-01c/e gap; 2026-09-03b
crest = DEM; law ``structures.toml [tunnel]``):

* a BORE is a chain of mapped ``tunnel=yes`` ways; it is generated only
  where it passes UNDER an airport surface (a classified cell) — a bore
  that touches no cell drapes the DEM like any road v2 does not emit;
* the MOUTH is the mapped end of the bore (08-07 ruling 1: "mapped ends
  are preserved unconditionally"); the bore itself is never emitted —
  the covering surface keeps its own law (08-07 ruling 2: mapped-bore
  interiors are roofed by definition);
* the RAMP descends the approach corridor to the mouth line: its axis
  follows the approach ways outward from the mouth, its width is the
  carriageway's (``width`` tag, else ``lanes × lane_width_m``); two
  bores whose mouths stand within ``dual_carriageway_max_separation_m``
  with parallel approaches are ONE ramp spanning both (31h); the ramp
  ends where a ``ramp_max_grade`` climb from the mouth datum meets the
  DEM (the top edge is DEM);
* ``wall_gap_m`` of UNOWNED ground round the ramp (three sides), then
  the WALL BAND (``wall_band_width_m``) on both sides and an END CAP
  across the mouth — one U-shaped face whose crest is the DEM;
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
  between its walls' inner faces following their curves, the band each
  wall's own footprint, the floor at the mouth = ground − plate height,
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

from ..classify.roles import Cell, Classification
from ..law import Law
from ..law.tables import role_side, zone2_half_width_m
from ..model.airport import Airport, OsmWay
from ..model.frame import XY
from ..model.structures import Deck, Tunnel
from .basins import object_decks
from .object_corridor import Group, mouth_covered_by, object_groups, trench_outside_m
from .structure_approach import (carriageway_width_m, chains, is_bridge, is_tunnel,
                                 merge_duals, mouths, unit)
from .structure_geometry import geometry

__all__ = ["StructureStats", "build_structures", "carriageway_width_m"]

_MITRE = dict(join_style="mitre", mitre_limit=2.0)
RUNWAY_FAMILY = ("runway", "runway_crossing")
#: Two OSM node coordinates closer than this (frame metres) are one node.
NODE_TOL = 0.05
#: Approach ways are followed at most this many hops from the mouth.
MAX_HOPS = 6
#: A deck crossing the axis at less than this angle is along it, not over it.
_DECK_MIN_ANGLE_DEG = 30.0
#: Two directions within 30° are parallel (31h's dual test; the approach kink test).
PARALLEL_COS = math.cos(math.radians(30))


@_dc.dataclass
class StructureStats:
    """What the structure pass found, made and refused."""

    bores: int = 0
    bores_uncovered: int = 0
    mouths: int = 0
    duals_merged: int = 0
    tunnels: int = 0
    decks: int = 0
    object_decks: int = 0
    refused: list[str] = _dc.field(default_factory=list)
    cells_cut: int = 0
    #: RULINGS 2026-09-05k-1 / 05n-3: object corridors built, the OSM bores
    #: replaced (both mouths inside an object), the mouths taken, and the
    #: per-bore precedence record.
    object_corridors: int = 0
    bores_replaced_by_object: int = 0
    mouths_replaced_by_object: int = 0
    bore_precedence: list[str] = _dc.field(default_factory=list)


def _dem(airport: Airport, p: XY) -> float:
    return float(airport.dem.z(p[0], p[1]))


def _ramp_top(airport: Airport, law: Law, axis_fn, mouth_z: float, climb_from: float,
              spacing: float, half: float) -> tuple[float | None, list[float]]:
    """``(s_top, station s values)`` — the first station where the
    ``ramp_max_grade`` climb from ``mouth_z`` (starting at ``climb_from``)
    is at or above the DEM AND the DIRECT distance from the mouth line
    reaches the climb at the cap (the within-shape law prices ring pairs
    over the chord, so a curved corridor needs more axis than a straight
    one), plus one station of slack; ``None`` when the DEM is not reached
    within ``max_ramp_length_m``."""
    tn = law.tables.structures.tunnel
    ss = [0.0]
    s = 0.0
    m = axis_fn(climb_from)          # the chord is measured from where the climb starts
    while s < tn.max_ramp_length_m:
        s += spacing
        ss.append(s)
        if s <= climb_from:
            continue
        # the ramp meets the DEM where the DEM enters the ±ramp_max_grade
        # CONE from the datum: rising ground is climbed, ground that has
        # fallen below the bore floor (a mouth on a ridge of the smoothed
        # DEM — measured LEMD -15327+-5980: the DEM 8.4 m under the datum
        # 24 m out) is descended to, never stepped down to
        reach = tn.ramp_max_grade * (s - climb_from)
        p = axis_fn(s)
        d = _dem(airport, p)
        if math.isnan(d):
            return None, ss
        chord = math.hypot(p[0] - m[0], p[1] - m[1]) - 2.0 * half
        if abs(d - mouth_z) <= reach and chord * tn.ramp_max_grade >= abs(d - mouth_z):
            ss.append(s + spacing)
            return s + spacing, ss
    return None, ss


# ── build ────────────────────────────────────────────────────────────────

def build_structures(airport: Airport, classification: Classification, law: Law,
                     objects: _t.Sequence = (), corridors: _t.Sequence = ()
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
    referenced ramp, the band each wall's footprint at the ground.  A
    classification with no bores and no corridors comes back unchanged."""
    stats = StructureStats()
    odecks = object_decks(objects)
    tn = law.tables.structures.tunnel
    corridors = list(corridors)
    tunnel_ways = [w for w in airport.osm_ways if is_tunnel(w) and len(w.points) >= 2]
    if (not tunnel_ways and not corridors) or not classification.cells:
        return classification, (), stats
    cells = list(classification.cells)
    polys = [Polygon(c.ring, c.holes) for c in cells]
    cover = unary_union(polys)
    bores = chains(tunnel_ways) if tunnel_ways else []
    stats.bores = len(bores)
    covered = []
    for b in bores:
        if b.line.intersection(cover).length >= 1.0:
            covered.append(b)
        else:
            stats.bores_uncovered += 1
    if not covered and not corridors:
        return classification, (), stats
    reach = tn.max_ramp_length_m + 2 * (tn.wall_gap_m + tn.wall_band_width_m)
    mouth_list = mouths(covered, list(airport.osm_ways), law, reach) if covered else []
    # THE PRECEDENCE PER MOUTH (05n-3, ``tunnel.object.source_precedence``):
    # an OSM bore mouth inside an object corridor's footprint is the
    # object's — its OSM ramp is not built; a mouth outside every object
    # keeps its ramp exactly as before.  A bore covered at both mouths is
    # replaced; one covered at one end ships an object ramp there and an
    # OSM ramp at the other.
    replaced_ways: dict[str, list[int]] = {}
    if corridors and tn.object.source_precedence[0] == "object":
        tol = tn.wall_gap_m + tn.wall_band_width_m + tn.object.end_cap_open_m
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
    stats.object_corridors = len(corridors)

    # what a ramp may not cross
    runway_u = unary_union([p for p, c in zip(polys, cells) if c.role in RUNWAY_FAMILY]) \
        if any(c.role in RUNWAY_FAMILY for c in cells) else None
    pads = [(p, c.ref) for p, c in zip(polys, cells) if c.role == "building"]
    pad_tree = STRtree([p for p, _r in pads]) if pads else None
    strip: list[Polygon] = []
    for p, c in zip(polys, cells):
        if c.role in RUNWAY_FAMILY:
            hw = zone2_half_width_m(law, "runway", c.code_number, c.code_letter)
            if hw:
                strip.append(p.buffer(hw, **_MITRE))
    strip_u = unary_union(strip) if strip else None
    bridges = [w for w in airport.osm_ways if is_bridge(w) and len(w.points) >= 2]
    bridge_lines = [LineString(w.points) for w in bridges]
    bridge_tree = STRtree(bridge_lines) if bridge_lines else None

    spacing = law.tables.emit.chords.station_spacing_m
    gap, bw = tn.wall_gap_m, tn.wall_band_width_m
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

        def axis_fn(s: float, _ln=axis_ln) -> XY:
            p = _ln.interpolate(min(s, _ln.length))
            return (p.x, p.y)

        # THE MOUTH DATUM is the MOUTH WALL NODE's DEM − bore_datum_m
        # (09-03b): the end cap's centre, gap + half the band in front of
        # the mouth line — not the axis point's sample (measured LEMD
        # -15327+-5980: a cutting whose cap stands 2 m above the axis
        # sample; the ramp planned from the axis sample was 0.2 % over cap).
        # An OBJECT corridor's datum is ground(mouth) − plate height
        # (05n-1, ``mouth_depth = "plate"``), read by the corridor reader.
        cap_c = (mouth[0] + inward[0] * (gap + bw / 2), mouth[1] + inward[1] * (gap + bw / 2))
        mouth_dem = _dem(airport, cap_c) if c is None else c.mouth_dem_z
        if math.isnan(mouth_dem):
            stats.refused.append(f"{tid}: no DEM at the mouth")
            continue
        mouth_z = c.floor_z if c is not None else mouth_dem - tn.bore_datum_m
        # decks across the corridor (a first pass over the full reach)
        deck_ivals = _deck_intervals(axis_ln, half + gap + bw, bridges, bridge_lines,
                                     bridge_tree, law)
        obj_ivals = _object_deck_intervals(axis_ln, half + gap + bw, odecks)
        if obj_ivals:
            # the object law governs where an object bridge stands: a
            # mapped bridge way over it mints no terrain deck (08-30d)
            ou = unary_union([dp for _o, _s0, _s1, dp, _z in obj_ivals])
            deck_ivals = [d for d in deck_ivals if not d[3].intersects(ou)]
        design_grade = g.design_grade if c is not None else tn.ramp_max_grade
        if c is not None and g.climbs:
            # THE RAMP INSIDE THE WALLS (05n-1): the climb starts AT the
            # mouth; it tops at the wall end when the depth fits there at
            # the law — along the axis AND over the ring pairs' direct
            # distance (the census prices chords) — else it continues
            # beyond at ramp_max_grade along the approach (decks inside
            # the walls are not read: the walls are the object's)
            deck_ivals = [d for d in deck_ivals if d[1] >= g.hull_s]
            obj_ivals = [d for d in obj_ivals if d[1] >= g.hull_s]
            e = axis_fn(g.hull_s)
            chord = math.hypot(e[0] - mouth[0], e[1] - mouth[1]) - 2.0 * half
            fits = (g.hull_s * tn.ramp_max_grade >= c.plate_y - 1e-9
                    and chord * tn.ramp_max_grade >= c.plate_y - 1e-9)
            if fits:
                deck_ivals, obj_ivals = [], []
            else:
                # the climb beyond the walls is planned first WITHOUT decks:
                # a deck standing beyond where the ramp already meets the
                # DEM is not over the ramp at all (the axis past the walls
                # is an extension, not a mapped road — OTHH tunnel_sw: a
                # bridge 400 m out pushed the climb past the reach)
                design_grade = tn.ramp_max_grade
                s_free, _ss = _ramp_top(airport, law, axis_fn, mouth_z, 0.0, spacing, half)
                if s_free is not None:
                    deck_ivals = [d for d in deck_ivals if d[1] <= s_free]
                    obj_ivals = [d for d in obj_ivals if d[1] <= s_free]
        climb_from = 0.0 if c is not None else 0.0
        climb_from = max([climb_from] + [s1 + gap for _w, s0, s1, _p in deck_ivals]
                         + [s1 + gap for _o, s0, s1, _p, _z in obj_ivals])
        if g.climbs and c is not None and fits:
            ss = [spacing * k for k in range(int(g.hull_s // spacing) + 1)]
            if g.hull_s - ss[-1] > 1e-6:
                ss.append(g.hull_s)
            s_top = g.hull_s
        elif g.climbs:
            if c is not None and c.far_closed:
                stats.refused.append(f"{tid}: the {tn.ramp_max_grade:.0%} climb cannot reach the "
                                     f"ground inside the walls ({c.plate_y:.2f} m over "
                                     f"{g.hull_s:.0f} m) and the far end is a wall")
                continue
            s_top, ss = _ramp_top(airport, law, axis_fn, mouth_z, climb_from, spacing, half)
            if s_top is None:
                if any(math.isnan(_dem(airport, axis_fn(s))) for s in ss):
                    stats.refused.append(f"{tid}: no DEM along the climb (the corridor leaves "
                                         f"the DEM / reaches water) within {ss[-1]:.0f} m")
                else:
                    ds = [_dem(airport, axis_fn(s)) for s in ss]
                    m = axis_fn(climb_from)
                    e = axis_fn(ss[-1])
                    stats.refused.append(f"{tid}: the {tn.ramp_max_grade:.0%} climb from "
                                         f"{mouth_z:.2f} at s {climb_from:.0f} does not reach the "
                                         f"DEM ({min(ds):.2f}..{max(ds):.2f}) within "
                                         f"{tn.max_ramp_length_m:.0f} m (axis {axis_ln.length:.0f} m, "
                                         f"chord at the end {math.hypot(e[0] - m[0], e[1] - m[1]):.0f} m, "
                                         f"half {half:.1f} m)")
                continue
            if c is not None and all(abs(s - g.hull_s) > 1e-6 for s in ss):
                # the station ON the wall end: the trench spans the walls
                ss = sorted(ss + [g.hull_s])
        else:
            # a trench flat at the mouth depth (two mouths, 05n-1 at each):
            # stations along the walls, the last one ON the far end line
            ss = [spacing * k for k in range(int(g.hull_s // spacing) + 1)]
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
        ss = [s for s in ss if s <= s_top + 1e-9]
        beyond = _beyond(axis_fn, g.hull_s, reach + width) if c is not None and g.climbs else None
        while True:
            geom = geometry(axis_fn, ss, half, gap, bw, inward, grid, g.capped, g.far_capped,
                            g.half_fn, g.bw_fn, g.cap_bw, g.far_bw)
            if geom is None:
                stats.refused.append(f"{tid}: the approach bends tighter than the corridor "
                                     f"(ramp or wall ring self-intersects)")
                break
            probe = geom.outer if beyond is None else geom.outer.intersection(beyond)
            hit = _pad_hit(probe, pads, pad_tree, gap) if not probe.is_empty else None
            if hit is None:
                break
            clipped_by = hit
            top_pinned = False
            if len(ss) <= 2:
                stats.refused.append(f"{tid}: the mouth stands against building pad {hit}")
                geom = None
                break
            ss = ss[:-1]
            s_top = ss[-1]
        if geom is None:
            continue
        axis, nrm, left, right = geom.axis, geom.normals, geom.left, geom.right
        ramp, wall, outer, cap_in, cap_out = geom.ramp, geom.wall, geom.outer, geom.cap_in, geom.cap_out
        if c is not None and not g.capped:
            # an OPEN mouth (the bore continues under the covering ground):
            # the gap strip beyond the mouth line cuts that ground back, so
            # the mouth edge shares no vertex with it (09-01c/e)
            a, b = left[0], right[0]
            strip_m = LineString([a, b]).buffer(gap + grid, cap_style="flat", **_MITRE)
            outer = unary_union([outer, strip_m])
            if outer.geom_type != "Polygon":
                outer = outer.convex_hull
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
        decks: list[Deck] = []
        deck_polys: list[Polygon] = []
        for w, s0, s1, dp in deck_ivals:
            if s0 > s_top:
                continue
            dpoly = dp.intersection(outer)
            if dpoly.is_empty or dpoly.area < 1.0:
                continue
            dref = f"bridge_deck:{w.id}"
            decks.append(Deck(dref, w.id, s0, s1, tuple(dpoly.exterior.coords)[:-1]))
            deck_polys.append(dpoly)
            stats.decks += 1
        # OBJECT BRIDGES: recorded, never severing (the terrain stays open
        # under the object; the deck-top clearance is the generator's row)
        for oid, s0, s1, dp, top_z in obj_ivals:
            if s0 > s_top:
                continue
            dpoly = dp.intersection(outer)
            if dpoly.is_empty or dpoly.area < 1.0:
                continue
            if dpoly.geom_type != "Polygon":
                dpoly = max(_parts(dpoly), key=lambda g: g.area, default=None)
                if dpoly is None:
                    continue
            decks.append(Deck(f"object_deck:{oid}", 0, s0, s1,
                              tuple(dpoly.exterior.coords)[:-1], "deck_top", top_z))
            stats.object_decks += 1
        # the ramp's ref is EXACTLY the oracle's population key too
        ramp_refs: list[str] = []
        ramp_geom = ramp
        wall_geom = wall
        if deck_polys:
            du = unary_union(deck_polys)
            ramp_geom = ramp.difference(du.buffer(gap + grid, **_MITRE))
            wall_geom = wall.difference(du)
        ramp_parts = _parts(ramp_geom)
        for part in ramp_parts:
            ramp_refs.append("tunnel_ramp")
            new_cells.append(("tunnel_ramp", "tunnel_ramp", part, tid))
        wall_ref = "tunnel_wall"
        for part in _parts(wall_geom):
            new_cells.append(("retaining_wall", wall_ref, part, tid))
        for d, dp in zip(decks, deck_polys):
            for k, part in enumerate(_parts(dp)):
                new_cells.append(("service_road", d.ref + (f"#{k}" if k else ""), part, tid))
        cap_mid = [((ci[0] + co[0]) / 2, (ci[1] + co[1]) / 2) for ci, co in zip(cap_in, cap_out)]
        far_mid = [((ci[0] + co[0]) / 2, (ci[1] + co[1]) / 2)
                   for ci, co in zip(geom.far_in, geom.far_out)]
        # the band's centreline: the middle of its inner and outer edges
        # (an object's bands vary in width by station)
        wall_path = ([((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                      for a, b in zip(reversed(geom.left_in), reversed(geom.left_out))]
                     + cap_mid
                     + [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                        for a, b in zip(geom.right_in, geom.right_out)] + far_mid)
        if far_mid and cap_mid:
            wall_path.append(wall_path[0])          # the O: a closed centreline
        notes = []
        if len(members) > 1:
            notes.append(f"dual carriageway of {len(members)} bores (2026-08-31h)")
        for d in decks:
            if d.datum == "deck_top":
                notes.append(f"object bridge {d.ref} deck top {d.z:.2f} over s {d.s0:.0f}-{d.s1:.0f}")
        if clipped_by:
            notes.append(f"clipped at building pad {clipped_by} at {s_top:.1f} m "
                         f"(08-07 ruling 3)")
        extra: dict = {}
        if c is not None:
            outside = trench_outside_m(ramp_parts, c)
            expect = _reseat_expect(c, mouth_z, design_grade, s_top, airport)
            notes.append(f"tunnel wall object {c.resource} (2026-09-05n): floor at the mouth "
                         f"{mouth_z:.2f} = ground {mouth_dem:.2f} − plate {c.plate_y:.2f}, ends "
                         f"{c.ends}, mouth by {c.mouth_kind}")
            notes.extend(c.notes)
            extra = dict(source="object", crest=tn.crest, crest_z=mouth_dem,
                         resource=c.resource, objects=tuple(c.objects), depth_m=c.plate_y,
                         hull_length_m=c.length_m, hull_width_m=c.width_m, ends=c.ends,
                         replaced_ways=tuple(replaced_ways.get(c.id, ())),
                         capped=g.capped, far_capped=g.far_capped,
                         wall_length_m=c.length_m, mouth_kind=c.mouth_kind,
                         ground_kind=c.ground_kind, reseat_expect_m=expect,
                         trench_outside_max_m=outside)
        tunnels.append(Tunnel(tid, tuple(i for m in members for i in m.ways),
                              tuple(axis), half, mouth_dem, mouth_z, s_top, climb_from,
                              tuple(ramp_refs), wall_ref, tuple(wall_path), tuple(decks),
                              tuple(notes), top_pinned, clipped_by,
                              (cap_mid[0], cap_mid[2]) if cap_mid else None,
                              cap_mid[1] if cap_mid else None, design_grade=design_grade,
                              **extra))
        if clipped_by:
            # THE PORTAL FACE AT THE PAD EDGE (08-07 ruling 3): the clipped
            # ramp's top edge stands off the ground beyond it by the gap
            # too — an unowned strip the mesh triangulates as the face
            dx, dy = right[-1][0] - left[-1][0], right[-1][1] - left[-1][1]
            L = math.hypot(dx, dy) or 1.0
            ext = gap + 3 * grid + bw + grid
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
            # (08-26: the trench is senior to the pad authority)
            hull_knives.append(outer if beyond is None else outer.difference(beyond))
    # TWO STRUCTURES MAY NOT OVERLAP: parallel mouths beyond 31h's test
    # (a diverging separation profile, a crossing approach) would be
    # polygonised into crumbs; the narrower one is refused loudly
    keep = [True] * len(tunnels)
    for i in range(len(tunnels)):
        for j in range(i + 1, len(tunnels)):
            if not (keep[i] and keep[j]):
                continue
            if footprints[i].intersects(footprints[j]) and \
                    footprints[i].intersection(footprints[j]).area > 1.0:
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
    for role, ref, part, _tid in new_cells:
        out_cells.append(Cell(len(out_cells), role, ref, tuple(part.exterior.coords)[:-1],
                              tuple(tuple(h.coords)[:-1] for h in part.interiors),
                              None, None, role_side(law, role), "structure", {}))
    out_cells = [_dc.replace(c, id=i) for i, c in enumerate(out_cells)]
    cl = _dc.replace(classification, cells=tuple(out_cells),
                     keepouts=tuple(tuple(k.exterior.coords)[:-1] for k in keepouts),
                     stats={**dict(classification.stats), "tunnels": stats.tunnels,
                            "tunnel_decks": stats.decks, "tunnel_object_decks": stats.object_decks,
                            "tunnel_cells_cut": stats.cells_cut,
                            "tunnels_refused": len(stats.refused),
                            "tunnel_object_corridors": stats.object_corridors,
                            "bores_replaced_by_object": stats.bores_replaced_by_object,
                            "mouths_replaced_by_object": stats.mouths_replaced_by_object})
    return cl, tuple(tunnels), stats


def _reseat_expect(c, mouth_z: float, grade: float, s_top: float, airport: Airport
                   ) -> tuple[float, ...]:
    """The re-seat the DESIGN implies for the corridor's placement(s)
    (05n-4): ``ground(anchor) − (floor at the anchor's station + agl +
    plate)`` — the post-mesh seat measures the real one."""
    ln = LineString(c.axis)
    s = ln.project(Point(c.anchor_xy))
    floor = min(mouth_z + grade * min(s, s_top), c.anchor_dem_z) if grade > 0 else mouth_z
    return (round(c.anchor_dem_z - (floor + c.agl_m + c.plate_y), 3),)


def _beyond(axis_fn, s_end: float, length: float) -> Polygon:
    """The half-plane strip BEYOND the axis station ``s_end`` (an object
    corridor's open end line): ``length`` long along the axis, as wide."""
    a, b = axis_fn(max(0.0, s_end - 1.0)), axis_fn(s_end)
    ux, uy = unit(a, b)
    nx, ny = -uy, ux
    e = axis_fn(s_end)
    return Polygon([(e[0] + nx * length, e[1] + ny * length),
                    (e[0] - nx * length, e[1] - ny * length),
                    (e[0] - nx * length + ux * length, e[1] - ny * length + uy * length),
                    (e[0] + nx * length + ux * length, e[1] + ny * length + uy * length)])


def _owner_kept(cell: tuple, tunnels: list[Tunnel], keep: list[bool]) -> bool:
    ids = {t.id for t, k in zip(tunnels, keep) if k}
    return cell[3] in ids


def _pad_hit(outer: Polygon, pads: list[tuple[Polygon, str]], tree: STRtree | None,
             gap: float) -> str | None:
    """The ref of a building pad the footprint touches (closer than the
    gap), or ``None``."""
    if tree is None:
        return None
    for j in tree.query(outer.buffer(gap), predicate="intersects"):
        p, ref = pads[int(j)]
        if p.distance(outer) < gap - 1e-9:
            return ref
    return None


def ramp_targets(tunnels: _t.Sequence[Tunnel], law: Law, faces: dict, edges: list,
                 vxy: list[XY], dem_z: _t.Sequence[float]) -> dict[int, float]:
    """THE RAMP'S OBJECTIVE TARGET IS ITS OWN DESIGN, not the DEM: vertex
    id -> the designed profile value ``clamp(DEM, mouth_z − g·Δs, mouth_z
    + g·Δs)`` (``Δs`` from where the climb starts; ``g`` the tunnel's
    ``design_grade`` — ``min(ramp_max_grade, depth / wall length)`` for an
    object corridor, 05n-1 — else ``ramp_max_grade``) for every
    ``tunnel_ramp`` ring vertex.  With the DEM as target the ramp's pull levered the
    apron sharing its end cap 0.49 m up through the mouth datum
    (measured on the M4 twin) — groundside pulling airside; at its
    design the ramp has nothing to pull with."""
    if not tunnels:
        return {}
    g = law.tables.structures.tunnel.ramp_max_grade
    axes = {tn.id: LineString(tn.axis) for tn in tunnels}
    out: dict[int, float] = {}
    for fid, face in faces.items():
        if face.role != "tunnel_ramp":
            continue
        ids = {edges[e].a for e in face.ring} | {edges[e].b for e in face.ring}
        cx = sum(vxy[v][0] for v in ids) / len(ids)
        cy = sum(vxy[v][1] for v in ids) / len(ids)
        tid = min(axes, key=lambda k: axes[k].distance(Point(cx, cy)))
        tn = tunnels[[t.id for t in tunnels].index(tid)]
        gt = tn.design_grade if tn.design_grade > 0.0 else g
        for v in ids:
            s = axes[tid].project(Point(vxy[v]))
            reach = gt * max(0.0, s - tn.climb_from_s)
            d = float(dem_z[v])
            if math.isnan(d):
                continue
            out[v] = max(tn.mouth_z - reach, min(tn.mouth_z + reach, d))
    return out


def _parts(geom) -> list[Polygon]:
    if geom is None or geom.is_empty:
        return []
    return [g for g in shapely.get_parts(geom) if g.geom_type == "Polygon" and g.area > 1e-6]


def _deck_intervals(axis_ln: LineString, half_outer: float, bridges: list[OsmWay],
                    lines: list[LineString], tree: STRtree | None, law: Law
                    ) -> list[tuple[OsmWay, float, float, Polygon]]:
    """``(way, s0, s1, deck polygon)`` per mapped bridge way crossing the
    corridor (at ≥ 30° to the axis), ordered by ``s0``."""
    if tree is None:
        return []
    corridor = axis_ln.buffer(half_outer, cap_style="flat", **_MITRE)
    out = []
    for j in tree.query(corridor, predicate="intersects"):
        w, ln = bridges[int(j)], lines[int(j)]
        x = ln.intersection(axis_ln)
        if x.is_empty:
            continue
        pts = [g for g in shapely.get_parts(x) if g.geom_type == "Point"]
        if not pts:
            continue
        s_mid = axis_ln.project(pts[0])
        # crossing angle
        a = axis_ln.interpolate(max(0.0, s_mid - 1.0))
        b = axis_ln.interpolate(min(axis_ln.length, s_mid + 1.0))
        ux, uy = b.x - a.x, b.y - a.y
        sb = ln.project(pts[0])
        c = ln.interpolate(max(0.0, sb - 1.0))
        d = ln.interpolate(min(ln.length, sb + 1.0))
        vx, vy = d.x - c.x, d.y - c.y
        den = (math.hypot(ux, uy) * math.hypot(vx, vy)) or 1.0
        ang = math.degrees(math.acos(max(-1.0, min(1.0, abs(ux * vx + uy * vy) / den))))
        if ang < _DECK_MIN_ANGLE_DEG:
            continue
        wd = carriageway_width_m(w.tags, law)
        dpoly = ln.intersection(corridor.buffer(2.0)).buffer(wd / 2, cap_style="flat", **_MITRE)
        if dpoly.is_empty:
            continue
        # the covered stretch along the axis
        seg = axis_ln.intersection(dpoly)
        if seg.is_empty:
            continue
        s_vals = []
        for g in shapely.get_parts(seg):
            for q in g.coords:
                s_vals.append(axis_ln.project(Point(q)))
        out.append((w, min(s_vals), max(s_vals), dpoly))
    out.sort(key=lambda t: t[1])
    return out


def _object_deck_intervals(axis_ln: LineString, half_outer: float,
                           odecks: list[tuple[str, Polygon, float]]
                           ) -> list[tuple[str, float, float, Polygon, float]]:
    """``(object id, s0, s1, deck footprint, deck top)`` per hard-deck
    object footprint crossing the corridor, ordered by ``s0``."""
    if not odecks:
        return []
    corridor = axis_ln.buffer(half_outer, cap_style="flat", **_MITRE)
    out = []
    for oid, dp, top in odecks:
        if not dp.intersects(corridor):
            continue
        seg = axis_ln.intersection(dp)
        if seg.is_empty:
            continue
        s_vals = [axis_ln.project(Point(q)) for g in shapely.get_parts(seg) for q in g.coords]
        if not s_vals:
            continue
        out.append((oid, min(s_vals), max(s_vals), dp, top))
    out.sort(key=lambda t: t[1])
    return out
