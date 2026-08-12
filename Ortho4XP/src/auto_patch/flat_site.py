"""FLAT-SITE detector — REPORT-ONLY classification of an airport's site.

Spec: ``docs/specs/flat-site-detector-spec.md`` (2026-08-09, FROZEN),
phase 1 of the owner's 2026-08-09 charter ("we want to see if we can
implement a simplification for airports like OTHH that are pretty much at
sea level, and are genuinely flat ... recommend a plan for identifying
this scenario at other airports").

**Nothing here changes any build path.**  The detector measures four
signals, writes one log line and one sidecar evidence record
(``site_class``), and returns.  No solver, emitter or law reads it.
Phase 2 — a FLAT-SITE solve mode at the CIFP consensus elevation — is a
separate spec the owner writes after reading this detector's sweep.

THE FOUR SIGNALS (spec section 2)

* **S1 — threshold consensus.**  ``max − min`` over the airport's CIFP
  runway threshold elevations must be ≤
  :data:`~auto_patch.config.FLAT_SITE_THRESHOLD_SPREAD_M`.  Their mean is
  the consensus elevation ``Z0`` — instrument truth for the site.
* **S2 — no credible DEM relief.**  Over ``pavement ∪ boundary`` — the
  GATE extent, v3 amendment (a) — the plane-fit slope must be ≤
  ``FLAT_SITE_MAX_SLOPE_PCT`` AND the ``p95 − p5`` relief must be at or
  under the NOISE FLOOR OF THE DEM'S OWN SOURCE CLASS
  (``FLAT_SITE_RELIEF_FLOOR_BY_CLASS``).  The ``FLAT_SITE_MARGIN_M``
  ring is measured the same way and kept as ``s2_ring_*`` context with
  NO GATE POWER: the mode flattens the airport and feathers outward, so
  surrounding terrain has no standing to veto it.  A metre-credible
  (LIDAR-class) source SHORT-CIRCUITS to ``lidar_credible`` — that DEM
  is trustworthy and the normal path already handles a flat site
  correctly under it.
* **S2a — the SEA-BAND EXCLUSION** (v2 amendment).  At a site whose Z0
  sits at or above ``FLAT_SITE_SEA_BAND_MIN_Z0_M``, DEM samples at or
  below the sea surface are excluded from BOTH the percentiles and the
  plane fit: they are sea or void fill, not terrain testimony, and a
  plane regressed through land and bay zeros together measures the
  shoreline rather than the airfield.  A below-sea site keeps every
  sample.  The excluded share rides in ``s2_sea_excluded_frac``.
* **S3 — DEM-vs-instrument offset**, reported and never gated.  A large
  offset at a flat-candidate site is EVIDENCE FOR the DEM being
  unreliable (OTHH: 3.96 m), not against candidacy.
* **S4 — pack-object consensus**, confirmatory only, from a prior
  post-mesh pad-request sidecar when one exists.  Absent data is
  ``no_data``, never a fail.

WHERE THE SOURCE CLASS COMES FROM (spec section 2, S2).  Only the
EXISTING DEM/inset provenance surface, in this order:

1. the airport-elevation INSETS that actually baked into this DEM
   (``provenance.dem_provenance_from_dem`` → ``native_resolution_m``,
   written by the fetch sidecar and stamped by
   ``O4_Airport_Elevation_Insets.bake_airport_insets_into_alt_dem``);
2. the tile-wide OVERLAY that baked into it
   (``dem.tile_overlay_provenance['target_resolution_m']``, stamped by
   ``O4_Elevation_Level``);
3. otherwise the BASE TIER, whose class the tile's own elevation level
   declares — ``O4_Elevation_Level.base_prefers_coarse`` is exactly the
   "90 m (3 arc-second) class or 1 arc-second class" question, and
   ``dem.elevation_level`` is the value it was loaded with.

**The raster's own posting is NOT consulted, and must not be**: a
1201×1201 (3 arc-second) ``.hgt`` is UPSAMPLED to 3601×3601 by
``O4_DEM_Utils.read_elevation_from_file`` with no record of the native
size, so ``nxdem`` reports a 1-arcsec grid over 3-arcsec data.  Reading
posting off the array would put OTHH under the 1-arcsec floor (5 m) when
its data is 3-arcsec (8 m) and flip the type specimen's verdict.
"""
from __future__ import annotations

import math
import os
from typing import Iterable, Sequence

from . import config as _config

__all__ = [
    "VERDICT_FLAT_CANDIDATE",
    "VERDICT_NOT_FLAT",
    "VERDICT_LIDAR_CREDIBLE",
    "VERDICT_NO_DATA",
    "VERDICT_FLAT_DECLARED",
    "declared_flat_airports",
    "declared_flat_elevations",
    "extents_from_apt",
    "SOURCE_CLASS_LIDAR",
    "cifp_threshold_elevations",
    "threshold_consensus",
    "source_class_for_dem",
    "extent_from_apt",
    "dem_relief",
    "pack_seat_targets",
    "pack_consensus",
    "classify_site",
    "detect_for_layout",
    "format_log_line",
]


