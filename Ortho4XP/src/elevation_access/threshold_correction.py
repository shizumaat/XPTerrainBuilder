"""Correct an airport inset to its surveyed runway thresholds (#2089).

Owner decision 2026-11-14T20:27Z (option 1): when a high-resolution DEM
disagrees with the CIFP runway thresholds, shift it with a smooth
correction fitted to those thresholds, at every airport.  Spec:
``docs/specs/2089-inset-threshold-correction-spec.md``.

The correction is ARITHMETIC, not data (the flat-site precedent): it is
never written to ``Elevation_data`` and never cached.  This module holds
the one reader (the threshold disc), the one bar (:data:`BAR_M`), the
verdict and the field; ``O4_Airport_Elevation_Insets`` plans it when the
working grid is final and adds it in the bake; the harness judges insets
with the same reader.  numpy / scipy / GDAL only -- no ``O4_*`` import.
"""
from __future__ import annotations

import math

__all__ = [
    "BAR_M", "CAP_M", "MIN_WITNESSES", "DISC_RADIUS_M", "SOFTEN_M",
    "TAPER_M", "BASE_SIGMA_M", "BASE_TOL_M", "BASE_PRIOR", "MATERIALITY_M",
    "MODEL_B", "disc_median_m", "threshold_readings", "verdict",
    "taper", "correction_field", "provenance_record",
]

#: The "inset disagrees with its thresholds" bar (owner §10 Q2: 3.0 m).
#: The harness's ``INSET_ARP_SANITY["warn_abs_delta_m"]`` reads it.
BAR_M = 3.0
#: Above this residual the disagreement is datum- or CIFP-class: the inset
#: is REFUSED a correction and reported (owner §10 Q3).
CAP_M = 10.0
#: At least two thresholds must witness the inset.
MIN_WITNESSES = 2
#: The threshold disc radius (the harness's ``threshold_disc_radius_m``).
DISC_RADIUS_M = 15.0
#: Inverse-distance softening length: w = 1 / (d^2 + SOFTEN_M^2).
SOFTEN_M = 15.0
#: The correction rises from zero at the inset box edge to full this far in.
TAPER_M = 300.0
#: Model B: Gaussian low-pass of the base-minus-inset difference.
BASE_SIGMA_M = 150.0
#: Model B: base cells outside the surveyed range by more than this are not
#: evidence, and the base must reproduce every threshold within it.
BASE_TOL_M = 1.5
#: Model B: weight of the threshold field where the base gives no evidence.
BASE_PRIOR = 0.02
#: A field smaller than this everywhere is no correction.
MATERIALITY_M = 0.01
#: Owner §10 Q1: the base DEM may witness the shape of the correction.
MODEL_B = True

_M_PER_DEG_LAT = 111_320.0


def disc_median_m(inset_path, lat, lon, radius_m, at_least_one_cell=False):
    """``(median_m, cells)`` of the valid cells of an EPSG:4326 raster
    whose centres lie within ``radius_m`` of (``lat``, ``lon``);
    ``(None, 0)`` when none does (off the raster, or all no-data).
    ``at_least_one_cell`` widens the disc to half a cell diagonal, so a
    small disc on a coarse inset still holds the cell under the point."""
    import numpy
    from osgeo import gdal

    dataset = gdal.Open(str(inset_path))
    if dataset is None:
        return (None, 0)
    (x0, dx, _rx, y0, _ry, dy) = dataset.GetGeoTransform()
    band = dataset.GetRasterBand(1)
    nodata = band.GetNoDataValue()
    m_lon = _M_PER_DEG_LAT * math.cos(math.radians(lat))
    if at_least_one_cell:
        radius_m = max(radius_m, math.hypot(abs(dx) * m_lon,
                                            abs(dy) * _M_PER_DEG_LAT) / 2.0)
    half_cols = int(math.ceil(radius_m / (abs(dx) * m_lon))) + 1
    half_rows = int(math.ceil(radius_m / (abs(dy) * _M_PER_DEG_LAT))) + 1
    col = int((lon - x0) / dx)
    row = int((lat - y0) / dy)
    c0, c1 = max(col - half_cols, 0), min(col + half_cols + 1,
                                          dataset.RasterXSize)
    r0, r1 = max(row - half_rows, 0), min(row + half_rows + 1,
                                          dataset.RasterYSize)
    if c0 >= c1 or r0 >= r1:
        return (None, 0)
    values = band.ReadAsArray(c0, r0, c1 - c0, r1 - r0).astype(numpy.float64)
    dataset = None
    rows, cols = numpy.mgrid[r0:r1, c0:c1]
    distance = numpy.hypot((y0 + (rows + 0.5) * dy - lat) * _M_PER_DEG_LAT,
                           (x0 + (cols + 0.5) * dx - lon) * m_lon)
    valid = (distance <= radius_m) & numpy.isfinite(values)
    if nodata is not None:
        valid &= values != nodata
    valid &= values != -32768.0
    if not valid.any():
        return (None, 0)
    return (float(numpy.median(values[valid])), int(valid.sum()))


