"""The flight record (spec flight-manager-and-world-20261110 §6.1).

``<data folder>/Flights/<id>.json``, written atomically; one flight is
active at a time.  This module is the record's shape and its store:
:func:`from_plan` makes a record from a read plan
(``O4_Flight_Plan.FlightPlan``), :func:`save` / :func:`load` /
:func:`list_flights` / :func:`active_flight` keep it.  The flight
manager (``flight_manager.py``, lane F1b) fills ``tiles`` and moves
``state``; nothing here runs a job.

The record is what Build mode reads afterwards ("the record keeps what
was built, how long each took, and what was late", §4.3 step 9), so
unknown keys from a newer engine are kept on load and written back.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import O4_File_Names as FNAMES
import O4_Flight_Plan as FP
import O4_Flight_Schedule as SCHEDULE

from .patch_file import write_atomic

__all__ = [
    "FlightRecord", "TileRow", "STATES", "SOURCE_KINDS", "PROFILE_BASES",
    "flight_id", "from_plan", "flights_dir", "save", "load", "list_flights",
    "active_flight", "DEFAULT_CORRIDOR_KM",
]

FOLDER = "Flights"
#: §5.5 ``fly_corridor_km`` default.
DEFAULT_CORRIDOR_KM = 20.0

#: ``state`` (the ``FlightStatus`` vocabulary, §5.3).
STATES = ("preparing", "ready", "flying", "arrived", "closed", "error")
#: States of a flight that is still the active one.
ACTIVE_STATES = frozenset({"preparing", "ready", "flying"})
SOURCE_KINDS = ("simbrief", "fms", "lnmpln", "none")
#: ``profile.basis``: the plan's own speed or times, the last flight with
#: this aircraft, the 250 kt default, or the pilot's entry on the card.
PROFILE_BASES = ("plan", "aircraft", "default", "pilot")


@dataclass
class TileRow:
    """One tile of the flight (§6.1 ``tiles``)."""
    tile: List[int]
    role: str
    kind: str
    state: str = "queued"
    deadline_s: Optional[float] = None
    est_s: Optional[List[float]] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    swapped_at: Optional[str] = None
    late: bool = False


@dataclass
class FlightRecord:
    id: str
    source: Dict[str, Any]
    origin: Optional[Dict[str, Any]]
    destination: Optional[Dict[str, Any]]
    alternate: Optional[Dict[str, Any]] = None
    build_alternate: bool = False
    waypoints: List[Dict[str, Any]] = field(default_factory=list)
    profile: Dict[str, Any] = field(default_factory=dict)
    corridor_km: float = DEFAULT_CORRIDOR_KM
    state: str = "preparing"
    phase: str = ""
    created_at: str = ""
    ready_at: Optional[str] = None
    departed_at: Optional[str] = None
    arrived_at: Optional[str] = None
    tiles: List[TileRow] = field(default_factory=list)
    skipped_questions: List[Any] = field(default_factory=list)
    notes: List[Any] = field(default_factory=list)
    #: Keys this engine does not know, kept as read (a newer engine's).
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        doc = asdict(self)
        extra = doc.pop("extra")
        return {**extra, **doc}

    @classmethod
    def from_dict(cls, doc: Dict[str, Any]) -> "FlightRecord":
        names = {f.name for f in fields(cls)} - {"extra"}
        known = {k: v for k, v in doc.items() if k in names}
        known["tiles"] = [_tile_row(t) for t in doc.get("tiles") or []]
        return cls(**known, extra={k: v for k, v in doc.items() if k not in names})


def _tile_row(doc: Dict[str, Any]) -> TileRow:
    names = {f.name for f in fields(TileRow)}
    return TileRow(**{k: v for k, v in doc.items() if k in names})


def _utc(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ident_part(ident: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (ident or "").upper())[:8] or "NONE"


def flight_id(origin: str, destination: str, now: datetime) -> str:
    """``20261110T1612Z-<origin>-<destination>`` (file-name safe)."""
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%MZ")
    return "%s-%s-%s" % (stamp, _ident_part(origin), _ident_part(destination))


def _place(point) -> Optional[Dict[str, Any]]:
    if point is None:
        return None
    return {"ident": point.ident, "lat": point.lat, "lon": point.lon}


def _waypoint(w) -> Dict[str, Any]:
    row = {"ident": w.ident, "lat": w.lat, "lon": w.lon}
    if w.alt_ft is not None:
        row["alt_ft"] = w.alt_ft
    if w.t_s is not None:
        row["t_s"] = w.t_s
    return row


def _profile(plan, cruise_kt: Optional[float],
             aircraft_ms: Optional[float]) -> Dict[str, Any]:
    flown = plan.waypoints[-1].t_s
    mean = (FP.route_length_km(plan.points()) * 1000.0 / flown
            if flown and all(w.t_s is not None for w in plan.waypoints) else None)
    if cruise_kt:
        speed, basis = cruise_kt * SCHEDULE.KT_TO_MS, "pilot"
    elif plan.cruise_ms or mean:
        speed, basis = plan.cruise_ms or mean, "plan"
    elif aircraft_ms:
        speed, basis = aircraft_ms, "aircraft"
    else:
        speed, basis = SCHEDULE.DEFAULT_CRUISE_KT * SCHEDULE.KT_TO_MS, "default"
    profile: Dict[str, Any] = {"cruise_ms": speed, "basis": basis}
    if plan.cruise_alt_ft is not None:
        profile["cruise_alt_ft"] = plan.cruise_alt_ft
    if plan.ete_s is not None:
        profile["ete_s"] = plan.ete_s
    return profile


def from_plan(plan, source_kind: str, now: datetime, *,
              build_alternate: bool = False, cruise_kt: Optional[float] = None,
              corridor_km: float = DEFAULT_CORRIDOR_KM,
              aircraft_ms: Optional[float] = None) -> FlightRecord:
    """A new ``preparing`` record from a read plan.  ``source_kind`` is one
    of :data:`SOURCE_KINDS`; ``cruise_kt`` is the pilot's entry on the
    flight card, ``aircraft_ms`` the last flight's speed with this
    aircraft (§4.3 step 3: plan, else aircraft, else 250 kt)."""
    if source_kind not in SOURCE_KINDS:
        raise ValueError("unknown plan source %r" % source_kind)
    first, last = plan.waypoints[0], plan.waypoints[-1]
    return FlightRecord(
        id=flight_id(first.ident, last.ident, now),
        source={"kind": source_kind, "name": plan.source, "read_at": _utc(now)},
        origin=_place(first), destination=_place(last),
        alternate=_place(plan.alternate), build_alternate=bool(build_alternate),
        waypoints=[_waypoint(w) for w in plan.waypoints],
        profile=_profile(plan, cruise_kt, aircraft_ms),
        corridor_km=float(corridor_km), created_at=_utc(now))


# ===========================================================================
# The store
# ===========================================================================
def flights_dir(data_root: Optional[str] = None) -> str:
    """``<data folder>/Flights``."""
    return os.path.join(data_root or FNAMES.current_data_root(), FOLDER)


def save(record: FlightRecord, folder: str) -> str:
    """Write the record atomically; returns its path.  Raises OSError."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, record.id + ".json")
    write_atomic(path, json.dumps(record.to_dict(), indent=1, sort_keys=True) + "\n")
    return path


def load(path: str) -> FlightRecord:
    """Read one record.  Raises OSError or ValueError."""
    with open(path, encoding="utf-8") as handle:
        doc = json.load(handle)
    if not isinstance(doc, dict) or "id" not in doc:
        raise ValueError("%s is not a flight record" % path)
    return FlightRecord.from_dict(doc)


def list_flights(folder: str) -> List[FlightRecord]:
    """Every readable record in ``folder``, newest first (by ``created_at``,
    then id).  An unreadable file is left out."""
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    records = []
    for name in names:
        if name.endswith(".json"):
            try:
                records.append(load(os.path.join(folder, name)))
            except (OSError, ValueError, TypeError):
                continue
    records.sort(key=lambda r: (r.created_at, r.id), reverse=True)
    return records


def active_flight(folder: str) -> Optional[FlightRecord]:
    """The newest record still preparing, ready or flying."""
    return next((r for r in list_flights(folder) if r.state in ACTIVE_STATES), None)
