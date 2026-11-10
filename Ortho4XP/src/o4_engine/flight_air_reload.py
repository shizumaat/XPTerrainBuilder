"""Rule S6 (b) of spec flight-manager-and-world-20261110 §7.5 (owner
RULINGS 2026-11-10k Q4; lane F2): the one scenery reload in the air.

When the destination (or a diversion airport) could not be in place
before X-Plane loaded its area, its tile waits staged (rule S4).  Once,
and only near the ground -- inside :data:`NEAR_KM` of that airport and
below :data:`LOW_AGL_M` above the ground -- the reload is ANNOUNCED
:data:`ANNOUNCE_S` ahead with "Not now".  Not pressed: it is sent.
"Not now": it is only offered from then on, and the pilot presses it
(``flight_reload``).  Never for an en-route tile; never a second time in
one flight.

:class:`AirReload` is the state, as ``FlightStatus.reload`` spells it:
``""`` (nothing to do), ``scheduled`` (announced, sent at ``due_at``),
``offered`` (after "Not now"), ``sent``.  Pure: the caller passes the
clock and does the reload.
"""
from __future__ import annotations

from typing import Optional

__all__ = ["NEAR_KM", "LOW_AGL_M", "ANNOUNCE_S", "AirReload"]

#: "Near the ground" (§7.5 S6 (b)): within 20 km of the airport ...
NEAR_KM = 20.0
#: ... and below 3,000 ft above the ground.
LOW_AGL_M = 3000.0 * 0.3048
#: The announcement comes this far ahead of the reload (RULINGS 10k Q4).
ANNOUNCE_S = 30.0


class AirReload:
    """See the module."""

    def __init__(self) -> None:
        self.state = ""
        self.due_at: Optional[float] = None

    def step(self, now: float, needed: bool, near: bool) -> str:
        """One tick: ``"announce"`` (post the 30 s notice), ``"send"``
        (reload now, then :meth:`sent`), or ``""``."""
        if self.state == "sent":
            return ""
        if not needed:
            self.state, self.due_at = "", None
            return ""
        if self.state == "" and near:
            self.state, self.due_at = "scheduled", now + ANNOUNCE_S
            return "announce"
        if self.state == "scheduled" and now >= (self.due_at or now):
            return "send"
        return ""

    def not_now(self) -> bool:
        """The pilot's "Not now": the announced reload is held back and
        stays offered.  False when nothing was announced."""
        if self.state != "scheduled":
            return False
        self.state, self.due_at = "offered", None
        return True

    def press(self) -> bool:
        """The pilot asks for the reload (``flight_reload``): True when one
        is announced or offered (the caller sends it)."""
        return self.state in ("scheduled", "offered")

    def sent(self) -> None:
        self.state, self.due_at = "sent", None