#: The four verdicts.  ``no_data`` is what an absent CIFP file or an
#: absent/empty DEM produces — never a crash, never a silent "not flat".
VERDICT_FLAT_CANDIDATE = "flat_candidate"
VERDICT_NOT_FLAT = "not_flat"
VERDICT_LIDAR_CREDIBLE = "lidar_credible"
VERDICT_NO_DATA = "no_data"

#: (c) The OWNER DECLARATION verdict.  A DISTINCT string with full
#: provenance beside it — the flat-site MODE treats it exactly as
#: ``flat_candidate``, and a reader can always tell the two apart.
VERDICT_FLAT_DECLARED = "flat_declared"

#: The metre-credible class.  Its presence short-circuits S2.
SOURCE_CLASS_LIDAR = "lidar"

#: Degeneracy guard, not a law value: a plane fit needs three
#: non-collinear samples and a p95−p5 over a handful of cells is noise.
#: An extent yielding fewer valid DEM cells than this reports ``no_data``.
_MIN_DEM_SAMPLES = 8

#: Local-metre projection constant — ``layout.R_EARTH``'s value, imported
#: lazily at use so this module stays importable without the layout
#: package (the sweep and the tests both import it bare).
_R_EARTH = 6378137.0


# ──────────────────────────────────────────────────────────────────────
# S1 — CIFP threshold consensus
# ──────────────────────────────────────────────────────────────────────
def cifp_threshold_elevations(xplane_root: str, icao: str) -> list:
    """Every CIFP runway threshold elevation (metres) for ``icao``.

    Uses the engine's OWN CIFP locator and parser
    (``elevation._find_cifp_path`` → ``cifp_reader.parse_cifp_file``) so
    the detector reads the same file, with the same AIRAC precedence, as
    the runway profile does.  Empty list when no CIFP file exists.
    """
    from .elevation import _find_cifp_path

    path = _find_cifp_path(xplane_root, icao)
    if not path:
        return []
    return cifp_threshold_elevations_from_file(path)


def cifp_threshold_elevations_from_file(path: str) -> list:
    """The threshold elevations in one CIFP ``.dat`` file, metres."""
    from . import cifp_reader as _CIFP

    try:
        runways = _CIFP.parse_cifp_file(path)
    except Exception:                                # pragma: no cover
        return []
    out = []
    for record in (runways or {}).values():
        try:
            out.append(float(record["elevation_m"]))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def threshold_consensus(elevations_m: Sequence) -> dict:
    """S1 — ``{n, spread_m, z0_m, pass}`` over the CIFP thresholds.

    ``z0_m`` is the MEAN of the thresholds (the spec's consensus Z0) and
    is ``None`` when there are none.  ``pass`` is ``None`` (not False)
    with no data: absent instrument truth is not a failed consensus.

    The comparison is STRICTLY less-than, which is how the owner's
    2026-08-09 ruling is worded ("CIFP threshold spread < 5m should be a
    flat candidate") and how spec section 2 spells S1.  The boundary is
    reachable in practice — CIFP elevations are whole feet, and 16 ft is
    4.877 m — so ``<`` versus ``<=`` is a real distinction, not a
    formality.
    """
    values = [float(v) for v in (elevations_m or ())
              if v is not None and float(v) == float(v)]
    if not values:
        return {"n": 0, "spread_m": None, "z0_m": None, "pass": None}
    spread = max(values) - min(values)
    return {
        "n": len(values),
        "spread_m": round(spread, 3),
        "z0_m": round(sum(values) / len(values), 3),
        "pass": bool(spread < _config.FLAT_SITE_THRESHOLD_SPREAD_M),
    }


# ──────────────────────────────────────────────────────────────────────
# S2a — the DEM's source class (provenance only; see the module docstring)
# ──────────────────────────────────────────────────────────────────────
def class_for_resolution_m(resolution_m) -> str | None:
    """The source class of a declared native resolution, or ``None``."""
    if resolution_m is None:
        return None
    try:
        metres = float(resolution_m)
    except (TypeError, ValueError):
        return None
    if metres != metres or metres <= 0.0:
        return None
    for bound_m, name in _config.FLAT_SITE_SOURCE_CLASS_BOUNDS_M:
        if metres <= bound_m:
            return name
    return _config.FLAT_SITE_COARSE_SOURCE_CLASS


