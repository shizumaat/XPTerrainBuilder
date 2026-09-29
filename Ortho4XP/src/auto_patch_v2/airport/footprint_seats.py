"""§16g (1)/(2) THE PLAN-WIDE SEATS — the connector seat machinery split
out of ``footprint_unit`` (issue #104: that file passed the 1,500-line split
point, RULINGS 2026-09-13bz).  No behaviour of its own: :func:`plan_wide_seats`
seats every plan unit and every §16g (6) connector (its end probes, the
linear-structure joint of RULINGS 2026-09-29v (2)) on the unit datums
``footprint_unit.plan_unit_datums`` reads, and ``footprint_unit`` re-exports
both names, so every caller still reads ``footprint_unit.plan_wide_seats``.
"""
from __future__ import annotations

import typing as _t

from . import anchor_rule as _ar
from . import placement_boxes as _pb
from .footprint_connector import PlanConnector, authored_unit_census
from .placement_family import union_area_m2

__all__ = ["plan_wide_seats"]


def _end_probe(cn: _t.Any, own: _t.Sequence[tuple], feet_of
               ) -> tuple:
    """§16g (7) (2) as clarified (owner RULINGS 2026-09-14j): WHERE the
    connector's end contact is read.

    At the connector's OWN GROUND FEET in that end, as degenerate boxes,
    so ``plan_unit_datums`` samples the terrain exactly where the piece
    touches it — its pad if it stands on one, the design surface
    otherwise.  Round 3 sampled the end's BOX CENTRES and HECA's
    1,149 m rail read OFF-SHEET at both ends (measured: 0 of 7 and 0 of
    8 centres on any graded face), so only one end ever produced a datum
    and the ``min`` of the two had nothing to choose from — the rail came
    out at 93.16, its south end, when its north end stands at ~73.4.  A
    foot is a real contact point and is on the sheet wherever the patch
    covers the piece at all.  With no foot in the end, the box centres
    stand as they did."""
    lo = min(b[0] for b in own)
    hi = max(b[2] for b in own)
    lo2 = min(b[1] for b in own)
    hi2 = max(b[3] for b in own)
    feet = [f for f in feet_of(cn.pids)
            if lo <= f[0] <= hi and lo2 <= f[1] <= hi2]
    if feet:
        return tuple((f[0], f[1], f[0], f[1]) for f in feet)
    return tuple(own)


