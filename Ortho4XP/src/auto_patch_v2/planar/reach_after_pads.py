"""AIRCRAFT REACHABILITY, READ AGAIN ONCE THE BUILDINGS STAND (#1302; owner
RULINGS 2026-10-19ag, 2026-10-27h).

19ag: "pavement aircraft can reach only through a passage too narrow to
manoeuvre is groundside", and a building divides when aircraft cannot get
around it.  ``classify/reachability`` reads it on the pavement pages, BEFORE
the building pads are cut out of them -- a page drawn under a terminal is
room there.  MEASURED LFPG T2: ``dsf:pol459`` (507,378 m2) runs from the
stands under the halls into the 43,482 m2 central corridor between 2E and
2F; read whole it is reachable, so the corridor stayed apron, solved at
103.2-104.1 m between lower levels held at 97.8 m.

HERE, after ``pad_cut.apron_cut_to_pads`` (the apron cut back to every pad
it carries), the same read (``reachability.unreachable_aprons``, the one
derivation) runs on each connected piece of every apron region the pads
cut apart: a piece whose room is all beyond, a lot by that read's own
test, with no startup on it, while another piece of the same page stays
reachable, is GROUNDSIDE -- ``<ref>#beyond<k>`` with the role
``open_default.unclassified_groundside_role`` names.  A page wholly beyond
is classify's to judge, as it judged it.  The pads join the
pavement for the "joined to the taxi network" read only (``bridge``): a
piece the pads enclose is pavement among buildings, never a detached
island.  The pieces aircraft reach keep the region whole.

THE UNIT JUDGED IS WHAT THE REACHABLE SWEEP LEAVES (#1935; owner RULINGS
2026-11-10a (5): "Those coordinates are on the groundside of the terminal,
on a road, there should not be taxiway or apron on that side of the
terminal").  A page piece is one polygon however thin the pavement that
joins it: MEASURED EFHK, ``dsf:pol201`` runs past the pier's land side as a
1-2 m strip round its south-east end, so the 25-30 m lot between the pier
and the kerb road (room aircraft never reach) was one piece with the stands
and stayed apron -- 395 of the terminal pad's 3,307 frontage contacts
stood on its land side, their ground down to 41.98 m against a pad at
47.63 m.
:func:`_beyond_passages` reads each piece the pads leave against the sweep of
the REACHABLE room (dilated back to the pavement edge, the weld included):
a part of it outside that sweep that holds unreachable room, carries no
startup and is a lot by the 19ag test is groundside, with the passages too
narrow to manoeuvre that lead to it up to their mouth -- an aircraft gets
into neither.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import Point
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..geom.parts import nonempty_polygon_parts
from ..law.tables import role_side

__all__ = ["BEYOND", "unreachable_after_pads"]

#: the ref spelling of an apron piece made groundside here
BEYOND = "#beyond"


def unreachable_after_pads(base_regions: list, pad_regions: _t.Sequence, law, airport,
                           *, level_b: float | None = None) -> "tuple[list, dict]":
    """``(base_regions, counts)``: the regions with every apron piece aircraft
    cannot reach once the pads stand made groundside (module docstring), and
    then -- where the airport's objects state a level B (``level_b``, the
    depth its lower level takes the covered pavement to) -- every covered
    part once the road bridges stand too (``planar/reach_under_covers``,
    #1717)."""
    out, counts = _after_pads(base_regions, pad_regions, law, airport)
    out, passed = _beyond_passages(out, law, airport, pad_regions)
    counts = {**counts, **passed}
    if level_b is None:
        return out, counts
    from .reach_under_covers import covered_beyond
    out, cov = covered_beyond(out, law, airport)
    return out, {**counts, **cov}


def _after_pads(base_regions: list, pad_regions: _t.Sequence, law, airport
                ) -> "tuple[list, dict]":
    """The pads' half of :func:`unreachable_after_pads`."""
    from ..classify.reachability import unreachable_aprons
    from ..classify.rules import load_rules
    cells = [(i, r) for i, r in enumerate(base_regions)
             if r.source == "cell" and r.polygon is not None and not r.polygon.is_empty]
    if not any(r.role == "apron" for _i, r in cells):
        return base_regions, {}
    entries: list[list] = []
    owner: list[int] = []
    for i, r in cells:
        if r.role == "apron":
            for q in nonempty_polygon_parts(r.polygon):
                entries.append([r.role, r.ref, q, r.code_letter, {}, r.role])
                owner.append(i)
        elif role_side(law, r.role) == "airside":
            entries.append([r.role, r.ref, r.polygon, r.code_letter, {}, r.role])
            owner.append(i)
    runways = [r.polygon for _i, r in cells if r.role in ("runway", "runway_crossing")]
    pads = unary_union([r.polygon for r in pad_regions
                        if r.polygon is not None and not r.polygon.is_empty])
    starts = [s.xy for s in getattr(airport, "startups", ()) or ()]
    rep = unreachable_aprons(entries, runways, law, load_rules(), starts, bridge=pads)
    if not rep.get("reach_demoted"):
        return base_regions, {"reach_after_pads": 0}
    kept: dict[int, list] = {}
    lost: dict[int, list] = {}
    for (role, _ref, q, _l, _e, _k), i in zip(entries, owner, strict=True):
        if base_regions[i].role != "apron":
            continue
        (kept if role == "apron" else lost).setdefault(i, []).append((role, q))
    # a page wholly beyond is classify's verdict to give
    # (``classify/reachability``), never this split's: only a page the pads
    # cut into pieces aircraft reach and pieces they do not is split
    reached = {str(base_regions[i].ref) for i in kept}
    out: list = []
    n, m2 = 0, 0.0
    for i, r in enumerate(base_regions):
        if i not in lost or str(r.ref) not in reached:
            out.append(r)
            continue
        if kept.get(i):
            out.append(_dc.replace(r, polygon=unary_union([q for _r, q in kept[i]])))
        for k, (role, q) in enumerate(lost[i], 1):
            out.append(_dc.replace(r, role=role, ref=f"{r.ref}{BEYOND}{k}", polygon=q,
                                   side=role_side(law, role)))
            n += 1
            m2 += float(q.area)
    return out, {"reach_after_pads": n, "reach_after_pads_m2": round(m2, 1)}


def _beyond_passages(regions: list, law, airport, pad_regions: _t.Sequence = ()
                    ) -> "tuple[list, dict]":
    """``(regions, counts)``: every apron part the REACHABLE sweep leaves that
    aircraft cannot use made groundside ``<ref>#beyond<k>`` (module
    docstring, #1935).  Only a page piece the sweep enters is read: a piece
    it never enters is the per-piece read's (:func:`_after_pads`) or
    classify's to judge.

    THE LAND SIDE STEPS DOWN FROM THE PAD (owner RULINGS 2026-11-10a (5):
    "there could be a step there allowing the apron and terminal to stay
    within grade law"; 10a (2) for a lot at a wall's foot).  A piece read
    groundside here stands back from every pad by the groundside set-back
    knife (``structures.building_pad.groundside_cutback_m`` + the snap
    margin, ``classify/roles._cut_back_groundside``'s), so the two share no
    vertex: the lot keeps its own ground and the pad's edge is the kerb or
    wall between (``constraints/pad_frontage_gs`` holds the pair as a
    terrace).  MEASURED EFHK: welded, the 8 m lot between the pier and the
    kerb road climbed to the pad (47.46 m) and lifted the road's edge --
    29 more ``road_cross_section`` rows."""
    from ..law.tables import snap_margin_m, taxi_half_width_m
    from .reach_under_covers import room_pieces, split_beyond
    r0 = taxi_half_width_m(law, None)
    aprons = [i for i, r in enumerate(regions) if r.role == "apron" and r.source == "cell"
              and r.polygon is not None and not r.polygon.is_empty]
    if not aprons or not r0 or r0 <= 0.0:
        return regions, {}
    reach, unreach = room_pieces(regions, None, float(r0), law)
    if not reach or not unreach:
        return regions, {"beyond_passages": 0}
    weld = float(law.tables.emit.identity.weld_spacing_m)
    sweep = unary_union([p.buffer(float(r0) + weld) for p in reach])
    stands = [Point(s.xy) for s in getattr(airport, "startups", ()) or ()]
    pmin = float(law.tables.structures.building_pad.min_area_m2)
    utree = STRtree(unreach)
    lost: dict[int, list] = {}
    for i in aprons:
        for piece in nonempty_polygon_parts(regions[i].polygon):
            if not len(utree.query(piece, predicate="intersects")) \
                    or not piece.intersects(sweep):
                continue
            for q in nonempty_polygon_parts(piece.difference(sweep)):
                if q.area >= pmin and _is_beyond_lot(q, unreach, float(r0), stands):
                    lost.setdefault(i, []).append(q)
    if not lost:
        return regions, {"beyond_passages": 0}
    pads = [r.polygon for r in pad_regions if r.polygon is not None and not r.polygon.is_empty]
    knife = law.tables.structures.building_pad.groundside_cutback_m + snap_margin_m(law)
    keep_off = (unary_union(pads).buffer(knife, join_style="mitre", mitre_limit=2.0)
                if pads and knife > 0.0 else None)
    return split_beyond(regions, lost, law, "beyond_passages", keep_off)


def _is_beyond_lot(q, unreach: list, r0: float, stands: list) -> bool:
    """``q`` holds unreachable room, no startup, and is a LOT by 19ag's test
    (``classify/reachability``: at least half of it is swept by that room --
    a road network one page draws as apron is passages, never a lot)."""
    own = [p for p in unreach if p.intersects(q) and p.intersection(q).area > 0.0]
    if not own or any(q.contains(s) for s in stands):
        return False
    return 2.0 * unary_union([p.buffer(r0) for p in own]).intersection(q).area >= q.area
