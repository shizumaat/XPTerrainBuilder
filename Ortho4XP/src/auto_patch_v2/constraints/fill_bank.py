"""THE BANK'S TOE IS ON THE GROUND: one loop for every graded-ground family
whose toe meets the lidar.

* THE OLD-DEM FILL (owner RULINGS 2026-11-06a (2); #1915; spec
  ``docs/specs/old-dem-fill-spec.md`` §2 (3): "its TOE vertices carry the
  ground datum (z = DEM, the toe is on current ground)").  A fill-bank piece
  (``planar/fill_bank``) carries the weak ground datum at the fill's level
  on every vertex (``solve/design_ground``), and the bending term rounds a
  steep embankment's toe and crest off it: MEASURED on the FHSH capture,
  the bank's ring stood up to 4.1 m off its fill, its toe 3.2 m over the
  DEM the core mesh meets there.  So every vertex of a bank piece that
  stands on the patch's open edge (an edge with no face beyond it: the toe,
  or the stand-off gap beside a road terrace) and belongs to bank pieces
  alone is pinned at its sampled level — the fill's, which is the DEM's at
  the toe and the terrace's beside a road.  Its crest, shared with the zone
  bands, keeps the zone law.
* A DECK STACK'S GROUND (#1971; spec ``interchange-levels-v2-20261113.md``
  §3.3 R4): the same rule on ``planar/stack_ground``'s pieces, on the
  stack's TOE only (the edge of ``airport/deck_stack.ground_footprint``'s
  outline): its stand-off gaps beside a road ribbon or the floor's void
  band are held by the stack's own rows (R1 / R2), and there the sampled
  level is the raw DEM, not the neighbour's.

No airport is named (RULINGS 2026-10-05e)."""
from __future__ import annotations

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Pin, Row, Source
from ..model.planar import PlanarMap, is_fill_bank_ref, is_stack_ground_ref

__all__ = ["fill_toe_pins", "GEN", "RULING", "STACK_RULING"]

GEN = "fill_toe_pins"
RULING = "zones.adjacent_ground old-DEM fill toe"
STACK_RULING = "RULINGS 2026-11-13g / 2026-11-11b: a deck stack's ground meets the lidar at its toe"


def _stack_toe(planar: PlanarMap, law: Law, airport: Airport):
    """``xy -> bool``: on a stack's toe (its ground outline's edge, off the
    floor's keep), within the identity grid."""
    import shapely

    from ..airport.deck_ends import ground_footprint
    stacks = tuple(getattr(airport, "deck_stacks", ()) or ())
    if not stacks:
        return lambda _xy: False
    grid = float(law.tables.emit.identity.min_distinct_spacing_m)
    lines = []
    for st in stacks:
        fp = ground_footprint(st, law)
        lines.append(fp["outline"].boundary.difference(fp["keep"].buffer(grid)))
    toe = shapely.union_all(lines).buffer(grid)
    shapely.prepare(toe)
    return lambda xy: bool(shapely.contains_xy(toe, xy[0], xy[1]))


def fill_toe_pins(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """One hard pin per open-edge vertex of a bank family's toe (docstring)."""
    rows: list[Row] = []
    seen: set[int] = set()
    for is_ref, ruling, toe in ((is_fill_bank_ref, RULING, None),
                                (is_stack_ground_ref, STACK_RULING, _stack_toe)):
        bank = {f.id for f in planar.faces.values() if is_ref(f.ref)}
        if not bank:
            continue
        on_toe = toe(planar, law, airport) if toe is not None else None
        for e in planar.edges.values():
            if (e.left_face is None) == (e.right_face is None):
                continue
            if (e.left_face if e.left_face is not None else e.right_face) not in bank:
                continue
            for v in (e.a, e.b):
                vx = planar.vertices[v]
                if v in seen or vx.dem_z is None or not set(vx.incident_faces) <= bank:
                    continue
                if on_toe is not None and not on_toe(vx.xy):
                    continue
                seen.add(v)
                rows.append(Pin(v, float(vx.dem_z), Source(GEN, ruling, (f"vertex:{v}",))))
    return rows
