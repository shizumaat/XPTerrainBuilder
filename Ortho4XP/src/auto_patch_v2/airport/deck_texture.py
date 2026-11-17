"""THE GENERATED DECK TEXTURE (spec 2123 §A2): one deterministic 256 x 256
PNG painted here, so a generated taxiway deck never borrows Laminar
library art (licensing not checked; the design avoids it).

The atlas is four regions, each a rectangle in UV space (u right, v up,
OBJ8 convention: v = 0 is the image's BOTTOM row):

* :data:`CONCRETE_UV` -- the deck top: light grey concrete, mottled;
* :data:`FASCIA_UV`   -- the side faces and the underside: darker, with a
  rain-streak band near the top edge;
* :data:`YELLOW_UV` / :data:`WHITE_UV` -- flat taxiway paint, sampled at a
  region's centre by the painted-line quads.

The same ``seed`` always paints the same pixels (``random.Random`` and a
NumPy ``default_rng``), so the PNG's bytes are a function of the seed and
the Pillow version only.  Build-time impact: one 256 x 256 encode
(~5 ms) per generated deck, at write time only.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

__all__ = ["SIZE", "CONCRETE_UV", "FASCIA_UV", "YELLOW_UV", "WHITE_UV",
           "uv_centre", "deck_texture_png"]

SIZE = 256

#: ``(u0, v0, u1, v1)`` per region
CONCRETE_UV = (0.0, 0.0, 0.5, 1.0)
FASCIA_UV = (0.5, 0.0, 0.75, 1.0)
YELLOW_UV = (0.75, 0.5, 0.875, 1.0)
WHITE_UV = (0.875, 0.5, 1.0, 1.0)
_BLACK_UV = (0.75, 0.0, 1.0, 0.5)

_CONCRETE = (172, 170, 164)
_FASCIA = (128, 126, 121)
_YELLOW = (226, 178, 32)
_WHITE = (232, 232, 228)
_BLACK = (24, 24, 24)


def uv_centre(region: tuple[float, float, float, float]) -> tuple[float, float]:
    """The UV point at a region's centre (where a flat-paint quad samples)."""
    u0, v0, u1, v1 = region
    return ((u0 + u1) / 2.0, (v0 + v1) / 2.0)


def _px(region: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    """Region -> ``(x0, y0, x1, y1)`` image rows/columns, y down."""
    u0, v0, u1, v1 = region
    return (round(u0 * SIZE), round((1.0 - v1) * SIZE),
            round(u1 * SIZE), round((1.0 - v0) * SIZE))


def _fill(img: np.ndarray, region, rgb, noise: np.ndarray | None = None) -> None:
    x0, y0, x1, y1 = _px(region)
    block = np.empty((y1 - y0, x1 - x0, 3), dtype=np.float64)
    block[:] = rgb
    if noise is not None:
        block += noise[y0:y1, x0:x1, None]
    img[y0:y1, x0:x1] = np.clip(block, 0, 255)


def _mottle(rng: np.random.Generator, amplitude: float) -> np.ndarray:
    """Low-frequency mottling plus fine grain, tile-safe (periodic)."""
    coarse = rng.normal(0.0, 1.0, (8, 8))
    up = np.kron(coarse, np.ones((SIZE // 8, SIZE // 8)))
    # a 3-tap periodic box blur, twice, so the cells do not read as squares
    for _ in range(2):
        up = (up + np.roll(up, SIZE // 16, 0) + np.roll(up, -SIZE // 16, 0)) / 3.0
        up = (up + np.roll(up, SIZE // 16, 1) + np.roll(up, -SIZE // 16, 1)) / 3.0
    grain = rng.normal(0.0, 0.5, (SIZE, SIZE))
    return amplitude * (up + grain)


def deck_texture_png(seed: int = 2123) -> bytes:
    """The atlas as PNG bytes (RGB, 8 bit)."""
    rng = np.random.default_rng(seed)
    img = np.zeros((SIZE, SIZE, 3), dtype=np.float64)
    _fill(img, CONCRETE_UV, _CONCRETE, _mottle(rng, 6.0))
    streak = _mottle(rng, 5.0)
    x0, y0, x1, y1 = _px(FASCIA_UV)
    streak[y0:y0 + (y1 - y0) // 6, x0:x1] -= 14.0      # the drip band under the deck edge
    _fill(img, FASCIA_UV, _FASCIA, streak)
    _fill(img, YELLOW_UV, _YELLOW)
    _fill(img, WHITE_UV, _WHITE)
    _fill(img, _BLACK_UV, _BLACK)
    out = io.BytesIO()
    Image.fromarray(img.astype(np.uint8), "RGB").save(out, format="PNG", optimize=False)
    return out.getvalue()
