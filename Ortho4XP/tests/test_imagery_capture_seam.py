"""Capture seams inside one provider's mosaic and the field that closes
them (#2108, ``O4_Imagery_Capture_Seam``).

Offline: synthetic mosaics (smooth noise ground, a scene darker on one
side of a jogging N-S line, the provider's 3-px feather) and a synthetic
reference provider."""
import os
import sys

import numpy
import pytest
from PIL import Image, ImageFilter

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.path.join(REPO_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(REPO_ROOT, "src"))

import O4_Imagery_Capture_Seam as SEAM  # noqa: E402
import O4_Imagery_Provider_Blend as BLEND  # noqa: E402

N = SEAM.SAMPLE
SQUARES = 6
X0, Y0 = 11456, 25952       # any ZL16 square corner


def _ground(seed=1):
    """Tan ground: hills a few km across and fine grain, ``(h, w, 3)``."""
    rng = numpy.random.default_rng(seed)
    size = N * SQUARES

    def noise(blur):
        image = Image.fromarray((rng.random((size, size)) * 255).astype(numpy.uint8))
        value = numpy.asarray(image.filter(ImageFilter.GaussianBlur(blur)), dtype=float)
        return (value - value.mean()) / max(value.std(), 1e-9)
    luma = 130.0 + 15.0 * noise(20) + 4.0 * noise(0)
    return numpy.stack([luma * 1.1, luma, luma * 0.8], axis=-1)


