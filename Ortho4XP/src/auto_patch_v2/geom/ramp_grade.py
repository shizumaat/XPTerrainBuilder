"""THE GRADE A RAMP IS BUILT AT — its design grade, and the cap above it
(owner RULINGS 2026-10-08c (1): "it's a CAP, not a target, it should only
allow more flex where needed"; 2026-10-08d (1); 2026-10-09c (2b)).

A ramp leaves a stated level and runs until it meets the surface it is
going to.  It is built at its DESIGN grade; the cap is the grade it
steepens toward ONLY where the design grade cannot meet that surface in
the run the ramp has, and then at the SMALLEST grade that does.  One
arithmetic for every ramp that has nothing but its run to say how long it
is — a mapped tunnel's approach (``planar/unframed_ramp``, spec §34 (1a))
and a groundside road leaving its airside contact (``airport/road_descent``
and ``constraints/road_ramp``, spec §37 (6)).  Pure numbers: the callers
own the run (where it ends, what level stands at each station).
"""
from __future__ import annotations

import typing as _t

__all__ = ["least_grade", "built_grade", "grade_envelope", "GRADE_SLACK"]

#: The ulp of slack that makes the LEAST grade's own station read as met.
GRADE_SLACK = 1.0 + 1e-9


def least_grade(samples: _t.Iterable[tuple[float, float]]) -> float | None:
    """The SMALLEST grade that meets the surface somewhere in the run:
    ``min |rise| / run`` over ``samples`` = ``(run from the ramp's start,
    surface − start level)`` at each station of the run.  Stations at the
    start itself (``run <= 0``) say nothing; ``None`` when no station
    does."""
    need = None
    for run, rise in samples:
        if run <= 0.0:
            continue
        g = abs(rise) / run
        need = g if need is None else min(need, g)
    return need


def built_grade(need: float | None, design: float, cap: float) -> float | None:
    """The grade the ramp is BUILT at: ``design`` where the design grade
    fits (``need <= design``), else the least grade that fits; ``None``
    where no grade up to ``cap`` does (or the run has no station) — the
    caller's own outcome, never a grade over the cap."""
    if need is None or need > cap + 1e-12:
        return None
    return max(need, design)


def grade_envelope(ss: _t.Sequence[float], vals: _t.Sequence[float], grade: float,
                   lower: bool = False) -> dict[float, float]:
    """The ``grade``-Lipschitz UPPER envelope of the labels ``vals`` at the
    sorted stations ``ss`` of one run: the least profile at or over every
    label that never falls faster than ``grade`` — ONE VALUE PER STATION.
    ``lower``: the LOWER envelope (the least-rising profile at or under
    every label).  The §37 (8) ramp onto a route (``airport/road_ramp``)
    and the dip a linked road run descends into (#1964,
    ``constraints/road_ramp.terrace_profile``)."""
    pick, k = (min, grade) if lower else (max, -grade)
    out = list(vals)
    for i in range(1, len(out)):                            # forward
        out[i] = pick(out[i], out[i - 1] + k * (ss[i] - ss[i - 1]))
    for i in range(len(out) - 2, -1, -1):                   # backward
        out[i] = pick(out[i], out[i + 1] + k * (ss[i + 1] - ss[i]))
    return {s_: z_ for s_, z_ in zip(ss, out, strict=True)}
