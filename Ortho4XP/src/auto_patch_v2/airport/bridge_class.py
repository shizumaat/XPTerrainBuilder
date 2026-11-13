"""ONE BRIDGE CLASSIFIER: a verdict per pack deck member (#2065; spec
``bridge-classifier-spec.md`` §1; RULINGS 2026-10-22m/n/p/d, 10-26d, 10-30a/f,
13r).

Every ``flag`` / ``signature`` deck gets exactly one class, read top to
bottom; the first that holds wins.  The classes before ``free_bridge`` are
their own readers' outcomes, passed in, never re-derived here — admission
stays theirs:

=================== ============================================ =====================
class               witness                                      reader
=================== ============================================ =====================
``stack_deck``      member of a deck stack (#1971)                ``airport/deck_stack``
``cut_deck``        its frame holds a pack object cut (10-26d)    ``cut_deck_seat``
``airside_hard_deck`` pavement runs across (A; 22n / 30a)         ``planar/deck_bridge``
``road_overpass``   a road beneath, not its own route (30f (5))   ``planar/overpass_deck``
``free_bridge``     W1-W6 (``airport/bridge_witness``; 22m/22p)   ``free_bridge_seat``
``all_deck_frame``  every member of its frame a deck (22d/22p)    ``placement_family``
``attached_bridge`` W1-W5 hold, W6 fails (22m (2), 10-03e)        the unit path
``graded_deck``     ``deck_datum_z`` set (§49)                    unchanged
``not_a_bridge``    else — reason: the first failed witness       today's path
=================== ============================================ =====================

13r: any doubt — a witness that fails — and the deck stays on today's path.
Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc

from .bridge_witness import Witness

__all__ = ["CLASSES", "DeckFacts", "Verdict", "classify"]

#: the classes in precedence order (module doc)
CLASSES: tuple[str, ...] = ("stack_deck", "cut_deck", "airside_hard_deck", "road_overpass",
                            "free_bridge", "all_deck_frame", "attached_bridge",
                            "graded_deck", "not_a_bridge")


@_dc.dataclass(frozen=True)
class DeckFacts:
    """What the readers already decided for one deck member, and its
    witness (``None`` = not read: no ring, no plate)."""

    in_stack: bool = False
    frame_cut: bool = False
    airside: bool = False
    overpass: bool = False
    all_deck_frame: bool = False
    graded: bool = False
    witness: "Witness | None" = None


@_dc.dataclass(frozen=True)
class Verdict:
    """One deck's class and why (the witness that decided it)."""

    cls: str
    reason: str


def _witness_holds(w: "Witness | None") -> bool:
    """W1-W5 hold, or the deck joined a W-deck's group as its stub."""
    return w is not None and (not w.failed or bool(w.joined))


def classify(f: DeckFacts) -> Verdict:
    """The deck's class (module doc), first that holds."""
    if f.in_stack:
        return Verdict("stack_deck", "a member of a deck stack")
    if f.frame_cut:
        return Verdict("cut_deck", "its frame holds a pack object cut")
    if f.airside:
        return Verdict("airside_hard_deck", "pavement runs across it")
    if f.overpass:
        return Verdict("road_overpass", "a road beneath that is not its own route")
    w = f.witness
    if _witness_holds(w) and not w.frame_failed:
        return Verdict("free_bridge", f"joins {w.joined}" if w.joined else w.span)
    if f.all_deck_frame:
        return Verdict("all_deck_frame", "every member of its frame is a deck")
    if _witness_holds(w):
        return Verdict("attached_bridge", w.frame_failed)
    if f.graded:
        return Verdict("graded_deck", "deck_datum_z set")
    return Verdict("not_a_bridge", w.failed if w is not None else "no plate read")
