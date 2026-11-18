"""WHICH OBJECT FLOORS OWN GROUND -- the read every layer asks of a
``airport/object_floor.ObjectFloor`` (duck-typed: ``hidden``,
``footprint``, ``rim_banks``, ``rim_tops``), kept in ``model`` so
``constraints`` may ask it too (M0 §1: constraints import law + model;
#1949 R3's ``constraints/fill_bank`` toe reads the banked pits).

No airport is named (RULINGS 2026-10-05e)."""
from __future__ import annotations

import typing as _t

__all__ = ["owns_ground", "has_footprint", "banked_floors"]


def owns_ground(f) -> bool:
    """Does ``f`` own any ground — cut cells, pins, portal and mouth seats
    (A4: a shallower surface inside a deeper one owns none; 2026-11-06d (1):
    a HIDDEN shell owns none, it leaves the terrain solve)?"""
    return not f.hidden and has_footprint(f)


def has_footprint(f) -> bool:
    """Does ``f`` state a cut's extent — its footprint, read as a WITNESS
    even when hidden (2026-11-06d (1): the deck pieces over it, the cut ring
    the object stage seats them by)?"""
    fp = f.footprint
    return fp is not None and not fp.is_empty and fp.area > 0.0


def banked_floors(floors: _t.Sequence) -> list:
    """The floors that own their ground and state open-edge rims (#1949 R3,
    ``planar/pit_bank``)."""
    return [f for f in floors if getattr(f, "rim_banks", False) and f.rim_tops
            and owns_ground(f)]
