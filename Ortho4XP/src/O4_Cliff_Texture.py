"""A seamless, colour-matched face texture for one cliff region (#2096).

Made only from the tile's own orthophoto, offline, with classical methods
(no network, no learned model):

1. **exemplar** -- the most cliff-like window of UNSTRETCHED pixels near
   the region: pixels the mesh says are moderately sloped (the mountain's
   own flanks, not the stretched face and not the flat valley floor where
   roofs and fields are), scored by how close their colour is to the
   face's (:func:`pick_exemplar`);
2. **synthesis** -- toroidal image quilting (Efros & Freeman 2001, with a
   minimum-error boundary cut on every overlap, wrapped at the edges) turns
   the window into a tile that repeats without a seam (:func:`quilt`);
3. **colour match** -- the tile's CIE Lab mean and spread are moved to the
   orthophoto's under and around the region (:func:`match_lab`), so the
   face keeps the colour the photo gives it, without the smear.

``srgb_to_lab`` / ``_lab_to_srgb`` are the D65 sRGB <-> CIE L*a*b*
formulas.
"""
from __future__ import annotations

import numpy

__all__ = ["match_lab", "pick_exemplar", "quilt",
           "srgb_to_lab", "blend_ramp"]

_M = numpy.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
_WHITE = numpy.array([0.95047, 1.0, 1.08883])


def srgb_to_lab(rgb):
    """(..., 3) uint8 sRGB -> float CIE Lab (D65)."""
    c = numpy.asarray(rgb, dtype=float) / 255.0
    c = numpy.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = c @ _M.T / _WHITE
    f = numpy.where(xyz > (6 / 29) ** 3, numpy.cbrt(xyz),
                    xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return numpy.stack((116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]),
                        200 * (f[..., 1] - f[..., 2])), -1)


def _lab_to_srgb(lab):
    """float CIE Lab (D65) -> (..., 3) uint8 sRGB."""
    lab = numpy.asarray(lab, dtype=float)
    fy = (lab[..., 0] + 16) / 116
    f = numpy.stack((fy + lab[..., 1] / 500, fy, fy - lab[..., 2] / 200), -1)
    xyz = numpy.where(f > 6 / 29, f ** 3, 3 * (6 / 29) ** 2 * (f - 4 / 29))
    c = (xyz * _WHITE) @ numpy.linalg.inv(_M).T
    c = numpy.clip(c, 0.0, 1.0)
    c = numpy.where(c <= 0.0031308, 12.92 * c,
                    1.055 * c ** (1 / 2.4) - 0.055)
    return numpy.round(c * 255).astype(numpy.uint8)


def match_lab(rgb, mean, std):
    """``rgb`` with its Lab mean and per-channel spread moved to ``mean`` /
    ``std`` (Reinhard-style transfer in Lab)."""
    lab = srgb_to_lab(rgb)
    flat = lab.reshape(-1, 3)
    src_mean, src_std = flat.mean(0), flat.std(0) + 1e-6
    out = (lab - src_mean) * (numpy.asarray(std) / src_std) + mean
    return _lab_to_srgb(out)


def _box_means(values, k):
    """Mean of every ``k`` x ``k`` box of ``values`` (h, w, c), by a
    summed-area table: (h - k + 1, w - k + 1, c)."""
    sat = numpy.zeros((values.shape[0] + 1, values.shape[1] + 1,
                       values.shape[2]))
    sat[1:, 1:] = values.cumsum(0).cumsum(1)
    return (sat[k:, k:] - sat[:-k, k:] - sat[k:, :-k] + sat[:-k, :-k]) / (k * k)