def threshold_readings(inset_path, thresholds, radius_m=DISC_RADIUS_M):
    """Every CIFP ``RW*`` threshold of ``thresholds``
    (``cifp.read_threshold_dicts`` shape) read on the inset FILE, in
    designator order: ``[{runway, lat, lon, elevation_m, inset_m, cells,
    residual_m}]`` with residual = CIFP - inset disc median.  A threshold
    whose disc holds no valid cell is not a witness and is left out."""
    out = []
    for runway in sorted(thresholds or {}):
        if not str(runway).upper().startswith("RW"):
            continue
        pin = thresholds[runway]
        (median, cells) = disc_median_m(inset_path, pin["lat"], pin["lon"],
                                        radius_m, at_least_one_cell=True)
        if median is None:
            continue
        elevation = float(pin["elevation_m"])
        out.append({"runway": runway, "lat": float(pin["lat"]),
                    "lon": float(pin["lon"]), "elevation_m": elevation,
                    "inset_m": median, "cells": cells,
                    "residual_m": elevation - median})
    return out


def verdict(readings):
    """``{"status": "none"|"apply"|"refused", "why"}`` for one inset's
    readings (spec §3).  No outlier rejection: the thresholds are hard pins
    in the solve, so the ground follows the airside there."""
    if len(readings) < MIN_WITNESSES:
        return {"status": "none",
                "why": f"{len(readings)} threshold witness(es) "
                       f"(< {MIN_WITNESSES})"}
    worst = max(abs(r["residual_m"]) for r in readings)
    if worst <= BAR_M:
        return {"status": "none",
                "why": f"max |residual| {worst:.2f} m within {BAR_M} m"}
    if worst > CAP_M:
        return {"status": "refused",
                "why": f"max |residual| {worst:.2f} m over {CAP_M} m "
                       f"(datum- or CIFP-class disagreement)"}
    return {"status": "apply",
            "why": f"max |residual| {worst:.2f} m over {BAR_M} m"}


