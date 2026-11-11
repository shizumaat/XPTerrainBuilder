"""The app's two modes, Build and Fly (RULINGS 2026-11-11k; Library mode,
10j's third, is retired: a remembered "library" restores Build).

Pure: no Qt, no engine.  The Qt window (``O4_Qt_Modes``) reads it; the
Mac app's ``AppMode.swift`` holds the same keys, words and offer rule, and
``tests/test_app_modes.py`` holds the two equal.

- One map, one selection; the side pane follows the mode.
- The app remembers the last mode (:data:`PREF_KEY`).
- When X-Plane answers with a flight loaded while the app is in another
  mode, the app OFFERS Fly (:class:`FlyOffer`); it never switches by
  itself.  "A flight loaded" is read from the imagery follow job's status
  (``ImageryFollowStatus``): X-Plane's Web API answers and positions
  arrive.  A new flight load (``flight_loads`` grows) offers again.
"""

from __future__ import annotations

__all__ = ["MODES", "DEFAULT", "PREF_KEY", "FLY_PLACEHOLDER", "OFFER_TEXT",
           "OFFER_OPEN", "OFFER_DISMISS", "restore", "flight_loaded",
           "FlyOffer"]

#: The modes, left to right in the segmented control.
MODES = ("build", "fly")
DEFAULT = "build"
#: The app preference that remembers the last mode (Mac: UserDefaults
#: ``AppMode``; Qt: prefs ``app_mode``).
PREF_KEY = "app_mode"

#: Fly mode's pane before a flight is named (spec §4.3).
FLY_PLACEHOLDER = ("Name a flight and the app makes the scenery for it: the "
                   "departure ready before you fly, the route built ahead of "
                   "you, the destination while you fly.")
OFFER_TEXT = "X-Plane has a flight loaded."
OFFER_OPEN = "Open Fly"
OFFER_DISMISS = "Not now"

#: Follow-job states in which X-Plane's positions arrive.
_CONNECTED_STATES = ("following", "paused")


def restore(value) -> str:
    """The remembered mode, or :data:`DEFAULT` for anything unknown."""
    return value if value in MODES else DEFAULT


def flight_loaded(state: str, xplane: bool) -> bool:
    """X-Plane answers with a flight loaded (positions arrive)."""
    return bool(xplane) and state in _CONNECTED_STATES


class FlyOffer:
    """When to show the "Open Fly" banner.  Feed every follow status to
    :meth:`observe`; :attr:`shown` says whether the banner shows."""

    def __init__(self):
        self.shown = False
        self._loaded = False
        self._loads = 0

    def observe(self, state: str, xplane: bool, flight_loads: int, mode: str) -> bool:
        loaded = flight_loaded(state, xplane)
        new_flight = loaded and (not self._loaded or flight_loads > self._loads)
        if new_flight and mode != "fly":
            self.shown = True
        if not loaded or mode == "fly":
            self.shown = False
        self._loaded = loaded
        self._loads = max(self._loads, flight_loads)
        return self.shown

    def dismiss(self):
        """"Not now" (or "Open Fly"): hidden until the next flight."""
        self.shown = False
