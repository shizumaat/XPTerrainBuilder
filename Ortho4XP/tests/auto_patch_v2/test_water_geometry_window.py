"""Issue #1408: ``ProductionDem.water_geometry`` enters only the polygons
that can reach the clip, and each one once per frame.

The flat-site decisions of DEM prep cut every airport's region against the
tile's water (``flat_site._cut_water``).  Each airport has its own frame,
so the water must ENTER each frame (§46 (9) row 16) — but before #1408 the
WHOLE tile's water entered it, point by point, for every airport and every
call: 13.4 s of the vector step's 16.5 s on a 17-airport tile.

The twin: on a synthetic multi-airport tile the answer is byte-identical
to the pre-#1408 loop (kept below as the oracle), the far polygons never
enter, and a repeated call enters nothing.
"""
from __future__ import annotations

import math
import random

import pytest
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union

from auto_patch_v2.airport import dem_production as dp
from auto_patch_v2.airport.dem_production import ProductionDem, TileWater, _entered
from auto_patch_v2.airport.flat_site import _cut_water
from auto_patch_v2.model.frame import Frame

TILE = (51, -1)


def _tile_water() -> TileWater:
    """A tile of many small lakes (some holed), a sea strip along the south
    edge, and a lake wider than the window's span guard that runs on past
    the tile edge — the layer is not cut at the tile edge."""
    rnd = random.Random(1408)
    lakes = []
    for _ in range(400):
        x, y = rnd.uniform(0.0, 1.0), rnd.uniform(0.05, 1.0)
        s = rnd.uniform(0.0005, 0.01)
        shell = [(x + s * math.cos(a / 7 * 2 * math.pi) * rnd.uniform(0.7, 1.0),
                  y + s * math.sin(a / 7 * 2 * math.pi) * rnd.uniform(0.7, 1.0))
                 for a in range(7)]
        hole = None
        if rnd.random() < 0.2:
            h = s * 0.2
            hole = [[(x - h, y - h), (x + h, y - h), (x + h, y + h), (x - h, y + h)]]
        p = Polygon(shell, hole)
        if p.is_valid:
            lakes.append(p)
    wide = Polygon([(-0.4, 0.62), (1.3, 0.60), (1.3, 0.605), (-0.4, 0.625)])
    inland = unary_union(lakes + [wide])
    sea = MultiPolygon([box(-0.05, -0.05, 1.05, 0.04)])
    return TileWater(TILE[0], TILE[1], sea, inland)


def _dem(origin: tuple[float, float], water: TileWater) -> ProductionDem:
    frame = Frame("ZZZZ", origin, 11, input_quantum_m=0.001)
    return ProductionDem.over_prep(frame, "ZZZZ", _NoRaster(), TILE[0], TILE[1],
                                   water, out=lambda _m: None)


class _NoRaster:
    """``over_prep`` reads only these off DEM prep's raster."""
    alt_dem = None
    x0 = x1 = y0 = y1 = 0.0


def _oracle(dem: ProductionDem, bounds, sea_only: bool = False):
    """``water_geometry`` as it stood before #1408: every polygon of the
    tile enters the frame, then is clipped."""
    import shapely
    w = dem.water(*TILE)
    clip = None if bounds is None else box(*bounds)
    out = []
    for p, kind in zip(w.polys, w.kinds):
        if sea_only and kind != "sea":
            continue
        q = shapely.transform(p, lambda c: _entered(c, dem._enter, w.lon, w.lat))
        if clip is not None:
            if not q.intersects(clip):
                continue
            q = q.intersection(clip)
        if not q.is_empty:
            out.append(q)
    if not out:
        return None
    u = unary_union(out)
    return None if u.is_empty else u


def _wkb(g):
    return None if g is None else g.wkb


#: Airports across the tile: inland, on the coast strip, on the wide lake,
#: and one at the tile corner.
ORIGINS = [(51.31, -0.42), (51.03, -0.90), (51.61, -0.05), (51.50, -0.75),
           (51.95, -0.98), (51.20, -0.20)]


@pytest.fixture(scope="module")
def water():
    return _tile_water()


@pytest.mark.parametrize("origin", ORIGINS)
def test_the_windowed_water_is_byte_identical_to_the_whole_tile(water, origin):
    dem = _dem(origin, water)
    rnd = random.Random(hash(origin) & 0xffff)
    boxes = [(-3000.0, -2500.0, 3500.0, 2000.0), (-300.0, -300.0, 300.0, 300.0),
             (-12000.0, -9000.0, 15000.0, 11000.0)]
    for _ in range(12):
        cx, cy = rnd.uniform(-20000, 20000), rnd.uniform(-20000, 20000)
        hw, hh = rnd.uniform(50, 6000), rnd.uniform(50, 6000)
        boxes.append((cx - hw, cy - hh, cx + hw, cy + hh))
    for b in boxes:
        assert _wkb(dem.water_geometry(b)) == _wkb(_oracle(dem, b)), b
        assert _wkb(dem.sea_geometry(b)) == _wkb(_oracle(dem, b, True)), b
    assert _wkb(dem.water_geometry()) == _wkb(_oracle(dem, None))


@pytest.mark.parametrize("origin", ORIGINS)
def test_the_flat_site_cut_is_unchanged(water, origin):
    """The flat-site decision's own reading, ``_cut_water``, with and
    without the airport's land declaration."""
    dem = _dem(origin, water)
    site = box(-2500.0, -1800.0, 2600.0, 1900.0)
    land = box(-1500.0, -300.0, 1500.0, 300.0)

    class _Oracle:
        def water_geometry(self, bounds):
            return _oracle(dem, bounds)

    for ln in (None, land):
        got, got_m2 = _cut_water(dem, site, ln)
        want, want_m2 = _cut_water(_Oracle(), site, ln)
        assert got.wkb == want.wkb and got_m2 == want_m2


def test_far_water_never_enters_and_a_repeat_enters_nothing(water, monkeypatch):
    calls = []

    def counting(coords, enter, lon0, lat0):
        calls.append(len(coords))
        return _entered(coords, enter, lon0, lat0)

    monkeypatch.setattr(dp, "_entered", counting)
    dem = _dem(ORIGINS[0], water)
    b = (-2500.0, -1800.0, 2600.0, 1900.0)
    dem.water_geometry(b)
    first = len(calls)
    assert 0 < first
    # every ring of every polygon is one ``_entered`` call: the window
    # entered a small fraction of the tile's rings
    rings = sum(1 + len(p.interiors) for p in water.polys)
    assert first < rings / 5, (first, rings)
    dem.water_geometry(b)
    dem.sea_geometry(b)
    assert len(calls) == first, "a repeated call re-entered the water"
    # the per-tile lat/lon index is built once and shared by every frame
    bounds = water.bounds_ll()
    _dem(ORIGINS[1], water).water_geometry(b)
    assert water.bounds_ll() is bounds


def test_a_new_witness_is_entered_afresh(water):
    dem = _dem(ORIGINS[0], water)
    b = (-2500.0, -1800.0, 2600.0, 1900.0)
    before = dem.water_geometry(b)
    dem._water = {TILE: TileWater(TILE[0], TILE[1], None, None)}
    assert dem.water_geometry(b) is None and before is not None
