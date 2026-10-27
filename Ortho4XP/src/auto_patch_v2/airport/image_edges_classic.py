"""THE CLASSIC IMAGE METHOD (#1359; spec
``docs/specs/multi-source-terrain-spec.md`` §3, §7.3): luminance profiles
along line probes, no learned weights.  Registered as ``classic_edges``.

* ``edges(..., "graded_edge" | "pavement_edge")`` — the strongest
  luminance step along each probe's normal, of the along-track MEDIAN
  profile (a strip ``2 * half_width_m`` wide, so a single bush or a road
  crossing the strip does not make an edge); strength is the step over a
  2× floor, and a step under the floor is ``none``.
* ``edges(..., "threshold_marking")`` — along a runway's axis (the normal),
  each across-width row is tested for the threshold-marking signature: a
  high-contrast row split into at least ``_MIN_STRIPES`` bright stripes
  covering a quarter to four fifths of the row; the answer is the start of
  the first run of such rows at least ``_MIN_RUN_M`` long.
* ``edges(..., "pavement_start")`` — along a runway's axis, the first
  station from which the rows read as the runway's own pavement (their
  median within ``_PAVE_TOL`` of the runway body's) for ``_PAVE_RUN_M``.
* ``presence(..., "portal_opening")`` — how much darker the window's
  darkest quarter is than the window's surround (an opening and its
  shadow), strength over a 2× floor.

Every number here is a property of an orthophoto, never of an airport.
"""
from __future__ import annotations

import numpy as np
import shapely
from scipy import ndimage

from .image_provider import NONE, ImageEvidence, ImagePatch, Probes, register

__all__ = ["ClassicEdges", "CLASSIC", "strip_profiles"]

#: a luminance step (0-255 levels) under this is no edge
_STEP_MIN = 12.0
#: the step is measured between the means of this many metres either side
_STEP_SIDE_M = 4.0
#: a graded edge is read over this many neighbouring stations ...
_WINDOW = 9
#: ... and a station's candidate must lie this near their mode
_MODE_TOL_M = 6.0
#: threshold-marking row: contrast (p90 - p10) at least this many levels
_MARK_CONTRAST = 40.0
_MIN_STRIPES = 4
_MARK_FRAC = (0.2, 0.8)
_MIN_RUN_M = 15.0
#: stripes along the axis: the row this far on lights the same pixels ...
_STRIPE_RUN_M = 3.0
#: ... at least this much (intersection over union)
_STRIPE_IOU = 0.6
_GAP_M = 3.0
#: pavement row: its median within this of the runway body's
_PAVE_TOL = 25.0
_PAVE_RUN_M = 40.0
#: portal opening: darker by at least this many levels than the surround
_DARK_MIN = 25.0
#: the surround a window is compared with, metres beyond its edge
_SURROUND_M = 15.0


def strip_profiles(patch: ImagePatch, probes: Probes, step_m: float | None = None
                   ) -> np.ndarray:
    """Luminance N×M×K: per station, per normal offset, the K along-track
    samples across ``±half_width_m`` (K = 1 when the half width is 0)."""
    lum = patch.luminance()
    filled = np.where(np.isfinite(lum), lum, 0.0)
    valid = np.isfinite(lum).astype(np.float32)
    step = step_m or patch.m_per_px
    hw = float(probes.half_width_m)
    ts = np.arange(-hw, hw + 1e-9, step) if hw > 0 else np.zeros(1)
    n = np.asarray(probes.normal, dtype=float)
    tang = np.stack([-n[:, 1], n[:, 0]], axis=-1)
    xy = (np.asarray(probes.xy, dtype=float)[:, None, None, :]
          + n[:, None, None, :] * np.asarray(probes.offsets_m)[None, :, None, None]
          + tang[:, None, None, :] * ts[None, None, :, None])
    rc = patch.rowcol(xy.reshape(-1, 2)).T
    z = ndimage.map_coordinates(filled, rc, order=1, mode="constant", cval=0.0)
    w = ndimage.map_coordinates(valid, rc, order=1, mode="constant", cval=0.0)
    out = np.where(w > 0.99, z, np.nan)
    return out.reshape(xy.shape[0], xy.shape[1], xy.shape[2])


