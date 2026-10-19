"""The mask-square memo (issue #850): ``build_dsf`` decodes each 4096 px mask
square once, and the crops it hands back are the uncached crops, byte for
byte.  Headless, ``tmp_path`` only."""
import os
import sys
import threading
import types

import numpy
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import O4_File_Names as FNAMES  # noqa: E402
import O4_Mask_Utils as MASK  # noqa: E402


def _tile(tmp_path, monkeypatch):
    monkeypatch.setenv("O4_MASKS_DIR", str(tmp_path))
    return types.SimpleNamespace(lat=22, lon=113, mask_zl=14)


def _write_square(tile, m_x, m_y, seed):
    path = os.path.join(FNAMES.mask_dir(tile.lat, tile.lon),
                        FNAMES.legacy_mask(m_x, m_y))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rng = numpy.random.default_rng(seed)
    Image.fromarray(rng.integers(0, 256, (4096, 4096), dtype=numpy.uint8),
                    "L").save(path)


def _crops(tile, squares):
    out = []
    for m_x, m_y in squares:
        for k in range(4):           # ZL16 textures inside a ZL14 square
            out.append(MASK.land_class_for_texture(
                tile, 4 * m_x + 16 * k, 4 * m_y + 16 * k, 16))
    return out


def test_memo_crops_equal_uncached_crops(tmp_path, monkeypatch):
    tile = _tile(tmp_path, monkeypatch)
    squares = [(28480, 53376), (28496, 53376)]
    for i, (m_x, m_y) in enumerate(squares):
        _write_square(tile, m_x, m_y, i)
    plain = _crops(tile, squares)
    opened = []
    real_open = Image.open
    monkeypatch.setattr(MASK.Image, "open",
                        lambda p, *a, **k: opened.append(p) or real_open(p, *a, **k))
    with MASK.mask_square_memo():
        memo = _crops(tile, squares + squares)[:len(plain)]
    assert len(opened) == len(squares)       # one decode per square
    for (c0, i0), (c1, i1) in zip(plain, memo):
        assert c0 == c1 == "mask"
        assert i0.tobytes() == i1.tobytes() and i0.mode == i1.mode


def test_memo_is_bounded_scoped_and_thread_local(tmp_path, monkeypatch):
    tile = _tile(tmp_path, monkeypatch)
    squares = [(28480, 53376), (28496, 53376), (28512, 53376)]
    for i, (m_x, m_y) in enumerate(squares):
        _write_square(tile, m_x, m_y, i)
    seen = {}
    with MASK.mask_square_memo(max_squares=2):
        _crops(tile, squares)
        assert len(MASK._square_memo.cache) == 2
        worker = threading.Thread(
            target=lambda: seen.update(
                cache=getattr(MASK._square_memo, "cache", None)))
        worker.start()
        worker.join()
    assert seen["cache"] is None             # other threads: uncached path
    assert MASK._square_memo.cache is None   # nothing outlives the scope
