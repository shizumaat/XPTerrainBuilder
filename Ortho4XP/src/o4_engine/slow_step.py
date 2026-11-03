"""The slow-step alert (issue #1351): when one step of one tile runs too
long, say what it is doing, why it is slow and when it should finish,
and offer the answers the step supports.

The ENGINE owns the threshold, the words and the list of options; both
front ends show the :class:`~o4_engine.events.SlowStep` event verbatim
and answer with the ``slow_step_choice`` command.

* **When.** A step alerts once it has run past ``slow_step_alert_minutes``
  (an app setting, default 5; 0 turns the alert off) AND past what this
  machine's recorded builds say it takes (the step's learned estimate
  from :mod:`o4_engine.tile_time_model` times :data:`EXPECTED_MARGIN`) —
  a step whose record says it takes forty minutes is not "slow" at five.
  No per-airport or per-region number exists here.
* **What / why.** A counted phase that registered its words with
  :mod:`o4_engine.task_meter` (the approach-ring cells, the airport
  insets) names itself and its reason; any other step is described by its
  name, how long it has run and what its recorded builds took.
* **ETA.** The session's live remaining-time estimate for the step (the
  same figure as the run clock, floored by the phase's own pace).
* **Options.** "Continue" and "Cancel this tile" always; "Use coarser
  data" only while the slowest phase said it can finish on coarser data.
  An open alert is re-sent every :data:`REFRESH_SECONDS` with a fresh
  ETA until it is answered or the step ends, then closed (``resolved``).
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

import O4_File_Names as FNAMES

from .task_meter import request_coarser, slowest_phase
from .events import SlowStep

__all__ = ["DEFAULT_ALERT_MINUTES", "EXPECTED_MARGIN", "OPTION_LABELS",
           "REFRESH_SECONDS", "SlowStepWatch"]

#: The owner's five minutes (#1351); ``slow_step_alert_minutes`` raises it
#: or, at 0, turns the alert off.
DEFAULT_ALERT_MINUTES = 5

#: A step is judged against its recorded duration with this much slack:
#: a step that has not yet outrun its own record is not slow.
EXPECTED_MARGIN = 1.25

#: An open alert's ETA is refreshed this often.
REFRESH_SECONDS = 30.0

#: The answers and their button words, in the order a front end shows them.
OPTION_LABELS = {
    "continue": "Continue",
    "coarser": "Use coarser data",
    "cancel": "Cancel this tile",
}


def _alert_after_seconds(minutes=None) -> Optional[float]:
    """The threshold in seconds, ``None`` when the alert is off.

    ``minutes`` defaults to the ``slow_step_alert_minutes`` app setting
    (:data:`DEFAULT_ALERT_MINUTES` when it is unreadable)."""
    if minutes is None:
        try:
            import O4_Config_Utils as CFG
            minutes = getattr(CFG, "slow_step_alert_minutes",
                              DEFAULT_ALERT_MINUTES)
        except Exception:
            minutes = DEFAULT_ALERT_MINUTES
    try:
        minutes = float(minutes)
    except (TypeError, ValueError):
        minutes = float(DEFAULT_ALERT_MINUTES)
    return minutes * 60.0 if minutes > 0 else None


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


def _why(step, phase):
    """``(why, reason)``: the phase's own words and pace, else the record."""
    if phase is not None and (phase["why"] or phase["seconds_per_unit"]):
        why = phase["why"]
        if phase["seconds_per_unit"]:
            why = (why.rstrip(".") + "; at the current rate" if why
                   else "At the current rate") + (
                " each one takes %s." % _spoken_duration(
                    phase["seconds_per_unit"]))
        return why, phase["reason"] or "slow_phase"
    expected = step["expected"]
    if expected:
        return ("Earlier builds like this one took %s for this step."
                % _spoken_duration(expected), "longer_than_recorded")
    return ("There is no earlier build of this step to compare with.",
            "no_record")


def _words(step, phase, elapsed, remaining):
    """``(title, message, reason, options)`` of one alert."""
    title = "Tile %s: the %s step is slow" % (
        FNAMES.short_latlon(*step["tile"]), step["name"])
    ran = "It has run for %s." % _spoken_duration(elapsed)
    what = phase["what"].rstrip(".") + ". " + ran if phase else ran
    why, reason = _why(step, phase)
    eta = ("At the current rate it should finish in %s."
           % _spoken_duration(remaining) if remaining is not None
           else "There is no estimate of when it will finish yet.")
    options = ["continue"]
    if phase is not None and phase["coarser"]:
        options.append("coarser")
    options.append("cancel")
    return title, "\n\n".join((what, why, eta)), reason, tuple(options)


class SlowStepWatch:
    """The running step of ONE session's in-process build, watched.

    :meth:`begin` / :meth:`end` frame a step; :meth:`poll` (the session's
    ~1 Hz heartbeat) emits the alert once the step is slow and refreshes
    it; :meth:`choose` is the user's answer.  Thread-safe."""

    def __init__(self, emit: Callable):
        self._emit = emit
        self._lock = threading.Lock()
        self._step: Optional[dict] = None

    def begin(self, tile, step_key, step_name, expected_seconds=None,
              alert_after=None, now=None):
        """A step started.  ``alert_after`` (seconds) defaults to the
        setting; 0 turns the alert off."""
        self.end()
        if alert_after is None:
            alert_after = _alert_after_seconds()
        threshold = None
        if alert_after:
            threshold = max(alert_after,
                            EXPECTED_MARGIN * float(expected_seconds or 0.0))
        with self._lock:
            self._step = {
                "tile": (int(tile[0]), int(tile[1])), "key": str(step_key),
                "name": str(step_name), "expected": expected_seconds,
                "t0": time.time() if now is None else now,
                "threshold": threshold, "alerted": False, "answered": False,
                "last": 0.0, "phase": None,
            }

    def end(self):
        """The step ended: close its alert if one is open."""
        with self._lock:
            step, self._step = self._step, None
        if step and step["alerted"] and not step["answered"]:
            self._resolved(step)

    def poll(self, remaining_seconds: Callable = lambda: None, now=None):
        """Emit or refresh the alert when the running step is slow;
        returns the event sent, or ``None``."""
        now = time.time() if now is None else now
        with self._lock:
            step = self._step
            if (step is None or step["answered"] or step["threshold"] is None
                    or now - step["t0"] < step["threshold"]
                    or (step["alerted"]
                        and now - step["last"] < REFRESH_SECONDS)):
                return None
            step["alerted"], step["last"] = True, now
        try:
            remaining = remaining_seconds()
        except Exception:
            remaining = None
        phase = slowest_phase()
        with self._lock:
            step["phase"] = phase["key"] if phase else None
        elapsed = now - step["t0"]
        title, message, reason, options = _words(step, phase, elapsed,
                                                 remaining)
        event = SlowStep(
            lat=step["tile"][0], lon=step["tile"][1], step_key=step["key"],
            title=title, message=message, reason=reason, options=options,
            option_labels=tuple(OPTION_LABELS[o] for o in options),
            elapsed_seconds=round(elapsed, 1),
            expected_seconds=step["expected"],
            eta_seconds=None if remaining is None else round(remaining, 1))
        self._emit(event)
        return event

    def choose(self, tile, choice) -> bool:
        """The user's answer for the tile's open alert: ``"continue"``
        (never ask again for this step) or ``"coarser"`` (the slowest
        phase finishes its remaining units on coarser data); either closes
        the alert.  False when the tile has no open alert or the answer
        is not one it offered.  ``"cancel"`` is the session's per-tile
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
