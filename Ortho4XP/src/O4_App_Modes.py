"""The app's three modes, Build · Fly · Library (RULINGS 2026-11-10j).

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
           "OFFER_OPEN", "OFFER_DISMISS", "STORAGE_POINTER",
           "STORAGE_POINTER_BUTTON", "restore", "flight_loaded", "FlyOffer"]

#: The modes, left to right in the segmented control.
MODES = ("build", "fly", "library")
DEFAULT = "build"
#: The app preference that remembers the last mode (Mac: UserDefaults
#: ``AppMode``; Qt: prefs ``app_mode``).
PREF_KEY = "app_mode"

#: Fly mode's pane until the flight manager lands (spec §16 U1).
FLY_PLACEHOLDER = ("Flights come here: name a flight plan and the app makes "
                   "the scenery for it. Until then, the line below follows "
                   "X-Plane and sharpens the imagery around you.")
OFFER_TEXT = "X-Plane has a flight loaded."
OFFER_OPEN = "Open Fly"
OFFER_DISMISS = "Not now"
#: Settings ▸ Storage keeps a pointer to Library mode (10j).
STORAGE_POINTER = ("The data folder's sizes, Clear and the disk budget's use "
                   "are in Library.")
STORAGE_POINTER_BUTTON = "Show in Library"

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