def _line(rows):
    """The seam's column: 400 in the north half, 392 in the south."""
    return numpy.where(rows < N * SQUARES // 2, 400.0, 392.0)


def _scene(ground, shift=-30.0):
    """``ground`` with the scene east of :func:`_line` shifted by
    ``shift``, over a 3-px feather."""
    rows, cols = numpy.mgrid[0:ground.shape[0], 0:ground.shape[1]]
    east = numpy.clip((cols - _line(rows) + 1.5) / 3.0, 0.0, 1.0)
    return numpy.clip(ground + shift * east[..., None], 0, 255)


def _reference(image):
    def square(til_x, til_y):
        i, j = (til_y - Y0) // 16, (til_x - X0) // 16
        return image[i * N:(i + 1) * N, j * N:(j + 1) * N].astype(numpy.uint8)
    return square


def test_a_capture_seam_is_found_where_the_reference_shows_none():
    ground = _ground()
    seams = SEAM.find_seams(_scene(ground), X0, Y0, _reference(ground))
    assert len(seams) == 1
    seam = seams[0]
    assert seam.axis == "V" and seam.open_start and seam.open_end
    rows = (numpy.array([a for a, _ in seam.line]) - Y0) * 8.0
    across = (numpy.array([c for _, c in seam.line]) - X0) * 8.0
    assert numpy.median(numpy.abs(across - _line(rows))) <= 1.0
    half = numpy.median([k[1] for k in seam.knots], axis=0)
    assert numpy.all(numpy.abs(half + 15.0) <= 4.0)        # each side halfway
    assert numpy.allclose([k[2] for k in seam.knots],
                          [-numpy.array(k[1]) for k in seam.knots])


def test_a_ground_edge_every_provider_shows_is_not_a_seam():
    edge = _scene(_ground())
    assert SEAM.find_seams(edge, X0, Y0, _reference(edge)) == []


def test_without_a_reference_no_line_is_a_seam():
    ground = _ground()
    assert SEAM.find_seams(_scene(ground), X0, Y0, None) == []


def test_water_beside_land_is_never_a_candidate():
    ground = _ground()
    rows, cols = numpy.mgrid[0:ground.shape[0], 0:ground.shape[1]]
    water = numpy.where((cols >= _line(rows))[..., None], 25.0, ground)
    assert SEAM.find_seams(water, X0, Y0, _reference(ground)) == []


def test_a_road_with_two_sides_is_not_a_seam():
    """Its two sides step opposite ways a few px apart (``_unpaired``)."""
    ground = _ground()
    cols = numpy.arange(ground.shape[1])
    road = (cols >= 398) & (cols < 402)
    image = numpy.where(road[None, :, None], 230.0, ground)
    chains, bands = SEAM._chains_of(image)
    assert SEAM._unpaired(chains, bands) == []


@pytest.fixture(scope="module")
def field():
    ground = _ground()
    return SEAM.SeamField(SEAM.find_seams(_scene(ground), X0, Y0,
                                          _reference(ground))), ground


def test_the_field_closes_the_step_and_fades_beyond_the_feather(field):
    seams, ground = field
    scene = _scene(ground)
    rows = numpy.arange(N * SQUARES)
    x = X0 + (numpy.arange(N * SQUARES) + 0.5) / 8.0
    y = Y0 + (rows + 0.5) / 8.0
    fixed = scene + seams.at(x[None, :], y[:, None])
    line = _line(rows).astype(int)

    def side(image, lo, hi):
        return numpy.array([image[r, c + lo:c + hi].mean()
                            for r, c in zip(rows, line, strict=True)])
    raw = side(scene, 2, 4) - side(scene, -4, -2)          # 120-250 m out
    closed = side(fixed, 2, 4) - side(fixed, -4, -2)
    assert abs(numpy.median(raw)) > 20.0
    assert abs(numpy.median(closed)) < 6.0
    far = seams.at(x[None, :340], y[:, None])                # > 0.9 km west
    assert numpy.abs(far).max() < 0.5


def test_two_textures_read_the_same_field_on_their_shared_edge(field):
    seams, _ = field
    upper = seams.fields(X0 + 48, Y0 + 16, 16)[0]            # the seam
    lower = seams.fields(X0 + 48, Y0 + 32, 16)[0]            # runs through both
    assert numpy.abs(upper).max() > 10.0
    across = numpy.abs(upper[-1] - lower[0]).max()
    within = numpy.abs(numpy.diff(upper, axis=0)).max()
    assert across <= within + 0.5      # one field: no step at the edge
    fine = seams.fields((X0 + 48) * 2, (Y0 + 16) * 2, 17)    # one zoom finer
    assert fine is not None and fine[1] is None


def test_the_hook_adds_seams_to_the_blend_and_base(field):
    seams, _ = field

    class Tile:
        provider_blend = None
        capture_seams = seams
    base = numpy.ones((256, 256, 3), dtype=numpy.float32)
    total = BLEND.add_field(Tile, base, X0 + 48, Y0 + 16, 16)
    alone = seams.fields(X0 + 48, Y0 + 16, 16)[0]
    assert numpy.allclose(total, alone + 1.0)
    assert BLEND.gain_field(Tile, X0 + 48, Y0 + 16, 16) is None


def test_the_book_finds_once_and_reads_back(tmp_path, monkeypatch):
    ground = _ground()
    scene = _scene(ground)
    calls = []
    monkeypatch.setattr(SEAM, "mosaic_of", lambda lat, lon, p, image_of: (
        calls.append(p) or (scene, X0, Y0)))

    def image_of(provider, til_x, til_y):
        assert provider == SEAM.reference_provider("BI") == "Arc"
        return _reference(ground)(til_x, til_y)
    book = SEAM.SeamBook(str(tmp_path / "capture_seams.json"))
    found = book.seams(34, -117, "BI", image_of)
    again = SEAM.SeamBook(book.path).seams(34, -117, "BI")
    assert len(found) == 1 and calls == ["BI"]
    assert [s.as_dict() for s in again] == [s.as_dict() for s in found]
    assert SEAM.SeamBook(book.path).seams(35, -117, "BI") is None


def test_attach_never_fails_a_build(monkeypatch):
    class Tile:
        lat, lon = 34, -117

    def broken():
        raise OSError("no data folder")
    monkeypatch.setattr(SEAM, "book", broken)
    tile = Tile()
    SEAM.attach(tile, "BI", measure=False)
    assert tile.capture_seams is None and tile.capture_seams_of == "BI"


def test_offline_finds_nothing_and_writes_nothing(tmp_path, monkeypatch):
    """No reference photo: nothing is known, so nothing is booked and the
    next build finds again."""
    scene = _scene(_ground())
    monkeypatch.setattr(SEAM, "mosaic_of", lambda lat, lon, p, image_of: (scene, X0, Y0))
    book = SEAM.SeamBook(str(tmp_path / "capture_seams.json"))
    assert book.seams(34, -117, "BI", lambda provider, x, y: None) == []
    assert not book.has(book.key(34, -117, "BI"))
