"""THE NO-BRIDGE AIRSIDE: STAGE 1 IS SOLVED AS IF NO GENERATED BRIDGE STOOD
(owner RULINGS 2026-11-19s (1); ``docs/specs/airside-first-bridges-spec.md``
section 1 row 2).

A deck WE generate (``planar/deck_generated``) never moves airside.  Stage
1's map (``pipeline/stage_one_map``, derived under ``model/stage_one.
from_full``) is the airside problem, so the generated decks of the full map
are WITHHELD from it (:func:`withheld`): no deck record, no ring cut out of
the pavement, no deck ground, no survey keep-out, no anchor and no bore
under the ring (:func:`drop_bores`).  Its ring is FILLED instead
(:func:`fill_rings`): one cell of the carried route's pavement role over
the whole ring, so the taxiway spans the road on its own grade law; the
covered roads under it are covered ground (``planar/covered_ground``: the
bare-earth trench never reaches ``Vertex.dem_z`` there).  The full map
builds the deck, its cut and its carve as before; stage 2 solves them with
every airside vertex a constant (``constraints/deck_floor_follow``).

Nothing here names an airport.  Build-time impact: one shapely knife per
airport with a generated deck, on stage 1's map only.
"""
from __future__ import annotations

import contextlib
import dataclasses as _dc
import typing as _t

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

__all__ = ["withheld", "fill_rings", "drop_bores", "FILL_MARK", "no_bridge_arm"]

#: the evidence mark of a ring's fill cell (and of every cell the ring cut)
FILL_MARK = "deck_fill"

#: THE NO-BRIDGE MEASUREMENT ARM (``tools/v2_solve_replay.py --no-bridge``,
#: never a build): the full map withholds its generated decks too, so the
#: whole build is the no-bridge solve the 19s bar is read against
_ARM: list[list] = []


@contextlib.contextmanager
def no_bridge_arm() -> _t.Iterator[None]:
    """Inside, the FULL map withholds its own generated decks (``_ARM``)."""
    _ARM.append([])
    try:
        yield
    finally:
        _ARM.pop()


def withheld(decks: _t.Sequence = ()) -> tuple:
    """The full map's GENERATED decks while stage 1's map is derived
    (``model/stage_one``: inside ``stage_one()`` under ``from_full``);
    ``()`` on the full map -- but under :func:`no_bridge_arm` the full
    map's own (``decks``, recorded for its stage 1)."""
    from ..model.stage_one import deriving, full_map
    from ..model.structures import is_generated
    full = full_map()
    if _ARM:
        if full is None and decks:
            _ARM[-1][:] = [d for d in decks if is_generated(d)]
        return tuple(_ARM[-1])
    if full is None or not deriving():
        return ()
    return tuple(d for d in getattr(full, "decks", ()) or () if is_generated(d))


def _carried(cells, polys, ring: Polygon, air: _t.AbstractSet[str]):
    """The airside cell the ring carries most of (its overlap with the ring
    grown 2 m: a ring over a pack's hole touches the pavement only at its
    ends), or ``None``."""
    grown = ring.buffer(2.0)
    best, area = None, 0.0
    for c, p in zip(cells, polys, strict=True):
        if c.role not in air or p.is_empty or not p.intersects(grown):
            continue
        a = p.intersection(grown).area
        if a > area:
            best, area = c, a
    return best


def fill_rings(classification, decks: _t.Sequence, law, airport=None
               ) -> tuple[_t.Any, list[str]]:
    """``classification`` with each deck's ring cut out of every cell and
    filled by ONE cell of the pavement role it carries (module doc), and a
    note per deck; ``airport`` runs its taxi routes on across the fill
    (``planar/route_lines``).  Unchanged with no deck."""
    if not decks or classification is None:
        return classification, []
    from ..law.tables import rolled_on_roles
    from ..classify.roles import Cell
    from .cell_knife import knife_cells
    from .deck_bridge import deck_polygon
    polys = []
    for c in classification.cells:
        p = Polygon(c.ring, c.holes) if len(c.ring) >= 3 else Polygon()
        polys.append(p if p.is_valid else p.buffer(0.0))
    air = rolled_on_roles(law)
    fills, notes, rings = [], [], []
    for d in decks:
        ring = deck_polygon(d)
        if ring.is_empty or ring.area < 1.0:
            continue
        src = _carried(classification.cells, polys, ring, air)
        if src is None:
            notes.append(f"{d.object_id}: no airside pavement meets its ring -- not filled")
            continue
        rings.append(ring)
        fills.append(Cell(0, src.role, f"{src.ref}#{FILL_MARK}:{d.object_id}",
                          tuple(ring.exterior.coords)[:-1], (), src.code_number,
                          src.code_letter, src.side, src.kind,
                          {**dict(src.evidence or {}), FILL_MARK: 1.0}))
        notes.append(f"{d.object_id}: stage 1 solves the airside with no bridge -- its "
                     f"{ring.area:,.0f} m2 ring is {src.role} ({src.ref}) over the road "
                     f"(RULINGS 2026-11-19s (1))")
    if not fills:
        return classification, notes
    cells, n = knife_cells(classification.cells, polys, unary_union(rings), law, (),
                           cut_pads=True, mark=FILL_MARK, new_cells=fills)
    notes.append(f"{n} cell(s) cut under {len(fills)} withheld generated deck ring(s)")
    # the taxi route runs on across the fill (``planar/route_lines``)
    from .route_lines import with_route_lines
    out, n_lines = with_route_lines(_dc.replace(classification, cells=tuple(cells)), airport,
                                    rings)
    if n_lines:
        notes.append(f"{n_lines} taxi centreline piece(s) across the filled ring(s)")
    return out, notes


def drop_bores(ways: _t.Sequence, decks: _t.Sequence) -> tuple[list, int]:
    """``(ways, n dropped)``: every bore way running more than a metre
    inside a withheld deck's ring dropped (the road under the bridge is the
    carve's, stage 2's: stage 1 has none)."""
    if not decks:
        return list(ways), 0
    from .deck_bridge import deck_polygon
    rings = unary_union([deck_polygon(d) for d in decks])
    out = [w for w in ways if len(w.points) < 2
           or LineString(w.points).intersection(rings).length <= 1.0]
    return out, len(ways) - len(out)
