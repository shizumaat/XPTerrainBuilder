"""THE WELD OUTRANKS THE CAP — inside the LATE chord limiter too.

HECA round 6 item 4 (spec ``docs/specs/heca-round6-groundside-\
classification-spec.md`` Family C).  The owner's site 30.1055367,\
31.3994026 read "still seems low"; the road's climb to the taxiway
existed but its LEVEL sat ~2 m under the airside weld it touches, and
the contact still stepped.

MEASURED MECHANISM (1.50.1713 patch).  service_junction 756 (way
-10756) shares nodes -10383/-10384 with airside junction 2675 (way
-12675) at byte-identical values 108.30 / 108.27 — the weld EXISTS and
holds.  Its free neighbour -10382 sits 1.30 m from that weld and 8.83 m
from a free node at 106.24, so its chord band is EMPTY: floor 108.20
from the weld, ceiling 106.95 from the free neighbour.
``_chord_cut_and_fill`` resolved that empty band with ``hi``, and its
closing guarantee sweep is cut-only — both one-directional DOWN — so
the node emitted at 106.38, 1.9 m under the weld it touches.  That
asymmetry (pin holds, neighbour is cut) IS the step.

``free_road_profile`` already resolves this exact pair the other way —
"RULING 1 — THE WELD OUTRANKS THE CAP.  The span BUILDS: both welds are
met exactly and the excess stands as a census row" — and the limiter
runs AFTER it (``pipeline._post_projection_conformance_passes`` →
``_grade_limit_groundside_chords``), as the last road-family altitude
writer of the build.  Two writers, opposite dispositions; this file
pins the limiter to the ruling.

The twins below are a single-variable pair: the SAME geometry and the
SAME values, differing only in whether the high end is PINNED.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from auto_patch import config as C                          # noqa: E402
from auto_patch import groundside as G                      # noqa: E402

CAP = C.SERVICE_ROAD_MAX_GRADE

# The measured site, to scale: a straight road arm running away from an
# airside weld.  x is metres along the arm; index 0 is the weld.
_RING = [(0.0, 0.0), (1.30, 0.0), (10.13, 0.0), (41.3, 0.0)]
_VALS = [108.30, 106.38, 106.24, 104.71]


def _run(pinned_high: bool):
    vals = list(_VALS)
    live = list(range(len(_RING)))
    free = live[1:] if pinned_high else list(live)
    G._chord_cut_and_fill(_RING, vals, live, free, CAP)
    return vals


def test_an_empty_band_floored_by_a_weld_builds_up_to_the_weld():
    """The node beside the weld resolves UP to the weld's floor."""
    vals = _run(pinned_high=True)
    assert vals[0] == pytest.approx(108.30, abs=1e-9)   # the weld holds
    # Every free node reaches the weld's own cap-reachable floor.
    for i in (1, 2, 3):
        floor = _VALS[0] - CAP * (_RING[i][0] - _RING[0][0])
        assert vals[i] >= floor - 1e-3, (i, vals[i], floor)
    # The measured node: 106.38 before, now within a cap-length of the
    # weld it touches instead of 1.9 m under it.
    assert vals[1] > 108.0
    assert abs(vals[0] - vals[1]) <= CAP * 1.30 + 1e-3


def test_the_same_band_with_no_weld_still_resolves_DOWN():
    """The single variable is the PIN.  With the high end free, the
    infeasibility is two free neighbours disagreeing — no weld outranks
    anything — and the cut-only disposition is preserved exactly."""
    vals = _run(pinned_high=False)
    assert vals[0] < _VALS[0] - 1.0          # the high end is CUT
    assert max(vals) <= max(_VALS) + 1e-9    # nothing was BUILT
    # And the node the ruling lifts when the end is pinned is not
    # lifted here: it stays under the pinned arm's answer.
    assert vals[1] < _run(pinned_high=True)[1] - 1.0


def test_a_feasible_band_is_untouched_by_the_ruling():
    """``lo_pin <= lo <= hi`` whenever the band is non-empty, so every
    new clause is the identity there: a ring already inside its cap
    comes back byte-identical."""
    ring = [(0.0, 0.0), (50.0, 0.0), (100.0, 0.0)]
    vals = [100.0, 100.5, 101.0]              # 1 % — well inside 8 %
    before = list(vals)
    G._chord_cut_and_fill(ring, vals, list(range(3)), [1, 2], CAP)
    assert vals == before


def test_the_band_reports_its_pinned_bounds_separately():
    """``_chord_band``'s last two returns are the bounds restricted to
    the PINNED generators — the values the ruling keys on."""
    vals = list(_VALS)
    live = list(range(len(_RING)))
    lo, hi, lo_pin, hi_pin = G._chord_band(_RING, vals, live, 1, CAP,
                                           pinned={0})
    assert lo > hi                                   # the band IS empty
    assert lo_pin == pytest.approx(_VALS[0] - CAP * 1.30, abs=1e-9)
    assert lo_pin > hi                               # and the weld wins
    assert lo_pin <= hi_pin                          # the welds agree
    # With no pinned set the bounds are unreported and the old
    # disposition (take ``hi``) is what the kernel must keep.
    _lo, _hi, none_lo, none_hi = G._chord_band(_RING, vals, live, 1, CAP)
    assert none_lo == float("-inf")
    assert none_hi == float("inf")


def test_two_mutually_infeasible_WELDS_keep_the_documented_ceiling():
    """The case ``chord_limit_ring_altitudes`` already answers: a free
    vertex between two welds that cannot both be met takes the CEILING,
    "never a value above a weld it must reach down to".  Disjoint from
    the ruling above, and unchanged by it."""
    ring = [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0)]
    vals = [110.0, 105.0, 100.0]          # ends pinned 10 m apart, 10 m up
    live = list(range(3))
    G._chord_cut_and_fill(ring, vals, live, [1], CAP)
    lo, hi, lo_pin, hi_pin = G._chord_band(ring, vals, live, 1, CAP,
                                           pinned={0, 2})
    assert lo_pin > hi_pin                # the welds are mutually infeasible
    # The free vertex sits at the LOW weld's ceiling, not lifted to the
    # high weld's floor.
    assert vals[1] == pytest.approx(100.0 + CAP * 5.0, abs=1e-6)
