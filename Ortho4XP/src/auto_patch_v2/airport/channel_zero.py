"""A CHANNEL'S PACK FRAME SITS AT THE ZERO ITS FLOOR WAS READ AT (#1883).

Where the pack states a channel's floor (§45 (3) (i), ``datum_source ==
"pack"``), the planar stage read the floor as its witness placement's
deepest genuine solid at that placement's own zero (``planar/
channel_floor``): the floor IS the witness's floor.  The object stage then
seated each body of the frame on the channel's RIM (``anchor_rule.
_basin_rim_anchor``: "the object's zero is the rim"), and a channel's rim
is a design crest that climbs and falls along a kilometre of cut, so one
pack frame took as many zeros as it had bodies.  MEASURED LGAV (FlyTampa's
trench stack on one anchor, the motorway and the rail line in the cut):
the liner pieces' bottoms stood at 58.6, 63.4, 68.8 against the 66.47
floor -- the owner's "not seated right, its bottom has to be at the bottom
of the cut" (1.0.465).

THE RULE: the witness's plate (``pipeline/rebake_inputs._channel_plates``,
``plate_kind == "channel:<n>"``, its ``plate_y`` the deepest solid's y)
gives the zero -- the solved floor at the plate's stations less that y --
and every body of the unit that the rim of THAT channel would seat
(``channel_wall:<n>#...``) takes it instead: one frame, one zero, its
floor on the floor.  A deck seated over a pack cut and what stands on it
(``cut_deck_seat``) are read after this and keep their own seats.

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import typing as _t

__all__ = ["CHANNEL_KIND", "channel_zeros", "rim_channel"]

#: ``rebake_inputs.CHANNEL_PLATE``'s prefix, repeated here so the object
#: stage imports nothing from the pipeline
CHANNEL_KIND = "channel:"
_RIM = "basin rim (channel_wall:"


def channel_zeros(members: _t.Iterable[_t.Any], surface: _t.Any) -> dict[str, float]:
    """``{channel number: zero}`` off every channel-witness member's plate."""
    out: dict[str, float] = {}
    for m in members:
        kind = str(getattr(m, "plate_kind", "") or "")
        y = getattr(m, "plate_y", None)
        st = tuple(getattr(m, "plate_stations", ()) or ())
        if not kind.startswith(CHANNEL_KIND) or y is None or not st:
            continue
        zs = [z for z in (surface(float(q[0]), float(q[1])) for q in st) if z is not None]
        if zs:
            out.setdefault(kind[len(CHANNEL_KIND):], sum(zs) / len(zs) - float(y))
    return out


def rim_channel(body: _t.Any) -> "str | None":
    """The channel number whose rim seated ``body``, or ``None``."""
    r = str(getattr(getattr(body, "anchor", None), "reason", "") or "")
    if not r.startswith(_RIM):
        return None
    return r[len(_RIM):].split("#", 1)[0]