def source_class_for_dem(dem, icao: str | None = None,
                         dem_meta: dict | None = None) -> dict:
    """``{class, resolution_m, whence}`` for the DEM the solve grades on.

    ``whence`` names WHICH provenance surface answered — ``inset``,
    ``overlay``, ``base_tier`` or ``unknown`` — so a report can never
    confuse a declared resolution with an assumed one.  ``dem_meta`` is
    an already-computed ``provenance.dem_provenance_from_dem`` result
    (the pipeline has one in hand; recomputed here when omitted).
    """
    if dem is None:
        return {"class": None, "resolution_m": None, "whence": "unknown"}

    if dem_meta is None:
        try:
            from . import provenance as _provenance

            dem_meta = _provenance.dem_provenance_from_dem(dem, icao=icao)
        except Exception:                            # pragma: no cover
            dem_meta = None

    # 1 — the airport-elevation insets that actually baked into this DEM.
    #     The FINEST wins: the insets are fetched FOR this airport and
    #     cover exactly the footprint the detector measures over.
    finest = None
    for entry in ((dem_meta or {}).get("insets") or ()):
        if not isinstance(entry, dict):
            continue
        value = entry.get("native_resolution_m")
        if value is None:
            value = entry.get("resolution_m")
        try:
            value = float(value)
        except (TypeError, ValueError):
            continue
        if value > 0.0 and (finest is None or value < finest):
            finest = value
    if finest is not None:
        return {"class": class_for_resolution_m(finest),
                "resolution_m": finest, "whence": "inset"}

    # 2 — the tile-wide elevation overlay, when one baked.
    overlay = getattr(dem, "tile_overlay_provenance", None)
    if isinstance(overlay, dict):
        try:
            value = float(overlay.get("target_resolution_m"))
        except (TypeError, ValueError):
            value = None
        if value and value > 0.0:
            return {"class": class_for_resolution_m(value),
                    "resolution_m": value, "whence": "overlay"}

    # 3 — the base tier.  ``base_prefers_coarse`` IS the engine's own
    #     "90 m (3 arc-second) class vs 1 arc-second class" question, and
    #     ``dem.elevation_level`` is the value this DEM was loaded with.
    level = getattr(dem, "elevation_level", None)
    if level is None:
        return {"class": None, "resolution_m": None, "whence": "unknown"}
    try:
        import O4_Elevation_Level as _LEVEL

        coarse = bool(_LEVEL.base_prefers_coarse(level))
    except Exception:                                # pragma: no cover
        return {"class": None, "resolution_m": None, "whence": "unknown"}
    resolution_m = (_config.FLAT_SITE_BASE_COARSE_RESOLUTION_M if coarse
                    else _config.FLAT_SITE_BASE_FINE_RESOLUTION_M)
    return {"class": class_for_resolution_m(resolution_m),
            "resolution_m": resolution_m, "whence": "base_tier"}


def relief_floor_for_class(source_class: str | None):
    """The p95−p5 noise floor of a source class, or ``None``."""
    if not source_class:
        return None
    return _config.FLAT_SITE_RELIEF_FLOOR_BY_CLASS.get(source_class)


# ──────────────────────────────────────────────────────────────────────
# S2b — the measurement extent
# ──────────────────────────────────────────────────────────────────────
def extent_from_apt(apt, to_m, margin_m: float | None = None):
    """``(pavement ∪ runways ∪ boundary) ⊕ margin`` in LOCAL METRES.

    ONE builder, driven by the apt.dat record, so the pipeline call site
    and the offline sweep measure over the SAME population — a second
    extent derived from the built layout's shapes would be a different
    footprint (it carries taxi rects, groundside and clearance cuts the
    apt.dat record does not), and two instruments over two populations is
    how this repo has been burned before.

    ``to_m`` is the layout's ``(lon, lat) -> (x, y)`` projection.
    Returns ``None`` when the airport contributes no geometry at all.
    """
    from shapely.geometry import Polygon
    from shapely.ops import transform as _shp_transform
    from shapely.ops import unary_union

    from .pavement.runways import _runway_rect_m

    if margin_m is None:
        margin_m = _config.FLAT_SITE_MARGIN_M
    parts = []
    for runway in (getattr(apt, "runways", None) or ()):
        try:
            rect = _runway_rect_m(runway, to_m)
        except Exception:                            # pragma: no cover
            continue
        if rect is not None and not rect.is_empty:
            parts.append(rect)
    for pavement in (getattr(apt, "pavements", None) or ()):
        polygon = getattr(pavement, "polygon", None)
        if polygon is None or polygon.is_empty:
            continue
        try:
            projected = _shp_transform(to_m, polygon)
        except Exception:                            # pragma: no cover
            continue
        if not projected.is_empty:
            parts.append(projected)
    boundary = getattr(apt, "boundary", None)
    if boundary is not None and not boundary.is_empty:
        try:
            projected = _shp_transform(
                lambda lon, lat, z=None: to_m(lon, lat), boundary)
        except Exception:                            # pragma: no cover
            projected = None
        if projected is not None and not projected.is_empty:
            parts.append(projected)
    if not parts:
        return None
    try:
        union = unary_union(parts)
    except Exception:                                # pragma: no cover
        return None
    if union.is_empty:
        return None
    buffered = union.buffer(float(margin_m))
    return None if buffered.is_empty else buffered


