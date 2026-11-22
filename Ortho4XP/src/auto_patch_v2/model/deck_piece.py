"""ONE HARD-DECK PIECE OF A REBAKE MEMBER (walled-multibridge-frames spec W9).

``Member.deck_ring`` is a deck's LARGEST polygon only (kept for its old
readers); ``Member.deck_rings`` carries EVERY piece as a :class:`DeckPiece`:
its ring, its tag -- ``airside`` or ``road`` for a span the planar map
witnessed (``planar/deck_bridge``, ``DeckBridge.family``), ``rider`` for a
piece no witness holds (it rides the cell it stands in, W2 (c)) -- and, for
a span, its own end-line stations, each station's deck top off the frame's
mean and its own span cut ``(a, b, ((s_a, s_b), ...), cap)`` (``a``, ``b``
in ``(lat, lon)``; ``DeckBridge.span_cut``).  The object stage cuts a frame
whose pieces carry two or more cuts into cells (``airport/deck_plates``).

No airport is named (RULINGS 2026-10-05e)."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from .frame import LL

__all__ = ["DeckPiece", "SPAN_TAGS", "RIDER"]

#: the tags of a witnessed span (W2 (a) airside, W2 (b) a road deck)
SPAN_TAGS = ("airside", "road")
#: the tag of a piece no witness holds (W2 (c))
RIDER = "rider"


@_dc.dataclass(frozen=True)
class DeckPiece:
    """One hard-deck piece (module doc)."""

    ring: tuple[LL, ...]
    tag: str = RIDER
    stations: tuple[LL, ...] = ()
    tops: tuple[float, ...] = ()
    span_cut: tuple = ()

    def to_dict(self) -> dict[str, _t.Any]:
        d: dict[str, _t.Any] = {"ring": [[a, b] for a, b in self.ring], "tag": self.tag}
        if self.stations:
            d["stations"] = [[a, b] for a, b in self.stations]
            d["tops"] = list(self.tops)
        if self.span_cut:
            a, b, spans, *cap = self.span_cut
            d["span_cut"] = [list(a), list(b), [list(q) for q in spans], *cap]
        return d

    @classmethod
    def from_dict(cls, d: _t.Mapping[str, _t.Any]) -> "DeckPiece":
        cut: tuple = ()
        if d.get("span_cut"):
            a, b, spans, *cap = d["span_cut"]
            cut = ((float(a[0]), float(a[1])), (float(b[0]), float(b[1])),
                   tuple((float(x), float(y)) for x, y in spans),
                   *(None if c is None else float(c) for c in cap[:1]))
        return cls(tuple((float(a), float(b)) for a, b in d.get("ring", ())),
                   str(d.get("tag") or RIDER),
                   tuple((float(a), float(b)) for a, b in d.get("stations", ())),
                   tuple(float(t) for t in d.get("tops", ())), cut)
