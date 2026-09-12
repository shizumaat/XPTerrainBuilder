"""THE BODIES OF ONE PLACEMENT (spec ``object-placement-spec.md`` §14 /
§14a / §16 / §16a / §16b; owner RULINGS 2026-09-11ai/aj/ap).

Where ``placement_cut`` divides geometry, this module DECIDES what a
member's raw bodies are: the segment cut's stations, §16b (1)'s prior
terrain cut on a body's own written triangles, §14a (1)'s basin arcs,
§14 (2)'s whole basin, §16 (2)'s parts-by-terrain groups and the
ε-contact triangle groups — each already CLASSED and ANCHORED (§6,
``_whole_body``).

It lives next door to ``placement_cut`` for the 1,000-line law only; the
two are one reading and every caller (and every twin) reads these names
as ``placement_cut``'s, which re-exports them.

NO LAW CONSTANT LIVES HERE.
"""
from __future__ import annotations

import typing as _t

from ..model.rebake import Member, Part, Unit
from . import anchor_rule as _ar
from . import basin_ring as _br
from . import placement_carrier as _pc
from .placement_carrier import is_elevated
from .placement_cut import (_basin_floor_member, _bodies_of,
                            _cut_parts_by_terrain, _floor_member,
                            _geom_ground, _geom_span, _LineCutter,
                            _part_zero, _plan_span_m, _rim_of,
                            segment_anchor)

__all__ = ["_Raw", "_raw_bodies", "_whole_body"]


#: one member's raw bodies before coarsening: ``(parts, class, anchor,
#: feet, elevated, segment triangles, geometry samples, terrain ground)``
#: — the last two are §16b's: what the body WRITES, and the design
#: surface under it (its terrain group's own height).
_Raw = _t.Tuple[list, str, _ar.Anchor, tuple, bool, tuple, tuple,
                "float | None"]

