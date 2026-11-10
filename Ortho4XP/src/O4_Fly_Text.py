"""The Fly pane's words (spec flight-manager-and-world-20261110 §4.3,
§6.2, §14; lane U2).

Pure: no Qt, no engine, no I/O.  The Qt pane (``O4_Qt_Fly_Pane``) reads
it; the Mac app's ``Sources/SceneryKit/FlyText.swift`` holds the same
words and rules, and ``tests/test_fly_pane.py`` holds the two equal
through the shared fixture ``tests/fixtures/fly_pane_cases.json``.

The plan-tier words "placeholder", "drape", "light" never reach the user
(§14): the map legend says :data:`LEGEND`.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

import O4_Flight_Plan as FP
import O4_Flight_Schedule as FS
import O4_Glossary as GLOSSARY

__all__ = [
    "PLAN_SOURCE_LABEL", "PLAN_CHOOSE", "PLAN_SIMBRIEF", "PLAN_NONE",
    "SIMBRIEF_PLACEHOLDER", "SIMBRIEF_BUTTON", "OPEN_PLAN", "QUICK_FROM",
    "QUICK_TO", "QUICK_BUTTON", "PREPARE", "BUILD_ALTERNATE", "CRUISE_LABEL",
    "CORRIDOR_LABEL", "SIM_PRIORITY_LABEL", "SIM_PRIORITIES", "LIVE_PREVIEW",
    "LIVE_PREVIEW_STUB", "DIVERT", "END_FLIGHT", "NO_FLIGHT_MANAGER",
    "NO_STATUS", "READINESS_LABELS", "STATE_MARKS", "LEGEND",
    "DEFAULT_CRUISE_KT", "DEFAULT_CORRIDOR_KM", "plan_row_label",
    "unknown_airport", "refusal", "quick_plan", "cruise_kt", "card_lines",
    "countdown_text", "item_text", "world_line", "follow_status_line",
    "legend_key",
]

PLAN_SOURCE_LABEL = "Flight plan"
PLAN_CHOOSE = "Choose a flight…"
PLAN_SIMBRIEF = "SimBrief: latest plan"
PLAN_NONE = "No plan: follow the aircraft"
SIMBRIEF_PLACEHOLDER = FP.SIMBRIEF_PLACEHOLDER
SIMBRIEF_BUTTON = "Fetch"
OPEN_PLAN = FP.OPEN_BUTTON
QUICK_FROM = "From"
QUICK_TO = "To"
QUICK_BUTTON = "Use"
PREPARE = "Prepare flight"
BUILD_ALTERNATE = "Also build the alternate"
CRUISE_LABEL = "Cruise speed (kt)"
CORRIDOR_LABEL = "Corridor (km each side)"
SIM_PRIORITY_LABEL = "While flying"
#: ``fly_sim_priority`` (§5.5): (value, words).
SIM_PRIORITIES = (("smooth", "Smooth flying first"),
                  ("balanced", "Balanced"),
                  ("fast", "Build fastest"))
LIVE_PREVIEW = GLOSSARY.TERMS["live_flight_preview"]
LIVE_PREVIEW_STUB = ("Shows each square's installed imagery on the map; "
                     "the drawing arrives in a later version.")
DIVERT = "Divert…"
END_FLIGHT = "End flight"
#: An engine that answers a ``flight_*`` command with a refusal.
NO_FLIGHT_MANAGER = "This engine has no flight manager yet."
#: The readiness list before the engine reports a flight.
NO_STATUS = "Prepare a flight to see what it needs."

#: §6.2's readiness rows, in the engine's order.
READINESS_LABELS = {
    "world": "World pack in X-Plane",
    "budget": "Fits the disk budget",
    "network": "Internet, or everything on disk",
    "prefetch": "Map data and elevation",
    "departure": "Departure airport",
    "first_window": "Scenery around the departure",
    "route": "Route built ahead in time",
    "destination": "Destination airport",
    "alternate": "Alternate airport",
    "loaded": "Loaded in X-Plane",
}
#: A readiness row's state as one mark.
STATE_MARKS = {"done": "✓", "working": "…", "waiting": "○",
               "blocked": "!", "failed": "✕"}
#: The map legend (§14): (key, words), drawn in this order.
LEGEND = (("own", GLOSSARY.TERMS["xplane_own_scenery"]),
          ("quick", "photo, quick"),
          ("built", "built"),
          ("building", "building"))

DEFAULT_CRUISE_KT = FS.DEFAULT_CRUISE_KT
DEFAULT_CORRIDOR_KM = 20

_WORLD_STATES = {"off": "World pack off", "idle": "World pack ready",
                 "following": "World pack following the aircraft",
                 "building": "World pack building ahead",
                 "paused": "World pack paused", "error": "World pack stopped"}
_BUILDING = frozenset({"fetching", "building"})
_DONE = frozenset({"staged", "swapped"})


def plan_row_label(row: Dict[str, Any]) -> str:
    """One ``flight_plans_list`` row in the plan menu: "CYLW → CYYC
    (CYLWCYYC)"; the bare name when the plan names no airports."""
    origin, destination = row.get("origin") or "", row.get("destination") or ""
    name = row.get("name") or ""
    if origin or destination:
        return "%s → %s (%s)" % (origin or "?", destination or "?", name)
    return name


