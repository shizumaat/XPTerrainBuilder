"""Progress INSIDE one running build step, in predicted seconds (#2045).

The owner, 2026-11-13 (+39-105, data mostly cached): the tile bar sat
still for ~90 % of the build while KDEN solved, then raced through the
rest.  Two causes: the vector step's window was capped near a third of
the bar however long its airports take (``session.reweight_plan_by_
seconds``, fixed alongside this module), and inside the step the bar
moved only when an airport crossed one of its seven stage lines — KDEN
spent 9 min in ``[69/100]``.  This clock gives every step a fraction of
its own predicted seconds that moves with the wall clock:

* a step with no percentage of its own (mesh, overlays) creeps along its
  predicted seconds (:func:`_creep`), slowing toward — never reaching —
  its end when it outlives the prediction;
* the vector step is ``pre`` overhead, then the airport solves, then
  ``post`` overhead (:data:`PRE_SHARE` splits the learned overhead).
  The airports solve in parallel workers, so their wall time is the
  longest airport's, or their total over the workers when more airports
  wait than there are workers (:meth:`StepClock._wall`).  Each airport
  moves from its last reported stage percent at its predicted pace
  (``o4_engine.airport_time_model``), so a nine-minute stage moves the
  bar instead of holding it.

:meth:`StepClock.remaining` is the same model read as seconds, for the
run clock (``session._EtaTracker``): an overrun recedes at
``tile_time_model.OVERRUN_REMAINING_FRACTION`` of itself instead of
reading "done".  Pure arithmetic on the times it is given; never raises
past its caller's ``try``.
"""

from __future__ import annotations

import math

from .tile_time_model import remaining_step_seconds

__all__ = ["StepClock", "PRE_SHARE", "for_step", "CLOCK_STEPS"]

#: The steps whose whole-tile percent is this clock's (they report no
#: percentage of their own); masks and imagery move by their bars.
CLOCK_STEPS = ("vector", "mesh", "overlays")

#: Share of the vector step's non-airport seconds spent BEFORE the
#: airports begin (map data, elevation insets, the airports' imagery).
PRE_SHARE = 0.5
#: :func:`_creep` follows the clock linearly up to this fraction ...
CREEP_LINEAR = 0.9
#: ... and then closes on 1 with this time constant (in predictions).
CREEP_TAIL = 0.5
#: The overhead a vector step keeps when its airports were not planned.
OVERHEAD_FLOOR = 0.1
#: A prediction is never shorter than this (seconds).
MIN_SECONDS = 1.0


def _creep(elapsed, predicted):
    """Fraction of a step ``elapsed`` seconds into ``predicted``: linear
    to :data:`CREEP_LINEAR`, then an exponential approach to 1 that never
    arrives (an overrun keeps moving, slower and slower)."""
    predicted = max(float(predicted or 0.0), MIN_SECONDS)
    x = max(float(elapsed), 0.0) / predicted
    if x <= CREEP_LINEAR:
        return x
    return 1.0 - (1.0 - CREEP_LINEAR) * math.exp(
        -(x - CREEP_LINEAR) / CREEP_TAIL)


