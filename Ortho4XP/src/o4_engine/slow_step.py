"""The stuck-step alert (issue #1351): when one step of one tile is
STUCK -- never merely long -- say what is stuck and why, and offer the
answers the step supports.

The ENGINE owns the rules, the words and the list of options; both
front ends show the :class:`~o4_engine.events.SlowStep` event verbatim
and answer with the ``slow_step_choice`` command.

* **When (owner 2026-11-04).** A step alerts only while one of these
  holds, each read from the process's own telemetry; a step that runs
  long because many tiles are queued or the processor is shared never
  alerts:

  1. a download has STALLED (no data for :data:`STALL_SECONDS`) or is
     CRAWLING (below :data:`CRAWL_BYTES_PER_SECOND` for
     :data:`CRAWL_SECONDS`) -- :func:`o4_engine.download_meter.activity`;
  2. a server keeps REFUSING (:data:`REFUSAL_COUNT` refused or failed
     requests and nothing served during the step);
  3. a counted phase finished NO unit for :data:`NO_PROGRESS_SECONDS` --
     :func:`o4_engine.task_meter.idlest_phase`;
  4. a cache lock held by another process has been waited for
     :data:`LOCK_WAIT_SECONDS` -- :func:`O4_File_Lock.lock_waits`;
  5. the disk the build writes to has less than
     :data:`DISK_FREE_MIN_BYTES` free.

  The ``slow_step_alert_minutes`` app setting is the on/off switch (0 =
  off, any other value on).  No per-airport or per-region number exists
  here.  An open alert closes by itself when its condition clears.
* **ETA.** The session's live remaining-time estimate for the step.
* **Options.** "Continue" (never ask again for this step) and "Cancel
  this tile" always; "Use coarser data" only while the running phase
  said it can finish on coarser data.  An open alert is re-sent every
  :data:`REFRESH_SECONDS` with fresh words until it is answered, it
  clears, or the step ends, then closed (``resolved``).
"""

from __future__ import annotations

import os
import shutil
import threading
import time
from typing import Callable, Optional

import O4_File_Lock as FLOCK
import O4_File_Names as FNAMES

from . import download_meter
from .events import SlowStep
from .task_meter import idlest_phase, request_coarser, slowest_phase

__all__ = ["CRAWL_BYTES_PER_SECOND", "CRAWL_SECONDS", "DEFAULT_ALERT_MINUTES",
           "DISK_FREE_MIN_BYTES", "LOCK_WAIT_SECONDS", "NO_PROGRESS_SECONDS",
           "OPTION_LABELS", "REFRESH_SECONDS", "REFUSAL_COUNT",
           "STALL_SECONDS", "SlowStepWatch"]

#: ``slow_step_alert_minutes``' default: any value above 0 turns the
#: alert on (the setting no longer sets a time, #1351 2026-11-04).
DEFAULT_ALERT_MINUTES = 5

#: Rule 1 (owner 2026-11-04): a download in flight with no data for this
#: long has stalled ...
STALL_SECONDS = 120.0
#: ... and one moving less than this for :data:`CRAWL_SECONDS` crawls.
CRAWL_BYTES_PER_SECOND = 50 * 1024
CRAWL_SECONDS = 300.0
#: A provider that sends no byte progress is measured in completed
#: requests: this many in the crawl window is progress, not a crawl.
CRAWL_MIN_REQUESTS = 10

#: Rule 2: this many refused or failed requests from one server, with
#: nothing served by it during the step.
REFUSAL_COUNT = 10

#: Rule 3: a counted phase that finished no unit for this long is hung.
NO_PROGRESS_SECONDS = 600.0

#: Rule 4: a cache lock held by another process, waited for this long.
LOCK_WAIT_SECONDS = 300.0

#: Rule 5: less free space than this on the disk the build writes to,
#: checked every :data:`DISK_CHECK_SECONDS`.
DISK_FREE_MIN_BYTES = 500 * 1024 * 1024
DISK_CHECK_SECONDS = 15.0

#: An open alert's words are refreshed this often.
REFRESH_SECONDS = 30.0

#: The answers and their button words, in the order a front end shows them.
OPTION_LABELS = {
    "continue": "Continue",
    "coarser": "Use coarser data",
    "cancel": "Cancel this tile",
}


def _alert_on(minutes=None) -> bool:
    """Whether the alert is on: ``minutes`` (default the
    ``slow_step_alert_minutes`` app setting) above 0; unreadable reads
    as :data:`DEFAULT_ALERT_MINUTES`."""
    if minutes is None:
        try:
            import O4_Config_Utils as CFG
            minutes = getattr(CFG, "slow_step_alert_minutes",
                              DEFAULT_ALERT_MINUTES)
        except Exception:
            minutes = DEFAULT_ALERT_MINUTES
    try:
        return float(minutes) > 0
    except (TypeError, ValueError):
        return DEFAULT_ALERT_MINUTES > 0


