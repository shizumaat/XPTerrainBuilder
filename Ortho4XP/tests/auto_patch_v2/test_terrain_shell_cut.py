"""The terrain step's cut and rim fill at a terrain model's box and skirt
(owner RULINGS 2026-11-26b).  (2) THE BOX'S GAPS: a posting inside a
plan's box that the plan does not cover (a notch) is bounded by no member
and the rim fill raises it like any posting outside the plan -- no
``nan`` reaches the bound.  (4) THE SKIRT (#2217 option (b)): the ground
is never cut under a model's rim-connected buried region -- the model
sits as authored and our ground covers its skirt, no moat.  Synthetic
grids on a stand-in tile window, no corpus."""
import math
import os
import sys
import types

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from auto_patch import terrain_cut_stage as TCS  # noqa: E402
from auto_patch_v2.airport import terrain_cut as TC  # noqa: E402
from auto_patch_v2.airport import terrain_model as TM  # noqa: E402
from auto_patch_v2.geom.terrain_deck import CELL_M, UNDER_M, DeckGrid, target_at  # noqa: E402

LAT, LON = -22.5, -43.5
STEP_M = 5.0


def _tile(ground, half_m=700.0):
    """A stand-in tile whose raster is a ``STEP_M`` window around (LAT,
    LON); ``ground(x, y)`` its height at frame metres."""
    kx = 111_320.0 * math.cos(math.radians(LAT))
    n = int(2 * half_m / STEP_M) + 1
    dx, dy = STEP_M / kx, STEP_M / 111_320.0
    tlat, tlon = math.floor(LAT), math.floor(LON)
    w, nn = LON - half_m / kx, LAT + half_m / 111_320.0
    lons = w + dx * np.arange(n)
    lats = nn - dy * np.arange(n)
    glon, glat = np.meshgrid(lons, lats)
    to_xy, _ll = TC.projector(LAT, LON)
    alt = np.asarray(ground(*to_xy(glon.ravel(), glat.ravel())), np.float32).reshape(n, n)
    dem = types.SimpleNamespace(alt_dem=alt, x0=w - tlon, x1=float(lons[-1]) - tlon,
                                y0=float(lats[-1]) - tlat, y1=nn - tlat)
    return types.SimpleNamespace(lat=tlat, lon=tlon, dem=dem)


def _rec(z0=10.0):
    return {"id": "dsf:obj1", "resource": "m.obj", "seat": TM.SEAT, "elevation": z0,
            "cut": {"file": "m.obj", "lat": LAT, "lon": LON, "heading": 0.0, "fill": True}}


def _at(tile, x, y):
    from auto_patch_v2.airport import terrain_fill as TF
    d = tile.dem
    ny, nx = d.alt_dem.shape
    r = TF.Raster(d.alt_dem, tile.lon + d.x0, tile.lat + d.y1, (d.x1 - d.x0) / (nx - 1),
                  (d.y1 - d.y0) / (ny - 1))
    _xy, to_ll = TC.projector(LAT, LON)
    return r.sample(*to_ll(np.atleast_1d(np.asarray(x, float)),
                           np.atleast_1d(np.asarray(y, float))))


def _notched(n=61):
    """A flat SKIN (top == bot == 0) over ``n`` x ``n`` cells centred on the
    anchor, a notch 3 cells wide cut 30 cells deep into its south side."""
    h = (n - 1) / 2.0
    top = np.zeros((n, n))
    top[29:32, 31:] = np.nan       # authored j grows south (-z north)
    return DeckGrid(-h * CELL_M, -h * CELL_M, top.copy(), top)


@pytest.fixture(autouse=True)
def _dry(monkeypatch):
    """No mapped water on the stand-in tile."""
    monkeypatch.setattr(TCS, "_wet", lambda tile, dem, rows, cols: np.zeros(len(rows), bool))


