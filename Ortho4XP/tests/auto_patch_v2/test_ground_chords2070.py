"""#2070 (ENTC 69.680905, 18.907925): a road-family ring chord follows its
ground (``planar/ground_chords``).  MEASURED on the ENTC capture:
``small_roads:-255`` ran ONE 48 m chord from a car park (DEM 5.76) to the
apron edge (7.76) across a 1.3 m bank to apron-level ground (7.97); the
drawn road stood 1.14 m under that ground for 30 m.  The twin is that
profile: a split where the bank is, none on ground the chord follows."""
from __future__ import annotations

import types

import numpy as np
import pytest
from auto_patch_v2.law import Law
from auto_patch_v2.planar import ground_chords as GC


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _bank(xs, ys):
    """The ENTC section: car park 5.8 m to x=10, a bank to 7.8 m at x=18,
    then level apron-height ground to the pavement at x=48."""
    xs = np.asarray(xs, dtype=float)
    return np.interp(xs, [0.0, 10.0, 18.0, 48.0], [5.8, 6.4, 7.8, 7.8])


def _worst(points, ground):
    """The largest departure of the drawn chords (straight between the
    ground at each vertex) from the ground under them."""
    worst = 0.0
    for (ax, ay), (bx, by) in zip(points, points[1:], strict=False):
        t = np.linspace(0.0, 1.0, 97)
        xs, ys = ax + (bx - ax) * t, ay + (by - ay) * t
        za, zb = ground([ax], [ay])[0], ground([bx], [by])[0]
        worst = max(worst, float(np.max(np.abs(za + (zb - za) * t - ground(xs, ys)))))
    return worst


def test_a_chord_across_a_bank_is_split_where_the_ground_turns():
    chord = [(0.0, 0.0), (48.0, 0.0)]
    assert _worst(chord, _bank) > 1.0                      # the ENTC cut
    out = GC.follow_ground(chord, _bank, 0.5, 2.0, 4.0)
    assert out[0] == chord[0] and out[-1] == chord[-1]
    assert len(out) > 2
    assert all(y == 0.0 for _x, y in out)                  # on the chord it splits
    assert _worst(out, _bank) <= 0.5
    xs = [x for x, _y in out]
    assert xs == sorted(xs) and min(np.diff(xs)) >= 4.0    # no piece under the floor


def test_a_chord_its_ground_follows_gains_nothing():
    def slope(xs, ys):
        return 3.0 + 0.04 * np.asarray(xs, dtype=float)
    ring = [(0.0, 0.0), (60.0, 0.0), (60.0, 7.0), (0.0, 7.0), (0.0, 0.0)]
    assert GC.follow_ground(ring, slope, 0.5, 2.0, 4.0) == ring


def test_unread_ground_is_never_a_reason_to_split():
    def blind(xs, ys):
        return np.full(len(np.asarray(xs)), np.nan)
    chord = [(0.0, 0.0), (48.0, 0.0)]
    assert GC.follow_ground(chord, blind, 0.5, 2.0, 4.0) == chord


def test_a_short_chord_is_left_whole():
    chord = [(10.0, 0.0), (17.0, 0.0)]                      # under two floors
    assert GC.follow_ground(chord, _bank, 0.5, 2.0, 4.0) == chord


def test_the_densifier_reads_the_law_and_the_airports_dem(law):
    ch = law.tables.emit.chords
    assert ch.road_ground_sample_m > 0.0 and ch.road_ground_min_chord_m > 0.0
    assert GC.road_ground_densifier(types.SimpleNamespace(dem=None), law) is None
    dem = types.SimpleNamespace(z_many=_bank)
    dens = GC.road_ground_densifier(types.SimpleNamespace(dem=dem), law)
    assert _worst(dens([(0.0, 0.0), (48.0, 0.0)]), _bank) <= law.tables.emit.cockpit.visual_m
    # a DEM that answers one point at a time is read the same way
    one = types.SimpleNamespace(z=lambda x, y: float(_bank([x], [y])[0]))
    assert dens([(0.0, 0.0), (48.0, 0.0)]) == \
        GC.road_ground_densifier(types.SimpleNamespace(dem=one), law)([(0.0, 0.0), (48.0, 0.0)])