def _raw_bodies(m: Member, u: Unit, edges: _t.Sequence[tuple[int, int]],
                surface: _ar.Surface, pads: _t.Sequence[_ar.PadRing],
                rims: _t.Sequence[_ar.RimRing], counts: dict[str, int],
                *, split_tol_m: float, elevated_base_m: float,
                line_segment_m: float, line_stations_max: int,
                line_ratio: float, line_max_h: float,
                foot_band_m: float, coarsen_reach_m: float = 0.0,
                cutter: "_LineCutter | None" = None
                ) -> list[_Raw]:
    """One member's bodies, classed and anchored — the per-placement half,
    unchanged by §14 except that the basin's rim anchor is now wired
    (``anchor_rule``) and the segment cut still never touches an elevated
    body (§13 (1)).

    §16a (1): A CARRIED BODY IS NEVER CUT BY THE GROUND UNDER ITSELF.
    The body is classed and anchored WHOLE first; one that comes out
    ELEVATED or FOOTLESS leaves this function in one piece, and
    ``placement_plan``'s pass 3 cuts it against its CARRIER's terrain
    groups instead.  §16 (2)'s part and triangle cuts stay exactly as
    they were for a body that stands on the ground."""
    groups = _bodies_of(m, edges)
    pid_of = {p.pid: p for p in m.parts}
    # ONE cutter per member: it holds the parsed OBJ8 and its components,
    # and §16a (1)'s carrier cut (pass 3) reads the same geometry.  Two
    # cutters meant two parses — 618 of OTHH's members parsed twice, 42 s
    # of ``solid_components`` in the plan stage, measured.
    if cutter is None:
        cutter = _LineCutter(m, line_segment_m, line_stations_max, foot_band_m,
                             line_ratio, line_max_h, u.anchor[0], u.anchor[1])
    raw: list[_Raw] = []
    # §14a (2): the mark is applied to whatever the group's branch
    # appended, at the top of the next turn — the branches all ``continue``
    floor_mark, n0 = "", 0
    for g in groups:
        if floor_mark:
            for _t_ in range(n0, len(raw)):
                raw[_t_] = _floor_member(raw[_t_], floor_mark)
            floor_mark = ""
        n0 = len(raw)
        parts = [pid_of[q] for q in g]
        base_min = min(p.base_y for p in parts)
        # §13 (1): the line-segment cut NEVER applies to an elevated body
        # — a 65 m tower part that happens to read line-shaped (LEMD's
        # `-ZNTWR`) is not a fence
        pieces = ([] if (elevated_base_m > 0.0 and base_min > elevated_base_m)
                  else cutter.segments(parts))
        if pieces:
            # 11f (2): the body IS the line, cut into its stations
            counts["line_bodies_segmented"] = \
                counts.get("line_bodies_segmented", 0) + 1
            counts["line_segments"] = counts.get("line_segments", 0) + len(pieces)
            # §16b (1) AND THE SEGMENT: measured and REPORTED (§16b
            # MEASURED).  Cutting each station again by the ground under
            # it took LEMD's fence and grass files 2,227 -> 7,722 for a
            # class the eye does not read — §10's station is already a
            # terrain reading every 100 m, at its own mid-foot — so the
            # station law stands and the segments' residual span is
            # reported by class instead.
            for si, (tris, feet) in enumerate(pieces):
                sa = segment_anchor(feet, surface, si, len(pieces))
                spts, _sp, sg = _geom_ground(cutter, parts, tris, surface)
                raw.append((parts, _ar.LINE_SEGMENT, sa, feet,
                            is_elevated(min(f[2] for f in feet), sa,
                                        elevated_base_m), tris, spts, sg))
            continue
        # §16 (2): EVERY BODY IS RE-CUT BY TERRAIN — the ε-contact body is
        # asked the same question §15 (2) asks a plan-overlap bond, one
        # level down, on its own parts.  A BASIN body is exempt for §14
        # (2)'s reason (the pit was cut TO the object, so its floor plate
        # standing 7 m under its rim is the authoring, not two bodies).
        # §14a: THE BASIN BODY FOLLOWS ITS RING.  Every body standing in
        # a basin ring is asked whether it FORMS the pit or merely STANDS
        # IN it (§14a (2)) — not only the ones 10ba's ``base_y < 0`` test
        # classes ``basin``, because the slab authored AT the rim inside
        # the pit is exactly the body that test misses and §14 (3)'s plan
        # overlap then binds into the pit's rim-anchored group (measured:
        # ``Ground-FSX-LEMD13``'s 5 x 18 m slab, the loose white one in
        # the garden).  A floor member reads NO ring from here on: the
        # class, the anchor and every cut below take the generic rule,
        # and its bind key holds it out of the pit's group.
        lowest0 = min(parts, key=lambda p: p.base_y)
        ring0 = _ar.rim_of(rims, lowest0.lat, lowest0.lon)
        is_basin = ring0 is not None and lowest0.base_y < 0.0
        rim0 = ring0 if is_basin else None
        arcs: tuple = ()
        if (ring0 is not None and _br.is_basin_ring(ring0.ref) and ring0.z
                and _basin_floor_member(cutter, parts, ring0, split_tol_m)):
            counts["basin_floor_members"] = \
                counts.get("basin_floor_members", 0) + 1
            floor_mark = ring0.ref
            is_basin = False
            rim0 = None
        elif is_basin and _br.is_basin_ring(rim0.ref) and rim0.z:
            arcs = _br.arcs_of(rim0.z, rim0.ring, split_tol_m,
                               line_stations_max)
        body_rims = rims if is_basin else ()
        # §16a (1): IS THIS BODY CARRIED?  Asked of the WHOLE body,
        # before any terrain cut — because a carried body's pieces are
        # its CARRIER's terrain groups, not its own ground's, and the
        # ground under a roof is exactly the reading §16a deletes.
        # §16b (1)/(4): WHAT THE FILE WILL CONTAIN.  A placement the plan
        # reads as ONE body is written as the WHOLE object (the writer
        # gives every triangle no body owns to the nearest one), so for
        # such a member the body's own written geometry is the file's own
        # triangles — not the parts the partition happened to record.
        own_tris = (cutter.all_tris() if len(groups) == 1 else ())
        whole0 = _whole_body(parts, m, u, surface, pads, body_rims, split_tol_m)
        if is_elevated(base_min, whole0[1], elevated_base_m) or whole0[3]:
            # §16b (1): THE TERRAIN CUT IS PRIOR AND UNIVERSAL, and it is
            # read on the body's OWN WRITTEN TRIANGLES.  §16a (1) left a
            # carried body whole and cut it against its CARRIER — which
            # is right WITHIN a terrain group and wrong across one: a
            # roof-panel resource authored as one welded component over
            # 1 x 2 km of terminal (`green-TEJ3`) then rode ONE carrier
            # at ONE zero and read +10.74 / +16.22 m at the owner's two
            # sites (11ap).  So the body is first divided by the ground
            # under its own geometry; §16a (1)'s carrier cut then runs
            # inside each piece (``placement_plan._carrier_pieces``).
            # A BASIN body is exempt for §14 (2)'s reason.
            cpieces = ([] if (is_basin or split_tol_m <= 0.0
                              or _geom_span(cutter, parts, own_tris,
                                            surface)[1] <= split_tol_m)
                       else cutter.terrain_groups(parts, surface, split_tol_m,
                                                  line_stations_max,
                                                  by_ground=True,
                                                  tris_in=own_tris))
            if cpieces:
                counts["carried_bodies_cut_by_own_ground"] = \
                    counts.get("carried_bodies_cut_by_own_ground", 0) + 1
                counts["carried_own_ground_pieces"] = \
                    counts.get("carried_own_ground_pieces", 0) + len(cpieces)
                for tris, tpts in cpieces:
                    cpts, _cs, cg = _geom_ground(cutter, parts, tris, surface)
                    # ``tpts`` are the piece's own lowest vertices: its
                    # PLAN EXTENT (``box_of``) and nothing else — an
                    # elevated body's vertices are never feet (§13 (3)),
                    # and every reader excludes them by the flag below.
                    raw.append((list(parts), whole0[0], whole0[1], tuple(tpts),
                                True, tris, cpts, cg))
                continue
            counts["carried_bodies_uncut"] = \
                counts.get("carried_bodies_uncut", 0) + 1
            wpts, _ws, wg = _geom_ground(cutter, parts, own_tris, surface)
            raw.append((list(parts), whole0[0], whole0[1], whole0[2], True,
                        (), wpts, wg))
            continue
        # §14a (1): THE WALL IS CUT BY THE RING'S STATIONS.  The body's
        # WALL BAND — what stands at the ring — is cut into one piece per
        # ARC, each anchored at its arc's rim point and so at the apron's
        # own level there; the INTERIOR remainder (arc -1) keeps §14 (2)'s
        # single rim point, because the trench floor under it is one level
        # (§24 (2)) and a floor plate written per arc would step where the
        # terrain beneath it does not.
        arc_pieces, wall_arcs = (
            cutter.ring_arcs(parts, rim0, arcs, _br.WALL_BAND_M)
            if arcs and len(arcs) > 1 else ([], ()))
        for _k in wall_arcs:
            # §14a (4): this arc HAS a wall, whether or not a piece
            # survives the coarsening — the bar reads it either way
            counts[_br.wall_arc_key(rim0.ref, _k)] = 1
        if arc_pieces:
            counts["basin_bodies_arc_cut"] = \
                counts.get("basin_bodies_arc_cut", 0) + 1
            counts["basin_arc_pieces"] = \
                counts.get("basin_arc_pieces", 0) + len(arc_pieces)
            for k, tris, feet in arc_pieces:
                aa = _br.arc_anchor(k, arcs, whole0[1], rim0, surface)
                # §16b (4): the census reads the WRITTEN geometry — an arc
                # piece publishes its own samples like every other piece
                apts, _as, ag = _geom_ground(cutter, parts, tris, surface)
                raw.append((list(parts), _ar.BASIN, aa, feet, False, tris,
                            apts, ag))
            continue
        pieces_p = ([list(parts)] if is_basin
                    else _cut_parts_by_terrain(parts, surface, split_tol_m,
                                               coarsen_reach_m))
        if len(pieces_p) > 1:
            counts["bodies_re_cut_by_terrain"] = \
                counts.get("bodies_re_cut_by_terrain", 0) + 1
            counts["terrain_body_groups"] = \
                counts.get("terrain_body_groups", 0) + len(pieces_p)
        for parts in pieces_p:
            base_min = min(p.base_y for p in parts)
            lowest = min(parts, key=lambda p: p.base_y)
            # §6 on THIS piece, read at most ONCE: the gate below needs
            # the anchor it would take, and so does the fallback at the
            # bottom of the loop — but a piece the cuts divide needs
            # neither, and asking anyway put 68,721 anchor readings into
            # OTHH's stage.
            whole = whole0 if len(pieces_p) == 1 else None
            # §16 (2) BY FOOT (11ak (2)): IS THIS BODY MIS-ANCHORED ON
            # ITS OWN FEET?  Neither cut below can see that class — the
            # ground under the body barely moves and its FEET are
            # authored over metres of relief, so the anchor rule drops
            # the whole body to its low-side foot.  That is the body
            # §16a (2) refuses as a carrier (LEMD 117), and a refused
            # carrier is a body the roofs over it cannot ride.  The test
            # is the refusal's own (:func:`anchor_ground_off`), so one
            # reading decides both.
            # The test is §16a (2)'s OWN — the median of what this
            # body's feet say its zero is, against the zero its anchor
            # takes — so one reading decides both the cut and the
            # refusal.  A cheaper stand-in was tried and REFUTED: gated
            # on the feet's AUTHORED span alone the cut fired 195 times
            # instead of 615 and LEMD's refusal set came back at 100
            # rather than 21, because a body can be off its own feet
            # over ground that moves under it as well as over relief it
            # was authored with.
            off = None
            if not is_basin and any(p.feet for p in parts):
                if whole is None:
                    whole = _whole_body(parts, m, u, surface, pads, body_rims,
                                        split_tol_m)
                off = _pc.anchor_ground_off(whole[1], whole[2], surface)
            foot_pieces = (cutter.foot_groups(parts, surface, split_tol_m,
                                              line_stations_max)
                           if (off is not None and split_tol_m > 0.0
                               and off > split_tol_m) else [])
            if foot_pieces:
                counts["bodies_re_cut_by_foot"] = \
                    counts.get("bodies_re_cut_by_foot", 0) + 1
                counts["terrain_foot_groups"] = \
                    counts.get("terrain_foot_groups", 0) + len(foot_pieces)
            # §16 (2) BY TRIANGLE: the part cut has nothing to divide in a
            # body authored as ONE welded component (LEMD's `green-TEJ3`,
            # a roof-panel resource over 1 x 2 km).  Where the ground
            # under the body's own parts still spans more than the
            # tolerance, the TRIANGLES are grouped by the ground under
            # them.  The pre-test is five samples; the cut itself only
            # runs on a body that fails it.
            # §16b (1): the pre-test is READ ON THE WRITTEN TRIANGLES
            # (:func:`_geom_span`), never on the parts' hull box — the
            # same reading the census makes, so a body the census calls
            # wider than its terrain group is a body this cut was asked
            # to divide.
            span = (0.0 if foot_pieces or is_basin or split_tol_m <= 0.0
                    else _geom_span(cutter, parts,
                                    own_tris if len(pieces_p) == 1 else (),
                                    surface)[1])
            # THE KEY IS THE INTENDED ZERO, not the raw ground — measured
            # and REPORTED (§16b MEASURED): read by ground this cut slices
            # a rigid footed solid wherever the terrain under it moves
            # 0.3 m (LEMD files 1,371 -> 5,891, a garage into 20 slices)
            # and STILL cannot reach the bar, because a body's atom is its
            # TRIANGLE and this pack authors slabs and ramps as four of
            # them spanning 6 m of fall.  A footed body reads its own
            # feet; the carried class §16b (1) names is cut by ground
            # above, where the body has no feet to read.
            # §16c (1): THE CUT READS THE SAME TRIANGLES THE PRE-TEST DID
            # — the body's OWN WRITTEN geometry (`own_tris`), not just
            # the components the plan's parts happen to name.  A member
            # the plan reads as ONE part is WRITTEN as the whole object
            # (§16b (1)), so a cut over the parts' components measured a
            # span it could not act on.
            tri_pieces = foot_pieces or (
                cutter.terrain_groups(parts, surface, split_tol_m,
                                      line_stations_max,
                                      tris_in=own_tris if len(pieces_p) == 1
                                      else ())
                if span > split_tol_m else [])
            if tri_pieces:
                if not foot_pieces:
                    counts["bodies_re_cut_by_triangle"] = \
                        counts.get("bodies_re_cut_by_triangle", 0) + 1
                    counts["terrain_triangle_groups"] = \
                        counts.get("terrain_triangle_groups", 0) + len(tri_pieces)
                for tris, tfeet in tri_pieces:
                    tlow = min(tfeet, key=lambda f: f[2])
                    tcls = _ar.classify_body(
                        skirted=m.skirted,
                        basin_member=False,
                        line=all(p.line for p in parts),
                        deck=m.deck_kind in ("flag", "signature"),
                        plate=m.plate_y is not None,
                        has_pad=_ar._pad_of(pads, tlow[0], tlow[1]) is not None)
                    tgeom = _ar.BodyGeometry(
                        ((tlow[0], tlow[1], tlow[2],
                          tuple((f[0], f[1], f[2]) for f in tfeet)),),
                        u.anchor[0], u.anchor[1])
                    ta = _ar.anchor_for(tcls, tgeom, surface, pads, body_rims,
                                        tol_m=split_tol_m)
                    # §16 (1): a triangle group of a body with no ground
                    # contact has none either (the VOR-marker class)
                    tfootless = (not any(p.feet for p in parts)
                                 and ta.body_class not in (_ar.BASIN,
                                                           _ar.PLATE_ONLY,
                                                           _ar.DECK))
                    tpts, _ts, tg = _geom_ground(cutter, parts, tris, surface)
                    raw.append((list(parts), ta.body_class, ta, tuple(tfeet),
                                is_elevated(tlow[2], ta, elevated_base_m)
                                or tfootless, tris, tpts, tg))
                continue
            if whole is None:
                whole = _whole_body(parts, m, u, surface, pads, body_rims,
                                    split_tol_m)
            cls, a, feet, footless = whole
            gpts, _gs, gg = _geom_ground(
                cutter, parts, own_tris if len(pieces_p) == 1 else (), surface)
            raw.append((list(parts), a.body_class, a, feet,
                        is_elevated(base_min, a, elevated_base_m) or footless,
                        (), gpts, gg))
    if floor_mark:
        for _t_ in range(n0, len(raw)):
            raw[_t_] = _floor_member(raw[_t_], floor_mark)
    return raw


