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
    monkeypatch.setattr(VET, "_REPORTED", set())
    monkeypatch.setattr(VET.UI, "loud_warning",
                        lambda *a: said.append(" ".join(map(str, a))))
    VET.vet_coastline(_stray(), LAT, LON, _witness(_highland()))
    assert len(said) == 2 and "stray OSM natural=coastline" in said[0]
    assert "44.956" in said[0]
    # the other cached readers of the same build are told quietly
    VET.vet_coastline(_stray(), LAT, LON, _witness(_highland()))
    assert len(said) == 2


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


def test_the_bathymetry_band_reads_the_vetted_coastline():
    """A stray fragment must not make a landlocked tile "coastal" to the
    band (it would fetch lake cells no provider measures)."""
    import O4_Bathymetry_Band as BAND

    class _Tile:
        lat, lon, dem = LAT, LON, _highland()

    assert BAND._vetted(_stray(), _Tile()).is_empty
    coast = _real_coast()
    _Tile.dem = _coastal()
    assert BAND._vetted(coast, _Tile()) is coast


# --- a witness buffer GEOS returns in parts (#1300) -----------------------
#: a real 53-vertex closed coastline ring (tile-relative, ~480 m) whose
#: 150 m witness buffer GEOS returns as a MultiPolygon: the polygon plus
#: two ~1e-11 deg^2 slivers.  Vetting raised AttributeError on it, which
#: took the whole tile's coastline (and the emit's shore witness) down.
_SLIVER_RING = [(0.5024994, 0.4763696), (0.5024994, 0.4763077), (0.5025061, 0.4762696), (0.5025436, 0.4761959), (0.5026013, 0.4761602), (0.5026402, 0.4761257), (0.5026979, 0.4760685), (0.5027435, 0.4760162), (0.5027917, 0.4759484), (0.5028105, 0.4758936), (0.5028762, 0.4758377), (0.5029755, 0.475846), (0.5030734, 0.4759305), (0.5031807, 0.4760198), (0.5032531, 0.4761316), (0.5033174, 0.4762256), (0.503351, 0.4763053), (0.5033644, 0.4764267), (0.5033349, 0.4765802), (0.5033081, 0.4766765), (0.5032759, 0.4768027), (0.5032437, 0.4768717), (0.5031377, 0.4769276), (0.5031109, 0.476955), (0.5030693, 0.4770026), (0.5029768, 0.4769954), (0.5029916, 0.4769312), (0.5029594, 0.4768598), (0.5028521, 0.4767943), (0.5027475, 0.4767717), (0.5026147, 0.4768015), (0.5025302, 0.4768443), (0.5024578, 0.4769109), (0.5024337, 0.4769454), (0.5024042, 0.4770406), (0.5023518, 0.4771108), (0.5023183, 0.477181), (0.5022714, 0.4772072), (0.5022084, 0.4772132), (0.5021788, 0.477181), (0.5022177, 0.4770989), (0.5022808, 0.4770133), (0.5022754, 0.4769383), (0.5023143, 0.4768848), (0.5023626, 0.4768336), (0.502427, 0.4767753), (0.5024685, 0.4767206), (0.5024404, 0.4766325), (0.5024444, 0.4765909), (0.5024699, 0.4765112), (0.502486, 0.4764683), (0.5025088, 0.4764291), (0.5024994, 0.4763696)]


def test_a_buffer_returned_in_parts_is_still_witnessed():
    ring = geometry.LineString(_SLIVER_RING)
    assert ring.buffer(VET.WITNESS_REACH_M / VET._LAT_TO_M,
                       quad_segs=4).geom_type == "MultiPolygon"
    coast = geometry.MultiLineString([ring])
    kept, dropped = VET.vet_coastline(coast, LAT, LON, _witness(_coastal()))
    assert kept is coast and dropped == []
    gone, dropped = VET.vet_coastline(coast, LAT, LON,
                                      _witness(_highland()))
    assert gone.is_empty and len(dropped) == 1
