"""Cliff overlay over the photo's shadow (#2102), on a synthetic photo.

A flat plain with a north-south wall in the middle; the photo is one ZL16
texture whose pixels the test paints: lit everywhere, or with a shadow band
at the wall's west foot, or a dark patch far from it."""
import dataclasses
import math
import os

import numpy
import O4_Cliff_Faces as FACES
import O4_Cliff_Photos as PHOTOS
import O4_Cliff_Shade as SHADE
import O4_DDS_Encode as ENC
import O4_Geo_Utils as GEO
import pytest

LAT0, LON0 = 38.0, 13.0
ZL = 16
LOOSE = dataclasses.replace(FACES.CliffParams(), min_area_m2=100.0,
                            slope_lo=58.0, slope_hi=68.0)
CELL = 30.0
N = 40                      # cells a side: 1200 m
WALL = 20                   # the wall is cell column WALL


def _mesh(height=200.0):
    xs = numpy.arange(N + 1) * CELL
    gx, gy = numpy.meshgrid(xs, xs)
    z = numpy.where(gx > xs[WALL], height, 0.0)
    xyz = numpy.stack((gx.ravel(), gy.ravel(), z.ravel()), 1)
    tris = []
    for j in range(N):
        for i in range(N):
            a = j * (N + 1) + i
            tris += [(a, a + 1, a + N + 2), (a, a + N + 2, a + N + 1)]
    k = math.radians(1) * FACES.EARTH_RADIUS_M
    lon = LON0 + 0.3 + xyz[:, 0] / (k * math.cos(math.radians(LAT0 + 0.5)))
    lat = LAT0 + 0.3 + xyz[:, 1] / k
    return xyz, numpy.array(tris), numpy.stack((lon, lat), 1)


XYZ, TRIS, LONLAT = _mesh()
LAND = numpy.ones(len(TRIS), bool)
ATTRS = (*GEO.wgs84_to_orthogrid(LAT0 + 0.3, LON0 + 0.3, ZL), ZL, "BI")
LAYOUT = FACES.find_cliff_layout(XYZ, TRIS, LAND, LOOSE)
PX = 256


def _photo(dark_x=None, value=150.0, dark=20.0):
    """A PX square photo, ``value`` grey; ``dark`` grey where the plain's
    x (m) is in ``dark_x`` = (lo, hi), across the whole y range."""
    img = numpy.full((PX, PX, 3), value)
    if dark_x is not None:
        k = math.radians(1) * FACES.EARTH_RADIUS_M
        cos = math.cos(math.radians(LAT0 + 0.5))
        pts = numpy.array([[LON0 + 0.3 + x / (k * cos), LAT0 + 0.3]
                           for x in dark_x])
        c0, c1 = SHADE.photo_pixel_coords(pts, ATTRS, PX)[:, 0]
        img[:, int(round(c0)):int(round(c1)) + 1] = dark
    return img.astype(numpy.uint8)


def _run(img, layout=LAYOUT):
    return SHADE.shadow_alpha(layout, XYZ, LONLAT, TRIS, LAND,
                              lambda pts: [ATTRS] * len(pts),
                              lambda attrs: img)


def _x_of_alpha(extra):
    """The plain's x (m) of nodes with extra opacity."""
    return XYZ[extra > 0, 0]


def test_photo_covers_the_mesh():
    px = SHADE.photo_pixel_coords(LONLAT, ATTRS, PX)
    assert px.min() > 0 and px.max() < PX


def test_lit_photo_changes_nothing():
    extra, stats = _run(_photo())
    assert extra is None and stats.extension_m == []
    assert stats.median == pytest.approx(150, abs=1)