def _whole_body(parts: _t.Sequence[Part], m: Member, u: Unit,
                surface: _ar.Surface, pads: _t.Sequence[_ar.PadRing],
                rims: _t.Sequence[_ar.RimRing], split_tol_m: float
                ) -> tuple[str, _ar.Anchor, tuple, bool]:
    """One set of parts CLASSED and ANCHORED as a body: ``(class, anchor,
    feet, footless)`` — §6's rule, read once.

    §16a (1) needs this answer BEFORE the terrain cut runs (a carried
    body is cut by its carrier, not by its own ground) and the cut's own
    pieces need it after, so it is one function rather than two readings
    of §6 in one file.

    §16 (1): A BODY WITH NO GROUND CONTACT AT ALL IS FOOTLESS.  The feet
    fallback gives a body with no part feet its parts' own positions so
    that it still has a box — read as FEET they would make a ground body
    out of geometry that never met the ground.  The resources §16 (1)
    admits are exactly that (no genuine solid, so the partition strips
    their feet), and one of them — a two-triangle VOR marker reaching
    50 m below its own zero — was offered to the carrier search as
    ground and read by the census as something to stand over.  The
    structure-seated classes are excluded: a plate, a deck and a basin
    member carry drape stations rather than feet, and another law
    governs their elevation (14.1 rule 4)."""
    lowest = min(parts, key=lambda p: p.base_y)
    cls = _ar.classify_body(
        skirted=m.skirted,
        basin_member=_rim_of(rims, lowest.lat, lowest.lon, lowest.base_y),
        line=all(p.line for p in parts),
        deck=m.deck_kind in ("flag", "signature"),
        plate=m.plate_y is not None,
        has_pad=_ar._pad_of(pads, lowest.lat, lowest.lon) is not None)
    geom = _ar.BodyGeometry(
        tuple((p.lat, p.lon, p.base_y,
               tuple((f[0], f[1], f[2]) for f in p.feet)) for p in parts),
        u.anchor[0], u.anchor[1])
    a = _ar.anchor_for(cls, geom, surface, pads, rims, tol_m=split_tol_m)
    feet = tuple((f[0], f[1], f[2]) for p in parts for f in p.feet) \
        or tuple((p.lat, p.lon, p.base_y) for p in parts)
    footless = (not any(p.feet for p in parts)
                and a.body_class not in (_ar.BASIN, _ar.PLATE_ONLY, _ar.DECK))
    return (cls, a, feet, footless)
