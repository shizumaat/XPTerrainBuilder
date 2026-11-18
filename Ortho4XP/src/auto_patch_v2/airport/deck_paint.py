"""THE PAINT ON A GENERATED DECK (spec ``docs/specs/2123.md`` A2; Q4 as
ruled 16y; issue #2123): an apt.dat ``120`` line the region cut dropped
(``apt_edit.Dropped``), redrawn on the deck's top as the stripes X-Plane
itself paints for that line type.

X-Plane drapes apt.dat lines on the TERRAIN MESH, never on an object, so
a deck must carry its own paint.  The table below is X-Plane's own line
SPECIFICATION, read from ``Resources/default scenery/sim objects/
apt_lines/<n>_*.lin`` (``SCALE`` across / along, ``TEX_WIDTH``,
``S_OFFSET``) and the alpha pattern of its paint texture (where the
stripe is solid and where it is dashed) on 2026-11-16 -- the numbers
only, never the art: each stripe is ``(offset across the line m, width
m, colour, dash)`` with ``dash = (on m, off m)`` or ``None`` for solid,
the offsets centred on the stripes' own middle.  ``51``-``64`` (``_b``)
lay a black under-stripe first.  A line type not in the table (red,
orange, blue, green guidance) is not painted.

Build-time impact: a few hundred quads per deck, written by the object
stage.
"""
from __future__ import annotations

from shapely.geometry import LineString

__all__ = ["STRIPES", "stripes_of", "dashed_pieces", "light_names"]

Stripe = tuple[float, float, str, "tuple[float, float] | None"]
_D = (0.375, 0.375)            # a 3 m texture repeat holds four dashes
_HOLD = (0.938, 0.562)
_PARK = (1.664, 1.336)

#: line type -> its stripes, the under-stripe first (module doc)
STRIPES: dict[int, tuple[Stripe, ...]] = {
    1: ((0.0, 0.141, "yellow", None),),
    2: ((0.0, 0.141, "yellow", _D),),
    3: ((-0.117, 0.141, "yellow", None), (0.117, 0.141, "yellow", None)),
    4: ((-0.352, 0.141, "yellow", _D), (-0.117, 0.141, "yellow", _D),
        (0.117, 0.141, "yellow", None), (0.352, 0.141, "yellow", None)),
    5: ((-0.117, 0.141, "yellow", _D), (0.117, 0.141, "yellow", None)),
    6: ((0.0, 0.703, "yellow", (0.141, 0.609)),),
    7: ((-0.164, 0.094, "yellow", _HOLD), (0.0, 0.141, "yellow", None),
        (0.164, 0.094, "yellow", _HOLD)),
    8: ((0.0, 0.141, "yellow", _PARK),),
    9: ((-0.117, 0.141, "yellow", _PARK), (0.117, 0.141, "yellow", _PARK)),
    10: ((0.0, 0.234, "yellow", None),),
    11: ((-0.273, 0.156, "yellow", (1.562, 0.938)), (0.0, 0.234, "yellow", None),
         (0.273, 0.156, "yellow", (1.562, 0.938))),
    12: ((-0.703, 0.281, "yellow", (0.75, 0.75)), (-0.234, 0.281, "yellow", (0.75, 0.75)),
         (0.234, 0.281, "yellow", None), (0.703, 0.281, "yellow", None)),
    13: ((-0.234, 0.281, "yellow", (0.75, 0.75)), (0.234, 0.281, "yellow", None)),
    14: ((0.0, 1.406, "yellow", (0.281, 1.219)),),
    19: ((0.0, 0.984, "yellow", None),),
    20: ((0.0, 0.141, "white", None),),
    21: ((0.0, 0.375, "white", (0.336, 0.331)),),
    22: ((0.0, 0.141, "white", (1.25, 1.25)),),
    23: ((0.0, 0.141, "white", _D),),
    24: ((0.0, 0.234, "white", None),),
    25: ((0.0, 0.234, "white", (0.625, 0.625)),),
}
#: the black under-stripe of each ``_b`` type (its base type is ``t - 50``)
_UNDER: dict[int, Stripe] = {
    51: (0.0, 0.281, "black", None), 52: (0.0, 0.281, "black", None),
    53: (0.0, 0.516, "black", None), 54: (0.0, 0.984, "black", None),
    55: (0.0, 0.516, "black", None), 56: (0.0, 0.844, "black", None),
    57: (0.0, 0.516, "black", None), 58: (0.0, 0.281, "black", None),
    59: (0.0, 0.516, "black", None), 60: (0.0, 0.391, "black", None),
    61: (0.0, 0.859, "black", None), 62: (0.0, 1.969, "black", None),
    63: (0.0, 1.031, "black", None), 64: (0.0, 1.688, "black", None),
    70: (0.0, 0.281, "black", None), 71: (0.0, 0.375, "black", None),
    72: (0.0, 0.281, "black", None), 73: (0.0, 0.281, "black", None),
    74: (0.0, 0.391, "black", None), 75: (0.0, 0.391, "black", None),
}


def stripes_of(line_type: int) -> tuple[Stripe, ...]:
    """The stripes of ``line_type``, the black under-stripe first; ``()``
    for a type the table does not paint."""
    if line_type in _UNDER:
        return (_UNDER[line_type], *STRIPES.get(line_type - 50, ()))
    return STRIPES.get(line_type, ())


def dashed_pieces(line: LineString, dash: "tuple[float, float] | None"
                  ) -> list[LineString]:
    """``line`` itself (solid) or its dashes: ``on`` metres painted,
    ``off`` left, from the line's start (X-Plane restarts its texture
    repeat at each line; the phase is not read)."""
    from shapely.ops import substring
    if dash is None:
        return [line]
    on, off = dash
    out, s, L = [], 0.0, line.length
    while s < L:
        e = min(L, s + on)
        if e - s > 0.02:
            out.append(substring(line, s, e))
        s += on + off
    return out


def light_names(light: int) -> tuple[str, ...]:
    """The OBJ8 named lights (``lights.txt``) for an apt.dat ``120``
    light code (Q4 as ruled: kept as ``taxi_g`` / ``taxi_g_rev``): ``101``
    the green bidirectional taxiway centreline, ``107`` the one-way one,
    ``102`` the blue taxiway EDGE light (``taxi_b``, #2132 spec
    2132-design section 4); ``()`` for the rest (hold and stop-bar
    lights: not redrawn)."""
    return {101: ("taxi_g", "taxi_g_rev"), 102: ("taxi_b",),
            107: ("taxi_g",)}.get(int(light), ())
