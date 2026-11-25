"""#2271: a partial inset's coastline keeps the base where it is untrustworthy
(:mod:`elevation_access.partial_inset_coast`)."""
import json
import types

import numpy
from elevation_access.partial_inset_coast import (
    _partial_fill_cover,
    _untrusted_coast_cells,
    refuse_partial_coast,
)

ND = -32768.0


def test_partial_fill_cover_judges_only_a_masked_fill_under_the_threshold():
    assert _partial_fill_cover({}, 0.8) is None
    assert _partial_fill_cover({"provider_fill": None}, 0.8) is None
    assert _partial_fill_cover(
        {"provider_fill": {"valid_fraction": 0.95}}, 0.8) is None
    assert _partial_fill_cover(
        {"provider_fill": {"valid_fraction": 0.34}}, 0.8) == 0.34


def _scene():
    """Rows 0-2 land, row 3 a sub-sea fringe, rows 4-5 the masked fill."""
    values = numpy.array([
        [30.0, 30.0, 30.0, 30.0, 30.0],
        [20.0, 20.0, 20.0, 20.0, 20.0],
        [5.0, 5.0, 12.0, 5.0, 5.0],
        [-6.0, -6.0, 15.0, -6.0, -6.0],
        [ND, ND, ND, ND, ND],
        [ND, ND, ND, ND, ND],
    ])
    base = numpy.array([
        [30.0, 30.0, 30.0, 30.0, 30.0],
        [20.0, 20.0, 20.0, 20.0, 20.0],
        [8.0, 8.0, 8.0, 8.0, 8.0],
        [4.0, 4.0, 4.0, 4.0, 4.0],
        [0.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0, 0.0],
    ])
    return values, base


def test_sub_sea_fringe_and_the_low_ring_beside_it_are_refused():
    values, base = _scene()
    refused, sub_sea = _untrusted_coast_cells(values, ND, base)
    # the -6 m pixels where the base reads 4 m: refused as sub-sea
    assert sub_sea[3].tolist() == [True, True, False, True, True]
    # the ring next to them, standing BELOW the base (5 m over 8 m): refused
    assert refused[2].tolist() == [True, True, False, True, True]
    # a ring pixel standing ABOVE the base is the provider's detail: kept
    assert not refused[3, 2] and not refused[2, 2]
    # two pixels inland: never judged
    assert not refused[:2].any()


def test_a_coast_pixel_above_the_base_is_kept_a_cliff_top_runway():
    values = numpy.array([[32.0, 32.0], [31.0, 31.0], [ND, ND]])
    base = numpy.array([[25.0, 25.0], [12.0, 12.0], [0.0, 0.0]])
    refused, sub_sea = _untrusted_coast_cells(values, ND, base)
    assert not refused.any() and not sub_sea.any()


def test_base_nodata_never_reads_as_land():
    values = numpy.array([[-3.0, ND]])
    base = numpy.array([[-32768.0, 0.0]])
    refused, sub_sea = _untrusted_coast_cells(values, ND, base, -32768.0)
    assert not sub_sea.any() and not refused.any()


def _inset(values):
    rows, columns = values.shape
    return types.SimpleNamespace(alt_dem=values.copy(), nodata=ND,
                                 x0=0.0, x1=float(columns - 1),
                                 y0=0.0, y1=float(rows - 1))


def _base(base):
    rows, columns = base.shape
    return types.SimpleNamespace(alt_dem=base, nodata=-32768.0,
                                 x0=0.0, x1=float(columns - 1),
                                 y0=0.0, y1=float(rows - 1),
                                 nxdem=columns, nydem=rows)


def test_refuse_partial_coast_masks_in_place_once(tmp_path):
    values, base = _scene()
    path = tmp_path / "NSAS_fabdem.tif"
    (tmp_path / "NSAS_fabdem.json").write_text(json.dumps(
        {"provider_fill": {"fill_value": 0.0, "valid_fraction": 0.34}}),
        encoding="utf-8", newline="\n")
    inset = _inset(values)
    record = refuse_partial_coast(inset, _base(base), str(path), 0.8)
    assert record == {"cover": 0.34, "refused": 8, "sub_sea": 4}
    assert (inset.alt_dem[3, [0, 1, 3, 4]] == ND).all()
    assert inset.alt_dem[3, 2] == 15.0
    # a second bake on the same decoded raster neither re-erodes nor re-counts
    again = refuse_partial_coast(inset, _base(base), str(path), 0.8)
    assert again == record
    assert (inset.alt_dem[1] == 20.0).all()


def test_an_inset_without_a_masked_fill_is_untouched(tmp_path):
    values, base = _scene()
    path = tmp_path / "KBUF_usgs3dep.tif"
    (tmp_path / "KBUF_usgs3dep.json").write_text(json.dumps(
        {"provider": "USGS3DEP"}), encoding="utf-8", newline="\n")
    inset = _inset(values)
    assert refuse_partial_coast(inset, _base(base), str(path), 0.8) is None
    assert numpy.array_equal(inset.alt_dem, values)


def test_a_low_coastline_beside_the_fill_alone_is_kept_lpma_class():
    """No sub-sea pixel: the coastline next to the fill keeps its inset,
    however it stands against the base (a runway platform, a cliff)."""
    values = numpy.array([[40.0, 40.0], [35.0, 2.0], [ND, ND]])
    base = numpy.array([[45.0, 45.0], [44.0, 30.0], [0.0, 0.0]])
    refused, sub_sea = _untrusted_coast_cells(values, ND, base)
    assert not refused.any() and not sub_sea.any()