def pick_exemplar(image, candidate, target_mean, window, min_fill=0.85,
                  step=4):
    """``(row, col)`` of the ``window``-pixel square of ``image`` (h, w, 3)
    whose pixels are at least ``min_fill`` ``candidate`` (bool, same h, w)
    and whose Lab mean is nearest ``target_mean``.  Penalised: a
    textureless window (lightness spread under 3: water, a roof) and dark
    blobs (pixels 25 L* below the target: bushes and their shadows, which
    read as dots stuck on a wall).  Windows are scored on a ``step``-pixel
    grid; ``None`` when none qualifies."""
    lab = srgb_to_lab(image[::step, ::step])
    k = max(1, window // step)
    if lab.shape[0] < k or lab.shape[1] < k:
        return None
    light = lab[..., :1]
    planes = numpy.concatenate((
        lab, light * light, (light < target_mean[0] - 25.0),
        candidate[::step, ::step, None]), -1).astype(float)
    m = _box_means(planes, k)
    spread = numpy.sqrt(numpy.maximum(0.0, m[..., 3] - m[..., 0] ** 2))
    score = (numpy.linalg.norm(m[..., :3] - numpy.asarray(target_mean),
                               axis=-1)
             + 10.0 * numpy.maximum(0.0, 3.0 - spread) + 40.0 * m[..., 4])
    score[m[..., 5] < min_fill] = numpy.inf
    if not numpy.isfinite(score).any():
        return None
    r, c = numpy.unravel_index(int(numpy.argmin(score)), score.shape)
    return (int(r) * step, int(c) * step)


def _cut_mask(err):
    """Minimum-error vertical path through ``err`` (h, o): ``True`` right
    of the path (the new patch), ``False`` left (the old one)."""
    h, o = err.shape
    cost = err.copy()
    for i in range(1, h):
        prev = cost[i - 1]
        left = numpy.concatenate(([numpy.inf], prev[:-1]))
        right = numpy.concatenate((prev[1:], [numpy.inf]))
        cost[i] += numpy.minimum(numpy.minimum(left, prev), right)
    path = numpy.empty(h, dtype=int)
    path[-1] = int(numpy.argmin(cost[-1]))
    for i in range(h - 2, -1, -1):
        j = path[i + 1]
        lo, hi = max(0, j - 1), min(o, j + 2)
        path[i] = lo + int(numpy.argmin(cost[i, lo:hi]))
    return numpy.arange(o)[None, :] >= path[:, None]


def _new_mask(patch, old, filled, overlap):
    """Which pixels of a patch window take the new patch: on every side
    whose overlap is already filled, the new side of the boundary cut;
    everywhere not yet filled, the new patch."""
    b, o = patch.shape[0], overlap
    keep = numpy.ones((b, b), dtype=bool)
    err = ((patch - old) ** 2).sum(-1)
    if filled[:, :o].all():                     # old on the left
        keep[:, :o] &= _cut_mask(err[:, :o])
    if filled[:, b - o:].all():                 # old on the right
        keep[:, b - o:] &= _cut_mask(err[:, b - o:][:, ::-1])[:, ::-1]
    if filled[:o, :].all():                     # old above
        keep[:o, :] &= _cut_mask(err[:o, :].T).T
    if filled[b - o:, :].all():                 # old below
        keep[b - o:, :] &= _cut_mask(err[b - o:, :].T[:, ::-1])[:, ::-1].T
    return keep | ~filled


def quilt(exemplar, size=512, patch=80, overlap=16, candidates=80,
          tolerance=0.1, rng=None):
    """A ``size`` x ``size`` texture that tiles without a seam, quilted
    from ``exemplar`` (h, w, 3 uint8, each side at least ``patch``):
    ``(size // (patch - overlap))`` patches a side, each chosen among
    ``candidates`` random exemplar windows within ``tolerance`` of the best
    overlap error, wrapped around the torus."""
    rng = rng or numpy.random.default_rng(0)
    ex = numpy.asarray(exemplar, dtype=numpy.float32)
    step = patch - overlap
    n = size // step
    size = n * step
    out = numpy.zeros((size, size, 3))
    filled = numpy.zeros((size, size), dtype=bool)
    h, w = ex.shape[:2]
    for gi in range(n):
        for gj in range(n):
            rows = numpy.arange(gi * step, gi * step + patch) % size
            cols = numpy.arange(gj * step, gj * step + patch) % size
            old = out[numpy.ix_(rows, cols)]
            have = filled[numpy.ix_(rows, cols)]
            pr = rng.integers(0, h - patch + 1, candidates)
            pc = rng.integers(0, w - patch + 1, candidates)
            if have.any():
                hy, hx = numpy.nonzero(have)
                hy, hx = hy[::3], hx[::3]   # a third of the overlap scores it
                # (candidates, overlap pixels, 3): every candidate at once
                errs = ((ex[pr[:, None] + hy, pc[:, None] + hx]
                         - old[hy, hx]) ** 2).sum((1, 2))
                ok = numpy.nonzero(errs <= errs.min() * (1 + tolerance))[0]
                k = int(rng.choice(ok))
            else:
                k = 0
            new = ex[pr[k]:pr[k] + patch, pc[k]:pc[k] + patch]
            keep = _new_mask(new, old, have, overlap)
            out[numpy.ix_(rows, cols)] = numpy.where(keep[..., None], new, old)
            filled[numpy.ix_(rows, cols)] = True
    return numpy.clip(numpy.round(out), 0, 255).astype(numpy.uint8)


def blend_ramp(height=64, width=4):
    """The border texture of the cliff terrain: grey ``1 - |2t - 1|`` down
    its rows, so a vertex whose second texture pair is ``(0.5, alpha / 2)``
    draws the cliff texture at opacity ``alpha`` whichever way up X-Plane
    reads rows.  (h, w) uint8."""
    t = (numpy.arange(height) + 0.5) / height
    col = numpy.round(255 * (1 - numpy.abs(2 * t - 1))).astype(numpy.uint8)
    return numpy.repeat(col[:, None], width, 1)
