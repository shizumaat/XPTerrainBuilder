"""Where the aircraft and the camera are, read from X-Plane's own Web API
(#1992 local-imagery-cache spec §4.2; extracted from the read recorder,
``tools/xplane_reads/record_reads.py``, which imports this module: one
implementation).

X-Plane 12.1.1 and later answers ``http://localhost:8086/api/v2`` with no
setup and no plugin.  A dataref's numeric id comes from
``GET /datarefs?filter[name]=<ref>``, its value from
``GET /datarefs/<id>/value``.  X-Plane hands out NEW ids when a flight
loads and may drop the connection then (recorder flights 1-2), so a
reader forgets its ids on any error and resolves them again on the next
read.  X-Plane 12.4 may instead answer all through a load, with the
aircraft and the camera read in two local frames (#2028: a camera
5,800 km from the aircraft): a reader trusts a position only once
X-Plane's clock (``sim/time/total_running_time_sec``) is seen running
(or paused after it ran), and a good read that follows a failure or a
load is the flight-load witness of spec §4.5
(:attr:`PositionReader.resets`).

* :data:`POS_REFS` — the datarefs read, ``(key, dataref, required)``.
* :func:`base_url` — the API root for a port (expert
  ``xplane_web_api_port``, default :data:`DEFAULT_PORT`).
* :func:`resolve_refs` / :func:`read_position` — one id lookup, one read.
* :class:`PositionReader` — reads that survive id resets and drops.
* :func:`camera_position` — the camera's latitude and longitude: X-Plane
  pages scenery by the camera, which an outside view moves away from the
  aircraft (never more than :data:`MAX_CAMERA_OFFSET_M`).
* :func:`poll_positions` — the recorder's 1 Hz loop.
* :func:`command_id` / :func:`activate_command` — X-Plane's commands
  (API v2, X-Plane 12.1.4 and later): the id of a command by name
  (``GET /commands?filter[name]=<name>``) and its press-and-release
  (``POST /command/<id>/activate`` with ``{"duration": 0}``).
* :func:`reload_scenery` — :data:`RELOAD_SCENERY` activated: X-Plane
  reads every scenery file again (spec §4.5, §11 U9; no plugin).

Standard library only: the recorder runs under ``/usr/bin/python3``.
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

# (command_id and activate_command are reload_scenery's parts.)
__all__ = ["DEFAULT_PORT", "LOADING", "MAX_CAMERA_OFFSET_M", "POS_REFS",
           "RELOAD_SCENERY", "PositionReader", "base_url", "camera_agl_m",
           "camera_position", "now_stamp", "poll_positions",
           "read_position", "reload_scenery", "resolve_refs"]

#: X-Plane's default Web API port (Settings > Network; expert setting
#: ``xplane_web_api_port``).
DEFAULT_PORT = 8086

# (key, dataref, required).  Optional ones are reported once as missing.
POS_REFS = (
    ("lat", "sim/flightmodel/position/latitude", True),
    ("lon", "sim/flightmodel/position/longitude", True),
    ("elev_m", "sim/flightmodel/position/elevation", True),
    ("agl_m", "sim/flightmodel/position/y_agl", False),
    ("hdg", "sim/flightmodel/position/true_psi", False),
    ("pitch", "sim/flightmodel/position/true_theta", False),
    ("gs_ms", "sim/flightmodel/position/groundspeed", False),
    ("ias_kt", "sim/flightmodel/position/indicated_airspeed", False),
    ("local_x", "sim/flightmodel/position/local_x", False),
    ("local_y", "sim/flightmodel/position/local_y", False),
    ("local_z", "sim/flightmodel/position/local_z", False),
    ("view_x", "sim/graphics/view/view_x", False),
    ("view_y", "sim/graphics/view/view_y", False),
    ("view_z", "sim/graphics/view/view_z", False),
    ("view_hdg", "sim/graphics/view/view_heading", False),
    ("view_pitch", "sim/graphics/view/view_pitch", False),
    ("view_type", "sim/graphics/view/view_type", False),
    ("fov_deg", "sim/graphics/view/field_of_view_deg", False),
    ("vis_sm", "sim/weather/aircraft/visibility_reported_sm", False),
    ("vis_m", "sim/weather/visibility_reported_m", False),
    ("paused", "sim/time/paused", False),
    ("sim_time_s", "sim/time/total_running_time_sec", False),
    ("frame_s", "sim/time/framerate_period", False),   # U10 stutter
)

#: X-Plane's command "Force reloading the current scenery" (its own
#: ``Resources/plugins/Commands.txt``; the Developer menu's "Reload
#: Scenery").
RELOAD_SCENERY = "sim/operation/reload_scenery"

_M_PER_DEG = 111_320.0

#: The camera is never farther than this from the aircraft (m): an outside
#: view, a tower or a free camera stays within it.  A larger offset is the
#: two read in different local frames while a flight loads (#2028), and the
#: aircraft's own position is taken.
MAX_CAMERA_OFFSET_M = 50_000.0

#: :attr:`PositionReader.error` while X-Plane's clock is not running.
LOADING = "X-Plane is loading a flight (its clock is not running)"


def base_url(port: int = DEFAULT_PORT, host: str = "localhost") -> str:
    """The Web API v2 root on ``host:port``."""
    return f"http://{host}:{int(port)}/api/v2"


def now_stamp() -> dict:
    """``{"utc": ISO time, "t": epoch seconds}`` for a record."""
    t = time.time()
    return {"utc": _dt.datetime.fromtimestamp(t, _dt.timezone.utc)
            .isoformat(timespec="milliseconds"), "t": round(t, 6)}


def _get(url: str, timeout: float = 2.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


def resolve_refs(base: str | None = None, refs=POS_REFS,
                 timeout: float = 2.0) -> tuple[dict[str, int], list[str]]:
    """Key -> dataref id, and the optional datarefs X-Plane lacks.  A
    missing required one raises ``KeyError``."""
    base = base or base_url()
    ids, missing = {}, []
    for key, ref, req in refs:
        q = urllib.parse.quote(ref, safe="")
        data = _get(f"{base}/datarefs?filter%5Bname%5D={q}", timeout)["data"]
        if data:
            ids[key] = data[0]["id"]
        elif req:
            raise KeyError(f"required dataref missing: {ref}")
        else:
            missing.append(ref)
    return ids, missing


def read_position(ids: dict[str, int], base: str | None = None,
                  timeout: float = 2.0) -> dict:
    """One ``pos`` record: every resolved dataref's value, stamped."""
    base = base or base_url()
    rec = {"kind": "pos", **now_stamp()}
    for key, ident in ids.items():
        v = _get(f"{base}/datarefs/{ident}/value", timeout)["data"]
        rec[key] = round(float(v), 6) if isinstance(v, (int, float)) else v
    return rec


