"""Spawn and jump: the imagery an aircraft that APPEARED somewhere needs,
and whether X-Plane must reload its scenery to show it (#1992
local-imagery-cache spec §4.5, phase P5).

THE READ MODEL (spec §2.4-2.5, recorder flight 1): at a flight load
X-Plane opens every texture in range at mip 4, then about 24 s later
opens them again at the level each one's distance wants.  A texture
resident at the level it wants is not read again until it has stepped
down and up (for the field of a local flight: never).  So a finer file
landed INSIDE that flight-start window is read by X-Plane itself; one
landed after it shows only after a scenery reload.

A WITNESS says the camera appeared somewhere it did not fly to:

* ``spawn`` -- the first position the follow job reads in a session
  (X-Plane may have stood there for an hour: no window is counted on,
  so whatever lands for the core is taken as missed);
* ``flight_load`` -- positions resumed after X-Plane's Web API dropped
  (it drops while a flight loads; ``O4_XPlane_WebAPI.PositionReader``);
* ``jump`` -- the camera moved further than any aircraft flies (map
  jump, replay, "move to"; ``O4_Imagery_Follow_Motion``).

Each witness opens an :class:`Episode`: the CORE of the new place (every
square a camera standing there wants finer than its file on disk, by the
rule of the kept airport cores, ``O4_Imagery_OnDemand_Cores.core_tier``),
fetched core first, each square straight at the tier it wants, files that
need no download first, against the deadline "end of the flight-start
window".  When nothing of the core is left to land, the episode closes:
if a file landed after the window and the camera is still inside the
distance where X-Plane wants that tier, ONE scenery reload is due; if
nothing missed the window, none.  Nothing lands without a network, so no
reload follows there either (spec §8).

Positions that resume where the camera was are not always a load;
:meth:`SpawnWatch.witness` opens no episode for

* a drop shorter than :data:`LOAD_DOWN_S`: a stutter; X-Plane read
  nothing again, so an open episode and its window stand, and no reload
  follows a stall in mid-flight;
* positions resumed within :data:`RELOAD_QUIET_S` of this job's own
  reload: that reload's stall (one reload per jump).

A jump, and positions that resume somewhere else, always open one, and
an episode still open then is dropped: X-Plane has loaded another place.

Pure: no I/O, no clock; the follow job (``o4_engine.imagery_follow``)
passes the time, the camera and the index rows.
"""
from __future__ import annotations

import dataclasses

import O4_Imagery_OnDemand_Cores as CORES
import O4_Imagery_OnDemand_Index as INDEX
import O4_Imagery_Tier_Plan as PLAN

# The follow job's surface; Episode and core_wants are SpawnWatch's parts.
__all__ = ["FLIGHT_START_WINDOW_S", "LOAD_DOWN_S", "RELOAD_QUIET_S",
           "SAME_PLACE_M", "WINDOW_MARGIN_S", "SpawnWatch"]

#: Seconds from a flight load's first (mip 4) texture opens to X-Plane's
#: finer opens (flight 1: 24-25 s; one sample, spec §11 U11).
FLIGHT_START_WINDOW_S = 24.0
#: Seconds of that window not counted on: the witness (positions resumed)
#: may trail X-Plane's first opens, and a landing must be whole before the
#: finer open.  An unneeded reload is a stall; a skipped one a blurry field.
WINDOW_MARGIN_S = 4.0
#: Seconds after this job's own reload in which resumed positions at the
#: same place are that reload (X-Plane stalls while it reloads).
RELOAD_QUIET_S = 120.0
#: A Web API drop at least this long is a load (X-Plane read its textures
#: again; flight 1's lasted ~90 s); a shorter one with the camera where
#: it was is a stutter.
LOAD_DOWN_S = 10.0
#: The camera "did not move" across a drop within this distance.
SAME_PLACE_M = 2000.0


def core_wants(rows, lat: float, lon: float) -> dict[str, int]:
    """``{key: tier}`` for the index ``rows`` (``{key: row}``) a camera
    standing at ``(lat, lon)`` wants finer than the file on disk: full
    inside 1.65 S, 2048 inside 2.8 S, 1024 inside 5.2 S (the airport-core
    rule).  Failed rows are left out."""
    here = [("", lat, lon)]
    wants = {}
    for key, row in rows.items():
        if row.get("state") == "failed":
            continue
        tier = CORES.core_tier(row, here)
        if tier is not None and tier > PLAN.tier_of_width(row.get("tier_px")):
            wants[key] = tier
    return wants


