"""The Activity list's row order and status tone (issue #1341).

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

__all__ = ["FINISHED_STATES", "is_finished", "status_tone", "restamp",
           "display_order"]

#: Engine / app states a row does not leave without being queued again.
FINISHED_STATES = ("done", "error", "stopped")


def is_finished(state, label=""):
    """True for a row whose tile has left the run: done, failed, stopped
    here, or drained by the engine (state ``queued``, label ``stopped``)."""
    return state in FINISHED_STATES or label == "stopped"


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
