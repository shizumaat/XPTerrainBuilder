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
    "QUICK_TO", "QUICK_BUTTON", "NO_DESTINATION", "DEPARTURE_ONLY_CARD",
    "DEPARTURE_ONLY_PREPARING", "DEPARTURE_ONLY_FLYING", "PREPARE",
    "BUILD_ALTERNATE", "CRUISE_LABEL",
    "CORRIDOR_LABEL", "SIM_PRIORITY_LABEL", "SIM_PRIORITIES",
    "DRAPE_PX_LABEL", "DRAPE_PX_KEY", "DRAPE_PX_CHOICES", "LIVE_PREVIEW",
    "LIVE_PREVIEW_HELP", "CENTER_ON_AIRCRAFT", "NO_AIRCRAFT_POSITION",
    "AIRCRAFT_FRESH_S", "aircraft_is_current", "DIVERT", "END_FLIGHT", "NO_FLIGHT_MANAGER",
    "NO_STATUS", "READINESS_LABELS", "STATE_MARKS", "LEGEND", "PREVIEW_KEYS",
    "DEFAULT_CRUISE_KT", "DEFAULT_CORRIDOR_KM", "plan_row_label",
    "unknown_airport", "refusal", "quick_plan", "cruise_kt", "card_lines",
    "countdown_text", "item_text", "world_line", "follow_status_line",
    "legend_key", "here_lines",
    "added_destination",
]

PLAN_SOURCE_LABEL = "Flight plan"
PLAN_CHOOSE = "Choose a flight…"
PLAN_SIMBRIEF = "SimBrief: latest plan"
PLAN_NONE = "No plan: follow the aircraft"
SIMBRIEF_PLACEHOLDER = FP.SIMBRIEF_PLACEHOLDER
SIMBRIEF_BUTTON = "Fetch"
OPEN_PLAN = FP.OPEN_BUTTON
QUICK_FROM = "From"
QUICK_TO = "To (optional)"
QUICK_BUTTON = "Use"
#: A departure-only plan (#2023: From with an empty To): the card's
#: words, and the status line's while it prepares and once it may leave.
NO_DESTINATION = "no destination"
DEPARTURE_ONLY_CARD = "Prepares the departure area; the rest builds as you fly"
DEPARTURE_ONLY_PREPARING = (
    "Departure only: the departure tile at full detail, the tiles around "
    "it as quick photos (Quick, whatever Photo detail ahead says); the "
    "rest builds as you fly.")
DEPARTURE_ONLY_FLYING = "Departure only: the scenery ahead builds as you fly."
PREPARE = "Prepare flight"
BUILD_ALTERNATE = "Also build the alternate"
CRUISE_LABEL = "Cruise speed (kt)"
CORRIDOR_LABEL = "Corridor (km each side)"
SIM_PRIORITY_LABEL = "While flying"
#: ``fly_sim_priority`` (§5.5): (value, words).
SIM_PRIORITIES = (("smooth", "Smooth flying first"),
                  ("balanced", "Balanced"),
                  ("fast", "Build fastest"))
DRAPE_PX_LABEL = "Photo detail ahead"
#: ``drape_photo_px`` (RULINGS 2026-11-11j): (value, words).
DRAPE_PX_KEY = "drape_photo_px"
DRAPE_PX_CHOICES = ((512, "Quick"),
                    (1024, "Sharper"),
                    (4096, "Full detail (slow)"))
LIVE_PREVIEW = GLOSSARY.TERMS["live_flight_preview"]
LIVE_PREVIEW_HELP = ("Shows the imagery installed for X-Plane on the map, "
                     "square by square, as it arrives; zoom in to see it.")
#: The map's button beside the zoom controls (#2016): it pans to the
#: aircraft and keeps the zoom; disabled, with NO_AIRCRAFT_POSITION as
#: its help, while no position is current.
CENTER_ON_AIRCRAFT = "Center on aircraft"
NO_AIRCRAFT_POSITION = ("No aircraft position: X-Plane is not running, "
                        "or Fly mode is off.")
#: Seconds an ``AircraftPosition`` stays current: the watch sends one a
#: second and nothing while X-Plane does not answer.
AIRCRAFT_FRESH_S = 5.0
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
          ("building", "building"),
          ("sharp", "full-detail photo"))
#: The legend's keys the map draws only while "Live flight preview" is
#: on (a square of installed imagery at full resolution, #2020).
PREVIEW_KEYS = frozenset({"sharp"})

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


def quick_plan(departure: Sequence, arrival: Optional[Sequence] = None
               ) -> Dict[str, Any]:
    """A two-airport plan in the ``flight_plan_read`` shape (``plan_wire``)
    from ``(ident, lat, lon)`` of each end: the departure + arrival quick
    entry.  No arrival: a departure-only plan of one waypoint (#2023)."""
    places = [{"ident": str(p[0]).upper(), "lat": float(p[1]),
               "lon": float(p[2]), "alt_ft": None, "t_s": None}
              for p in (departure, arrival) if p]
    return {"source": "quick", "origin": places[0]["ident"],
            "destination": places[1]["ident"] if arrival else "",
            "waypoints": places,
            "alternate": None, "ete_s": None, "cruise_ms": None,
            "cruise_alt_ft": None,
            "route_km": FP.route_length_km(
                [(p["lat"], p["lon"]) for p in places])}