def sea_band_applies(z0_m) -> bool:
    """Whether S2a's sea-band exclusion runs at a site with this ``Z0``.

    False with no instrument truth (nothing to judge the zeros against)
    and false below ``FLAT_SITE_SEA_BAND_MIN_Z0_M`` — a below-sea or
    at-sea airport's zeros are plausible TERRAIN, and discarding them
    would delete the very ground it is built on.
    """
    if z0_m is None:
        return False
    try:
        return float(z0_m) >= _config.FLAT_SITE_SEA_BAND_MIN_Z0_M
    except (TypeError, ValueError):                  # pragma: no cover
        return False


def extents_from_apt(apt, to_m, margin_m: float | None = None):
    """``(gate_extent, ring)`` in local metres.

    v3 amendment (a): the GATE statistics are taken over ``pavement ∪
    boundary`` alone; the margin ring — the same 200 m band, now a
    difference rather than a dilation — is REPORT-ONLY context.  Both
    come from the one builder, so the two zones can never describe
    different airports.
    """
    core = extent_from_apt(apt, to_m, margin_m=0.0)
    if core is None:
        return None, None
    full = extent_from_apt(apt, to_m, margin_m=margin_m)
    ring = None
    if full is not None:
        try:
            ring = full.difference(core)
            if ring.is_empty:
                ring = None
        except Exception:                            # pragma: no cover
            ring = None
    return core, ring


# ──────────────────────────────────────────────────────────────────────
# (c) THE OWNER DECLARATION — intent never waits on statistics
# ──────────────────────────────────────────────────────────────────────
def _cfg_value(name: str, override=None) -> str:
    """A tile-cfg string, from an explicit override or the live config.

    Read through ``O4_Config_Utils``' module attribute — the surface the
    global and per-tile cfg loaders both write — with a getattr default,
    so a frozen engine, a bare test process or a tree predating the key
    all read "" rather than raising.
    """
    if override is not None:
        return str(override)
    try:
        import O4_Config_Utils as _CFG

        return str(getattr(_CFG, name, "") or "")
    except Exception:                                # pragma: no cover
        return ""


def declared_flat_airports(value=None) -> set:
    """The ICAOs the owner has DECLARED flat (``flat_site_declared``)."""
    raw = _cfg_value("flat_site_declared", value)
    return {token.strip().upper() for token in raw.split(",") if token.strip()}


def declared_flat_elevations(value=None) -> dict:
    """``{ICAO: metres}`` from ``flat_site_declared_elevation_m``.

    Malformed pairs are SKIPPED, never raised on and never guessed at: a
    typo in a cfg string must not take a build down, and the airport
    simply falls back to its CIFP consensus Z0.
    """
    raw = _cfg_value("flat_site_declared_elevation_m", value)
    out = {}
    for token in raw.split(","):
        token = token.strip()
        if not token or ":" not in token:
            continue
        icao, _, metres = token.partition(":")
        try:
            out[icao.strip().upper()] = float(metres)
        except (TypeError, ValueError):
            continue
    return out


