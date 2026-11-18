"""THE BANK UNDER EVERY BRIDGE DECK (owner RULINGS 2026-11-17p, #1717:
"EVERY bridge -- pack bridge objects (road and taxiway decks) as well as
our generated bridges -- shares the logic just added for ESSA's
auto-generated bridges: the cut under the bridge extends 1 m past the
bridge, then blends back to the cut and natural terrain").

A deck the pack models no walls under (``DeckBridge.walls`` empty, or a
wall on one side only: a generated deck, a wall-less pack hard deck) stands
on a BANK: from each end
line down to the cut's floor at :func:`deck_bank_slope`, the bank running
:func:`bank_past_m` beyond the deck's ring before the ground beyond blends.
Its readers are the ONE derivation of that bank:

* ``planar/structures`` -- a GENERATED deck's floor face (``planar/
  deck_bridge.deck_cut``) stops at the bank's toe; a pack deck's floor face
  keeps the 1:3 run (MEASURED KIAH: widened, it pulled the pack decks and
  their taxiways down 1-2 m), the bank's rows carrying the ground down to
  the floor's level beyond the toe;
* ``planar/deck_bridge.deck_ground`` -- the deck's own ground reaches
  :func:`bank_past_m` past the ring;
* ``constraints/edge_deck`` -- the span rows hold that ground ON the bank
  (never flush with the seats), to :func:`bank_past_m` past the ring;
* ``planar/deck_generated`` -- the generated deck's size reads the run;
* ``planar/deck_skirt`` -- the free ground round the deck the bank blends
  out over (#2141: run-on, then the deepest end's depth at the slope).

A WALLED deck (``planar/deck_walls``, RULINGS 2026-10-30f (3)) keeps its
walls: the pack states the cut's shape there and the fill behind them is
flush with the deck (``deck_bridge._walled_trench``).
Nothing here names an airport.
"""
from __future__ import annotations

__all__ = ["deck_bank_slope", "bank_past_m", "banked"]


def deck_bank_slope(law) -> float:
    """The bank under a bridge deck: 1V:1.5H, the steep engineered-fill face
    (``zones.adjacent_ground.old_dem_fill_slope``, the one law key that
    states it).  The deck hides it; ``emit.design.bank_slope`` (1:3, a slope
    a pilot reads as ground) is the OPEN ground's.  Owner 2026-11-17 18:30Z
    (ESSA 86aefaf4 over the service road -141): "seems to be larger than it
    needs to be" -- at 1:3 a 6 m floor ran 18 m of bank each side; owner sim
    read 19:42Z: "The embankment under bridges should be a bit steeper";
    17p: every bridge shares it."""
    return float(law.tables.zones.adjacent_ground.old_dem_fill_slope)


def bank_past_m(law) -> float:
    """How far the bank under a deck runs past its ring before the ground
    beyond blends (``[bridge] bank_past_edge_m``; owner sim read
    2026-11-17T19:42Z "that embankment needs to extend about 1m past the
    bridge edges")."""
    return float(law.tables.structures.bridge.bank_past_edge_m)


def banked(db) -> bool:
    """Whether ``db`` stands on a bank (module doc): the pack models no wall
    on one side of the road under it or the other -- the planar cut's own
    test (``deck_bridge._walled_trench``: a deck walled on one side only is
    cut as a banked one, MEASURED LFPG ``H16`` obj13023), so the span rows
    and the deck's ground read the cut the planar stage made.  The same
    inner-face test as ``_walled_trench`` (``geom/wall_lines``): here in
    ``model`` because ``constraints`` may not import ``planar``."""
    walls = getattr(db, "walls", ())
    if not walls:
        return True
    from ..geom.wall_lines import inner_faces, project_span
    r, n, faces = walls
    u_lo, u_hi = project_span(db.ring, n)
    s_lo, s_hi = project_span(db.ring, r)
    ua, ub = inner_faces(faces, s_lo, s_hi, 0.5 * (u_lo + u_hi))
    return ua is None or ub is None