def _spoken_duration(seconds) -> str:
    """``"about 3 min"``, ``"about 1 h 20 min"``, ``"less than a minute"``."""
    seconds = max(float(seconds or 0.0), 0.0)
    if seconds < 60.0:
        return "less than a minute"
    minutes = int(round(seconds / 60.0))
    if minutes < 60:
        return "about %d min" % minutes
    hours, minutes = divmod(minutes, 60)
    return ("about %d h" % hours if not minutes
            else "about %d h %d min" % (hours, minutes))


# ---------------------------------------------------------------------
# The five stuck rules: each returns ``(reason, what, why)`` or None.
# ---------------------------------------------------------------------
def _download_stuck(step, now, act):
    """Rule 1: in flight, and no data for STALL_SECONDS, or a crawl."""
    busy = act["busy_since"]
    if not act["in_flight"] or busy is None:
        return None
    quiet_since = max(busy, act["last_progress"] or busy, step["t0"])
    if now - quiet_since >= STALL_SECONDS:
        return ("download_stalled",
                "Downloading has stopped: no data has arrived for %s."
                % _spoken_duration(now - quiet_since),
                "The server is not answering or the connection dropped; "
                "it may recover on its own.")
    then = [s for s in step["samples"] if s[0] <= now - CRAWL_SECONDS]
    if busy > now - CRAWL_SECONDS or not then:
        return None
    (t_then, bytes_then, requests_then) = then[-1]
    rate = (act["bytes"] - bytes_then) / max(now - t_then, 1.0)
    if (rate >= CRAWL_BYTES_PER_SECOND
            or act["requests"] - requests_then >= CRAWL_MIN_REQUESTS):
        return None
    return ("download_crawling",
            "Downloading is crawling: %.1f KB/s over the last %s."
            % (rate / 1024.0, _spoken_duration(now - t_then)),
            "The server or the connection is very slow.")


def _provider_refusing(step, act):
    """Rule 2: one server refused REFUSAL_COUNT requests, served none."""
    for host, (served, refused) in sorted(act["hosts"].items()):
        (served0, refused0) = step["hosts0"].get(host, (0, 0))
        count = refused - refused0
        if count >= REFUSAL_COUNT and served == served0:
            return ("provider_refusing",
                    "The server %s has refused or failed %d requests and "
                    "sent no data." % (host, count),
                    "It may be down, or it may not accept these requests.")
    return None


def _no_progress(step, now, phase):
    """Rule 3: a counted phase finished no unit for NO_PROGRESS_SECONDS
    (its idle time counted from the step's start at the earliest)."""
    if phase is None:
        return None
    idle = min(phase["idle_seconds"], now - step["t0"])
    if idle < NO_PROGRESS_SECONDS:
        return None
    what = phase["what"].rstrip(".") or "Working: %d of %d done" % (
        phase["done"], phase["total"])
    return ("no_progress",
            "%s. Nothing has finished for %s." % (what,
                                                  _spoken_duration(idle)),
            "The step looks hung.")


def _lock_wait(step, now):
    """Rule 4: a cache lock held by another process, LOCK_WAIT_SECONDS."""
    for lock_path, since in FLOCK.lock_waits():
        waited = now - max(since, step["t0"])
        if waited >= LOCK_WAIT_SECONDS:
            return ("lock_wait",
                    "Waiting for another build to finish with %s (%s so "
                    "far)." % (os.path.basename(lock_path[:-5] or lock_path),
                               _spoken_duration(waited)),
                    "Another build on this machine holds that file.")
    return None