@dataclasses.dataclass
class Episode:
    """One spawn or jump: ``witness`` at time ``at`` with the camera at
    ``(lat, lon)``; ``wants`` the core's ``{key: tier}`` and ``had`` the
    tier each had on disk then (what X-Plane read at the load); ``local``
    the keys that need no download; ``landed`` the keys whose tier is
    down, ``missed`` those of them that landed after the window."""
    witness: str
    at: float
    lat: float
    lon: float
    window_end: float
    wants: dict[str, int]
    had: dict[str, int]
    local: set[str] = dataclasses.field(default_factory=set)
    landed: set[str] = dataclasses.field(default_factory=set)
    missed: set[str] = dataclasses.field(default_factory=set)

    def pending(self, rows, failed=()) -> list[str]:
        """The core's keys still to land, in fetch order: files that need
        no download first, then the finest tier first (the core before
        its rings), nearest first."""
        keys = [key for key, tier in self.wants.items()
                if key in rows and key not in failed
                and rows[key].get("state") != "failed"
                and PLAN.tier_of_width(rows[key].get("tier_px")) < tier]
        return sorted(keys, key=lambda key: (
            key not in self.local, -self.wants[key],
            INDEX.distance_m(rows[key], self.lat, self.lon), key))

    def fetches(self, rows, now: float, failed=()) -> list[PLAN.Fetch]:
        """The planner's fetches for :meth:`pending`: each square straight
        at its tier, due now, its deadline the end of the window (negative
        once that has passed: the buffer is empty, spec §4.4)."""
        return [PLAN.Fetch(key, self.wants[key], self.wants[key],
                           self.window_end - now, 0.0,
                           INDEX.distance_m(rows[key], self.lat, self.lon),
                           False)
                for key in self.pending(rows, failed)]

    def note_landed(self, key: str, tier: int, landed_at: float) -> None:
        """A file of ``tier`` landed for ``key`` at ``landed_at``; the
        first one of the tier the core wants (or finer) counts."""
        if (key not in self.landed
                and tier >= self.wants.get(key, len(PLAN.TIER_WIDTH))):
            self.landed.add(key)
            if landed_at > self.window_end:
                self.missed.add(key)

    def stale(self, rows, lat: float, lon: float) -> list[str]:
        """The missed squares X-Plane still shows too coarse: the camera
        is inside the distance where it wants a finer tier than the file
        it read at the load, so it holds that coarser level and no
        step-up open will read the new file (spec §2.5 read model)."""
        def inside(key) -> bool:
            row = rows[key]
            radius = (PLAN.CROSSING_S[self.had[key] + 1]
                      * float(row.get("load_size_m") or 0.0))
            return INDEX.distance_m(row, lat, lon) <= radius
        return sorted(key for key in self.missed
                      if key in rows and inside(key))


class SpawnWatch:
    """The witnesses of one follow session and the episode they open.
    ``episode`` is the open one (or ``None``); ``episodes`` and ``reloads``
    count the session's."""

    def __init__(self, window_s: float = FLIGHT_START_WINDOW_S,
                 margin_s: float = WINDOW_MARGIN_S):
        self.window_s = max(0.0, float(window_s) - float(margin_s))
        self.episode: Episode | None = None
        self.episodes = 0
        self.reloads = 0
        self._reload_at: float | None = None

    def witness(self, kind: str, now: float, lat: float, lon: float, rows,
                *, moved_m: float = float("inf"), down_s: float = 0.0,
                is_local=None) -> Episode | None:
        """A witness ``kind`` at ``now`` with the camera at ``(lat, lon)``;
        ``moved_m`` and ``down_s`` are the camera's move and the seconds
        without a position across a ``flight_load``'s drop.  Opens the
        episode of the new place (replacing an open one) and returns it,
        or ``None`` when the witness belongs to an event already known.
        ``is_local(row, tier)`` says a file needs no download."""
        if kind == "flight_load" and moved_m <= SAME_PLACE_M:
            if down_s < LOAD_DOWN_S:
                return None                 # a stutter: nothing read again
            if (self._reload_at is not None
                    and now - self._reload_at <= RELOAD_QUIET_S):
                return None                 # this job's own reload
        wants = core_wants(rows, lat, lon)
        local = {key for key, tier in wants.items()
                 if is_local is not None and is_local(rows[key], tier)}
        had = {key: PLAN.tier_of_width(rows[key].get("tier_px"))
               for key in wants}
        window_s = 0.0 if kind == "spawn" else self.window_s
        self.episode = Episode(kind, now, lat, lon, now + window_s,
                               wants, had, local)
        self.episodes += 1
        return self.episode

    def settle(self, rows, lat: float, lon: float,
               failed=()) -> list[str] | None:
        """``None`` while the open episode still has files to land (or
        none is open; a file in flight is still to land: its row changes
        when it is down).  Else the episode closes and the squares a
        reload would sharpen are returned: empty when nothing missed the
        window or the camera has left them behind."""
        episode = self.episode
        if episode is None or episode.pending(rows, failed):
            return None
        self.episode = None
        return episode.stale(rows, lat, lon)

    def reloaded(self, now: float) -> None:
        """This job asked X-Plane to reload its scenery at ``now``."""
        self.reloads += 1
        self._reload_at = now
