"""#2206 lane llate: an item memo over a function that ASKS THE DEM
(``airport/dem_memo``) serves an answer only while the DEM gives every
answer it read again, and says the questions into the asking run's
recorder on a hit as on a miss (``airport/dem_record``); the units' level
reading (``planar/unit_levels_read``) is held by everything it reads."""
from __future__ import annotations

import dataclasses as _dc
import types

import numpy as np
from auto_patch_v2.airport import dem_memo
from auto_patch_v2.airport.dem_record import DemRecorder
from auto_patch_v2.geom import item_memo as im
from auto_patch_v2.planar import unit_levels_read as ulr


class _Dem:
    """A plane DEM; ``lift`` moves it."""

    def __init__(self, lift: float = 0.0) -> None:
        self.lift = lift

    def z(self, x, y):
        return 0.5 * x + 0.25 * y + self.lift

    def z_many(self, xs, ys):
        return 0.5 * np.asarray(xs, float) + 0.25 * np.asarray(ys, float) + self.lift


def _reading(dem):
    """A function of a key that reads the DEM at three points."""
    return float(dem.z(1.0, 2.0) + dem.z_many([3.0, 4.0], [5.0, 6.0]).sum())


def test_a_dem_reading_is_served_while_the_dem_answers_the_same():
    m = im.ItemMemo("test.dem")
    dem, calls = _Dem(), []

    def compute(d):
        calls.append(1)
        return _reading(d)
    first = dem_memo.asked(m, ("k",), dem, compute)
    again = dem_memo.asked(m, ("k",), dem, compute)
    assert again == first and len(calls) == 1
    fresh = dem_memo.asked(m, ("k",), _Dem(lift=0.125), compute)
    assert len(calls) == 2 and fresh == _reading(_Dem(lift=0.125))


def test_the_questions_reach_the_listening_recorder_on_a_hit_as_on_a_miss():
    m = im.ItemMemo("test.dem.witness")
    dem = _Dem()
    records = []
    for _ in range(2):
        outer = DemRecorder(dem)
        outer.recording(True)
        dem_memo.asked(m, ("w",), outer, _reading)
        records.append(outer.record())
    plain = DemRecorder(dem)
    plain.recording(True)
    _reading(plain)
    want = plain.record()
    for rec in records:
        assert np.array_equal(rec["samples"]["xy"], want["samples"]["xy"])
        assert np.array_equal(rec["samples"]["z"], want["samples"]["z"])
        assert rec["calls"] == want["calls"] and rec["attrs"] == want["attrs"]
    closed = DemRecorder(dem)                     # a closed window hears nothing
    dem_memo.asked(m, ("w",), closed, _reading)
    assert closed.record()["samples"]["z"].size == 0


def test_the_level_key_reads_the_run_fields_by_what_is_read_of_them():
    from shapely.geometry import box

    @_dc.dataclass(frozen=True)
    class _Ap:
        partition: object
        dem: object
        flat_site: object
        deck_stacks: tuple
    part, law = object(), object()
    a = _Ap(part, _Dem(), None, ())

    unit = box(0, 0, 1, 1)

    def key(ap, lw=law, air=unit, ground=None):
        return ulr._levels_key(ap, lw, air, ground, ())
    # another DEM object (asked, never keyed): the same key
    assert key(_dc.replace(a, dem=_Dem(3.0))) == key(a)
    fa = _dc.replace(a, flat_site=types.SimpleNamespace(signals={"s2_source_class": "lidar"}))
    fb = _dc.replace(a, flat_site=types.SimpleNamespace(signals={"s2_source_class": "lidar"}))
    assert key(fa) == key(fb)                     # the class it reads, not the object
    for other in (_dc.replace(a, partition=object()), fa, _dc.replace(a, deck_stacks=(1,))):
        assert key(other) != key(a)
    assert key(a, lw=object()) != key(a)
    assert key(a, air=box(0, 0, 1, 2)) != key(a)
    assert key(a, ground=box(2, 2, 3, 3)) != key(a)
