"""#2206 step 4: ``airport/split_level._band_cover`` (one ``np.add.at``)
is the face-by-face loop ``_side_feet`` ran, bit for bit (the loop as it
stood, below) — every band sums its faces in face order."""
from __future__ import annotations

import math

import numpy as np
from auto_patch_v2.airport import split_level as SL


def _loop(on, y0, y1, ln, lo, nb):
    cov = np.zeros(nb)
    for q in np.flatnonzero(on):
        b0 = int(math.floor((y0[q] - lo) / SL.BAND_M))
        b1 = int(math.ceil((y1[q] - lo) / SL.BAND_M))
        cov[b0:max(b1, b0 + 1)] += 0.5 * ln[q]
    return cov


def test_the_band_cover_is_the_loop_bit_for_bit():
    rnd = np.random.default_rng(2206)
    for trial in range(200):
        m = int(rnd.integers(0, 60))
        y0 = rnd.uniform(-3.0, 20.0, m)
        if trial % 4 == 0:                       # on band edges: floor == ceil
            y0 = np.round(y0 / SL.BAND_M) * SL.BAND_M
        y1 = y0 + rnd.choice([0.0, rnd.uniform(0.0, 9.0)], m)
        ln = rnd.uniform(0.0, 7.0, m) * rnd.uniform(0.9, 1.1, m) / 3.0
        on = rnd.random(m) < 0.7
        lo = float(y0.min()) if m else 0.0
        hi = float(y1.max()) if m else 0.0
        nb = int(math.ceil((hi - lo) / SL.BAND_M)) + 1
        got, want = SL._band_cover(on, y0, y1, ln, lo, nb), _loop(on, y0, y1, ln, lo, nb)
        assert got.tobytes() == want.tobytes()