def _disk_full(step, now):
    """Rule 5: the build's disk below DISK_FREE_MIN_BYTES free."""
    if now - step["disk_checked"] < DISK_CHECK_SECONDS:
        return step["disk_verdict"]
    step["disk_checked"], step["disk_verdict"] = now, None
    for path in step["disk_paths"]:
        try:
            free = shutil.disk_usage(path).free
        except OSError:
            continue
        if free < DISK_FREE_MIN_BYTES:
            step["disk_verdict"] = (
                "disk_full",
                "The disk holding %s has only %d MB free." % (
                    path, free // (1024 * 1024)),
                "Writing stops when the disk is full; free some space "
                "and the build carries on.")
            break
    return step["disk_verdict"]


def _disk_paths():
    """The folders the build writes to: the Tiles and temporary folders."""
    paths = []
    for path in (FNAMES.Tile_dir, FNAMES.Tmp_dir):
        if path and os.path.isdir(path) and path not in paths:
            paths.append(path)
    return tuple(paths)


def _words(step, stuck, coarser, remaining):
    """``(title, message, options)`` of one alert."""
    (_reason, what, why) = stuck
    title = "Tile %s: the %s step is stuck" % (
        FNAMES.short_latlon(*step["tile"]), step["name"])
    eta = ("At the current rate it should finish in %s."
           % _spoken_duration(remaining) if remaining is not None
           else "There is no estimate of when it will finish yet.")
    options = ["continue"] + (["coarser"] if coarser else []) + ["cancel"]
    return title, "\n\n".join((what, why, eta)), tuple(options)


class SlowStepWatch:
    """The running step of ONE session's in-process build, watched.

    :meth:`begin` / :meth:`end` frame a step; :meth:`poll` (the session's
    ~1 Hz heartbeat) emits the alert while the step is stuck, refreshes
    it and closes it when it clears; :meth:`choose` is the user's answer.
    Thread-safe."""

    def __init__(self, emit: Callable):
        self._emit = emit
        self._lock = threading.Lock()
        self._step: Optional[dict] = None

    def begin(self, tile, step_key, step_name, enabled=None, now=None):
        """A step started.  ``enabled`` defaults to the setting."""
        self.end()
        if enabled is None:
            enabled = _alert_on()
        if enabled:
            download_meter.watch_transfers()
        act = download_meter.activity()
        with self._lock:
            self._step = {
                "tile": (int(tile[0]), int(tile[1])), "key": str(step_key),
                "name": str(step_name), "enabled": bool(enabled),
                "t0": time.time() if now is None else now,
                "alerted": None, "answered": False, "last": 0.0,
                "phase": None, "samples": [], "hosts0": act["hosts"],
                "disk_paths": _disk_paths(), "disk_checked": float("-inf"),
                "disk_verdict": None,
            }

    def end(self):
        """The step ended: close its alert if one is open."""
        with self._lock:
            step, self._step = self._step, None
        if step and step["alerted"] and not step["answered"]:
            self._resolved(step)

    def _stuck(self, step, now):
        """The first stuck rule that holds, and the phase it concerns."""
        act = download_meter.activity()
        step["samples"].append((now, act["bytes"], act["requests"]))
        while (len(step["samples"]) > 1
               and step["samples"][1][0] <= now - CRAWL_SECONDS):
            step["samples"].pop(0)
        idle = idlest_phase()
        hung = _no_progress(step, now, idle)
        if hung:
            return hung, idle
        stuck = (_download_stuck(step, now, act)
                 or _provider_refusing(step, act)
                 or _lock_wait(step, now) or _disk_full(step, now))
        return stuck, (slowest_phase() if stuck else None)

    def poll(self, remaining_seconds: Callable = lambda: None, now=None):
        """Emit, refresh or close the alert of the running step; returns
        the event sent, or ``None``."""
        now = time.time() if now is None else now
        with self._lock:
            step = self._step
            if step is None or step["answered"] or not step["enabled"]:
                return None
            (stuck, phase) = self._stuck(step, now)
            if stuck is None:
                cleared, step["alerted"] = step["alerted"], None
            elif (step["alerted"] == stuck[0]
                  and now - step["last"] < REFRESH_SECONDS):
                return None
            else:
                cleared = None
                step["alerted"], step["last"] = stuck[0], now
                step["phase"] = phase["key"] if phase else None
        if stuck is None:
            if cleared:
                self._resolved(step)
            return None
        try:
            remaining = remaining_seconds()
        except Exception:
            remaining = None
        title, message, options = _words(
            step, stuck, bool(phase and phase["coarser"]), remaining)
        event = SlowStep(
            lat=step["tile"][0], lon=step["tile"][1], step_key=step["key"],
            title=title, message=message, reason=stuck[0], options=options,
            option_labels=tuple(OPTION_LABELS[o] for o in options),
            elapsed_seconds=round(now - step["t0"], 1),
            eta_seconds=None if remaining is None else round(remaining, 1))
        self._emit(event)
        return event

    def choose(self, tile, choice) -> bool:
        """The user's answer for the tile's open alert: ``"continue"``
        (never ask again for this step) or ``"coarser"`` (the phase
        finishes its remaining units on coarser data); either closes the
        alert.  False when the tile has no open alert or the answer is
        not one it offered.  ``"cancel"`` is the session's per-tile
        stop, not this watch's."""
        with self._lock:
            step = self._step
            if (step is None or step["tile"] != (int(tile[0]), int(tile[1]))
                    or not step["alerted"] or step["answered"]
                    or choice not in ("continue", "coarser")):
                return False
            phase = step["phase"]
            step["answered"] = True
        if choice == "coarser" and not (
                phase and request_coarser(phase)):
            with self._lock:
                step["answered"] = False
            return False
        self._resolved(step)
        return True

    def _resolved(self, step):
        self._emit(SlowStep(lat=step["tile"][0], lon=step["tile"][1],
                            step_key=step["key"], resolved=True))
