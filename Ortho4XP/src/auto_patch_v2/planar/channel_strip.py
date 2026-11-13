"""A NECK NEVER INFERS A CUT IN A RUNWAY'S STRIP (§45 (22) PROPOSED, issue
#2038) — lane ``lksfo2038``.

A paved neck (§45 (1) (b)) states only that the airside pavement crosses a
road; the DEPTH under it is INFERRED by §45 (3) (iii), "Cut the road down":
deck top − ``bridge.clearance_m`` (5.1 m) under every deck, climbing at
``ramp_max_grade`` between them.  Where the corridor runs through a
runway's GRADED STRIP that inference contradicts the strip's own law — the
graded portion of a runway strip (Annex 14 §3.4; the FAA RSA) carries no
open cut — so a neck-ONLY channel, with no pack wall/floor object, no
credible lidar and no bridge to state the structure itself, is an at-grade
crossing there and is refused at admission (the one derivation site, beside
§45 (21)'s survey refutation).

The site: KSFO on 1.0.506 (USGS 3DEP down, the inset fell back to
Copernicus, so §45 (21) could not refute the necks).  Seven
``highway=service`` ways crossing the four runways at grade were admitted
as neck-only channels — the RUNWAYS were their decks — and channel:1's
floor, dug 5.1 m under runway 10L/28R and sharing its south edge, dragged
the runway edge to −0.02 m beside a 3.05 m crest: the runway's own laws
went infeasible at 37.6237, −122.3814 (stage 0 hard violation 0.30 m) and
verify read ``runway_vertical_curve`` 1 (−2.01 % over 12 m).

A channel that carries a depth witness is never asked: the pack or the
survey states the cut, and the strip law yields to a witnessed structure.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString
from shapely.ops import substring

from ..airport.runway_strip import strip_band
from ..law import Law
from ..model.airport import Airport

__all__ = ["strip_refusal", "strips_crossed"]


def strips_crossed(airport: Airport, law: Law, axis_ln: LineString,
                   ends: tuple[float, float], half_m: float) -> list[str]:
    """The runway ids whose graded strip (``airport/runway_strip.
    strip_band``, the ONE derivation) the channel's CORRIDOR — the axis
    between its ``ends`` stations ⊕ its half-width ``half_m`` — reaches;
    empty where it reaches none."""
    s0, s1 = min(ends), max(ends)
    run = substring(axis_ln, s0, s1) if s1 > s0 else axis_ln
    corridor = run.buffer(max(half_m, 0.0), cap_style="flat") if half_m > 0.0 else run
    out: list[str] = []
    for rw in airport.runways:
        band = strip_band(rw, law)
        if band is not None and corridor.intersects(band):
            out.append(str(rw.id))
    return out


def strip_refusal(cid: str, ways: _t.Iterable[int], crossed: _t.Sequence[str],
                  n_decks: int) -> str:
    """The NAMED refusal line (the stats every replay publishes)."""
    return (f"{cid}: witnessed by a paved neck alone, its floor only inferred by "
            f"\"Cut the road down\" — and the corridor runs through the graded strip "
            f"of runway(s) {', '.join(crossed)}, which carries no open cut: "
            f"{n_decks} crossing(s) at grade, not a channel (§45 (22) proposed, "
            f"#2038). Ways {'+'.join(str(int(w)) for w in ways)}")
