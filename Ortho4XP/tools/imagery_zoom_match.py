"""Does a provider serve the SAME capture at coarse zooms as at full ZL?
(#2017: Bing serves a different, green capture at z12 and coarser at
KMRY; ``min_source_zl`` in a provider's ``.lay`` is set only where this
tool measured a boundary.)

    cd Ortho4XP && venv/bin/python tools/imagery_zoom_match.py \\
        --provider BI --lat 36.587 --lon -121.843 --out SCRATCH_DIR

Fetches, through the engine's own ``download_jpeg_ortho`` into
``--out`` only (never the data repo's orthophoto cache):

* the ZL14 square holding the point at drops 0..4 (z14..z10, 341 map
  requests),
* ``--squares`` ZL16 squares inside it at z16 (the reference, 256 each)
  and z15 (64 each) -- the one holding the point, then the farthest.

The provider's own ``min_source_zl`` is switched off for the run: the
tool measures what the server sends at each zoom.

Each ZL16 square splits into 2 x 2 samples; per zoom 10..15 the tool
prints the square-mean CIEDE2000 against z16 (mean and max over samples,
water and failed pixels masked from the reference), the median
brightness correlation (L*, ``--res`` px per sample) and the mean
L*a*b* shift (a* < 0 greener).  A zoom whose
square-mean dE is small (about 1-3) and whose rL is high is the same
capture; a jump in dE with a fall in rL is a different one.  ``--json``
writes the table.  ~1,000 requests per run with the defaults.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(1, _SRC)

_M = np.array([[0.4124564, 0.3575761, 0.1804375],
               [0.2126729, 0.7151522, 0.0721750],
               [0.0193339, 0.1191920, 0.9503041]])
_WHITE = np.array([0.95047, 1.0, 1.08883])


def srgb_to_lab(rgb):
    """CIE L*a*b* (D65) of an sRGB uint8 array (..., 3)."""
    c = rgb.astype(np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = c @ _M.T / _WHITE
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], -1)


def de2000(l1, l2):
    """CIEDE2000 between two L*a*b* arrays."""
    L1, a1, b1 = (l1[..., i] for i in range(3))
    L2, a2, b2 = (l2[..., i] for i in range(3))
    cm = (np.hypot(a1, b1) + np.hypot(a2, b2)) / 2
    g = 0.5 * (1 - np.sqrt(cm ** 7 / (cm ** 7 + 25 ** 7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1 = np.degrees(np.arctan2(b1, a1p)) % 360
    h2 = np.degrees(np.arctan2(b2, a2p)) % 360
    dl, dc = L2 - L1, c2p - c1p
    dh = h2 - h1
    dh = np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh))
    dh = np.where(c1p * c2p == 0, 0, dh)
    dhh = 2 * np.sqrt(c1p * c2p) * np.sin(np.radians(dh / 2))
    lm, cmp_ = (L1 + L2) / 2, (c1p + c2p) / 2
    hs = h1 + h2
    hm = np.where(np.abs(h1 - h2) > 180, (hs + 360) / 2, hs / 2)
    hm = np.where(c1p * c2p == 0, hs, hm)
    t = (1 - 0.17 * np.cos(np.radians(hm - 30)) + 0.24 * np.cos(np.radians(2 * hm))
         + 0.32 * np.cos(np.radians(3 * hm + 6)) - 0.20 * np.cos(np.radians(4 * hm - 63)))
    dth = 30 * np.exp(-((hm - 275) / 25) ** 2)
    rc = 2 * np.sqrt(cmp_ ** 7 / (cmp_ ** 7 + 25 ** 7))
    sl = 1 + 0.015 * (lm - 50) ** 2 / np.sqrt(20 + (lm - 50) ** 2)
    sc, sh = 1 + 0.045 * cmp_, 1 + 0.015 * cmp_ * t
    rt = -np.sin(np.radians(2 * dth)) * rc
    return np.sqrt((dl / sl) ** 2 + (dc / sc) ** 2 + (dhh / sh) ** 2
                   + rt * (dc / sc) * (dhh / sh))


def _engine():
    import O4_File_Names as FNAMES
    sys.path.append(FNAMES.Provider_dir)
    import O4_Geo_Utils as GEO
    import O4_Imagery_Utils as IMG
    IMG.initialize_extents_dict()
    IMG.initialize_color_filters_dict()
    IMG.initialize_providers_dict()
    IMG.initialize_combined_providers_dict()
    if IMG.shared_tile_cache_dir is not None:
        raise SystemExit("refusing: the shared tile cache is on")
    return GEO, IMG


def _fetch(IMG, out, provider, x, y, zl, drop):
    # the server's own answer at each zoom: the floor under test is off
    IMG.providers_dict[provider].pop("min_source_zl", None)
    d = os.path.join(out, provider, "fetch")
    name = "%d_%d_%s%d_d%d.jpg" % (y, x, provider, zl, drop)
    path = os.path.join(d, name)
    if not os.path.isfile(path):
        IMG.download_jpeg_ortho(d, name, x, y, zl, provider, drop=drop)
    return np.asarray(Image.open(path).convert("RGB"))


def _ref_squares(fx, fy, n):
    """ZL16 square offsets (0..3, 0..3) inside the ZL14 square: the one
    holding the point first, then the farthest from it, then the rest."""
    order = sorted(((i, j) for i in range(4) for j in range(4)),
                   key=lambda s: -((s[0] - fx) ** 2 + (s[1] - fy) ** 2))
    first = (min(3, int(fx)), min(3, int(fy)))
    rest = [s for s in order if s != first]
    return [first] + rest[:max(0, n - 1)]


def _shrink(rgb, res):
    return np.asarray(Image.fromarray(rgb).resize((res, res), Image.BOX))


def measure(provider, lat, lon, out, squares=2, res=32):
    """The per-zoom table (dict zoom -> metrics) for one site/provider."""
    GEO, IMG = _engine()
    x14, y14 = GEO.wgs84_to_orthogrid(lat, lon, 14)
    tx, ty = GEO.wgs84_to_gtile(lat, lon, 16)
    fx, fy = (tx - x14 * 4) / 16.0, (ty - y14 * 4) / 16.0
    coarse = {14 - d: _fetch(IMG, out, provider, x14, y14, 14, d) for d in range(5)}
    samples = {z: [] for z in range(10, 17)}
    for i, j in _ref_squares(fx, fy, squares):
        x16, y16 = x14 * 4 + 16 * i, y14 * 4 + 16 * j
        fine = {16: _fetch(IMG, out, provider, x16, y16, 16, 0),
                15: _fetch(IMG, out, provider, x16, y16, 16, 1)}
        for qi in range(2):
            for qj in range(2):
                for z, img in fine.items():
                    s = img.shape[0] // 2
                    samples[z].append(_shrink(img[qj * s:(qj + 1) * s, qi * s:(qi + 1) * s], res))
                for z, img in coarse.items():
                    s = img.shape[0] // 8
                    r0, c0 = (2 * j + qj) * s, (2 * i + qi) * s
                    samples[z].append(_shrink(img[r0:r0 + s, c0:c0 + s], res))
    lab = {z: np.stack([srgb_to_lab(s) for s in v]) for z, v in samples.items()}
    rgb = {z: np.stack(v) for z, v in samples.items()}
    bad = np.zeros(lab[16].shape[:3], bool)
    for z in rgb:
        bad |= np.all(rgb[z] >= 254, -1)
    L, a, b = (lab[16][..., k] for k in range(3))
    hue = np.degrees(np.arctan2(b, a)) % 360
    water = ((hue > 180) & (hue < 300) & (np.hypot(a, b) > 4)) | (L < 18)
    land = ~(water | bad)
    table = {}
    for z in range(10, 16):
        des, rls, shift = [], [], []
        for k in range(len(samples[16])):
            m = land[k]
            if m.sum() < 0.2 * m.size:
                continue
            des.append(float(de2000(lab[z][k][m].mean(0), lab[16][k][m].mean(0))))
            rls.append(float(np.corrcoef(lab[z][k][..., 0][m], lab[16][k][..., 0][m])[0, 1]))
            shift.append(lab[z][k][m].mean(0) - lab[16][k][m].mean(0))
        table[z] = {"dE_sqmean": round(float(np.mean(des)), 2) if des else None,
                    "dE_sqmax": round(float(np.max(des)), 2) if des else None,
                    "rL": round(float(np.median(rls)), 3) if rls else None,
                    "dLab": [round(float(v), 1) for v in np.mean(shift, 0)] if shift else None,
                    "samples": len(des)}
    return table


def main(argv=None):
    import O4_Console_Encoding
    O4_Console_Encoding.configure_console_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--provider", required=True)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--out", required=True, help="scratch folder (never the data repo)")
    ap.add_argument("--squares", type=int, default=2)
    ap.add_argument("--res", type=int, default=32)
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    table = measure(a.provider, a.lat, a.lon, a.out, a.squares, a.res)
    print("%s @ %.4f,%.4f  (reference z16)" % (a.provider, a.lat, a.lon))
    for z, row in table.items():
        print("  z%-2d dE_sqmean %-6s max %-6s rL %-6s dLab %s n=%d" % (
            z, row["dE_sqmean"], row["dE_sqmax"], row["rL"], row["dLab"],
            row["samples"]))
    if a.json:
        with open(a.json, "w") as f:
            json.dump({"provider": a.provider, "lat": a.lat, "lon": a.lon,
                       "table": table}, f, indent=1)


if __name__ == "__main__":
    main()
