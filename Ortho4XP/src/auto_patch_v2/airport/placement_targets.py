"""THE CARRIER QUESTION A TARGET ASKS, and what the answer cuts (spec
``object-placement-spec.md`` §14 (1) / §16a (1) / §16b (2) / §16e (3)).

``placement_plan``'s pass 3 asks, per elevated body and per piece of a
footless placement, WHICH candidates it may rest on and what the ranked
answer divides it into.  The three functions live here for the
1,000-line law only; ``placement_plan`` re-exports all three and every
caller and every twin reads them there.

NO LAW CONSTANT LIVES HERE.
"""
from __future__ import annotations

import typing as _t

from . import placement_carrier as _pc
from .placement_cut import _geom_ground
from .placement_record import Staged as _Staged   # noqa: F401

__all__ = ["_footless_targets", "_carrier_pieces", "welded_carriers"]


def _footless_targets(st: "_Staged", tol_m: float
                      ) -> list[tuple[list[int], list[tuple]]]:
    """§16b (2): the carrier questions a FOOTLESS placement asks.

    §14 (1) asked ONE — a footbridge is a rigid span and a terminal roof
    a rigid plate, and two carriers would give its halves two zeros.
    §16b (1)'s cut has already divided the placement WHERE THE GROUND
    UNDER IT DIFFERS, so rigidity holds within a terrain group and the
    question is asked once per group: a span over one terrain is still
    one target, and LEMD's `green-TEJ3` — one welded roof-panel resource
    over 1 x 2 km — asks per piece and rides the roof each piece stands
    over."""
    groups: list[list[int]] = []
    levels: list[float | None] = []
    for i in range(len(st.raw)):
        g = st.raw[i][7] if len(st.raw[i]) > 7 else None
        for gi, lv in enumerate(levels):
            if (g is None) == (lv is None) and (
                    g is None or tol_m <= 0.0 or abs(float(g) - float(lv)) <= tol_m):
                groups[gi].append(i)
                break
        else:
            groups.append([i])
            levels.append(g)
    return [(g, [b for i in g for b in st.part_boxes[i]]) for g in groups]


def _carrier_pieces(st: "_Staged", grp: list[int],
                    over: _t.Sequence[tuple[_pc.Candidate, str]],
                    counts: dict[str, int], tol_m: float = 0.0
                    ) -> list[tuple[list[int], _pc.Candidate, str]]:
    """§16a (1): A CARRIED BODY IS CUT WHERE ITS CARRIER IS CUT.

    ``over`` is :func:`placement_carrier.carriers_for`'s ranked list of
    the carrier groups this body stands over.  With one of them the body
    is not cut at all (§14 (1)'s rigid span).  With several — a roof over
    walls the terrain re-cut into three groups, a roof over two buildings
    — the body's TRIANGLES are assigned to the carrier group each stands
    over and one piece is made per group, each riding that group's zero
    at the authored offset.  The ground under the carried body is never
    read: that was §16 (3)'s reading, and it put the garage pavilions
    −1.27 … +3.70 m against the slab they sit on.

    New pieces are appended to ``st.raw`` / ``st.boxes`` /
    ``st.part_boxes`` (the three parallel lists every later pass reads by
    index) and the source body's own index is left behind, referenced by
    nothing."""
    if len(over) < 2:
        return [(list(grp), over[0][0], over[0][1])]
    # §9 STILL RULES THE FILE: carriers standing at ONE zero (within
    # ``split_tol_m``) are one reading of the terrain, and cutting the
    # body against them would make pieces ``merge_rides`` puts straight
    # back into one file.  Dropping them before the cut changes no
    # answer and is most of the cut's cost at a FLAT airport — OTHH
    # asked for 3,869 cuts and needs 319 of them.
    if tol_m > 0.0:
        keep, zeros = [], []
        for c, why in over:
            z = (None if c.anchor.surface_z is None
                 else float(c.anchor.surface_z) - float(c.anchor.y_zero))
            if z is not None and any(abs(z - q) <= tol_m for q in zeros):
                continue
            keep.append((c, why))
            if z is not None:
                zeros.append(z)
        over = keep
        if len(over) < 2:
            return [(list(grp), over[0][0], over[0][1])]
    parts = [p for i in grp for p in st.raw[i][0]]
    # §16c (1): the cut reads the group's OWN written triangles — the
    # pieces a prior cut made, else everything this member's file will
    # contain; never only the components its parts happen to name
    gtris = (tuple(q for i in grp for q in (st.raw[i][5] or ()))
             or (st.cutter.all_tris() if len(st.raw) == 1 else ()))
    pieces = st.cutter.carrier_groups(parts, [c.part_boxes for c, _w in over],
                                      tris_in=gtris)
    if not pieces:
        return [(list(grp), over[0][0], over[0][1])]
    counts["carried_bodies_cut_by_carrier"] = \
        counts.get("carried_bodies_cut_by_carrier", 0) + 1
    counts["carrier_pieces"] = counts.get("carrier_pieces", 0) + len(pieces)
    senior = st.raw[max(grp, key=lambda i: len(st.raw[i][0]))]
    out: list[tuple[list[int], _pc.Candidate, str]] = []
    for k, tris, box in pieces:
        bi = len(st.raw)
        _pp, _sp, _gg = _geom_ground(st.cutter, parts, tris, st.surface)
        st.raw.append(([p for p in parts], senior[1], senior[2], (), True, tris,
                       _pp, _gg))
        st.boxes.append(box)
        st.part_boxes.append([box])
        if st.part_tops:              # §16c (4): the piece's own top
            st.part_tops.append(list(st.cutter.part_tops(
                [(parts, "", None, (), True, tris, (), None)])[0]))
        out.append(([bi], over[k][0], over[k][1]))
    return out