class StepClock:
    """One running step's fraction done and seconds remaining.

    ``predicted_s`` is the step's predicted seconds; for the vector step
    ``airports`` maps each planned airport to its predicted seconds (the
    plan's guess, replaced by :meth:`airports_begin` with the airports
    the build actually solves)."""

    def __init__(self, key, predicted_s, now, airports=None):
        self.key = key
        self.t0 = float(now)
        self.predicted = max(float(predicted_s or 0.0), MIN_SECONDS)
        planned = dict(airports or {})
        airport_wall = max(planned.values()) if planned else 0.0
        self.overhead = max(self.predicted - airport_wall, MIN_SECONDS)
        self.airports = planned          # icao -> predicted seconds
        self.started = {}                # icao -> first event time
        self.reported = {}               # icao -> reported fraction
        self.reported_at = {}            # icao -> when it last advanced
        self.finished = {}               # icao -> finish time
        self.peak = 0                    # most airports solving at once
        self.begin_at = None             # airports began
        self.end_at = None               # every airport finished
        self._high = 0.0

    # -- feed --------------------------------------------------------------
    def airports_begin(self, predicted, now):
        """The build begins solving these airports (``{icao: seconds}``)."""
        planned = bool(self.airports)
        self.airports = {icao: max(float(s), MIN_SECONDS)
                         for icao, s in dict(predicted).items()}
        if not planned:
            # The step's prediction knew no airports of this tile, so it
            # is a vector step's typical WHOLE time: what the airports
            # do not take of it is the overhead.
            self.overhead = max(self.predicted - self._wall(
                list(self.airports.values())),
                OVERHEAD_FLOOR * self.predicted, MIN_SECONDS)
        self.begin_at = float(now)
        self.end_at = None if self.airports else float(now)

    def airport(self, icao, fraction, finished, now):
        """One airport's report: its stage fraction, or that it ended."""
        if icao not in self.airports:
            return
        self.started.setdefault(icao, float(now))
        self.peak = max(self.peak, len(set(self.started) - set(self.finished)))
        fraction = min(max(float(fraction), 0.0), 1.0)
        if fraction > self.reported.get(icao, 0.0) or icao not in self.reported:
            self.reported[icao] = max(self.reported.get(icao, 0.0), fraction)
            self.reported_at[icao] = float(now)
        if finished:
            self.finished.setdefault(icao, float(now))
            if self.end_at is None and len(self.finished) >= len(self.airports):
                self.end_at = float(now)

    def airport_seconds(self, icao):
        """The airport's measured solve seconds once it finished (first
        report to its end), else None."""
        if icao in self.finished and icao in self.started:
            return self.finished[icao] - self.started[icao]
        return None

    # -- read --------------------------------------------------------------
    def _airport_remaining(self, icao, now):
        if icao in self.finished:
            return 0.0
        predicted = self.airports[icao]
        start = self.started.get(icao)
        if start is None:                      # waiting for a worker
            return predicted
        if now - start >= predicted:           # past its prediction
            return remaining_step_seconds(predicted, now - start)
        return predicted * (1.0 - self._airport_done(icao, now))

    def _airport_done(self, icao, now):
        """The airport's fraction: on from its last stage percent ``p`` at
        its predicted pace (the rest, ``(1 - p) x predicted`` seconds,
        creeping), or its time since its start — whichever is further."""
        if icao in self.finished:
            return 1.0
        start = self.started.get(icao)
        if start is None:
            return 0.0
        predicted = self.airports[icao]
        stage = self.reported.get(icao, 0.0)
        since = now - self.reported_at.get(icao, start)
        onward = stage + (1.0 - stage) * _creep(since, (1.0 - stage) * predicted)
        return max(_creep(now - start, predicted), onward)

    def _workers(self):
        """How many airports solve at once: all of them, until one is
        seen waiting while others run — then the most seen at once."""
        waiting = set(self.airports) - set(self.started)
        if waiting and self.peak:
            return self.peak
        return max(len(self.airports), 1)

    def _wall(self, seconds):
        """Wall seconds of airport work ``seconds`` (per airport) over
        the workers: the longest one, or the total spread over them."""
        if not seconds:
            return 0.0
        return max(max(seconds), sum(seconds) / self._workers())

    def _parts(self):
        """``(pre, airports wall, post)`` predicted seconds."""
        return (self.overhead * PRE_SHARE,
                self._wall(list(self.airports.values())),
                self.overhead * (1.0 - PRE_SHARE))

    def fraction(self, now):
        """Fraction of the step done, monotone, in [0, 1)."""
        now = float(now)
        if self.key != "vector":
            value = _creep(now - self.t0, self.predicted)
        else:
            (pre, wall, post) = self._parts()
            total = pre + wall + post
            if self.begin_at is None:
                done = pre * _creep(now - self.t0, pre)
            elif self.end_at is None:
                remaining = self._wall([
                    self.airports[i] * (1.0 - self._airport_done(i, now))
                    for i in self.airports])
                done = pre + max(wall - remaining, 0.0)
            else:
                done = pre + wall + post * _creep(now - self.end_at, post)
            value = done / total if total > 0 else 0.0
        self._high = max(self._high, min(value, 0.999))
        return self._high

    def remaining(self, now):
        """Predicted seconds left in the step (an overrun recedes)."""
        now = float(now)
        if self.key != "vector":
            return remaining_step_seconds(self.predicted, now - self.t0)
        (pre, wall, post) = self._parts()
        if self.begin_at is None:
            return remaining_step_seconds(pre, now - self.t0) + wall + post
        if self.end_at is None:
            return self._wall([self._airport_remaining(i, now)
                               for i in self.airports]) + post
        return remaining_step_seconds(post, now - self.end_at)


def for_step(tile, key, predicted_s, now):
    """The clock for ``key`` starting now on ``tile``; the vector step
    carries the tile's planned airports, each priced by
    ``airport_time_model`` (``tile_time_model.planned_airports``)."""
    from . import tile_time_model as TTM

    if predicted_s is None:
        predicted_s = TTM.DEFAULT_STEP_SECONDS.get(key, 60.0)
    airports = None
    if key == "vector":
        planned = TTM.planned_airports(*tile)
        if planned:
            airports = predict_airports(planned)
    return StepClock(key, predicted_s, now, airports)


def predict_airports(icaos):
    """``{icao: predicted seconds}`` from the airport time model and the
    tile store's per-airport seconds; never raises."""
    try:
        from . import airport_time_model as ATM
        from . import tile_time_model as TTM

        return ATM.predict_each(list(icaos), TTM.every_record())
    except Exception:
        return {icao: 120.0 for icao in icaos}
