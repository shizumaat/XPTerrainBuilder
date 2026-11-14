"""A FREE OR KEPT BRIDGE AS A FLOORLESS DECK STACK (#2065 A3 rules 1-3, 10;
RULINGS 2026-11-14d / e / f; spec ``docs/specs/2065-bridge-class-A3.md``).

Read once at the pack stage (``planar/free_bridge.attach_free_bridges``),
after the trench stacks: every bridge the positive witness holds — the FREE
bridges (``Airport.free_bridges``) and the decks of ALL-DECK frames
(``Airport.kept_bridges``, 14d) — gets its ZERO and the STATE of each land
end (``airport/bridge_end_state``); a bridge with a GRADED end becomes a
:class:`~..model.deck_stack.DeckStack` of kind ``free`` / ``kept`` (no floor,
no walls, no caps), whose ground and rows the trench stack's passes mint.

THE ZERO, fixed here and never re-derived (rule 2), through the SAME
functions the object stage calls, on a member-shaped view of the pack
object (the fields ``rebake_plan`` stamps) and a DEM surface:

* FREE: ``free_bridge_seat._bridge_zero`` over ``deck_end_read.
  deck_end_reads`` — the highest ``G_e - top_e`` over the land ends, a 22p
  clearance one candidate (R2's rule).  Every land end not held or listed
  is then held to it (R1).
* KEPT: today's reader, ``bridge_approach.approach_seat`` (rectangle ends,
  ``datum.y``, 22p) = the PREDICTED seat; the end it seats flush (the
  GOVERNING end) and a 22p anchor get no row and no ground.

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import types
import typing as _t

from ..model.deck_stack import FREE, KEPT, STACK_PREFIX, DeckStack, StackDeck
from ..model.free_bridge import published

__all__ = ["bridge_stacks", "log_lines"]


class _DemSurface:
    """``(lat, lon) -> DEM z`` (``None`` off it), with ``water(lat, lon)``
    off the DEM's water witness over ``box`` (the object stage's surface
    shape, ``anchor_rule.Surface``)."""

    def __init__(self, airport, box) -> None:
        from .dem import dem_z_many
        self._xy, _ll = airport.frame.transformers()
        self._dem = airport.dem
        self._z = dem_z_many
        fn = getattr(airport.dem, "water_geometry", None)
        w = None
        if callable(fn):
            try:
                w = fn(box)
            except Exception:                             # pragma: no cover
                w = None
        self._water = None if w is None or w.is_empty else w
        self.water = self._wet if self._water is not None else None

    def __call__(self, lat: float, lon: float) -> "float | None":
        import numpy as np
        x, y = self._xy(lon, lat)
        z = float(self._z(self._dem, np.array([x]), np.array([y]))[0])
        return z if math.isfinite(z) else None

    def _wet(self, lat: float, lon: float) -> bool:
        from shapely.geometry import Point
        x, y = self._xy(lon, lat)
        return bool(self._water.contains(Point(x, y)))


def _box(rings, pad: float = 60.0) -> tuple:
    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)


def _view(o, to_ll, **fields) -> types.SimpleNamespace:
    """The member-shaped view of pack deck ``o`` (``rebake_plan._with_deck``'s
    fields) the object-stage readers take."""
    from .rebake_plan import _deck_ring_xy
    ring = tuple(to_ll(x, y) for x, y in _deck_ring_xy(o))
    base = dict(resource=str(o.path), deck_ring=ring, deck_kind=str(o.deck_kind or ""),
                deck_top_y=float(o.deck_top_z - o.anchor_z - o.agl_m), deck_datum_z=None,
                heading_deg=float(o.heading_deg or 0.0), authored_path="", parts=(),
                plate_y=None, plate_kind="", plate_stations=(), deck_end_stations=(),
                deck_ends=None)
    base.update(fields)
    return types.SimpleNamespace(**base)


def _ground(chord_ll, surface, step: float) -> float:
    """G_e: ``bridge_approach.end_ground`` over the end chord's stations
    (``rebake_plan.end_line_stations``), the read ``approach_seat`` makes."""
    from .bridge_approach import end_ground
    from .rebake_plan import end_line_stations
    g = end_ground(end_line_stations([tuple(chord_ll)], step), surface,
                   getattr(surface, "water", None))
    return float(g[0]) if g is not None else math.nan


def _plate(o, cache):
    import shapely
    from .deck_stack import _plate_tris
    hd = o.hard_deck
    piece = max(shapely.get_parts(hd), key=lambda g: g.area) if hd.geom_type != "Polygon" else hd
    return _plate_tris(o, cache, piece)


def _stack(bid: str, kind: str, members, decks, ends, zero: float, notes) -> DeckStack:
    return DeckStack(
        id=STACK_PREFIX + bid, walls_id="", walls_resource="", members=tuple(members),
        zero_z=float(zero), zero_spread_m=0.0,
        end_zeros=tuple((e.object_id, 0, e.side, round(e.ground, 3), round(e.top, 3))
                        for e in ends if math.isfinite(e.ground)),
        feet_y=0.0, crest_y=0.0, floor=(), rim=(), runouts=(), under_ways=(),
        decks=tuple(decks), notes=tuple(notes), kind=kind, ends=tuple(ends), bridge=bid)


def _stack_deck(o, cache, d) -> StackDeck:
    ea, eb = (d.ends + (None, None))[:2]
    return StackDeck(str(o.id), str(o.path), 0, tuple(d.ring), 1, tuple(d.ways), (),
                     tuple(ea.stations) if ea else (), tuple(eb.stations) if eb else (),
                     float(ea.top) if ea else 0.0, float(eb.top) if eb else 0.0,
                     tuple(tuple(tuple(float(v) for v in p) for p in t)
                           for t in _plate(o, cache)))


class _Ctx:
    """What every bridge's read shares (one per pack stage)."""

    def __init__(self, airport, objects, cache, law) -> None:
        from .bridge_end_state import Obstacles
        br = law.tables.structures.bridge
        self.airport, self.cache, self.law = airport, cache, law
        self.by_id = {str(o.id): o for o in objects}
        self.to_xy, self.to_ll = airport.frame.transformers()
        self.step = float(br.abutment_sample_step_m)
        self.out_m = float(br.free_end_ground_out_m)
        self.walk = float(br.abutment_walk_max_m)
        self.tol = float(law.tables.structures.placement.split_tol_m)
        zeros = {str(pid): float(s.zero_z) for s in getattr(airport, "deck_stacks", ()) or ()
                 for pid, _r in s.members}
        self.obs = Obstacles(airport, objects, cache, law, zeros)

    def surface(self, rings) -> _DemSurface:
        return _DemSurface(self.airport, _box(rings))

    def ends(self, fb, d, o, zero, surface, chords, governing=frozenset()) -> list:
        """Every land end of deck ``d`` of bridge ``fb``, its state read."""
        from .bridge_end_state import end_state
        out = []
        for k, e in enumerate(d.ends):
            if not e.land:
                continue
            side = "ab"[k]
            g = _ground(chords[k], surface, self.step)
            st = end_state(oid=d.object_id, side=side, stations=e.stations, top=e.top,
                           out=e.out, ground=g, zero=zero, carried=d.ways,
                           stub=bool(d.stub_of), own=set(fb.members), obs=self.obs,
                           law=self.law)
            if side in governing:
                st = _dc.replace(st, state="governing",
                                 why=f"the predicted seat's flush end ({st.why})")
            out.append(st)
        return out