class PositionReader:
    """Position reads that survive X-Plane's id resets and dropped
    connections: :meth:`read` returns a ``pos`` record or ``None`` (the
    error is in :attr:`error`); the ids are forgotten on any error and
    resolved again on the next read.

    ``settled_only`` (the default): a record is trusted only while
    X-Plane's clock runs -- it moved since the reader's last record, or
    it ran before and the sim is paused now.  A record from a frozen,
    unpaused clock (X-Plane starting or loading a flight: its datarefs
    are not yet the flight's) is ``None`` with :data:`LOADING` and
    :attr:`loading` set; a record with no clock is trusted (an X-Plane
    without the dataref).  The recorder reads every record
    (``settled_only=False``).

    :attr:`resets` counts good reads that follow a failure or a load after
    an earlier good read (a flight load, spec §4.5)."""

    def __init__(self, base: str | None = None, refs=POS_REFS,
                 timeout: float = 2.0, settled_only: bool = True):
        self.base = base or base_url()
        self.refs = refs
        self.timeout = timeout
        self.settled_only = settled_only
        self.ids: dict[str, int] = {}
        self.missing: list[str] = []
        self.resets = 0
        self.errors_since_ok = 0
        self.down_since: float | None = None
        self.error = ""
        self.resolved = False     # True right after a (re)resolve
        self.loading = False      # the last record came from a frozen clock
        self._seen_ok = False
        self._down = False        # a failure or a load since the last good read
        self._clock: float | None = None
        self._running = False

    def read(self) -> dict | None:
        """One ``pos`` record, or ``None`` on any failure or while X-Plane
        loads."""
        self.resolved = False
        try:
            if not self.ids:
                self.ids, self.missing = resolve_refs(
                    self.base, self.refs, self.timeout)
                self.resolved = True
            rec = read_position(self.ids, self.base, self.timeout)
            if not all(isinstance(rec.get(k), (int, float))
                       for k in ("lat", "lon")):
                # X-Plane answers while a flight loads with no position yet
                raise ValueError("no position yet (lat/lon not a number)")
        except Exception as e:          # menu, load, restart, stale ids...
            self.ids = {}
            self._fail(repr(e)[:300])
            return None
        self.loading = self.settled_only and not self._clock_runs(rec)
        if self.loading:                # the ids stand: X-Plane answers
            self._fail(LOADING)
            return None
        if self._seen_ok and self._down:
            self.resets += 1
        self._seen_ok, self._down = True, False
        return rec

    def _fail(self, error: str) -> None:
        self.errors_since_ok += 1
        self._down = True
        if self.down_since is None:
            self.down_since = time.time()
        self.error = error

    def _clock_runs(self, rec: dict) -> bool:
        """X-Plane's clock moved since the last record, or ran before and
        the sim is paused; ``True`` when the record has no clock."""
        clock = rec.get("sim_time_s")
        if not isinstance(clock, (int, float)):
            return True
        previous, self._clock = self._clock, float(clock)
        if previous is not None and clock > previous:
            self._running = True
        elif not (self._running and rec.get("paused")):
            self._running = False       # frozen, or reset by a new flight
        return self._running

    def recovered(self) -> tuple[float, int] | None:
        """After a good read that ended a failure: ``(seconds down,
        errors)``, and the failure is forgotten; else ``None``."""
        if self.down_since is None:
            return None
        out = (time.time() - self.down_since, self.errors_since_ok)
        self.down_since, self.errors_since_ok = None, 0
        return out