def plan_wide_seats(plan: _t.Any, surface: _ar.Surface,
                    pads: _t.Sequence[_ar.PadRing], touch_m: float,
                    cluster_min_m2: float, counts: dict,
                    connector_span_m: float = 0.0,
                    chain_min_height_m: float = 0.0,
                    contents_min_fraction: float = 0.0,
                    sheet_chain_min_fraction: float = 0.0
                    ) -> "tuple[dict[int, tuple], list[tuple[float, float, float, float, float, str]]]":
    """§16g (1)/(2) PLAN-WIDE, as one call: ``(part id -> (unit id, zero,
    where, source, connector ends, the HIGH end's own seat), the units'
    plan boxes with their zero)``.

    ``connector ends`` is ``("", "")`` for an ordinary member and the two
    end units of a §16g (6) CONNECTOR; the sixth field is then that
    connector's HIGH end's ``(unit, zero, where, source)``, which
    :func:`_bind_plan_wide` takes ONLY when the staged ground-step test
    fires too.  The first four fields stay the body's own UNIT's seat, so
    a long body that turns out not to step is an ordinary member.

    The PART is the join for a staged candidate, because the plan's
    bodies and a candidate's ground groups are different partitions of
    the same triangles.  The BOXES are the join for §16g (5)'s dropped
    multi-anchor placement, which has no part of its own in the plan at
    all — the pack dropped it before the plan was written — and can only
    be placed by WHERE IT STANDS."""
    if touch_m <= 0.0:
        return {}, []
    # unit-platform spec §2 (owner RULINGS 2026-09-28a (2)): THE ONE
    # CONNECTOR VERDICT stamped on the plan at planar time — the same one
    # ``plan_clusters`` cut the design surface's chains by.  A CUT
    # connector leaves its unit's chain here too, and is seated on its low
    # end's contact below; a SOLID one is an ordinary member of the unit it
    # joins.  A plan written before the stamp keeps the staged reading.
    from .footprint_connector import cut_pids, verdicts_of
    stamped = verdicts_of(plan) if connector_span_m > 0.0 else None
    cut = cut_pids(stamped) if stamped else frozenset()
    units, conns = plan_units_and_connectors(plan, touch_m,
                                             connector_span_m, counts,
                                             chain_min_height_m,
                                             contents_min_fraction,
                                             sheet_chain_min_fraction,
                                             cut=cut)
    counts["connector_verdict_stamped"] = int(stamped is not None)
    if stamped is not None:
        counts["connectors_solid"] = sum(1 for v in stamped if v.solid)
        counts["connectors_cut"] = sum(1 for v in stamped if not v.solid)
        conns = [PlanConnector(
            id=f"cn:{v.pids[0] if v.pids else 0}", key=(-1, -1, -1),
            pids=frozenset(v.pids), resource=v.resource, span_m=v.span_m,
            unit="", end_a=v.end_a, end_b=v.end_b,
            boxes_a=v.own_a if v.end_a else (),
            boxes_b=v.own_b if v.end_b else (),
            own_a=v.own_a, own_b=v.own_b)
            for v in stamped if not v.solid]
    _parts = {p.pid: p for u in plan.units for m in u.members for p in m.parts}

    def _feet_of(pids):
        out = []
        for q in pids:
            p = _parts.get(q)
            if p is not None:
                out.extend(p.feet)
        return out
    dat = plan_unit_datums(units, plan, surface, pads, cluster_min_m2)
    out: dict[int, tuple] = {}
    seats: list[tuple[float, float, float, float, float, str]] = []
    for un in units:
        d = dat.get(un.id)
        if d is None:
            continue
        for q in un.pids:
            out[q] = (un.id, d[0], d[1], d[2], ("", ""), None)
        # §16g (7) THE DECK GUARD: the deck's datum is LENT, per body, to
        # the bodies whose footprint polygons touch it — never to the unit
        if un.deck is not None and un.deck_pids:
            dz, name = un.deck
            for q in un.deck_pids:
                if q in out:
                    out[q] = (un.id, dz, name, "deck", ("", ""), None)
        h = _pb.hull_of(un.boxes)
        if h is not None:
            seats.append((h[0], h[1], h[2], h[3], d[0], d[2]))
    # §16g (6) (2): THE HIGH END KEEPS THE CONNECTOR.  Between the two end
    # units the datum SOURCE ranks first — DECK over PAD over GROUND, the
    # deck-side unit being the one the piece arrives at in the air — and
    # the higher zero breaks the tie.  An end on open ground names no unit
    # and can never win; a connector neither of whose ends has a datum is
    # left to §16c.
    # §16g (7) (2) (owner RULINGS 2026-09-14c item 1): THE CONNECTOR IS
    # SEATED LOW.  13df seated it on its HIGH end so the piece met the
    # deck it arrived at; at HECA that reading lifted the T3 terminal
    # complex onto `T3_road.obj`'s deck, and the owner withdrew it.  The
    # piece now takes its LOW end's contact — ground or pad — so it
    # disappears INTO the ground at the high end instead of standing the
    # airport up to meet it, and §10's station cut, when it is written,
    # grades it between its two end contacts.  Between the two ends the
    # LOWER zero wins outright; the source ranks only a tie.
    rank = {"ground": 0, "pad": 1, "cluster_pad": 1, "deck": 2}
    n_open = 0
    from .footprint_connector import linear_pids
    _lin = linear_pids(stamped) if stamped else frozenset()
    _mem = {p.pid: (ui, mi) for ui, u in enumerate(plan.units)
            for mi, m in enumerate(u.members) for p in m.parts}
    _legs: dict[tuple[int, int], list] = {}

    def _centre(boxes):
        return (sum(0.5 * (b[0] + b[2]) for b in boxes) / len(boxes),
                sum(0.5 * (b[1] + b[3]) for b in boxes) / len(boxes))

    def _write(cn, us, d):
        base = out.get(next(iter(cn.pids)))
        for q in cn.pids:
            row = out.get(q) or base
            if row is None and stamped is not None:
                # §2: a CUT connector is in no unit's chain — its own row
                # IS its seat, and the verdict rides with it
                row = (us, d[0], d[1], d[2])
            if row is None:
                continue
            out[q] = (row[0], row[1], row[2], row[3],
                      (cn.end_a, cn.end_b), (us, d[0], d[1], d[2]),
                      "cut" if stamped is not None else "")
    for cn in conns:
        # §16g (7) (2): each end's contact is read under the CONNECTOR'S
        # OWN geometry at that end, never over the end unit — a rail's end
        # component is a whole district and its median ground is not the
        # ground the abutment stands on.
        ends = [(u, _end_probe(cn, own, _feet_of), ky)
                for u, own, bx, ky in
                ((cn.end_a, cn.own_a, cn.boxes_a, cn.keys_a),
                 (cn.end_b, cn.own_b, cn.boxes_b, cn.keys_b))
                if u and bx and own]
        ends = [e for e in ends if e[1]]
        if not ends:
            continue
        ed = plan_unit_datums(
            [PlanUnit(id=u, bodies=(), pids=frozenset(), members=(),
                      boxes=tuple(own), area_m2=union_area_m2(list(own)))
             for u, own, ky in ends], plan, surface, pads, cluster_min_m2)
        cand = [(round(ed[u][0], 6), rank.get(ed[u][2], 3), u)
                for u, _own, _ky in ends if u in ed]
        if not cand:
            continue
        _z, _r, u = min(cand)
        d = ed[u]
        if not (cn.end_a and cn.end_b):
            n_open += 1
        # the body keeps its UNIT's seat unless the staged ground-step
        # test also fires (``_bind_plan_wide``); the HIGH end's seat rides
        # beside it as the alternative, never as the default (``_write``).
        # §2: a stamped CUT connector is its OWN seat.  The end labels
        # (``<unit>/cN``) name the components of ONE removal, so two
        # connectors of one unit share ``.../c0`` for different ground —
        # MEASURED at HECA (lane unitplatform): seven cut connectors of
        # ``fu:38:96`` pooled under ``fu:38:96/c0`` took the LAST one's
        # zero, and T2's ``Titles_not_metal`` b4 sat 23.06 m over its own
        # ground.  The seat's unit id is made the connector's own.
        us = u if stamped is None else f"{u}~{cn.id}"
        # RULINGS 2026-09-29v (2): a LINEAR cut connector's legs are ONE
        # structure — held back and seated once, below
        mk = _mem.get(next(iter(cn.pids))) if cn.pids & _lin else None
        if mk is not None:
            _legs.setdefault(mk, []).append(
                (cn, us, d, [(ed[e[0]], _centre(e[1])) for e in ends
                             if e[0] in ed]))
            continue
        _write(cn, us, d)
    # RULINGS 2026-09-29v (2): A LINEAR ELEVATED STRUCTURE IS SEATED ONCE.
    # The legs of one member that the station removal split into several
    # cut connectors (HECA's `road_train/concrete_3`: b0 495 m, b1 1,149 m)
    # share the pack's ONE authored datum — never each leg on its own
    # low-end contact, which put b0 at 93.12 and b1 at 76.75, 16.4 m
    # apart where they meet at the station, b1's piers buried 16.8 m.  The
    # datum is the contact AT THE JOINT, where the legs meet each other —
    # the plane the pack's pieces were authored on together: the joint is
    # the midpoint of the closest pair of ends across two legs, and the
    # contact is read under EACH leg's ground foot nearest it (an END box
    # is a whole stretch of the leg — HECA's N leg's station end spans
    # 360 m and its median ground, 89.23, is not the ground at the
    # station, 93.3).  A single leg keeps its low end's contact (§16g (7)
    # (2)).
    for mk, legs in sorted(_legs.items()):
        seat = None
        if len(legs) >= 2:
            best = None
            for i, (_c1, _u1, _d1, e1) in enumerate(legs):
                for _c2, _u2, _d2, e2 in legs[i + 1:]:
                    for _da, ca in e1:
                        for _db, cb in e2:
                            g = _pb.box_gap_m((ca[0], ca[1], ca[0], ca[1]),
                                              (cb[0], cb[1], cb[0], cb[1]))
                            if best is None or g < best[0]:
                                best = (g, (0.5 * (ca[0] + cb[0]),
                                            0.5 * (ca[1] + cb[1])))
            probe = []
            if best is not None:
                jl, jo = best[1]
                ml, mo = _ar._m_per_deg(jl)
                for cn, _us, _d, _e in legs:
                    ft = _feet_of(cn.pids)
                    if ft:
                        f = min(ft, key=lambda q: ((q[0] - jl) * ml) ** 2
                                + ((q[1] - jo) * mo) ** 2)
                        probe.append((f[0], f[1], f[0], f[1]))
            if probe:
                jd = plan_unit_datums(
                    [PlanUnit(id="joint", bodies=(), pids=frozenset(),
                              members=(), boxes=tuple(probe),
                              area_m2=union_area_m2(probe))],
                    plan, surface, pads, cluster_min_m2).get("joint")
                if jd is not None:
                    seat = jd
                    counts["connector_legs_one_seat"] = \
                        counts.get("connector_legs_one_seat", 0) + len(legs)
        us0 = sorted(us for _c, us, _d, _e in legs)[0] + "~joint"
        for cn, us, d, _e in legs:
            _write(cn, us0 if seat is not None else us,
                   seat if seat is not None else d)
    counts["plan_wide_units"] = len(units)
    counts["plan_wide_units_seated"] = len(dat)
    counts["plan_wide_connectors"] = len(conns)
    counts["plan_wide_connectors_to_open_ground"] = n_open
    counts.update(authored_unit_census(plan, out))
    return out, seats


# Imported LAST (``footprint_unit`` re-exports this module at ITS end): the
# names are bound whichever of the two modules is imported first.
from .footprint_unit import (PlanUnit, plan_unit_datums,  # noqa: E402
                             plan_units_and_connectors)