def _free_one(fb, cx: _Ctx) -> "tuple[DeckStack | None, list[str], bool]":
    """``(the bridge's stack or None, notes, refused)`` of one FREE bridge
    (module doc; rule 10: an unread land end of a bridge with no stack
    refuses it).  The stack is returned whether or not it has a GRADED end
    (the caller mints only those that do)."""
    from .deck_end_read import deck_end_reads
    from .free_bridge_seat import _bridge_zero
    pub = published([fb], cx.to_ll, cx.out_m)
    objs = [cx.by_id.get(d.object_id) for d in fb.decks]
    if any(o is None for o in objs):
        return None, [f"{fb.id}: a deck is not in the pack read"], False
    surface = cx.surface([d.ring for d in fb.decks])
    views, reads = [], []
    for d, o in zip(fb.decks, objs, strict=True):
        rec = pub.get(d.object_id)
        if rec is None:
            views.append(None)
            reads.append(None)
            continue
        from .rebake_plan import _free_fields
        v = _view(o, cx.to_ll, **_free_fields(rec, cx.step))
        views.append(v)
        reads.append(deck_end_reads(v, surface, origin=cx.to_ll(*o.xy), agl_m=float(o.agl_m),
                                    step_m=cx.step, walk_max_m=cx.walk, level_tol_m=cx.tol))
    abut = [[not x for x in (v.deck_end_land if v else ())] for v in views]
    got = _bridge_zero(reads, abut)
    if got is None:
        return None, [f"{fb.id}: no land end read on the DEM — no zero"], True
    zero, why, unread = got
    notes = [f"{fb.id}: zero {zero:.3f} ({why})"]
    ends = []
    for d, o in zip(fb.decks, objs, strict=True):
        rec = pub.get(d.object_id)
        if rec is not None:
            ends += cx.ends(fb, d, o, zero, surface, rec["ends"])
    if unread:
        notes.append(f"{fb.id}: free_end_unread {unread} land end(s) read nowhere (rule 10)")
    graded = any(e.state == "graded" for e in ends)
    if not graded:
        notes.append(f"{fb.id}: no GRADED end — no stack")
    decks = [_stack_deck(o, cx.cache, d) for d, o in zip(fb.decks, objs, strict=True)]
    decks += _own_decks(fb, cx)
    return _stack(fb.id, FREE, [(m, str(cx.by_id[m].path) if m in cx.by_id else "")
                                for m in fb.members], decks, ends, zero, notes), notes, \
        bool(unread) and not graded


