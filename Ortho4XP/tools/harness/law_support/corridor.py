"""The apron spine CORRIDOR COVER the constraint generator asks for.

COPIED from ``apron_terrace.py`` on 2026-09-17 (lane ``v1retire`` round 1, ruling (d)
of the stage-B brief: "the census stays engine-neutral BY IMPLEMENTATION").
`tools/check_grade.py` priced v2 patches with law machinery that lived in
modules the v1 deletion takes; what it USES is copied here ONCE, verbatim, and
the census reads it from the harness.  Values that are law live in
``auto_patch/config.py`` (KEEP) or ``auto_patch_v2/law/*.toml`` and are
IMPORTED, never re-spelled.

Do not edit to change behaviour: this is a transcription, and the acceptance
was a census A/B on the same HECA patch bytes reading IDENTICAL.
"""

from __future__ import annotations

from auto_patch.config import APRON_TERRACE_CORRIDOR_HALF_WIDTH_M
from auto_patch.config import APRON_TERRACE_JOINT_CLEARANCE_M
from shapely.errors import GEOSException, TopologicalError
from shapely.ops import unary_union


_GEOM_EXC = (ValueError, GEOSException, TopologicalError, AttributeError)


def corridor_cover_radius_m() -> float:
    """THE corridor-cover radius: the corridor half-width plus the joint
    clearance (13.5 m).  ONE function, so :func:`corridor_cover` and
    :func:`spine_corridor_cover` cannot drift, and so the value the apron
    within-shape population is read at (RULINGS 2026-08-21b) is the SAME
    existing constant pair the terrace law already uses — no new constant.
    ⚠ Flagged for owner ratification: the ruling names "the spine corridor
    cover" without naming a radius, and this is the engine's only one."""
    return float(APRON_TERRACE_CORRIDOR_HALF_WIDTH_M
                 + APRON_TERRACE_JOINT_CLEARANCE_M)


def spine_corridor_cover(lines):
    """The SPINE half of :func:`corridor_cover`: every taxi/route centerline
    (ground-vehicle SVC spines INCLUDED) buffered by
    :func:`corridor_cover_radius_m` — and nothing else.

    THE APRON WITHIN-SHAPE POPULATION reads THIS (RULINGS 2026-08-21b, spec
    §1): a frontage chord's far endpoint must lie on the SPINE it grades to.
    The full :func:`corridor_cover` additionally carries the frontage chords,
    the runway-strip footprint and every building pad — the no-cross set a
    terrace joint must avoid — and a cover containing the pads would make
    every pair touching a building "in the corridor", which is not the ruled
    population.

    ``lines`` is an iterable of shapely LineStrings in the reader's own metre
    frame (both readers pass their ``GradeContext.centerlines`` geometry, the
    ONE spine enumeration ``grade_graph.centerline_specs`` /
    ``verification.taxi_axes_ll`` share).  Returns a shapely geometry, or
    ``None`` when the layout has no corridor at all."""
    pieces = [ls for ls in (lines or ())
              if ls is not None and not getattr(ls, "is_empty", True)]
    if not pieces:
        return None
    try:
        cover = unary_union(pieces).buffer(corridor_cover_radius_m())
    except _GEOM_EXC:                                     # pragma: no cover
        return None
    if cover is None or cover.is_empty:
        return None
    return cover