def unknown_airport(ident: str) -> str:
    return "No airport %s in X-Plane's list." % (ident.strip().upper() or "?")


def quick_plan(departure: Sequence, arrival: Sequence) -> Dict[str, Any]:
    """A two-airport plan in the ``flight_plan_read`` shape (``plan_wire``)
    from ``(ident, lat, lon)`` of each end: the departure + arrival quick
    entry."""
    places = [{"ident": str(p[0]).upper(), "lat": float(p[1]),
               "lon": float(p[2]), "alt_ft": None, "t_s": None}
              for p in (departure, arrival)]
    return {"source": "quick", "origin": places[0]["ident"],
            "destination": places[1]["ident"], "waypoints": places,
            "alternate": None, "ete_s": None, "cruise_ms": None,
            "cruise_alt_ft": None,
            "route_km": FP.route_length_km(
                [(p["lat"], p["lon"]) for p in places])}


def refusal(error: str) -> str:
    """A refused ``flight_*`` command, for the user: an engine without
    the command says :data:`NO_FLIGHT_MANAGER`, else its own sentence."""
    if not error or str(error).startswith("unknown command"):
        return NO_FLIGHT_MANAGER
    return str(error)


def cruise_kt(plan: Optional[Dict[str, Any]]) -> int:
    """The cruise speed field's prefill: the plan's, else 250 kt."""
    ms = (plan or {}).get("cruise_ms")
    return int(round(ms / FS.KT_TO_MS)) if ms else int(DEFAULT_CRUISE_KT)


def _duration(seconds: float) -> str:
    minutes = int(round(seconds / 60.0))
    if minutes < 60:
        return "%d min" % minutes
    return "%d h %02d min" % (minutes // 60, minutes % 60)


def card_lines(plan: Dict[str, Any], cruise: float) -> List[str]:
    """The flight card: route, alternate, distance and time en route
    (the plan's, else the distance at ``cruise`` knots)."""
    km = float(plan.get("route_km") or 0.0)
    ete = plan.get("ete_s")
    if not ete and cruise > 0:
        ete = km / (cruise * FP.KM_PER_NM) * 3600.0
    alternate = plan.get("alternate")
    return ["%s → %s" % (plan.get("origin") or "?",
                         plan.get("destination") or "?"),
            "Alternate %s" % alternate["ident"] if alternate
            else "No alternate in the plan",
            "%s km · %s en route" % (format(int(round(km)), ","),
                                     _duration(ete or 0.0))]


def countdown_text(seconds: Optional[float]) -> str:
    """"Ready in about 12 min" (``O4_Flight_Schedule.countdown_text``)."""
    return FS.countdown_text(seconds)


def item_text(row: Sequence) -> str:
    """One readiness row ``[key, state, eta_s, detail]`` as a line:
    "✓ Departure airport", "… Destination airport · about 4 min",
    "! World pack in X-Plane · Restart X-Plane once"."""
    key, state, eta, detail = (list(row) + [None, None, None, ""])[:4]
    text = "%s %s" % (STATE_MARKS.get(state, "○"),
                      READINESS_LABELS.get(key, key))
    if detail:
        return text + " · " + detail
    if state not in ("done", "failed", "blocked") and eta is not None and eta > 0:
        return text + " · about %d min" % max(1, math.ceil(eta / 60.0))
    return text


def world_line(status: Optional[Dict[str, Any]]) -> str:
    """The World pack's one line from a ``WorldStatus`` (its fields as a
    dict); a dash before the engine reports one."""
    if not status:
        return "World pack: —"
    text = _WORLD_STATES.get(status.get("state") or "", "World pack")
    building = len(status.get("building") or [])
    if building:
        text += " · %d building" % building
    loaded = len(status.get("loaded") or [])
    if loaded:
        text += " · %d in X-Plane" % loaded
    reason = status.get("reason") or ""
    return text + (" · " + reason if reason else "")


def follow_status_line(status: Optional[Dict[str, Any]]) -> str:
    """The flight's state line under the countdown, from a
    ``FlightStatus`` (its fields as a dict): the engine's ``reason``
    sentence, else the route flown so far."""
    if not status:
        return ""
    if status.get("reason"):
        return str(status["reason"])
    route, done = status.get("route_km") or 0, status.get("done_km") or 0
    if route:
        return "%s of %s km flown" % (format(int(round(done)), ","),
                                     format(int(round(route)), ","))
    return ""


def legend_key(kind: str, state: str) -> str:
    """A corridor tile's legend key from its job's kind and state."""
    if state in _BUILDING:
        return "building"
    if state in _DONE:
        return "built" if kind == "full" else "quick"
    return "own"