def _own_decks(fb, cx: _Ctx) -> list[StackDeck]:
    """Rule 8: the other hard decks of the bridge's OWN frame (B01's approach
    slabs) are the bridge — no ends, the ground stays under them (R3)."""
    from shapely.geometry import Polygon as _P
    have = set(fb.deck_ids())
    out = []
    for m in fb.members:
        o = cx.by_id.get(m)
        hd = getattr(o, "hard_deck", None) if o is not None else None
        if m in have or hd is None or hd.is_empty or o.deck_top_z is None:
            continue
        ring = max(getattr(hd, "geoms", [hd]), key=lambda g: g.area)
        if not isinstance(ring, _P):
            continue
        out.append(StackDeck(str(o.id), str(o.path), 0,
                             tuple((float(x), float(y)) for x, y in ring.exterior.coords[:-1]),
                             0, (), (), (), (), 0.0, 0.0,
                             tuple(tuple(tuple(float(v) for v in p) for p in t)
                                   for t in _plate(o, cx.cache))))
    return out


def _mid(stations) -> tuple[float, float]:
    """The mean of an end line's stations."""
    return (sum(p[0] for p in stations) / len(stations),
            sum(p[1] for p in stations) / len(stations))


def _rect_ends(o, view, to_ll) -> "tuple | None":
    """The kept deck's RECTANGLE end lines as the plan stamps them
    (``rebake_plan._with_deck``: a signature plate's ends, else the ring's)."""
    from .rebake_plan import _reads_datum, ring_ends
    pl = getattr(o, "deck_plate", None)
    if not _reads_datum(o) and pl is not None and pl.ends is not None:
        return tuple(tuple(to_ll(x, y) for x, y in e) for e in pl.ends)
    return ring_ends(view.deck_ring)