def dem_relief(dem, tile_lat: int, tile_lon: int, anchor, extent_m,
               z0_m=None, relief_floor_m=None) -> dict:
    """S2's measurement over ``extent_m`` (local metres about ``anchor``).

    Reads the DEM's OWN cells inside the extent — nothing is invented
    between samples — and returns ``{n, median_m, p5_m, p95_m, relief_m,
    slope_pct, residual_std_m, sea_excluded_frac}``, or a record with
    ``n = 0`` when the DEM exposes no usable raster over the extent.
    ``nodata`` cells are dropped, never zero-filled.

    S2a — THE SEA-BAND EXCLUSION.  When ``z0_m`` says the site sits
    meaningfully above sea level (:func:`sea_band_applies`), samples at
    or below ``FLAT_SITE_SEA_BAND_MAX_M`` are SEA SURFACE or VOID FILL
    and take no part in the percentiles OR the plane fit — the fit
    especially, because a plane regressed through land AND bay zeros
    measures the shoreline, not the airfield.  ``sea_excluded_frac`` is
    the share of otherwise-valid in-extent samples that fell in the
    band, and is reported whatever the outcome: at a site the exclusion
    empties, the fraction is the finding.

    S2b — THE DSM-STRUCTURE TRIM.  With ``relief_floor_m`` given, samples
    above ``median + FLAT_SITE_DSM_TRIM_FRACTION_OF_FLOOR * floor`` are
    dropped from the percentiles and the fit as well: the 3-arcsec
    sources are SURFACE models and a 93 m cell over a terminal reports
    the roof, which is not the ground the airport is graded to.  The
    cutoff is taken from the POST-SEA median — the central tendency
    these sites already get right — and the trimmed share is reported as
    ``dsm_trimmed_frac``.
    """
    empty = {"n": 0, "median_m": None, "p5_m": None, "p95_m": None,
             "relief_m": None, "slope_pct": None, "residual_std_m": None,
             "sea_excluded_frac": None, "dsm_trimmed_frac": None,
             "dsm_cutoff_m": None}
    if dem is None or extent_m is None or extent_m.is_empty:
        return empty
    try:
        import numpy as np
        from shapely import contains_xy
    except Exception:                                # pragma: no cover
        return empty

    alt = getattr(dem, "alt_dem", None)
    nx = int(getattr(dem, "nxdem", 0) or 0)
    ny = int(getattr(dem, "nydem", 0) or 0)
    if alt is None or nx < 2 or ny < 2:
        return empty
    x0, x1 = float(dem.x0), float(dem.x1)
    y0, y1 = float(dem.y0), float(dem.y1)
    step_lon = (x1 - x0) / (nx - 1)
    step_lat = (y1 - y0) / (ny - 1)
    if step_lon <= 0.0 or step_lat <= 0.0:
        return empty

    lat0, lon0 = float(anchor[0]), float(anchor[1])
    cos0 = math.cos(math.radians(lat0))
    if abs(cos0) < 1e-9:                             # pragma: no cover
        return empty

    def _to_ll(x_m, y_m):
        return (lat0 + math.degrees(y_m / _R_EARTH),
                lon0 + math.degrees(x_m / (_R_EARTH * cos0)))

    xmin, ymin, xmax, ymax = extent_m.bounds
    lat_lo, lon_lo = _to_ll(xmin, ymin)
    lat_hi, lon_hi = _to_ll(xmax, ymax)
    # Tile-relative degrees, exactly the frame ``dem.x0..x1`` is in.
    j0 = max(0, int(math.floor((lon_lo - tile_lon - x0) / step_lon)))
    j1 = min(nx - 1, int(math.ceil((lon_hi - tile_lon - x0) / step_lon)))
    i0 = max(0, int(math.floor((y1 - (lat_hi - tile_lat)) / step_lat)))
    i1 = min(ny - 1, int(math.ceil((y1 - (lat_lo - tile_lat)) / step_lat)))
    if j1 <= j0 or i1 <= i0:
        return empty

    window = np.asarray(alt[i0:i1 + 1, j0:j1 + 1], dtype=float)
    if window.size == 0:
        return empty
    lon_deg = tile_lon + x0 + np.arange(j0, j1 + 1) * step_lon
    lat_deg = tile_lat + y1 - np.arange(i0, i1 + 1) * step_lat
    x_m = np.radians(lon_deg - lon0) * _R_EARTH * cos0
    y_m = np.radians(lat_deg - lat0) * _R_EARTH
    grid_x, grid_y = np.meshgrid(x_m, y_m)

    keep = contains_xy(extent_m, grid_x, grid_y)
    nodata = getattr(dem, "nodata", None)
    if nodata is not None:
        keep &= window != float(nodata)
    keep &= np.isfinite(window)

    # S2a — the sea band.  Measured over the VALID in-extent samples, so
    # the fraction answers "how much of this airport's DEM testimony was
    # sea surface?" and not "how much of the bounding box was".
    valid_n = int(keep.sum())
    sea_excluded_frac = None
    if sea_band_applies(z0_m) and valid_n:
        sea = keep & (window <= float(_config.FLAT_SITE_SEA_BAND_MAX_M))
        sea_excluded_frac = round(float(int(sea.sum())) / valid_n, 4)
        keep &= ~sea

    if int(keep.sum()) < _MIN_DEM_SAMPLES:
        return dict(empty, sea_excluded_frac=sea_excluded_frac)

    # S2b — the DSM-structure trim, on what the sea band left behind.
    dsm_trimmed_frac = None
    dsm_cutoff = None
    if relief_floor_m is not None:
        land_n = int(keep.sum())
        dsm_cutoff = float(np.median(window[keep])) + (
            _config.FLAT_SITE_DSM_TRIM_FRACTION_OF_FLOOR
            * float(relief_floor_m))
        tall = keep & (window > dsm_cutoff)
        dsm_trimmed_frac = round(float(int(tall.sum())) / land_n, 4)
        dsm_cutoff = round(dsm_cutoff, 3)
        keep &= ~tall
        if int(keep.sum()) < _MIN_DEM_SAMPLES:
            return dict(empty, sea_excluded_frac=sea_excluded_frac,
                        dsm_trimmed_frac=dsm_trimmed_frac,
                        dsm_cutoff_m=dsm_cutoff)

    z = window[keep]
    px = grid_x[keep]
    py = grid_y[keep]
    p5, p95 = (float(v) for v in np.percentile(z, [5.0, 95.0]))
    design = np.column_stack([np.ones(z.size), px, py])
    try:
        coefficients, *_ = np.linalg.lstsq(design, z, rcond=None)
        slope_pct = 100.0 * math.hypot(float(coefficients[1]),
                                       float(coefficients[2]))
        residual_std = float((z - design @ coefficients).std())
    except Exception:                                # pragma: no cover
        slope_pct = None
        residual_std = None
    return {
        "n": int(z.size),
        "median_m": round(float(np.median(z)), 3),
        "p5_m": round(p5, 3),
        "p95_m": round(p95, 3),
        "relief_m": round(p95 - p5, 3),
        "slope_pct": (None if slope_pct is None else round(slope_pct, 4)),
        "residual_std_m": (None if residual_std is None
                           else round(residual_std, 3)),
        "sea_excluded_frac": sea_excluded_frac,
        "dsm_trimmed_frac": dsm_trimmed_frac,
        "dsm_cutoff_m": dsm_cutoff,
    }


