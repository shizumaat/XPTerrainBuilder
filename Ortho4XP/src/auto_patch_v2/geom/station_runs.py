"""THE RUNS OF CONSECUTIVE STATIONS (issues #1996, #1935).

A reading taken every few metres along a line (a covered bore's cut,
``planar/covered_ground``; a mapped bridge's deck in the DEM,
``airport/bridge_ground``) keeps only the stations that read: a station
that reads nothing drops out.  What those stations span — a footprint, an
interpolation along the line — is read PER RUN of consecutive stations,
never across a gap: one dropped station is bridged, a longer gap splits
the run, and a run of fewer than two stations reads nothing."""
from __future__ import annotations

import typing as _t

__all__ = ["section_runs"]


def section_runs(secs: _t.Sequence, station_m: float) -> list[list]:
    """``secs`` (anything with an along-line ``s``, in order) split
    wherever two successive stations stand more than ``2 x station_m``
    apart, runs of fewer than two stations dropped."""
    out: list[list] = []
    run: list = []
    for c in secs:
        if run and c.s - run[-1].s > 2.0 * station_m + 1e-6:
            out.append(run)
            run = []
        run.append(c)
    out.append(run)
    return [r for r in out if len(r) >= 2]
