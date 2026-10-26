"""The per-step strip of one tile's Activity row (issue #825).

A tile's build reads as six steps, in this order::

    Map data → Airports → Ground → Water → Imagery → Install

each waiting, running or done (or skipped, failed, stopped), a finished
step with its time, and the running Airports step naming the airport and
its stage in plain words ("KSEA — shaping runways (65 %)").

This module is the ONE event -> strip mapping of the Qt window; the Mac
app's twin is ``Sources/SceneryKit/StepStrip.swift``.  Both are pure (the
caller passes the time an event arrived) and both are tested against the
same fixture, ``tests/fixtures/step_strip_cases.json`` — so the two apps
show the same strip for the same events.  The data is what the engine
already sends (``StepProgress``, ``AutoPatchBegin``, ``AutoPatchProgress``,
``TileState``, ``BuildDone``); there is no wire change.
"""

import math

#: (key, display name) in build order.
PILLS = (
    ("map_data", "Map data"),
    ("airports", "Airports"),
    ("ground", "Ground"),
    ("water", "Water"),
    ("imagery", "Imagery"),
    ("install", "Install"),
)
PILL_KEYS = tuple(key for key, _name in PILLS)

#: Engine step key (wire ``StepProgress.step_key``) -> pill.  Airport
#: grading runs inside the ``vector`` step; its own events say so.
STEP_PILLS = {
    "vector": "map_data",
    "mesh": "ground",
    "masks": "water",
    "imagery": "imagery",
    "dsf": "imagery",
    "overlays": "install",
    "overlay": "install",
}

#: An airport build's phase label (``auto_patch.engine_v2.V2_PHASE_LABELS``,
#: ``auto_patch.progress.PHASE_LABELS``; a heartbeat line starts with its
#: phase's label) -> the stage in plain words, matched by lower-case
#: prefix.  Mirrored in StepStrip.swift (``airportStages``).
AIRPORT_STAGES = (
    ("loading airport", "reading the airport"),
    ("loading apt.dat", "reading the airport"),
    ("partitioning the pack", "sorting the airport's shapes"),
    ("classifying", "reading buildings and structures"),
    ("building the planar map", "laying out the surfaces"),
    ("assembling pavement", "laying out runways"),
    ("building taxi", "laying out taxiways"),
    ("generating the law constraints", "setting the grading rules"),
    ("solving", "shaping runways"),
    ("emitting", "writing the airport patch"),
)
AIRPORT_STAGE_DEFAULT = "grading"

#: The glyph in front of each state's name.
GLYPHS = {
    "waiting": "○",
    "running": "●",
    "done": "✓",
    "skipped": "–",
    "failed": "✕",
    "stopped": "■",
}
SEPARATOR = " → "
NBSP = " "

_AUTO_PATCH = "auto-patch"
_REUSED = " · reused"


def new_strip():
    """A strip with every step waiting."""
    return {
        "pills": {key: {"state": "waiting", "started": None,
                        "seconds": None, "reused": False}
                  for key in PILL_KEYS},
        "furthest": -1,
        "airports_total": 0,
        "airports_finished": [],
        "airport_line": "",
        # Built, failed or stopped: later news of this attempt is stale.
        "ended": False,
    }


def airport_stage(label):
    """The plain-words stage of an airport build's progress label."""
    text = str(label or "").strip().lower()
    for prefix, words in AIRPORT_STAGES:
        if text.startswith(prefix):
            return words
    return AIRPORT_STAGE_DEFAULT


def _half_up(value):
    return int(math.floor(value + 0.5))


