"""THE THRESHOLD'S HEIGHT OVER ITS RUNWAY END — the datum of an end's
approach surface (owner RULINGS 2026-10-15m (1); audit row 5): FAA AC
150/5300-13B Tables 3-2 to 3-4 start each approach surface at the
THRESHOLD's elevation, while the end-profile rows are stated against the
runway END.  With a displaced threshold the two differ by the runway's own
grade over the displaced length (KASE 33: 314 m).

Read from the two CIFP threshold elevations the profile is pinned to: the
straight line through them, extended to each end, gives ``z_thr - z_end``
= ``g · displaced`` at end a and ``-g · displaced`` at end b.  A runway
with fewer than two CIFP thresholds, or no displacement, reads 0 (the
surface starts at the end's own level, as before)."""
from __future__ import annotations

__all__ = ["threshold_datums"]


def threshold_datums(rw) -> tuple[float, float]:
    """``(z_thr - z_end at end a, ... at end b)`` for runway ``rw``.  The
    grade runs between the two PINS where they sit (``RunwayEnd.pin_along``,
    issue #1358: a CIFP pin at its own landing threshold); the datum is
    stated at the apt.dat displaced threshold, where the surface starts."""
    a, b = rw.ends
    da, db = float(a.displaced_m or 0.0), float(b.displaced_m or 0.0)
    if a.threshold_elev_m is None or b.threshold_elev_m is None or (da <= 0.0 and db <= 0.0):
        return (0.0, 0.0)
    pa, pb = (float(e.pin_along()) if hasattr(e, "pin_along") else float(e.displaced_m or 0.0)
              for e in (a, b))
    span = float(rw.length_m) - pa - pb
    if span <= 0.0:
        return (0.0, 0.0)
    g = (float(b.threshold_elev_m) - float(a.threshold_elev_m)) / span
    return (g * da, -g * db)
