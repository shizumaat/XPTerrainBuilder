"""THE FLAT-SITE DETECTOR (RULINGS 2026-09-05k-2; spec
``docs/specs/auto-patch-v2/flat-site-datum-spec.md`` §3.1) — a pure
MEASUREMENT over the loaded :class:`~auto_patch_v2.model.airport.Airport`,
v1's ``auto_patch/flat_site.py`` (flat-site-detector-spec v3) ported
signal for signal, every constant read from ``law/flat_site.toml``:

* **S1** the CIFP threshold consensus: ``max − min`` over the runway
  ends' threshold elevations STRICTLY under ``threshold_spread_max_m``
  (owner 2026-08-09 "spread < 5 m"); their MEAN is ``Z0``;
* **S2** no credible DEM relief over pavement ∪ runways ∪ boundary (the
  GATE extent, margin 0): ``p95 − p5`` at or under the source class's
  floor (``relief_floor_m``) AND the plane-fit slope at or under
  ``plane_slope_max``; a lidar-class pixel SHORT-CIRCUITS to
  ``lidar_credible``; **S2a** the sea band (samples at or under
  ``sea_band_max_m`` are sea / void fill when ``Z0 ≥ sea_band_min_z0_m``);
  **S2b** the DSM trim (samples above ``median + dsm_trim_over_median_m
  × floor`` are roofs, not ground);
* **S3** ``|DEM median − Z0|``, reported, never gated;
* **S4** the pack's placement seats (``anchor DEM + AGL``; an object whose
  deepest solid's authored base is at or under ``below_grade_base_y_m``
  is below grade and excluded) — median within ``seat_consensus_max_m``
  of Z0 and p95−p5 under ``seat_spread_max_m`` CONFIRMS, never gates.

``verdict`` = ``flat_candidate`` ⇔ S1 ∧ S2; ``lidar_credible`` on a
metre-credible source; ``no_data`` with no thresholds or too few DEM
samples; ``not_flat`` otherwise.  A ``[declared]`` entry (option (c))
OVERRIDES the verdict to ``flat_declared`` and ``auto_verdict`` keeps
what the detector measured (v1's audit).  The datum's SOURCE is
``[datum] source`` (``cifp`` | ``pack_seats``) or the declaration's
(``metres`` = the number is the datum).

The DEM read is the production frame — the same composed raster the core
mesh drapes, which at a flat site ALREADY carries the core's plateau
(``dem_production.py``); the core's own ``synthetic_flat_site`` verdict is
read back through the sampler and COMPARED (``signals["core"]``), a
disagreement LOGGED, never reconciled (spec §3.3).  The margin ring
(``pavement ∪ boundary ⊕ margin_m`` minus the core) is measured as report
context with NO gate power (v3 amendment (a)); the dilated extent is the
:class:`FlatVerdict.region` the preference rows cover.

Imports ``law`` and ``model`` only (``test_model.test_dependency_direction``).
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np
from shapely import contains_xy
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.ops import unary_union

from ..law import Law
from ..law.tables import (FLAT_CLASS_COARSE, FLAT_CLASS_LIDAR, flat_declared,
                          flat_relief_floor_m, flat_site, flat_source_class)
from ..model.airport import Airport, FlatVerdict

__all__ = ["VERDICTS", "detect", "log_line", "notes", "record",
           "region_polygon", "dem_relief", "seat_consensus"]

#: The five verdicts (v1 ``VERDICT_*``).
FLAT_CANDIDATE = "flat_candidate"
NOT_FLAT = "not_flat"
LIDAR_CREDIBLE = "lidar_credible"
NO_DATA = "no_data"
FLAT_DECLARED = "flat_declared"
VERDICTS = (FLAT_CANDIDATE, NOT_FLAT, LIDAR_CREDIBLE, NO_DATA, FLAT_DECLARED)

#: Degeneracy guards, not law (v1 ``_MIN_DEM_SAMPLES``): a plane fit needs
#: three non-collinear samples and a p95−p5 over a handful of cells is
#: noise; fewer valid cells than this reports ``no_data``.
_MIN_DEM_SAMPLES = 8
#: The sampling step when the sampler states no posting (a synthetic
#: ``DemSample`` in a twin) — a mechanism default, never a law value; the
#: production sampler always states its own working-grid posting.
_FALLBACK_STEP_M = 30.0
#: The most cells the detector reads (the step coarsens above it): a
#: read-time bound, not a law value.
_MAX_SAMPLES = 400_000
#: Percentiles of the relief measure (p95 − p5; v1).
_P_LO, _P_HI = 5.0, 95.0


# ── the extent ───────────────────────────────────────────────────────────

def _runway_rect(rw) -> Polygon | None:
    (ax, ay), (bx, by) = rw.ends[0].xy, rw.ends[1].xy
    if math.hypot(bx - ax, by - ay) < 1e-6 or rw.width_m <= 0.0:
        return None
    return LineString([(ax, ay), (bx, by)]).buffer(rw.width_m / 2.0, cap_style=2)


def _poly(outer, holes) -> Polygon | None:
    if len(outer) < 3:
        return None
    p = Polygon(list(outer), [list(h) for h in holes if len(h) >= 3])
    if not p.is_valid:
        p = p.buffer(0)
    return None if p.is_empty else p


def region_polygon(airport: Airport, margin_m: float):
    """``(pavement ∪ runways ∪ boundary) ⊕ margin_m`` in the frame (v1
    ``extent_from_apt``, ONE builder for the gate extent, the ring and
    the preference region), or ``None`` with no geometry at all."""
    parts = []
    for rw in airport.runways:
        r = _runway_rect(rw)
        if r is not None:
            parts.append(r)
    for pv in airport.pavements:
        p = _poly(pv.outer, pv.holes)
        if p is not None:
            parts.append(p)
    for b in airport.boundaries:
        p = _poly(b.outer, b.holes)
        if p is not None:
            parts.append(p)
    if not parts:
        return None
    u = unary_union(parts)
    if u.is_empty:
        return None
    if margin_m > 0.0:
        u = u.buffer(float(margin_m))
    return None if u.is_empty else u


def _cut_water(dem, geom):
    """``(geom − water, m² removed)`` — the datum region's water cut
    (owner RULINGS 2026-09-09m (3)).  The witness is the production
    frame's ``water_geometry``; a sampler without one (the authored
    ``DemSampler``, a test double) leaves the region as it is."""
    fn = getattr(dem, "water_geometry", None)
    if not callable(fn):
        return geom, None
    try:
        water = fn(geom.bounds)
    except Exception:                           # pragma: no cover
        return geom, None
    if water is None or water.is_empty:
        return geom, 0.0
    cut = geom.difference(water)
    # an empty cut is honest: a site whose whole region is water has no
    # dry datum region, and mints no datum rows.
    return cut, round(float(geom.area - cut.area), 1)


def _rings(geom) -> tuple[tuple[tuple, tuple], ...]:
    polys = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
    out = []
    for p in polys:
        if p.is_empty or not isinstance(p, Polygon):
            continue
        outer = tuple((float(x), float(y)) for x, y in p.exterior.coords[:-1])
        holes = tuple(tuple((float(x), float(y)) for x, y in h.coords[:-1])
                      for h in p.interiors)
        out.append((outer, holes))
    return tuple(out)


# ── S2: the DEM read ─────────────────────────────────────────────────────

def _samples(dem, geom) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The DEM's cells inside ``geom``: a grid at the sampler's own posting
    (``posting_m()``, the production frame) over the extent's bounds,
    kept where it falls inside the polygon; ``(x, y, z)`` of the finite
    samples."""
    xmin, ymin, xmax, ymax = geom.bounds
    step = None
    post = getattr(dem, "posting_m", None)
    if callable(post):
        try:
            step = post()
        except Exception:
            step = None
    step = float(step) if step and step > 0.0 else _FALLBACK_STEP_M
    span_x, span_y = max(xmax - xmin, step), max(ymax - ymin, step)
    n_est = (span_x / step + 1.0) * (span_y / step + 1.0)
    if n_est > _MAX_SAMPLES:
        step *= math.sqrt(n_est / _MAX_SAMPLES)
    xs = np.arange(xmin, xmax + step, step)
    ys = np.arange(ymin, ymax + step, step)
    gx, gy = np.meshgrid(xs, ys)
    gx, gy = gx.ravel(), gy.ravel()
    keep = contains_xy(geom, gx, gy)
    gx, gy = gx[keep], gy[keep]
    if gx.size == 0:
        return gx, gy, np.zeros(0)
    many = getattr(dem, "z_many", None)
    if callable(many):
        z = np.asarray(many(gx, gy), dtype=float)
    else:
        z = np.array([dem.z(float(x), float(y)) for x, y in zip(gx, gy)], dtype=float)
    ok = np.isfinite(z)
    return gx[ok], gy[ok], z[ok]


