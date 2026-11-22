"""The photo's own sun (O4_Cliff_Sun): Lambert's law over sloped land."""
import math

import numpy
import O4_Cliff_Sun as SUN
import pytest


def _samples(azimuth_deg, n=2000, amplitude=30.0, noise=5.0, seed=1):
    rng = numpy.random.default_rng(seed)
    slope = rng.uniform(10, 40, n)
    aspect = rng.uniform(0, 2 * math.pi, n)
    s = numpy.radians(slope)
    normals = numpy.stack((numpy.sin(s) * numpy.sin(aspect),
                           numpy.sin(s) * numpy.cos(aspect),
                           numpy.cos(s)), 1)
    sun = numpy.array((math.sin(math.radians(azimuth_deg)),
                       math.cos(math.radians(azimuth_deg))))
    lum = 80 + amplitude * normals[:, :2] @ sun + rng.normal(0, noise, n)
    return lum, normals, slope


@pytest.mark.parametrize("azimuth", [35.0, 152.0, 270.0])
def test_the_fit_finds_the_sun(azimuth):
    sun = SUN.sun_direction(*_samples(azimuth))
    got = math.degrees(math.atan2(sun[0], sun[1])) % 360
    assert abs((got - azimuth + 180) % 360 - 180) < 5


def test_flat_light_has_no_sun():
    assert SUN.sun_direction(*_samples(150.0, amplitude=0.0)) is None


def test_too_few_samples_have_no_sun():
    lum, normals, slope = _samples(150.0, n=SUN.MIN_SAMPLES - 1)
    assert SUN.sun_direction(lum, normals, slope) is None


def test_dark_rock_needs_the_sun_on_its_face_and_a_dark_photo():
    # two one-triangle regions: one looks east, one west; nodes 0-2, 3-5
    tri_idx = numpy.array([[0, 1, 2], [3, 4, 5]])
    normals = numpy.array([[0.9, 0.0, 0.44], [-0.9, 0.0, 0.44]])
    areas = numpy.ones(2)
    slopes = numpy.full(2, 64.0)
    regions = [numpy.array([0]), numpy.array([1])]
    dark = numpy.full(6, 20.0)
    east = numpy.array((1.0, 0.0))
    got = SUN.dark_rock_regions(regions, tri_idx, dark, 80.0, east,
                                normals, areas, slopes)
    assert got.tolist() == [True, False]
    lit = numpy.full(6, 120.0)
    assert not SUN.dark_rock_regions(regions, tri_idx, lit, 80.0, east,
                                     normals, areas, slopes).any()
    assert not SUN.dark_rock_regions(regions, tri_idx, dark, 80.0, None,
                                     normals, areas, slopes).any()
