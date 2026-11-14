"""ONE BRIDGE CLASSIFIER: a verdict per pack deck member (#2065; spec
``bridge-classifier-spec.md`` §1; RULINGS 2026-10-22m/n/p/d, 10-26d, 10-30a/f,
13r).

Every ``flag`` / ``signature`` deck gets exactly one class, read top to
bottom; the first that holds wins (order as amended by
``2065-bridge-class-A1.md`` §A1).  The classes before the witness's are
their own readers' outcomes, passed in, never re-derived here — admission
stays theirs:

=================== ============================================ =====================
class               witness                                      reader
=================== ============================================ =====================
``stack_deck``      member of a deck stack (#1971)                ``airport/deck_stack``
``cut_deck``        its frame holds a pack object cut (10-26d)    ``cut_deck_seat``
``airside_hard_deck`` pavement runs across (A; 22n / 30a)         ``planar/deck_bridge``
``road_overpass``   a road beneath, not its own route (30f (5))   ``planar/overpass_deck``
``all_deck_frame``  every member of its frame a deck (22d/22p)    ``placement_family``
``plated_deck``     W1-W7 + W4b hold, an edge / walled /          its plate's reader
                    split_level plate
``free_bridge``     W1-W7 + W4b (``airport/bridge_witness``)      ``free_bridge_seat``
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

__all__ = ["CLASSES", "DeckFacts", "classify", "witness_holds"]

#: the classes in precedence order (module doc)
CLASSES: tuple[str, ...] = ("stack_deck", "cut_deck", "airside_hard_deck", "road_overpass",
                            "all_deck_frame", "plated_deck", "free_bridge",
                            "attached_bridge", "graded_deck", "not_a_bridge")


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
    #: carries an ``edge`` / ``walled`` / ``split_level`` plate
    plated: bool = False
    witness: "Witness | None" = None


@_dc.dataclass(frozen=True)
class Verdict:
    """One deck's class and why (the witness that decided it)."""

    cls: str
    reason: str


def _witness_holds(w: "Witness | None") -> bool:
    """W1-W5 hold, or the deck joined a W-deck's group as its stub."""
    return w is not None and (not w.failed or bool(w.joined))


def witness_holds(w: "Witness | None") -> bool:
    """The whole witness holds: W1-W5 (or a joined stub), W6, W7 and W4b."""
    return _witness_holds(w) and not w.frame_failed and not w.end_failed


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
    if f.all_deck_frame:
        return Verdict("all_deck_frame", "every member of its frame is a deck")
    w = f.witness
    if witness_holds(w):
        if f.plated:
            return Verdict("plated_deck", "carries an edge / walled / split_level plate")
        return Verdict("free_bridge", f"joins {w.joined}" if w.joined else w.span)
    if _witness_holds(w) and w.frame_failed:
        return Verdict("attached_bridge", w.frame_failed)
    if f.graded:
        return Verdict("graded_deck", "deck_datum_z set")
    if w is None:
        return Verdict("not_a_bridge", "no plate read")
    return Verdict("not_a_bridge", w.end_failed if _witness_holds(w) else w.failed)