def command_id(name: str, base: str | None = None,
               timeout: float = 2.0) -> int | None:
    """The id of X-Plane's command ``name``, or ``None`` when it has none:
    no flight is loaded (the list is empty until one is), or X-Plane is
    older than 12.1.4 (no ``/commands``).  A dropped connection raises."""
    base = base or base_url()
    q = urllib.parse.quote(name, safe="")
    try:
        data = _get(f"{base}/commands?filter%5Bname%5D={q}", timeout)["data"]
    except urllib.error.HTTPError as error:
        if error.code in (400, 404):    # invalid_command_name, no endpoint
            return None
        raise
    return int(data[0]["id"]) if data else None


def activate_command(name: str, base: str | None = None,
                     duration_s: float = 0.0, timeout: float = 5.0) -> bool:
    """Press and release X-Plane's command ``name``; ``True`` when X-Plane
    took the request, ``False`` when it has no such command.  X-Plane may
    carry a long command out before it answers (a scenery reload stalls
    it), so no answer within ``timeout`` after the request was sent still
    counts as taken; a refused connection raises."""
    base = base or base_url()
    ident = command_id(name, base)
    if ident is None:
        return False
    request = urllib.request.Request(
        f"{base}/command/{ident}/activate",
        data=json.dumps({"duration": float(duration_s)}).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as answer:
            answer.read()
    except TimeoutError:                # sent; X-Plane is busy doing it
        return True
    except urllib.error.HTTPError as error:
        if error.code == 404:           # invalid_command_id
            return False
        raise
    return True


def reload_scenery(base: str | None = None) -> bool:
    """Ask X-Plane to reload the current scenery (every ``.ter``, DSF and
    texture is read again; the sim stalls while it does).  ``True`` when
    the request was taken."""
    return activate_command(RELOAD_SCENERY, base)


def camera_position(rec: dict) -> tuple[float, float]:
    """The camera's ``(lat, lon)``: the aircraft's, moved by the camera's
    offset from it in X-Plane's local frame (x east, z south, metres);
    the aircraft's when the record has no camera, or the camera is more
    than :data:`MAX_CAMERA_OFFSET_M` from it."""
    lat, lon = float(rec["lat"]), float(rec["lon"])
    try:
        east = float(rec["view_x"]) - float(rec["local_x"])
        north = -(float(rec["view_z"]) - float(rec["local_z"]))
    except (KeyError, TypeError, ValueError):
        return lat, lon
    if math.hypot(east, north) > MAX_CAMERA_OFFSET_M:
        return lat, lon                 # two frames: a flight loading
    cos_lat = max(1e-6, math.cos(math.radians(lat)))
    return lat + north / _M_PER_DEG, lon + east / (_M_PER_DEG * cos_lat)


def camera_agl_m(rec: dict) -> float:
    """The camera's height above the ground (m): the aircraft's ``y_agl``
    plus the camera's height over the aircraft in the local frame (+y
    up), clamped at 0; 0 (the ground) when the record has no ``agl_m``.
    The ground under an outside camera is taken as the aircraft's."""
    try:
        agl = float(rec["agl_m"])
    except (KeyError, TypeError, ValueError):
        return 0.0
    try:
        agl += float(rec["view_y"]) - float(rec["local_y"])
    except (KeyError, TypeError, ValueError):
        pass
    return agl if agl > 0.0 else 0.0


def poll_positions(emit, stop: threading.Event, period: float,
                   base: str | None = None) -> None:
    """The recorder's loop.  Never gives up: any failure forgets the ids
    and retries every ``period`` s for the whole recording; at most one
    ``pos_error`` per 30 s; ``pos_resumed`` on the first good read after
    a failure."""
    reader = PositionReader(base, settled_only=False)
    last_err = 0.0
    while not stop.is_set():
        t0 = time.time()
        rec = reader.read()
        if rec is None:
            if t0 - last_err > 30:
                emit({"kind": "pos_error", **now_stamp(),
                      "error": reader.error,
                      "errors_since_ok": reader.errors_since_ok})
                last_err = t0
        else:
            if reader.resolved:
                emit({"kind": "pos_refs", **now_stamp(),
                      "found": sorted(reader.ids), "missing": reader.missing})
            emit(rec)
            back = reader.recovered()
            if back is not None:
                emit({"kind": "pos_resumed", **now_stamp(),
                      "down_s": round(back[0], 1), "errors": back[1]})
        stop.wait(max(0.05, period - (time.time() - t0)))
