"""THE GENERATED DECKS STAGE 1 WITHHOLDS (owner RULINGS 2026-11-19s (1);
``planar/deck_airside``): which of the full map's generated decks stage 1's
map leaves out, and the no-bridge measurement arm.  Model-level so the
planar cut and the constraints (``constraints/deck_floor_follow``, which may
not import ``planar``) read ONE answer.  Moved from ``planar/deck_airside``
unchanged.  Nothing here names an airport.
"""
from __future__ import annotations

import contextlib
import typing as _t

__all__ = ["withheld", "no_bridge_arm"]

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
    from .stage_one import deriving, full_map
    from .structures import is_generated
    full = full_map()
    if _ARM:
        if full is None and decks:
            _ARM[-1][:] = [d for d in decks if is_generated(d)]
        return tuple(_ARM[-1])
    if full is None or not deriving():
        return ()
    return tuple(d for d in getattr(full, "decks", ()) or () if is_generated(d))