def test_a_posting_in_the_box_the_plan_does_not_cover_is_filled(monkeypatch):
    g = _notched()
    monkeypatch.setattr(TM, "plan_grid", lambda p: g)
    tile = _tile(lambda x, y: np.zeros(len(x)))
    fit = TCS._fit(_rec())
    to_xy, to_ll = TC.projector(LAT, LON)
    # the notch's centre lies inside the plan's box, on no covered cell
    nx_, ny_ = 0.0, -0.5 * 30 * CELL_M - 5.0 * CELL_M
    _i, _j, inside = fit.grid.cell_of(*fit.local(np.array([nx_]), np.array([ny_])))
    assert not inside.any()
    cap = TCS._bound([TCS._composite(_rec(), (10.0, 7.0))])(*to_ll(np.array([nx_]),
                                                                    np.array([ny_])))
    assert np.isposinf(cap).all(), "an uncovered cell in the box is bounded by no member"
    TCS.bake(tile, [_rec()])
    # the rim hangs 10 m over the ground: the notch is filled toward it
    z = float(_at(tile, nx_, ny_)[0])
    assert z > 5.0
    assert z <= 10.0 - UNDER_M + 1e-3


def test_target_at_never_carries_nan():
    g = _notched()
    fit = TC.cut_fit(g, 0.0, 0.0)
    xs, ys = np.meshgrid(np.linspace(-200, 200, 81), np.linspace(-200, 200, 81))
    for ground in (np.inf, 3.0):
        z, ok = target_at(fit, xs.ravel(), ys.ravel(), np.full(xs.size, ground))
        assert not np.isnan(z).any()
        assert np.all(z[~ok] == ground)


def _skirted_hill(n=61, skirt=4, drop=20.0):
    """A HILL (top == bot) rising 1 m per cell from its rim, its outer
    ``skirt`` cells a skirt dropping ``drop`` m under the rim's level."""
    h = (n - 1) / 2.0
    i, j = np.mgrid[0:n, 0:n]
    edge = np.minimum.reduce([i, j, n - 1 - i, n - 1 - j]).astype(float)
    top = np.where(edge < skirt, -drop * (skirt - edge) / skirt, edge - skirt)
    return DeckGrid(-h * CELL_M, -h * CELL_M, top.copy(), top), edge


def test_the_skirt_is_the_rim_connected_buried_lower_edge():
    g, edge = _skirted_hill()
    ground = np.zeros(g.top.shape)            # flat ground at the model's zero
    ground[28:33, 28:33] = 80.0               # a coarse DEM's bump over the body
    sk = TC.buried_skirt(g, ground)
    assert sk[edge < 4].all(), "the skirt under the ground round it is buried"
    assert not sk[edge >= 4].any(), "the body over the ground is not"
    assert not sk[28:33, 28:33].any(), "a body a bump covers is no skirt (it rises over its edge)"
    # buried but not reaching the edge: no skirt
    assert not TC.buried_skirt(g, np.where(edge < 2, -50.0, 0.0)).any()


def test_the_ground_is_never_cut_under_the_skirt_no_moat(monkeypatch):
    g, _edge = _skirted_hill()
    monkeypatch.setattr(TM, "plan_grid", lambda p: g)
    bump = lambda x, y: np.where(np.hypot(x, y) < 12.0, 80.0, 10.0)  # noqa: E731
    rec = dict(_rec(), cut=dict(_rec()["cut"], fill=False))
    tile = _tile(bump)
    before = tile.dem.alt_dem.copy()
    TCS.bake(tile, [rec])
    a = tile.dem.alt_dem
    h = (g.top.shape[0] - 1) / 2.0 * CELL_M
    # the rim's ground (the skirt, 10-20 m over its top) stands as it was
    for x, y in ((h - 2.0, 0.0), (0.0, -h + 2.0), (-h + 4.0, 0.0)):
        assert float(_at(tile, x, y)[0]) == pytest.approx(10.0, abs=1e-3)
    # the bump over the body is cut to the top as 13k rules
    assert float(_at(tile, 0.0, 0.0)[0]) < 80.0 - 1.0
    assert np.all(a <= before + 1e-6)
    # without THE SKIRT the cut lowers the rim toward the skirt's bottom
    monkeypatch.setattr(TCS, "_skirted", lambda r: False)
    moat = _tile(bump)
    TCS.bake(moat, [rec])
    assert float(_at(moat, h - 2.0, 0.0)[0]) < 10.0 - 5.0


def test_a_ground_object_and_a_rock_run_out_have_no_skirt():
    assert TCS._skirted(_rec())
    assert not TCS._skirted(dict(_rec(), cut=dict(_rec()["cut"], erode_m=5.0)))
    assert not TCS._skirted(dict(_rec(), cut=dict(_rec()["cut"], floor_m=3.0)))
    assert not TCS._skirted(dict(_rec(), cut=dict(_rec()["cut"], rim_only=True)))
