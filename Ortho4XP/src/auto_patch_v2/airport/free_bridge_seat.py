"""CLASS B: A FREE-STANDING BRIDGE FRAME SEATS AT ITS DECK'S END LINES
(owner RULINGS 2026-10-22m / 22p, amending 22d; #2035 follow-up).

22m: "Seat bridges so whichever end is closer to the ground, that sides deck
is flush with the terrain, then the still floating side, the terrain must
grade up to the deck height."  The reading of each end already exists
(``bridge_approach.approach_seat``: the ground AT the end line, a road
ribbon where most of the line lies on one, else the mesh; a bank on water
walks landward, ``anchor_rule._datum_anchor``).  What did not exist is the
FRAME that reading seats: ``placement_family.frame_is_bridge`` calls a frame
a bridge only when EVERY member is a deck, and a pack that models a bridge
as a deck plus its piers, rails and lamp masts on one anchor — every bridge
OTHH's pack authors — never qualified.  Its deck kept its own datum at
best, and the 22o connected-group median then moved it onto its piers'
feet: OTHH ``Bridge_04`` (piers in the canal) stood its deck 2.5 m over
both banks, the flyover ramps ``Bridge_02`` / ``_06`` 1-2 m over the land
at their ends.

THE FRAME IS THE BRIDGE by the witness class A and the refused class A
already read (``airside_deck_seat._is_the_bridge``): every body of the
frame stands inside a deck's model footprint (§16e (3) ``bridge_of``) or,
outside it, on no emitted object pad — no building shares it (22m (2): a
bridge attached to a building stays with the building).  A frame class A
or its refused reading takes is theirs; a deck carrying a plate (an
overpass's road beneath, a hard-deck bridge's end lines, an edge, a walled
or split-level plate) keeps that plate's reader.

THE ZERO, per deck member (a frame may hold several bridges: OTHH's
interchange puts three on one anchor): the deck-top datum of a FREE deck
(``anchor_rule.datum_of(free_standing=True)``), read at its END LINES with
the deck top AT each end (``airside_deck_seat.end_tops``: a ramp is
authored on a grade) — flush at the end whose ground less its top is the
highest, the other end floating for the terrain to grade up to (#1138).
Every body the frame's deck footprints name (``Body.bridge_of``) takes its
deck's zero; in a one-deck frame every body does (the supports stay
attached, 10-22c).

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import typing as _t

from . import anchor_rule as _ar

__all__ = ["PLATED_KINDS", "REASON", "free_bridge_zeros", "free_bridge_seat", "deck_of_body"]

#: a member carrying one of these plates is seated by that plate's own
#: reader (``airside_deck_seat._plate_zero``, ``anchor_rule.datum_of``)
PLATED_KINDS = frozenset({"deck", "overpass", "edge", "walled", "split_level"})

#: the reason prefix :func:`free_bridge_seat` writes
REASON = "one free-standing bridge at its deck's end lines"


def _free_deck(m: _t.Any) -> bool:
    """A deck member the class-B reading seats: a flag / signature deck
    with a top and a ring, over no graded face, carrying no plate."""
    return (str(getattr(m, "deck_kind", "") or "") in ("flag", "signature")
            and getattr(m, "deck_top_y", None) is not None
            and getattr(m, "deck_datum_z", None) is None
            and len(getattr(m, "deck_ring", None) or ()) >= 3
            and str(getattr(m, "plate_kind", "") or "") not in PLATED_KINDS)


def _deck_zero(m: _t.Any, surface: _ar.Surface, origin: tuple[float, float],
               agl_m: float, step_m: float, walk_max_m: float,
               level_tol_m: float) -> "tuple[float, str] | None":
    """``(zero, why)`` of one free deck member, or ``None`` where its end
    lines read no land."""
    from .airside_deck_seat import end_tops
    from .bridge_approach import approach_seat
    from .rebake_plan import end_line_stations
    datum = _ar.datum_of(m, abutment_step_m=step_m, abutment_walk_max_m=walk_max_m,
                         level_tol_m=level_tol_m, free_standing=True)
    if datum is None:
        return None
    tops = None
    if len(datum.ends) >= 2 and step_m > 0.0:
        lines = tuple(end_line_stations([e], step_m) for e in datum.ends[:2])
        tops = end_tops(m, lines, origin, step_m)
    seat = approach_seat(datum, surface, origin=origin, authored_agl_m=agl_m, tops=tops)
    if seat is not None:
        return seat.zero, seat.reason
    return _walked_zero(datum, surface, tops)


def _walked_zero(datum: _t.Any, surface: _ar.Surface,
                 tops: "_t.Sequence[float] | None") -> "tuple[float, str] | None":
    """An end line on a bank (or off the sheet): §16e (6)'s LANDWARD WALK
    (``anchor_rule._walked_stations``; 13v, the canal bridges), read PER
    END with that end's own deck top — flush at the end whose walked ground
    less its top is the highest, as :func:`bridge_approach.approach_seat`."""
    from .rebake_plan import end_line_stations
    stations, note = _ar._walked_stations(datum, surface, getattr(surface, "water", None))
    sizes = [len(end_line_stations([e], datum.step_m)) for e in datum.ends] \
        if datum.ends and datum.step_m > 0.0 else []
    if len(sizes) < 2 or sum(sizes) != len(stations):
        sizes = [len(stations)]
    ys = (list(tops) if tops is not None and len(tops) == len(sizes)
          else [float(datum.y)] * len(sizes))
    best = None
    k0 = 0
    for k, n in enumerate(sizes):
        kept, _wet, _off = _ar._line_reading(stations[k0:k0 + n], surface,
                                             getattr(surface, "water", None))
        k0 += n
        if not kept:
            continue
        zs = sorted(q[0] for q in kept)
        z = zs[len(zs) // 2] - float(ys[k])
        if best is None or z > best[0]:
            best = (z, f"§16e {datum.label} datum: the authored y {ys[k]:+.2f} flush with "
                       f"the walked ground {zs[len(zs) // 2]:.2f} at end line {k + 1}"
                       f"{note} (RULINGS 2026-10-22m, 2026-09-13v)")
    return best


def free_bridge_zeros(staged: _t.Sequence[_t.Any], surface: _ar.Surface, *,
                      origin: tuple[float, float], agl_m: float, step_m: float,
                      walk_max_m: float = 0.0, level_tol_m: float = 0.0,
                      counts: "dict | None" = None) -> dict[str, tuple[float, str, tuple]]:
    """``{deck resource: (zero, why, ring box)}`` of a frame that IS a
    free-standing bridge (module doc), or ``{}``.  ``staged`` are the
    frame's staged members (``placement_record.Staged``: ``m``, ``bridge``,
    ``boxes``); the ring box is ``(lat0, lon0, lat1, lon1)``."""
    from .airside_deck_seat import _is_the_bridge
    decks = [st for st in staged if _free_deck(st.m)]
    if not decks or not all(_is_the_bridge(staged, st, surface) for st in decks):
        return {}
    out: dict[str, tuple[float, str, tuple]] = {}
    for st in decks:
        got = _deck_zero(st.m, surface, origin, agl_m, step_m, walk_max_m, level_tol_m)
        if got is not None:
            ring = st.m.deck_ring
            box = (min(q[0] for q in ring), min(q[1] for q in ring),
                   max(q[0] for q in ring), max(q[1] for q in ring))
            out[str(st.m.resource)] = (got[0], got[1], box)
    if out and counts is not None:
        counts["free_bridge_frames"] = counts.get("free_bridge_frames", 0) + 1
    return out


def _overlap(a: tuple, b: tuple) -> float:
    """Plan overlap of two ``(lat0, lon0, lat1, lon1)`` boxes, deg²."""
    return (max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
            * max(0.0, min(a[3], b[3]) - max(a[1], b[1])))


def deck_of_body(b: _t.Any, resource: str,
                 zeros: _t.Mapping[str, tuple[float, str, tuple]]) -> "str | None":
    """The deck of a free bridge frame this body moves with: the deck its
    footprint names (``Body.bridge_of``, §16e (3)), else its own member's
    when that member is the deck, else in a ONE-deck frame that deck, else
    the deck whose ring box its plan box overlaps most (a curved ramp's
    own rails, whose hull centre falls off the deck's footprint); ``None``
    where it overlaps none."""
    key = str(getattr(b, "bridge_of", "") or "").split("#", 1)[0]
    if key in zeros:
        return key
    if resource in zeros:
        return resource
    if len(zeros) == 1:
        return next(iter(zeros))
    box = getattr(b, "geom_box", None) or getattr(b, "plan_box", None)
    if box is None:
        return None
    best = max(zeros, key=lambda k: _overlap(tuple(box), zeros[k][2]))
    return best if _overlap(tuple(box), zeros[best][2]) > 0.0 else None


def free_bridge_seat(record: _t.Any, m: _t.Any,
                     zeros: _t.Mapping[str, tuple[float, str, tuple]]) -> _t.Any:
    """Every body of ``record`` at the zero of its deck (:func:`deck_of_body`);
    a body no deck takes keeps its own seat."""
    if not zeros:
        return record
    from .open_frame_seat import at_zero
    res = str(getattr(m, "resource", "") or "")
    out = record
    for key, (zero, why, _box) in zeros.items():
        def take(b, _k=key, _z=zero):
            return (deck_of_body(b, res, zeros) == _k and b.anchor.surface_z is not None
                    and abs(float(b.anchor.surface_z) - float(b.anchor.y_zero) - _z) > 1e-6)
        out = at_zero(out, m, zero, take, f"{REASON} {zero:.2f} ({why})")
    return out
