"""Lane ``tunnelwitness2`` twins — issues #65, #5 [SPJC-3], #12 [OTHH-1]
Q-12b (owner RULINGS 2026-09-27a (3) (4)).

#65: ``structure_service._rise_m`` read the ground over a bore against the
MEAN of its two ends, so a bore under ground that merely slopes read half
its own fall as a hill.  The rise is now the ground standing above THE
LINE BETWEEN THE TWO MOUTH GROUNDS.
"""
from __future__ import annotations

import types

import pytest
from shapely.geometry import LineString

from auto_patch_v2.planar.structure_service import _rise_m


class _Dem:
    provenance = {"source": "fixture"}

    def __init__(self, fn):
        self.fn = fn

    def z(self, x, y):
        return self.fn(x, y)

    def bounds(self):
        return (-20000.0, -20000.0, 20000.0, 20000.0)


def _ap(fn):
    return types.SimpleNamespace(dem=_Dem(fn))


# ── #65: the rise is read against the mouth chord ───────────────────────

def test_a_SLOPING_bore_under_flat_ground_reads_ZERO_rise():
    """SPJC -5724: the DEM falls 21.97 -> 21.44 m along 35 m.  Against the
    mean of the ends it read +0.27 m; against the chord it reads 0.  A
    bore falling 2.0 m (which passed ``terrain_rise_m`` 0.5 before) also
    reads 0."""
    ln = LineString([(300.0, -100.0), (335.0, -100.0)])
    spjc = _ap(lambda x, y: 21.97 - (0.53 / 35.0) * (x - 300.0))
    assert _rise_m(spjc, ln) == pytest.approx(0.0, abs=1e-9)
    steep = _ap(lambda x, y: 30.0 - (2.0 / 35.0) * (x - 300.0))
    assert _rise_m(steep, ln) == pytest.approx(0.0, abs=1e-9)


def test_a_real_HILL_reads_its_rise_over_the_chord_even_on_a_slope():
    """A ridge 3.0 m high over the middle of a bore whose mouths differ by
    2.0 m reads 3.0 m over the chord (the mean-of-ends read 4.0 there —
    the error ran both ways)."""
    ln = LineString([(0.0, 0.0), (100.0, 0.0)])

    def hill(x, y):
        base = 50.0 - 0.02 * x                      # 50.0 -> 48.0
        return base + (3.0 if 40.0 <= x <= 60.0 else 0.0)

    assert _rise_m(_ap(hill), ln) == pytest.approx(3.0, abs=1e-6)
    flat_hill = _ap(lambda x, y: 10.0 + (0.7 if 40.0 <= x <= 60.0 else 0.0))
    assert _rise_m(flat_hill, ln) == pytest.approx(0.7, abs=1e-6)


def test_a_bore_in_a_DIP_reads_no_rise():
    """Ground BELOW the chord everywhere is no cover at all."""
    ln = LineString([(0.0, 0.0), (100.0, 0.0)])
    dip = _ap(lambda x, y: 10.0 - (1.0 if 20.0 <= x <= 80.0 else 0.0))
    assert _rise_m(dip, ln) == pytest.approx(0.0, abs=1e-9)   # the mouths themselves
