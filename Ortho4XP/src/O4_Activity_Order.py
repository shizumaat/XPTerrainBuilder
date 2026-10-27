"""The Activity list's row order and status tone (issue #1341), which
section a row sits in (#1556), and how the list's native selection and
the map's tile selection stay one selection (#1537).

Finished rows (done, built with warnings, failed, stopped) stay in the
list until the app quits.  Live rows (queued, running) sit on top, the
newest queued batch first; finished rows follow in the order they
finished, the first finished directly under the live block.

Each row carries a STAMP ``[queued, finished]``: the counter value of the
batch that queued it, and of the moment it finished (``None`` while it is
live).  :func:`restamp` advances the stamps from the rows' current states;
:func:`display_order` reads the order off them.  A finished row queued
again (resume, "Build failed tiles again", a new Build) is live once more
and gets a fresh queued stamp, so it returns to the top.

Pure, no Qt.  Twin: ``Sources/SceneryKit/ActivityOrder.swift``; both read
``tests/fixtures/activity_order_cases.json``.
"""

__all__ = ["FINISHED_STATES", "ACTIVITY", "COMPLETED", "is_finished",
           "section", "shown_selected", "list_edit", "status_tone", "restamp",
           "display_order"]

#: Engine / app states a row does not leave without being queued again.
FINISHED_STATES = ("done", "error", "stopped")


def is_finished(state, label=""):
    """True for a row whose tile has left the run: done, failed, stopped
    here, or drained by the engine (state ``queued``, label ``stopped``)."""
    return state in FINISHED_STATES or label == "stopped"


#: The pane sections a row sits in (#1556).
ACTIVITY = "activity"
COMPLETED = "completed"


def section(state):
    """The pane section a row sits in (#1556): a built tile (``done``,
    with or without warnings) leaves Activity for Completed, where its
    row is compact (#1542) -- title, then status and elapsed time, no
    bar, no steps.  Failed, stopped and live rows stay in Activity; a
    completed tile queued again is live, so it moves back."""
    return COMPLETED if state == "done" else ACTIVITY


def shown_selected(rows, selected):
    """The rows the list shows selected (#1537, RULINGS 2026-10-28n):
    every row whose tile is in the map selection.  ``rows`` is every row
    of both sections."""
    return set(rows) & set(selected)


def list_edit(new, shown, active):
    """The map selection after the user changed the list's own selection
    (#1537): ``(selected, active, frame)``.  ``new`` is the list's
    selection now, ``shown`` what it showed before.  The list's selection
    becomes the map selection; the one row the edit added becomes the
    active tile, else the active tile stays if it is still selected, else
    the first.  ``frame``: the edit left one row selected -- a click on
    a row -- which frames its tile on the map (#816)."""
    new = set(new)
    added = new - set(shown)
    if len(added) == 1:
        (active,) = added
    elif active not in new:
        active = min(new) if new else None
    frame = len(new) == 1
    return (new, active, frame)


def status_tone(state, label="", has_issues=False):
    """The status text's colour role: ``live`` (gray), ``done`` (green),
    ``warning`` (gold: built with warnings), ``failed`` (red) or
    ``stopped`` (orange)."""
    if state == "error":
        return "failed"
    if state == "done":
        return "warning" if has_issues else "done"
    if state == "stopped" or label == "stopped":
        return "stopped"
    return "live"


def restamp(rows, stamps, counter):
    """``(stamps, counter)`` after the rows' current states.

    ``rows``: ``(key, finished)`` pairs in the order the rows were made.
    A key absent from ``rows`` loses its stamp.  Every row new to the
    stamps, or live again after finishing, takes ONE shared queued value
    (a batch keeps its own order); each row that has just finished takes
    its own finished value, in ``rows`` order.
    """
    out = {}
    batch = None
    for key, finished in rows:
        old = stamps.get(key)
        if old is not None and not (old[1] is not None and not finished):
            stamp = [old[0], old[1]]
        else:
            if batch is None:
                counter += 1
                batch = counter
            stamp = [batch, None]
        if finished and stamp[1] is None:
            counter += 1
            stamp[1] = counter
        out[key] = stamp
    return (out, counter)


def display_order(keys, stamps):
    """``keys`` (in the order the rows were made) as the list shows them:
    live rows newest batch first, then finished rows in finish order."""
    indexed = list(enumerate(keys))
    live = [(pos, key) for pos, key in indexed
            if (stamps.get(key) or [0, None])[1] is None]
    done = [(pos, key) for pos, key in indexed
            if (stamps.get(key) or [0, None])[1] is not None]
    live.sort(key=lambda item: (-(stamps.get(item[1]) or [0])[0], item[0]))
    done.sort(key=lambda item: (stamps[item[1]][1], item[0]))
    return [key for _pos, key in live + done]
