"""A TRENCH STACK'S END-SEATED DECKS, PREDICTED AT THE PACK STAGE (#2116
item 3; owner RULINGS 2026-11-18c with 2026-10-22m).

18c seats a deck of an object floor's frame by its own end lines -- flush
at the lower of the two roads it lands on -- at the OBJECT stage, after the
mesh (``airport/floor_deck_ends.end_lifts``).  A deck stack's ground
(``planar/stack_ground``) is minted before that, and it mints end aprons for
the stack's own decks only, so the trench's bank ran on past such a deck's
end lines 1.3-2.4 m under its seated top (KDEN ``Over_Train_Bridge.obj``,
lkden7's attribution).  This module runs THE SAME RULE
(``floor_deck_ends.read_seat``) on every member of a TRENCH stack that is
not one of its decks, placed at the stack's zero, with the road ground
PREDICTED: the median lidar under the stations of each end's approach band
that stand on a mapped at-grade road's ribbon (``road_ways``,
``ribbon_half_width_m``), where the object stage reads the drawn road
faces.  A deck it seats is published on ``DeckStack.end_seated`` with its
tops over the zero WITH the predicted lift; the stack's ground then gives
it end aprons at its plate top (22m: the ground meets the deck at its end
lines) and the end-line roads are held there (``model/deck_ends``).  The
object stage still seats the deck on the drawn surface.

Geometry only: nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np

from ..model.deck_stack import TRENCH, DeckStack, StackDeck
from .floor_deck_ends import EndSeat, faces_of, law_of, place, read_seat

__all__ = ["seat_stacks"]


def _road_ground(airport, law, fl) -> _t.Callable[[np.ndarray, np.ndarray], "float | None"]:
    """``end_ground(edge stations, outward)`` (``floor_deck_ends.
    read_seat``): the median lidar under the approach band's stations that
    stand on a mapped at-grade road's ribbon, the band walked as the object
    stage walks it; ``None`` where none does."""
    import shapely

    from .dem import dem_z_many
    from .road_ways import ribbon_half_width_m, road_ways
    ribbons = [ln.buffer(ribbon_half_width_m(getattr(w, "tags", None) or {}, law),
                         cap_style="flat")
               for w, ln in road_ways(getattr(airport, "osm_ways_mapped", None)
                                      or airport.osm_ways)]
    tree = shapely.STRtree(ribbons) if ribbons else None
    walk = np.arange(0.0, fl.step_m + 1e-9, fl.touch_m)

    def end_ground(edge: np.ndarray, out_dir: np.ndarray) -> "float | None":
        if tree is None or not len(edge):
            return None
        q = (edge[None, :, :] + walk[:, None, None] * out_dir[None, None, :]).reshape(-1, 2)
        on = np.unique(tree.query(shapely.points(q[:, 0], q[:, 1]), predicate="intersects")[0])
        if not len(on):
            return None
        z = dem_z_many(airport.dem, q[on, 0], q[on, 1])
        zs = sorted(float(v) for v in z if np.isfinite(v))
        return zs[len(zs) // 2] if zs else None
    return end_ground


def _deck(pid: str, res: str, st: DeckStack, got: EndSeat) -> StackDeck:
    """The seated deck as a stack deck: its plan's hull ring, its end
    edges' stations and its tops over the zero with its lift (level 0: no
    level of the stack)."""
    hull = got.plan.convex_hull.simplify(0.05)
    ring = tuple((float(x), float(y)) for x, y in hull.exterior.coords[:-1])
    a, b = (tuple((float(x), float(y)) for x, y in e) for e in got.edges)
    ta, tb = (float(t) - float(st.zero_z) + got.lift for t in got.top)
    return StackDeck(pid, res, 0, ring, 0, (), (), a, b, ta, tb)


def _one(st: DeckStack, by_id: dict, fl, end_ground, notes: list) -> DeckStack:
    """``st`` with its end-seated decks (module doc)."""
    own = {d.object_id for d in st.decks}
    memo: dict = {}
    placed = {}
    for pid, _res in st.members:
        o = by_id.get(pid)
        f = faces_of(str(o.resolved), memo) if o is not None and o.resolved else None
        placed[pid] = None if f is None else (
            f, place(f, float(o.xy[0]), float(o.xy[1]), float(o.heading_deg),
                          float(st.zero_z)))
    decks, grounds = [], []
    for pid, res in st.members:
        if pid in own or placed[pid] is None:
            continue
        mates = [p[1] for q, p in placed.items() if q != pid and p is not None]
        got = read_seat(placed[pid][1], placed[pid][0], mates, fl, end_ground)
        if got is None:
            continue
        decks.append(_deck(pid, str(res), st, got))
        grounds += [(pid, 0, s, round(g, 3)) for s, g in zip("ab", got.ground, strict=True)]
        k = got.flush
        notes.append(f"{st.walls_id}: {str(res).rsplit('/', 1)[-1]} {pid} seated by its end "
                     f"lines (RULINGS 2026-11-18c, predicted): lift {got.lift:+.2f}, end "
                     f"{'ab'[k]} flush with its road {got.ground[k]:.2f}, end {'ab'[1 - k]}'s "
                     f"road {got.ground[1 - k]:.2f}; end aprons at its plate top")
    if not decks:
        return st
    return _dc.replace(st, end_seated=tuple(decks), end_seated_ground=tuple(grounds))


def seat_stacks(stacks: _t.Sequence[DeckStack], airport, objects, law,
                notes: "list | None" = None) -> tuple[DeckStack, ...]:
    """``stacks`` with every TRENCH stack's end-seated decks (module doc);
    a stack with none, a free / kept stack, or no rule law: as given."""
    fl = law_of(law.tables.structures)
    if fl is None or getattr(airport, "dem", None) is None \
            or not any(st.kind == TRENCH for st in stacks):
        return tuple(stacks)
    by_id = {str(o.id): o for o in objects or () if getattr(o, "kind", "") == "OBJECT"}
    end_ground = _road_ground(airport, law, fl)
    out_notes: list[str] = []
    out = tuple(_one(st, by_id, fl, end_ground, out_notes) if st.kind == TRENCH else st
                for st in stacks)
    if notes is not None:
        notes.extend(out_notes)
    return out
