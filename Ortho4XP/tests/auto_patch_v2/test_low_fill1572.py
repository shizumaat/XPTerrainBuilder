"""Twin of RULINGS 2026-10-28s (3) (Q251 a; #1572): the part of a lower pad
level standing on fill along a lot edge is cut off the level; the rest of
the level, and a level with no lot or no fill, are untouched."""
from __future__ import annotations

import dataclasses as _dc
import types

from auto_patch_v2.law import Law
from auto_patch_v2.planar.low_fill import cut_fill_bands, fill_band
from shapely.geometry import box


class _Dem:
    """Ground 302 over the level, falling to 299.5 over its north 20 m."""

    def z(self, x, y):
        return 302.0 if y < 80.0 else 302.0 - 2.5 * (y - 80.0) / 20.0


@_dc.dataclass
class _R:
    ref: str
    polygon: object
    role: str = "building"


LEVEL = box(0.0, 0.0, 200.0, 100.0)
LOT_N = box(0.0, 100.7, 200.0, 140.0)      # 0.7 m off the level's north edge


def _law():
    return Law.for_airport("ZZZZ")


def test_the_band_is_the_fill_along_the_lot():
    band = fill_band(LEVEL, LOT_N, _Dem(), 1.0, 0.3, 3.0)
    assert band is not None
    y0 = band.bounds[1]
    assert 80.0 <= y0 <= 84.0 and band.bounds[3] == 100.0


def test_no_lot_near_or_no_fill_no_band():
    far = box(0.0, 120.0, 200.0, 140.0)
    assert fill_band(LEVEL, far, _Dem(), 1.0, 0.3, 3.0) is None
    flat = types.SimpleNamespace(z=lambda x, y: 302.0)
    assert fill_band(LEVEL, LOT_N, flat, 1.0, 0.3, 3.0) is None


def test_fill_away_from_the_lot_is_kept():
    lot_s = box(0.0, -40.0, 200.0, -0.7)    # the lot on the high side
    assert fill_band(LEVEL, lot_s, _Dem(), 1.0, 0.3, 3.0) is None


def test_the_cut_leaves_the_level_its_high_part_and_records_it():
    reg = types.SimpleNamespace(landings={"b/p1": {"kind": "low_level", "block": "b"}})
    airport = types.SimpleNamespace(dem=_Dem())
    res = [_R("b/p1", LEVEL), _R("b", box(0.0, -50.0, 200.0, -1.0))]
    counts: dict = {}
    got = cut_fill_bands(res, reg, [LOT_N], airport, _law(), 1.0, counts, "low_level")
    lvl = [r for r in got if r.ref == "b/p1"]
    assert lvl and max(r.polygon.bounds[3] for r in lvl) <= 84.0
    assert [r for r in got if r.ref == "b"][0].polygon.equals(res[1].polygon)
    assert counts["low_level_fill_cut"] == 1 and reg.landings["b/p1"]["fill_cut_m2"] > 0