def _departure_only(plan: Optional[Dict[str, Any]]) -> bool:
    """A plan with a departure and no destination (#2023): every
    waypoint at the first one's position (``FlightPlan.departure_only``)."""
    points = {(w.get("lat"), w.get("lon"))
              for w in (plan or {}).get("waypoints") or ()}
    return len(points) == 1


def _status_departure_only(status: Optional[Dict[str, Any]]) -> bool:
    """A ``FlightStatus`` of a departure-only flight: no route, a
    departure job and no destination job."""
    if not status or status.get("route_km"):
        return False
    roles = {row[1] for row in status.get("jobs") or () if len(row) > 1}
    return "departure" in roles and "destination" not in roles


def added_destination(status: Optional[Dict[str, Any]],
                      plan: Optional[Dict[str, Any]]
                      ) -> Optional[Dict[str, Any]]:
    """The ``destination`` of ``flight_update`` when the quick entry adds
    a To to the active departure-only flight (#2023): the plan's last
    waypoint ``{ident, lat, lon}``, when ``plan`` starts where that
    flight does; else None (a new plan for the next Prepare)."""
    points = (plan or {}).get("waypoints") or []
    if (not _status_departure_only(status) or _departure_only(plan)
            or len(points) < 2
            or (status or {}).get("state") not in ("preparing", "ready",
                                                   "flying")):
        return None
    dep = [row[0] for row in status.get("jobs") or ()
           if len(row) > 1 and row[1] == "departure"]
    if dep and list(dep[0]) != [math.floor(points[0]["lat"]),
                                math.floor(points[0]["lon"])]:
        return None
    last = points[-1]
    return {"ident": last["ident"], "lat": last["lat"], "lon": last["lon"]}


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
    alternate = plan.get("alternate")
    alternate_line = ("Alternate %s" % alternate["ident"] if alternate
                      else "No alternate in the plan")
    if _departure_only(plan):
        return ["%s → %s" % (plan.get("origin") or "?", NO_DESTINATION),
                alternate_line, DEPARTURE_ONLY_CARD]
    km = float(plan.get("route_km") or 0.0)
    ete = plan.get("ete_s")
    if not ete and cruise > 0:
        ete = km / (cruise * FP.KM_PER_NM) * 3600.0
    return ["%s → %s" % (plan.get("origin") or "?",
                         plan.get("destination") or "?"),
            alternate_line,
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
    if _status_departure_only(status):
        return (DEPARTURE_ONLY_PREPARING if status.get("state") == "preparing"
                else DEPARTURE_ONLY_FLYING)
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


def aircraft_is_current(seen_at: Optional[float], now: float) -> bool:
    """True when the last ``AircraftPosition`` (received at ``seen_at``,
    seconds on the clock ``now`` reads) is younger than
    :data:`AIRCRAFT_FRESH_S` -- the center-on-aircraft button's rule."""
    return seen_at is not None and 0.0 <= now - seen_at < AIRCRAFT_FRESH_S


#: ``here_lines``: the quick photo's state by build-ahead's ``job``.
_HERE_JOB = {"queued": "Quick photo: waiting for a build slot",
             "late": "Quick photo: waiting for a build slot",
             "staged": "Quick photo: built, going in",
             "failed": "Quick photo: the build failed"}
#: ... and with no job, by the pack's ``kind`` of the tile.
_HERE_KIND = {"placeholder": "Quick photo: not built yet",
              "drape": "Quick photo: in place",
              "full": "Scenery built at full detail"}


def _clock(seconds) -> str:
    seconds = max(0, int(seconds or 0))
    return "%d:%02d" % (seconds // 60, seconds % 60)


def here_lines(here: Optional[Dict[str, Any]]) -> List[str]:
    """The Fly pane's block for the aircraft's own tile with no plan
    (#2020), from ``WorldStatus.here`` (``o4_engine.fly_here``): the
    headline ("Preparing imagery at CYYR", "Imagery ready at ..."), the
    quick photo's state (building with elapsed and estimate), and the
    full-detail squares around the aircraft ("3 of 9 squares sharp").
    ``[]`` before the engine reports one."""
    if not here:
        return []
    place = here.get("airport") or "tile %s" % (here.get("tile") or "?")
    kind, job = here.get("kind") or "", here.get("job") or ""
    squares, sharp = int(here.get("squares") or 0), int(here.get("sharp") or 0)
    if not kind and not job:
        return ["Imagery at %s: drawn by other scenery" % place]
    if job == "building":
        quick = "Quick photo: building · %s of about %d min" % (
            _clock(here.get("elapsed_s")),
            max(1, math.ceil((here.get("estimate_s") or 0) / 60.0)))
    else:
        quick = _HERE_JOB.get(job) or _HERE_KIND.get(kind, "")
    ready = (kind in ("drape", "full") and job in ("", "swapped")
             and sharp >= squares)
    lines = ["%s at %s" % ("Imagery ready" if ready else "Preparing imagery",
                           place)]
    if quick:
        lines.append(quick)
    if squares:
        lines.append("Full detail nearby: %d of %d squares sharp"
                     % (sharp, squares))
    elif job == "building" and here.get("core"):
        lines.append("Full detail nearby: fetching")
    return lines
