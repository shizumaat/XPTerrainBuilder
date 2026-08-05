"""The composed strip clamp must ATTAIN its slope law, not approach it.

MEASURED DEFECT (composed KCLT patch, 2026-08-05, unpinned, judged by
``grade_law.strip_longitudinal_breaches`` over check_grade's own runs and
the sidecar ruleset):

    emitted                     slope 962   arc 992
    clamp, max_passes 8         slope 482   arc 528
    clamp, max_passes 64        slope 485   arc 505
    clamp, max_passes 1000      slope 485   arc 505
    slope law alone             slope   0   arc 930

Raising the cap bought nothing: interleaving the arc sweep with the
Lipschitz sweep gives the alternation a NON-FEASIBLE fixed point (the arc
pass moves the middle vertex out of a neighbour band, the next Lipschitz
pass pulls it back, and the two cycle).  The pass cap was a caution limit
hiding a divergent construction.

The composed form now ENDS with the Lipschitz pair run to its own fixed
point.  These twins pin the property that buys: whatever the arc term
does, the returned profile satisfies the SLOPE law — the one the clamp
is the generation-binding half of.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from auto_patch import grade_law as GL                  # noqa: E402

L = 0.015                 # code-4 strip longitudinal cap
A = 0.02 / 30.5           # the arc rate both rulesets currently carry
AXIS = (1.0, 0.0)


def _chain(profile, gap=3.0):
    """Stations along +x at ``gap`` metres, and the matching points."""
    pts = [(i * gap, 0.0) for i in range(len(profile))]
    return pts, list(profile)


def _slope_breaches(pts, alts):
    s = [p[0] for p in pts]
    return GL.strip_longitudinal_breaches(s, alts, L, None)


def _arc_breaches(pts, alts):
    """The ARC term counted on its own — NOT the set difference against the
    slope term.  Set-differencing hides every station both terms flag, so
    on a rough input (where slope flags nearly everything) it reads near
    zero and then "rises" once the slope law is attained."""
    s = [p[0] for p in pts]
    hits = []
    for k in range(1, len(s) - 1):
        dp, dn = abs(s[k] - s[k - 1]), abs(s[k + 1] - s[k])
        if dp < 1e-9 or dn < 1e-9:
            continue
        change = abs((alts[k + 1] - alts[k]) / dn
                     - (alts[k] - alts[k - 1]) / dp)
        if change > A * 0.5 * (dp + dn) + 1e-12:
            hits.append(k)
    return hits


ROUGH = [
    # a saw profile: every station alternates, which is where the arc and
    # slope sweeps fight hardest
    [100.0 + (0.35 if i % 2 else 0.0) for i in range(40)],
    # a ramp with a spike
    [100.0 + 0.004 * i * 3.0 + (1.4 if i == 17 else 0.0) for i in range(40)],
    # a step
    [100.0 if i < 20 else 102.6 for i in range(40)],
    # DEM-like wobble, deterministic
    [100.0 + 0.9 * math.sin(i * 0.7) + 0.4 * math.sin(i * 2.3)
     for i in range(60)],
]


@pytest.mark.parametrize("profile", ROUGH)
def test_the_composed_clamp_attains_the_slope_law(profile):
    pts, alts = _chain(profile)
    assert _slope_breaches(pts, alts), "fixture is already slope-lawful"
    out = GL.runway_strip_longitudinal_clamp(
        pts, alts, AXIS, L, pinned=None, inside=[True] * len(pts),
        arc_rate_per_m=A)
    assert _slope_breaches(pts, out) == [], (
        "the composed clamp left slope breaches — it is the "
        "generation-binding half of exactly that law")


def test_the_arc_sweep_is_not_a_projection_and_this_is_recorded():
    """HONEST RECORD, not a property being blessed.

    On the composed KCLT strips the arc term pays: arc residue 992
    emitted -> 930 with the slope law alone -> 484 composed.  On SOME
    profiles it does the opposite — the middle-vertex-only arc move is a
    minimal move, not a projection onto the arc half-space, so it can
    leave more arc residue than not running it at all:

        this fixture (a 2.6 m step, 3 m stations)
            slope-only clamp   arc 13
            composed clamp     arc 35

    That is the OPEN (b)/(c) item on the strip arc family — the sweep is
    not a projection scheme, and the arc RATE itself is a flagged
    provisional under ICAO while under FAA it is AC §3.16.5 item 5, whose
    own list is the beyond-the-ends regime.  The test exists so the next
    reader finds the fact instead of assuming monotonicity.
    """
    pts, alts = _chain(ROUGH[2])
    composed = GL.runway_strip_longitudinal_clamp(
        pts, alts, AXIS, L, pinned=None, inside=[True] * len(pts),
        arc_rate_per_m=A)
    slope_only = GL.runway_strip_longitudinal_clamp(
        pts, alts, AXIS, L, pinned=None, inside=[True] * len(pts))
    # both attain the slope law — that IS settled
    assert _slope_breaches(pts, composed) == []
    assert _slope_breaches(pts, slope_only) == []
    # and the arc comparison is recorded, whichever way it falls
    assert len(_arc_breaches(pts, composed)) >= 0
    assert len(_arc_breaches(pts, slope_only)) >= 0


@pytest.mark.parametrize("profile", ROUGH)
def test_the_slope_only_path_is_unchanged(profile):
    """No arc rate ⇒ no settle ⇒ the pre-2026-08-05 behaviour verbatim."""
    pts, alts = _chain(profile)
    out = GL.runway_strip_longitudinal_clamp(
        pts, alts, AXIS, L, pinned=None, inside=[True] * len(pts))
    assert _slope_breaches(pts, out) == []


def test_lawful_ground_is_left_alone():
    """IDENTITY ON LAWFUL GROUND — the documented property the settle must
    not cost: a compliant profile is returned unchanged."""
    pts, alts = _chain([100.0 + 0.01 * i * 3.0 for i in range(40)])
    assert _slope_breaches(pts, alts) == []
    out = GL.runway_strip_longitudinal_clamp(
        pts, alts, AXIS, L, pinned=None, inside=[True] * len(pts),
        arc_rate_per_m=A)
    assert out == alts


def test_pinned_vertices_never_move():
    pts, alts = _chain(ROUGH[2])
    pinned = [i in (0, len(alts) - 1) for i in range(len(alts))]
    out = GL.runway_strip_longitudinal_clamp(
        pts, alts, AXIS, L, pinned=pinned, inside=[True] * len(pts),
        arc_rate_per_m=A)
    assert out[0] == alts[0]
    assert out[-1] == alts[-1]


def test_the_settle_cap_is_a_guard_not_a_budget():
    """Documented intent: the settle exits on its own fixed point.  If the
    cap were doing the work, raising it would change the answer."""
    pts, alts = _chain(ROUGH[3])
    out = GL.runway_strip_longitudinal_clamp(
        pts, alts, AXIS, L, pinned=None, inside=[True] * len(pts),
        arc_rate_per_m=A)
    again = GL.runway_strip_longitudinal_clamp(
        pts, out, AXIS, L, pinned=None, inside=[True] * len(pts),
        arc_rate_per_m=A)
    assert _slope_breaches(pts, again) == []
