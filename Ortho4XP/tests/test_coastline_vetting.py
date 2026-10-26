"""Coastline vetting (#1354): stray OSM coastline never floods high ground,
and a real coast is left exactly as it was."""

import numpy
import O4_Coastline_Vetting as VET
import O4_Tile_Failures as FAIL
import O4_Vector_Map as VMAP
import pytest
from shapely import geometry

LAT, LON = 44, -112


class _DEM:
    """A tile-relative raster stand-in: ``alt_dem`` over x, y in [0, 1]."""

    def __init__(self, alt):
        self.alt_dem = numpy.asarray(alt, dtype=numpy.float32)
        self.x0, self.x1, self.y0, self.y1 = 0.0, 1.0, 0.0, 1.0


def _highland(level=2000.0, n=121):
    return _DEM(numpy.full((n, n), level))


def _coastal(n=121):
    """Sea (0 m) west of x = 0.5, land rising from 5 m to the east."""
    xs = numpy.linspace(0.0, 1.0, n)
    alt = numpy.where(xs < 0.5, 0.0, 5.0 + 200.0 * (xs - 0.5))
    return _DEM(numpy.tile(alt, (n, 1)))


def _ring(cx, cy, r, ccw=True, k=24):
    t = numpy.linspace(0, 2 * numpy.pi, k, endpoint=False)
    if not ccw:
        t = t[::-1]
    pts = [(cx + r * numpy.cos(a), cy + r * numpy.sin(a)) for a in t]
    return geometry.LineString(pts + [pts[0]])


def _stray():
    """Two closed ~15 m rings well inside the frame (the #1354 shape)."""
    return geometry.MultiLineString([
        _ring(0.974, 0.9564, 0.00003), _ring(0.9742, 0.9565, 0.00003)])


def _witness(dem):
    sampler = VET.dem_sampler(dem)
    return lambda: sampler


# --- the defect, then rule 1 ---------------------------------------------
def test_unvetted_stray_rings_read_as_an_ocean_tile():
    sea = VMAP.sea_area_from_coastline(_stray(), LAT, LON)
    assert sea.area > 0.99          # the mechanism #1354 measured


def test_stray_rings_on_high_ground_are_dropped_and_the_tile_stays_land():
    vetted, dropped = VET.vet_coastline(_stray(), LAT, LON,
                                        _witness(_highland()))
    assert vetted.is_empty and len(dropped) == 2
    assert all(length < VET.FRAGMENT_MAX_LENGTH_M
               for (_la, _lo, length, _w) in dropped)
    # an empty coastline is what every caller already reads as "no sea"
    # (include_sea and the cached readers skip it, as on any inland tile)


def test_the_drop_is_said_out_loud(monkeypatch):
    said = []
    monkeypatch.setattr(VET.UI, "loud_warning",
                        lambda *a: said.append(" ".join(map(str, a))))
    VET.vet_coastline(_stray(), LAT, LON, _witness(_highland()))
    assert len(said) == 2 and "stray OSM natural=coastline" in said[0]
    assert "44.956" in said[0]


def test_no_witness_keeps_what_it_cannot_judge():
    coast = _stray()
    vetted, dropped = VET.vet_coastline(coast, LAT, LON, lambda: None)
    assert vetted is coast and dropped == []


def test_a_dangling_open_fragment_on_high_ground_is_dropped():
    frag = geometry.MultiLineString([[(0.3, 0.3), (0.302, 0.3)]])
    vetted, dropped = VET.vet_coastline(frag, LAT, LON,
                                        _witness(_highland()))
    assert vetted.is_empty and len(dropped) == 1


# --- a real coast is unchanged --------------------------------------------
def _real_coast():
    """A shore crossing the frame north to south at x = 0.5 (land to the
    east, two ways chained), a tiny real islet in the sea and a short way
    continuing the shore."""
    return geometry.MultiLineString([
        [(0.5, 1.2), (0.5, 0.6)],
        [(0.5, 0.6), (0.5005, 0.5995)],      # short, but chains
        [(0.5005, 0.5995), (0.5, -0.2)],
        list(_ring(0.3, 0.4, 0.0002).coords),  # an islet in 0 m water
    ])


def test_a_real_coast_and_its_islet_are_kept_unchanged():
    coast = _real_coast()
    sampler = VET.dem_sampler(_coastal())
    vetted, dropped = VET.vet_coastline(coast, LAT, LON, lambda: sampler)
    assert vetted is coast and dropped == []


def test_a_real_coast_never_reads_its_dem_when_nothing_is_tiny():
    coast = geometry.MultiLineString([[(0.5, 1.2), (0.5, -0.2)]])

    def boom():
        raise AssertionError("witness read without a candidate")

    assert VET.vet_coastline(coast, LAT, LON, boom)[0] is coast


def test_real_sea_seeds_are_kept():
    sea = VMAP.sea_area_from_coastline(_real_coast(), LAT, LON)
    assert 0.45 < sea.area < 0.55
    kept, withheld = VET.withhold_highland_seeds(
        sea, VET.dem_sampler(_coastal()), LAT, LON)
    assert withheld == 0 and kept is sea
    VET.refuse_mostly_sea_highland(sea, _coastal(), LAT, LON)  # no raise


# --- rules 2 and 3 ----------------------------------------------------------
def _whole_tile_sea():
    return geometry.MultiPolygon([geometry.box(0, 0, 1, 1)])


def test_a_seed_on_high_ground_is_withheld():
    kept, withheld = VET.withhold_highland_seeds(
        _whole_tile_sea(), VET.dem_sampler(_highland()), LAT, LON)
    assert withheld == 1 and kept.is_empty


def test_a_cliffed_sea_with_open_water_inside_is_kept():
    alt = numpy.full((121, 121), 300.0)
    alt[40:80, 40:80] = 0.0          # open water inside, cliffs on the rim
    kept, withheld = VET.withhold_highland_seeds(
        _whole_tile_sea(), VET.dem_sampler(_DEM(alt)), LAT, LON)
    assert withheld == 0 and not kept.is_empty


def test_mostly_sea_on_high_ground_fails_loudly():
    with pytest.raises(VET.ImplausibleSeaTile, match="mostly sea"):
        VET.refuse_mostly_sea_highland(_whole_tile_sea(), _highland(),
                                       LAT, LON)
    assert FAIL.code_for_exception(VET.ImplausibleSeaTile("x")) == \
        "map_coastline_implausible"


def test_a_small_sea_on_high_ground_is_not_the_guard_rails_case():
    small = geometry.MultiPolygon([geometry.box(0, 0, 0.3, 0.3)])
    VET.refuse_mostly_sea_highland(small, _highland(), LAT, LON)
