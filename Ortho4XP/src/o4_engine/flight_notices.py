"""The flight's one-shot notices (spec flight-manager-and-world-20261110
§5.3 ``FlightNotice``, §4.3, §11; lane F2, capability ``flight_notices``):
the words of each code, ready for a system notification in both apps
(Mac ``UNUserNotificationCenter``, Qt ``QSystemTrayIcon``).

:func:`notice` gives ``{code, title, text, severity}``; :class:`Board`
keeps which were posted so each fires once a flight (``tile_late`` and
``offline`` once per count change, never twice for the same count).
Pure.  No airport is named here: idents come from the plan.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

__all__ = ["CODES", "notice", "Board"]

#: Codes, their titles and severity (``info``, ``warning``).
CODES: Dict[str, tuple] = {
    "ready": ("Departure ready", "info"),
    "reloading_on_ground": ("Scenery reloads now", "info"),
    "falling_behind": ("Building is behind", "warning"),
    "tile_late": ("Building is behind", "warning"),
    "destination_ready": ("Destination ready", "info"),
    "destination_late": ("Destination after a reload", "warning"),
    "diversion_ready": ("Diversion ready", "info"),
    "reload_announced": ("Scenery reloads in 30 s", "warning"),
    "offline": ("No internet for part of the route", "warning"),
    "budget": ("Not enough disk space", "warning"),
    "arrived": ("Flight complete", "info"),
}


def _minutes(seconds: Optional[float]) -> str:
    if seconds is None or seconds < 60:
        return "under a minute"
    return "%d min" % math.floor(seconds / 60.0)


def notice(code: str, *, origin: str = "", destination: str = "",
           count: int = 0, margin_s: Optional[float] = None,
           detail: str = "") -> dict:
    """The notice of ``code`` (see :data:`CODES`)."""
    title, severity = CODES[code]
    place = destination or "the destination"
    text = {
        "ready": "Your flight %sto %s is ready for departure."
                 % ("from %s " % origin if origin else "", place),
        "reloading_on_ground": "The new scenery goes in with one reload, "
                               "on the ground, before departure.",
        "falling_behind": detail or "Building is behind at this speed.",
        "tile_late": "%d tile(s) ahead will show X-Plane's own scenery."
                     % count,
        "destination_ready": "Scenery for %s is in place, %s before it loads."
                             % (place, _minutes(margin_s)),
        "destination_late": "%s will be ready after X-Plane loads its area: "
                            "the scenery reloads once near the ground, "
                            "30 s after a notice." % place,
        "diversion_ready": "Scenery for %s is in place." % place,
        "reload_announced": "Scenery for %s is ready. The scenery reloads "
                            "in 30 s; choose Not now to keep flying "
                            "without it." % place,
        "offline": "%d tile(s) en route need the internet to be built. You "
                   "can fly with X-Plane's own scenery there." % count,
        "budget": detail or "This flight's tiles do not fit the disk budget.",
        "arrived": "Arrived at %s." % place,
    }[code]
    return {"code": code, "title": title, "text": text,
            "severity": severity}


class Board:
    """Which notices this flight has posted (see the module)."""

    def __init__(self) -> None:
        self._posted: Dict[str, int] = {}
        self.pending: List[dict] = []

    def post(self, code: str, key: int = 0, **fields) -> bool:
        """Queue ``code`` unless it was posted with this ``key`` (a count,
        or 0 for once a flight)."""
        if code in self._posted and self._posted[code] >= key:
            return False
        self._posted[code] = key
        self.pending.append(notice(code, **fields))
        return True

    def drain(self) -> List[dict]:
        out, self.pending = self.pending, []
        return out