def dem_relief(dem, geom, *, z0: float | None, floor_m: float | None,
               sea_band_max_m: float, sea_band_min_z0_m: float,
               dsm_trim: float) -> dict:
    """S2's measurement over ``geom`` (v1 ``dem_relief``): ``{n, median_m,
    p5_m, p95_m, relief_m, slope, residual_std_m, sea_excluded_frac,
    dsm_trimmed_frac, dsm_cutoff_m}``; ``n = 0`` with no usable cells."""
    empty = {"n": 0, "median_m": None, "p5_m": None, "p95_m": None,
             "relief_m": None, "slope": None, "residual_std_m": None,
             "sea_excluded_frac": None, "dsm_trimmed_frac": None,
             "dsm_cutoff_m": None}
    if geom is None or geom.is_empty:
        return empty
    x, y, z = _samples(dem, geom)
    valid_n = int(z.size)
    sea_frac = None
    if z0 is not None and float(z0) >= sea_band_min_z0_m and valid_n:
        sea = z <= sea_band_max_m
        sea_frac = round(float(sea.sum()) / valid_n, 4)
        x, y, z = x[~sea], y[~sea], z[~sea]
    if z.size < _MIN_DEM_SAMPLES:
        return dict(empty, sea_excluded_frac=sea_frac)
    dsm_frac = None
    cutoff = None
    if floor_m is not None:
        land_n = int(z.size)
        cutoff = float(np.median(z)) + dsm_trim * float(floor_m)
        tall = z > cutoff
        dsm_frac = round(float(tall.sum()) / land_n, 4)
        cutoff = round(cutoff, 3)
        x, y, z = x[~tall], y[~tall], z[~tall]
        if z.size < _MIN_DEM_SAMPLES:
            return dict(empty, sea_excluded_frac=sea_frac,
                        dsm_trimmed_frac=dsm_frac, dsm_cutoff_m=cutoff)
    p5, p95 = (float(v) for v in np.percentile(z, [_P_LO, _P_HI]))
    design = np.column_stack([np.ones(z.size), x, y])
    try:
        coef, *_ = np.linalg.lstsq(design, z, rcond=None)
        slope = math.hypot(float(coef[1]), float(coef[2]))
        resid = float((z - design @ coef).std())
    except Exception:                       # pragma: no cover
        slope, resid = None, None
    return {"n": int(z.size), "median_m": round(float(np.median(z)), 3),
            "p5_m": round(p5, 3), "p95_m": round(p95, 3),
            "relief_m": round(p95 - p5, 3),
            "slope": None if slope is None else round(slope, 6),
            "residual_std_m": None if resid is None else round(resid, 3),
            "sea_excluded_frac": sea_frac, "dsm_trimmed_frac": dsm_frac,
            "dsm_cutoff_m": cutoff}