def test_shadow_at_the_wall_foot_carries_the_overlay_and_ramps_out():
    wall_x = WALL * CELL
    extra, stats = _run(_photo(dark_x=(wall_x - 240, wall_x)))
    assert extra is not None and len(stats.extension_m) == 1
    reach = stats.extension_m[0]
    assert 240 <= reach <= 240 + SHADE.RAMP_M + CELL
    xs = XYZ[:, 0]
    inside = (xs > wall_x - 200) & (xs < wall_x - 40)
    assert extra[inside].min() == pytest.approx(1.0)
    assert _x_of_alpha(extra).min() >= wall_x - 240 - SHADE.RAMP_M - 1
    # the soft end: some nodes between 0 and 1 just past the dark band
    edge = (xs < wall_x - 240) & (extra > 0)
    assert edge.any() and extra[edge].max() < 1.0
    lay = FACES.find_cliff_layout(XYZ, TRIS, LAND, LOOSE, extra_alpha=extra)
    assert len(lay.tris) > len(LAYOUT.tris)
    assert set(LAYOUT.tris.tolist()) <= set(lay.tris.tolist())
    assert len(lay.region_tris) == len(LAYOUT.region_tris)


def test_dark_is_relative_to_the_tile():
    wall_x = WALL * CELL
    bright = _run(_photo(dark_x=(wall_x - 240, wall_x)))[0]
    dim = _run(_photo(dark_x=(wall_x - 240, wall_x), value=60, dark=8))[0]
    numpy.testing.assert_allclose(bright, dim, atol=1e-9)
    # 60 grey is "dark" against nothing: a uniformly dim tile is lit
    assert _run(_photo(value=60))[0] is None


def test_dark_patch_away_from_the_wall_is_left_alone():
    extra, _stats = _run(_photo(dark_x=(30, 200)))
    assert extra is None


def test_reach_is_capped():
    wall_x = WALL * CELL
    extra, stats = _run(_photo(dark_x=(0, wall_x)))
    assert stats.extension_m[0] <= SHADE.REACH_M + SHADE.RAMP_M
    assert extra[XYZ[:, 0] < wall_x - SHADE.REACH_M - SHADE.RAMP_M].max() == 0
    assert extra[XYZ[:, 0] == wall_x - 300].min() == pytest.approx(1.0)


def test_no_photo_no_extension():
    extra, stats = SHADE.shadow_alpha(LAYOUT, XYZ, LONLAT, TRIS, LAND,
                                      lambda pts: [ATTRS] * len(pts),
                                      lambda attrs: None)
    assert extra is None and stats.photos == 0


class _Tile:
    def __init__(self, build_dir):
        self.build_dir = build_dir


def test_reader_takes_the_texture_mip(tmp_path):
    os.makedirs(tmp_path / "textures")
    import O4_File_Names as FNAMES
    rgb = numpy.zeros((1024, 1024, 3), numpy.uint8)
    rgb[:, :512] = 200
    ENC.encode_file(rgb, "bc1", str(tmp_path / "textures" /
                                    FNAMES.dds_file_name_from_attributes(
                                        *ATTRS)))
    got = PHOTOS.photo_reader(_Tile(str(tmp_path)), fetch=False)(ATTRS)
    assert got.shape == (PHOTOS.SAMPLE_PX, PHOTOS.SAMPLE_PX, 3)
    assert abs(int(got[5, 5, 0]) - 200) <= 8 and got[5, -5, 0] <= 8


def test_reader_falls_back_to_the_jpeg_and_never_fetches_when_told(
        tmp_path, monkeypatch):
    from PIL import Image
    jpeg = tmp_path / "photo.jpg"
    Image.fromarray(numpy.full((4096, 4096, 3), 90, numpy.uint8)).save(jpeg)
    monkeypatch.setattr(PHOTOS, "_jpeg_path", lambda tile, attrs: str(jpeg))
    read = PHOTOS.photo_reader(_Tile(str(tmp_path)), fetch=False)
    got = read(ATTRS)
    assert got.shape == (PHOTOS.SAMPLE_PX, PHOTOS.SAMPLE_PX, 3)
    assert abs(int(got.mean()) - 90) <= 2
    import O4_Imagery_Utils as IMG

    def _no_fetch(*_a, **_k):
        raise AssertionError("fetched")
    monkeypatch.setattr(IMG, "build_jpeg_ortho", _no_fetch)
    monkeypatch.setattr(PHOTOS, "_jpeg_path",
                        lambda tile, attrs: str(tmp_path / "absent.jpg"))
    assert read(ATTRS) is None
