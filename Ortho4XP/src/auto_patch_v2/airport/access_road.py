"""A DECK ON THE HELD ACCESS ROAD RIDES THE LINE (#2090 B4b; spec
``2090-agp-group-groundside-spec.md``, amendment B′).

At the pack stage, after the kept bridges are read (``airport/bridge_stack.
bridge_stacks``): the joined stacks of one AGP floor whose graded end
carries an access road are SIBLINGS (``model/deck_ends.sibling_ends``), and
the road between them is held on the line between their levels (B4).  A
kept deck with no join of its own that carries one of those access ways
(``StackDeck.carried``) stands ON that held road; seated by its own
predicted seat it would leave a step in the level road the pack holds at
one level.  It RIDES the line instead:

* the siblings stand in LINES along the access road (``sibling_ends``' split:
  the road runs between two consecutive ends of one line);
* an end of it is ON THE HOLD when its middle lies between two consecutive
  siblings (``model/deck_ends.between_siblings``, B4's own test), or when its
  end line comes within two ``[bridge] abutment_sample_step_m`` of an
  outermost sibling's end-line stations; ``L_e`` is the line's level there;
* with one end or more on the hold its zero is ``mean(L_e - top_e)``, it
  takes the siblings' AGP group (``DeckStack.datum_group``) and
  ``DeckStack.rides = (member, y_floor)``; the on-hold ends take state
  ``joined`` (no row, no ground: the held road is their row) and its other
  land end is read as a sibling's other end — graded on an access road, it is
  the group's new outermost sibling;
* it is always minted (its zero is published);
* a spread of ``L_e - top_e`` over ``deck_flush_m`` is listed
  ``access_deck_tilt``; a re-seat over ``[agp] deck_join_reach_m`` is
  refused, listed ``access_deck_out_of_reach``.

Repeated until nothing changes (a new outermost sibling may reach the next
deck).  Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import typing as _t

from ..geom.end_line import near_stations
from ..model.deck_ends import between_siblings, sibling_ends

__all__ = ["ride_access_roads", "on_hold_levels"]


def on_hold_levels(st, sibs, step: float) -> dict[str, float]:
    """``{side: L_e}`` per land end of stack ``st`` on the hold of the sibling
    ends ``sibs`` (``sibling_ends``' order; module doc)."""
    out: dict[str, float] = {}
    outer = [sibs[0], sibs[-1]] if sibs else []
    for e in st.ends:
        if not e.stations:
            continue
        mid = (sum(p[0] for p in e.stations) / len(e.stations),
               sum(p[1] for p in e.stations) / len(e.stations))
        got = between_siblings(sibs, mid, step)
        if got is not None:
            out[e.side] = float(got[0])
            continue
        for s, se in outer:
            if near_stations(list(e.stations), se.stations, 2.0 * step).any():
                out[e.side] = float(s.zero_z) + float(se.top)
                break
    return out


def _ways_near(cx):
    """``on_road`` of ``sibling_ends`` at the pack stage: a mapped way's
    centreline of the ones named within ``reach`` of ``xy`` (``cx.obs``'s
    way graph, the one ``bridge_end_state.access_ways`` reads)."""
    from shapely.geometry import LineString, Point
    lines: dict[int, _t.Any] = {}
    by_id = {int(w.id): w for w in cx.obs.graph.ways}

    def on_road(xy, ways, reach: float) -> bool:
        p = Point(float(xy[0]), float(xy[1]))
        for w in ways:
            if w not in lines:
                pts = list(by_id[w].points) if w in by_id else []
                lines[w] = LineString(pts) if len(pts) >= 2 else None
            if lines[w] is not None and lines[w].distance(p) <= reach:
                return True
        return False
    return on_road


def _candidates(every, ways: set[int]) -> list:
    """Kept stacks with no join and no ride whose deck carries a way of ``ways``."""
    from ..model.deck_stack import KEPT
    return [st for st in every if st.kind == KEPT and not st.joins and not st.rides
            and any(int(w) in ways for d in st.decks for w in d.carried)]


def _ride_one(st, key, sibs, step: float, flush: float, reach: float
              ) -> "tuple[float | None, dict[str, float], list[str]]":
    """``(zero or None, {side: L_e}, notes)`` of candidate ``st`` on the hold
    of ``sibs``; ``None`` = not on it, or refused (listed)."""
    hold = on_hold_levels(st, sibs, step)
    if not hold:
        return None, {}, []
    tops = {e.side: float(e.top) for e in st.ends}
    offs = [hold[s] - tops[s] for s in sorted(hold)]
    zero = sum(offs) / len(offs)
    tag = (f"{st.id}: rides the access road of {key[0]} floor y {key[1]:.2f} (ends "
           + ", ".join(f"{s} {hold[s]:.3f}" for s in sorted(hold))
           + f"; zero {st.zero_z:.3f} -> {zero:.3f}, {zero - st.zero_z:+.2f})")
    if abs(zero - float(st.zero_z)) > reach:
        return None, hold, [f"{tag} — access_deck_out_of_reach (over deck_join_reach_m "
                            f"{reach:.1f}): refused, listed"]
    notes = [f"{tag} (#2090 B4b)"]
    if max(offs) - min(offs) > flush:
        notes.append(f"{st.id}: access_deck_tilt {max(offs) - min(offs):.3f} m over "
                     f"deck_flush_m {flush:.2f}")
    return zero, hold, notes


def ride_access_roads(cx, out: _t.Sequence, every: _t.Sequence,
                      restack: _t.Callable) -> tuple[list, list, list[str]]:
    """``(minted, every read, notes)`` with every deck on a held access road
    re-seated to ride it (module doc).  ``restack(st, zero, joined, key,
    gid, note)`` re-reads stack ``st``'s ends on ``zero`` with the sides of
    ``joined`` (``{side: why}``) joined and returns the riding stack."""
    out, every = list(out), list(every)
    notes: list[str] = []
    step = float(cx.step)
    flush = float(cx.law.tables.structures.bridge.deck_flush_m)
    reach = float(cx.law.tables.structures.agp.deck_join_reach_m)
    done: set[str] = set()
    changed = True
    while changed:
        changed = False
        for key, sibs in sibling_ends(every, _ways_near(cx), step).items():
            gid = next((s.datum_group for s, _e in sibs if s.datum_group), "")
            ways = {int(w) for _s, e in sibs for w in e.access}
            for st in _candidates(every, ways):
                if st.id in done:
                    continue
                zero, hold, n = _ride_one(st, key, sibs, step, flush, reach)
                notes += n
                if hold:
                    done.add(st.id)
                if zero is None:
                    continue
                joined = {s: f"rides the held access road at {hold[s]:.3f} (#2090 B4b)"
                          for s in hold}
                new = restack(st, zero, joined, key[:2], gid, n[0])
                every = [new if s.id == st.id else s for s in every]
                out = [s for s in out if s.id != st.id] + [new]
                changed = True
                break
            if changed:
                break
    return out, every, notes
