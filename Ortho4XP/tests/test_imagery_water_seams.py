"""O4_Imagery_Water_Seams: straight seams and red squares under shallow water
are colour-matched and blurred; land never changes (owner 2026-11-24).

Synthetic, headless: a 1024-px texture of noisy water with a land strip
(mask 255) on its west edge, and a straight scene edge, a red-cast square
or a natural curved edge drawn in the water.
"""
from __future__ import annotations

import numpy
import pytest
from PIL import Image

import O4_DDS_Encode as DDSENC
import O4_Imagery_Water_Seams as WS

SIZE = 1024
LAND_COLUMNS = 96
WATER_ALPHA = 230
METRES_PER_PX = 8.7  # a 1024-px drop tier of a ZL16 texture at 24 N


def _water(seed: int = 7) -> numpy.ndarray:
    """Teal water with a gentle gradient and sensor noise, float RGB."""
    rng = numpy.random.default_rng(seed)
    y, x = numpy.mgrid[0:SIZE, 0:SIZE].astype(numpy.float32)
    base = numpy.stack([40 + 0.01 * x, 110 + 0.02 * y, 115 + 0.01 * y], -1)
    return base + rng.normal(0.0, 3.0, base.shape)


def _mask() -> numpy.ndarray:
    mask = numpy.full((SIZE // 4, SIZE // 4), WATER_ALPHA, numpy.uint8)
    mask[:, : LAND_COLUMNS // 4] = 255
    return mask


def _image(array: numpy.ndarray) -> Image.Image:
    return Image.fromarray(numpy.clip(numpy.rint(array), 0, 255).astype(numpy.uint8))


def _land_pixels(mask: numpy.ndarray) -> numpy.ndarray:
    return numpy.kron(mask >= 255, numpy.ones((4, 4), bool))


def _scene_edge() -> numpy.ndarray:
    """A straight N-S scene edge at x = 600: the east side 25 counts paler
    (the west edge at x = 96 is the shore)."""
    a = _water()
    a[100:900, 600:] += (10.0, 25.0, 25.0)
    return a


def test_straight_scene_edge_is_found_and_closed():
    image, mask = _image(_scene_edge()), _mask()
    seams = WS._find_water_seams(image, mask, METRES_PER_PX)
    columns = numpy.nonzero(seams.flag_x.any(axis=0))[0]
    assert 598 <= columns.min() and columns.max() <= 602
    assert max(seams.runs()) >= 600  # one run along most of the edge
    before = seams.step_stats()[0]
    assert before > 20.0
    repaired, _ = WS.repair_water_seams(image, mask, METRES_PER_PX, seams=seams)
    after = WS._find_water_seams(repaired, mask, METRES_PER_PX)
    assert after.step_stats(seams.flag_x, seams.flag_y)[0] < 3.0
    assert after.flagged == 0


def test_land_pixels_and_their_dxt_blocks_never_change():
    image, mask = _image(_scene_edge() + (0.0, 0.0, 0.0)), _mask()
    # a seam reaching the shore: the edge runs into the land strip
    a = _scene_edge()
    a[300:700, 0:300] += (0.0, 20.0, 20.0)
    image = _image(a)
    repaired, seams = WS.repair_water_seams(image, mask, METRES_PER_PX)
    assert seams.flagged
    before, after = numpy.asarray(image), numpy.asarray(repaired)
    land = _land_pixels(mask)
    assert (before != after).any()
    assert (before[land] == after[land]).all()
    blocks = [numpy.frombuffer(DDSENC.encode_level(x, "bc1"), numpy.uint8)
              .reshape(-1, 8) for x in (before, after)]
    land_blocks = land.reshape(SIZE // 4, 4, SIZE // 4, 4).any(axis=(1, 3)).ravel()
    assert (blocks[0][land_blocks] == blocks[1][land_blocks]).all()


def test_a_natural_curved_edge_and_a_gradient_are_left_alone():
    a = _water()
    y, x = numpy.mgrid[0:SIZE, 0:SIZE]
    channel = numpy.abs(x - (500 + 120 * numpy.sin(y / 90.0))) < 25
    a[channel] -= (0.0, 30.0, 25.0)
    image, mask = _image(a), _mask()
    seams = WS._find_water_seams(image, mask, METRES_PER_PX)
    assert seams.flagged == 0
    repaired, _ = WS.repair_water_seams(image, mask, METRES_PER_PX, seams=seams)
    assert repaired is image


def test_red_cast_square_is_tinted_with_its_luminance_kept():
    """A reddish source tile ~350 m across (40 work px, as over the KEYW
    flats), its cast 30 counts R-G over the water around it."""
    a = _water()
    square = (slice(400, 440), slice(400, 440))
    a[square] += (24.0, -6.0, -6.0)
    image, mask = _image(a), _mask()
    seams = WS._find_water_seams(image, mask, METRES_PER_PX)
    assert seams.tinted.any()
    repaired, _ = WS.repair_water_seams(image, mask, METRES_PER_PX, seams=seams)
    inner = (slice(410, 430), slice(410, 430))
    before = numpy.asarray(image, numpy.float32)[inner].reshape(-1, 3).mean(0)
    after = numpy.asarray(repaired, numpy.float32)[inner].reshape(-1, 3).mean(0)
    around = numpy.asarray(image, numpy.float32)[400:440, 600:700].reshape(-1, 3).mean(0)
    cast = lambda c: c[0] - c[1]  # noqa: E731
    assert cast(before) - cast(around) > 25.0
    assert abs(cast(after) - cast(around)) < 6.0
    luma = numpy.array([0.299, 0.587, 0.114])
    assert abs(float(after @ luma) - float(before @ luma)) < 3.0


def test_apply_on_water_keeps_land_and_changes_water():
    image, mask = _image(_water()), _mask()
    changed = _image(numpy.asarray(image, numpy.float32) + 20.0)
    out = numpy.asarray(WS.apply_on_water(image, changed, mask))
    land = _land_pixels(mask)
    assert (out[land] == numpy.asarray(image)[land]).all()
    assert (out[:, 400:] == numpy.asarray(changed)[:, 400:]).all()


@pytest.mark.parametrize("value, expected", [(255, False), (10, False), (200, True)])
def test_shows_water_only_where_water_shows(value, expected):
    mask = numpy.full((256, 256), value, numpy.uint8)
    assert WS.shows_water(mask) is expected


def test_rgba_alpha_passes_through():
    a = _scene_edge()
    rgba = numpy.dstack([numpy.clip(a, 0, 255), numpy.full((SIZE, SIZE), 77.0)])
    image = Image.fromarray(rgba.astype(numpy.uint8), "RGBA")
    repaired, seams = WS.repair_water_seams(image, _mask(), METRES_PER_PX)
    assert seams.flagged and repaired.mode == "RGBA"
    assert (numpy.asarray(repaired)[..., 3] == 77).all()
