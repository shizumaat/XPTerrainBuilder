"""The apps' text size (issue #827): View > Bigger Text / Smaller Text /
Actual Size, remembered between launches.

The steps and the one rule both apps follow -- the Qt window
(:mod:`O4_Qt_Text_Scale`, :mod:`O4_Qt_GUI`) and the macOS app
(``Sources/SceneryKit/TextScale.swift``, the Swift half) -- twinned on
``tests/fixtures/text_scale_cases.json``.

A scale is one of :data:`STEPS`; Bigger/Smaller move one step and stop
at the ends; a stored value that is not a step (hand-edited prefs, an
older step list) snaps to the nearest step, and an unreadable one is
Actual Size.
"""

from typing import Any

__all__ = [
    "STEPS",
    "DEFAULT",
    "PREF_KEY",
    "BIGGER_TITLE",
    "SMALLER_TITLE",
    "ACTUAL_TITLE",
    "clamp",
    "bigger",
    "smaller",
    "scaled",
]

STEPS = (0.85, 1.0, 1.15, 1.3, 1.45, 1.6)
DEFAULT = 1.0

# The Qt prefs key (the Mac app's UserDefaults key is TextScale.prefKey,
# the same string).
PREF_KEY = "text_scale"

BIGGER_TITLE = "Bigger Text"
SMALLER_TITLE = "Smaller Text"
ACTUAL_TITLE = "Actual Size"


def clamp(value: Any) -> float:
    """The step nearest ``value``; :data:`DEFAULT` when it is not a
    positive number."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return DEFAULT
    if not number > 0:  # also rejects NaN
        return DEFAULT
    return min(STEPS, key=lambda step: (abs(step - number), step))


def bigger(value: Any) -> float:
    """One step up from ``value``; the largest step stays."""
    index = STEPS.index(clamp(value))
    return STEPS[min(index + 1, len(STEPS) - 1)]


def smaller(value: Any) -> float:
    """One step down from ``value``; the smallest step stays."""
    index = STEPS.index(clamp(value))
    return STEPS[max(index - 1, 0)]


def scaled(points: float, value: Any) -> float:
    """``points`` at text scale ``value``, rounded to a half point."""
    return round(points * clamp(value) * 2.0) / 2.0