def _kept_one(fb, cx: _Ctx) -> "tuple[list[DeckStack], list[DeckStack], list[str]]":
    """``(minted, every read, notes)``: the KEPT stacks of one all-deck
    bridge, one per deck (each deck of an all-deck frame keeps its own 22d /
    22p seat)."""
    from .anchor_rule import datum_of
    from .bridge_approach import approach_seat
    out, every, notes = [], [], []
    for d in fb.decks:
        o = cx.by_id.get(d.object_id)
        if o is None or len(d.ends) != 2:
            continue
        view = _view(o, cx.to_ll)
        view.deck_ends = _rect_ends(o, view, cx.to_ll)
        datum = datum_of(view, abutment_step_m=cx.step, abutment_walk_max_m=cx.walk,
                         level_tol_m=cx.tol, free_standing=True)
        surface = cx.surface([d.ring])
        origin = cx.to_ll(*o.xy)
        seat = None if datum is None else approach_seat(datum, surface, origin=origin,
                                                        authored_agl_m=float(o.agl_m))
        tag = f"{d.object_id} {str(o.path).rsplit('/', 1)[-1]}"
        if seat is None:
            notes.append(f"{tag}: kept, no predicted seat on the DEM (an end on water or "
                         "off it) — nothing graded, listed")
            continue
        gov: set[str] = set()
        if "authored clearance" not in seat.reason:
            k = max(range(len(seat.ends)), key=lambda i: (seat.ends[i], -i))
            a, b = datum.ends[k]
            mid = cx.to_xy((a[1] + b[1]) / 2.0, (a[0] + b[0]) / 2.0)
            near = min(range(2), key=lambda j: math.dist(mid, _mid(d.ends[j].stations)))
            gov.add("ab"[near])
        pub = published([_dc.replace(fb, decks=(d,))], cx.to_ll, cx.out_m)[d.object_id]
        ends = cx.ends(fb, d, o, seat.zero, surface, pub["ends"], frozenset(gov))
        note = f"{tag}: kept, predicted seat {seat.zero:.3f} ({seat.reason})"
        notes.append(note)
        st = _stack(f"kept:{d.object_id}", KEPT, [(m, str(cx.by_id[m].path)
                                                   if m in cx.by_id else "")
                                                  for m in fb.members],
                    [_stack_deck(o, cx.cache, d)], ends, seat.zero, [note])
        every.append(st)
        if any(e.state == "graded" for e in ends):
            out.append(st)
    return out, every, notes


def bridge_stacks(airport, objects, cache, law
                  ) -> tuple[tuple[DeckStack, ...], tuple[DeckStack, ...], frozenset[str],
                             list[str]]:
    """``(the free and kept stacks minted — those with a GRADED end; every
    bridge read, minted or not (the census's rows); the free bridges refused
    (rule 10); notes)`` (module doc)."""
    free = tuple(getattr(airport, "free_bridges", ()) or ())
    kept = tuple(getattr(airport, "kept_bridges", ()) or ())
    if not (free or kept) or getattr(airport, "dem", None) is None or law is None:
        return (), (), frozenset(), []
    cx = _Ctx(airport, objects, cache, law)
    out: list[DeckStack] = []
    every: list[DeckStack] = []
    refused: set[str] = set()
    notes: list[str] = []
    for fb in free:
        st, n, ref = _free_one(fb, cx)
        notes += n
        if st is not None:
            every.append(st)
            if st.graded_ends():
                out.append(st)
        if ref:
            refused.add(fb.id)
            notes.append(f"{fb.id}: REFUSED as free (rule 10: an unread land end and no "
                         "stack) — today's path, listed")
    for fb in kept:
        st, ev, n = _kept_one(fb, cx)
        out += st
        every += ev
        notes += n
    return tuple(out), tuple(every), frozenset(refused), notes


def log_lines(icao: str, stacks: _t.Sequence[DeckStack]) -> list[str]:
    """One line per land end of the free / kept stacks (the census's rows)."""
    out = []
    for st in stacks:
        if st.kind not in (FREE, KEPT):
            continue
        for e in st.ends:
            out.append(f"[{icao}] [bridge-end] {st.id} {e.object_id} {e.side} {e.state}: "
                       f"gap {e.gap:+.2f} run {e.run:.0f} m at {e.grade:.2%} — {e.why}")
    return out