def clock(seconds):
    """``m:ss``, or ``h:mm:ss`` from an hour on (``ProgressRowText.clock``)."""
    total = _half_up(max(0.0, float(seconds)))
    if total >= 3600:
        return "%d:%02d:%02d" % (total // 3600, (total % 3600) // 60,
                                 total % 60)
    return "%d:%02d" % (total // 60, total % 60)


def _running(strip):
    for key in PILL_KEYS:
        if strip["pills"][key]["state"] == "running":
            return key
    return None


def _finish_running(strip, now, state="done"):
    key = _running(strip)
    if key is None:
        return
    pill = strip["pills"][key]
    pill["state"] = state
    if state == "done" and pill["started"] is not None:
        pill["seconds"] = max(0.0, now - pill["started"])
    if key == "airports":
        strip["airport_line"] = ""


def _enter(strip, key, now):
    """Step ``key`` is running: the one before it is done, any passed
    over are skipped.  News of a step already behind is ignored."""
    index = PILL_KEYS.index(key)
    if index <= strip["furthest"]:
        return False
    _finish_running(strip, now)
    for passed in PILL_KEYS[strip["furthest"] + 1:index]:
        strip["pills"][passed]["state"] = "skipped"
    strip["pills"][key].update(state="running", started=now, seconds=None)
    strip["furthest"] = index
    return True


def _finish_build(strip, now, ok):
    strip["ended"] = True
    if not ok:
        if _running(strip) is None and strip["furthest"] >= 0:
            # The step that ended the build had finished (an airport that
            # failed after the others): it is the one that failed.
            key = PILL_KEYS[strip["furthest"]]
            strip["pills"][key]["state"] = "running"
        _finish_running(strip, now, state="failed")
        return
    _finish_running(strip, now)
    for key in PILL_KEYS:
        pill = strip["pills"][key]
        if pill["state"] == "waiting":
            # The tile is written out whether or not an overlay step ran.
            pill["state"] = "done" if key == "install" else "skipped"
    strip["furthest"] = len(PILL_KEYS) - 1


def stop(strip, now):
    """The user stopped the tile: its running step is stopped, and the
    engine's late news of this attempt changes nothing."""
    if not strip["ended"]:
        _finish_running(strip, now, state="stopped")
        strip["ended"] = True
    return strip


def apply_event(strip, event, now):
    """Fold one engine event, which arrived at ``now`` (seconds), into
    ``strip`` (from :func:`new_strip`) in place; return the strip.

    ``event`` is an ``o4_engine.events`` object; anything but the five
    events above is ignored, and so is everything after the tile was
    built, failed or stopped.  A re-queued tile starts a new strip
    (:func:`new_strip`) — that is the caller's enqueue, not an event.
    """
    kind = type(event).__name__
    if strip["ended"]:
        return strip
    if kind == "StepProgress":
        label = str(event.label or "")
        if label == _AUTO_PATCH or label.startswith(_AUTO_PATCH + " "):
            key = "airports"
        else:
            key = STEP_PILLS.get(event.step_key)
        if key is None:
            return strip
        _enter(strip, key, now)
        if _REUSED in label and strip["pills"][key]["state"] == "running":
            strip["pills"][key]["reused"] = True
    elif kind == "AutoPatchBegin":
        if _enter(strip, "airports", now) or _running(strip) == "airports":
            strip["airports_total"] = len(tuple(event.airports or ()))
    elif kind == "AutoPatchProgress":
        if _running(strip) != "airports":
            if not _enter(strip, "airports", now):
                return strip
        airport = str(event.airport or "")
        if event.status in ("done", "fail"):
            if airport not in strip["airports_finished"]:
                strip["airports_finished"].append(airport)
            strip["airport_line"] = ""
            total = strip["airports_total"]
            if total and len(strip["airports_finished"]) >= total:
                _finish_running(strip, now)
            return strip
        percent = (100.0 * float(event.done) / float(event.total)
                   if event.total else 0.0)
        strip["airport_line"] = "%s — %s (%d %%)" % (
            airport, airport_stage(event.label),
            _half_up(min(max(percent, 0.0), 100.0)))
    elif kind == "TileState":
        if event.state == "done":
            _finish_build(strip, now, ok=True)
        elif event.state == "error":
            _finish_build(strip, now, ok=False)
        elif event.label == "stopped":
            stop(strip, now)
    elif kind == "BuildDone":
        _finish_build(strip, now, ok=bool(event.ok))
    return strip


def segments(strip):
    """``[(state, text)]`` per step, in order: what a row shows.  Words
    of one step are joined by no-break spaces, so a wrapping row breaks
    only between steps (or inside the airport line)."""
    out = []
    for key, name in PILLS:
        pill = strip["pills"][key]
        state = pill["state"]
        text = GLYPHS[state] + NBSP + name.replace(" ", NBSP)
        if key == "airports":
            total = strip["airports_total"]
            if state == "running" and total > 1:
                text += NBSP + "%d/%d" % (
                    len(strip["airports_finished"]), total)
            if state == "running" and strip["airport_line"]:
                text += " · " + strip["airport_line"]
        if state == "done" and pill["reused"]:
            text += NBSP + "reused"
        elif state == "done" and pill["seconds"] is not None:
            text += NBSP + clock(pill["seconds"])
        out.append((state, text))
    return out


def strip_text(strip):
    """The whole strip as one plain line (the segments, arrows between)."""
    return SEPARATOR.join(text for _state, text in segments(strip))
