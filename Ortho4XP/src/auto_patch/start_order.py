"""The order a tile's airport builds START in: the longest first.

The tile's vector step ends when its LAST airport ends, and the airports
start one at a time — each start ships the tile DEM to its worker (762 MB
pickled on +33-112, about a second each) and, when the session's machine
slots run short, waits for a slot.  Started in task order, the long pole
started late: on +33-112 KPHX (467 s) was the 4th of 5 starts, on
+43-080 CYYZ (438 s) the 5th of 7 (measured 2026-11-24).  Started longest
first, nothing waits on its predecessors' starts.

The prediction is the session's own (``o4_engine.airport_time_model``):
the airport's recorded solves, else its size.  Only the START order moves:
every build reads the same inputs and the driver reports and verifies the
results in task order, so the outputs are those of any other order.
"""
from __future__ import annotations

__all__ = ["longest_first"]


def longest_first(tasks: list) -> list:
    """``tasks`` (each a dict with ``"icao"``) longest predicted build
    first, task order among equals; ``tasks``' own order when no
    prediction can be read."""
    try:
        from o4_engine import airport_time_model as _model
        seconds = _model.predict_each([t["icao"] for t in tasks])
    except Exception:
        return list(tasks)
    order = sorted(range(len(tasks)),
                   key=lambda i: (-float(seconds.get(tasks[i]["icao"]) or 0.0), i))
    return [tasks[i] for i in order]
