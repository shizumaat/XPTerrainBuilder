"""First-visit guidance on the map, and the empty states (issue #828).

The words and the one rule both apps follow -- the Qt window
(:mod:`O4_Qt_Map_Hint`, :mod:`O4_Qt_GUI`) and the macOS app
(``Sources/SceneryKit/MapGuidance.swift``, the Swift half) -- twinned on
``tests/fixtures/map_guidance_cases.json``.

The hint over the map shows until it is DISMISSED, and stays dismissed
across launches: the user's first selection dismisses it, so does its
close button, and Help > Show Tips brings it back (until the next
selection or close).
"""

from typing import Iterable, List

__all__ = [
    "HINT_TEXT",
    "SHOW_TIPS_TITLE",
    "EMPTY_SELECTION_TEXT",
    "NOTHING_BUILT_TEXT",
    "HINT_DISMISSED_PREF",
    "SELECTED",
    "DESELECTED",
    "CLOSED",
    "SHOW_TIPS",
    "dismissed_after",
    "visibility",
]

HINT_TEXT = "Search your airport, or click its square on the map. Drag to move the map."
SHOW_TIPS_TITLE = "Show Tips"
EMPTY_SELECTION_TEXT = (
    "Nothing is selected yet. A tile is one 1° × 1° square of the map. "
    "Building it downloads imagery and elevation for that square and "
    "fits the runways, taxiways and aprons of every airport in it to "
    "the terrain.")
NOTHING_BUILT_TEXT = (
    "No tiles built yet. Search your airport or click its square, then "
    "press Build.")

# The Qt prefs key (the Mac app's UserDefaults key is
# PrefKeys.mapHintDismissed, the same string).
HINT_DISMISSED_PREF = "map_hint_dismissed"

# Events the rule reacts to.
SELECTED = "selected"        # the selection became non-empty
DESELECTED = "deselected"    # the selection became empty
CLOSED = "closed"            # the hint's close button
SHOW_TIPS = "show_tips"      # Help > Show Tips


def dismissed_after(dismissed: bool, event: str) -> bool:
    """The hint's dismissed state after ``event``."""
    if event in (SELECTED, CLOSED):
        return True
    if event == SHOW_TIPS:
        return False
    return dismissed


def visibility(dismissed: bool, events: Iterable[str]) -> List[bool]:
    """Whether the hint shows after each of ``events``, from a stored
    ``dismissed`` state (the hint shows exactly when not dismissed)."""
    shown = []
    for event in events:
        dismissed = dismissed_after(dismissed, event)
        shown.append(not dismissed)
    return shown
