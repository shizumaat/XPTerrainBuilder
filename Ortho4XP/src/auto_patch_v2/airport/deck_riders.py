"""A BRIDGE AUTHORED AS SEVERAL FILES ON ONE ROW SEATS AS ONE BRIDGE (#2086).

Owner RULINGS 2026-10-22d (a free-standing bridge's deck sits flush with the
terrain at its ends, its supports sinking or floating as they must) and
2026-10-22m ("they should always move as a group") read a frame — one plan
unit, every row at one anchor spelling — as a bridge when EVERY member of
it is a deck (``placement_family.frame_is_bridge``).  A pack may author one
bridge as two files: the deck surface (a ``signature`` deck: its plate and
its mapped bridge way) and the structure carrying it — parapets, sides,
piers — which the signature pass names a member of the deck's FAMILY with
no plate of its own ("seats with its deck", ``deck_signature._apply``).
Read member by member, that frame is not all-deck, so the deck took the
generic low-side foot and the structure took its OWN low-side foot: LEMG's
motorway viaduct (1.0.519) drew its structure 13-19 m over the ground and
its deck 16 m under the structure, its ends buried up to 1.3 m.

THE RIDER WITNESS.  A plateless family member RIDES a deck of its own frame
when EVERY one of its parts' plan centroids stands on that deck's model
footprint, within §16e (3)'s contact reach (``bridge_family.CONTACT_M``, the
same polygon and reach that names a body's ``bridge_of``).  A frame whose
every member is a deck or a rider is a bridge: its decks take the
free-standing deck-top datum (22d) and each rider takes the datum of the
deck it rides, so the whole frame takes ONE zero.  A terminal's frame whose
family members stand beside its decks (measured over the shared plans:
6-91 % of their family parts off every deck print) is not a bridge and
reads as before.

The relation is per frame, never partial: one family part off every deck
leaves the whole frame to today's reading (lane ``v2bridgecontact`` measured
a PARTIALLY bound bridge worse than an unbound one, ``bridge_family``).
Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import typing as _t

from .bridge_family import CONTACT_M, DeckPrint
from .placement_family import DECK_VERDICTS

__all__ = ["FAMILY_KIND", "FrameDatums", "end_tops", "riding_frames"]

#: ``Member.deck_kind`` of a member of an accepted deck family that has no
#: plate of its own (``deck_signature._apply``)
FAMILY_KIND = "family"


def _kind(m: _t.Any) -> str:
    return str(getattr(m, "deck_kind", "") or "")


def _deck_ridden(m: _t.Any, prints: _t.Sequence[DeckPrint]) -> "int | None":
    """The member index of the deck every part of ``m`` stands on, or None."""
    parts = tuple(getattr(m, "parts", ()) or ())
    if not parts:
        return None
    lats = [float(p.lat) for p in parts]
    lons = [float(p.lon) for p in parts]
    for pr in prints:
        if all(pr.contains_many(lats, lons, CONTACT_M)):
            return int(pr.member)
    return None


def riding_frames(plan: _t.Any, prints: _t.Sequence[DeckPrint]
                  ) -> dict[tuple[int, int], int]:
    """``(unit, member) -> the member whose datum it takes`` (its own index
    for a deck, its deck's for a rider) over every frame that holds a
    plateless deck-family member and is otherwise all decks, every such
    member riding one of the frame's own decks (module doc).  Frames
    ``frame_is_bridge`` already reads are not listed."""
    by_unit: dict[int, list[DeckPrint]] = {}
    for pr in prints:
        by_unit.setdefault(int(pr.unit), []).append(pr)
    out: dict[tuple[int, int], int] = {}
    for ui, u in enumerate(getattr(plan, "units", ()) or ()):
        ms = tuple(getattr(u, "members", ()) or ())
        kinds = [_kind(m) for m in ms]
        if (FAMILY_KIND not in kinds or not any(k in DECK_VERDICTS for k in kinds)
                or any(k not in DECK_VERDICTS and k != FAMILY_KIND for k in kinds)):
            continue
        own = by_unit.get(ui, [])
        seats: dict[int, int] = {}
        for mi, m in enumerate(ms):
            if kinds[mi] in DECK_VERDICTS:
                seats[mi] = mi
                continue
            deck = _deck_ridden(m, own)
            if deck is None:
                seats = {}
                break
            seats[mi] = deck
        out.update({(ui, mi): d for mi, d in seats.items()})
    return out


#: the deck's own vertices this far beyond the nearest one to an end line
#: are read as its end (a vertex pair of one end edge differs by a rounding)
_END_BAND_M = 1.0


def end_tops(deck: _t.Any, ends: _t.Sequence, origin: tuple[float, float]
             ) -> "tuple[float, ...] | None":
    """The deck top AT each end line: the highest of the deck file's own
    vertices nearest the end line's midpoint (within ``_END_BAND_M`` of the
    nearest).  A deck authored on a grade meets each end at its own height
    (LEMG's viaduct: -0.25 at one end, -1.53 at the other, +1.28 at its
    crown).  None where the file does not parse."""
    import math
    import os

    import numpy as np

    from . import obj8 as _obj8
    from .rebake_plan import _mpd
    path = str(getattr(deck, "authored_path", "") or "")
    if not path or not os.path.isfile(path):
        return None
    try:
        v = np.asarray(_obj8.parse_obj8(path).vertices, float)[:, :3]
    except (OSError, ValueError):
        return None
    if not len(v):
        return None
    h = math.radians(float(getattr(deck, "heading_deg", 0.0) or 0.0))
    c, sn = math.cos(h), math.sin(h)
    east, north = v[:, 0] * c - v[:, 2] * sn, -(v[:, 0] * sn + v[:, 2] * c)
    ml, mo = _mpd(float(origin[0]))
    out = []
    for a, b in ends[:2]:
        mx = (0.5 * (float(a[1]) + float(b[1])) - float(origin[1])) * mo
        my = (0.5 * (float(a[0]) + float(b[0])) - float(origin[0])) * ml
        d = np.hypot(east - mx, north - my)
        out.append(float(v[d <= float(d.min()) + _END_BAND_M, 1].max()))
    return tuple(out)


class FrameDatums:
    """The ONE datum of each riding frame's bridge, read once per deck: the
    deck's free-standing deck-top datum (22d) with the deck top AT each end
    line (:func:`end_tops`; 22m then sets the end flush), handed to every
    member of the frame that rides that deck."""

    def __init__(self, plan: _t.Any, rides: _t.Mapping[tuple[int, int], int],
                 step_m: float, walk_max_m: float, tol_m: float) -> None:
        self._plan, self._rides = plan, rides
        self._kw = {"abutment_step_m": step_m, "abutment_walk_max_m": walk_max_m,
                    "level_tol_m": tol_m, "free_standing": True}
        self._step = float(step_m)
        self._memo: dict[tuple[int, int], _t.Any] = {}

    def of(self, ui: int, mi: int) -> _t.Any:
        """The datum member ``mi`` of unit ``ui`` takes, or None (not a
        rider frame, or its deck carries no datum: today's reading)."""
        d = self._rides.get((ui, mi))
        if d is None:
            return None
        key = (ui, d)
        if key not in self._memo:
            self._memo[key] = self._read(self._plan.units[ui], self._plan.units[ui].members[d])
        return self._memo[key]

    def _read(self, u: _t.Any, deck: _t.Any) -> _t.Any:
        import dataclasses as _dc

        from . import anchor_rule as _ar
        datum = _ar.datum_of(deck, **self._kw)
        if datum is None or len(datum.ends) < 2:
            return datum
        tops = end_tops(deck, datum.ends, (float(u.anchor[0]), float(u.anchor[1])))
        return datum if tops is None else _dc.replace(datum, tops=tops)