def _step_edge(prof: np.ndarray, offsets: np.ndarray) -> ImageEvidence:
    """The strongest step of one median profile along its offsets; a step
    is measured only where both sides are wholly valid (an unread gap is
    never an edge)."""
    ok = np.isfinite(prof)
    if ok.sum() < max(8, prof.size // 2):
        return ImageEvidence(None, 0.0, NONE)
    d = float(np.median(np.diff(offsets))) if offsets.size > 1 else 1.0
    p = np.where(ok, prof, 0.0)
    w = ok.astype(float)
    sig = max(1.0, 1.0 / d)
    num = ndimage.gaussian_filter1d(p, sig)
    den = ndimage.gaussian_filter1d(w, sig)
    p = np.where(den > 0.5, num / np.maximum(den, 1e-9), np.nan)
    side = max(1, int(round(_STEP_SIDE_M / d)))
    best, at = 0.0, None
    for i in range(side, p.size - side):
        left, right = p[i - side:i], p[i:i + side]
        if not (np.isfinite(left).all() and np.isfinite(right).all()):
            continue
        s = abs(float(right.mean() - left.mean()))
        if s > best:
            best, at = s, i
    if at is None or best < _STEP_MIN:
        return ImageEvidence(None, min(1.0, best / (2 * _STEP_MIN)), NONE)
    return ImageEvidence(float(offsets[at]), min(1.0, best / (2 * _STEP_MIN)), "edge")


def _step_candidates(prof: np.ndarray, offsets: np.ndarray) -> list[tuple[float, float]]:
    """Every local maximum of the step magnitude at or over the floor:
    ``[(offset, step)]`` (the same measure as :func:`_step_edge`)."""
    ok = np.isfinite(prof)
    if ok.sum() < max(8, prof.size // 2):
        return []
    d = float(np.median(np.diff(offsets))) if offsets.size > 1 else 1.0
    p = np.where(ok, prof, 0.0)
    w = ok.astype(float)
    sig = max(1.0, 1.0 / d)
    num = ndimage.gaussian_filter1d(p, sig)
    den = ndimage.gaussian_filter1d(w, sig)
    p = np.where(den > 0.5, num / np.maximum(den, 1e-9), np.nan)
    side = max(1, int(round(_STEP_SIDE_M / d)))
    st = np.full(p.size, 0.0)
    for i in range(side, p.size - side):
        left, right = p[i - side:i], p[i:i + side]
        if np.isfinite(left).all() and np.isfinite(right).all():
            st[i] = abs(float(right.mean() - left.mean()))
    out = []
    for i in range(1, p.size - 1):
        if st[i] >= _STEP_MIN and st[i] >= st[i - 1] and st[i] > st[i + 1]:
            out.append((float(offsets[i]), float(st[i])))
    return out


def _coherent(cands: list[list[tuple[float, float]]]) -> list[ImageEvidence]:
    """THE GRADED EDGE IS A LINE: per station, the candidate nearest the
    strength-weighted mode of the candidates of the ``_WINDOW`` stations
    around it (within ``_MODE_TOL_M``), else none — an unrelated patch
    (bare soil, a crop field) is strong at a few stations, the edge of the
    graded band is present at most of them."""
    out: list[ImageEvidence] = []
    n = len(cands)
    for i in range(n):
        lo, hi = max(0, i - _WINDOW // 2), min(n, i + _WINDOW // 2 + 1)
        pool = [c for j in range(lo, hi) for c in cands[j]]
        if not pool or not cands[i]:
            out.append(ImageEvidence(None, 0.0, NONE))
            continue
        offs = np.array([c[0] for c in pool])
        wts = np.array([min(1.0, c[1] / (2 * _STEP_MIN)) for c in pool])
        grid = np.arange(offs.min() - _MODE_TOL_M, offs.max() + _MODE_TOL_M + 1e-9, 1.0)
        z = (grid[:, None] - offs[None, :]) / _MODE_TOL_M
        dens = (wts[None, :] * np.exp(-0.5 * z ** 2)).sum(1)
        mode = float(grid[int(np.argmax(dens))])
        best = min(cands[i], key=lambda c: abs(c[0] - mode))
        if abs(best[0] - mode) <= _MODE_TOL_M:
            out.append(ImageEvidence(best[0], min(1.0, best[1] / (2 * _STEP_MIN)), "graded_edge"))
        else:
            out.append(ImageEvidence(None, 0.0, NONE))
    return out


def _marking_rows(rows: np.ndarray, d: float) -> np.ndarray:
    """Per row (M×K), whether it carries the threshold-marking signature:
    a high-contrast row split into at least ``_MIN_STRIPES`` bright stripes
    covering ``_MARK_FRAC`` of it, whose stripes RUN ALONG THE AXIS — the
    row ``_STRIPE_RUN_M`` further on lights the same pixels (IoU at least
    ``_STRIPE_IOU``).  A blast pad's chevrons and a designation's digits
    split a row too, but their stripes move from row to row."""
    n = rows.shape[0]
    ok = np.zeros(n, dtype=bool)
    masks: list[np.ndarray | None] = [None] * n
    min_px = max(1, int(round(0.8 / d)))
    for i, r in enumerate(rows):
        fin = np.isfinite(r)
        if fin.sum() < 8:
            continue
        v = r[fin]
        lo, hi = np.percentile(v, 10), np.percentile(v, 90)
        if hi - lo < _MARK_CONTRAST:
            continue
        bright = np.where(fin, r > (lo + hi) / 2.0, False)
        frac = float(bright[fin].mean())
        if not (_MARK_FRAC[0] <= frac <= _MARK_FRAC[1]):
            continue
        lab, k = ndimage.label(bright)
        if k < _MIN_STRIPES:
            continue
        sizes = ndimage.sum(bright, lab, range(1, k + 1))
        if int((np.asarray(sizes) >= min_px).sum()) >= _MIN_STRIPES:
            ok[i] = True
            masks[i] = bright
    lag = max(1, int(round(_STRIPE_RUN_M / d)))
    out = np.zeros(n, dtype=bool)
    for i in range(n):
        if not ok[i]:
            continue
        for j in (i + lag, i - lag):
            if 0 <= j < n and ok[j]:
                a, b = masks[i], masks[j]
                if (a & b).sum() >= _STRIPE_IOU * max(1, (a | b).sum()):
                    out[i] = True
                    break
    return out


def _first_run(flags: np.ndarray, offsets: np.ndarray, run_m: float) -> float | None:
    """The offset where the first run of True (gaps ≤ ``_GAP_M`` bridged)
    at least ``run_m`` long starts."""
    d = float(np.median(np.diff(offsets))) if offsets.size > 1 else 1.0
    f = ndimage.binary_closing(flags, structure=np.ones(max(1, int(_GAP_M / d)) + 1)) | flags
    lab, n = ndimage.label(f)
    for k in range(1, n + 1):
        idx = np.flatnonzero(lab == k)
        if (idx[-1] - idx[0] + 1) * d >= run_m:
            return float(offsets[idx[0]])
    return None


class ClassicEdges:
    """The classic method (module docstring)."""

    name = "classic_edges"
    version = "1"

    def edges(self, patch: ImagePatch, probes: Probes, kind: str) -> list[ImageEvidence]:
        prof = strip_profiles(patch, probes)
        offs = np.asarray(probes.offsets_m, dtype=float)
        out: list[ImageEvidence] = []
        for i in range(prof.shape[0]):
            rows = prof[i]
            if kind == "threshold_marking":
                at = _first_run(_marking_rows(rows, patch.m_per_px), offs, _MIN_RUN_M)
                out.append(ImageEvidence(at, 1.0 if at is not None else 0.0,
                                         "threshold_marking" if at is not None else NONE))
            elif kind == "pavement_start":
                med = np.nanmedian(rows, axis=1)
                body = med[offs >= offs.max() / 2.0]
                if not np.isfinite(body).any():
                    out.append(ImageEvidence(None, 0.0, NONE))
                    continue
                ref = float(np.nanmedian(body))
                pave = (np.isfinite(med) & (np.abs(med - ref) <= _PAVE_TOL)) \
                    | _marking_rows(rows, patch.m_per_px)
                at = _first_run(pave, offs, _PAVE_RUN_M)
                out.append(ImageEvidence(at, 1.0 if at is not None else 0.0,
                                         "pavement_edge" if at is not None else NONE))
            else:
                med = np.nanmedian(rows, axis=1) if rows.shape[1] > 1 else rows[:, 0]
                ev = _step_edge(med, offs)
                out.append(ImageEvidence(ev.offset_m, ev.strength,
                                         kind if ev.offset_m is not None else NONE))
        if kind == "graded_edge":
            with np.errstate(all="ignore"):
                meds = [np.nanmedian(prof[i], axis=1) for i in range(prof.shape[0])]
            return _coherent([_step_candidates(m, offs) for m in meds])
        return out

    def presence(self, patch: ImagePatch, window_xy: np.ndarray, kind: str) -> ImageEvidence:
        if kind != "portal_opening":
            return ImageEvidence(None, 0.0, NONE)
        lum = patch.luminance()
        h, w = lum.shape
        cx = patch.origin_xy[0] + (np.arange(w) + 0.5) * patch.m_per_px
        cy = patch.origin_xy[1] - (np.arange(h) + 0.5) * patch.m_per_px
        gx, gy = np.meshgrid(cx, cy)
        win = shapely.Polygon(np.asarray(window_xy, dtype=float))
        inside = shapely.contains_xy(win, gx, gy) & np.isfinite(lum)
        ring = (shapely.contains_xy(win.buffer(_SURROUND_M), gx, gy)
                & ~shapely.contains_xy(win, gx, gy) & np.isfinite(lum))
        if inside.sum() < 16 or ring.sum() < 16:
            return ImageEvidence(None, 0.0, NONE)
        score = float(np.median(lum[ring]) - np.percentile(lum[inside], 25))
        strength = max(0.0, min(1.0, score / (2 * _DARK_MIN)))
        return ImageEvidence(0.0 if score >= _DARK_MIN else None, strength,
                             "portal_opening" if score >= _DARK_MIN else NONE)


CLASSIC = register(ClassicEdges())
