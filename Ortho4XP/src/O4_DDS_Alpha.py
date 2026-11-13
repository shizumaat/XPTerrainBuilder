"""The alpha channel of a DXT5 (BC3) texture, decoded (#2037).

A World drape's water squares carry their water mask in the DDS alpha
(``O4_World_Drape_Water``).  When the follow job lands a finer tier over
such a square, the mask must come with it: :func:`alpha_of` decodes the
mask the drape's own file holds, and the lander imprints it, scaled, into
the finer tier (``o4_engine.imagery_follow_drape``).

BC3 alpha: per 4 x 4 block, two endpoints ``a0, a1`` and sixteen 3-bit
indices into the palette they make (eight values when ``a0 > a1``, else
six plus 0 and 255), pixels row by row within the block.

numpy only (the file is read by ``O4_DDS_File.read_level``).
"""
from __future__ import annotations

import numpy
import O4_DDS_File as DDS

__all__ = ["alpha_of"]

_BLOCK_BYTES = 16


def _palettes(a0: numpy.ndarray, a1: numpy.ndarray) -> numpy.ndarray:
    """``(blocks, 8)`` palettes of the endpoints (uint8 each)."""
    a0 = a0.astype(numpy.int32)[:, None]
    a1 = a1.astype(numpy.int32)[:, None]
    i7 = numpy.arange(1, 7, dtype=numpy.int32)[None, :]
    i5 = numpy.arange(1, 5, dtype=numpy.int32)[None, :]
    eight = numpy.concatenate([a0, a1, ((7 - i7) * a0 + i7 * a1) // 7], axis=1)
    six = numpy.concatenate(
        [a0, a1, ((5 - i5) * a0 + i5 * a1) // 5,
         numpy.zeros_like(a0), numpy.full_like(a0, 255)], axis=1)
    return numpy.where(a0 > a1, eight, six).astype(numpy.uint8)


def _decode_bc3_alpha(blocks: bytes, width: int, height: int) -> numpy.ndarray:
    """The ``height`` x ``width`` uint8 alpha of one BC3 level's block
    data (partial edge blocks cropped)."""
    bw, bh = (width + 3) // 4, (height + 3) // 4
    data = numpy.frombuffer(blocks, dtype=numpy.uint8,
                            count=bw * bh * _BLOCK_BYTES).reshape(-1, _BLOCK_BYTES)
    bits = numpy.zeros(len(data), dtype=numpy.uint64)
    for k in range(6):
        bits |= data[:, 2 + k].astype(numpy.uint64) << numpy.uint64(8 * k)
    shifts = numpy.arange(16, dtype=numpy.uint64) * numpy.uint64(3)
    index = ((bits[:, None] >> shifts[None, :]) & numpy.uint64(7)).astype(numpy.intp)
    values = numpy.take_along_axis(_palettes(data[:, 0], data[:, 1]), index, axis=1)
    image = values.reshape(bh, bw, 4, 4).transpose(0, 2, 1, 3).reshape(bh * 4, bw * 4)
    return image[:height, :width]


def alpha_of(path: str) -> "numpy.ndarray | None":
    """The full-size alpha of the DXT5 texture at ``path``; ``None`` for a
    DXT1 file or one that does not read."""
    try:
        width, height, fmt, blocks = DDS.read_level(path, 1 << 30)
    except (OSError, ValueError):
        return None
    if fmt != "bc3":
        return None
    return _decode_bc3_alpha(blocks, width, height)