# ──────────────────────────────────────────────────────────────────────
# S4 — pack-object consensus (confirmatory)
# ──────────────────────────────────────────────────────────────────────
def pack_seat_targets(patch_dir: str, icao: str) -> dict:
    """Non-below-grade seat targets from a prior post-mesh pad sidecar.

    Reads ``o4_object_foot_pads.json`` through ``object_pads``' OWN
    reader (one sidecar reader, never a second parser) and keeps each
    request's ``target_ground_metres`` — the elevation the pack asks the
    ground to be at.  BELOW-GRADE requests are excluded: an open-pit
    drainage basin's request is a trench floor, not a ground-level seat,
    and its object base sits ``FLAT_SITE_PACK_BELOW_GRADE_M`` or more
    under its own anchor datum.

    Returns ``{targets, n_total, n_below_grade, sidecar_version, path}``;
    ``targets`` is empty when no sidecar exists.
    """
    from . import object_pads as _object_pads

    out = {"targets": [], "n_total": 0, "n_below_grade": 0,
           "sidecar_version": 0, "path": None}
    if not patch_dir:
        return out
    path = _object_pads.sidecar_path(patch_dir)
    out["path"] = path
    payload = _object_pads.load_sidecar(path)
    if not payload:
        return out
    out["sidecar_version"] = _object_pads.sidecar_version(payload)
    floor = float(_config.FLAT_SITE_PACK_BELOW_GRADE_M)
    for block in (payload.get("airports") or ()):
        if not isinstance(block, dict):
            continue
        if str(block.get("icao") or "").upper() != str(icao or "").upper():
            continue
        for request in (block.get("requests") or ()):
            if not isinstance(request, dict):
                continue
            try:
                target = float(request["target_ground_metres"])
            except (KeyError, TypeError, ValueError):
                continue
            out["n_total"] += 1
            try:
                base_y = float(request.get("base_y"))
            except (TypeError, ValueError):
                base_y = 0.0
            if base_y <= -floor:
                out["n_below_grade"] += 1
                continue
            out["targets"].append(target)
    return out


