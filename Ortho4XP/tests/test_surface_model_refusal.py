"""#2280: a stereo surface-model inset keeps the base under inland water and
at its blunders (:mod:`elevation_access.surface_model_refusal`)."""
import types

import numpy
from shapely.geometry import box

import O4_Airport_Elevation_Insets as INSETS
from elevation_access.surface_model_refusal import (
    BLUNDER_M,
    blunder_cells,
    refuse_surface_model_cells,
)

ND = -32768.0
# 1 m per degree both ways: the synthetic frames below are in metres.
METRES = (1.0, 1.0)


def _grid(values, x0=0.0, y0=0.0, step=1.0):
    values = numpy.asarray(values, dtype=numpy.float32)
    rows, columns = values.shape
    return types.SimpleNamespace(
        alt_dem=values, nodata=ND, x0=x0, y0=y0,
        x1=x0 + (columns - 1) * step, y1=y0 + (rows - 1) * step,
        nxdem=columns, nydem=rows)


def _block_scene():
    """A 30 m plain; the inset carries a 150 m flat-topped block with
    one-post walls, and a +10 m roof the building mask missed."""
    inset = numpy.full((40, 40), 31.0)
    inset[10:20, 10:20] = 150.0           # the block's flat top
    inset[9, 10:20] = inset[20, 10:20] = 90.0   # its walls, half height
    inset[30:32, 30:32] = 41.0            # a roof: +10 m, kept
    return inset, numpy.full((40, 40), 30.0)


def test_a_blunder_block_goes_whole_walls_and_all():
    inset, base = _block_scene()
    valid = numpy.ones(inset.shape, bool)
    refused = blunder_cells(inset, valid, base, base)
    assert refused[10:20, 10:20].all()
    assert refused[9, 10:20].all() and refused[20, 10:20].all()
    assert not refused[30:32, 30:32].any()          # the roof stays
    assert refused.sum() == 120


def test_a_real_cliff_inside_the_base_envelope_is_kept():
    # the base reads 0 .. 100 m across the cliff, the inset sharpens it
    inset = numpy.zeros((10, 10))
    inset[:, 5:] = 100.0
    low = numpy.zeros((10, 10))
    high = numpy.full((10, 10), 100.0)
    assert not blunder_cells(inset, numpy.ones((10, 10), bool),
                             low, high).any()


def test_a_pit_is_a_blunder_and_a_shallow_dip_is_not():
    inset = numpy.full((9, 9), 31.0)
    inset[2, 2] = 31.0 - BLUNDER_M - 25.0
    inset[6, 6] = 24.0                    # -7 m: no core beside it
    base = numpy.full((9, 9), 31.0)
    refused = blunder_cells(inset, numpy.ones((9, 9), bool), base, base)
    assert refused[2, 2] and not refused[6, 6]


def test_water_and_blunders_are_refused_in_place_and_once():
    values, base_values = _block_scene()
    values[0:4, 25:40] = 95.0             # +64 m noise over the lake
    values[4:6, 25:40] = 29.0             # quiet lake pixels
    inset = _grid(values)
    base = _grid(base_values)
    # a lake over rows 0..5 (y 34..39) east of x 24.5
    lake = box(24.5, 33.5, 60.0, 60.0)
    record = refuse_surface_model_cells(inset, base, lake, METRES)
    assert record["water"] == 6 * 15
    assert record["blunder"] == 120
    assert (inset.alt_dem[0:6, 25:40] == ND).all()
    assert (inset.alt_dem[10:20, 10:20] == ND).all()
    assert inset.alt_dem[31, 31] == 41.0
    again = refuse_surface_model_cells(inset, base, lake, METRES)
    assert again is record


def test_a_clean_inset_is_untouched():
    values = numpy.full((12, 12), 31.0)
    values[3, 3] = 40.0
    inset = _grid(values)
    before = inset.alt_dem.copy()
    assert refuse_surface_model_cells(
        inset, _grid(numpy.full((12, 12), 30.0)), None, METRES) is None
    assert numpy.array_equal(inset.alt_dem, before)


def test_only_a_declared_stereo_surface_model_is_judged(monkeypatch):
    values, base_values = _block_scene()
    base = _grid(base_values)
    tile = types.SimpleNamespace(lat=62, lon=-8, dem=base,
                                 _inset_inland_water=None)
    monkeypatch.setattr(INSETS, "elevation_providers_dict", {
        "STEREO": {"stereo_surface_model": True},
        "LIDAR": {"stereo_surface_model": False}})
    lidar = _grid(values.copy())
    INSETS._refuse_surface_model_cells(tile, "/x/ABCD_lidar.tif", lidar)
    assert numpy.array_equal(lidar.alt_dem, values.astype(numpy.float32))
    stereo = _grid(values.copy())
    INSETS._refuse_surface_model_cells(tile, "/x/ABCD_stereo.tif", stereo)
    assert (stereo.alt_dem[10:20, 10:20] == ND).all()
    assert base.inset_surface_refusals["/x/ABCD_stereo.tif"]["blunder"] == 120


def test_the_declaration_never_moves_a_provider_version():
    # a bake treatment, not the question: no index re-asks its negatives
    from elevation_access.recheck import provider_version
    definition = {"code": "X", "access_strategy": "direct_cog"}
    assert provider_version(definition) == provider_version(
        dict(definition, stereo_surface_model=True))