def _source_class(dem, law: Law) -> tuple[str | None, float | None, str]:
    """``(class, pixel_m, whence)``: the production sampler states the
    finest source that baked (``source_pixel_m``); a sampler stating
    nothing is an unknown class."""
    fn = getattr(dem, "source_pixel_m", None)
    if not callable(fn):
        return None, None, "unknown"
    pixel, whence = fn()
    if pixel is None:
        return (FLAT_CLASS_COARSE if whence == "base_tier" else None), None, whence
    return flat_source_class(law, pixel), float(pixel), whence


# ── S4: the pack's seats ─────────────────────────────────────────────────

def seat_consensus(objects: _t.Iterable, z0: float | None, *,
                   below_grade_base_y_m: float, consensus_max_m: float,
                   spread_max_m: float) -> dict:
    """S4 over the placed objects (``airport/obj8.PlacedObject``, duck
    typed: ``resolved``, ``anchor_z``, ``agl_m``, ``solid_min_z``): the
    seat is ``anchor_z + agl_m``; an object whose deepest solid's
    authored base (``solid_min_z − seat``) is at or under
    ``below_grade_base_y_m`` is below grade and excluded (a drainage
    basin's floor is not a ground seat).  ``pass`` is ``None`` with no
    data or no Z0 — never a fail."""
    seats: list[float] = []
    n_total = n_below = 0
    for o in objects or ():
        if not getattr(o, "resolved", None):
            continue
        try:
            seat = float(o.anchor_z) + float(o.agl_m)
        except (TypeError, ValueError, AttributeError):
            continue
        if not math.isfinite(seat):
            continue
        n_total += 1
        smz = getattr(o, "solid_min_z", None)
        if smz is not None and math.isfinite(float(smz)) and \
                float(smz) - seat <= below_grade_base_y_m:
            n_below += 1
            continue
        seats.append(seat)
    out = {"n": len(seats), "n_total": n_total, "n_below_grade": n_below,
           "median_m": None, "spread_m": None, "offset_m": None, "pass": None}
    if not seats:
        return out
    arr = np.asarray(seats, dtype=float)
    p5, p95 = (float(v) for v in np.percentile(arr, [_P_LO, _P_HI]))
    med = float(np.median(arr))
    out.update(median_m=round(med, 3), spread_m=round(p95 - p5, 3))
    if z0 is not None:
        off = abs(med - float(z0))
        out.update(offset_m=round(off, 3),
                   **{"pass": bool(off <= consensus_max_m and p95 - p5 <= spread_max_m)})
    return out