def pack_consensus(targets: Sequence, z0_m) -> dict:
    """S4 — ``{n, median_m, spread_m, offset_m, pass}`` against ``Z0``.

    ``pass`` is ``None`` with no data (spec: absent data is ``no_data``,
    never a fail) and with no ``Z0`` to measure the offset against.
    """
    try:
        import numpy as np
    except Exception:                                # pragma: no cover
        return {"n": 0, "median_m": None, "spread_m": None,
                "offset_m": None, "pass": None}
    values = np.asarray([float(v) for v in (targets or ())], dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {"n": 0, "median_m": None, "spread_m": None,
                "offset_m": None, "pass": None}
    p5, p95 = (float(v) for v in np.percentile(values, [5.0, 95.0]))
    median = float(np.median(values))
    spread = p95 - p5
    if z0_m is None:
        offset = None
        verdict = None
    else:
        offset = abs(median - float(z0_m))
        verdict = bool(
            offset <= _config.FLAT_SITE_PACK_OFFSET_MAX_M
            and spread <= _config.FLAT_SITE_PACK_SPREAD_MAX_M)
    return {"n": int(values.size), "median_m": round(median, 3),
            "spread_m": round(spread, 3),
            "offset_m": (None if offset is None else round(offset, 3)),
            "pass": verdict}


# ──────────────────────────────────────────────────────────────────────
# The detector
# ──────────────────────────────────────────────────────────────────────
def classify_site(*, icao: str, cifp_elevations_m: Sequence, dem,
                  tile_lat: int, tile_lon: int, anchor, extent_m,
                  ring_m=None,
                  dem_meta: dict | None = None,
                  pack_targets: Sequence | None = None,
                  pack_meta: dict | None = None,
                  declared=None, declared_elevations=None) -> dict:
    """The ``site_class`` evidence record (spec section 2).  Report-only.

    Every field is evidence; ``verdict`` is the one summary:
    ``flat_candidate`` ⇔ S1 ∧ S2, ``lidar_credible`` when the DEM source
    is metre-credible (flat-candidacy not applicable), ``no_data`` when
    the instruments needed are absent, ``not_flat`` otherwise.
    """
    s1 = threshold_consensus(cifp_elevations_m)
    z0 = s1.get("z0_m")
    klass = source_class_for_dem(dem, icao=icao, dem_meta=dem_meta)
    floor_m = relief_floor_for_class(klass.get("class"))
    # S2a needs S1's consensus elevation and S2b needs the class's floor,
    # so the thresholds and the source class are both resolved BEFORE the
    # measurement and handed into it.  ``extent_m`` is the GATE extent
    # (pavement ∪ boundary); the ring is measured the same way and kept
    # as context with no gate power (v3 amendment (a)).
    relief = dem_relief(dem, tile_lat, tile_lon, anchor, extent_m,
                        z0_m=z0, relief_floor_m=floor_m)
    ring = (dem_relief(dem, tile_lat, tile_lon, anchor, ring_m,
                       z0_m=z0, relief_floor_m=floor_m)
            if ring_m is not None else {})

    offset_m = None
    if z0 is not None and relief.get("median_m") is not None:
        offset_m = round(abs(float(relief["median_m"]) - float(z0)), 3)

    s4 = pack_consensus(pack_targets, z0)
    if pack_meta:
        s4 = dict(s4, **{k: pack_meta[k] for k in
                         ("n_total", "n_below_grade", "sidecar_version")
                         if k in pack_meta})

    slope_ok = (relief.get("slope_pct") is not None
                and relief["slope_pct"] <= _config.FLAT_SITE_MAX_SLOPE_PCT)
    relief_ok = (floor_m is not None and relief.get("relief_m") is not None
                 and relief["relief_m"] <= floor_m)
    s2_pass = (None if (relief.get("n", 0) == 0 or floor_m is None)
               else bool(slope_ok and relief_ok))

    if s1["pass"] is None or relief.get("n", 0) == 0:
        auto_verdict = VERDICT_NO_DATA
    elif klass.get("class") == SOURCE_CLASS_LIDAR:
        auto_verdict = VERDICT_LIDAR_CREDIBLE
    elif s2_pass is None:
        auto_verdict = VERDICT_NO_DATA
    elif s1["pass"] and s2_pass:
        auto_verdict = VERDICT_FLAT_CANDIDATE
    else:
        auto_verdict = VERDICT_NOT_FLAT

    # (c) THE OWNER DECLARATION.  It overrides the VERDICT and nothing
    # else: every measurement above was taken in the detector's own
    # frame on the CIFP consensus, and ``auto_verdict`` keeps what the
    # detector would have said, so declaration and detection stay
    # auditable against each other forever.  The declared elevation is
    # carried for the MODE to grade to; absent one, Z0 stands.
    key = str(icao or "").upper()
    is_declared = key in (declared_flat_airports()
                          if declared is None
                          else {str(i).upper() for i in declared})
    declared_elevation = (declared_flat_elevations()
                          if declared_elevations is None
                          else dict(declared_elevations)).get(key)
    verdict = VERDICT_FLAT_DECLARED if is_declared else auto_verdict

    return {
        "icao": key,
        "verdict": verdict,
        "declared": is_declared,
        "auto_verdict": auto_verdict,
        "declared_elevation_m": (
            None if not is_declared else
            (z0 if declared_elevation is None else declared_elevation)),
        "z0_m": z0,
        "s1_spread_m": s1["spread_m"],
        "s1_threshold_count": s1["n"],
        "s1_pass": s1["pass"],
        "s2_slope_pct": relief.get("slope_pct"),
        "s2_relief_m": relief.get("relief_m"),
        "s2_source_class": klass.get("class"),
        "s2_source_resolution_m": klass.get("resolution_m"),
        "s2_source_whence": klass.get("whence"),
        "s2_relief_floor_m": floor_m,
        "s2_residual_std_m": relief.get("residual_std_m"),
        "s2_dem_median_m": relief.get("median_m"),
        "s2_dem_samples": relief.get("n", 0),
        # S2a: the share of valid in-extent DEM samples that were SEA
        # SURFACE / VOID FILL and took no part in the statistics above.
        # None means the exclusion did not run (no Z0, or a site at or
        # below sea level whose zeros are plausible terrain).
        "s2_sea_excluded_frac": relief.get("sea_excluded_frac"),
        # S2b: the share of LAND samples cut as DSM structure, and the
        # elevation above which a sample was treated as a roof.
        "s2_dsm_trimmed_frac": relief.get("dsm_trimmed_frac"),
        "s2_dsm_cutoff_m": relief.get("dsm_cutoff_m"),
        # (a) THE MARGIN RING — audit context, NO GATE POWER.  Kept so
        # "what is the mode's feather going to have to cross?" stays
        # answerable, and so a future ruling that re-arms the ring has
        # the numbers it would need.
        "s2_ring_samples": ring.get("n", 0),
        "s2_ring_median_m": ring.get("median_m"),
        "s2_ring_relief_m": ring.get("relief_m"),
        "s2_ring_slope_pct": ring.get("slope_pct"),
        "s2_ring_sea_excluded_frac": ring.get("sea_excluded_frac"),
        "s2_ring_dsm_trimmed_frac": ring.get("dsm_trimmed_frac"),
        "s2_pass": s2_pass,
        "s3_offset_m": offset_m,
        "s4": s4,
    }


def detect_for_layout(layout, *, icao: str, apt, to_m, dem,
                      tile_lat: int, tile_lon: int,
                      patch_dir: str | None = None,
                      xplane_root: str | None = None) -> dict | None:
    """Run the detector at the pipeline's DEM-in-hand point.  Report-only.

    Returns the ``site_class`` record (also stored on the layout), or
    ``None`` when the layout has no anchor to measure about.
    """
    if layout is None or getattr(layout, "anchor", None) is None:
        return None
    extent_m, ring_m = extents_from_apt(apt, to_m)
    elevations = (cifp_threshold_elevations(xplane_root, icao)
                  if xplane_root else [])
    pack = ({"targets": [], "n_total": 0, "n_below_grade": 0,
             "sidecar_version": 0, "path": None} if not patch_dir
            else pack_seat_targets(patch_dir, icao))
    record = classify_site(
        icao=icao, cifp_elevations_m=elevations, dem=dem,
        tile_lat=tile_lat, tile_lon=tile_lon, anchor=layout.anchor,
        extent_m=extent_m, ring_m=ring_m,
        dem_meta=getattr(layout, "dem_inset_provenance", None),
        pack_targets=pack["targets"], pack_meta=pack)
    try:
        layout.site_class = record
    except AttributeError:                           # pragma: no cover
        pass
    return record


def format_log_line(record: dict | None) -> str:
    """The one verbosity-0 line the detector prints per airport."""
    if not record:
        return "  [flat-site] (no record)"
    icao = record.get("icao") or "????"
    verdict = record.get("verdict") or VERDICT_NO_DATA

    def _num(value, digits=2, unit=""):
        return "?" if value is None else f"{float(value):.{digits}f}{unit}"

    sea = record.get("s2_sea_excluded_frac")
    sea_text = ("" if sea is None
                else f", sea-excluded {100.0 * float(sea):.0f} %")
    trim = record.get("s2_dsm_trimmed_frac")
    if trim is not None:
        sea_text += f", dsm-trimmed {100.0 * float(trim):.0f} %"
    declared_text = ("" if not record.get("declared") else
                     f" [DECLARED by owner; detector said "
                     f"{record.get('auto_verdict')}]")
    s4 = record.get("s4") or {}
    if s4.get("pass") is None:
        pack = "no_data"
    else:
        pack = (f"{'ok' if s4['pass'] else 'no'} "
                f"(n={s4.get('n')}, off {_num(s4.get('offset_m'))} m, "
                f"spread {_num(s4.get('spread_m'))} m)")
    return (
        f"  [flat-site] {icao}: {verdict} — "
        f"Z0 {_num(record.get('z0_m'))} m "
        f"(CIFP spread {_num(record.get('s1_spread_m'))} m over "
        f"{record.get('s1_threshold_count', 0)} threshold(s)) | "
        f"DEM {record.get('s2_source_class') or '?'}"
        f"[{record.get('s2_source_whence') or '?'}] relief "
        f"{_num(record.get('s2_relief_m'))} m vs floor "
        f"{_num(record.get('s2_relief_floor_m'), 1)} m, slope "
        f"{_num(record.get('s2_slope_pct'), 3)} %{sea_text} | "
        f"DEM−Z0 {_num(record.get('s3_offset_m'))} m | pack {pack}"
        + declared_text)
