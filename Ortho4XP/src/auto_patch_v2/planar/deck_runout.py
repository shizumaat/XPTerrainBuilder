"""THE AIRSIDE RUN-OUT OF A KEPT DECK'S ROAD (#2062 spec R5; master ruling
2026-11-15 on the owner's 13:50Z "it should be road on both ends, not apron,
and we don't want a step" and 13:52Z "the road appears elevated above the
apron at the east end of the bridge and descends down meeting at the taxiway
into the apron").

A KEPT stack's rowed end (``model/deck_stack.DeckStack.rowed_ends``) whose
deck carries an apt.dat GROUND ROUTE (``airport/ground_route_ways``) that
runs on past the end line over AIRSIDE PAVEMENT -- the cells under at least
half of its first ``abutment_sample_step_m`` x 2 past the line -- is a road
end: the route's road is minted past the line, ``StackEnd.airside_run``
metres (its continuation, at most ``[bridge] airside_run_max_m``) along it
(``StackEnd.path``), at the road ramp grade.  The airside cells under it and
its bank (``[bridge] airside_run_bank_m`` either side) are cut
(:func:`run_knife`, the planar stage's one knife); the stack's ground fills
the hole (``geom/deck_ground``: the end's apron along the path and its bank);
``constraints/deck_runout`` holds it at the deck end's top coming down until
it meets the airside stage 1 solved, then on the airside.

Nothing here names a pack, a resource or an airport."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import LineString
from shapely.ops import substring, unary_union

__all__ = ["with_airside_runs", "run_knife"]


def _beyond(route: LineString, e) -> "LineString | None":
    """``route`` from where it crosses ``e``'s end line, outward."""
    end = LineString(e.stations)
    x = route.intersection(end)
    if x.is_empty:
        return None
    p = x if x.geom_type == "Point" else x.representative_point()
    s = route.project(p)
    q_up = route.interpolate(min(route.length, s + 1.0))
    sense = (q_up.x - p.x) * e.out[0] + (q_up.y - p.y) * e.out[1]
    out = substring(route, s, route.length) if sense > 0.0 else \
        LineString(list(substring(route, 0.0, s).coords)[::-1])
    return out if out.length > 0.0 else None


def with_airside_runs(stacks: _t.Sequence, classification, airport, law,
                      notes: "list[str] | None" = None) -> tuple:
    """``stacks`` with each KEPT stack's airside run-out ends read (module
    doc): their ``path``, ``run``, ``grade`` and ``airside_run``."""
    from ..airport.ground_route_ways import ground_route_ways
    from ..law.tables import rolled_on_roles
    from ..model.deck_stack import KEPT
    from .deck_bridge import CellRoles
    kept = [st for st in stacks if st.kind == KEPT and st.rowed_ends()]
    if not kept or classification is None:
        return tuple(stacks)
    routes = {int(w.id): LineString(w.points) for w in ground_route_ways(airport)
              if len(w.points) >= 2}
    if not routes:
        return tuple(stacks)
    br = law.tables.structures.bridge
    step = float(br.abutment_sample_step_m)
    grade = float(law.tables.emit.road_contact.ramp_grade)
    air = set(rolled_on_roles(law))
    roles = CellRoles(classification, airport)
    out = []
    for st in stacks:
        if st not in kept:
            out.append(st)
            continue
        carried = {int(w) for d in st.decks for w in d.carried}
        ends = []
        for e in st.ends:
            beyond = None
            if e in st.rowed_ends():
                for wid in sorted(carried & set(routes)):
                    beyond = _beyond(routes[wid], e)
                    if beyond is not None:
                        break
            if beyond is None or beyond.length < step:
                ends.append(e)
                continue
            probe = [beyond.interpolate(0.5 + k) for k in range(int(2.0 * step))]
            on_air = sum(roles.at_xy((q.x, q.y)) in air for q in probe)
            if 2 * on_air < len(probe):
                ends.append(e)
                continue
            run = min(beyond.length, float(br.airside_run_max_m))
            path = substring(beyond, 0.0, run)
            ends.append(_dc.replace(e, path=tuple((float(x), float(y)) for x, y, *_z
                                                  in path.coords),
                                    run=run, grade=grade, airside_run=run))
            if notes is not None:
                notes.append(f"{st.id} {e.object_id} {e.side}: its ground route runs on over "
                             f"airside pavement {beyond.length:.1f} m -- the road is minted "
                             f"{run:.1f} m past the end line (#2062 R5 airside run-out)")
        out.append(_dc.replace(st, ends=tuple(ends)))
    return tuple(out)


def run_knife(stacks: _t.Sequence, law):
    """The cut of every airside run-out: each such end's slab and its
    corridor along the path, the bank's width either side; ``None`` with
    none."""
    from ..geom.deck_ground import (end_corridor, end_inner_strip, end_slab, path_line,
                                    ring_polygon)
    step = float(law.tables.structures.bridge.abutment_sample_step_m)
    bank = float(law.tables.structures.bridge.airside_run_bank_m)
    parts = []
    for st in stacks:
        rings = unary_union([p for p in (ring_polygon(d.ring) for d in st.decks) if p])
        for e in st.ends:
            if not getattr(e, "airside_run", 0.0):
                continue
            line = path_line(e, e.run)
            if line is None:
                continue
            g = unary_union([end_slab(e, step), end_corridor(e, line, e.half_width + bank)])
            ring = next((ring_polygon(d.ring) for d in st.decks if d.object_id == e.object_id),
                        None)
            parts.append(unary_union([g.difference(rings), end_inner_strip(e, bank, ring)]))
    return unary_union(parts) if parts else None


