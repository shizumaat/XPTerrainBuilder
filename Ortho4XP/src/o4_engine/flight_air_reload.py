"""Rule S6 (b) of spec flight-manager-and-world-20261110 §7.5 (owner
RULINGS 2026-11-10k Q4; lane F2; owner 2026-11-12T14:34Z: "Never ask
x-plane to reload unless the user requests it."): the reload in the air
is OFFERED, never sent on its own.

When the destination (or a diversion airport) could not be in place
before X-Plane loaded its area, its tile waits staged (rule S4).  Once,
and only near the ground -- inside :data:`NEAR_KM` of that airport and
below :data:`LOW_AGL_M` above the ground -- the reload is offered (a
notice and "Reload scenery now"); it is sent only when the pilot presses
it (``flight_reload``).  Never for an en-route tile; never a second time
in one flight.

:class:`AirReload` is the state, as ``FlightStatus.reload`` spells it:
``""`` (nothing to do), ``offered``, ``sent``.  Pure: the caller passes
the clock and does the reload.
"""
from __future__ import annotations

__all__ = ["NEAR_KM", "LOW_AGL_M", "AirReload"]

#: "Near the ground" (§7.5 S6 (b)): within 20 km of the airport ...
NEAR_KM = 20.0
#: ... and below 3,000 ft above the ground.
LOW_AGL_M = 3000.0 * 0.3048


class AirReload:
    """See the module."""

    def __init__(self) -> None:
        self.state = ""

    def step(self, now: float, needed: bool, near: bool) -> str:
        """One tick: ``"offer"`` (post the notice; the pilot may press
        "Reload scenery now") or ``""``.  Never a send."""
        if self.state == "sent":
            return ""
        if not needed:
            self.state = ""
            return ""
        if self.state == "" and near:
            self.state = "offered"
            return "offer"
        return ""

    def press(self) -> bool:
        """The pilot asks for the reload (``flight_reload``): True when one
        is offered (the caller sends it)."""
        return self.state == "offered"

    def sent(self) -> None:
        self.state = "sent"
