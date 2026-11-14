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

THE FRAME IS THE BRIDGE by the POSITIVE WITNESS (#2065; spec
``2065-bridge-class-A1.md`` §A4 S3): the pack stage read it
(``planar/free_bridge``: W1-W7 + W4b, ``airport/bridge_witness``) and the
rebake plan published each free deck (``plate_kind == "free"``) with its
bridge's id, its two ROUTE end lines (``deck_ends``), the driven layer's top
at each (``deck_end_tops``) and whether each meets LAND (``deck_end_land``,
W7).  Nothing else is admitted here: a deck the witness did not hold, an
all-deck frame (22d / 22p), a plated deck and a class-A frame keep their own
readers.

THE ZERO, per BRIDGE (a frame may hold several: OTHH's interchange puts
three on one anchor): ONE zero per ``free_bridge`` id (22o; 13y (4)) — over
its LAND ends, the highest ``ground - top`` (``deck_end_read.deck_end_reads``:
the ground at the end line, the published top on it), so that end is flush
and every other floats for the terrain to grade up to (#1138).  Every body
takes its deck's bridge's zero (:func:`_deck_of_body`); in a one-deck frame
every body does (the supports stay attached, 10-22c).

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import typing as _t

from ..model.free_bridge import FREE_PLATE
from . import anchor_rule as _ar

__all__ = ["PLATED_KINDS", "REASON", "free_bridge_zeros", "free_bridge_seat",
           "free_member", "bridge_groups"]

#: a member carrying one of these plates is seated by that plate's own
#: reader (``airside_deck_seat._plate_zero``, ``anchor_rule.datum_of``)
PLATED_KINDS = frozenset({"deck", "overpass", "edge", "walled", "split_level"})

#: the reason prefix :func:`free_bridge_seat` writes
REASON = "one free-standing bridge at its deck's end lines"


def free_member(m: _t.Any) -> bool:
    """A deck the rebake plan published as a FREE BRIDGE's (#2065 S2): its
    plate kind ``"free"``, a top, its two route end lines and their land
    flags."""
    return (str(getattr(m, "plate_kind", "") or "") == FREE_PLATE
            and getattr(m, "deck_top_y", None) is not None
            and len(getattr(m, "deck_ends", None) or ()) >= 2
            and len(getattr(m, "deck_end_land", ()) or ()) >= 2)


def _rings_local(decks: _t.Sequence[_t.Any], origin: tuple[float, float]) -> list:
    """Each deck's ring as a plan polygon in metres about ``origin``."""
    from shapely.geometry import Polygon

    from .deck_end_read import _local
    out = []
    for st in decks:
        p = Polygon([_local(q, origin) for q in st.m.deck_ring])
        out.append(p if p.is_valid else p.buffer(0))
    return out


def bridge_groups(decks: _t.Sequence[_t.Any], origin: tuple[float, float],
                  touch_m: float) -> list[list[int]]:
    """The indices of ``decks`` grouped into BRIDGES: decks whose rings
    come within ``touch_m`` of each other, transitively (a census's reading
    of a frame no witness published)."""
    rings = _rings_local(decks, origin)
    root = list(range(len(decks)))

    def find(k: int) -> int:
        while root[k] != k:
            root[k] = root[root[k]]
            k = root[k]
        return k
    for i in range(len(decks)):
        for j in range(i + 1, len(decks)):
            if rings[i].distance(rings[j]) <= touch_m:
                root[find(j)] = find(i)
    groups: dict[int, list[int]] = {}
    for k in range(len(decks)):
        groups.setdefault(find(k), []).append(k)
    return list(groups.values())


def _abuts(line: _t.Sequence[tuple[float, float]], others: _t.Sequence[_t.Any],
           origin: tuple[float, float], touch_m: float) -> bool:
    """Does an end line ABUT another deck of its bridge — most of its
    stations within ``touch_m`` of that deck's ring?"""
    from shapely.geometry import Point

    from .deck_end_read import _local
    pts = [Point(_local(q, origin)) for q in line]
    return any(2 * sum(1 for p in pts if r.distance(p) <= touch_m) > len(pts)
               for r in others)


def _bridge_zero(reads: _t.Sequence[_t.Any], lines_abut: _t.Sequence[_t.Sequence[bool]]
                ) -> "tuple[float, str, int] | None":
    """``(zero, why, unread)`` of one bridge from its decks' end reads
    (``deck_end_read._DeckEnds``, ``None`` for a deck read nowhere):
    the highest ``ground - top`` over its land ends (``lines_abut[d][k]``
    false), else over every end; a 22p clearance stands as one candidate.
    ``unread`` counts the LAND ends read nowhere (#2065 A3 rule 10: never
    dropped silently — the caller notes them)."""
    cands: list[tuple[float, str]] = []
    every: list[tuple[float, str]] = []
    unread = 0
    for d, r in enumerate(reads):
        land = [not (k < len(lines_abut[d]) and lines_abut[d][k]) for k in range(2)]
        if r is None:
            unread += sum(land)
            continue
        if r.clearance is not None:
            cands.append(r.clearance)
            continue
        unread += sum(1 for k in getattr(r, "unread", ()) if k < 2 and land[k])
        for k, e in enumerate(r.ends):
            c = (e.ground - e.top, e.why)
            every.append(c)
            if not (k < len(lines_abut[d]) and lines_abut[d][k]):
                cands.append(c)
    got = cands or every
    return (*max(got, key=lambda c: c[0]), unread) if got else None


def free_bridge_zeros(staged: _t.Sequence[_t.Any], surface: _ar.Surface, *,
                      origin: tuple[float, float], agl_m: float, step_m: float,
                      walk_max_m: float = 0.0, level_tol_m: float = 0.0,
                      counts: "dict | None" = None) -> dict[str, tuple[float, str, tuple]]:
    """``{deck resource: (zero, why, ring box)}`` of every free bridge in a
    frame (module doc), or ``{}``.  ``staged`` are the frame's staged
    members (``placement_record.Staged``: ``m``); the ring box is
    ``(lat0, lon0, lat1, lon1)``."""
    from .deck_end_read import deck_end_reads
    decks = [st for st in staged if free_member(st.m)]
    if not decks:
        return {}
    reads = [deck_end_reads(st.m, surface, origin=origin, agl_m=agl_m, step_m=step_m,
                            walk_max_m=walk_max_m, level_tol_m=level_tol_m)
             for st in decks]
    groups: dict[str, list[int]] = {}
    for i, st in enumerate(decks):
        groups.setdefault(str(st.m.free_bridge), []).append(i)
    out: dict[str, tuple[float, str, tuple]] = {}
    for bid, group in sorted(groups.items()):
        abut = [[not land for land in decks[i].m.deck_end_land] for i in group]
        got = _bridge_zero([reads[i] for i in group], abut)
        if got is None:
            continue
        why = f"{got[1]}; {bid}" if len(group) == 1 else \
            f"{got[1]}; {bid}, one bridge of {len(group)} decks (RULINGS 2026-10-22o)"
        if got[2]:
            # #2065 A3 rule 10: an unread land end is counted and noted
            why += f"; free_end_unread {got[2]} (the terrain holds its ends)"
            if counts is not None:
                counts["free_end_unread"] = counts.get("free_end_unread", 0) + int(got[2])
        for i in group:
            ring = decks[i].m.deck_ring
            box = (min(q[0] for q in ring), min(q[1] for q in ring),
                   max(q[0] for q in ring), max(q[1] for q in ring))
            out[str(decks[i].m.resource)] = (got[0], why, box)
    if out and counts is not None:
        counts["free_bridge_frames"] = counts.get("free_bridge_frames", 0) + 1
    return out


def _overlap(a: tuple, b: tuple) -> float:
    """Intersection over union of two ``(lat0, lon0, lat1, lon1)`` plan
    boxes (a deck's own rails share its box; a neighbour's larger box that
    merely contains it scores less)."""
    inter = (max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
             * max(0.0, min(a[3], b[3]) - max(a[1], b[1])))
    union = ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)
    return inter / union if union > 0.0 else 0.0


def _deck_of_body(b: _t.Any, resource: str,
                 zeros: _t.Mapping[str, tuple[float, str, tuple]]) -> "str | None":
    """The deck of a free bridge frame this body moves with: the deck its
    footprint names (``Body.bridge_of``, §16e (3)), else its own member's
    when that member is the deck, else in a ONE-deck frame that deck, else
    the deck whose ring box its plan box overlaps most, by intersection
    over union (a curved ramp's
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
    """Every body of ``record`` at the zero of its deck (:func:`_deck_of_body`);
    a body no deck takes keeps its own seat."""
    if not zeros:
        return record
    from .open_frame_seat import at_zero
    res = str(getattr(m, "resource", "") or "")
    out = record
    for key, (zero, why, _box) in zeros.items():
        def take(b, _k=key, _z=zero):
            return (_deck_of_body(b, res, zeros) == _k and b.anchor.surface_z is not None
                    and abs(float(b.anchor.surface_z) - float(b.anchor.y_zero) - _z) > 1e-6)
        out = at_zero(out, m, zero, take, f"{REASON} {zero:.2f} ({why})")
    return out