def welded_carriers(targets: _t.Sequence[_t.AbstractSet[int]],
                    carrier_of: _t.Mapping[int, _pc.Candidate],
                    contacts: _t.Iterable[tuple[int, int]],
                    ) -> dict[int, tuple[_pc.Candidate, str]]:
    """Issue #127 (flat-pad spec §7): A BODY THE SEARCH LEFT ON ITS OWN
    GROUND RIDES WHAT IT IS WELDED TO.

    §15's search offers only FOOTED candidates, so a footless facade
    whose one weld is to a body that is itself CARRIED (HECA T3: the
    ``glass_blue_2`` panes welded to ``T2_Brick`` b4, which rests on
    ``door`` b27) found nothing it may stand on and fell to §16 (3)'s
    own ground — the design surface under its own footprint, 1.1-1.4 m
    over the zero its wall was written at, a seam the eye reads across a
    2 mm weld.  The weld is the stronger evidence: the pack authored the
    two parts touching, so they share ONE carrier.

    ``targets`` are the part-id sets of the bodies with no carrier;
    ``carrier_of`` maps every part id already placed to the candidate its
    body is written on (a footed body's own pids to itself, a carried
    body's to its carrier); ``contacts`` is the unit's ε-contact graph
    (welds only, never abutments).  A target takes the carrier holding
    the MOST of its welds (ties: the carrier with the most feet, then
    member, then group).  The walk is breadth-first in ROUNDS read from
    a snapshot, so two facades welded to each other share the carrier of
    whichever reaches a placed body first, and the answer never depends
    on the order the targets are listed.  Targets welded to nothing
    placed are absent from the result and keep their own ground.

    ``{target index: (carrier, why)}``."""
    adj: dict[int, set[int]] = {}
    for a, b in contacts:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    placed = dict(carrier_of)
    out: dict[int, tuple[_pc.Candidate, str]] = {}
    hops = 0
    while True:
        hops += 1
        new: dict[int, tuple[_pc.Candidate, str]] = {}
        for ti, pids in enumerate(targets):
            if ti in out:
                continue
            votes: dict[int, list] = {}
            for p in pids:
                for q in adj.get(p, ()):
                    if q in pids:
                        continue
                    c = placed.get(q)
                    if c is None:
                        continue
                    v = votes.setdefault(id(c), [0, c])
                    v[0] += 1
            if not votes:
                continue
            n, c = min(votes.values(),
                       key=lambda v: (-v[0], -v[1].feet, v[1].member,
                                      v[1].group))
            new[ti] = (c, f"welded ({n} part contact(s), hop {hops}) to a "
                          f"body written on it")
        if not new:
            return out
        for ti, (c, _w) in new.items():
            for p in targets[ti]:
                placed.setdefault(p, c)
        out.update(new)