# ── the detector ─────────────────────────────────────────────────────────

def detect(airport: Airport, law: Law, *, objects: _t.Iterable = ()
           ) -> FlatVerdict:
    """The verdict for ``airport`` under ``law`` (module docstring).
    ``objects`` are the placed objects the planar stage read (S4; empty
    = ``no_data``, never a fail)."""
    fs = flat_site(law)
    det = fs.detector
    icao = airport.icao.upper()
    # S1
    thr = [float(e.threshold_elev_m) for rw in airport.runways for e in rw.ends
           if e.threshold_elev_m is not None and math.isfinite(float(e.threshold_elev_m))]
    spread = (max(thr) - min(thr)) if thr else None
    z0_cifp = (sum(thr) / len(thr)) if thr else None
    s1_pass = None if spread is None else bool(spread < det.threshold_spread_max_m)
    # S2
    klass, pixel, whence = _source_class(airport.dem, law)
    floor_m = flat_relief_floor_m(law, klass)
    core = region_polygon(airport, 0.0)
    full = region_polygon(airport, det.margin_m)
    ring = None
    if core is not None and full is not None:
        ring = full.difference(core)
        if ring.is_empty:
            ring = None
    kw = dict(z0=z0_cifp, floor_m=floor_m, sea_band_max_m=det.sea_band_max_m,
              sea_band_min_z0_m=det.sea_band_min_z0_m,
              dsm_trim=det.dsm_trim_over_median_m)
    relief = dem_relief(airport.dem, core, **kw)
    ring_rel = dem_relief(airport.dem, ring, **kw) if ring is not None else {}
    slope_ok = relief.get("slope") is not None and relief["slope"] <= det.plane_slope_max
    relief_ok = floor_m is not None and relief.get("relief_m") is not None \
        and relief["relief_m"] <= floor_m
    s2_pass = None if (relief.get("n", 0) == 0 or floor_m is None) \
        else bool(slope_ok and relief_ok)
    # S3
    offset = None
    if z0_cifp is not None and relief.get("median_m") is not None:
        offset = round(abs(float(relief["median_m"]) - z0_cifp), 3)
    # S4
    s4 = seat_consensus(objects, z0_cifp,
                        below_grade_base_y_m=det.below_grade_base_y_m,
                        consensus_max_m=det.seat_consensus_max_m,
                        spread_max_m=det.seat_spread_max_m)
    if s1_pass is None or relief.get("n", 0) == 0:
        auto = NO_DATA
    elif klass == FLAT_CLASS_LIDAR:
        auto = LIDAR_CREDIBLE
    elif s2_pass is None:
        auto = NO_DATA
    elif s1_pass and s2_pass:
        auto = FLAT_CANDIDATE
    else:
        auto = NOT_FLAT
    # the datum: [datum] source, or the declaration's
    decl = flat_declared(law, icao)
    source = decl.source if decl is not None else fs.datum.source
    if source == "metres":
        z0 = float(decl.z0)
    elif source == "pack_seats" and s4.get("median_m") is not None:
        z0 = float(s4["median_m"])
    else:
        z0 = z0_cifp
    verdict = FLAT_DECLARED if decl is not None else auto
    # the core's own verdict on the composed raster (spec §3.3)
    core_rec = None
    fn = getattr(airport.dem, "core_flat_site", None)
    if callable(fn):
        try:
            core_rec = fn()
        except Exception:                   # pragma: no cover
            core_rec = None
    # THE DATUM REGION NEVER COVERS WATER (owner RULINGS 2026-09-09m (3)).
    # Cut at the region's SINGLE derivation site, so every consumer of
    # ``FlatVerdict.region`` — the datum preference rows
    # (``constraints/flat_site.py``) and the object seats' region
    # (``emit/rebake.py`` ``_Region``, 08f (e)) — excludes water with no
    # second rule anywhere.  The witness is the production frame's
    # (``dem_production.TileWater``); a sampler without one leaves the
    # region untouched.
    water_cut_m2 = None
    if full is not None:
        full, water_cut_m2 = _cut_water(airport.dem, full)
    core_sig = None if core_rec is None else {
        "verdict": core_rec.get("verdict"), "z0_m": core_rec.get("z0_m")}
    signals = {
        "icao": icao, "declared": decl is not None,
        "declared_source": None if decl is None else decl.source,
        "z0_cifp_m": None if z0_cifp is None else round(z0_cifp, 3),
        "s1_spread_m": None if spread is None else round(spread, 3),
        "s1_threshold_count": len(thr), "s1_pass": s1_pass,
        "s2_source_class": klass, "s2_source_pixel_m": pixel,
        "s2_source_whence": whence, "s2_relief_floor_m": floor_m,
        "s2": relief, "s2_ring": ring_rel, "s2_pass": s2_pass,
        "s3_offset_m": offset, "s4": s4,
        "core": core_sig,
        "region_area_m2": None if full is None else round(float(full.area), 1),
        "region_water_cut_m2": water_cut_m2,
    }
    return FlatVerdict(verdict, auto, None if z0 is None else round(z0, 3),
                       source,
                       _rings(full) if full is not None and not full.is_empty else (),
                       signals)


