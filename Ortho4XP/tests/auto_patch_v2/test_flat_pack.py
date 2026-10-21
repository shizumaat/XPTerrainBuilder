"""THE FLAT-PACK WITNESS (``airport/flat_pack.py``; owner direction
2026-10-20, answers 59-66; spec ``flat-pack-terracing-spec.md`` §1) on
synthetic packs: a shared anchor over a 30 m slope reads ``flat_assumed``,
the same objects anchored each at its own ground read ``follows_terrain``,
a shared anchor on flat ground reads ``follows_terrain``, the apt.dat
``1302 flatten 1`` flag alone reads ``flat_assumed``, and too few objects
read ``no_data``.  Headless, no corpus."""
from __future__ import annotations

import math
import types

from auto_patch_v2.airport import flat_pack as fp
from auto_patch_v2.airport.pack import flatten_declared
from auto_patch_v2.law import Law

_M_PER_DEG = 111_320.0
LAT0, LON0 = 30.0, 31.0


class _Frame:
    def transformers(self):
        k = math.cos(math.radians(LAT0))

        def to_xy(lon, lat):
            return ((lon - LON0) * _M_PER_DEG * k, (lat - LAT0) * _M_PER_DEG)

        def to_ll(x, y):
            return (LON0 + x / (_M_PER_DEG * k), LAT0 + y / _M_PER_DEG)
        return to_xy, to_ll


class _Dem:
    """z rises ``slope`` per metre eastward; a coarse source (30 m pixel)."""

    def __init__(self, slope: float):
        self.slope = slope

    def z(self, x, y):
        return 100.0 + self.slope * x

    def source_pixel_m(self):
        return 30.0, "inset"


def _ll(x: float, y: float = 0.0):
    lon, lat = _Frame().transformers()[1](x, y)
    return (lat, lon)


def _member(i: int, x: float, origin):
    la, lo = _ll(x)
    feet = tuple((la + d, lo + d, 0.0) for d in (0.0, 1e-5, 2e-5))
    part = types.SimpleNamespace(scatter=False, line=False, feet=feet)
    return types.SimpleNamespace(id=f"m{i}", scatter=False, parts=(part,),
                                 base_profile={"feet_y": 0.0}, origin=origin)


def _airport(*, shared: bool, slope: float, n: int = 10, flatten: bool = False):
    xs = [i * 300.0 for i in range(n)]               # 0 .. 2,700 m east
    if shared:
        anchor = _ll(0.0)
        units = [types.SimpleNamespace(anchor=anchor, agl_m=0.0, members=tuple(
            _member(i, x, anchor) for i, x in enumerate(xs)))]
    else:
        units = [types.SimpleNamespace(anchor=_ll(x), agl_m=0.0,
                                       members=(_member(i, x, _ll(x)),))
                 for i, x in enumerate(xs)]
    return types.SimpleNamespace(
        icao="TEST", frame=_Frame(), dem=_Dem(slope),
        partition=types.SimpleNamespace(units=tuple(units)),
        pack=types.SimpleNamespace(flatten_declared=flatten))


LAW = Law.for_airport("TEST")


def test_shared_anchor_over_a_slope_is_flat_assumed():
    v = fp.detect(_airport(shared=True, slope=0.011), LAW)   # ~30 m over the pack
    assert v.verdict == fp.FLAT_ASSUMED and v.witness == "seats"
    assert v.level_share == 1.0 and v.level_m == 100.0
    assert v.relief_m > 8.0


def test_objects_on_their_own_ground_follow_terrain():
    v = fp.detect(_airport(shared=False, slope=0.011), LAW)
    assert v.verdict == fp.FOLLOWS_TERRAIN and v.witness == ""
    assert v.level_share < 0.9


def test_shared_anchor_on_flat_ground_follows_terrain():
    v = fp.detect(_airport(shared=True, slope=0.0), LAW)
    assert v.level_share == 1.0 and v.relief_m == 0.0
    assert v.verdict == fp.FOLLOWS_TERRAIN


def test_flatten_flag_alone_is_flat_assumed():
    v = fp.detect(_airport(shared=False, slope=0.011, flatten=True), LAW)
    assert v.verdict == fp.FLAT_ASSUMED and v.witness == "flatten_flag"


def test_too_few_objects_is_no_data():
    v = fp.detect(_airport(shared=True, slope=0.011, n=2), LAW)
    assert v.verdict == fp.NO_DATA and v.level_share is None


def test_record_and_log_line_are_plain():
    v = fp.detect(_airport(shared=True, slope=0.011), LAW)
    rec = fp.record(v)
    assert rec["verdict"] == "flat_assumed" and rec["signals"]["objects"] == 10
    assert fp.log_line("TEST", v).startswith("[flat-pack] TEST: flat_assumed")


def test_flatten_metadata_read():
    assert flatten_declared(["1 100 0 0 TEST x", "1302 flatten 1"])
    assert not flatten_declared(["1302 flatten 0"])
    assert not flatten_declared(["1302 city Cairo"])


def test_law_table_loads():
    t = LAW.tables.flat_pack
    assert t.detector.level_share_min == 0.9 and t.terrace is False