def taper(distance_to_edge_m):
    """tau = t^2 (3 - 2t), t = clip(d / TAPER_M, 0, 1): zero at the inset
    box edge, full :data:`TAPER_M` inside it."""
    import numpy
    t = numpy.clip(numpy.asarray(distance_to_edge_m, dtype=numpy.float64)
                   / TAPER_M, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _idw(points, values, x_m, y_m):
    """The softened inverse-distance blend of ``values`` at ``points``:
    exact at the points, bounded by the values."""
    import numpy
    numerator = numpy.zeros(x_m.shape)
    denominator = numpy.zeros(x_m.shape)
    for ((px, py), value) in zip(points, values, strict=True):
        weight = 1.0 / ((x_m - px) ** 2 + (y_m - py) ** 2 + SOFTEN_M ** 2)
        numerator += weight * value
        denominator += weight
    return numerator / denominator


def _at_points(field, points, x_m, y_m):
    """``field`` at the cell nearest each point."""
    import numpy
    out = []
    for (px, py) in points:
        index = numpy.argmin((x_m - px) ** 2 + (y_m - py) ** 2)
        out.append(float(field.flat[index]))
    return out


def _base_witness(residuals, points, x_m, y_m, inset_values, valid, base,
                  base_valid, pixel_m, lo, hi, prior):
    """Model B: ``(S, e_i)`` -- the low-passed base-minus-inset difference
    on the cells whose difference lies in the surveyed range, pulled to
    the threshold field ``prior`` where the base gives no evidence, and its
    misfit at each threshold; None when no base cell is evidence (a base
    that is all canopy witnesses nothing)."""
    import numpy
    from scipy import ndimage

    difference = numpy.asarray(base, dtype=numpy.float64) - inset_values
    evidence = (valid & base_valid & (difference >= lo - BASE_TOL_M)
                & (difference <= hi + BASE_TOL_M))
    if not evidence.any():
        return None
    sigma = (BASE_SIGMA_M / pixel_m[0], BASE_SIGMA_M / pixel_m[1])
    numerator = ndimage.gaussian_filter(
        numpy.where(evidence, difference, 0.0), sigma, mode="constant")
    denominator = ndimage.gaussian_filter(
        evidence.astype(numpy.float64), sigma, mode="constant")
    shape = (numerator + BASE_PRIOR * prior) / (denominator + BASE_PRIOR)
    misfit = [r - s for (r, s) in
              zip(residuals, _at_points(shape, points, x_m, y_m), strict=True)]
    return (shape, misfit)


def correction_field(residuals, points, x_m, y_m, inset_values, valid,
                     distance_to_edge_m, pixel_m, base=None,
                     base_valid=None):
    """``(tau * C, model, base_fit)`` on a bake window, in metres.

    ``residuals`` / ``points``: each witness's r_i and its (x, y) in the
    same metric frame as the cell centres ``x_m`` / ``y_m``.  ``pixel_m``
    is ``(row_m, col_m)``.  ``base`` (with ``base_valid``) is the pure
    base DEM on the same window, or None: model B is tried only with it
    and only under :data:`MODEL_B`.  ``base_fit`` is each witness's model
    B misfit e_i, or None when model B was not tried or the base held no
    evidence.  ``model`` is
    ``"base_witness"`` or ``"thresholds"``."""
    import numpy

    inset_values = numpy.asarray(inset_values, dtype=numpy.float64)
    threshold_field = _idw(points, residuals, x_m, y_m)
    lo = min(0.0, min(residuals))
    hi = max(0.0, max(residuals))
    field = threshold_field
    model = "thresholds"
    base_fit = None
    witness = None
    if MODEL_B and base is not None:
        witness = _base_witness(
            residuals, points, x_m, y_m, inset_values, valid, base,
            base_valid, pixel_m, lo, hi, threshold_field)
    if witness is not None:
        (shape, base_fit) = witness
        if max(abs(e) for e in base_fit) <= BASE_TOL_M:
            field = numpy.clip(shape + _idw(points, base_fit, x_m, y_m),
                               lo, hi)
            model = "base_witness"
    return (taper(distance_to_edge_m) * field, model, base_fit)


def provenance_record(plan, model=None, applied=None, base_fit=None):
    """The ``threshold_correction`` record (spec §5) of one planned inset:
    ``plan`` carries ``status``, ``why`` and ``readings``; ``applied`` is
    the field actually added on valid cells (None when nothing was)."""
    readings = plan.get("readings") or []
    record = {"status": plan.get("status"), "model": model,
              "why": plan.get("why"), "bar_m": BAR_M,
              "readings": [
                  {"runway": r["runway"],
                   "elevation_m": round(r["elevation_m"], 3),
                   "inset_m": round(r["inset_m"], 3),
                   "residual_m": round(r["residual_m"], 3),
                   "base_fit_m": (None if base_fit is None
                                  else round(base_fit[i], 3))}
                  for (i, r) in enumerate(readings)],
              "applied_m": None, "taper_m": TAPER_M}
    if applied is not None and getattr(applied, "size", 0):
        record["applied_m"] = [round(float(applied.min()), 3),
                               round(float(applied.max()), 3)]
    return record