# ── the report ───────────────────────────────────────────────────────────

def record(v: FlatVerdict) -> dict:
    """``report.load.flat_site``: the verdict and every signal, JSON-plain."""
    return {"verdict": v.verdict, "auto_verdict": v.auto_verdict,
            "z0_m": v.z0_m, "source": v.source, "substitutes": v.substitutes,
            "signals": dict(v.signals)}


def _num(value, digits: int = 2, unit: str = "") -> str:
    return "?" if value is None else f"{float(value):.{digits}f}{unit}"


def log_line(icao: str, v: FlatVerdict) -> str:
    """The one ``[flat-site]`` line per airport (v1 ``format_log_line``'s
    shape, so the two engines' lines read alike)."""
    s = v.signals
    r = s.get("s2") or {}
    sea = r.get("sea_excluded_frac")
    extra = "" if sea is None else f", sea-excluded {100.0 * float(sea):.0f} %"
    trim = r.get("dsm_trimmed_frac")
    if trim is not None:
        extra += f", dsm-trimmed {100.0 * float(trim):.0f} %"
    s4 = s.get("s4") or {}
    if s4.get("pass") is None:
        seats = "no_data" if not s4.get("n") else f"n={s4.get('n')}"
    else:
        seats = (f"{'ok' if s4['pass'] else 'no'} (n={s4.get('n')}, off "
                 f"{_num(s4.get('offset_m'))} m, spread {_num(s4.get('spread_m'))} m)")
    cut = s.get("region_water_cut_m2")
    if cut:
        extra += f", datum region minus {float(cut) / 1e6:.4f} km2 of WATER"
    declared = "" if not s.get("declared") else \
        f" [DECLARED {s.get('declared_source')}; detector said {v.auto_verdict}]"
    slope = r.get("slope")
    return (f"[flat-site] {icao}: {v.verdict} — Z0 {_num(v.z0_m)} m ({v.source}; "
            f"CIFP spread {_num(s.get('s1_spread_m'))} m over "
            f"{s.get('s1_threshold_count', 0)} threshold(s)) | "
            f"DEM {s.get('s2_source_class') or '?'}[{s.get('s2_source_whence') or '?'}] "
            f"relief {_num(r.get('relief_m'))} m vs floor "
            f"{_num(s.get('s2_relief_floor_m'), 1)} m, slope "
            f"{'?' if slope is None else f'{100.0 * slope:.3f}'} %{extra} | "
            f"DEM−Z0 {_num(s.get('s3_offset_m'))} m | seats {seats}" + declared)


def notes(icao: str, v: FlatVerdict) -> list[str]:
    """Follow-up lines: the core-vs-v2 comparison when the two verdicts
    or datums differ (LOGGED, never reconciled — spec §3.3)."""
    core = v.signals.get("core")
    out: list[str] = []
    if core is None:
        if v.substitutes:
            out.append(f"[flat-site] {icao}: v2 {v.verdict} vs core NONE — the composed "
                       f"raster carries no synthetic_flat_site record for this airport")
        return out
    cz = core.get("z0_m")
    same_z = v.z0_m is not None and cz is not None and abs(float(cz) - v.z0_m) < 1e-3
    if core.get("verdict") != v.auto_verdict or (v.substitutes and not same_z):
        out.append(f"[flat-site] {icao}: v2 {v.auto_verdict} (Z0 {_num(v.z0_m)}) vs core "
                   f"{core.get('verdict')} (Z0 {_num(cz)}) — DISAGREEMENT, logged, not reconciled")
    return out
